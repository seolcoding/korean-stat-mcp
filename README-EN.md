# korean-stat-mcp

> Korean Statistics (KOSIS) MCP server — 100% public API coverage with allow-list curated tools and citation verification.

[한국어 README](./README.md)

[![PyPI](https://img.shields.io/pypi/v/korean-stat-mcp.svg)](https://pypi.org/project/korean-stat-mcp/)
[![CI](https://img.shields.io/github/actions/workflow/status/<github-user>/korean-stat-mcp/ci.yml?branch=main)](https://github.com/<github-user>/korean-stat-mcp/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![MCP](https://img.shields.io/badge/MCP-compatible-blue)](https://modelcontextprotocol.io/)

## Why this tool

- **Proven reliability**: 99.38% success rate against the live KOSIS Open API, verified across a 10,000-table sample.
- **Curated tool surface**: ~16 carefully designed tools instead of exposing all 24 raw endpoints — the LLM picks the right tool faster, with fewer hallucinated parameters.
- **Citation verification**: A dedicated `verify_statistics` tool re-fetches source rows so the model can cite KOSIS values it actually retrieved, not numbers it invented.
- **Standard LLM tool for Korean statistics**: Designed to be the default way LLM agents read public Korean statistical data — population, economy, labor, housing, education, and more.

## 🚀 Quick Start — 4 install channels

### 1. Claude Code plugin marketplace

```bash
/plugin marketplace add <github-user>/korean-stat-mcp
```

### 2. Claude.ai custom connector (remote MCP)

In Claude.ai → Settings → Connectors → Add custom connector, use the remote URL:

```
https://korean-stat-mcp.example.com/mcp
```

(Public hosted endpoint — TBD; self-host instructions in [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md).)

### 3. Claude Desktop / Cursor / Windsurf (JSON config)

Add to your client config (`claude_desktop_config.json`, `.cursor/mcp.json`, etc.):

```json
{
  "mcpServers": {
    "korean-stat": {
      "command": "uvx",
      "args": ["korean-stat-mcp"],
      "env": {
        "KOSIS_API_KEY": "your_kosis_api_key_here"
      }
    }
  }
}
```

### 4. PyPI

```bash
pip install korean-stat-mcp
korean-stat-mcp --help
```

## Tool overview

The server exposes ~16 curated tools across these categories. See [docs/TOOL_MIGRATION.md](./docs/TOOL_MIGRATION.md) for the full tool→endpoint mapping.

| Category | Example tools | Purpose |
|---|---|---|
| Discovery | `search_statistics`, `list_categories` | Find tables by keyword or browse the catalog hierarchy |
| Metadata | `get_table_metadata`, `list_dimensions` | Inspect a table's classifications, periods, and items |
| Data fetch | `query_table`, `get_indicator_series` | Retrieve actual statistical values |
| Verification | `verify_statistics` | Re-fetch and cite a specific value the model is about to claim |
| Analysis | `execute_analysis`, `execute_visualization` | Statistical helpers and Altair charts (server-side) |
| Reporting | `execute_report`, `execute_table` | Composite HTML reports and styled tables |

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `KOSIS_API_KEY` | ✅ | Get one at https://kosis.kr/openapi/index/index.jsp |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` | optional | Cloudflare R2 credentials for hosting generated charts and reports |
| `KOSIS_ARTIFACTS_DIR` | optional | Local directory for artifacts when R2 is not configured |

See [.env.example](./.env.example) for the full list.

## Documentation

- [CLAUDE-EN.md](./CLAUDE-EN.md) — English project context for AI coding agents
- [docs/ARCHITECTURE_DESIGN.md](./docs/ARCHITECTURE_DESIGN.md) — System architecture
- [docs/KOSIS_API_REFERENCE.md](./docs/KOSIS_API_REFERENCE.md) — KOSIS endpoint and field reference
- [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) — Self-hosting (Docker, FastMCP HTTP, PostgreSQL)
- [docs/USER_GUIDE.md](./docs/USER_GUIDE.md) — End-user tool guide

## Contributing

Contributions are very welcome. See [CONTRIBUTING-EN.md](./CONTRIBUTING-EN.md) for the development setup, code style, and PR checklist. All contributors are expected to follow the [Code of Conduct](./CODE_OF_CONDUCT.md).

## License

MIT — see [LICENSE](./LICENSE).
