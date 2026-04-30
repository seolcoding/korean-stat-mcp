# Changelog

All notable changes to `korean-stat-mcp` are documented here.
The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Stop tracking generated HTML report artifacts; keep source scripts and regeneration notes in Git instead.
- Add packaging guardrails so local/generated artifacts such as `outputs/`, `kosis-reports/`, and `.omx/` do not enter release archives or Docker build context.
- Align the PR checklist with the scoped CI quality gates used by this repository.
- Replace pre-release placeholder URLs and marketplace owner strings with the public `seolcoding/korean-stat-mcp` repository path.
- Remove generated report/data folders, local editor/agent metadata, and legacy helper scripts from the public repository tree.

---

## [0.1.3] — 2026-04-30

### Changed
- Remove Altair from the base package and public MCP tool surface; native chart generation is delegated to client-side or dedicated visualization tools.
- Keep table and analysis helpers in the core package while returning explicit placeholders for legacy visualization helper calls.

---

## [0.1.2] — 2026-04-30

### Changed
- Trim heavyweight non-core dependencies from the base package by removing unused PDF tooling and binary chart export support; chart artifacts are HTML-only in the base install.

---

## [0.1.1] — 2026-04-30

### Changed
- Standardize the first public deployment shape: local `stdio` by default and Streamable HTTP at `/mcp` for remote connectors.
- Keep artifact handling local-only and remove the unused external object storage path, environment variables, optional extra, and Docker/Fly configuration.
- Add regression tests for `/health`, `/info`, and `/mcp` HTTP deployment endpoints.

---

## [0.1.0] — 2026-04-30

Initial public release. The package is renamed and refactored from the private `kosis-mcp` codebase into a public open-source MCP server.

### Added
- Bilingual KO/EN documentation: `README.md` + `README-EN.md`, `CONTRIBUTING.md` + `CONTRIBUTING-EN.md`, `CODE_OF_CONDUCT.md`.
- LLM routing manual (`docs/llm-routing-manual.md`): 17 query→tool decision rows, 6 implementation rules, 6 scenario chains, 9 anti-patterns. Importable system-prompt module at `src/mcp_server/system_prompt.py`.
- Allow-list tool surface (`src/mcp_server/exposed_tools.py`): 16 curated tools exposed to LLM clients; 10 internal tools reachable via `discover_tools` / `execute_tool` meta tools.
- `verify_statistics` MCP tool: cross-checks LLM numeric claims against the actual KOSIS source row, returns confidence ranking and source URL.
- KOSIS OpenAPI coverage matrix (`docs/API_COVERAGE.md`): 14/14 public endpoints implemented, parameter-level gaps closed.
- New parameters across endpoint wrappers: `newEstPrdCnt`/`prdInterval` (data), `sort=RANK|DATE` (search), `format=sdmx|xml|html` shared helper (base), `xls` format (big_data), `content=table|html` (table_meta) — all keyword-only with `None` defaults.
- Validation harness: `scripts/validation/run_reliability_test.py` (KOSIS API success-rate gate, default ≥99%) and `scripts/validation/run_llm_judge.py` (tool-routing accuracy gate, default ≥85%).
- GitHub Actions CI (`ruff`, `mypy`, `pytest`) and release workflow (PyPI Trusted Publishing + GHCR Docker push on tag).
- Fly.io deploy config (`fly.toml`) + bilingual `deploy/README.md` covering Fly.io, Render, Railway, DigitalOcean App Platform, and self-hosted Docker.
- Issue & PR templates under `.github/`.

### Changed
- Renamed package from `kosis-mcp` to `korean-stat-mcp`.
- `asyncpg` moved from required to optional extras (`[postgres]` / `[all]`). The base `pip install korean-stat-mcp` now requires no third-party AI vendor key.

### Removed
- OpenAI embeddings stack: `src/kosis_tools/embeddings.py` and `src/kosis_tools/hybrid_search.py` deleted; `search_tables_hybrid` MCP tool removed.
- pgvector schema parts in `migrations/init.sql` (vector extension, embedding column, hybrid_search SQL function).
- `openai` dependency dropped from `pyproject.toml`.
- All references to private hosting infrastructure (server hostname, owner-specific domain, temporary Cloudflare Tunnel URL) replaced with neutral placeholders or the `${KOSIS_MCP_URL}` environment variable.

### Archived
- `docs/HYBRID_SEARCH.md` → `docs/legacy/`
- `scripts/load_metadata.py` → `scripts/legacy/load_metadata_with_embeddings.py` (FTS-only loader to be added when needed).

### Reliability baseline
- KOSIS OpenAPI success rate: **99.38%** on a 10K-table sample (carried forward from internal pre-release testing). Re-verified at smaller pilot sizes via `scripts/validation/run_reliability_test.py`.
- Unit test suite: 445 tests, 100% pass.

---

[Unreleased]: https://github.com/seolcoding/korean-stat-mcp/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/seolcoding/korean-stat-mcp/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/seolcoding/korean-stat-mcp/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/seolcoding/korean-stat-mcp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/seolcoding/korean-stat-mcp/releases/tag/v0.1.0
