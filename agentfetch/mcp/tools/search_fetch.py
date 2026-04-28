"""MCP tool: `search_and_fetch`."""
from __future__ import annotations

from agentfetch.core.fetchers import jina as jina_fetcher
from agentfetch.core.pipeline import fetch_many


def search_and_fetch(
    query: str,
    num_results: int = 3,
    max_tokens_each: int = 2000,
) -> dict:
    """Search the web and return clean content from the top results.

    Wraps Jina's search endpoint to find URLs, then runs each through the
    AgentFetch pipeline. Returns one combined response.

    Args:
        query: Search query string.
        num_results: Number of top results to fetch (default 3, max 10).
        max_tokens_each: Token budget per result.
    """
    num_results = max(1, min(num_results, 10))
    urls = jina_fetcher.search(query, num_results=num_results)
    if not urls:
        return {
            "query": query,
            "count": 0,
            "results": [],
            "error": "search returned no results",
        }
    results = fetch_many(urls, max_tokens_each=max_tokens_each)
    return {"query": query, "count": len(results), "results": results}
