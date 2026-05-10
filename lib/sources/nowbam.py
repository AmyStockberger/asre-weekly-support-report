"""
Pull the latest 3 articles from the nowbam.com re-news category.

Returns a list of {"title", "url", "summary", "published"} dicts.
On error returns [].
"""

import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

URL = "https://nowbam.com/category/re-news"
BASE = "https://nowbam.com"

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


def fetch():
    try:
        html = _fetch(URL)
    except Exception as exc:
        logger.warning("nowbam fetch failed: %s", exc)
        return []

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        logger.warning("nowbam parse failed: %s", exc)
        return []

    items = []
    seen = set()

    for article in soup.find_all("article"):
        link = article.find("a", href=True)
        title_tag = article.find(["h1", "h2", "h3"])
        if not link or not title_tag:
            continue

        href = urljoin(BASE, link["href"])
        if href in seen:
            continue
        seen.add(href)

        title = title_tag.get_text(strip=True)

        summary_tag = article.find(["p", "div"], class_=lambda c: c and "excerpt" in c.lower())
        if not summary_tag:
            summary_tag = article.find("p")
        summary = summary_tag.get_text(strip=True) if summary_tag else ""

        time_tag = article.find("time")
        published = ""
        if time_tag:
            published = time_tag.get("datetime") or time_tag.get_text(strip=True)

        items.append({
            "title": title,
            "url": href,
            "summary": summary,
            "published": published,
        })

        if len(items) >= 3:
            break

    if not items:
        # Fallback to h2 link discovery if the page does not use <article>
        for h2 in soup.find_all(["h2", "h3"]):
            link = h2.find("a", href=True)
            if not link:
                continue
            href = urljoin(BASE, link["href"])
            if href in seen:
                continue
            seen.add(href)
            items.append({
                "title": link.get_text(strip=True),
                "url": href,
                "summary": "",
                "published": "",
            })
            if len(items) >= 3:
                break

    return items
