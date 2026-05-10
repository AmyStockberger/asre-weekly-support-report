"""
Constants for The ASRE Weekly Support Report.

Pulled directly from the SKILL.md spec. Edit here once and it propagates
through compile.py and send_email.py.
"""

# ElevenLabs voice clone for Amy Stockberger
ELEVENLABS_VOICE_ID = "2gEMANtbXYR1bT4pIVSN"

# Google Drive document and folder IDs
GOOGLE_DRIVE = {
    "hst_partner_spotlight_doc": "1fyAuHta7j6f3UvtO4WUqFwfD2xxvi1AJ04xeHoqj88o",
    "client_events_doc": "1AFPGJ3odEuWfD__aVBw1Q9F3PLGalfUg9RdUJ8nLncY",
    "sf_market_stats_folder": "1QMEdpJM_g1u9nNdY3XGZSF3mHjA1UN58",
    "parent_folder": "1evCpBGeoeIoiCoGHEw1FTaqrqYQHvpEK",
}

# Web sources scraped weekly
WEB_SOURCES = {
    "siouxfalls_business": "https://siouxfalls.business",
    "logan_mohtashami": "https://loganmohtashami.com",
    "nowbam_re_news": "https://nowbam.com/category/re-news",
    "asre_discounts": "https://amystockberger.com/home-support-team-discounts",
}

# Gemini model used for all summarization (free tier)
ANTHROPIC_MODEL = "claude-haiku-4-5"

# Cap reports.json at six months of weekly entries
REPORT_HISTORY_CAP = 26

# Audio retention window in days
AUDIO_RETENTION_DAYS = 180

# Outlook SMTP settings
OUTLOOK_SMTP = {
    "host": "smtp.office365.com",
    "port": 587,
    "use_tls": True,
}

# Brand colors used by the email renderer
BRAND_NAVY = "#24327A"
BRAND_YELLOW = "#EED75F"
