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


def test_mcp_endpoint_requires_api_key_without_env(monkeypatch):
    """When env is unset and ?apiKey= is missing, /mcp returns 401."""
    monkeypatch.delenv("KOSIS_API_KEY", raising=False)
    from mcp_server.app import create_app

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"] == "missing_api_key"
    assert "kosis.kr/openapi" in body["issue_url"]


def test_mcp_endpoint_accepts_api_key_via_query(monkeypatch):
    """When ?apiKey= is set, the middleware does not 401 — request proceeds."""
    monkeypatch.delenv("KOSIS_API_KEY", raising=False)
    from mcp_server.app import create_app

    app = create_app()
    # raise_server_exceptions=False so FastMCP's uninitialized task group
    # (expected in TestClient without full lifespan) yields a 500 rather
    # than propagating as a Python exception.
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/mcp?apiKey=k1",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    # 401 is the only thing we ruled out; downstream may be 200 or another
    # MCP-level status, depending on FastMCP. The point is that the gate
    # passes when a key is supplied.
    assert response.status_code != 401


def test_rate_limit_returns_429(monkeypatch):
    """After RATE_LIMIT_RPM, subsequent requests within the window get 429."""
    monkeypatch.setenv("RATE_LIMIT_RPM", "2")
    monkeypatch.setenv("KOSIS_API_KEY", "env-key")  # so 401 gate passes
    from mcp_server.app import create_app

    app = create_app()
    client = TestClient(app)

    r1 = client.get("/health")
    r2 = client.get("/health")
    r3 = client.get("/health")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert "Retry-After" in r3.headers
