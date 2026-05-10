"""
Gemini summarization wrapper.

Replaces the Anthropic Claude calls described in SKILL.md with the free
Gemini API. The system prompt that locks Amy's voice rules is preserved
verbatim from the spec.
"""

import os
import sys
import logging

from .config import GEMINI_MODEL

logger = logging.getLogger(__name__)

# Voice rules pulled directly from SKILL.md. Do not edit casually.
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
    """
    Call Gemini with a system prompt and user prompt.

    Returns the generated text on success. Returns None on any error so
    callers can fall back to placeholder content without crashing the
    overall compile.

    The caller passes their own system_prompt for flexibility, but most
    sources should pass SYSTEM_PROMPT from this module to keep voice
    rules intact.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY is not set")
        return None

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system_prompt,
        )

        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": 0.7,
        }

        response = model.generate_content(
            user_prompt,
            generation_config=generation_config,
        )

        # Gemini sometimes returns no text if filters trigger. Guard
        # against attribute errors.
        text = getattr(response, "text", None)
        if not text:
            try:
                # Older SDK shape uses candidates list
                text = response.candidates[0].content.parts[0].text
            except Exception:
                text = None

        if not text:
            logger.error("Gemini returned empty response")
            return None

        return text.strip()

    except Exception as exc:
        logger.exception("Gemini summarize failed: %s", exc)
        print(f"[gemini_summarize] error: {exc}", file=sys.stderr)
        return None
