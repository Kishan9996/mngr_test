"""Retry decorator with exponential backoff for transient external API errors."""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable)

# HTTP status codes worth retrying (rate-limit and server errors)
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


def _is_retryable(exc: Exception) -> bool:
    """Return True for transient errors that may succeed on retry."""
    # Google API errors
    try:
        from googleapiclient.errors import HttpError  # type: ignore
        if isinstance(exc, HttpError):
            return int(exc.resp.status) in RETRYABLE_STATUS_CODES
    except ImportError:
        pass

    # httpx errors (Outlook / any other HTTP client)
    try:
        import httpx
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in RETRYABLE_STATUS_CODES
        if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError)):
            return True
    except ImportError:
        pass

    # Generic network / connection errors
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True

    return False


def with_retry(
    max_attempts: int = 3,
    backoff_base: float = 1.0,
    retryable: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator: retry `fn` up to `max_attempts` times with exponential backoff.

    Only retries when `_is_retryable(exc)` returns True, so permanent errors
    (e.g. 401 Unauthorized, 403 Forbidden) are raised immediately.
    """
    def decorator(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc: Exception | None = None
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except retryable as exc:
                    if not _is_retryable(exc):
                        raise
                    last_exc = exc
                    if attempt == max_attempts - 1:
                        break
                    wait = backoff_base * (2 ** attempt)   # 1s, 2s, 4s …
                    logger.warning(
                        "Transient error in %s (attempt %d/%d) — retrying in %.1fs: %s",
                        fn.__qualname__,
                        attempt + 1,
                        max_attempts,
                        wait,
                        exc,
                    )
                    time.sleep(wait)
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator
