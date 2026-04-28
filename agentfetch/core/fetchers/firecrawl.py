"""FireCrawl fetcher — used for JS-heavy pages.

Endpoint: POST https://api.firecrawl.dev/v1/scrape
"""
from __future__ import annotations

import time

import httpx

from agentfetch.config import get_settings
from agentfetch.core.fetchers import FetchResult

FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"


def fetch(url: str, timeout: int = 60) -> FetchResult:
    started = time.time()
    api_key = get_settings().firecrawl_api_key
    if not api_key:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="firecrawl",
            error="FIRECRAWL_API_KEY not configured",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    try:
        resp = httpx.post(
            FIRECRAWL_URL,
            json={
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
                "waitFor": 1500,  # JS pages need a moment to settle
            },
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )
    except httpx.HTTPError as e:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="firecrawl",
            error=f"http error: {e}",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    if resp.status_code != 200:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="firecrawl",
            error=f"firecrawl returned {resp.status_code}: {resp.text[:200]}",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    try:
        body = resp.json()
    except ValueError:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="firecrawl",
            error="firecrawl returned non-JSON body",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    data = body.get("data") or {}
    md = data.get("markdown") or ""
    metadata = data.get("metadata") or {}

    return FetchResult(
        url=url,
        success=bool(md),
        markdown=md,
        title=metadata.get("title"),
        author=metadata.get("author"),
        published_date=metadata.get("publishedDate") or metadata.get("publishedTime"),
        content_type="text/markdown",
        fetcher_used="firecrawl",
        fetch_time_ms=int((time.time() - started) * 1000),
        cost_credits=5,  # equivalent to $0.005
        error=None if md else "firecrawl returned empty markdown",
    )
