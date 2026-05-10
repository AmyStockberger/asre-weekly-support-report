"""
Renderers for the report dict and the branded HTML email.

build_report turns raw week_data into the reports.json contract.
build_email_html turns a single report into an inline-styled HTML email.
"""

import html as html_lib

from .config import BRAND_NAVY, BRAND_YELLOW


def _safe(value, default=""):
    if value is None:
        return default
    return value


def build_report(week_data: dict) -> dict:
    """
    Coerce the compile output into the reports.json schema.

    week_data keys expected:
        weekId, weekLabel, publishedAt, greeting, podcastUrl, podcastDuration,
        sections (dict matching the spec)
    """
    return {
        "weekId": _safe(week_data.get("weekId")),
        "weekLabel": _safe(week_data.get("weekLabel")),
        "publishedAt": _safe(week_data.get("publishedAt")),
        "greeting": _safe(week_data.get("greeting")),
        "podcastUrl": week_data.get("podcastUrl"),
        "podcastDuration": _safe(week_data.get("podcastDuration"), "approx 4 min"),
        "sections": week_data.get("sections", {}),
    }


def _section_teaser(report: dict, key: str, fallback_headline: str, fallback_teaser: str):
    section = report.get("sections", {}).get(key, {}) or {}
    headline = section.get("headline") or fallback_headline
    teaser = ""

    if key == "marketStats":
        bullets = section.get("bullets") or []
        if bullets:
            teaser = bullets[0]
    elif key == "mortgage":
        teaser = section.get("summary") or ""
    elif key == "partner":
        spotlight = section.get("spotlight", {}) or {}
        teaser = spotlight.get("pitch") or ""
        if not headline or headline == fallback_headline:
            name = spotlight.get("name")
            if name:
                headline = f"Spotlight on {name}"
    else:
        items = section.get("items") or []
        if items:
            first = items[0]
            teaser = first.get("summary") or first.get("title") or ""
        elif section.get("note"):
            teaser = section["note"]

    if not teaser:
        teaser = fallback_teaser

    # Trim teaser to ~180 chars so the email stays compact
    if len(teaser) > 180:
        teaser = teaser[:177].rstrip() + "..."

    return headline, teaser


def build_email_html(report: dict, artifact_url: str) -> str:
    """
    Build the inline-styled HTML email body for one weekly report.
    """
    week_label = html_lib.escape(_safe(report.get("weekLabel"), "this week"))
    greeting = html_lib.escape(
        _safe(
            report.get("greeting"),
            "Quick read for the week. Pour a coffee and let us know what lands.",
        )
    )

    podcast_url = report.get("podcastUrl")
    cta_url = artifact_url or "#"
    cta_url_safe = html_lib.escape(cta_url, quote=True)

    sections_meta = [
        ("marketStats", "Sioux Falls market stats", "Latest numbers from the local board."),
        ("localNews", "Sioux Falls this week", "What is moving around town."),
        ("realEstate", "Local development to watch", "Projects worth tracking for clients."),
        ("mortgage", "Rates and mortgage chatter", "What Logan Mohtashami is calling out."),
        ("national", "National real estate news", "The headlines worth a glance."),
        ("partner", "Home Support Partners spotlight", "Who to lean on this week."),
        ("events", "Client events this week", "Where to bring your people."),
    ]

    teaser_rows = []
    for key, fallback_headline, fallback_teaser in sections_meta:
        headline, teaser = _section_teaser(report, key, fallback_headline, fallback_teaser)
        teaser_rows.append(
            f"""
            <tr>
              <td style="padding: 10px 0; border-bottom: 1px solid #e6e6ea;">
                <div style="font-family: Arial, Helvetica, sans-serif; font-size: 15px; color: {BRAND_NAVY}; font-weight: bold;">
                  {html_lib.escape(headline)}
                </div>
                <div style="font-family: Arial, Helvetica, sans-serif; font-size: 14px; color: #333; margin-top: 4px;">
                  {html_lib.escape(teaser)}
                </div>
              </td>
            </tr>
            """
        )

    teasers_html = "".join(teaser_rows)

    podcast_row = ""
    if podcast_url:
        podcast_row = f"""
        <tr>
          <td style="padding: 16px 0 0 0; font-family: Arial, Helvetica, sans-serif; font-size: 14px; color: #333;">
            Listen instead.
            <a href="{html_lib.escape(podcast_url, quote=True)}" style="color: {BRAND_NAVY}; font-weight: bold;">Open the podcast.</a>
          </td>
        </tr>
        """

    # Logo placeholder. Amy can swap the src later for a hosted logo URL.
    logo_html = f"""
    <div style="font-family: Arial, Helvetica, sans-serif; font-size: 22px; font-weight: bold; color: {BRAND_NAVY}; letter-spacing: 0.5px;">
      Amy Stockberger Real Estate
    </div>
    """

    html_doc = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>The ASRE Weekly Support Report</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f4f7;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f7; padding: 24px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background: #ffffff; border-radius: 6px; overflow: hidden; max-width: 600px;">

          <tr>
            <td style="background: {BRAND_NAVY}; padding: 20px 24px;">
              {logo_html.replace(BRAND_NAVY, "#ffffff")}
            </td>
          </tr>

          <tr>
            <td style="background: {BRAND_YELLOW}; padding: 12px 24px; font-family: Arial, Helvetica, sans-serif; color: {BRAND_NAVY}; font-size: 14px; font-weight: bold; letter-spacing: 0.5px;">
              The ASRE Weekly Support Report &middot; {week_label}
            </td>
          </tr>

          <tr>
            <td style="padding: 24px;">
              <p style="font-family: Arial, Helvetica, sans-serif; font-size: 16px; color: #222; line-height: 1.5; margin: 0 0 18px 0;">
                {greeting}
              </p>

              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                {teasers_html}
              </table>

              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top: 24px;">
                <tr>
                  <td align="center">
                    <a href="{cta_url_safe}" style="display: inline-block; background: {BRAND_YELLOW}; color: {BRAND_NAVY}; font-family: Arial, Helvetica, sans-serif; font-size: 16px; font-weight: bold; padding: 14px 28px; border-radius: 4px; text-decoration: none;">
                      Read this week's full report
                    </a>
                  </td>
                </tr>
                {podcast_row}
              </table>
            </td>
          </tr>

          <tr>
            <td style="background: {BRAND_NAVY}; padding: 18px 24px; font-family: Arial, Helvetica, sans-serif; color: #ffffff; font-size: 12px; line-height: 1.5; text-align: center;">
              Lifetime Home Support&trade; from Amy Stockberger Real Estate.<br>
              Before, during, and forever.<br>
              <span style="color: {BRAND_YELLOW}; font-weight: bold; letter-spacing: 1px;">Serve. Serve. Serve. Sell.</span>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    return html_doc
