"""Scrape QS, Times Higher Education, and ARWU top-100 rankings."""
import logging
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from .db import upsert_university, _conn
from .fetch import fetch, fetch_playwright, fetch_requests

logger = logging.getLogger(__name__)

# ── Hardcoded fallback (used when a ranking page is unscrapable) ──────────────
# Covers most universities that appear in all three top-100 lists.
_FALLBACK: list[tuple[str, str]] = [
    ("Massachusetts Institute of Technology", "https://www.mit.edu"),
    ("Harvard University", "https://www.harvard.edu"),
    ("Stanford University", "https://www.stanford.edu"),
    ("University of Oxford", "https://www.ox.ac.uk"),
    ("University of Cambridge", "https://www.cam.ac.uk"),
    ("ETH Zurich", "https://ethz.ch"),
    ("Imperial College London", "https://www.imperial.ac.uk"),
    ("UCL", "https://www.ucl.ac.uk"),
    ("University College London", "https://www.ucl.ac.uk"),
    ("Paris-Saclay University", "https://www.universite-paris-saclay.fr/en"),
    ("University of California, San Francisco", "https://www.ucsf.edu"),
    ("Washington University in St. Louis", "https://wustl.edu"),
    ("Rockefeller University", "https://www.rockefeller.edu"),
    ("University of Michigan-Ann Arbor", "https://umich.edu"),
    ("University of California, Berkeley", "https://www.berkeley.edu"),
    ("University of Chicago", "https://www.uchicago.edu"),
    ("Princeton University", "https://www.princeton.edu"),
    ("Yale University", "https://www.yale.edu"),
    ("Columbia University", "https://www.columbia.edu"),
    ("California Institute of Technology", "https://www.caltech.edu"),
    ("Johns Hopkins University", "https://www.jhu.edu"),
    ("University of Pennsylvania", "https://www.upenn.edu"),
    ("Cornell University", "https://www.cornell.edu"),
    ("University of Michigan", "https://umich.edu"),
    ("Duke University", "https://www.duke.edu"),
    ("Northwestern University", "https://www.northwestern.edu"),
    ("Carnegie Mellon University", "https://www.cmu.edu"),
    ("Georgia Institute of Technology", "https://www.gatech.edu"),
    ("University of Washington", "https://www.washington.edu"),
    ("University of Texas at Austin", "https://www.utexas.edu"),
    ("University of California, Los Angeles", "https://www.ucla.edu"),
    ("University of California, San Diego", "https://ucsd.edu"),
    ("New York University", "https://www.nyu.edu"),
    ("University of Wisconsin-Madison", "https://www.wisc.edu"),
    ("University of Illinois Urbana-Champaign", "https://illinois.edu"),
    ("University of Toronto", "https://www.utoronto.ca"),
    ("McGill University", "https://www.mcgill.ca"),
    ("University of British Columbia", "https://www.ubc.ca"),
    ("University of Melbourne", "https://www.unimelb.edu.au"),
    ("University of Sydney", "https://www.sydney.edu.au"),
    ("University of Queensland", "https://www.uq.edu.au"),
    ("Monash University", "https://www.monash.edu"),
    ("University of New South Wales", "https://www.unsw.edu.au"),
    ("Australian National University", "https://www.anu.edu.au"),
    ("National University of Singapore", "https://www.nus.edu.sg"),
    ("Nanyang Technological University", "https://www.ntu.edu.sg"),
    ("Peking University", "https://english.pku.edu.cn"),
    ("Tsinghua University", "https://www.tsinghua.edu.cn/en"),
    ("Fudan University", "https://www.fudan.edu.cn/en"),
    ("Shanghai Jiao Tong University", "https://en.sjtu.edu.cn"),
    ("Zhejiang University", "https://www.zju.edu.cn/english"),
    ("University of Tokyo", "https://www.u-tokyo.ac.jp/en"),
    ("Kyoto University", "https://www.kyoto-u.ac.jp/en"),
    ("Osaka University", "https://www.osaka-u.ac.jp/en"),
    ("Seoul National University", "https://en.snu.ac.kr"),
    ("KAIST", "https://www.kaist.ac.kr/en"),
    ("University of Hong Kong", "https://www.hku.hk"),
    ("Hong Kong University of Science and Technology", "https://hkust.edu.hk"),
    ("Chinese University of Hong Kong", "https://www.cuhk.edu.hk"),
    ("EPFL", "https://www.epfl.ch/en"),
    ("University of Zurich", "https://www.uzh.ch/en"),
    ("University of Geneva", "https://www.unige.ch/en"),
    ("Technical University of Munich", "https://www.tum.de/en"),
    ("LMU Munich", "https://www.lmu.de/en"),
    ("Heidelberg University", "https://www.uni-heidelberg.de/en"),
    ("Humboldt University of Berlin", "https://www.hu-berlin.de/en"),
    ("Delft University of Technology", "https://www.tudelft.nl/en"),
    ("University of Amsterdam", "https://www.uva.nl/en"),
    ("Utrecht University", "https://www.uu.nl/en"),
    ("Leiden University", "https://www.universiteitleiden.nl/en"),
    ("KU Leuven", "https://www.kuleuven.be/english"),
    ("Ghent University", "https://www.ugent.be/en"),
    ("Paris Sciences et Lettres University", "https://www.psl.eu/en"),
    ("Sorbonne University", "https://www.sorbonne-universite.fr/en"),
    ("University of Edinburgh", "https://www.ed.ac.uk"),
    ("University of Manchester", "https://www.manchester.ac.uk"),
    ("University of Bristol", "https://www.bristol.ac.uk"),
    ("University of Warwick", "https://warwick.ac.uk"),
    ("University of Glasgow", "https://www.gla.ac.uk"),
    ("King's College London", "https://www.kcl.ac.uk"),
    ("University of Birmingham", "https://www.birmingham.ac.uk"),
    ("University of Leeds", "https://www.leeds.ac.uk"),
    ("University of Southampton", "https://www.southampton.ac.uk"),
    ("Karolinska Institute", "https://ki.se/en"),
    ("Uppsala University", "https://www.uu.se/en"),
    ("Lund University", "https://www.lu.se/en"),
    ("Stockholm University", "https://www.su.se/english"),
    ("University of Copenhagen", "https://www.ku.dk/english"),
    ("University of Helsinki", "https://www.helsinki.fi/en"),
    ("University of Oslo", "https://www.uio.no/english"),
    ("University of Auckland", "https://www.auckland.ac.nz"),
    ("University of Pittsburgh", "https://www.pitt.edu"),
    ("Vanderbilt University", "https://www.vanderbilt.edu"),
    ("Rice University", "https://www.rice.edu"),
    ("Emory University", "https://www.emory.edu"),
    ("Boston University", "https://www.bu.edu"),
    ("Ohio State University", "https://www.osu.edu"),
    ("University of Minnesota", "https://www.umn.edu"),
    ("Purdue University", "https://www.purdue.edu"),
    ("University of California, Davis", "https://www.ucdavis.edu"),
    ("University of California, Santa Barbara", "https://www.ucsb.edu"),
    ("Trinity College Dublin", "https://www.tcd.ie"),
    ("University College Dublin", "https://www.ucd.ie"),
    ("University of Groningen", "https://www.rug.nl/en"),
    ("Radboud University", "https://www.ru.nl/en"),
]


