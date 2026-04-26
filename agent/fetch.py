import re
import time
import logging
from collections import defaultdict
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .config import REQUEST_DELAY, MAX_HTML_CHARS

logger = logging.getLogger(__name__)

_last_request: dict[str, float] = defaultdict(float)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _rate_limit(url: str):
    domain = urlparse(url).netloc
    wait = REQUEST_DELAY - (time.time() - _last_request[domain])
    if wait > 0:
        time.sleep(wait)
    _last_request[domain] = time.time()


def fetch_requests(url: str, timeout: int = 15) -> str | None:
    _rate_limit(url)
    try:
        with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=timeout) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.text
    except Exception as e:
        logger.debug(f"requests fetch failed for {url}: {e}")
        return None


def fetch_playwright(url: str, wait_ms: int = 2500) -> str | None:
    _rate_limit(url)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(extra_http_headers={"Accept-Language": "en-US,en;q=0.9"})
                page.goto(url, wait_until="networkidle", timeout=30_000)
                page.wait_for_timeout(wait_ms)
                return page.content()
            finally:
                browser.close()
    except Exception as e:
        logger.debug(f"playwright fetch failed for {url}: {e}")
        return None


def fetch(url: str, force_playwright: bool = False) -> str | None:
    if not force_playwright:
        html = fetch_requests(url)
        if html and len(html) > 1000:
            return html
    return fetch_playwright(url)


def clean(html: str, base_url: str = "") -> tuple[str, list[str]]:
    """Return (cleaned_text_truncated, deduplicated_absolute_links)."""
    soup = BeautifulSoup(html, "lxml")

    # Keep nav/footer — they contain the faculty-directory and PhD-admissions links
    # that the entry-point LLM prompt needs to see
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "img", "head"]):
        tag.decompose()

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
            full = urljoin(base_url, href) if base_url else href
            if full.startswith("http"):
                links.append(full)
                # Embed URL inline so the LLM can see and use the actual href
                anchor = a.get_text(strip=True)
                a.replace_with(f"{anchor} ({full})" if anchor else full)

    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)

    return text[:MAX_HTML_CHARS], list(dict.fromkeys(links))


def same_domain(url: str, base: str) -> bool:
    # removeprefix, not lstrip — lstrip strips individual chars, not the whole prefix
    b = urlparse(base).netloc.removeprefix("www.")
    u = urlparse(url).netloc.removeprefix("www.")
    return bool(b) and (u == b or u.endswith("." + b))
