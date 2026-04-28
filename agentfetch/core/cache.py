"""Redis cache layer.

6-hour default TTL. Keys are hashed URLs so very long URLs don't blow Redis key
limits and so we don't leak URLs in logs by accident.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional

from agentfetch.config import get_settings


def _key(url: str) -> str:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    return f"af:fetch:{h}"


class Cache:
    """Thin wrapper around redis-py.

    Uses a sync client because both the FastMCP server and the FastAPI app run
    sync handlers under uvicorn workers. Switch to redis.asyncio if we go fully
    async — it has the same key-shape API.
    """

    def __init__(self) -> None:
        self._client = None
        self._ttl = get_settings().cache_ttl_seconds

    @property
    def client(self):
        if self._client is None:
            try:
                import redis  # type: ignore
            except ImportError:
                return None
            url = get_settings().redis_url
            if not url:
                return None
            self._client = redis.Redis.from_url(url, decode_responses=True)
        return self._client

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        c = self.client
        if c is None:
            return None
        try:
            raw = c.get(_key(url))
        except Exception:
            return None
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set(self, url: str, value: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        c = self.client
        if c is None:
            return False
        ttl = ttl or self._ttl
        # Stamp when the entry was written so callers can compute cache age
        # without a separate Redis call.
        value = dict(value)
        value.setdefault("_cached_at", int(time.time()))
        value["_expires_at"] = value["_cached_at"] + ttl
        try:
            c.setex(_key(url), ttl, json.dumps(value))
            return True
        except Exception:
            return False

    def has(self, url: str) -> bool:
        c = self.client
        if c is None:
            return False
        try:
            return bool(c.exists(_key(url)))
        except Exception:
            return False

    def invalidate(self, url: str) -> bool:
        c = self.client
        if c is None:
            return False
        try:
            return bool(c.delete(_key(url)))
        except Exception:
            return False


# Module-level singleton for convenience.
cache = Cache()
