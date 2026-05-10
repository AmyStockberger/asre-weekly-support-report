"""
Pull current Home Support Partners discounts from amystockberger.com.

Returns a list of {"partner": str, "offer": str} dicts.
On error returns [].
"""

import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

URL = "https://amystockberger.com/home-support-team-discounts"

USER_AGENT = (
    "Mozilla/5.0 (compatible; ASRE-Weekly-Report/1.0; "
    "+https://amystockberger.com)"
)
TIMEOUT = 25


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
        logger.warning("asre_discounts fetch failed: %s", exc)
        return []

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        logger.warning("asre_discounts parse failed: %s", exc)
        return []

    entries = []

    # Strategy 1: dt/dd or strong + sibling text, common for discount lists
    for strong in soup.find_all(["strong", "b"]):
        partner = strong.get_text(strip=True)
        if not partner or len(partner) > 120:
            continue

        # Find nearby text as the offer
        offer_text = ""
        sibling = strong.next_sibling
        while sibling and not offer_text:
            if hasattr(sibling, "get_text"):
                offer_text = sibling.get_text(" ", strip=True)
            elif isinstance(sibling, str):
                offer_text = sibling.strip()
            sibling = getattr(sibling, "next_sibling", None)

        if not offer_text:
            parent = strong.parent
            if parent:
                offer_text = parent.get_text(" ", strip=True)
                if offer_text.startswith(partner):
                    offer_text = offer_text[len(partner):].strip(" :-")

        if partner and offer_text and partner.lower() != offer_text.lower():
            entries.append({"partner": partner, "offer": offer_text})

    # Strategy 2: list items "Partner — Offer" or "Partner: Offer"
    if not entries:
        for li in soup.find_all("li"):
            text = li.get_text(" ", strip=True)
            if not text:
                continue
            for sep in [":", " - ", " | "]:
                if sep in text:
                    partner, offer = text.split(sep, 1)
                    partner = partner.strip()
                    offer = offer.strip()
                    if partner and offer:
                        entries.append({"partner": partner, "offer": offer})
                    break

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for entry in entries:
        key = entry["partner"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)

    return deduped
