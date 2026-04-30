# Stream A — Public Hosting Design

- **Status**: Draft, pending review
- **Date**: 2026-04-30
- **Owner**: seolcoding
- **Reference project**: [chrisryugj/korean-law-mcp](https://github.com/chrisryugj/korean-law-mcp) (mirroring the hosting + connector UX pattern)

## 1. Goal

Stand up a public, hosted instance of `korean-stat-mcp` at
`https://kosis.seolcoding.com/mcp` so that Claude.ai / Claude Code / Claude
Desktop / Cursor / Windsurf users can connect with **a single URL** plus their
own KOSIS OpenAPI key — no `pip install`, no JSON config edits.

Success criteria for v1:

- Claude.ai custom connector pointed at `https://kosis.seolcoding.com/mcp?apiKey=<key>` can call `search_statistics`, `get_statistics_data`, `verify_statistics` end-to-end.
- Self-hosted users (existing PyPI consumers) keep working with `KOSIS_API_KEY` env var, unchanged.
- 99%+ availability over a 7-day soak; cold-start ≤ 3 s; p50 KOSIS roundtrip from NRT region ≤ 600 ms.
- Monthly egress under Fly free tier headroom for the first 1k DAU range.

## 2. Non-goals

- Shared/server-side KOSIS key (rejected — KOSIS terms risk + quota exhaustion).
- Plugin marketplace (Claude Code) registration — separate stream after the
  user guide is finalized.
- demo.gif, launch posts, video assets — Stream C (marketing repo).
- New MCP tools, expanded edge-case coverage — Stream D (reliability).
- Multi-region replication, blue/green deploys, paid uptime SLOs.

## 3. URL contract

Public connector URL:

```
https://kosis.seolcoding.com/mcp?apiKey=<KOSIS_API_KEY>
```

Auxiliary endpoints (already present in `mcp_server/app.py`):

- `GET https://kosis.seolcoding.com/health` → 200 with build info
- `GET https://kosis.seolcoding.com/info`   → 200 with tool surface metadata

Self-hosted entrypoint (unchanged):

```
KOSIS_API_KEY=... korean-stat-mcp --http
# → http://localhost:8000/mcp
```

Parameter naming choice: `apiKey` matches the native KOSIS OpenAPI field name.
The reference project uses `?oc=` for the same reason — it's the law portal's
native field. Consistency with the upstream API trumps short-URL aesthetics.

Error semantics when the key is missing **and** there is no env fallback:

```
HTTP 401
{
  "error": "missing_api_key",
  "message": "Provide ?apiKey=<your KOSIS OpenAPI key> in the connector URL.",
  "issue_url": "https://kosis.kr/openapi/"
}
```

## 4. Per-request key flow (code change scope)

Today's flow:

```
process start
 └─ KosisConfig.load_config()
     └─ os.getenv("KOSIS_API_KEY")
         └─ singleton config injected into every kosis_tools.* client
```

Required flow for hosted multi-tenant mode:

```
HTTP request (per call)
 └─ Starlette middleware reads ?apiKey=
     └─ contextvar `current_api_key.set(...)`
         └─ tool handler runs → KosisConfig.load_config()
             └─ contextvar wins; falls back to env if unset (self-host)
         └─ middleware token reset on response
```

Files touched:

| File | Change |
|---|---|
| `src/kosis_tools/request_context.py` (new) | Defines `current_api_key: ContextVar[str \| None]`. Located in `kosis_tools` (not `mcp_server`) so `config.load_config()` can read it without inverting the package layering. |
| `src/mcp_server/app.py` | Adds `ApiKeyMiddleware` to the Starlette app — extracts query param, sets contextvar, resets on finally |
| `src/kosis_tools/config.py` | `load_config()` checks contextvar first, then `KOSIS_API_KEY` env, then raises with the same 401-style message |
| `tests/mcp_server/test_request_context.py` (new) | Unit + asyncio concurrency test: two concurrent requests with different keys never see each other's key |

The contextvar approach is preferred over passing `request` through the entire
tool tree because:

- FastMCP tool handlers are decorated functions; rewriting them all to take a
  request object is a bigger blast radius than the goal warrants.
- `ContextVar` propagates correctly through `asyncio` tasks and `aiohttp`
  client calls, which is what the KOSIS clients use.
- stdio mode keeps working without any conditional — the contextvar is just
  empty there, env wins.

## 5. Fly.io infrastructure

Mirrors the reference project's `fly.toml` with Python-specific tweaks.

```toml
app = 'korean-stat-mcp'
primary_region = 'nrt'

[build]
  dockerfile = 'Dockerfile'

[env]
  KOSIS_HOST = '0.0.0.0'
  KOSIS_PORT = '8000'
  RATE_LIMIT_RPM = '300'
  PYTHONUNBUFFERED = '1'

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = 'suspend'
  auto_start_machines = true
  min_machines_running = 0

[[vm]]
  memory = '256mb'
  cpu_kind = 'shared'
  cpus = 1
```

Region `nrt` (Tokyo) keeps RTT to Korean users in the 30–50 ms range.
`auto_stop_machines = 'suspend'` is preferred over `stop` so warm starts are
sub-second; falls back to a cold start only after extended idleness.

## 6. Dockerfile (Python, 2-stage, non-root)

```dockerfile
# --- Build stage ---
FROM python:3.13-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir --upgrade pip uv
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv pip install --system --no-cache .

# --- Runtime stage ---
FROM python:3.13-slim
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin/korean-stat-mcp /usr/local/bin/
USER app
EXPOSE 8000
ENV PYTHONUNBUFFERED=1 KOSIS_HOST=0.0.0.0 KOSIS_PORT=8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"
CMD ["korean-stat-mcp", "--http"]
```

The existing repo `Dockerfile` becomes the source of truth. Replace its current
contents with the above; no separate `Dockerfile.fly`.

## 7. DNS — `kosis.seolcoding.com`

Steps, in order:

1. `flyctl apps create korean-stat-mcp` (if not yet created)
2. `flyctl deploy` once with the default `korean-stat-mcp.fly.dev` hostname to
   validate end-to-end before DNS work.
3. In the seolcoding.com DNS zone, add:
   ```
   kosis  CNAME  korean-stat-mcp.fly.dev.
   ```
4. `flyctl certs add kosis.seolcoding.com` — provisions Let's Encrypt cert.
5. Wait for `flyctl certs show kosis.seolcoding.com` to report `READY`.
6. Verification:
   ```
   curl -fsS https://kosis.seolcoding.com/health
   curl -fsS "https://kosis.seolcoding.com/mcp?apiKey=<test_key>" -X POST \
        -H 'Content-Type: application/json' \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
   ```

## 8. CI/CD

`.github/workflows/deploy.yml` — gated on the existing `ci.yml` workflow
completing successfully on `main`:

```yaml
name: deploy
on:
  workflow_run:
    workflows: ["ci"]      # name of the existing CI workflow
    branches: [main]
    types: [completed]
  workflow_dispatch:
jobs:
  deploy:
    if: ${{ github.event_name == 'workflow_dispatch' || github.event.workflow_run.conclusion == 'success' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Pre-deploy gate 1: full test suite (defense-in-depth even though
      # workflow_run already required ci.yml green — protects against ci.yml
      # being skipped or partially run)
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --all-extras --dev
      - run: uv run pytest -q

      # Pre-deploy gate 2: build the production Docker image and smoke-test
      # the HTTP server inside the container against the exact artifact that
      # will ship to Fly.
      - run: docker build -t korean-stat-mcp:ci .
      - name: Container smoke test
        run: |
          docker run -d --rm --name kstat-smoke -p 8000:8000 \
            -e KOSIS_API_KEY=ci-fake-key korean-stat-mcp:ci
          for i in {1..20}; do
            curl -fsS http://localhost:8000/health && break || sleep 1
          done
          curl -fsS http://localhost:8000/info | grep -q "korean-stat-mcp"
          curl -fsS -X POST "http://localhost:8000/mcp?apiKey=fake" \
               -H 'Content-Type: application/json' \
               -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
          docker stop kstat-smoke

      # Pre-deploy gate 3: actual deploy
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}

      # Post-deploy gate: confirm the freshly deployed instance actually
      # serves /health and /info before the workflow reports success.
      - name: Post-deploy health probe
        run: |
          for i in {1..30}; do
            curl -fsS https://kosis.seolcoding.com/health && exit 0
            sleep 2
          done
          echo "post-deploy health probe failed"; exit 1
```

Tag pushes (`v*`) continue to drive the existing PyPI release pipeline; they
do not deploy to Fly. Only `main` HEAD goes to the hosted instance.

## 9. Rate limiting & abuse guards

- Per-IP: 60 req/min, 600 req/hour
- Per-`apiKey`: same thresholds (a single user can't drown others by sharing a
  key across many IPs)
- Implementation: `slowapi` (Starlette-compatible) with an in-memory store —
  good enough for a single-VM deployment; revisit if multi-region.
- Single response cap: 5 MB. Larger payloads route through the existing
  `read_stored_data` chunked path.
- 429 response includes `Retry-After`.

## 10. Observability

- stderr structured logs (JSON one-line per record): `request_id`, `method`,
  `tool_name`, `apiKey_hash` (first 8 chars of SHA-256, never the raw key),
  `latency_ms`, `status`.
- Fly built-in metrics: CPU, memory, request rate, egress bytes.
- Alerts (Fly built-in): VM crash, daily egress > 5 GB.
- No Sentry / external APM in v1.

## 11. Backward compatibility

- Existing self-hosters using `KOSIS_API_KEY` env keep working unchanged.
- Existing PyPI install path (`pip install korean-stat-mcp`) untouched.
- README adds a new **"Hosted instance (no install)"** section *above* the
  existing install methods, mirroring the law-mcp ordering: Claude.ai web
  connector first, then Claude Code plugin (later), then desktop apps.

## 12. Test plan

### 12.1 Existing test refactor scope

The contextvar change touches `kosis_tools/config.py::load_config()`. Survey
of existing tests (449 total):

- **Most tests construct `KosisConfig(api_key="test-key")` directly** via the
  `tests/conftest.py::test_config` fixture and never call `load_config()`.
  These need **no change** — the fixture path is independent of the new
  contextvar logic.
- **`tests/unit/test_base.py::TestKosisConfig`** exercises `load_config()`'s
  env-var path. Refactor to add coverage for:
  - contextvar set → `load_config()` returns contextvar's key (env ignored)
  - contextvar unset + env set → env path (current behavior preserved)
  - contextvar unset + env unset → raises with the documented error
  - contextvar reset on a different asyncio task does not bleed into a
    sibling task
- **No test currently asserts MCP HTTP request handling end-to-end** — that
  is a gap the new integration test will close, not an existing-test rewrite.

The bar: 449 → 449+N tests pass; zero existing tests modified beyond the
`test_base.py::TestKosisConfig` class above. New tests live in new files
(`tests/unit/test_request_context.py`, `tests/integration/test_byok_http.py`)
to keep diffs reviewable.

### 12.2 New tests

| File | Layer | Coverage |
|---|---|---|
| `tests/unit/test_request_context.py` | Unit | `current_api_key` set/get/reset; isolation across asyncio tasks (`asyncio.gather` of two coroutines, each setting their own value, assert no bleed) |
| `tests/unit/test_load_config_priority.py` | Unit | `load_config()` priority order: contextvar > env > raise. One test per branch. |
| `tests/integration/test_byok_http.py` | Integration | Spin Starlette app via httpx test client. Issue concurrent POSTs to `/mcp?apiKey=foo` and `/mcp?apiKey=bar` with `aiohttp` outbound mocked; assert each KOSIS call carried the matching key. Cover 401 path (no key, no env). |
| `tests/integration/test_health_info.py` (extend if exists) | Integration | `/health` and `/info` keep working with and without `apiKey` query param. |

### 12.3 Pre-deploy gates (CI)

Encoded in `.github/workflows/deploy.yml` (Section 8). In order:

1. **Full pytest suite** runs again in the deploy workflow even though
   `workflow_run` already required `ci.yml` to be green. Defense-in-depth
   against `workflow_run` edge cases (skipped, re-run, etc.).
2. **Docker build** of the production image — same Dockerfile that ships.
3. **Container smoke test**: start the container, hit `/health`, `/info`, and
   `/mcp?apiKey=fake` `initialize` against the live container. Catches
   packaging regressions (missing files, wrong entrypoint, port binding
   issues) that pytest cannot.
4. **Fly deploy** runs only if 1–3 all pass.
5. **Post-deploy health probe**: poll `https://kosis.seolcoding.com/health`
   for up to 60 s; fail the workflow if it never returns 200.

### 12.4 Manual verification (one-time, on first deploy)

- `verify_statistics` against a known KOSIS row using a real key end-to-end
  through `https://kosis.seolcoding.com/mcp?apiKey=<real_key>`.
- 401 path: same URL without `?apiKey=`, expect `error: missing_api_key`.
- Concurrent two-key smoke: run two `verify_statistics` calls with different
  real keys interleaved, confirm each completes without cross-talk in
  Fly logs.

### 12.5 Soak

24 h passive monitoring of Fly metrics post-deploy: VM crashes, p50/p99
latency, egress, 5xx rate. Promote to "Stream A done" only after a clean
soak window.

## 13. Open questions (resolve during plan/implementation)

1. **KOSIS OpenAPI ToS** — verify that "user supplies own key, our server
   forwards their request to KOSIS using their key" is allowed. Expected
   answer: yes (analogous to any client library). If "no": fall back to
   self-host-only, no public hosting.
2. **Claude.ai connector query-string preservation** — confirm by adding the
   draft URL to a Claude.ai connector during implementation. Reference project
   already proves the mechanism works for `?oc=`; expect identical behavior.
3. **slowapi vs hand-rolled middleware** — final pick during implementation;
   no behavioral difference visible to the user.
4. **Fly app name conflict** — `korean-stat-mcp` is the intended slug; pick a
   `-prod` suffix if taken.

## 14. Out of scope (handled in other streams)

- Stream B: user guide, cookbook, troubleshooting (will reference this URL).
- Stream C: demo.gif, launch posts, comparison content, distribution.
- Stream D: edge-case coverage, error message polish, tool-routing accuracy.

## 15. Setup prerequisites (one-time)

These are **not** code changes — they are external account / credential /
DNS setup steps that must complete before the implementation plan can run.
Tracking them in the spec so they are not forgotten when the plan executes.

### 15.1 Local developer machine (one-time)

| Step | Command / action | Verification |
|---|---|---|
| Install flyctl | `brew install flyctl` (macOS) or `curl -L https://fly.io/install.sh \| sh` | `fly version` |
| Sign up / log in | `fly auth login` (opens browser) — uses an existing Fly account or creates one | `fly auth whoami` |
| Payment method on file | Add a card in the Fly dashboard. Free tier still works without paid resource use, but Fly requires a card for anti-abuse. | Fly dashboard → Billing |
| Create the app | `fly apps create korean-stat-mcp` — if name is taken, fall back to `korean-stat-mcp-prod` (also update `app =` in `fly.toml`) | `fly apps list` shows it |
| Verify region | Tokyo (`nrt`) is enabled by default for new apps. | `fly platform regions` |

### 15.2 GitHub repository (one-time)

| Step | Command / action | Verification |
|---|---|---|
| Mint deploy token | `fly tokens create deploy --name "korean-stat-mcp gh actions"` and copy the value | `fly tokens list` |
| Add repo secret | GitHub → Settings → Secrets and variables → Actions → New repository secret named `FLY_API_TOKEN`, paste the token | Secret appears in the list (value is hidden) |
| Confirm Actions allowed | Repo Settings → Actions → General → "Allow all actions and reusable workflows" (or the equivalent allow-list including `superfly/flyctl-actions/setup-flyctl@master`) | Workflow runs are not blocked |

### 15.3 DNS — `seolcoding.com` zone (one-time)

| Step | Action | Verification |
|---|---|---|
| Access the DNS zone | Log into the registrar / DNS provider managing `seolcoding.com` (Cloudflare, Route 53, Gabia, etc.) | Can edit records |
| Reserve the subdomain | Confirm `kosis.seolcoding.com` is not already in use for something else | `dig kosis.seolcoding.com` returns NXDOMAIN |
| Cloudflare orange-cloud decision | If on Cloudflare: keep the proxy *off* (gray cloud) for the initial Let's Encrypt cert issuance. Re-enable the proxy only after Fly cert is `READY`. | `flyctl certs show kosis.seolcoding.com` reaches `READY` |

### 15.4 KOSIS OpenAPI key (test/QA use)

| Step | Action |
|---|---|
| Issue a personal KOSIS key | Apply at <https://kosis.kr/openapi/> — used only for the manual E2E in §12.4. |
| Store it locally | `echo 'KOSIS_API_KEY=...' >> ~/.config/korean-stat-mcp.env` (or whatever per-developer secret store you already use). **Never** commit it. |

### 15.5 Stop conditions

If any of these fails, the implementation plan stops at the corresponding
step and surfaces the issue rather than working around it:

- Fly account creation fails or requires manual review → escalate, do not
  proceed.
- KOSIS OpenAPI ToS review (open question §13.1) returns "no proxying with
  user-supplied keys" → fall back to self-host-only, abandon §7 / DNS
  setup, document the decision, and close Stream A as "won't ship hosted".
- DNS zone access is unavailable on the day of cutover → ship to
  `korean-stat-mcp.fly.dev` first, defer §7 until DNS is reachable.

## 16. Rollout order

1. **Code + tests on `feat/hosting`**:
   - `request_context.py` + middleware + `load_config()` patch.
   - New tests per Section 12.2.
   - Refactor `test_base.py::TestKosisConfig` per Section 12.1.
   - Local `pytest` green; existing 449 tests still pass.
2. **Container parity**:
   - Update `Dockerfile` + `fly.toml`.
   - Local `docker build` + `docker run` smoke test (same script the CI
     gate runs in Section 12.3).
3. **CI gates wired**:
   - `.github/workflows/deploy.yml` added with all five gates from
     Section 12.3.
   - Trigger via `workflow_dispatch` once on the branch with a dry-run
     value (no `FLY_API_TOKEN`) to confirm gates 1–3 work; deploy step
     skipped.
4. **Open PR for review**.
5. **Pre-merge manual deploy** to `korean-stat-mcp.fly.dev` (no custom
   domain yet) using `flyctl deploy` from the branch — catches
   infrastructure issues (Fly app naming, region, secret wiring) without
   touching `main`.
6. **Manual E2E** per Section 12.4 against `*.fly.dev`.
7. **Merge `feat/hosting` → `main`** — automated deploy via the new
   workflow takes over from this point.
8. **DNS + cert** for `kosis.seolcoding.com` (Section 7) once the `fly.dev`
   instance is stable.
9. **README hosted-instance section** + `MIGRATION.md` note for
   self-hosters — committed on a small docs PR after the URL is live so
   public docs never reference an unreachable endpoint.
10. **24 h soak**, capture egress baseline, then promote Stream A to done.