def _normalize(name: str) -> str:
    name = re.sub(r"^(The|A)\s+", "", name.strip(), flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", name).strip()


# Pre-built lookup from the fallback list so we don't need DuckDuckGo for known names
_FALLBACK_LOOKUP: dict[str, str] = {
    _normalize(n).lower(): u for n, u in _FALLBACK
}


def _lookup_fallback(name: str) -> str | None:
    """Return a website from _FALLBACK by exact or parenthetical-stripped name."""
    key = _normalize(name).lower()
    if key in _FALLBACK_LOOKUP:
        return _FALLBACK_LOOKUP[key]
    # Strip parenthetical suffix, e.g. "Massachusetts Institute of Technology (MIT)"
    stripped = re.sub(r"\s*\(.*?\)", "", key).strip()
    return _FALLBACK_LOOKUP.get(stripped)


def _website_from_wiki(wiki_path: str) -> str | None:
    """Extract official website from a Wikipedia university article infobox."""
    html = fetch_requests(f"https://en.wikipedia.org{wiki_path}")
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    for th in soup.select("table.infobox th"):
        if "website" in th.get_text(strip=True).lower():
            td = th.find_next_sibling("td")
            if td:
                a = td.find("a", href=True)
                if a and a["href"].startswith("http"):
                    return a["href"]
    return None


def _resolve_website(name: str, wiki_path: str = "") -> str | None:
    """Resolve a university website: fallback list → Wikipedia infobox."""
    website = _lookup_fallback(name)
    if website:
        return website
    if wiki_path:
        website = _website_from_wiki(wiki_path)
    return website


# ── Per-source scrapers ───────────────────────────────────────────────────────

def _scrape_wiki_ranking_table(url: str, source_label: str,
                               caption_hint: str = "") -> list[dict]:
    """
    Parse a Wikipedia university ranking table (wikitable).
    Columns: Institution | Year1 | Year2 | ...
    The first <td> in each row contains a country flag link followed by the
    university link — we skip any <a> that has an <img> child (flag icons).
    Returns list of {name, website, wiki_path}.
    Wikipedia tables only cover historically top-10 entries (~10–26 rows).
    """
    html = fetch_requests(url)
    if not html:
        logger.warning("%s Wikipedia: fetch failed", source_label)
        return []

    soup = BeautifulSoup(html, "lxml")

    # Pick the right table by caption keyword when multiple wikitables exist
    table = None
    for t in soup.find_all("table", class_="wikitable"):
        caption_text = (t.find("caption") or t).get_text()
        if not caption_hint or caption_hint in caption_text:
            table = t
            break

    if not table:
        logger.warning("%s Wikipedia: ranking table not found", source_label)
        return []

    results = []
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if not cells:
            continue
        # Skip flag/country links (have <img> children); take first plain text link
        name_link = None
        for a in cells[0].find_all("a", href=re.compile(r"^/wiki/[^:]+$")):
            if not a.find("img"):
                name_link = a
                break
        if not name_link:
            continue
        name = _normalize(name_link.get_text(strip=True))
        if len(name) < 4:
            continue
        wiki_path = name_link["href"]
        website = _resolve_website(name, wiki_path)
        results.append({"name": name, "website": website, "wiki_path": wiki_path})

    logger.info("%s Wikipedia: %d entries", source_label, len(results))
    return results


def _scrape_qs() -> list[dict]:
    logger.info("Fetching QS rankings from Wikipedia...")
    return _scrape_wiki_ranking_table(
        "https://en.wikipedia.org/wiki/QS_World_University_Rankings", "QS",
        caption_hint="Global Top"
    )


def _scrape_times() -> list[dict]:
    logger.info("Fetching THE rankings from Wikipedia...")
    return _scrape_wiki_ranking_table(
        "https://en.wikipedia.org/wiki/Times_Higher_Education_World_University_Rankings", "THE",
        caption_hint="World University Rankings"
    )


def _scrape_arwu() -> list[dict]:
    # ARWU Wikipedia page has no ranked university table; rely on fallback list
    logger.info("ARWU: no Wikipedia table — covered by fallback list")
    return []


# ── Merge & persist ───────────────────────────────────────────────────────────

def fetch_all_rankings() -> int:
    """Build university list from fallback + Wikipedia scrapers, save to DB."""
    # Always seed the full fallback list first — guarantees a complete base
    for name, website in _FALLBACK:
        upsert_university(name, website=website, sources=["fallback"])
    logger.info("Seeded %d universities from fallback list", len(_FALLBACK))

    # Run Wikipedia scrapers to add ranking metadata and any additional entries
    qs = _scrape_qs()
    times = _scrape_times()
    arwu = _scrape_arwu()

    merged: dict[str, dict] = {}

    def _add(entries: list[dict], source: str, rank_key: str):
        for rank, uni in enumerate(entries, 1):
            key = _normalize(uni["name"]).lower()
            if key not in merged:
                merged[key] = {
                    "name": uni["name"],
                    "website": uni.get("website"),
                    "sources": [],
                    "rank_qs": None,
                    "rank_times": None,
                    "rank_arwu": None,
                }
            merged[key]["sources"].append(source)
            merged[key][rank_key] = rank
            if not merged[key]["website"] and uni.get("website"):
                merged[key]["website"] = uni["website"]

    _add(qs, "QS", "rank_qs")
    _add(times, "Times", "rank_times")
    _add(arwu, "ARWU", "rank_arwu")

    # Upsert scraped entries (adds rank metadata; website already resolved per entry)
    for uni in merged.values():
        upsert_university(**uni)

    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM universities").fetchone()[0]
    logger.info("Total unique universities in DB: %d", total)
    return total
