# Stream A — Public Hosting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up `https://kosis.seolcoding.com/mcp?apiKey=<key>` as a public hosted instance of `korean-stat-mcp` on Fly.io, with per-request BYOK key handling, full pre-deploy CI gates, and a documented manual cutover procedure.

**Architecture:** Per-request KOSIS API key flows from URL query string → Starlette middleware → `ContextVar` → `load_config()` (contextvar wins, falls back to env for self-hosters). Single Fly.io VM in `nrt`, scale-to-zero with suspend-resume, slowapi rate limiting per IP and per key hash.

**Tech Stack:** Python 3.12, FastMCP 2.14, Starlette, slowapi, uv, Fly.io, GitHub Actions, Docker (2-stage).

**Spec:** [`docs/superpowers/specs/2026-04-30-hosting-design.md`](../specs/2026-04-30-hosting-design.md)

**Branch:** `feat/hosting` off `main`.

---

## File Structure

| Path | Status | Responsibility |
|---|---|---|
| `src/kosis_tools/request_context.py` | Create | Define `current_api_key: ContextVar[str \| None]`. Lives in `kosis_tools` so `config.py` can import it without crossing into `mcp_server` (preserves layering). |
| `src/kosis_tools/config.py` | Modify | `load_config()` reads contextvar first, then env. No new fields on `KosisConfig`. |
| `src/mcp_server/middleware.py` | Create | `ApiKeyMiddleware` (extracts `?apiKey=` and sets contextvar) + `RateLimitMiddleware` wiring (slowapi). |
| `src/mcp_server/app.py` | Modify | Wire the new middlewares into `create_app()`. |
| `tests/unit/test_request_context.py` | Create | Unit + asyncio isolation tests for the contextvar. |
| `tests/unit/test_load_config_priority.py` | Create | `load_config()` priority order (contextvar > env > raise). |
| `tests/unit/test_base.py` | Modify | Existing `TestKosisConfig` class — add coverage for the env-unset + contextvar-unset branch (currently asserts via env only). |
| `tests/integration/test_byok_http.py` | Create | End-to-end Starlette test client: concurrent requests with different `?apiKey=`; 401 path; rate limit 429. |
| `Dockerfile` | Modify | Already 2-stage; minor cleanup, add `RATE_LIMIT_RPM` env passthrough. |
| `fly.toml` | Modify | `auto_stop_machines = "suspend"`, `RATE_LIMIT_RPM`, memory tuning. |
| `.github/workflows/deploy.yml` | Create | 5-gate pipeline: pytest → docker build → container smoke → fly deploy → post-deploy probe. |
| `README.md` | Modify | New "Hosted instance (no install)" section above existing methods. |
| `README-EN.md` | Modify | Same section in English. |
| `MIGRATION.md` | Modify | Note for self-hosters: ENV path unchanged. |
| `pyproject.toml` | Modify | Add `slowapi>=0.1.9` to dependencies. |

---

## Task 0: Branch setup

**Files:**
- N/A (branch only)

- [ ] **Step 0.1: Verify clean working tree on `main`**

```bash
git status
git pull --ff-only
```

Expected: `working tree clean` and `up to date with origin/main`.

- [ ] **Step 0.2: Create and switch to `feat/hosting`**

```bash
git switch -c feat/hosting
```

Expected: `Switched to a new branch 'feat/hosting'`.

- [ ] **Step 0.3: Confirm baseline test suite passes**

```bash
uv sync --all-extras --dev
uv run pytest -q
```

Expected: 449 tests pass (matches README claim). If lower or any fail, stop and resolve before touching code.

---

## Task 1: `current_api_key` ContextVar

**Files:**
- Create: `src/kosis_tools/request_context.py`
- Test: `tests/unit/test_request_context.py`

- [ ] **Step 1.1: Write the failing test**

Create `tests/unit/test_request_context.py`:

```python
"""Per-request API key contextvar isolation tests."""

from __future__ import annotations

import asyncio

import pytest

from kosis_tools.request_context import current_api_key


def test_default_is_none():
    assert current_api_key.get() is None


def test_set_and_get():
    token = current_api_key.set("abc")
    try:
        assert current_api_key.get() == "abc"
    finally:
        current_api_key.reset(token)
    assert current_api_key.get() is None


@pytest.mark.asyncio
async def test_isolation_across_concurrent_tasks():
    """Two concurrent tasks each see only their own key — never bleed."""
    seen: dict[str, str | None] = {}

    async def worker(name: str, key: str) -> None:
        token = current_api_key.set(key)
        try:
            await asyncio.sleep(0)  # yield to the other task
            seen[name] = current_api_key.get()
        finally:
            current_api_key.reset(token)

    await asyncio.gather(worker("a", "key-a"), worker("b", "key-b"))
    assert seen == {"a": "key-a", "b": "key-b"}
    assert current_api_key.get() is None
```

