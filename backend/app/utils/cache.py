"""Cache layer — Redis when available, in-memory TTL as fallback.

The public API is identical regardless of backend, so no caller changes
are needed when switching between the two.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── In-memory fallback ────────────────────────────────────────────────────────

class _MemoryCache:
    """Thread-safe TTL cache backed by a plain dict."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry and time.monotonic() < entry[1]:
                return entry[0]
            self._store.pop(key, None)
            return None

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (value, time.monotonic() + self._ttl)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()


# ── Redis backend ─────────────────────────────────────────────────────────────

class _RedisCache:
    """Redis-backed cache; falls back to _MemoryCache if Redis is unreachable."""

    def __init__(self, redis_url: str, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._fallback = _MemoryCache(ttl_seconds)
        self._client = None

        try:
            import redis as _redis
            client = _redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
            client.ping()
            self._client = client
            logger.info("Cache: Redis connected at %s", redis_url)
        except Exception as exc:
            logger.warning("Cache: Redis unavailable (%s) — using in-memory fallback", exc)

    def get(self, key: str) -> Optional[Any]:
        if self._client is None:
            return self._fallback.get(key)
        try:
            raw = self._client.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception:
            return self._fallback.get(key)

    def set(self, key: str, value: Any) -> None:
        if self._client is None:
            self._fallback.set(key, value)
            return
        try:
            self._client.setex(key, self._ttl, json.dumps(value, default=_json_default))
        except Exception:
            self._fallback.set(key, value)

    def delete(self, key: str) -> None:
        if self._client is None:
            self._fallback.delete(key)
            return
        try:
            self._client.delete(key)
        except Exception:
            self._fallback.delete(key)

    def clear(self) -> None:
        self._fallback.clear()


def _json_default(obj: Any) -> Any:
    """Serialise dataclasses; raise TypeError for unknown types."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serialisable")


# ── Factory ───────────────────────────────────────────────────────────────────

def _make_cache(ttl_seconds: int) -> _MemoryCache | _RedisCache:
    from app.core.config import get_settings
    redis_url = get_settings().redis_url
    if redis_url:
        return _RedisCache(redis_url, ttl_seconds)
    return _MemoryCache(ttl_seconds)


# ── Module-level shared caches ────────────────────────────────────────────────
# Instantiated lazily on first use so the app doesn't crash at import time
# if Redis isn't yet running.

_calendar_list_cache: Optional[_MemoryCache | _RedisCache] = None
_cache_lock = threading.Lock()


def _get_calendar_list_cache() -> _MemoryCache | _RedisCache:
    global _calendar_list_cache
    if _calendar_list_cache is None:
        with _cache_lock:
            if _calendar_list_cache is None:
                _calendar_list_cache = _make_cache(ttl_seconds=300)
    return _calendar_list_cache


class calendar_list_cache:  # noqa: N801 — acts as a namespace, not a class
    """Proxy that lazily initialises the real cache on first access."""

    @staticmethod
    def get(key: str) -> Optional[Any]:
        return _get_calendar_list_cache().get(key)

    @staticmethod
    def set(key: str, value: Any) -> None:
        _get_calendar_list_cache().set(key, value)

    @staticmethod
    def delete(key: str) -> None:
        _get_calendar_list_cache().delete(key)
