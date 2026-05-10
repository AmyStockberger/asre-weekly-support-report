"""
Pull articles from siouxfalls.business homepage and three categories.

Returns a list of dicts shaped:
    {"title": str, "url": str, "summary": str, "published": str}

On any error returns an empty list so the compile stays alive.
"""

import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE = "https://siouxfalls.business"
PATHS = [
    "",
    "/category/real-estate/",
    "/category/development/",
    "/category/retail/",
]

USER_AGENT = (
    "Mozilla/5.0 (compatible; ASRE-Weekly-Report/1.0; "
    "+https://amystockberger.com)"
)
TIMEOUT = 20


def _fetch(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.text


def _parse_articles(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")
    items = []

    # WordPress sites generally expose article elements. Fall back to h2 a
    # if none found.
    for article in soup.find_all("article"):
        link = article.find("a", href=True)
        title_tag = article.find(["h1", "h2", "h3"])
        if not link or not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        url = urljoin(base_url, link["href"])

        summary_tag = article.find(["p", "div"], class_=lambda c: c and "excerpt" in c.lower())
        if not summary_tag:
            summary_tag = article.find("p")
        summary = summary_tag.get_text(strip=True) if summary_tag else ""

        time_tag = article.find("time")
        published = ""
        if time_tag:
            published = time_tag.get("datetime") or time_tag.get_text(strip=True)

        if title and url:
            items.append({
                "title": title,
                "url": url,
                "summary": summary,
                "published": published,
            })

    if not items:
        # Fallback for non-article markup
        for h2 in soup.find_all(["h2", "h3"]):
            link = h2.find("a", href=True)
            if not link:
                continue
            title = link.get_text(strip=True)
            url = urljoin(base_url, link["href"])
            if title and url:
                items.append({
                    "title": title,
                    "url": url,
                    "summary": "",
                    "published": "",
                })

    return items


def fetch():
    """
    Return a deduplicated list of recent articles from siouxfalls.business.
    """
    seen = set()
    results = []

    for path in PATHS:
        url = BASE + path
        try:
            html = _fetch(url)
        except Exception as exc:
            logger.warning("siouxfalls.business fetch failed for %s: %s", url, exc)
            continue

        try:
            items = _parse_articles(html, BASE)
        except Exception as exc:
            logger.warning("siouxfalls.business parse failed for %s: %s", url, exc)
            continue

        for item in items:
            if item["url"] in seen:
                continue
            seen.add(item["url"])
            results.append(item)

    # Cap at 12 so the LLM step stays cheap
    return results[:12]
