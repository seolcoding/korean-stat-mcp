"""HTTP deployment surface regression tests."""

from __future__ import annotations

from starlette.testclient import TestClient

from mcp_server.app import create_app


def test_http_app_exposes_deployment_metadata() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/info")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "korean-stat-mcp"
    assert body["protocol"] == "MCP Streamable HTTP"
    assert body["endpoints"]["mcp"] == "/mcp"
    assert body["endpoints"]["health"] == "/health"
    assert body["endpoints"]["artifacts"] == "/artifacts"


def test_http_app_exposes_health_check() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "korean-stat-mcp"


def test_http_app_exposes_mcp_endpoint_at_mcp_path(monkeypatch) -> None:
    # Pass the BYOK gate via env so this test exercises the MCP protocol layer,
    # not the missing_api_key 401. The 401 path has dedicated coverage in
    # tests/integration/test_byok_http.py.
    monkeypatch.setenv("KOSIS_API_KEY", "test-key")
    with TestClient(create_app()) as client:
        response = client.get("/mcp")

    # A bare GET without the MCP Streamable HTTP accept headers is rejected by
    # the protocol layer, but the endpoint must exist for remote connectors.
    assert response.status_code in {200, 405, 406}
    assert response.status_code != 404
