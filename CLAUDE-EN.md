# KOSIS MCP Server - Claude Code Instructions

> 🇰🇷 한국어: [CLAUDE.md](./CLAUDE.md)

> **This document is the top-level entrypoint for Claude Code to understand and work on this project.**

---

## Document Hierarchy

### Core Documents (Must Read)

| Priority | Document | Purpose | When to Reference |
|:--------:|----------|---------|-------------------|
| 1 | **[PRD.md](./PRD.md)** | Product requirements, user stories, acceptance criteria | Before implementing features |
| 2 | **[MCP_PATTERN.md](./MCP_PATTERN.md)** | Core large-data handling patterns | Whenever building MCP tools |
| 3 | **[docs/ARCHITECTURE_DESIGN.md](./docs/ARCHITECTURE_DESIGN.md)** | Whole-system architecture | When designing new features |
| 4 | **[docs/CODEBASE_WALKTHROUGH.md](./docs/CODEBASE_WALKTHROUGH.md)** | Codebase structure, file responsibilities | When modifying code |

### API & Data Documents

| Document | Content | When to Reference |
|----------|---------|-------------------|
| [docs/KOSIS_API_REFERENCE.md](./docs/KOSIS_API_REFERENCE.md) | KOSIS API endpoints, parameters, response fields | When calling/parsing the API |
| [docs/KOSIS_API_IMPLEMENTATION_PLAN.md](./docs/KOSIS_API_IMPLEMENTATION_PLAN.md) | API implementation plan, gap analysis | When extending API features |
| [docs/LARGE_DATA_MCP_PATTERNS.md](./docs/LARGE_DATA_MCP_PATTERNS.md) | execute_code patterns in detail | When developing code-execution features |

### Metadata Documents

| Document | Content |
|----------|---------|
| [docs/METADATA_COLLECTION_GUIDE.md](./docs/METADATA_COLLECTION_GUIDE.md) | Metadata collection methods |
| [docs/METADATA_JSON_SCHEMA.md](./docs/METADATA_JSON_SCHEMA.md) | JSON schema definitions |
| [docs/METADATA_OPTIMIZATION_STRATEGY.md](./docs/METADATA_OPTIMIZATION_STRATEGY.md) | Local metadata utilization strategy (XLS-based) |

### User Documents

| Document | Content |
|----------|---------|
| [docs/USER_GUIDE.md](./docs/USER_GUIDE.md) | User guide, tool usage, examples |
| [docs/llm-routing-manual.md](./docs/llm-routing-manual.md) | Bilingual query→tool routing manual for LLM clients |

### Deployment & Infrastructure Documents

| Document | Content | Status |
|----------|---------|--------|
| [docs/ARCHITECTURE_DESIGN.md](./docs/ARCHITECTURE_DESIGN.md) | Whole-system architecture, layer structure, data flow | Done |
| [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) | FastMCP HTTP, Docker, PostgreSQL | Done |
| [docs/legacy/HYBRID_SEARCH.md](./docs/legacy/HYBRID_SEARCH.md) | (legacy) prior hybrid-search design. Since v0.1.0 only PG FTS is used | Archived |
| [docs/DOCKER_ARCHITECTURE.md](./docs/DOCKER_ARCHITECTURE.md) | Docker Compose deployment architecture | Planned |

### Test Documents

| Document | Content |
|----------|---------|
| [tests/e2e/E2E_TEST_PLAN.md](./tests/e2e/E2E_TEST_PLAN.md) | Persona-driven E2E test plan |

---

## Project Status (Current State)

### Completed Features

**Phase 1-2: Core MCP** (done)
- MCP server skeleton (FastMCP-based)
- KOSIS API integration (search, query, metadata)
- Code execution pattern (`execute_code` tool)
- Visualization (Altair-based chart generation)
- Report generation (HTML reports)

**Phase 3: Production Infrastructure** (done)
- PostgreSQL FTS (optional) — full-text search over 252,890 table metadata records
- KOSIS API native search (`statisticsSearch.do`) used as primary
- FastAPI HTTP server (`app.py`)
- Cloudflare R2 CDN (chart/report hosting, optional)
- Docker containerization

