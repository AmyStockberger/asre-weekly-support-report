import feedparser
import logging

logger = logging.getLogger(__name__)

RSS_URL = "https://rismedia.com/feed/"


def fetch() -> list[dict]:
    """Return up to 3 recent national RE articles from RIS Media RSS."""
    try:
        feed = feedparser.parse(RSS_URL)
        articles = []
        for entry in feed.entries[:3]:
            summary = getattr(entry, "summary", "") or ""
            if len(summary) > 300:
                summary = summary[:297] + "..."
            articles.append({
                "title": entry.get("title", "").strip(),
                "url": entry.get("link", ""),
                "summary": summary.strip(),
                "published": entry.get("published", ""),
            })
        logger.info("rismedia: fetched %d articles", len(articles))
        return articles
    except Exception as exc:
        logger.warning("rismedia.fetch failed: %s", exc)
        return []
