"""
Pull social and viral real estate content from BAM (nowbam.com) RSS.
Returns articles that mention Instagram, TikTok, reels, or trending social content.
"""
import logging

import feedparser

logger = logging.getLogger(__name__)

SOCIAL_KEYWORDS = {
    "tiktok", "instagram", "reel", "reels", "viral", "trending",
    "social media", "short video", "content creator", "hashtag",
}

BAM_RSS = "https://nowbam.com/feed/"


def fetch() -> list[dict]:
    """Return up to 4 recent social-focused articles from BAM RSS."""
    try:
        feed = feedparser.parse(BAM_RSS)
        articles = []
        for entry in feed.entries[:30]:
            title = entry.get("title", "").lower()
            summary = getattr(entry, "summary", "").lower()
            combined = title + " " + summary
            if any(kw in combined for kw in SOCIAL_KEYWORDS):
                summary_text = getattr(entry, "summary", "") or ""
                if len(summary_text) > 300:
                    summary_text = summary_text[:297] + "..."
                articles.append({
                    "title": entry.get("title", "").strip(),
                    "url": entry.get("link", ""),
                    "summary": summary_text.strip(),
                    "published": entry.get("published", ""),
                })
        logger.info("social_trends: found %d social articles", len(articles))
        return articles[:4]
    except Exception as exc:
        logger.warning("social_trends.fetch failed: %s", exc)
        return []
