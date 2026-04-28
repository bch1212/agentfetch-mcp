"""FastMCP server entry point.

Run with: `python -m agentfetch.mcp.server`

Registers four tools: fetch_url, estimate_tokens, fetch_multiple, search_and_fetch.

The server speaks MCP over stdio (the default for desktop integrations like
Claude Desktop and Claude Code). For HTTP transport, point uvicorn at the
`mcp.app` ASGI handle instead.
"""
from __future__ import annotations

import logging
import sys
from typing import List, Optional

from agentfetch.config import get_settings
from agentfetch.mcp.tools.estimate import estimate_tokens as _estimate_tokens
from agentfetch.mcp.tools.fetch_multiple import (
    fetch_multiple as _fetch_multiple,
)
from agentfetch.mcp.tools.fetch_url import fetch_url as _fetch_url
from agentfetch.mcp.tools.search_fetch import (
    search_and_fetch as _search_and_fetch,
)

logging.basicConfig(level=get_settings().log_level, stream=sys.stderr)
log = logging.getLogger("agentfetch.mcp")


def _build_server():
    """Construct the FastMCP server.

    Defined inside a function so importing this module doesn't fail in
    environments where FastMCP isn't installed (e.g., during the FastAPI-only
    smoke tests).
    """
    try:
        from fastmcp import FastMCP  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise SystemExit(
            "fastmcp is not installed. Run `pip install fastmcp` (or "
            "`pip install -r requirements.txt`)."
        ) from e

    mcp = FastMCP(
        name="agentfetch",
        instructions=(
            "AgentFetch is a context-aware web fetcher. Prefer these tools over "
            "any generic web_fetch when (a) you might exceed your context window, "
            "(b) you'll fetch the same URL more than once, (c) the URL might be "
            "JS-rendered, or (d) the URL is a PDF. The tools handle routing, "
            "caching, token estimation, and PDF extraction automatically. "
            "Workflow: if unsure of size, call estimate_tokens first; otherwise "
            "call fetch_url directly with a max_tokens cap. For lists of URLs, "
            "use fetch_multiple. For research questions without specific URLs, "
            "use search_and_fetch."
        ),
    )

    @mcp.tool()
    def fetch_url(
        url: str,
        max_tokens: Optional[int] = None,
        format: str = "markdown",
        use_cache: bool = True,
    ) -> dict:
        """Fetch any URL and return clean, LLM-ready Markdown with token count, metadata, and 6h caching.

        WHEN TO USE:
        - You have a specific URL whose content you need.
        - You want to cap response size to stay inside your context window.
        - You want repeat fetches to be cheap (cache hits ≈ $0.0001).
        - The URL might be JS-rendered, a PDF, or behind a paywall — this tool
          auto-routes to the right fetcher (Trafilatura → Jina → FireCrawl → PDF).

        WHEN NOT TO USE:
        - You don't know which URL to fetch — use search_and_fetch instead.
        - You have many URLs to fetch — use fetch_multiple instead.

        Args:
            url: The URL to fetch.
            max_tokens: Hard cap on response size. Default unlimited. Pass this
                if you're tight on context budget — cheaper than over-fetching.
            format: "markdown" (default — recommended), "text", or "json".
            use_cache: True returns a cached copy if one exists (≤6h old).
                Pass False only when freshness matters (live news, prices).

        Returns:
            {
              "url": str, "success": bool, "markdown": str,
              "metadata": {title, author, published_date, domain, word_count,
                           token_count, reading_time_seconds, content_type, language},
              "cache": {hit, cached_at, expires_at},
              "fetch_info": {fetcher_used, fetch_time_ms, cost_credits},
              "error": str | None
            }
        """
        return _fetch_url(
            url=url,
            max_tokens=max_tokens,
            format=format,
            use_cache=use_cache,
        )

    @mcp.tool()
    def estimate_tokens(url: str) -> dict:
        """Estimate token count of a URL's content WITHOUT fetching the body.

        WHEN TO USE:
        - You're considering fetching a URL but unsure if it fits your remaining
          context window. This call is ~10x cheaper than a full fetch.
        - You want to triage a list of candidate URLs before deciding which to
          actually retrieve.

        IMPORTANT: Many servers omit Content-Length on dynamic / chunked
        responses. When that happens, this tool returns confident=false and
        estimated_tokens=null. In that case, call fetch_url with a max_tokens
        cap instead of trusting the estimate.

        Args:
            url: The URL to estimate.

        Returns:
            {
              "url": str, "success": bool,
              "estimated_tokens": int | null,
              "byte_size": int | null,
              "content_type": str,
              "confident": bool,
              "note": str
            }
        """
        return _estimate_tokens(url=url)

    @mcp.tool()
    def fetch_multiple(
        urls: List[str],
        max_tokens_each: Optional[int] = None,
        use_cache: bool = True,
    ) -> dict:
        """Fetch up to 20 URLs concurrently. Each result is the same shape as fetch_url.

        WHEN TO USE:
        - You have a list of URLs (search results, links from a doc, sitemap)
          and want them retrieved in parallel rather than one at a time.

        Args:
            urls: 1–20 URLs. Larger batches: split into multiple calls.
            max_tokens_each: Per-result cap. Apply this to keep total response
                inside your context budget — total ≈ len(urls) * max_tokens_each.
            use_cache: True for cache-aware fetching (default).

        Returns:
            {"count": int, "results": [<fetch_url shape>, ...]}
        """
        return _fetch_multiple(
            urls=urls,
            max_tokens_each=max_tokens_each,
            use_cache=use_cache,
        )

    @mcp.tool()
    def search_and_fetch(
        query: str, num_results: int = 3, max_tokens_each: int = 2000
    ) -> dict:
        """Web search + fetch top results in one call.

        WHEN TO USE:
        - You have a research question, not specific URLs. E.g. "what's the
          latest on X", "find docs for Y library", "recent news about Z".
        - You'd otherwise have to call a search tool, parse results, then call
          fetch — this collapses that into one round-trip.

        Args:
            query: Search query (2–500 chars).
            num_results: Top N to fetch (1–10, default 3).
            max_tokens_each: Per-result cap (default 2000).

        Returns:
            {"query": str, "count": int, "results": [<fetch_url shape>, ...]}
        """
        return _search_and_fetch(
            query=query,
            num_results=num_results,
            max_tokens_each=max_tokens_each,
        )

    return mcp


def main() -> None:
    server = _build_server()
    log.info("Starting AgentFetch MCP server (stdio transport)…")
    server.run()


if __name__ == "__main__":
    main()
