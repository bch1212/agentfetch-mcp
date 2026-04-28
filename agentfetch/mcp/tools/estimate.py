"""MCP tool: `estimate_tokens`."""
from __future__ import annotations

from agentfetch.core.pipeline import estimate_url_tokens


def estimate_tokens(url: str) -> dict:
    """Estimate the token count of a URL's content WITHOUT fetching the body.

    Use this to decide whether a URL is worth fetching given your context
    budget. Returns the estimated token count along with the byte size and
    content type that informed the estimate.
    """
    return estimate_url_tokens(url)
