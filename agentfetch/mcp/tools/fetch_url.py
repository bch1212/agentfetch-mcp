"""MCP tool: `fetch_url`."""
from __future__ import annotations

from typing import Optional

from agentfetch.core.pipeline import fetch_pipeline


def fetch_url(
    url: str,
    max_tokens: Optional[int] = None,
    format: str = "markdown",
    use_cache: bool = True,
) -> dict:
    """Fetch a web URL and return clean, LLM-ready content with token estimation.

    Args:
        url: The URL to fetch.
        max_tokens: Optional cap on the size of the returned markdown.
            Defaults to no limit.
        format: One of "markdown", "text", "json". Defaults to "markdown".
        use_cache: When true, return a cached copy if one exists (≤6h old).

    Returns:
        A dict with the fetched content, metadata, cache info, and fetch info.
    """
    return fetch_pipeline(
        url, max_tokens=max_tokens, use_cache=use_cache, format=format
    )
