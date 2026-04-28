"""MCP tool: `fetch_multiple`."""
from __future__ import annotations

from typing import List, Optional

from agentfetch.core.pipeline import fetch_many


def fetch_multiple(
    urls: List[str],
    max_tokens_each: Optional[int] = None,
    use_cache: bool = True,
) -> dict:
    """Fetch multiple URLs concurrently.

    Args:
        urls: List of URLs to fetch (recommend ≤20 per call).
        max_tokens_each: Optional cap on each URL's response size.
        use_cache: When true, prefer cached copies (≤6h old).

    Returns:
        `{count, results}` where each result is the same shape as `fetch_url`.
    """
    if not urls:
        return {"count": 0, "results": []}
    results = fetch_many(
        urls, max_tokens_each=max_tokens_each, use_cache=use_cache
    )
    return {"count": len(results), "results": results}
