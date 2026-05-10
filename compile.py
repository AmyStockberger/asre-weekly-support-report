"""
Weekly compile entrypoint for The ASRE Weekly Support Report.

Run by .github/workflows/compile.yml every Sunday at 11:00 UTC.

Steps:
    1. Compute weekId and weekLabel.
    2. Pull each web source and Drive item inside try/except.
    3. Use Gemini to summarize each section.
    4. Build the report dict.
    5. Generate the ElevenLabs podcast mp3.
    6. Prepend to reports.json, cap at 26, sort newest first, write.
    7. Prune mp3 files older than AUDIO_RETENTION_DAYS.

Top-level try/except prints the failure to stderr and exits 1 so the
workflow shows a red X.
"""

import datetime as dt
import io
import json
import logging
import os
import sys
import traceback
from pathlib import Path

from lib import (
    elevenlabs_voice,
    gemini_summarize,
    google_drive,
    render,
)
from lib.config import (
    AUDIO_RETENTION_DAYS,
    GOOGLE_DRIVE,
    REPORT_HISTORY_CAP,
)
from lib.gemini_summarize import SYSTEM_PROMPT, summarize
from lib.sources import (
    asre_discounts,
    logan_mohtashami,
    nowbam,
    siouxfalls_business,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("compile")

REPO_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = REPO_ROOT / "reports"
AUDIO_DIR = REPORTS_DIR / "audio"
REPORTS_JSON = REPORTS_DIR / "reports.json"


# ---------- Date helpers ----------

def compute_week_id_and_label(now=None):
    """Return ('YYYY-Wxx', 'Week of Mon D')."""
    if now is None:
        now = dt.datetime.utcnow()
    iso_year, iso_week, iso_weekday = now.isocalendar()
    week_id = f"{iso_year}-W{iso_week:02d}"

    # Use the Monday of the ISO week for the label
    monday = dt.date.fromisocalendar(iso_year, iso_week, 1)
    week_label = f"Week of {monday.strftime('%B').strip()} {monday.day}"
    return week_id, week_label


# ---------- Section builders ----------

def _safe_call(label, func, fallback):
    """Run a callable, log on error, return fallback."""
    try:
        return func()
    except Exception as exc:
        logger.warning("%s failed: %s", label, exc)
        return fallback


def build_local_news_and_real_estate(used_urls):
    """
    Pull siouxfalls.business, ask Gemini to split top 3 into local news vs
    real estate development.
    """
    fallback_local = {
        "headline": "Sioux Falls this week",
        "items": [
            {
                "title": "Source unavailable",
                "summary": "Source unavailable this week, check back next Sunday.",
                "url": "",
            }
        ],
    }
    fallback_re = {
        "headline": "Local development to watch",
        "items": [
            {
                "title": "Source unavailable",
                "summary": "Source unavailable this week, check back next Sunday.",
                "url": "",
            }
        ],
    }

    articles = _safe_call("siouxfalls_business.fetch", siouxfalls_business.fetch, [])
    if not articles:
        return fallback_local, fallback_re

    # Build a compact list for the LLM
    listing = "\n".join(
        f"- {idx + 1}. {a['title']} | {a['url']} | {a.get('summary', '')[:200]}"
        for idx, a in enumerate(articles)
    )

    user_prompt = (
        "Below are recent articles from siouxfalls.business. Pick the three "
        "most useful for Amy Stockberger Real Estate agents this week. "
        "Group them into two buckets. Bucket A is general Sioux Falls "
        "interest. Bucket B is real estate development or commercial "
        "projects. Return strict JSON with two arrays named local_news and "
        "real_estate. Each entry has title, summary, url. Summary is two "
        "sentences in Amy's voice.\n\n"
        f"Articles:\n{listing}\n\n"
        "JSON only. No code fences."
    )

    raw = summarize(SYSTEM_PROMPT, user_prompt, max_tokens=1500)
    if not raw:
        return fallback_local, fallback_re

    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        parsed = json.loads(cleaned)
        local_items = parsed.get("local_news", []) or []
        re_items = parsed.get("real_estate", []) or []
    except Exception as exc:
        logger.warning("local/RE JSON parse failed: %s", exc)
        return fallback_local, fallback_re

    local = {"headline": "Sioux Falls this week", "items": local_items[:3]}
    re_section = {"headline": "Local development to watch", "items": re_items[:3]}

    for item in local["items"] + re_section["items"]:
        if item.get("url"):
            used_urls.add(item["url"])

    if not local["items"]:
        local = fallback_local
    if not re_section["items"]:
        re_section = fallback_re

    return local, re_section


def build_mortgage():
    fallback = {
        "headline": "Rates and mortgage chatter",
        "summary": "Source unavailable this week, check back next Sunday.",
        "keyPoints": [],
        "sourceUrl": "",
    }

    post = _safe_call("logan_mohtashami.fetch", logan_mohtashami.fetch, None)
    if not post:
        return fallback

    user_prompt = (
        "Read the Logan Mohtashami post below. Write one paragraph in "
        "Amy's voice summarizing the takeaway for real estate agents. "
        "Then list three short key points. Return strict JSON with keys "
        "summary and keyPoints. keyPoints is an array of three short "
        "strings. JSON only. No code fences.\n\n"
        f"Title: {post['title']}\n\n"
        f"Body:\n{post['full_text'][:8000]}"
    )

    raw = summarize(SYSTEM_PROMPT, user_prompt, max_tokens=1200)
    if not raw:
        return {**fallback, "sourceUrl": post["url"]}

    try:
        cleaned = raw.strip().strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        parsed = json.loads(cleaned)
        return {
            "headline": "Rates and mortgage chatter",
            "summary": parsed.get("summary", "").strip(),
            "keyPoints": parsed.get("keyPoints", [])[:3],
            "sourceUrl": post["url"],
        }
    except Exception as exc:
        logger.warning("mortgage JSON parse failed: %s", exc)
        return {**fallback, "sourceUrl": post["url"]}


def build_national():
    fallback = {
        "headline": "National real estate news",
        "items": [
            {
                "title": "Source unavailable",
                "summary": "Source unavailable this week, check back next Sunday.",
                "url": "",
            }
        ],
    }

    articles = _safe_call("nowbam.fetch", nowbam.fetch, [])
    if not articles:
        return fallback

    listing = "\n".join(
        f"- {idx + 1}. {a['title']} | {a['url']} | {a.get('summary', '')[:240]}"
        for idx, a in enumerate(articles)
    )
    user_prompt = (
        "Below are three recent national real estate articles from "
        "nowbam.com. Rewrite each summary in Amy's voice in exactly two "
        "sentences. Return strict JSON with key items. Each item has "
        "title, summary, url. Keep the original urls. JSON only. No code "
        f"fences.\n\nArticles:\n{listing}"
    )

    raw = summarize(SYSTEM_PROMPT, user_prompt, max_tokens=1200)
    if not raw:
        return fallback

    try:
        cleaned = raw.strip().strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        parsed = json.loads(cleaned)
        items = parsed.get("items") or []
        if not items:
            return fallback
        return {"headline": "National real estate news", "items": items[:3]}
    except Exception as exc:
        logger.warning("national JSON parse failed: %s", exc)
        return fallback


def build_partner(used_spotlights):
    fallback_spotlight = {
        "name": "Home Support Partners",
        "category": "Sioux Falls",
        "pitch": "Source unavailable this week, check back next Sunday.",
        "contact": "",
    }
    fallback = {
        "spotlight": fallback_spotlight,
        "discounts": [],
    }

    discounts = _safe_call("asre_discounts.fetch", asre_discounts.fetch, [])

    spotlight_doc_text = ""
    try:
        spotlight_doc_text = google_drive.read_doc(
            GOOGLE_DRIVE["hst_partner_spotlight_doc"]
        )
    except Exception as exc:
        logger.warning("spotlight doc read failed: %s", exc)

    spotlight = fallback_spotlight
    if spotlight_doc_text:
        used_str = ", ".join(sorted(used_spotlights)) or "none"
        user_prompt = (
            "Below is the Home Support Partners spotlight document. Pick "
            "the next spotlight that has not been used yet. Already used "
            f"spotlight names: {used_str}. Return strict JSON with keys "
            "name, category, pitch, contact. Pitch is two to three "
            "sentences in Amy's voice. JSON only. No code fences.\n\n"
            f"Document:\n{spotlight_doc_text[:8000]}"
        )
        raw = summarize(SYSTEM_PROMPT, user_prompt, max_tokens=800)
        if raw:
            try:
                cleaned = raw.strip().strip("`")
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                parsed = json.loads(cleaned)
                spotlight = {
                    "name": parsed.get("name", fallback_spotlight["name"]),
                    "category": parsed.get("category", fallback_spotlight["category"]),
                    "pitch": parsed.get("pitch", fallback_spotlight["pitch"]),
                    "contact": parsed.get("contact", fallback_spotlight["contact"]),
                }
            except Exception as exc:
                logger.warning("spotlight JSON parse failed: %s", exc)

    chosen_discounts = []
    if discounts:
        listing = "\n".join(
            f"- {d['partner']}: {d['offer']}" for d in discounts[:60]
        )
        user_prompt = (
            "Below is the full list of Home Support Partners discounts. "
            "Pick four to six that are most useful this week. Rotate so "
            "agents see fresh entries. Return strict JSON with key "
            "discounts. Each entry has partner and offer. Keep partner "
            "names exactly as written. JSON only. No code "
            f"fences.\n\nDiscounts:\n{listing}"
        )
        raw = summarize(SYSTEM_PROMPT, user_prompt, max_tokens=900)
        if raw:
            try:
                cleaned = raw.strip().strip("`")
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                parsed = json.loads(cleaned)
                chosen_discounts = parsed.get("discounts") or []
            except Exception as exc:
                logger.warning("discounts JSON parse failed: %s", exc)

        if not chosen_discounts:
            chosen_discounts = discounts[:5]

    return {"spotlight": spotlight, "discounts": chosen_discounts}


def build_events():
    fallback = {
        "headline": "Client events this week",
        "items": [
            {
                "title": "Source unavailable",
                "when": "",
                "where": "",
                "notes": "Source unavailable this week, check back next Sunday.",
            }
        ],
    }

    try:
        text = google_drive.read_doc(GOOGLE_DRIVE["client_events_doc"])
    except Exception as exc:
        logger.warning("events doc read failed: %s", exc)
        return fallback

    if not text:
        return fallback

    today = dt.date.today().isoformat()
    user_prompt = (
        f"Today is {today}. Below is the Amy Stockberger Real Estate "
        "client events document. Extract every event happening in the "
        "next seven days. Return strict JSON with key items. Each item "
        "has title, when, where, notes. Notes is one short line on who "
        "to invite and what to mention. JSON only. No code "
        f"fences.\n\nDocument:\n{text[:8000]}"
    )

    raw = summarize(SYSTEM_PROMPT, user_prompt, max_tokens=1200)
    if not raw:
        return fallback

    try:
        cleaned = raw.strip().strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        parsed = json.loads(cleaned)
        items = parsed.get("items") or []
        if not items:
            return fallback
        return {"headline": "Client events this week", "items": items}
    except Exception as exc:
        logger.warning("events JSON parse failed: %s", exc)
        return fallback


def build_market_stats():
    fallback = {
        "headline": "Sioux Falls market stats",
        "bullets": ["Source unavailable this week, check back next Sunday."],
        "chartTitle": "Median sale price, 12-month view",
        "chart": [],
        "sourceUrl": "",
    }

    try:
        files = google_drive.list_files_in_folder(
            GOOGLE_DRIVE["sf_market_stats_folder"]
        )
    except Exception as exc:
        logger.warning("market stats folder list failed: %s", exc)
        return fallback

    if not files:
        return fallback

    latest = files[0]
    file_id = latest["id"]
    mime = latest.get("mimeType", "")

    try:
        content = google_drive.download_file(file_id)
    except Exception as exc:
        logger.warning("market stats download failed: %s", exc)
        return fallback

    extracted_text = ""
    if isinstance(content, str):
        extracted_text = content
    elif isinstance(content, (bytes, bytearray)):
        if "pdf" in mime.lower() or latest.get("name", "").lower().endswith(".pdf"):
            try:
                from PyPDF2 import PdfReader

                reader = PdfReader(io.BytesIO(bytes(content)))
                extracted_text = "\n".join(
                    page.extract_text() or "" for page in reader.pages
                )
            except Exception as exc:
                logger.warning("market stats PDF parse failed: %s", exc)
                return fallback
        else:
            try:
                extracted_text = content.decode("utf-8", errors="replace")
            except Exception:
                return fallback

    if not extracted_text.strip():
        return fallback

    user_prompt = (
        "Below is the latest RASE Sioux Falls market stats document. "
        "Extract the headline numbers an agent needs this week. Return "
        "strict JSON with keys headline, bullets, chartTitle, chart, "
        "sourceUrl. headline is six to ten words sentence case. bullets "
        "is three short sentences in Amy's voice covering median sale "
        "price, pending sales year over year, and average days on "
        "market. chartTitle is one short phrase. chart is an array of "
        "twelve objects with month and value where month looks like "
        "'May 25' and value is the median sale price in thousands as a "
        "number. sourceUrl is empty if not given. JSON only. No code "
        f"fences.\n\nDocument:\n{extracted_text[:9000]}"
    )

    raw = summarize(SYSTEM_PROMPT, user_prompt, max_tokens=1500)
    if not raw:
        return fallback

    try:
        cleaned = raw.strip().strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        parsed = json.loads(cleaned)
        return {
            "headline": parsed.get("headline", fallback["headline"]),
            "bullets": parsed.get("bullets", fallback["bullets"]),
            "chartTitle": parsed.get("chartTitle", fallback["chartTitle"]),
            "chart": parsed.get("chart", []),
            "sourceUrl": parsed.get("sourceUrl", ""),
        }
    except Exception as exc:
        logger.warning("market stats JSON parse failed: %s", exc)
        return fallback


def build_greeting(week_label: str, sections: dict) -> str:
    fallback = (
        "Here is your weekly read. Pour a coffee and tell us what lands "
        "with your clients."
    )
    user_prompt = (
        f"Write a one to three sentence greeting from Amy for the "
        f"{week_label} edition of The ASRE Weekly Support Report. Reference "
        "one concrete item from the sections below if you find one worth "
        "calling out. Return plain text only.\n\n"
        f"Sections JSON:\n{json.dumps(sections)[:4000]}"
    )

    raw = summarize(SYSTEM_PROMPT, user_prompt, max_tokens=300)
    if not raw:
        return fallback
    return raw.strip().strip('"').strip()


def build_podcast_script(report: dict) -> str:
    sections_compact = json.dumps(report.get("sections", {}))[:6000]
    fallback = (
        "Hey team, Amy here. Here is your weekly read. Quick stats from "
        "Sioux Falls, a couple of local stories, and what is happening "
        "on rates. Take advantage of our Home Care Concierge if a client "
        "needs help between transactions. Reach out if you want to talk "
        "through how this hits one of your clients."
    )
    user_prompt = (
        "Write a 300 to 500 word podcast script in Amy's voice for The "
        "ASRE Weekly Support Report. Open with 'Hey team, Amy here. Here "
        "is your weekly read.' Walk through three to four highlights from "
        "the sections below. Close with a specific call to action like "
        "'Reach out if you want to talk through how this hits one of "
        "your clients.' Plain text only. No headers or bullet markers.\n\n"
        f"Sections JSON:\n{sections_compact}"
    )

    raw = summarize(SYSTEM_PROMPT, user_prompt, max_tokens=900)
    if not raw:
        return fallback
    return raw.strip()


# ---------- Persistence ----------

def load_existing_reports():
    if not REPORTS_JSON.exists():
        return {"version": 1, "updatedAt": "", "reports": []}
    try:
        with open(REPORTS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "reports" not in data:
            return {"version": 1, "updatedAt": "", "reports": []}
        return data
    except Exception as exc:
        logger.warning("reports.json load failed, starting fresh: %s", exc)
        return {"version": 1, "updatedAt": "", "reports": []}


def gather_used_spotlights(existing):
    names = set()
    for report in existing.get("reports", []):
        spotlight = report.get("sections", {}).get("partner", {}).get("spotlight", {})
        name = spotlight.get("name")
        if name:
            names.add(name)
    return names


def write_reports(payload):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORTS_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def prune_audio():
    if not AUDIO_DIR.exists():
        return
    cutoff = dt.datetime.utcnow().timestamp() - (AUDIO_RETENTION_DAYS * 86400)
    for path in AUDIO_DIR.glob("*.mp3"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                logger.info("pruned old audio: %s", path.name)
        except Exception as exc:
            logger.warning("prune failed for %s: %s", path, exc)


# ---------- Main ----------

def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    week_id, week_label = compute_week_id_and_label()
    published_at = dt.date.today().isoformat()

    existing = load_existing_reports()
    used_spotlights = gather_used_spotlights(existing)
    used_urls = set()

    logger.info("Compiling %s (%s)", week_id, week_label)

    market_stats = _safe_call("build_market_stats", build_market_stats, {
        "headline": "Sioux Falls market stats",
        "bullets": ["Source unavailable this week, check back next Sunday."],
        "chartTitle": "Median sale price, 12-month view",
        "chart": [],
        "sourceUrl": "",
    })

    local_news, real_estate = _safe_call(
        "build_local_news_and_real_estate",
        lambda: build_local_news_and_real_estate(used_urls),
        (
            {"headline": "Sioux Falls this week", "items": []},
            {"headline": "Local development to watch", "items": []},
        ),
    )

    mortgage = _safe_call("build_mortgage", build_mortgage, {
        "headline": "Rates and mortgage chatter",
        "summary": "Source unavailable this week, check back next Sunday.",
        "keyPoints": [],
        "sourceUrl": "",
    })

    national = _safe_call("build_national", build_national, {
        "headline": "National real estate news",
        "items": [],
    })

    partner = _safe_call(
        "build_partner",
        lambda: build_partner(used_spotlights),
        {
            "spotlight": {
                "name": "Home Support Partners",
                "category": "Sioux Falls",
                "pitch": "Source unavailable this week, check back next Sunday.",
                "contact": "",
            },
            "discounts": [],
        },
    )

    events = _safe_call("build_events", build_events, {
        "headline": "Client events this week",
        "items": [],
    })

    sections = {
        "marketStats": market_stats,
        "localNews": local_news,
        "realEstate": real_estate,
        "mortgage": mortgage,
        "national": national,
        "partner": partner,
        "events": events,
    }

    greeting = _safe_call(
        "build_greeting",
        lambda: build_greeting(week_label, sections),
        "Here is your weekly read. Pour a coffee and let us know what lands.",
    )

    week_data = {
        "weekId": week_id,
        "weekLabel": week_label,
        "publishedAt": published_at,
        "greeting": greeting,
        "podcastUrl": None,
        "podcastDuration": "approx 4 min",
        "sections": sections,
    }

    report = render.build_report(week_data)

    # Generate the podcast
    audio_relpath = f"reports/audio/{week_id}.mp3"
    audio_path = REPO_ROOT / audio_relpath
    script = build_podcast_script(report)
    success = elevenlabs_voice.generate_podcast(script, str(audio_path))
    if success:
        # Full raw GitHub URL so the artifact and email both work directly.
        report["podcastUrl"] = (
            "https://raw.githubusercontent.com/AmyStockberger/"
            f"asre-weekly-support-report/main/{audio_relpath}"
        )
    else:
        logger.warning("podcast generation failed, podcastUrl will be null")
        report["podcastUrl"] = None

    # Merge into existing reports
    existing_reports = existing.get("reports", []) or []
    existing_reports = [r for r in existing_reports if r.get("weekId") != week_id]
    existing_reports.insert(0, report)
    existing_reports.sort(key=lambda r: r.get("publishedAt", ""), reverse=True)
    capped = existing_reports[:REPORT_HISTORY_CAP]

    payload = {
        "version": 1,
        "updatedAt": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "reports": capped,
    }
    write_reports(payload)
    logger.info("Wrote %s with %d reports", REPORTS_JSON, len(capped))

    prune_audio()
    logger.info("Compile complete for %s", week_id)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"compile.py FATAL: {exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
