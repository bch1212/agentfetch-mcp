"""Jina Reader API fetcher.

Endpoint: GET https://r.jina.ai/<url>
Returns clean Markdown by default. We pass an Authorization header if a key is
configured (paid tier gets higher rate limits and faster routing).
"""
from __future__ import annotations

import time

import httpx

from agentfetch.config import get_settings
from agentfetch.core.fetchers import FetchResult

JINA_BASE = "https://r.jina.ai/"


def fetch(url: str, timeout: int = 30) -> FetchResult:
    started = time.time()
    headers = {
        "Accept": "text/markdown",
        "X-Return-Format": "markdown",
    }
    api_key = get_settings().jina_api_key
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = httpx.get(JINA_BASE + url, headers=headers, timeout=timeout)
    except httpx.HTTPError as e:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="jina",
            error=f"http error: {e}",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    if resp.status_code != 200:
        # Don't echo the response body into the error string — Jina sometimes
        # returns headers / quota messages that include identifying values.
        # Keep diagnostic info to status code + first 80 chars of body, with
        # bearer tokens scrubbed if they ever land there.
        snippet = (resp.text or "")[:80].replace("Bearer ", "Bearer ***")
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="jina",
            error=f"jina returned {resp.status_code}: {snippet}",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    md = resp.text or ""
    title = None
    # Jina prefixes the response with "Title: ..." headers when present.
    for line in md.splitlines()[:6]:
        if line.lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
            break

    return FetchResult(
        url=url,
        success=True,
        markdown=md,
        title=title,
        content_type="text/markdown",
        fetcher_used="jina",
        fetch_time_ms=int((time.time() - started) * 1000),
        cost_credits=2,  # equivalent to $0.002
    )


def search(query: str, num_results: int = 3, timeout: int = 30) -> list[str]:
    """Use Jina's `/search/` endpoint to get top-N URLs for a query.

    The fetch pipeline is responsible for actually fetching the bodies — this
    function only returns URLs.
    """
    headers = {"Accept": "application/json"}
    api_key = get_settings().jina_api_key
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        resp = httpx.get(
            f"https://s.jina.ai/{query}",
            headers=headers,
            timeout=timeout,
        )
    except httpx.HTTPError:
        return []
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except ValueError:
        return []
    results = data.get("data") if isinstance(data, dict) else data
    if not isinstance(results, list):
        return []
    urls: list[str] = []
    for item in results[:num_results]:
        if isinstance(item, dict) and "url" in item:
            urls.append(item["url"])
    return urls
