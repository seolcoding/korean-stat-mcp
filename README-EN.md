# korean-stat-mcp

A Python MCP server for working with Korean Statistical Information Service
(KOSIS) OpenAPI data.

It lets MCP clients such as Claude Desktop, Claude Code, Cursor, and Windsurf
search KOSIS tables, inspect metadata, fetch source rows, and create simple
charts or reports.

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
- Create Altair charts and HTML reports.
- Use `verify_statistics` to compare a claimed value with the source row.

KOSIS tables often require slightly different parameter combinations. Some
tables behave differently across monthly, quarterly, yearly, and local-government
datasets. This server wraps those details behind MCP tools so the client setup
stays small.

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

### Run with uvx

```json
{
  "mcpServers": {
    "korean-stat": {
      "command": "uvx",
      "args": ["korean-stat-mcp"],
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
korean-stat-mcp
```

Check the install:

```bash
korean-stat-mcp --version
```

## Remote MCP hosting

There is no official hosted endpoint yet. To use Claude.ai custom connectors,
deploy the server yourself and register:

```text
https://<your-host>/mcp
```

Deployment notes are in [deploy/README.md](./deploy/README.md). The repo includes
a Dockerfile and examples for Fly.io, Render, Railway, DigitalOcean App Platform,
and a plain VPS.

Health check:

```bash
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
| Output | `execute_visualization`, `execute_table`, `execute_report` | Generate charts, tables, and reports |

See [docs/TOOL_MIGRATION.md](./docs/TOOL_MIGRATION.md) for the full tool list
and migration notes.

## Environment variables

| Variable | Required | Description |
|---|---:|---|
| `KOSIS_API_KEY` | yes | KOSIS OpenAPI key |
| `KOSIS_ARTIFACTS_DIR` | no | Local chart/report output directory |
| `KOSIS_MCP_URL` | no | Base URL for a self-hosted server |
| `R2_BUCKET_NAME` | no | Cloudflare R2 bucket |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | no | Cloudflare R2 credentials |
| `R2_PUBLIC_URL` | no | Public URL prefix for R2 artifacts |

See [.env.example](./.env.example) for the full list.

## Validation

- CI runs on Python 3.12 and 3.13.
- As of 2026-04-30, the unit test suite has 446 passing tests.
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
