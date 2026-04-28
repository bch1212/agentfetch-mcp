"""Post-process fetched content into clean, agent-ready Markdown.

Rules:
- Strip leading/trailing whitespace and collapse 3+ newlines to 2.
- Remove obvious cookie banners, "subscribe to our newsletter" boilerplate, and
  share-to-twitter footers if they made it through the fetcher.
- Estimate reading time at 200 wpm (industry standard for adult silent reading).
- Detect language naively (English fallback).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Patterns we strip post-extraction. Conservative — we'd rather leave a little
# chrome in than accidentally chop article body.
_BOILERPLATE_PATTERNS = [
    re.compile(r"(?im)^subscribe to our newsletter.*$"),
    re.compile(r"(?im)^accept (all )?cookies.*$"),
    re.compile(r"(?im)^share (this|on) (twitter|facebook|linkedin|reddit).*$"),
    re.compile(r"(?im)^sign up for.*newsletter.*$"),
    re.compile(r"(?im)^by clicking.*you (agree|consent).*$"),
]

_MULTI_NEWLINE = re.compile(r"\n{3,}")
_TRAILING_WS = re.compile(r"[ \t]+\n")


@dataclass
class CleanedContent:
    markdown: str
    word_count: int
    reading_time_seconds: int
    language: str


def _detect_language(text: str) -> str:
    """Naive language detection. Good enough for English/non-English split.

    For real production, swap in `langdetect` or `cld3` — but those are heavy
    dependencies for a marginal accuracy gain on the agent-fetch use case.
    """
    if not text:
        return "und"
    sample = text[:500].lower()
    english_markers = (" the ", " and ", " of ", " to ", " is ", " in ")
    hits = sum(sample.count(m) for m in english_markers)
    return "en" if hits >= 3 else "und"


def clean_markdown(raw: str) -> CleanedContent:
    """Normalize Markdown content from any fetcher into a uniform shape."""
    if not raw:
        return CleanedContent(
            markdown="", word_count=0, reading_time_seconds=0, language="und"
        )

    md = raw
    for pattern in _BOILERPLATE_PATTERNS:
        md = pattern.sub("", md)

    md = _TRAILING_WS.sub("\n", md)
    md = _MULTI_NEWLINE.sub("\n\n", md)
    md = md.strip()

    word_count = len(md.split())
    # 200 wpm = ~3.33 words/second; we round to whole seconds.
    reading_time_seconds = max(1, int(word_count / 200 * 60)) if word_count else 0
    language = _detect_language(md)

    return CleanedContent(
        markdown=md,
        word_count=word_count,
        reading_time_seconds=reading_time_seconds,
        language=language,
    )


def extract_title(markdown: str, fallback: Optional[str] = None) -> Optional[str]:
    """Pull the first H1 from cleaned markdown, fall back to provided value."""
    if not markdown:
        return fallback
    for line in markdown.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback
