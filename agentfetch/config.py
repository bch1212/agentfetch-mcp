"""Centralized runtime configuration for the OSS AgentFetch MCP server.

Reads env vars (via dotenv if available) and exposes a typed Settings object.
Only the env vars relevant to the MCP server itself; the hosted service has
additional config in a separate (private) repo.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


class Settings:
    """Lightweight settings container."""

    redis_url: Optional[str] = os.getenv("REDIS_URL")
    jina_api_key: Optional[str] = os.getenv("JINA_API_KEY")
    firecrawl_api_key: Optional[str] = os.getenv("FIRECRAWL_API_KEY")
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL_SECONDS", "21600"))  # 6h
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Vestigial fields kept so shared code doesn't need to be forked. Set to
    # None / defaults that mean "no-op" in the hosted-service paths.
    database_url: Optional[str] = None
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    stripe_meter_event_name: str = "agentfetch_credits"
    sendgrid_api_key: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    free_tier_fetch_limit: int = 0
    env: str = os.getenv("ENV", "development")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
