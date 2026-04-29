# KOSIS Skill Reuse Plan

## Goal

Repackage this repository as a reusable Codex skill for KOSIS API work, instead of exposing the workflow primarily through an MCP server.

The target form is a progressive disclosure skill:

```text
kosis-api/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── references/
│   ├── official-api-index.md
│   ├── statistics-list.md
│   ├── statistics-data.md
│   ├── statistics-metadata.md
│   ├── large-data.md
│   ├── key-indicators.md
│   └── repo-client-map.md
└── scripts/
    ├── kosis_call.py
    ├── inspect_table.py
    └── extract_official_manual.py
```

`SKILL.md` should stay small. It should tell Codex which reference file to open for the current task, not embed the whole API manual.

## Current Findings

- The current working directory `/Users/sdh/Documents/Codex/2026-04-29/kosis-mcp` is empty.
- The actual reusable repository is `/Users/sdh/10_Dev/101_active/kosis-mcp`.
- The repo already contains Python KOSIS API clients under `src/kosis_tools/`.
- The repo is not just MCP glue. The MCP layer is mostly an adapter over reusable client modules.
- Full local test suite currently passes: `514 passed, 24 skipped, 2 warnings`.
- `skill-creator` was not preinstalled. It was installed globally from `openai/skills@skill-creator` and used as the skill design guide.

## Official KOSIS Documentation Check

Official sources to preserve in the skill references:

- KOSIS OpenAPI service introduction: `https://kosis.kr/openapi/introduce/introduce_01List.do`
- KOSIS statistics data guide: `https://kosis.kr/openapi/devGuide/devGuide_0203List.do`
- KOSIS OpenAPI PDF manual: `https://kosis.kr/openapi/file/openApi_manual_v1.0.pdf`

Confirmed from the official service introduction:

- KOSIS provides 7 API service groups: statistics list, statistics data, large statistics data, statistics explanation, table explanation, integrated search, and key indicators.
- Services are REST over HTTP.
- Common output formats include SDMX, JSON, XLS, and XML depending on service.
- Rate limit is documented as 1,000 calls per minute.
- The ordinary statistics data API has a 40,000-cell limit per request.
- Large statistics data supports SDMX and XLS, with XLS documented up to 200,000 cells.

Confirmed locally:

- The official PDF manual downloads successfully.
- The PDF is text-extractable with PyMuPDF.
- The downloaded manual has 158 pages.

Therefore, the skill can include official API context as local reference markdown generated from the PDF and official guide pages. The raw PDF should not be loaded into context directly; convert it into focused reference files.

## Skill Design Principles

Follow the installed `skill-creator` guidance:

- Keep `SKILL.md` concise.
- Put detailed API documentation under `references/`.
- Put repeatable, fragile request logic under `scripts/`.
- Avoid extra docs inside the skill folder such as README or changelog.
- Keep references one level deep from `SKILL.md`.
- Make each reference clearly discoverable by task.

## Proposed Trigger

Skill name:

```text
kosis-api
```

Frontmatter description draft:

```yaml
name: kosis-api
description: Work with Korean Statistical Information Service KOSIS OpenAPI data using the local kosis-mcp repository as a reusable Python API client. Use when Codex needs to search KOSIS tables, inspect table metadata, call statistics data APIs, handle KOSIS API quirks, process large responses, create charts or reports from KOSIS data, or refresh KOSIS official API documentation context without using the MCP server layer.
```

## Progressive Disclosure Map

`SKILL.md` should include only this navigation logic:

| User task | Load |
|---|---|
| "KOSIS에서 어떤 API가 있나?" | `references/official-api-index.md` |
| "통계표 검색/분류 탐색" | `references/statistics-list.md` |
| "실제 수치 데이터 조회" | `references/statistics-data.md` |
| "분류, 항목, 단위, 주기 확인" | `references/statistics-metadata.md` |
| "4만 셀 초과/대용량" | `references/large-data.md` |
| "100대 지표/주요지표" | `references/key-indicators.md` |
| "이 repo 코드 어디를 써야 하나?" | `references/repo-client-map.md` |

## Reuse Strategy

### Keep

- `src/kosis_tools/base.py`: shared request handling and nonstandard JSON parsing.
- `src/kosis_tools/config.py`: environment-driven API key and endpoint configuration.
- `src/kosis_tools/search.py`: statistics list/search client.
- `src/kosis_tools/data.py`: core statistics data retrieval.
- `src/kosis_tools/table_meta.py`: table metadata via `statisticsData.do?method=getMeta`.
- `src/kosis_tools/stats_explanation.py`: statistics explanation API.
- `src/kosis_tools/big_data.py`: large data API.
- `src/kosis_tools/key_indicators.py`: key indicator API.
- `src/kosis_tools/transform.py`: KOSIS response normalization and analysis helpers.
- `src/kosis_tools/visualize.py` and `src/kosis_tools/executors/`: optional reporting/chart workflows.

### De-emphasize

- `src/mcp_server/server.py`
- `src/mcp_server/app.py`
- Docker and deployment docs
- PostgreSQL hybrid search
- Cloudflare R2 artifact hosting

These are still useful for server deployment, but they should not be required for the skill's default workflow.

### Skill Default Workflow

