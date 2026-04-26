"""Crawl each university: find faculty pages, extract professors, extract PhD programs."""
import json
import logging

from .db import (
    get_pending_universities,
    phd_page_is_done,
    professor_is_done,
    save_phd_page,
    save_professor,
    set_university_crawling,
    set_university_status,
    touch_phd_page,
    touch_professor,
)
from .fetch import clean, fetch, same_domain
from .llm import call
from .prompts import (
    ENTRY_POINTS_SYS,
    ENTRY_POINTS_USER,
    MATCH_SYS,
    MATCH_USER,
    PHD_EXTRACT_SYS,
    PHD_EXTRACT_USER,
    PROF_EXTRACT_SYS,
    PROF_EXTRACT_USER,
    PROF_LINKS_SYS,
    PROF_LINKS_USER,
)

logger = logging.getLogger(__name__)

_MAX_PROF_URLS_PER_UNI = 80


# ── Individual page processors ────────────────────────────────────────────────

def _process_professor(uni_id: int, uni_name: str, url: str):
    if professor_is_done(url):
        return
    touch_professor(uni_id, url)
    try:
        html = fetch(url)
        if not html:
            return
        text, _ = clean(html, url)

        prof = call(PROF_EXTRACT_SYS, PROF_EXTRACT_USER.format(url=url, text=text))
        # Guard: LLM must return a dict, not a list or None
        if not isinstance(prof, dict) or prof.get("skip") or not prof.get("name"):
            return

        match = call(
            MATCH_SYS,
            MATCH_USER.format(
                name=prof.get("name", ""),
                title=prof.get("title", ""),
                department=prof.get("department", ""),
                university=uni_name,
                research_summary=prof.get("research_summary", ""),
            ),
        )

        score = 0
        reason = ""
        if isinstance(match, dict) and isinstance(match.get("score"), int):
            score = max(1, min(5, match["score"]))  # clamp to valid range
            reason = match.get("reason", "")

        save_professor(
            page_url=url,
            name=prof.get("name", ""),
            title=prof.get("title", ""),
            department=prof.get("department", ""),
            research_summary=prof.get("research_summary", ""),
            match_score=score,
            match_reason=reason,
            contact=prof.get("contact", ""),
        )
        if score >= 4:
            logger.info("  [%d/5] %s — %s", score, prof["name"], uni_name)
    except Exception:
        logger.exception("Failed to process professor %s", url)


def _process_phd_page(uni_id: int, uni_name: str, url: str):
    if phd_page_is_done(url):
        return
    touch_phd_page(uni_id, url)
    try:
        html = fetch(url)
        if not html:
            return
        text, _ = clean(html, url)

        result = call(PHD_EXTRACT_SYS, PHD_EXTRACT_USER.format(
            university_name=uni_name, url=url, text=text
        ))
        if not isinstance(result, dict):
            return

        programs = result.get("programs", [])
        if programs:
            save_phd_page(url, programs)
            logger.info("  PhD programs found at %s: %d", url, len(programs))
    except Exception:
        logger.exception("Failed to process PhD page %s", url)


# ── Per-university orchestration ──────────────────────────────────────────────

def _process_university(uni: dict):
    uni_id = uni["id"]
    uni_name = uni["name"]
    website = uni["website"]

    if not website:
        logger.warning("No website for %s — skipping", uni_name)
        set_university_status(uni_id, "error")
        return

    logger.info("Processing %s", uni_name)
    set_university_status(uni_id, "crawling")

    try:
        # ── Step 1: discover faculty & PhD entry points from homepage ────────
        html = fetch(website)  # already falls back to playwright internally
        if not html:
            logger.warning("Cannot fetch homepage of %s", uni_name)
            set_university_status(uni_id, "error")
            return

        text, _ = clean(html, website)
        entry = call(
            ENTRY_POINTS_SYS,
            ENTRY_POINTS_USER.format(
                university_name=uni_name, homepage_url=website, text=text
            ),
        )

        faculty_urls: list[str] = []
        phd_urls: list[str] = []
        if isinstance(entry, dict):
            faculty_urls = [
                u for u in entry.get("faculty_urls", [])
                if isinstance(u, str) and same_domain(u, website)
            ][:10]
            phd_urls = [
                u for u in entry.get("phd_urls", [])
                if isinstance(u, str) and same_domain(u, website)
            ][:5]

        set_university_crawling(uni_id, faculty_urls, phd_urls)

        # ── Step 2: collect individual professor URLs ────────────────────────
        professor_urls: set[str] = set()
        for fac_url in faculty_urls:
            html = fetch(fac_url)
            if not html:
                continue
            text, _ = clean(html, fac_url)
            result = call(PROF_LINKS_SYS, PROF_LINKS_USER.format(url=fac_url, text=text))
            if isinstance(result, dict):
                for u in result.get("professor_urls", []):
                    if isinstance(u, str) and same_domain(u, website):
                        professor_urls.add(u)

        # ── Step 3: process each professor ──────────────────────────────────
        prof_list = sorted(professor_urls)[:_MAX_PROF_URLS_PER_UNI]
        logger.info("  %d professor pages to process", len(prof_list))
        for url in prof_list:
            _process_professor(uni_id, uni_name, url)

        # ── Step 4: process PhD admissions pages ────────────────────────────
        for url in phd_urls:
            _process_phd_page(uni_id, uni_name, url)

        set_university_status(uni_id, "done")

    except Exception:
        logger.exception("Error processing %s", uni_name)
        set_university_status(uni_id, "error")


# ── Public entry point ────────────────────────────────────────────────────────

def crawl_all():
    pending = get_pending_universities()
    logger.info("Crawling %d universities...", len(pending))
    for i, uni in enumerate(pending, 1):
        logger.info("[%d/%d] %s", i, len(pending), uni["name"])
        _process_university(dict(uni))
