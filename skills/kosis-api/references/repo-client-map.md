# Repository Client Map

Use this file to choose the existing Python module instead of rewriting KOSIS logic.

## Core Modules

| Task | Module |
|---|---|
| Shared config, API key, base URL | `src/kosis_tools/config.py` |
| Shared request and KOSIS JSON parsing | `src/kosis_tools/base.py` |
| Statistics search/list | `src/kosis_tools/search.py`, `src/kosis_tools/list_categories.py` |
| Statistics data fetch | `src/kosis_tools/data.py` |
| Table metadata and `getMeta` calls | `src/kosis_tools/table_meta.py` |
| Statistics explanation | `src/kosis_tools/stats_explanation.py` |
| Large data API | `src/kosis_tools/big_data.py` |
| Key indicators | `src/kosis_tools/key_indicators.py` |
| Response normalization and analysis helpers | `src/kosis_tools/transform.py` |
| Charts and local artifacts | `src/kosis_tools/visualize.py`, `src/kosis_tools/executors/` |

## Avoid by Default

These are useful for server mode but should not be the skill's default path:

- `src/mcp_server/server.py`
- `src/mcp_server/app.py`
- Docker/Cloudflare/R2 deployment flow
- PostgreSQL hybrid search, unless the user asks for semantic search or metadata indexing

## Basic Live Workflow

1. Check `KOSIS_API_KEY`.
2. Use search/list clients to find candidate table ids.
3. Use `table_meta.py` to inspect period, items, classifications, and units.
4. Use `data.py` for a bounded data fetch.
5. Use `transform.py` to normalize `DT` and classification fields.
6. Use visualization/report modules only after the data shape is verified.
