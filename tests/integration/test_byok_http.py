"""End-to-end BYOK contract tests using Starlette TestClient."""

from __future__ import annotations

import asyncio

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from kosis_tools.request_context import current_api_key
from mcp_server.middleware import ApiKeyMiddleware


def _make_test_app() -> Starlette:
    """Tiny app that echoes the contextvar so we can assert on it."""

    async def echo(request):
        return JSONResponse({"api_key": current_api_key.get()})

    app = Starlette(routes=[Route("/echo", echo)])
    app.add_middleware(ApiKeyMiddleware)
    return app


def test_query_param_sets_contextvar():
    client = TestClient(_make_test_app())
    response = client.get("/echo?apiKey=k1")
    assert response.status_code == 200
    assert response.json() == {"api_key": "k1"}


def test_no_query_param_leaves_contextvar_unset():
    client = TestClient(_make_test_app())
    response = client.get("/echo")
    assert response.status_code == 200
    assert response.json() == {"api_key": None}


def test_contextvar_reset_after_request():
    client = TestClient(_make_test_app())
    client.get("/echo?apiKey=k1")
    # Contextvar must not leak into the test process after the request finishes.
    assert current_api_key.get() is None


@pytest.mark.asyncio
async def test_concurrent_requests_do_not_bleed():
    """Two concurrent requests with different keys each see their own."""
    from httpx import ASGITransport, AsyncClient

    app = _make_test_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        results = await asyncio.gather(
            ac.get("/echo?apiKey=k-a"),
            ac.get("/echo?apiKey=k-b"),
        )
    assert {r.json()["api_key"] for r in results} == {"k-a", "k-b"}
