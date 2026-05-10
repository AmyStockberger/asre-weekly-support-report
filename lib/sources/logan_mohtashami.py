"""
Pull the latest post from loganmohtashami.com.

Returns:
    {"title": str, "url": str, "full_text": str}
or None on failure.
"""

import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE = "https://loganmohtashami.com"
USER_AGENT = (
    "Mozilla/5.0 (compatible; ASRE-Weekly-Report/1.0; "
    "+https://amystockberger.com)"
)
TIMEOUT = 25


def _fetch(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.text


def _find_latest_post_url(home_html: str):
    soup = BeautifulSoup(home_html, "html.parser")

    # Try article-based markup first
    article = soup.find("article")
    if article:
        link = article.find("a", href=True)
        if link:
            return urljoin(BASE, link["href"])

    # Fallback: first h2 link inside the main content area
    for h2 in soup.find_all(["h1", "h2"]):
        link = h2.find("a", href=True)
        if link:
            href = link["href"]
            if "loganmohtashami.com" in href or href.startswith("/"):
                return urljoin(BASE, href)

    return None


def _extract_post(post_html: str):
    soup = BeautifulSoup(post_html, "html.parser")

    title_tag = soup.find(["h1", "h2"])
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Prefer an article body. Fall back to all paragraphs.
    body = soup.find("article") or soup.find("main") or soup
    paragraphs = [p.get_text(" ", strip=True) for p in body.find_all("p")]
    full_text = "\n\n".join(p for p in paragraphs if p)

    return title, full_text


def fetch():
    try:
        home_html = _fetch(BASE)
    except Exception as exc:
        logger.warning("logan_mohtashami homepage fetch failed: %s", exc)
        return None

    try:
        latest_url = _find_latest_post_url(home_html)
    except Exception as exc:
        logger.warning("logan_mohtashami home parse failed: %s", exc)
        return None

    if not latest_url:
        logger.warning("logan_mohtashami: no latest post found")
        return None

    try:
        post_html = _fetch(latest_url)
        title, full_text = _extract_post(post_html)
    except Exception as exc:
        logger.warning("logan_mohtashami post fetch failed: %s", exc)
        return None

    if not full_text:
        logger.warning("logan_mohtashami: empty post body")
        return None

    return {
        "title": title or "Latest post",
        "url": latest_url,
        "full_text": full_text,
    }