> Note: in US-001b the project removed pgvector and OpenAI embeddings. The current stack relies on the KOSIS native search API as the primary search path, with optional PostgreSQL FTS as a fallback/augmentation. There is no embedding-based hybrid search.

**Modular Executors** (done)
- `execute_visualization` — chart generation (thousand separators, no scientific notation)
- `execute_analysis` — statistical analysis (change rate, CAGR)
- `execute_table` — HTML tables (styled)
- `execute_report` — composite report (chart + analysis + table)

**Phase 4: Remote Deployment** (done, 2025-12-20)
- Cloudflare Tunnel set up (self-hosted URL)
- External access enabled (self-hosted remote server)
- E2E tests passing (11/11)
- Running in production

**Phase 4.5: API Reliability Optimization** (done, 2025-12-21)
- Auto strategy for `objL` parameters (7-step fallback)
- Quarter/half-year period auto-conversion (Q, H formats)
- Local-government table fallback strategy
- **API success rate: 99.38%** (10,000-sample test)
- Log cleanup: retry errors at DEBUG, only final failures at WARNING

### API Success Rate Test Results

| Sample size | Success | Failure | Success rate |
|-------------|---------|---------|--------------|
| 500 | 497 | 3 | 99.4% |
| 2,000 | 1,985 | 15 | 99.25% |
| **10,000** | **9,938** | **62** | **99.38%** |

> Failed tables are all `no_data` (deprecated or empty).

### Next Steps (Phase 5)
- Permanent Cloudflare tunnel (currently temporary URLs)
- Auth / authorization system
- Data caching optimization
- Filter deprecated tables (metadata cleanup)

---

## Core Constraints

### 1. Large-Data Handling Principle

```
ANTI-PATTERN: API → full data → LLM context (token explosion)
PREFERRED:    API → server-side store → summary to LLM → request chunks on demand
```

### 2. Number Format Rules

| Item | Rule | Example |
|------|------|---------|
| Population | Thousand-person units | `9,386천 명` (not `9386320`) |
| Y-axis | `format=",.0f"` | Thousand separators |
| Scientific notation | **Forbidden** | `5.17e+7` not allowed |

### 3. Tech Stack

| Area | Tech | Notes |
|------|------|-------|
| Visualization | **Altair** | Instead of Plotly/Matplotlib |
| Server | **FastMCP + FastAPI** | Dual MCP + HTTP mode |
| DB (optional) | **PostgreSQL FTS** | Metadata full-text search; falls back to KOSIS API search if unavailable |
| Search (default) | **KOSIS `statisticsSearch.do`** | API native search used as primary |

> No pgvector, no OpenAI embeddings — these were removed in US-001b. Search is API-first with optional PG FTS.

### 4. Forbidden

- **Playwright/Selenium/Puppeteer** are forbidden
- All data collection must use the API or `requests.get`
- Must be parseable quickly without browser automation

---

## Directory Structure

```
kosis-mcp/
├── src/
│   ├── mcp_server/
│   │   ├── server.py              # MCP server (tool definitions)
│   │   └── app.py                 # FastAPI HTTP app
│   └── kosis_tools/
│       ├── report_tools.py        # Data query / analysis
│       ├── code_executor.py       # Generic execute_code
│       ├── visualize.py           # Altair visualization
│       ├── executors/             # Modular executors
│       │   ├── visualization.py   # Charts (with guidelines)
│       │   ├── analysis.py        # Analysis (statistical helpers)
│       │   ├── table.py           # Tables (styled)
│       │   └── report.py          # Reports (composition)
│       ├── database.py            # PostgreSQL connection (optional)
│       └── r2_storage.py          # Cloudflare R2 storage (optional)
├── data/
│   └── metadata_api/
│       └── tables.json            # Metadata (252,890 tables)
├── migrations/
│   └── init.sql                   # PostgreSQL schema
├── scripts/
│   └── load_metadata.py           # DB load script
├── .claude/
│   └── commands/
│       └── test-mcp.md            # E2E test slash command
├── Dockerfile                     # Container build
├── docker-compose.yml             # Local dev environment
├── CLAUDE.md                      # Korean entrypoint
└── CLAUDE-EN.md                   # This document (English mirror)
```

