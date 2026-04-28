"""End-to-end fetch pipeline shared by the REST API and the MCP server.

`fetch_pipeline()` is the single entry point. It encapsulates:
  cache check → route → dispatch (with trafilatura→jina fallback) → clean →
  tokenize → cache write → build response.

Both the FastAPI handler and the FastMCP tool wrap this function. Don't
duplicate the logic anywhere else.
"""
from __future__ import annotations

import datetime as dt
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from agentfetch.core.cache import cache
from agentfetch.core.cleaner import clean_markdown, extract_title
from agentfetch.core.fetchers import FetchResult
from agentfetch.core.fetchers.router import dispatch, route_fetcher
from agentfetch.core.tokenizer import (
    count_tokens,
    estimate_tokens_from_size,
    truncate_to_tokens,
)
from agentfetch.core.url_safety import UnsafeURLError, validate_url


def _build_response(
    url: str,
    result: FetchResult,
    cleaned_markdown: str,
    word_count: int,
    reading_time_seconds: int,
    language: str,
    token_count: int,
    cache_hit: bool,
    cached_at: Optional[int],
    expires_at: Optional[int],
) -> Dict[str, Any]:
    return {
        "url": url,
        "success": result.success,
        "markdown": cleaned_markdown,
        "metadata": {
            "title": extract_title(cleaned_markdown, result.title),
            "author": result.author,
            "published_date": result.published_date,
            "domain": urlparse(url).netloc,
            "word_count": word_count,
            "token_count": token_count,
            "reading_time_seconds": reading_time_seconds,
            "content_type": _classify_content(cleaned_markdown),
            "language": language,
        },
        "cache": {
            "hit": cache_hit,
            "cached_at": (
                dt.datetime.utcfromtimestamp(cached_at).isoformat() + "Z"
                if cached_at
                else None
            ),
            "expires_at": (
                dt.datetime.utcfromtimestamp(expires_at).isoformat() + "Z"
                if expires_at
                else None
            ),
        },
        "fetch_info": {
            "fetcher_used": result.fetcher_used,
            "fetch_time_ms": result.fetch_time_ms,
            "cost_credits": result.cost_credits,
        },
        "error": result.error,
    }


def _classify_content(markdown: str) -> str:
    """Crude content classifier — good enough for the metadata field.

    Looks for structural cues. Real classification would need an ML pass; this
    just gives agents a hint about what they're looking at.
    """
    if not markdown:
        return "empty"
    head = markdown[:1500].lower()
    if "## page 1" in head and "## page 2" in markdown.lower():
        return "pdf"
    if head.count("- ") > 8 or head.count("* ") > 8:
        return "listicle"
    if "abstract" in head and ("introduction" in head or "references" in head):
        return "academic"
    if any(tag in head for tag in ("api", "endpoint", "request", "response")):
        return "documentation"
    return "article"


def _fetch_with_fallback(url: str) -> FetchResult:
    """Run the primary fetcher with a graduated fallback chain.

    Chain (worst-case): trafilatura → jina → firecrawl.
    PDFs and known JS-heavy domains skip straight to their dedicated fetcher
    but still fall through to firecrawl if that fails too.
    """
    import logging

    log = logging.getLogger(__name__)
    primary = route_fetcher(url)
    result = dispatch(primary, url)
    if result.success:
        return result
    log.info("fetcher %s failed for %s: %s", primary, url, result.error)

    # First fallback: Jina (unless it was already tried).
    if primary != "jina":
        result = dispatch("jina", url)
        if result.success:
            return result
        log.info("jina fallback failed for %s: %s", url, result.error)

    # Last-ditch fallback: FireCrawl (unless it was already tried). We pay
    # more here, but it's the most JS-capable fetcher.
    if primary != "firecrawl":
        result = dispatch("firecrawl", url)
        if result.success:
            return result
        log.warning("all fetchers failed for %s; final error: %s", url, result.error)

    return result


