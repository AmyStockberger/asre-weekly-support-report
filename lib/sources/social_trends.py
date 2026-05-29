import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

APIFY_BASE = "https://api.apify.com/v2"
ACTOR_ID = "data-slayer~instagram-search-reels"
POLL_INTERVAL = 8   # seconds between status checks
MAX_WAIT = 150       # seconds before giving up on a run


def _run_actor(query: str, max_pages: int = 1) -> list[dict]:
    """Start an Apify run, wait for completion, return raw dataset items."""
    api_key = os.environ.get("APIFY_API_KEY", "")
    if not api_key:
        logger.warning("APIFY_API_KEY not set — skipping Instagram scrape for %r", query)
        return []

    try:
        run_resp = requests.post(
            f"{APIFY_BASE}/acts/{ACTOR_ID}/runs",
            params={"token": api_key},
            json={
                "query": query,
                "maxPages": max_pages,
            },
            timeout=30,
        )
        run_resp.raise_for_status()
        run_data = run_resp.json().get("data", {})
        run_id = run_data.get("id")
        dataset_id = run_data.get("defaultDatasetId", "")
        if not run_id:
            logger.warning("Apify returned no run ID for query %r", query)
            return []

        # Poll until finished
        deadline = time.time() + MAX_WAIT
        status = "RUNNING"
        while time.time() < deadline:
            sr = requests.get(
                f"{APIFY_BASE}/actor-runs/{run_id}",
                params={"token": api_key},
                timeout=15,
            )
            sr.raise_for_status()
            run_info = sr.json().get("data", {})
            status = run_info.get("status", "")
            if not dataset_id:
                dataset_id = run_info.get("defaultDatasetId", "")
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
            time.sleep(POLL_INTERVAL)

        if status != "SUCCEEDED":
            logger.warning("Apify run for %r ended with status: %s", query, status)
            return []

        if not dataset_id:
            logger.warning("No dataset ID for Apify run %s", run_id)
            return []

        items_resp = requests.get(
            f"{APIFY_BASE}/datasets/{dataset_id}/items",
            params={"token": api_key, "clean": "true"},
            timeout=30,
        )
        items_resp.raise_for_status()
        items = items_resp.json() or []
        logger.info("Apify %r → %d reels", query, len(items))
        return items

    except Exception as exc:
        logger.warning("Apify scrape failed for %r: %s", query, exc)
        return []


def _fmt_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _to_reel(item: dict) -> dict | None:
    """Convert a raw Apify item to our clean reel dict. Returns None if unusable."""
    code = item.get("code") or item.get("shortcode") or ""
    if not code:
        return None
    url = f"https://www.instagram.com/reel/{code}/"

    # The actor returns raw Instagram API data — field names differ from
    # the cleaned versions some scrapers expose.
    plays = (
        item.get("play_count")
        or item.get("ig_play_count")
        or item.get("playCount")
        or item.get("videoPlayCount")
        or item.get("videoViewCount")
        or 0
    )
    likes = item.get("like_count") or item.get("likesCount") or item.get("likes") or 0

    # owner: raw data nests username inside a "user" object
    user_obj = item.get("user") or {}
    owner = (
        user_obj.get("username")
        or item.get("ownerUsername")
        or item.get("username")
        or ""
    )

    # caption: raw data is a dict with a "text" key; some scrapers return a plain string
    cap_raw = item.get("caption") or item.get("text") or ""
    if isinstance(cap_raw, dict):
        cap_raw = cap_raw.get("text") or ""
    caption = str(cap_raw).strip()

    # Keep first sentence or first 140 chars
    for sep in (".", "!", "?", "\n"):
        idx = caption.find(sep)
        if 20 < idx < 160:
            caption = caption[: idx + 1].strip()
            break
    if len(caption) > 160:
        caption = caption[:157].rstrip() + "\u2026"
    if not caption:
        caption = f"Reel by @{owner}"

    stats_parts = []
    if plays:
        stats_parts.append(f"{_fmt_count(plays)} plays")
    if likes:
        stats_parts.append(f"{_fmt_count(likes)} likes")

    return {
        "owner": owner,
        "url": url,
        "plays": plays,
        "likes": likes,
        "caption": caption,
        "stats": ", ".join(stats_parts),
    }


def fetch() -> dict:
    """Return {'luxury': reel_or_None, 'viral': [reel, ...]}"""
    # Query 1 — real estate (we pick the single top result as the featured luxury pick)
    re_raw = _run_actor("real estate", max_pages=1)
    re_reels = [r for r in (_to_reel(i) for i in re_raw) if r]
    re_reels.sort(key=lambda r: r["plays"], reverse=True)
    luxury = re_reels[0] if re_reels else None

    # Query 2 — broad viral (R&D inspiration, not real estate)
    viral_raw = _run_actor("viral trending 2026", max_pages=1)
    viral_reels = [r for r in (_to_reel(i) for i in viral_raw) if r]
    viral_reels.sort(key=lambda r: r["plays"], reverse=True)

    return {"luxury": luxury, "viral": viral_reels[:4]}
