"""PDF fetcher — downloads the file and runs pypdf2 locally.

Zero per-fetch external cost. The credit charge is for our own compute / time.
"""
from __future__ import annotations

import io
import time

import httpx

from agentfetch.core.fetchers import FetchResult


def fetch(url: str, timeout: int = 60) -> FetchResult:
    started = time.time()
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError as e:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="pdf",
            error=f"download failed: {e}",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    if resp.status_code != 200:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="pdf",
            error=f"download returned {resp.status_code}",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    try:
        from PyPDF2 import PdfReader  # type: ignore
    except ImportError:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="pdf",
            error="PyPDF2 not installed",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    try:
        reader = PdfReader(io.BytesIO(resp.content))
    except Exception as e:
        return FetchResult(
            url=url,
            success=False,
            fetcher_used="pdf",
            error=f"pdf parse failed: {e}",
            fetch_time_ms=int((time.time() - started) * 1000),
        )

    chunks: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            chunks.append(f"## Page {i + 1}\n\n{text.strip()}")

    md = "\n\n".join(chunks)
    title = None
    if reader.metadata:
        title = getattr(reader.metadata, "title", None)

    return FetchResult(
        url=url,
        success=bool(md),
        markdown=md,
        title=title,
        content_type="application/pdf",
        fetcher_used="pdf",
        fetch_time_ms=int((time.time() - started) * 1000),
        cost_credits=2,  # equivalent to $0.002
        error=None if md else "no extractable text — likely a scanned PDF",
    )
