"""In-process TTL cache for database query results.

Key: (org_id, tool_name, sha256(sorted_params))
Different TTLs per tool — ticket status changes faster than order totals.
Thread-safe via Lock.
"""

from __future__ import annotations

import hashlib
import json
import logging
from threading import Lock
from typing import Any, Optional

from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Seconds to cache each tool's results
_TOOL_TTLS: dict[str, int] = {
    "lookup_customer":    60,    # 1 min
    "query_ecommerce":   300,    # 5 min
    "query_support":     120,    # 2 min — status/priority changes
    "query_cross_domain": 300,   # 5 min
    "query_with_schema":  60,    # 1 min — arbitrary SQL, be conservative
}


class QueryCache:
    def __init__(self) -> None:
        self._caches: dict[str, TTLCache] = {
            name: TTLCache(maxsize=256, ttl=ttl)
            for name, ttl in _TOOL_TTLS.items()
        }
        self._lock = Lock()

    def get(self, org_id: int, tool_name: str, params: dict) -> Optional[Any]:
        cache = self._caches.get(tool_name)
        if cache is None:
            return None
        key = self._key(org_id, params)
        with self._lock:
            hit = cache.get(key)
        if hit is not None:
            logger.debug("Cache HIT  %s org=%d", tool_name, org_id)
        return hit

    def set(self, org_id: int, tool_name: str, params: dict, result: Any) -> None:
        cache = self._caches.get(tool_name)
        if cache is None:
            return
        key = self._key(org_id, params)
        with self._lock:
            cache[key] = result
        logger.debug("Cache SET  %s org=%d", tool_name, org_id)

    def invalidate_org(self, org_id: int) -> None:
        """Blow all cached results for an org — call after seeding."""
        prefix = f"{org_id}:"
        cleared = 0
        with self._lock:
            for cache in self._caches.values():
                stale = [k for k in list(cache) if str(k).startswith(prefix)]
                for k in stale:
                    del cache[k]
                    cleared += 1
        logger.info("Cache invalidated org=%d (%d entries evicted)", org_id, cleared)

    @staticmethod
    def _key(org_id: int, params: dict) -> str:
        h = hashlib.sha256(
            json.dumps(params, sort_keys=True, default=str).encode()
        ).hexdigest()[:12]
        return f"{org_id}:{h}"
