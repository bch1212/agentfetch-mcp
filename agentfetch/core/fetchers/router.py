"""Pick the cheapest effective fetcher for a given URL.

Heuristics, in priority order:
  1. URL ends in .pdf or has /pdf/ in path → local PDF fetcher (zero cost)
  2. Domain is on the JS-heavy list → FireCrawl
  3. Otherwise → Trafilatura first (free), Jina as fallback if extraction fails

The pipeline (`pipeline.py`) handles the trafilatura → jina fallback. The
router only has to declare intent.
"""
from __future__ import annotations

from urllib.parse import urlparse

from agentfetch.core.fetchers import FetchResult
from agentfetch.core.fetchers import firecrawl, jina, pdf, trafilatura_fetcher

# Domains where trafilatura/Jina won't work because the content is rendered
# client-side. We send these straight to FireCrawl.
JS_HEAVY_DOMAINS = {
    "twitter.com",
    "x.com",
    "linkedin.com",
    "instagram.com",
    "reddit.com",
    "notion.so",
    "airtable.com",
    "facebook.com",
    "tiktok.com",
    "threads.net",
}

# Registry — used by pipeline.py to dispatch to the right module after routing.
FETCHERS = {
    "trafilatura": trafilatura_fetcher.fetch,
    "jina": jina.fetch,
    "firecrawl": firecrawl.fetch,
    "pdf": pdf.fetch,
}


def _domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return netloc[4:] if netloc.startswith("www.") else netloc


def _looks_like_pdf(url: str) -> bool:
    lower = url.lower().split("?", 1)[0]
    return lower.endswith(".pdf")


def route_fetcher(url: str) -> str:
    """Return the *primary* fetcher name for this URL.

    Returns one of: "pdf", "firecrawl", "trafilatura", "jina".
    The pipeline will fall through trafilatura → jina if needed.
    """
    if _looks_like_pdf(url):
        return "pdf"
    domain = _domain(url)
    if any(d == domain or domain.endswith("." + d) for d in JS_HEAVY_DOMAINS):
        return "firecrawl"
    # Default: try the free fetcher first
    return "trafilatura"


def dispatch(fetcher_name: str, url: str) -> FetchResult:
    fn = FETCHERS.get(fetcher_name)
    if fn is None:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used=fetcher_name,
            error=f"unknown fetcher: {fetcher_name}",
        )
    return fn(url)
