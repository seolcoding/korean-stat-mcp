"""ASGI middlewares for the hosted HTTP MCP server."""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from kosis_tools.request_context import current_api_key


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Read ?apiKey=<key> from /mcp requests; 401 if no key and no env fallback."""

    GUARDED_PATH_PREFIX = "/mcp"

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        api_key = request.query_params.get("apiKey")
        if (
            request.url.path.startswith(self.GUARDED_PATH_PREFIX)
            and not api_key
            and not os.getenv("KOSIS_API_KEY")
        ):
            return missing_api_key_response()

        token = current_api_key.set(api_key) if api_key else None
        try:
            return await call_next(request)
        finally:
            if token is not None:
                current_api_key.reset(token)


def missing_api_key_response() -> Response:
    """Standard 401 body returned when neither query param nor env supplies a key."""
    return JSONResponse(
        {
            "error": "missing_api_key",
            "message": (
                "Provide ?apiKey=<your KOSIS OpenAPI key> in the connector URL, "
                "or set KOSIS_API_KEY for a self-hosted deployment."
            ),
            "issue_url": "https://kosis.kr/openapi/",
        },
        status_code=401,
    )


import hashlib

from limits import RateLimitItemPerMinute
from limits.aio.storage import MemoryStorage
from limits.aio.strategies import MovingWindowRateLimiter


def _bucket_key(request: Request) -> str:
    """Composite bucket: client IP + first 8 chars of sha256(apiKey).

    IP-only would let one buggy user starve everyone behind a NAT;
    apiKey-only would let one user rotate IPs to bypass.
    """
    client = request.client
    ip = client.host if client else "unknown"
    api_key = request.query_params.get("apiKey", "")
    digest = hashlib.sha256(api_key.encode()).hexdigest()[:8] if api_key else "anon"
    return f"{ip}:{digest}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Path-agnostic rate limit. RATE_LIMIT_RPM env (default 300) requests
    per minute per (IP, apiKey hash) bucket. Applies to /mcp, /health, /info.
    """

    def __init__(self, app, rpm: int | None = None) -> None:
        super().__init__(app)
        self._storage = MemoryStorage()
        self._strategy = MovingWindowRateLimiter(self._storage)
        configured_rpm = rpm if rpm is not None else int(os.getenv("RATE_LIMIT_RPM", "300"))
        self._limit = RateLimitItemPerMinute(configured_rpm)

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        bucket = _bucket_key(request)
        allowed = await self._strategy.hit(self._limit, bucket)
        if not allowed:
            return JSONResponse(
                {"error": "rate_limit_exceeded", "detail": "too many requests"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        return await call_next(request)


__all__ = [
    "ApiKeyMiddleware",
    "missing_api_key_response",
    "RateLimitMiddleware",
]
