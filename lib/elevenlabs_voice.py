"""
ElevenLabs TTS helper for the weekly podcast.

Uses the streaming endpoint and writes the result to disk as mp3.
Returns True on success, False on any failure. Never raises so the
compile keeps publishing the report even if audio fails.
"""

import os
import logging

import requests

from .config import ELEVENLABS_VOICE_ID

logger = logging.getLogger(__name__)

API_URL_TEMPLATE = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
MODEL = "eleven_multilingual_v2"
TIMEOUT = 120


def generate_podcast(text: str, output_path: str) -> bool:
    """
    Generate Amy's voice mp3 and save to output_path. Returns True on success.
    """
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        logger.error("ELEVENLABS_API_KEY is not set")
        return False

    if not text or not text.strip():
        logger.error("elevenlabs: empty text payload")
        return False

    url = API_URL_TEMPLATE.format(voice_id=ELEVENLABS_VOICE_ID)

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }

    payload = {
        "text": text,
        "model_id": MODEL,
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.75,
        },
    }

    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with requests.post(
            url,
            json=payload,
            headers=headers,
            stream=True,
            timeout=TIMEOUT,
        ) as response:
            if response.status_code != 200:
                logger.error(
                    "elevenlabs: HTTP %s, body: %s",
                    response.status_code,
                    response.text[:500],
                )
                return False

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        # Sanity check the file is non-trivial
        if os.path.getsize(output_path) < 1024:
            logger.error("elevenlabs: output file suspiciously small")
            return False

        return True

    except Exception as exc:
        logger.exception("elevenlabs failure: %s", exc)
        return False
