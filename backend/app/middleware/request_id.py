import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a short request ID to every request and echo it in the response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
