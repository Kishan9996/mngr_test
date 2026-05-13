import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.access")

_SKIP_PATHS = {"/health", "/"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request: method, path, status, duration, request ID."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        t0 = time.perf_counter()
        response = await call_next(request)
        ms = (time.perf_counter() - t0) * 1000
        rid = getattr(request.state, "request_id", "-")

        log = logger.warning if ms > 2000 else logger.info
        log(
            "%s %s → %d  %.0fms  [%s]",
            request.method,
            request.url.path,
            response.status_code,
            ms,
            rid,
        )
        return response
