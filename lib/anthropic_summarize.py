"""
Anthropic Claude summarization.
Uses ANTHROPIC_API_KEY env var. Returns text or None on any error.
"""
from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are writing for Amy Stockberger Real Estate, the number one real estate team in South Dakota since 2017. Write in Amy's voice, which is bold, pragmatic, and direct.

Hard rules:
- No em dashes anywhere
- No semicolons
- No markdown in output
- Active voice
- Short sentences
- No fluff
- Do not use these words: can, may, just, that, very, really, literally, actually, certainly, probably, basically, could, maybe, delve, embark, realm, game-changer, unlock, discover, skyrocket, revolutionize, disruptive, utilize, dive deep, illuminate, unveil, pivotal, intricate, hence, furthermore, however, harness, exciting, groundbreaking, cutting-edge, remarkable, navigating, landscape, testament, in summary, in conclusion, moreover, boost, powerful

When mentioning the company, always spell out "Amy Stockberger Real Estate" in full.
When mentioning the vendor program, always use "Home Support Partners" not HST or vendors.
When relevant, include "Lifetime Home Support" and indicate the trademark.

Output requested format only. No preamble, no closing remarks."""


def summarize(system_prompt: str, user_prompt: str, max_tokens: int = 2000):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY is not set")
        return None
    try:
        from anthropic import Anthropic
        from lib.config import ANTHROPIC_MODEL
        client = Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        if msg.content and len(msg.content):
            block = msg.content[0]
            return getattr(block, "text", None) or str(block)
        return None
    except Exception as exc:
        logger.error("Anthropic summarize failed: %s", exc)
        print(f"[anthropic_summarize] error: {exc}", file=sys.stderr)
        return None
