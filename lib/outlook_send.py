"""
Outlook / Microsoft 365 SMTP sender.

Auth pulls OUTLOOK_APP_PASSWORD and OUTLOOK_FROM_EMAIL from the
environment. The actual send is wrapped in try/except so a single bad
recipient does not crash the workflow.
"""

import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import OUTLOOK_SMTP

logger = logging.getLogger(__name__)


def send_email(subject: str, html: str, to_address: str) -> bool:
    """
    Send an HTML email through Microsoft 365 SMTP. Returns True on success.
    """
    from_email = os.environ.get("OUTLOOK_FROM_EMAIL")
    password = os.environ.get("OUTLOOK_APP_PASSWORD")

    if not from_email:
        logger.error("OUTLOOK_FROM_EMAIL is not set")
        return False
    if not password:
        logger.error("OUTLOOK_APP_PASSWORD is not set")
        return False
    if not to_address:
        logger.error("send_email called with empty to_address")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_address

    # Plain text fallback derived from a stripped HTML body so spam
    # filters get something to chew on.
    plain_fallback = (
        "This email contains the weekly Amy Stockberger Real Estate report. "
        "Open in an HTML capable client to see the formatted version."
    )

    msg.attach(MIMEText(plain_fallback, "plain"))
    msg.attach(MIMEText(html, "html"))

    host = OUTLOOK_SMTP["host"]
    port = OUTLOOK_SMTP["port"]
    use_tls = OUTLOOK_SMTP.get("use_tls", True)

    try:
        with smtplib.SMTP(host, port, timeout=60) as server:
            server.ehlo()
            if use_tls:
                server.starttls()
                server.ehlo()
            server.login(from_email, password)
            server.sendmail(from_email, [to_address], msg.as_string())
        return True
    except Exception as exc:
        logger.exception("outlook_send failed: %s", exc)
        return False
