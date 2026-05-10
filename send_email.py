"""
Send the weekly support report email.

Run by .github/workflows/send-email.yml every Sunday at 18:00 UTC.

The newest report in reports.json is rendered to HTML and sent via
Microsoft 365 SMTP. A workflow_dispatch input named recipient_override
is plumbed through env RECIPIENT_OVERRIDE so Amy can dry run to herself.
"""

import json
import logging
import os
import sys
from pathlib import Path

from lib import outlook_send, render

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("send_email")

REPO_ROOT = Path(__file__).resolve().parent
REPORTS_JSON = REPO_ROOT / "reports" / "reports.json"


def load_latest_report():
    if not REPORTS_JSON.exists():
        raise RuntimeError(f"reports.json not found at {REPORTS_JSON}")
    with open(REPORTS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    reports = data.get("reports", []) or []
    if not reports:
        raise RuntimeError("reports.json contains no reports")
    return reports[0]


def determine_recipient():
    override = (os.environ.get("RECIPIENT_OVERRIDE") or "").strip()
    if override:
        logger.info("Using RECIPIENT_OVERRIDE for dry run: %s", override)
        return override
    agent_list = (os.environ.get("AGENT_LIST_EMAIL") or "").strip()
    if not agent_list:
        raise RuntimeError("AGENT_LIST_EMAIL is not set")
    return agent_list


def main():
    report = load_latest_report()
    artifact_url = (os.environ.get("ARTIFACT_URL") or "").strip()
    if not artifact_url:
        logger.warning("ARTIFACT_URL is not set, CTA will fall back to '#'")

    week_label = report.get("weekLabel", "this week")
    subject = f"The ASRE Weekly Support Report: {week_label}"

    html = render.build_email_html(report, artifact_url)

    recipient = determine_recipient()

    ok = outlook_send.send_email(subject, html, recipient)
    if not ok:
        print("send_email.py: send failed", file=sys.stderr)
        sys.exit(1)

    logger.info("Email sent to %s", recipient)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"send_email.py FATAL: {exc}", file=sys.stderr)
        sys.exit(1)
