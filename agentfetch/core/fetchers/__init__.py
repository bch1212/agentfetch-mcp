"""Fetcher adapters.

Every fetcher returns a `FetchResult`. The router picks one. The pipeline
post-processes the result and writes it to cache.

Add a new fetcher by:
  1. Implementing a `fetch(url) -> FetchResult` callable in this package
  2. Registering it in `router.FETCHERS`
  3. Updating `route_fetcher()` so it can be selected
  4. Adding its cost to `agentfetch.billing.usage.COSTS_BY_FETCHER`
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FetchResult:
    """Normalized output every fetcher must return."""

    url: str
    success: bool
    markdown: str = ""
    raw_html: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None
    content_type: Optional[str] = None
    fetcher_used: str = ""
    fetch_time_ms: int = 0
    cost_credits: int = 0
    error: Optional[str] = None
    extras: dict = field(default_factory=dict)
