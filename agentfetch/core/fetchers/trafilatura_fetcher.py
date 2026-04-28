"""Trafilatura fetcher.

Free local fetch — works on ~70% of standard web pages (news, blogs, docs).
Falls through to Jina if trafilatura returns empty or near-empty output.
"""
from __future__ import annotations

import time
from typing import Optional

from agentfetch.core.fetchers import FetchResult


def fetch(url: str, timeout: int = 15) -> FetchResult:
    started = time.time()
    try:
        import trafilatura  # type: ignore
    except ImportError:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="trafilatura",
            error="trafilatura not installed",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    try:
        # download() returns the page HTML or None on failure.
        html = trafilatura.fetch_url(url, timeout=timeout)
    except Exception as e:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="trafilatura",
            error=f"download failed: {e}",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    if not html:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="trafilatura",
            error="no content returned",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    md = trafilatura.extract(
        html,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        favor_recall=False,
    )

    if not md or len(md.strip()) < 100:
        # Too little extracted — likely a JS-heavy page or a paywall. Caller
        # should fall back to Jina.
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="trafilatura",
            raw_html=html,
            error="extraction too short, likely JS-rendered",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    metadata = trafilatura.extract_metadata(html)
    title: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None
    if metadata:
        title = getattr(metadata, "title", None)
        author = getattr(metadata, "author", None)
        date_val = getattr(metadata, "date", None)
        published_date = str(date_val) if date_val else None

    return FetchResult(
        url=url,
        success=True,
        markdown=md,
        raw_html=html,
        title=title,
        author=author,
        published_date=published_date,
        content_type="text/html",
        fetcher_used="trafilatura",
        fetch_time_ms=int((time.time() - started) * 1000),
        cost_credits=1,  # equivalent to $0.001
    )
