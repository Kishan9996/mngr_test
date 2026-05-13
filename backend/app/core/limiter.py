"""Rate limiting via Depends — avoids slowapi decorator signature issues with FastAPI sync routes."""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Callable

from fastapi import HTTPException, Request

# Simple sliding-window counter: {key: [(timestamp, count)]}
_windows: dict[str, list[float]] = defaultdict(list)
_lock = Lock()


def _check(key: str, max_calls: int, window_seconds: int) -> None:
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        hits = _windows[key]
        # Evict timestamps outside the window
        _windows[key] = [t for t in hits if t > cutoff]
        if len(_windows[key]) >= max_calls:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down.",
                headers={"Retry-After": str(window_seconds)},
            )
        _windows[key].append(now)


def rate_limit(max_calls: int = 60, window_seconds: int = 60) -> Callable:
    """Return a FastAPI Depends factory that enforces a per-IP sliding-window rate limit."""

    def dependency(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        key = f"{ip}:{request.url.path}"
        _check(key, max_calls, window_seconds)

    return dependency


# Pre-built limits for common cases
limit_auth_register = rate_limit(max_calls=5, window_seconds=60)
limit_auth_login = rate_limit(max_calls=10, window_seconds=60)
limit_chat = rate_limit(max_calls=30, window_seconds=60)