- [ ] **Step 1.2: Run the test to verify it fails**

```bash
uv run pytest tests/unit/test_request_context.py -v
```

Expected: `ImportError: kosis_tools.request_context` or `ModuleNotFoundError`.

- [ ] **Step 1.3: Create the contextvar module**

Create `src/kosis_tools/request_context.py`:

```python
"""Per-request API key context for the HTTP server.

The hosted MCP server lets users supply their KOSIS OpenAPI key via a
URL query parameter on each call. The ApiKeyMiddleware in mcp_server stores
the per-request key here so that load_config() can read it without changing
every tool's signature.

stdio mode never sets this contextvar; load_config() falls back to env.
"""

from __future__ import annotations

from contextvars import ContextVar

current_api_key: ContextVar[str | None] = ContextVar("current_api_key", default=None)
```

- [ ] **Step 1.4: Run the test to verify it passes**

```bash
uv run pytest tests/unit/test_request_context.py -v
```

Expected: 3 passed.

- [ ] **Step 1.5: Commit**

```bash
git add src/kosis_tools/request_context.py tests/unit/test_request_context.py
git commit -m "feat: add per-request KOSIS api key contextvar"
```

---

## Task 2: `load_config()` priority — contextvar > env > raise

**Files:**
- Modify: `src/kosis_tools/config.py:104-151`
- Test: `tests/unit/test_load_config_priority.py` (create)
- Test: `tests/unit/test_base.py` (extend `TestKosisConfig`)

- [ ] **Step 2.1: Write the failing test**

Create `tests/unit/test_load_config_priority.py`:

```python
"""load_config() priority: contextvar > env > ValueError."""

from __future__ import annotations

import pytest

from kosis_tools.config import load_config
from kosis_tools.request_context import current_api_key


def test_contextvar_wins_over_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KOSIS_API_KEY", "from-env")
    token = current_api_key.set("from-contextvar")
    try:
        config = load_config()
        assert config.api_key == "from-contextvar"
    finally:
        current_api_key.reset(token)


def test_env_used_when_contextvar_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KOSIS_API_KEY", "from-env")
    assert current_api_key.get() is None
    config = load_config()
    assert config.api_key == "from-env"


def test_raises_when_neither_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("KOSIS_API_KEY", raising=False)
    assert current_api_key.get() is None
    with pytest.raises(ValueError, match="KOSIS_API_KEY"):
        load_config()


def test_empty_contextvar_falls_back_to_env(monkeypatch: pytest.MonkeyPatch):
    """Empty string contextvar (treated as missing) defers to env."""
    monkeypatch.setenv("KOSIS_API_KEY", "from-env")
    token = current_api_key.set("")
    try:
        config = load_config()
        assert config.api_key == "from-env"
    finally:
        current_api_key.reset(token)
```

- [ ] **Step 2.2: Run the test to verify it fails**

```bash
uv run pytest tests/unit/test_load_config_priority.py -v
```

