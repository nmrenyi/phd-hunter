"""Scrape QS, Times Higher Education, and ARWU top-100 rankings."""
import logging
import re

from bs4 import BeautifulSoup

from .db import upsert_university
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
    ("ETH Zurich", "https://ethz.ch/en"),
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


def _search_website(name: str) -> str | None:
    """DuckDuckGo fallback to find a university's homepage."""
    query = f"{name} official university website"
    html = fetch_requests(f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}")
    if not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    el = soup.select_one(".result__url")
    if el:
        raw = el.get_text(strip=True)
        if not raw.startswith("http"):
            raw = "https://" + raw
        return raw
    return None


# ── Per-source scrapers ───────────────────────────────────────────────────────

def _scrape_qs() -> list[dict]:
    logger.info("Fetching QS rankings...")
    url = "https://www.topuniversities.com/world-university-rankings/2025"
    html = fetch_playwright(url, wait_ms=3500)
    if not html:
        logger.warning("QS: page fetch failed")
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    # QS renders rows as <tr> elements with a data attribute or named link
    rows = (
        soup.select("tr.uni-link")
        or soup.select("div.uni-item")
        or soup.select("table tbody tr")
    )
    for row in rows[:100]:
        name_el = (
            row.select_one(".uni-name")
            or row.select_one("a[href*='/universities/']")
            or row.select_one("td:nth-child(2)")
        )
        if not name_el:
            continue
        name = _normalize(name_el.get_text(strip=True))
        if len(name) < 4:
            continue
        link = row.select_one("a[href^='http']")
        website = link["href"] if link else None
        results.append({"name": name, "website": website})

    logger.info("QS: %d entries", len(results))
    return results


def _scrape_times() -> list[dict]:
    logger.info("Fetching Times Higher Education rankings...")
    url = "https://www.timeshighereducation.com/world-university-rankings/2024/world-ranking"
    html = fetch_playwright(url, wait_ms=4000)
    if not html:
        logger.warning("THE: page fetch failed")
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    rows = (
        soup.select("tr.ranking-institution-row")
        or soup.select("[data-name]")
        or soup.select("table tbody tr")
    )
    for row in rows[:100]:
        name = (
            row.get("data-name")
            or (row.select_one(".ranking-institution-title") or {}).get_text(strip=True)  # type: ignore[operator]
            or ""
        )
        name = _normalize(name)
        if len(name) < 4:
            continue
        link = row.select_one("a[href^='http']")
        website = link["href"] if link else None
        results.append({"name": name, "website": website})

    logger.info("THE: %d entries", len(results))
    return results


def _scrape_arwu() -> list[dict]:
    logger.info("Fetching ARWU rankings...")
    url = "https://www.shanghairanking.com/rankings/arwu/2024"
    html = fetch(url) or fetch_playwright(url, wait_ms=2500)
    if not html:
        logger.warning("ARWU: page fetch failed")
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []

    rows = soup.select("tbody tr") or soup.select(".rk-table-item")
    for row in rows[:100]:
        name_el = (
            row.select_one(".univ-name")
            or row.select_one("a.university-name")
            or row.select_one("td:nth-child(2) a")
            or row.select_one("td:nth-child(2)")
        )
        if not name_el:
            continue
        name = _normalize(name_el.get_text(strip=True))
        if len(name) < 4:
            continue
        link = row.select_one("a[href^='http']")
        website = link["href"] if link else None
        results.append({"name": name, "website": website})

    logger.info("ARWU: %d entries", len(results))
    return results


# ── Merge & persist ───────────────────────────────────────────────────────────

def fetch_all_rankings() -> int:
    """Scrape all three ranking sources, merge, deduplicate, save to DB."""
    qs = _scrape_qs()
    times = _scrape_times()
    arwu = _scrape_arwu()

    # If all scrapers failed, fall back to hardcoded list
    if not qs and not times and not arwu:
        logger.warning("All ranking scrapers failed — using hardcoded fallback list")
        for name, website in _FALLBACK:
            upsert_university(name, website=website, sources=["fallback"])
        return len(_FALLBACK)

    merged: dict[str, dict] = {}

    def _add(entries: list[dict], source: str, rank_key: str):
        for rank, uni in enumerate(entries, 1):
            key = uni["name"].lower()
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

    # Fill in missing websites
    for uni in merged.values():
        if not uni["website"]:
            logger.info("Looking up website for %s", uni["name"])
            uni["website"] = _search_website(uni["name"])

    for uni in merged.values():
        upsert_university(**uni)

    logger.info("Total unique universities saved: %d", len(merged))
    return len(merged)
