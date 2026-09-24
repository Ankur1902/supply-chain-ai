import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger("http")

MAX_REQUEST_BODY_BYTES = 2 * 1024 * 1024  # 2 MB request size cap


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request_id, enforces a request-size limit, adds security
    headers, and logs structured access lines with latency."""

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id)

        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
            return Response(
                content='{"error":{"code":"PAYLOAD_TOO_LARGE","message":"Request body too large"}}',
                status_code=413,
                media_type="application/json",
            )

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled_request_error", path=request.url.path)
            raise
        latency_ms = int((time.perf_counter() - start) * 1000)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
        )
        structlog.contextvars.clear_contextvars()
        return response
