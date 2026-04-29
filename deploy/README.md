# Deployment Guide / 배포 가이드

> Self-hosting `korean-stat-mcp` as a public HTTP MCP endpoint (Streamable HTTP, port 8000).
> 외부 접근 가능한 HTTP MCP 엔드포인트로 자체 호스팅하는 방법.

The repository ships a production [`Dockerfile`](../Dockerfile) that runs the
FastAPI HTTP server (`mcp_server.app:app`) on port 8000 with a `/health`
endpoint. The same image works on Fly.io, Render, Railway, DigitalOcean
App Platform, or any plain VPS with Docker.

레포에 포함된 [`Dockerfile`](../Dockerfile) 은 8000 포트에서 FastAPI HTTP
서버(`mcp_server.app:app`)를 구동하며 `/health` 엔드포인트를 제공합니다. 동일
이미지를 Fly.io / Render / Railway / DigitalOcean App Platform / 일반 VPS 어디서나
사용할 수 있습니다.

---

## Required environment variables / 필수 환경변수

| Variable | Required | Notes |
|----------|----------|-------|
| `KOSIS_API_KEY` | yes | Free at https://kosis.kr/openapi/ |
| `R2_*` (R2 bucket / keys / public URL) | optional | Only if you want chart/report hosting on Cloudflare R2 |
| `KOSIS_ARTIFACTS_DIR` | optional | Local artifact path (default `/tmp/kosis_artifacts`) |
| `FASTMCP_STATELESS_HTTP` | optional | `true` for serverless / scale-to-zero hosts |

---

## Option 1 — Fly.io (recommended for low traffic / cost control)

This repo includes a ready [`fly.toml`](../fly.toml) configured for Tokyo
(`nrt`), scale-to-zero (`min_machines_running = 0`), and a `/health` HTTP check.

```bash
# 1. Install flyctl + login
brew install flyctl   # or: curl -L https://fly.io/install.sh | sh
fly auth login

# 2. Pick an app name (the default in fly.toml is a placeholder)
#    Either edit fly.toml's `app = "..."` field manually, or run:
fly launch --no-deploy --copy-config --name <your-app-name>

# 3. Inject secrets (these are encrypted at rest, never written to fly.toml)
fly secrets set KOSIS_API_KEY="<your-kosis-api-key>"

# 4. Deploy
fly deploy

# 5. Verify
curl https://<your-app-name>.fly.dev/health
```

Your MCP endpoint will be:

```
https://<your-app-name>.fly.dev/mcp
```

Use this URL in Claude.ai → Settings → Connectors → Add custom connector.

### Cost notes
- `min_machines_running = 0` + `auto_stop_machines = "stop"` puts the machine
  to sleep when idle. First request after sleep adds ~5-10s cold start.
- `shared-cpu-1x` / `512mb` is the cheapest tier; bump `[[vm]].memory` if you
  see OOM kills loading large catalog data.

---

## Option 2 — Render

1. New → Web Service → connect your GitHub fork.
2. Runtime: **Docker**, plan: Starter (free tier OK for hobby use).
3. Add environment variable `KOSIS_API_KEY`.
4. Health check path: `/health`.
5. Deploy. URL → `https://<service>.onrender.com/mcp`.

Render auto-detects the repo `Dockerfile`. No additional config needed.

---

## Option 3 — Railway

1. New Project → Deploy from GitHub repo.
2. Railway detects `Dockerfile` automatically.
3. Variables tab → add `KOSIS_API_KEY`.
4. Settings → Networking → Generate Public Domain.
5. Endpoint → `https://<project>.up.railway.app/mcp`.

---

## Option 4 — DigitalOcean App Platform

1. Create App → GitHub source → select repo / branch `main`.
2. Resource type: **Web Service**, source: **Dockerfile**.
3. HTTP Port: **8000**.
4. Add app-level env var `KOSIS_API_KEY` (mark as encrypted).
5. Health check: HTTP path `/health`.
6. Endpoint → `https://<app>.ondigitalocean.app/mcp`.

---

## Option 5 — Self-host on a VPS (Docker / docker-compose)

The simplest path uses the repo's `docker-compose.yml`:

```bash
git clone https://github.com/<github-user>/korean-stat-mcp.git
cd korean-stat-mcp
cp .env.example .env
# edit .env: set KOSIS_API_KEY=...
docker compose up -d
curl http://localhost:8000/health
```

Put the container behind your existing reverse proxy (Caddy / nginx / Traefik)
to terminate TLS. Example Caddyfile snippet:

```
mcp.example.com {
  reverse_proxy localhost:8000
}
```

---

## Verification / 검증

```bash
# Health check
curl https://<your-host>/health
# Expected: {"status":"ok",...}

# MCP endpoint exists
curl -i https://<your-host>/mcp
# Expected: 200/405/406 (depends on transport handshake), NOT 404
```

If you can hit `/health` but `/mcp` 404s, your reverse proxy is stripping the
path — fix the upstream config so the full request URI reaches the container.
