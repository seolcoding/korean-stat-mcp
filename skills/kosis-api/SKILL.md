---
name: kosis-api
description: Work with Korean Statistical Information Service KOSIS OpenAPI data using the local kosis-mcp repository as a reusable Python API client. Use when Codex needs to search KOSIS tables, inspect table metadata, call statistics data APIs, handle KOSIS API quirks, process large responses, create charts or reports from KOSIS data, or refresh KOSIS official API documentation context without using the MCP server layer.
---

# KOSIS API

Use this skill to work with KOSIS OpenAPI through the local Python client modules in this repository. Prefer direct Python module calls over starting the MCP server.

## Default Workflow

1. Identify the KOSIS task: search, metadata inspection, data fetch, large data, explanation, key indicator, transform, chart, or report.
2. Load only the reference file needed for that task.
3. Use `src/kosis_tools/` clients directly.
4. Require `KOSIS_API_KEY` before live KOSIS calls.
5. Search or inspect metadata before fetching data.
6. Fetch a small bounded slice first, then expand.
7. Report table id, organization id, period, unit, endpoint, and limits.

## Reference Routing

- For available official API groups, limits, and source URLs, read `references/official-api-index.md`.
- For ordinary statistics data calls and period/classification parameters, read `references/statistics-data.md`.
- For which repository module to reuse, read `references/repo-client-map.md`.

Add or read more reference files only when the task needs them. Keep official manual details in references, not here.

## Scripts

- Use `scripts/kosis_call.py` for a quick authenticated raw API check.
- Prefer repository modules for production work; the script is a smoke-test and debugging helper.

## Constraints

- Do not use the MCP server layer unless the user explicitly asks for MCP behavior.
- Do not browser-scrape KOSIS pages when an OpenAPI endpoint or official PDF reference is sufficient.
- Do not load the full official PDF into context. Extract or open only the relevant reference section.
- Treat older deployment URLs and production-status claims in repository docs as stale until verified.