---

## KOSIS API Quick Reference

### Core Endpoints

| Endpoint | Purpose |
|----------|---------|
| `statisticsParameterData.do` | Actual data retrieval |
| `statisticsList.do` | Statistics list browsing |

### Data Response Fields

| Field | Description | Example |
|-------|-------------|---------|
| `PRD_DE` | Period | `2023`, `202401` |
| `C1_NM` | Classification 1 (typically region) | `서울특별시` |
| `DT` | **Data value (string!)** | `"9411211"`, `"-"` |
| `ITM_NM` | Item name | `총인구` |
| `UNIT_NM` | Unit | `명`, `%` |

> Warning: `DT` is a string. Special values like `"-"` and `"*"` must be handled.

---

## Server Execution

### Remote Hosting (Optional)

`korean-stat-mcp` can be self-hosted by users. Set the `KOSIS_MCP_URL` env var to your instance address.

```
URL:    ${KOSIS_MCP_URL}        # e.g. https://kosis-mcp.example.com
Status: Self-hosted by user
Server: User-hosted (e.g. Ubuntu 24.04+, Docker)
```

**Test:**
```bash
# Health check (self-hosted instance)
curl ${KOSIS_MCP_URL}/health

# E2E workflow test
uv run python scripts/test_e2e_workflow.py ${KOSIS_MCP_URL}
```

### Local Development (Docker Compose)

```bash
# Start PostgreSQL + server
docker-compose up -d

# Or run manually
DATABASE_URL="postgresql://kosis:kosis_dev_password@localhost:5432/kosis" \
KOSIS_ARTIFACTS_DIR="/tmp/kosis_artifacts" \
KOSIS_BASE_URL="http://localhost:8000" \
uv run uvicorn mcp_server.app:app --port 8000
```

### Local Test

```bash
# Server health
curl http://localhost:8001/health

# E2E test slash command
/test-mcp
```

---

## Modular Executor Usage

### execute_visualization

```python
# Thousand separators + no scientific notation are auto-applied
code = '''
df = prepare_data(data, numeric_fields=["DT"])
df["population_thousand"] = df["DT"] / 1000

chart = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X("PRD_DE:N", title="Year"),
    y=alt.Y("population_thousand:Q", title="Population (thousand)",
            axis=alt.Axis(format=",.0f")),  # Required!
)
return save_chart(chart, "population.html")
'''
```

### execute_analysis

```python
# Helpers: calc_change_rate, calc_cagr, to_thousand
code = '''
df = prepare_data(data, numeric_fields=["DT"])
pop_2023 = df[df["PRD_DE"] == "2023"]["DT"].iloc[0]
pop_2019 = df[df["PRD_DE"] == "2019"]["DT"].iloc[0]

return {
    "summary": {
        "2023 population": f"{to_thousand(pop_2023):,.0f}천 명",
        "Change rate":     f"{calc_change_rate(pop_2023, pop_2019):.1f}%",
    }
}
'''
```

### execute_report (composition)

```python
# Combine analysis + charts + tables
code = '''
return build_report(
    title="Population Analysis Report",
    analysis=analysis,   # execute_analysis output
    charts=charts,       # array of execute_visualization outputs
    tables=tables,       # array of execute_table outputs
    source="Statistics Korea (KOSIS)",
)
'''
```

---

## References

- **KOSIS Top 100 Indicators**: https://kosis.kr/visual/nsportalStats/main.do
- **FastMCP docs**: https://gofastmcp.com/
- **Altair docs**: https://altair-viz.github.io/

---

*Last updated: 2025-12-21 (Phase 4.5 API reliability optimization complete)*
