"""
Backwards-compatible shim. The module name stays gemini_summarize so existing
imports keep working, but it now calls Anthropic's API.
"""
from lib.anthropic_summarize import SYSTEM_PROMPT, summarize  # noqa: F401