1. Interpret the user's statistical question.
2. Load only the relevant API reference file.
3. Use local Python client modules directly, not the MCP server.
4. If API key is missing, stop with the exact required environment variable.
5. Search candidate tables.
6. Inspect table metadata before fetching data.
7. Fetch a small bounded slice first.
8. Expand only after checking row count, period format, classification dimensions, and units.
9. Transform data into a compact table or chart.
10. Cite the source table, period, unit, and API endpoint used.

## Official Documentation Ingestion Plan

### Phase 1: Capture

- Store raw official PDF in a non-skill source cache, for example:
  - `docs/official_sources/openApi_manual_v1.0.pdf`
- Store fetch metadata:
  - URL
  - fetch date
  - file size
  - SHA256
- Do not put the raw 11 MB PDF inside the final skill unless there is a specific reason.

### Phase 2: Extract

Create `scripts/extract_official_manual.py` to:

- Extract PDF text by page.
- Split by top-level service sections.
- Write concise markdown files into `skills/kosis-api/references/`.
- Preserve official page numbers in headings.
- Avoid copying huge examples unless they are necessary.

### Phase 3: Normalize

For each API group, keep:

- Endpoint
- Required parameters
- Optional parameters
- Output formats
- Limits
- Known quirks
- Repo module/function that implements it
- Minimal request example
- Minimal response field map

### Phase 4: Cross-check Against Code

Build a coverage table:

| Official API group | Repo module | Status |
|---|---|---|
| Statistics list | `src/kosis_tools/list_categories.py`, `search.py` | implemented |
| Statistics data | `src/kosis_tools/data.py` | implemented |
| Large statistics data | `src/kosis_tools/big_data.py` | implemented |
| Statistics explanation | `src/kosis_tools/stats_explanation.py` | implemented |
| Table explanation / metadata | `src/kosis_tools/table_meta.py` | implemented |
| Integrated search | `src/kosis_tools/search.py`, `metadata_fetcher.py` | partially split |
| Key indicators | `src/kosis_tools/key_indicators.py` | implemented |

### Phase 5: Validate With Real Calls

Use `KOSIS_API_KEY` and run representative checks:

- `statisticsList.do`
- `statisticsSearch.do`
- `statisticsData.do?method=getMeta`
- `Param/statisticsParameterData.do`
- `statisticsExplData.do`
- `statisticsBigData.do`
- key indicator endpoints

Classify each as:

- works without registration
- requires prior table registration
- requires special period/classification handling
- currently unsupported by local wrapper

## Implementation Plan

### Step 1: Create Skill Skeleton

Use the installed skill creator script:

```bash
python /Users/sdh/.agents/skills/skill-creator/scripts/init_skill.py \
  kosis-api \
  --path /Users/sdh/10_Dev/101_active/kosis-mcp/skills \
  --resources scripts,references \
  --interface display_name="KOSIS API" \
  --interface short_description="Search and analyze Korean public statistics via KOSIS OpenAPI" \
  --interface default_prompt="Use KOSIS OpenAPI to find, inspect, fetch, and analyze Korean statistical data using the local Python client modules."
```

### Step 2: Add References

Create the first reference files manually from the current repo docs and official sources:

- `official-api-index.md`
- `statistics-data.md`
- `repo-client-map.md`

Then add the remaining reference files after extraction.

### Step 3: Add Scripts

Add deterministic scripts:

- `kosis_call.py`: minimal authenticated API call wrapper.
- `inspect_table.py`: search plus metadata inspection helper.
- `extract_official_manual.py`: PDF-to-reference extraction helper.

Scripts should import from `src/kosis_tools` where possible instead of duplicating client logic.

### Step 4: Validate Skill

Run:

```bash
python /Users/sdh/.agents/skills/skill-creator/scripts/quick_validate.py \
  /Users/sdh/10_Dev/101_active/kosis-mcp/skills/kosis-api
```

### Step 5: Smoke Test As a Skill

Use the skill on three real prompts:

- "KOSIS에서 출산율 관련 통계표 찾아줘"
- "서울/부산 인구를 최근 5년 비교해줘"
- "이 통계표의 분류와 항목 구조를 먼저 확인해줘"

Success criteria:

- The agent loads only the necessary reference file.
- It does not start the MCP server.
- It uses Python client modules directly.
- It reports endpoint, table id, period, unit, and data limitations.

## Risks

- Official guide pages are partly dynamic and sometimes expose detail through UI actions. The PDF manual is the more stable source for extraction.
- Some KOSIS APIs require prior registration or generated URLs. The skill must distinguish "callable directly" from "requires registration".
- KOSIS JSON can be nonstandard. The skill should route calls through existing repo parsing utilities instead of ad hoc JSON parsing.
- `execute_code` and MCP server deployment should not be part of the default skill path because they expand the security and runtime surface.
- Existing docs contain older deployment URLs and 2025 status claims; the skill should avoid treating those as current operational truth.

## Immediate Next Actions

1. Create `skills/kosis-api` with `skill-creator`.
2. Generate `references/official-api-index.md` from official KOSIS introduction plus repo API map.
3. Generate `references/statistics-data.md` from the official PDF and current `docs/KOSIS_API_REFERENCE.md`.
4. Add `references/repo-client-map.md` so future Codex runs know which Python modules to call.
5. Add `scripts/kosis_call.py` and smoke test it with missing-key and live-key paths.
6. Validate the skill folder.