def fetch_pipeline(
    url: str,
    *,
    max_tokens: Optional[int] = None,
    use_cache: bool = True,
    format: str = "markdown",
) -> Dict[str, Any]:
    """The one function to rule them all.

    Returns a fully-populated response dict in the agent-optimized shape
    documented in the README.
    """
    # 0) SSRF check before anything else
    try:
        validate_url(url)
    except UnsafeURLError as e:
        return _build_response(
            url=url,
            result=FetchResult(
                url=url,
                success=False,
                fetcher_used="rejected",
                error=f"URL rejected: {e}",
            ),
            cleaned_markdown="",
            word_count=0,
            reading_time_seconds=0,
            language="und",
            token_count=0,
            cache_hit=False,
            cached_at=None,
            expires_at=None,
        )

    # 1) Cache check
    if use_cache:
        cached = cache.get(url)
        if cached:
            md = cached.get("markdown", "")
            if max_tokens:
                md = truncate_to_tokens(md, max_tokens)
            return _build_response(
                url=url,
                result=FetchResult(
                    url=url,
                    success=True,
                    fetcher_used=cached.get("fetcher_used", "cache"),
                    fetch_time_ms=0,
                    cost_credits=0,  # cache hits cost ~$0.0001 (handled in billing)
                    title=cached.get("title"),
                    author=cached.get("author"),
                    published_date=cached.get("published_date"),
                ),
                cleaned_markdown=md,
                word_count=cached.get("word_count", len(md.split())),
                reading_time_seconds=cached.get("reading_time_seconds", 0),
                language=cached.get("language", "und"),
                token_count=count_tokens(md),
                cache_hit=True,
                cached_at=cached.get("_cached_at"),
                expires_at=cached.get("_expires_at"),
            )

    # 2) Fetch (with router + fallback)
    result = _fetch_with_fallback(url)

    if not result.success:
        return _build_response(
            url=url,
            result=result,
            cleaned_markdown="",
            word_count=0,
            reading_time_seconds=0,
            language="und",
            token_count=0,
            cache_hit=False,
            cached_at=None,
            expires_at=None,
        )

    # 3) Clean + tokenize
    cleaned = clean_markdown(result.markdown)
    md = cleaned.markdown
    if max_tokens:
        md = truncate_to_tokens(md, max_tokens)
    token_count = count_tokens(md)

    # 4) Cache write — store the *uncleaned-but-trimmed* markdown so future
    # callers with bigger budgets get the full content.
    if use_cache:
        cache.set(
            url,
            {
                "markdown": cleaned.markdown,
                "title": result.title,
                "author": result.author,
                "published_date": result.published_date,
                "fetcher_used": result.fetcher_used,
                "word_count": cleaned.word_count,
                "reading_time_seconds": cleaned.reading_time_seconds,
                "language": cleaned.language,
            },
        )
        # Re-read so we get the timestamps Redis stamped.
        stamps = cache.get(url) or {}
        cached_at = stamps.get("_cached_at")
        expires_at = stamps.get("_expires_at")
    else:
        cached_at = None
        expires_at = None

    response = _build_response(
        url=url,
        result=result,
        cleaned_markdown=md,
        word_count=cleaned.word_count,
        reading_time_seconds=cleaned.reading_time_seconds,
        language=cleaned.language,
        token_count=token_count,
        cache_hit=False,
        cached_at=cached_at,
        expires_at=expires_at,
    )

    # Optional format conversion. We always *cache* markdown; we transform on
    # the way out so different callers can request different shapes.
    if format == "text":
        response["markdown"] = _markdown_to_text(response["markdown"])
    elif format == "json":
        response["markdown"] = response["markdown"]  # kept as-is in markdown field
        response["text"] = _markdown_to_text(response["markdown"])

    return response


def fetch_many(
    urls: List[str],
    *,
    max_tokens_each: Optional[int] = None,
    use_cache: bool = True,
    max_workers: int = 8,
) -> List[Dict[str, Any]]:
    """Fetch many URLs in parallel via a thread pool.

    Threads are fine here — each fetch is I/O-bound and httpx releases the GIL
    on socket reads.
    """
    if not urls:
        return []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(urls))) as pool:
        futures = [
            pool.submit(
                fetch_pipeline,
                u,
                max_tokens=max_tokens_each,
                use_cache=use_cache,
            )
            for u in urls
        ]
        return [f.result() for f in futures]


def estimate_url_tokens(url: str, timeout: int = 10) -> Dict[str, Any]:
    """HEAD the URL and convert Content-Length to a token estimate.

    Cheap and fast — no body fetch. Falls back to a tiny GET if HEAD isn't
    supported by the server.
    """
    started = time.time()
    import httpx

    try:
        validate_url(url)
    except UnsafeURLError as e:
        return {
            "url": url,
            "success": False,
            "estimated_tokens": None,
            "error": f"URL rejected: {e}",
            "fetch_time_ms": int((time.time() - started) * 1000),
        }

    try:
        resp = httpx.head(url, timeout=timeout, follow_redirects=True)
        if resp.status_code == 405 or resp.status_code >= 400:
            # Some servers reject HEAD; do a streamed GET and just read headers.
            with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as s:
                headers = s.headers
                status = s.status_code
        else:
            headers = resp.headers
            status = resp.status_code
    except httpx.HTTPError as e:
        return {
            "url": url,
            "success": False,
            "estimated_tokens": 0,
            "error": str(e),
            "fetch_time_ms": int((time.time() - started) * 1000),
        }

    if status >= 400:
        return {
            "url": url,
            "success": False,
            "estimated_tokens": 0,
            "error": f"HEAD returned {status}",
            "fetch_time_ms": int((time.time() - started) * 1000),
        }

    content_length = int(headers.get("content-length", 0) or 0)
    content_type = headers.get("content-type", "text/html")
    estimate = estimate_tokens_from_size(content_length, content_type)

    # Many servers omit Content-Length on dynamic / chunked / compressed
    # responses. Don't lie to the agent — flag the estimate as unavailable.
    confident = content_length > 0
    return {
        "url": url,
        "success": True,
        "estimated_tokens": estimate if confident else None,
        "byte_size": content_length if confident else None,
        "content_type": content_type,
        "fetch_time_ms": int((time.time() - started) * 1000),
        "confident": confident,
        "note": (
            "Estimate based on Content-Length + content type. Actual count after "
            "cleaning may be lower."
            if confident
            else "Server did not return Content-Length. Estimate unavailable — "
            "fetch the URL to get the actual token count."
        ),
    }


def _markdown_to_text(md: str) -> str:
    """Strip Markdown syntax for the `text` output format."""
    import re

    out = re.sub(r"^#{1,6}\s+", "", md, flags=re.MULTILINE)
    out = re.sub(r"\*\*(.+?)\*\*", r"\1", out)
    out = re.sub(r"\*(.+?)\*", r"\1", out)
    out = re.sub(r"`([^`]+)`", r"\1", out)
    out = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", out)
    return out
