"""ASGI middlewares for the hosted HTTP MCP server."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from kosis_tools.request_context import current_api_key


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Read ?apiKey=<key> from the URL and pin it to the request's contextvar.

    Resets the contextvar in `finally` so a request never leaks its key into
    a subsequent task on the same event loop.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        api_key = request.query_params.get("apiKey")
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


__all__ = ["ApiKeyMiddleware", "missing_api_key_response"]
