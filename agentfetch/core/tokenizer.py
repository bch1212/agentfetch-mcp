"""Token counting + estimation.

Uses tiktoken's cl100k_base encoding, which approximates token counts well for
both Claude and GPT-family models. We don't load model-specific encoders because
the small per-model differences don't matter for context-budgeting decisions.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional


@lru_cache(maxsize=1)
def _get_encoder():
    try:
        import tiktoken  # type: ignore
        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def count_tokens(text: str) -> int:
    """Exact token count for a piece of text.

    Falls back to a chars/4 heuristic if tiktoken isn't installed (so the
    package can boot without it).
    """
    if not text:
        return 0
    enc = _get_encoder()
    if enc is None:
        return max(1, len(text) // 4)
    return len(enc.encode(text))


def estimate_tokens_from_size(byte_size: int, content_type: str = "text/html") -> int:
    """Rough estimate from a Content-Length header before fetching the body.

    Cheap heuristic — actual token count after cleaning will be lower because
    we strip nav/ads/scripts. We bias the estimate slightly high so agents
    don't over-fetch into a context-window blowout.

    Heuristics:
      - HTML: ~30% of bytes survive cleaning, ~4 chars/token → bytes * 0.3 / 4
      - Plain text: ~95% survives, ~4 chars/token → bytes * 0.95 / 4
      - PDF: ~50% extractable text, ~4 chars/token → bytes * 0.5 / 4
    """
    if byte_size <= 0:
        return 0

    ct = (content_type or "").lower()
    if "html" in ct:
        return int(byte_size * 0.30 / 4)
    if "pdf" in ct:
        return int(byte_size * 0.50 / 4)
    if "json" in ct or "xml" in ct:
        return int(byte_size * 0.80 / 4)
    if "text" in ct:
        return int(byte_size * 0.95 / 4)
    # Unknown — assume HTML-ish
    return int(byte_size * 0.30 / 4)


def truncate_to_tokens(text: str, max_tokens: Optional[int]) -> str:
    """Trim text to at most max_tokens. Returns text unchanged if max_tokens is None or 0."""
    if not max_tokens or max_tokens <= 0 or not text:
        return text
    enc = _get_encoder()
    if enc is None:
        # Char-based fallback: ~4 chars/token
        approx_chars = max_tokens * 4
        if len(text) <= approx_chars:
            return text
        return text[:approx_chars] + "\n\n[…truncated to fit token budget]"
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    truncated = enc.decode(tokens[:max_tokens])
    return truncated + "\n\n[…truncated to fit token budget]"