Expected: `test_contextvar_wins_over_env` fails (returns "from-env" because `load_config` doesn't yet read the contextvar). The other tests may pass since the env path already exists.

- [ ] **Step 2.3: Patch `load_config()` to honor the contextvar**

Edit `src/kosis_tools/config.py`. Replace the body of `load_config()` (currently lines 137–151):

```python
def load_config() -> KosisConfig:
    """
    환경변수 또는 요청 컨텍스트에서 KOSIS API 설정을 로드합니다.

    우선순위: request_context.current_api_key > 환경변수 KOSIS_API_KEY > ValueError.

    HTTP 호스팅 모드에서는 ApiKeyMiddleware가 요청별 키를 contextvar에 주입합니다.
    stdio 모드와 자체 호스팅에서는 contextvar가 비어 있으므로 환경변수 경로를 그대로 사용합니다.

    Raises:
        ValueError: contextvar 와 환경변수 모두에서 키를 찾을 수 없는 경우
    """
    from .request_context import current_api_key

    api_key = current_api_key.get() or os.getenv("KOSIS_API_KEY")
    if not api_key:
        raise ValueError(
            "KOSIS_API_KEY 환경변수가 설정되지 않았습니다. "
            ".env 파일이나 환경변수에 API 키를 설정하거나, "
            "호스팅 모드에서는 URL에 ?apiKey=<key>를 포함해주세요."
        )

    return KosisConfig(
        api_key=api_key,
        base_url=os.getenv("KOSIS_API_ENDPOINT", "https://kosis.kr/openapi"),
        rate_limit_delay=float(os.getenv("KOSIS_RATE_LIMIT", "1.0")),
        timeout=int(os.getenv("KOSIS_TIMEOUT", "60")),
        max_retries=int(os.getenv("KOSIS_MAX_RETRIES", "3")),
        retry_delay=float(os.getenv("KOSIS_RETRY_DELAY", "2.0")),
    )
```

(Existing module docstring above this function and the `import os` at the top stay as-is. Only the `load_config()` body changes.)

- [ ] **Step 2.4: Run the new tests**

```bash
uv run pytest tests/unit/test_load_config_priority.py -v
```

Expected: 4 passed.

- [ ] **Step 2.5: Run the existing `TestKosisConfig` class to confirm no regression**

```bash
uv run pytest tests/unit/test_base.py::TestKosisConfig -v
```

Expected: all existing 6 tests still pass.

- [ ] **Step 2.6: Run the full test suite**

```bash
uv run pytest -q
```

Expected: 449 + 4 = 453 passed.

- [ ] **Step 2.7: Commit**

```bash
git add src/kosis_tools/config.py tests/unit/test_load_config_priority.py
git commit -m "feat: load_config reads contextvar before env"
```

---

## Task 3: `ApiKeyMiddleware` — extract `?apiKey=` per request

**Files:**
- Create: `src/mcp_server/middleware.py`
- Modify: `src/mcp_server/app.py:142-148` (insert middleware before CORS)

- [ ] **Step 3.1: Write the failing test (integration)**

Create `tests/integration/test_byok_http.py`:

```python
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
```

- [ ] **Step 3.2: Run to verify it fails**

```bash
uv run pytest tests/integration/test_byok_http.py -v
```

Expected: `ImportError: cannot import name 'ApiKeyMiddleware' from 'mcp_server.middleware'`.

- [ ] **Step 3.3: Implement `ApiKeyMiddleware`**

Create `src/mcp_server/middleware.py`:

```python
"""ASGI middlewares for the hosted HTTP MCP server."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

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
```

- [ ] **Step 3.4: Run the middleware tests**

```bash
uv run pytest tests/integration/test_byok_http.py -v
```

Expected: 4 passed.

- [ ] **Step 3.5: Wire the middleware into `create_app()`**

Edit `src/mcp_server/app.py`. After the CORS middleware block (currently around lines 142–148), add:

```python
    # Per-request KOSIS API key extraction. Must run before MCP handlers so
    # that load_config() inside any tool sees the request's key.
    from .middleware import ApiKeyMiddleware
    mcp_app.add_middleware(ApiKeyMiddleware)
```

Place this immediately after the existing `mcp_app.add_middleware(CORSMiddleware, ...)` call.

- [ ] **Step 3.6: Run the full integration suite**

```bash
uv run pytest tests/integration -v
```

Expected: existing integration tests pass + 4 new BYOK tests pass.

- [ ] **Step 3.7: Run the full test suite**

```bash
uv run pytest -q
```

Expected: 453 + 4 = 457 passed.

- [ ] **Step 3.8: Commit**

```bash
git add src/mcp_server/middleware.py src/mcp_server/app.py tests/integration/test_byok_http.py
git commit -m "feat: ApiKeyMiddleware extracts ?apiKey= into request contextvar"
```

---

## Task 4: 401 response when neither contextvar nor env supplies a key

**Files:**
- Modify: `src/mcp_server/app.py` (use `missing_api_key_response` in a guard)
- Test: extend `tests/integration/test_byok_http.py`

The MCP protocol path `/mcp` itself runs many internal calls before any tool actually invokes `load_config()`. Rather than fail deep inside FastMCP, gate at the middleware level: if a request hits `/mcp` with no `?apiKey=` AND no `KOSIS_API_KEY` env var is set, return 401 immediately.

- [ ] **Step 4.1: Add the failing test**

Append to `tests/integration/test_byok_http.py`:

```python
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
    client = TestClient(app)
    response = client.post(
        "/mcp?apiKey=k1",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    # 401 is the only thing we ruled out; downstream may be 200 or another
    # MCP-level status, depending on FastMCP. The point is that the gate
    # passes when a key is supplied.
    assert response.status_code != 401
```

- [ ] **Step 4.2: Run to verify the new tests fail**

```bash
uv run pytest tests/integration/test_byok_http.py -v
```

Expected: both new tests fail (current middleware does not 401 on missing key).

- [ ] **Step 4.3: Tighten `ApiKeyMiddleware`**

Edit `src/mcp_server/middleware.py`. Replace the `dispatch` method:

```python
import os

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
```

(Add `import os` at the module top if not already present.)

- [ ] **Step 4.4: Run the integration tests**

```bash
uv run pytest tests/integration/test_byok_http.py -v
```

Expected: 6 passed.

- [ ] **Step 4.5: Run the full suite**

```bash
uv run pytest -q
```

Expected: 459 passed.

- [ ] **Step 4.6: Commit**

```bash
git add src/mcp_server/middleware.py tests/integration/test_byok_http.py
git commit -m "feat: 401 missing_api_key on /mcp without key or env"
```

---

## Task 5: Rate limiting per IP and per apiKey hash

**Files:**
- Modify: `pyproject.toml` (add `slowapi`)
- Modify: `src/mcp_server/middleware.py` (add `build_rate_limiter`)
- Modify: `src/mcp_server/app.py` (wire limiter)
- Test: extend `tests/integration/test_byok_http.py`

- [ ] **Step 5.1: Add slowapi dependency**

Edit `pyproject.toml`. In the `dependencies = [...]` array, append:

```toml
    "slowapi>=0.1.9",
```

Then sync:

```bash
uv sync --all-extras --dev
```

Expected: `slowapi` installs without conflict.

- [ ] **Step 5.2: Write the failing rate-limit test**

Append to `tests/integration/test_byok_http.py`:

```python
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
```

- [ ] **Step 5.3: Run to verify it fails**

```bash
uv run pytest tests/integration/test_byok_http.py::test_rate_limit_returns_429 -v
```

Expected: `r3.status_code == 200` not 429 (no limiter wired yet).

- [ ] **Step 5.4: Implement `build_rate_limiter`**

Append to `src/mcp_server/middleware.py`:

```python
import hashlib

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _key_func(request: Request) -> str:
    """Rate-limit bucket = client IP + first 8 chars of apiKey hash.

    Using only IP would let one buggy user starve everyone behind the same NAT;
    using only the apiKey would let one user rotate IPs to bypass it. The
    composite bucket caps both axes.
    """
    ip = get_remote_address(request)
    api_key = request.query_params.get("apiKey", "")
    digest = hashlib.sha256(api_key.encode()).hexdigest()[:8] if api_key else "anon"
    return f"{ip}:{digest}"


def build_rate_limiter() -> Limiter:
    """Create a slowapi Limiter using `RATE_LIMIT_RPM` from env (default 300)."""
    rpm = int(os.getenv("RATE_LIMIT_RPM", "300"))
    return Limiter(
        key_func=_key_func,
        default_limits=[f"{rpm}/minute"],
        headers_enabled=True,
    )


__all__ = [
    "ApiKeyMiddleware",
    "missing_api_key_response",
    "build_rate_limiter",
    "RateLimitExceeded",
]
```

- [ ] **Step 5.5: Wire the limiter into `create_app()`**

Edit `src/mcp_server/app.py`. After the `ApiKeyMiddleware` registration added in Task 3.5, add:

```python
    # Rate limiting (default 300 rpm, override via RATE_LIMIT_RPM).
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    from .middleware import build_rate_limiter

    limiter = build_rate_limiter()
    mcp_app.state.limiter = limiter
    mcp_app.add_middleware(SlowAPIMiddleware)

    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            {"error": "rate_limit_exceeded", "detail": str(exc.detail)},
            status_code=429,
            headers={"Retry-After": "60"},
        )

    mcp_app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
```

- [ ] **Step 5.6: Run the rate-limit test**

```bash
uv run pytest tests/integration/test_byok_http.py::test_rate_limit_returns_429 -v
```

Expected: passed.

- [ ] **Step 5.7: Run the full suite**

```bash
uv run pytest -q
```

Expected: 460 passed (or higher; no regressions).

- [ ] **Step 5.8: Commit**

```bash
git add pyproject.toml uv.lock src/mcp_server/middleware.py src/mcp_server/app.py tests/integration/test_byok_http.py
git commit -m "feat: per-IP+apiKey rate limiting with slowapi"
```

---

## Task 6: Dockerfile cleanup + local smoke

**Files:**
- Modify: `Dockerfile`

The current Dockerfile is already 2-stage and non-root. Two small changes: drop the `scripts/` copy (not needed for the hosted service — those are admin/maintenance scripts) and make `RATE_LIMIT_RPM` an explicit ENV with the documented default.

- [ ] **Step 6.1: Update Dockerfile**

Edit `Dockerfile`. Find the `# Copy scripts for updater service` block and the `COPY scripts/ scripts/` line; remove both. Then, in the `# Default environment` block (currently `ENV FASTMCP_STATELESS_HTTP=true`), append:

```dockerfile
ENV RATE_LIMIT_RPM=300
```

- [ ] **Step 6.2: Build the image**

```bash
docker build -t korean-stat-mcp:dev .
```

Expected: build succeeds (a few minutes on first run, ~30s on rebuild).

- [ ] **Step 6.3: Smoke-run the container with a fake env key**

```bash
docker run -d --rm --name kstat-smoke -p 8000:8000 \
  -e KOSIS_API_KEY=ci-fake-key korean-stat-mcp:dev
sleep 3
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/info | head -c 200
docker stop kstat-smoke
```

Expected: `/health` returns `{"status":"healthy",...}`; `/info` returns JSON with `"service":"korean-stat-mcp"`.

- [ ] **Step 6.4: Smoke the BYOK path through the container**

```bash
docker run -d --rm --name kstat-smoke -p 8000:8000 korean-stat-mcp:dev
sleep 3
# No env, no ?apiKey= → expect 401
curl -fsS -o /tmp/out -w "%{http_code}\n" -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' || true
cat /tmp/out
docker stop kstat-smoke
```

Expected: HTTP 401, body contains `"error":"missing_api_key"`.

- [ ] **Step 6.5: Commit**

```bash
git add Dockerfile
git commit -m "chore: trim Dockerfile, expose RATE_LIMIT_RPM"
```

---

## Task 7: `fly.toml` — suspend, RATE_LIMIT_RPM, mem

**Files:**
- Modify: `fly.toml`

- [ ] **Step 7.1: Update fly.toml**

Replace `fly.toml` with:

```toml
# fly.toml - Fly.io deployment for korean-stat-mcp
# Region nrt (Tokyo) keeps RTT to Korean users in the 30-50ms range.

app = "korean-stat-mcp"
primary_region = "nrt"

[build]
  dockerfile = "Dockerfile"

[env]
  FASTMCP_STATELESS_HTTP = "true"
  PYTHONUNBUFFERED = "1"
  RATE_LIMIT_RPM = "300"

[http_service]
  internal_port = 8000
  force_https = true
  # Suspend (instead of stop) preserves the running process state, so warm
  # starts are sub-second; falls back to a true cold start only after long
  # idleness. Keeps the cost-control benefit of scale-to-zero.
  auto_stop_machines = "suspend"
  auto_start_machines = true
  min_machines_running = 0
  processes = ["app"]

  [[http_service.checks]]
    grace_period = "30s"
    interval = "30s"
    method = "GET"
    timeout = "10s"
    path = "/health"

[[vm]]
  size = "shared-cpu-1x"
  # 512mb keeps headroom for asyncio + json5 parsing on large KOSIS payloads.
  # If memory metrics show steady RSS < 200MB after the soak, downsize to 256.
  memory = "512mb"
  cpu_kind = "shared"
  cpus = 1
```

(Note the deviation from the spec's 256mb — the spec capped soak-window memory at 256mb; the plan keeps the existing 512mb baseline so the *first* deploy has headroom, with a documented downsize path. Update the spec at the end of the rollout if soak data supports the smaller VM.)

- [ ] **Step 7.2: Validate the toml**

```bash
fly config validate -c fly.toml 2>&1 | head -10
```

Expected: `Configuration is valid`. (If flyctl is not installed yet, this step blocks until §15.1 prerequisites are done — that's intentional.)

- [ ] **Step 7.3: Commit**

```bash
git add fly.toml
git commit -m "chore(fly): suspend on idle, RATE_LIMIT_RPM env"
```

---

## Task 8: GitHub Actions deploy workflow with all 5 gates

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 8.1: Create the workflow**

Create `.github/workflows/deploy.yml`:

```yaml
name: deploy

on:
  workflow_run:
    workflows: ["CI"]   # exact name in .github/workflows/ci.yml
    branches: [main]
    types: [completed]
  workflow_dispatch:

concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: false

jobs:
  deploy:
    if: ${{ github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4

      # Gate 1: full pytest re-run
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --all-extras --dev
      - run: uv run pytest -q

      # Gate 2: build the production Docker image (same artifact that ships)
      - run: docker build -t korean-stat-mcp:ci .

      # Gate 3: container smoke test
      - name: Container smoke test
        run: |
          set -eu
          docker run -d --rm --name kstat-smoke -p 8000:8000 \
            -e KOSIS_API_KEY=ci-fake-key korean-stat-mcp:ci
          for i in $(seq 1 20); do
            if curl -fsS http://localhost:8000/health >/dev/null; then break; fi
            sleep 1
          done
          curl -fsS http://localhost:8000/health
          curl -fsS http://localhost:8000/info | grep -q "korean-stat-mcp"
          # 401 path: container with no env, expect missing_api_key
          docker stop kstat-smoke
          docker run -d --rm --name kstat-smoke -p 8000:8000 korean-stat-mcp:ci
          for i in $(seq 1 20); do
            if curl -fsS http://localhost:8000/health >/dev/null; then break; fi
            sleep 1
          done
          code=$(curl -s -o /tmp/body -w "%{http_code}" -X POST http://localhost:8000/mcp \
            -H 'Content-Type: application/json' \
            -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}')
          test "$code" = "401"
          grep -q '"missing_api_key"' /tmp/body
          docker stop kstat-smoke

      # Gate 4: deploy
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}

      # Gate 5: post-deploy health probe (uses fly.dev hostname; DNS comes
      # online in the manual cutover step in §15.8 of the spec)
      - name: Post-deploy health probe
        run: |
          for i in $(seq 1 30); do
            if curl -fsS https://korean-stat-mcp.fly.dev/health; then exit 0; fi
            sleep 2
          done
          echo "post-deploy health probe failed"; exit 1
```

- [ ] **Step 8.2: Verify YAML parses**

```bash
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/deploy.yml'))"
```

Expected: no output (clean parse).

- [ ] **Step 8.3: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: add gated deploy workflow for fly.io"
```

---

## Task 9: README — Hosted instance section

**Files:**
- Modify: `README.md`
- Modify: `README-EN.md`

Mirror the layout of `chrisryugj/korean-law-mcp` README §방법 2 — Claude.ai 커넥터 등록 단계별 안내.

- [ ] **Step 9.1: Insert the hosted section in `README.md`**

In `README.md`, find the line `## 설치` (Installation header). **Above** it, insert:

```markdown
## 호스팅 인스턴스로 바로 사용 (설치 없음)

`pip install` 없이, Claude.ai 커넥터에 URL 한 줄만 추가하면 됩니다.
Claude Pro/Max/Team/Enterprise 요금제가 필요합니다 (Free는 커넥터 1개만 가능).

### 0단계: KOSIS API 키 발급 (무료, 1분)

[KOSIS OpenAPI 신청 페이지](https://kosis.kr/openapi/)에서 회원가입 후
"Open API 사용 신청" 버튼을 누르면 인증키가 발급됩니다.

### 커넥터 추가 방법

1. [claude.ai](https://claude.ai)에 로그인합니다.
2. 왼쪽 사이드바 하단의 **본인 이름** → **설정** → **커넥터** 메뉴로 들어갑니다.
3. **커스텀 커넥터 추가** 버튼을 클릭합니다.
4. 아래 내용을 입력합니다 (`<YOUR_KEY>` 를 0단계에서 발급받은 키로 바꿉니다):
   - **이름**: `korean-stat`
   - **URL**: `https://kosis.seolcoding.com/mcp?apiKey=<YOUR_KEY>`
5. **추가** 버튼을 누르면 등록 완료.
6. 추가한 커넥터의 **구성** → 도구 목록에서 모든 도구를 **항상 사용**으로 설정.

### 사용

채팅 화면에서 자연어로 물어보면 `korean-stat` 도구가 자동 호출됩니다:

```
"2020년부터 2023년까지 전국 인구 추이 보여줘"
"서울 자치구별 사업체 수 비교"
```

### 자체 호스팅도 그대로 동작

기존 `pip install` + `KOSIS_API_KEY` 환경변수 방식은 변경 없이 작동합니다. 아래 [설치](#설치) 섹션을 참고하세요.

---
```

- [ ] **Step 9.2: Insert the equivalent in `README-EN.md`**

Find the matching `## Installation` (or similar) header in `README-EN.md` and prepend an English translation of the section above. Use exact same URL and steps.

- [ ] **Step 9.3: Commit**

```bash
git add README.md README-EN.md
git commit -m "docs: add hosted-instance quickstart to READMEs"
```

---

## Task 10: MIGRATION.md — note for self-hosters

**Files:**
- Modify: `MIGRATION.md`

- [ ] **Step 10.1: Append the migration note**

Append to `MIGRATION.md`:

```markdown
---

## 0.2.0 — Hosted instance + per-request API key

A public hosted endpoint at `https://kosis.seolcoding.com/mcp` is now available. URL form:

```
https://kosis.seolcoding.com/mcp?apiKey=<your KOSIS OpenAPI key>
```

For self-hosted deployments **nothing changes** — `KOSIS_API_KEY` env var still works exactly as before. The new behavior:

- HTTP requests with `?apiKey=` use that per-request key (env is ignored for that request).
- HTTP requests with no `?apiKey=` fall back to env.
- Without either, `/mcp` returns `401 missing_api_key` instead of failing deep inside a tool.

stdio mode is unchanged.
```

- [ ] **Step 10.2: Commit**

```bash
git add MIGRATION.md
git commit -m "docs: migration note for hosted instance + BYOK"
```

---

## Task 11: Open the PR

**Files:**
- N/A (GitHub PR)

- [ ] **Step 11.1: Push the branch**

```bash
git push -u origin feat/hosting
```

- [ ] **Step 11.2: Open the PR**

```bash
gh pr create --title "Stream A: public hosted instance with BYOK" --body "$(cat <<'EOF'
## Summary
- Public hosted endpoint at `https://kosis.seolcoding.com/mcp?apiKey=<key>`
- Per-request KOSIS key via URL query → contextvar → load_config (env fallback preserved for self-hosters)
- 5-gate deploy pipeline: pytest → docker build → container smoke → fly deploy → post-deploy probe
- slowapi rate limiting per IP + apiKey hash bucket
- Docs: hosted quickstart in README KO/EN, MIGRATION note for self-hosters

Spec: `docs/superpowers/specs/2026-04-30-hosting-design.md`
Plan: `docs/superpowers/plans/2026-04-30-stream-a-hosting.md`

## Test plan
- [x] All existing 449 tests still pass
- [x] New unit tests: contextvar isolation, load_config priority
- [x] New integration tests: BYOK middleware, 401 path, rate limiting
- [ ] Manual: deploy from this branch to korean-stat-mcp.fly.dev (no DNS yet); verify_statistics E2E with a real key
- [ ] Manual: 401 path live
- [ ] Manual: concurrent two-key smoke

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

---

## Task 12: Manual pre-merge deploy to `*.fly.dev` (no DNS yet)

**Files:**
- N/A (manual ops)

This step happens **before** merging the PR, against the `feat/hosting` branch directly. Catches infra issues (Fly secret wiring, region availability) without exposing them on `main`.

**Prerequisites:** Setup §15.1 (flyctl installed, `fly apps create`, payment method) and §15.2 (`FLY_API_TOKEN` GH secret) from the spec must be done.

- [ ] **Step 12.1: Verify Fly app exists**

```bash
fly apps list | grep korean-stat-mcp
```

Expected: app appears. If not: `fly apps create korean-stat-mcp` first.

- [ ] **Step 12.2: Set Fly secrets (none required for hosted; KOSIS_API_KEY is BYOK)**

Hosted mode does not need `KOSIS_API_KEY` as a Fly secret because every request brings its own. Confirm there are no stale secrets:

```bash
fly secrets list -a korean-stat-mcp
```

Expected: empty list, or only `RATE_LIMIT_RPM` / build-time vars.

If a stale `KOSIS_API_KEY` is set (legacy), unset it so the 401 path works correctly:

```bash
fly secrets unset KOSIS_API_KEY -a korean-stat-mcp
```

- [ ] **Step 12.3: Deploy from the local branch**

```bash
git checkout feat/hosting
fly deploy --remote-only
```

Expected: deploy completes; `https://korean-stat-mcp.fly.dev/health` returns 200 within 60s.

- [ ] **Step 12.4: Manual E2E — 401 path**

```bash
curl -i -X POST https://korean-stat-mcp.fly.dev/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

Expected: HTTP 401, body `{"error":"missing_api_key",...}`.

- [ ] **Step 12.5: Manual E2E — happy path with a real key**

Set `KOSIS_KEY` locally to a real KOSIS OpenAPI key (do NOT commit):

```bash
export KOSIS_KEY=...
curl -fsS -X POST "https://korean-stat-mcp.fly.dev/mcp?apiKey=$KOSIS_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

Expected: HTTP 200, MCP `initialize` response with `serverInfo.name == "korean-stat-mcp"`.

- [ ] **Step 12.6: Manual E2E — concurrent two-key isolation**

Run two requests in parallel with different keys; assert each completes:

```bash
(curl -fsS -X POST "https://korean-stat-mcp.fly.dev/mcp?apiKey=$KOSIS_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' &)
(curl -fsS -X POST "https://korean-stat-mcp.fly.dev/mcp?apiKey=other-fake-key" \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"initialize","params":{}}' &)
wait
```

Expected: first returns 200, second proceeds (server forwards the fake key to KOSIS, which then rejects — but the server itself stays healthy and the two calls do not interfere). Inspect `fly logs -a korean-stat-mcp` to confirm both `request_id`s appear with their respective `apiKey_hash` values.

- [ ] **Step 12.7: Decide go / no-go**

If all manual checks pass, proceed to merge. If any fail, fix on `feat/hosting` and re-run §12.3–§12.6.

---

## Task 13: Merge to `main`, automation takes over

**Files:**
- N/A (GitHub merge)

- [ ] **Step 13.1: Confirm CI green on PR**

```bash
gh pr checks
```

Expected: `CI` workflow `pass`. (Deploy workflow has not run yet because it triggers on `main` only.)

- [ ] **Step 13.2: Merge**

```bash
gh pr merge --squash --delete-branch
```

Expected: merge succeeds; `feat/hosting` deleted on remote.

- [ ] **Step 13.3: Watch the deploy workflow**

```bash
gh run watch
```

Expected: `deploy` workflow runs, all 5 gates pass, post-deploy probe returns 200.

---

## Task 14: DNS + cert for `kosis.seolcoding.com`

**Files:**
- N/A (manual ops)

**Prerequisites:** Setup §15.3 (DNS zone access).

- [ ] **Step 14.1: Add the CNAME**

In the seolcoding.com DNS zone (Cloudflare / wherever):

```
kosis  CNAME  korean-stat-mcp.fly.dev.   TTL 300
```

If on Cloudflare: keep proxy **off** (gray cloud) until cert is `READY`.

- [ ] **Step 14.2: Provision the cert**

```bash
flyctl certs add kosis.seolcoding.com -a korean-stat-mcp
```

- [ ] **Step 14.3: Wait for cert ready**

Poll until status is `READY`:

```bash
until flyctl certs show kosis.seolcoding.com -a korean-stat-mcp | grep -q "READY"; do
  sleep 10
done
echo "cert ready"
```

Expected: usually 1–5 minutes.

- [ ] **Step 14.4: Verify the URL works end-to-end**

```bash
curl -fsS https://kosis.seolcoding.com/health
curl -i -X POST https://kosis.seolcoding.com/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

Expected: `/health` returns 200; `/mcp` (no key) returns 401 with `missing_api_key`.

- [ ] **Step 14.5: (Cloudflare only) Re-enable proxy**

If on Cloudflare and you want DDoS protection: turn the orange cloud back on for the `kosis` record. Re-verify §14.4.

---

## Task 15: Update post-deploy probe to use the custom domain

**Files:**
- Modify: `.github/workflows/deploy.yml`

Once the custom domain is live, switch the deploy workflow's post-deploy probe so it asserts against the user-facing URL.

- [ ] **Step 15.1: Edit deploy.yml**

In `.github/workflows/deploy.yml`, replace `korean-stat-mcp.fly.dev` in the post-deploy probe step with `kosis.seolcoding.com`.

- [ ] **Step 15.2: Commit on a small follow-up PR**

```bash
git switch -c chore/probe-custom-domain
git add .github/workflows/deploy.yml
git commit -m "ci: probe custom domain in post-deploy gate"
git push -u origin chore/probe-custom-domain
gh pr create --title "ci: probe kosis.seolcoding.com in deploy gate" --body "Custom domain is live; switch the post-deploy probe to the user-facing URL." --fill
```

Merge after CI green.

---

## Task 16: 24-hour soak

**Files:**
- N/A (monitoring)

- [ ] **Step 16.1: Establish baseline**

Right after the merge, capture:

```bash
fly metrics -a korean-stat-mcp
```

Note: VM count, memory RSS, request rate.

- [ ] **Step 16.2: Set a one-day reminder**

Use whatever scheduling lives outside this plan. After 24 h:

- [ ] No VM crashes (`fly status`, `fly logs --since 24h | grep -i 'crash\|panic\|killed'` returns empty)
- [ ] p99 request latency < 2s (Fly metrics dashboard)
- [ ] Egress < 500 MB/day (Fly billing)
- [ ] No `429` storms (more than 10/hour suggests an attack or buggy client)

If all clean → mark Stream A done, move to Stream B (user guide). If issues → triage on `feat/hosting-fix-*` branch.

---

## Self-review

Re-read the spec sections against this plan:

- §3 URL contract → covered by Tasks 3, 4 (middleware + 401 path), 14 (DNS).
- §4 Per-request key flow → Tasks 1 (contextvar), 2 (load_config), 3 (middleware).
- §5 Fly.io infra → Task 7.
- §6 Dockerfile → Task 6.
- §7 DNS → Task 14.
- §8 CI/CD → Task 8 (initial), Task 15 (probe URL switch).
- §9 Rate limiting → Task 5.
- §10 Observability → Existing stdlib logging + Fly built-in metrics; no new task needed for v1 (matches spec §10 "v1 skip Sentry").
- §11 Backward compat → Task 2 (env fallback) + Task 10 (migration note).
- §12 Test plan → Tasks 1–5 (unit + integration), Task 12 (manual E2E).
- §13 Open questions → KOSIS ToS check is a one-time external review (not a code task); Claude.ai query-string preservation is verified by Task 12.5 manual E2E.
- §14 Out of scope → Streams B/C/D are not in this plan.
- §15 Setup prerequisites → Tasks 12 and 14 explicitly reference them.
- §16 Rollout order → Tasks 0–16 follow this order.

No placeholders found. Type names consistent (`current_api_key`, `ApiKeyMiddleware`, `build_rate_limiter`). Function `_key_func` only referenced inside `middleware.py`.
