# korean-stat-mcp

A Python MCP server for working with Korean Statistical Information Service
(KOSIS) OpenAPI data.

It lets MCP clients such as Claude Desktop, Claude Code, Cursor, and Windsurf
search KOSIS tables, inspect metadata, fetch source rows, and run simple
analysis helpers.

[한국어 README](./README.md)

[![PyPI](https://img.shields.io/pypi/v/korean-stat-mcp.svg)](https://pypi.org/project/korean-stat-mcp/)
[![CI](https://img.shields.io/github/actions/workflow/status/seolcoding/korean-stat-mcp/ci.yml?branch=main)](https://github.com/seolcoding/korean-stat-mcp/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-blue)](https://modelcontextprotocol.io/)

## What it does

- Search KOSIS tables by keyword.
- Browse tables by organization or topic.
- Read table metadata, classifications, items, and periods.
- Fetch source data from the KOSIS OpenAPI.
- Filter and aggregate fetched data.
- Read stored data chunks and verify source values.
- Use `verify_statistics` to compare a claimed value with the source row.

KOSIS tables often require slightly different parameter combinations. Some
tables behave differently across monthly, quarterly, yearly, and local-government
datasets. This server wraps those details behind MCP tools so the client setup
stays small.

## Hosted instance (no install)

No `pip install` required — just paste one URL into a Claude.ai custom
connector. A Claude Pro/Max/Team/Enterprise plan is required (Free allows
only one connector).

### Step 0: Get a KOSIS OpenAPI key (free, 1 minute)

Sign up at the [KOSIS OpenAPI page](https://kosis.kr/openapi/), click
"Open API 사용 신청", and you'll receive an authentication key.

### Add the connector

1. Sign in at [claude.ai](https://claude.ai).
2. Bottom-left sidebar → **your name** → **Settings** → **Connectors**.
3. Click **Add custom connector**.
4. Fill in (replace `<YOUR_KEY>` with the key from Step 0):
   - **Name**: `korean-stat`
   - **URL**: `https://korean-stat-mcp.seolcoding.com/mcp?apiKey=<YOUR_KEY>`
5. Click **Add**.
6. Open **Configure** on the new connector and set every tool to **Always allow**.

### Use it

Ask in natural language and the `korean-stat` tools fire automatically:

```
"Show Korea's population trend from 2020 to 2023"
"Compare the number of businesses across Seoul districts"
```

### Self-hosting still works

The existing `pip install` + `KOSIS_API_KEY` env var path is unchanged — see
the [Installation](#installation) section below.

---

## Installation

You need a KOSIS OpenAPI key. You can request one from the
[KOSIS OpenAPI page](https://kosis.kr/openapi/).

### Claude Desktop / Cursor / Windsurf

```bash
pip install korean-stat-mcp
```

Add this to your MCP client config:

```json
{
  "mcpServers": {
    "korean-stat": {
      "command": "korean-stat-mcp",
      "env": {
        "KOSIS_API_KEY": "<KOSIS_API_KEY>"
      }
    }
  }
}
```

On macOS, Claude Desktop uses:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

### MCP client config

```json
{
  "mcpServers": {
    "korean-stat": {
      "command": "korean-stat-mcp",
      "env": {
        "KOSIS_API_KEY": "<KOSIS_API_KEY>"
      }
    }
  }
}
```

### Run directly

```bash
pip install korean-stat-mcp
export KOSIS_API_KEY="<KOSIS_API_KEY>"
korean-stat-mcp          # stdio MCP for local Claude Desktop/Cursor
korean-stat-mcp --http   # Streamable HTTP server at http://localhost:8000/mcp
```

Check the install:

```bash
korean-stat-mcp --version
```

## Remote MCP hosting

Official hosted endpoint:

```text
https://korean-stat-mcp.seolcoding.com/mcp?apiKey=<YOUR_KOSIS_KEY>
```

Paste this URL straight into a Claude.ai custom connector or use it as the
Streamable HTTP endpoint from any MCP client. See the
[Hosted instance (no install)](#hosted-instance-no-install) section above for
the step-by-step Claude.ai setup.

Health and info:

```bash
curl https://korean-stat-mcp.seolcoding.com/health
curl https://korean-stat-mcp.seolcoding.com/info
```

### Self-hosting is still supported

Self-host if you want to keep your KOSIS key quota separate from the public
instance, or if you need to run inside a corporate / on-prem network. The
[deploy/README.md](./deploy/README.md) covers Docker, Fly.io, Render, Railway,
DigitalOcean App Platform, and plain VPS deployments.

```bash
# Self-hosted
KOSIS_API_KEY=<YOUR_KEY> korean-stat-mcp --http
curl https://<your-host>/health
```

## Main tools

| Area | Tools | Purpose |
|---|---|---|
| Search | `search_statistics` | Find tables by keyword |
| Browse | `browse_categories` | Browse by organization or topic |
| Metadata | `get_table_metadata`, `get_available_values` | Inspect classifications, items, and periods |
| Data | `get_statistics_data` | Fetch source rows |
| Transform | `filter_statistics`, `aggregate_statistics` | Filter and group results |
| Stored data | `read_stored_data`, `list_stored_data` | Read large results in chunks |
| Verification | `verify_statistics` | Compare a value with source data |

See [docs/TOOL_MIGRATION.md](./docs/TOOL_MIGRATION.md) for the full tool list
and migration notes.

## Environment variables

| Variable | Required | Description |
|---|---:|---|
| `KOSIS_API_KEY` | yes | KOSIS OpenAPI key |
| `KOSIS_ARTIFACTS_DIR` | no | Local chart/report output directory |
| `KOSIS_MCP_URL` | no | Base URL for a self-hosted server |

See [.env.example](./.env.example) for the full list.

## Validation

- CI runs on Python 3.12 and 3.13.
- As of 2026-04-30, the unit test suite has 449 passing tests.
- A 100-table live KOSIS pilot had no API errors, timeouts, or parse errors.
  Two empty responses were classified as `no_data`.

See [docs/VALIDATION_REPORT.md](./docs/VALIDATION_REPORT.md) for details.

## Documentation

- [docs/USER_GUIDE.md](./docs/USER_GUIDE.md): user guide
- [docs/KOSIS_API_REFERENCE.md](./docs/KOSIS_API_REFERENCE.md): KOSIS API notes
- [docs/TOOL_MIGRATION.md](./docs/TOOL_MIGRATION.md): tool mapping and migration notes
- [deploy/README.md](./deploy/README.md): deployment guide
- [MIGRATION.md](./MIGRATION.md): notes for previous `kosis-mcp` users
- [CONTRIBUTING-EN.md](./CONTRIBUTING-EN.md): development and PR workflow

## License

The code is MIT licensed. KOSIS data is subject to the KOSIS terms and policies.
