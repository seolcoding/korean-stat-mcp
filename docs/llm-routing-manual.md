# LLM Routing Manual / LLM 라우팅 매뉴얼

> Bilingual decision manual for LLM clients (and humans) using the `korean-stat-mcp` server.
> 한국어 ↔ English. KO and EN sit side by side in each section.

This document tells an LLM **which tool to call first**, **what to chain after**, and **what NOT to do**. It exists because the largest source of failure in MCP usage is *picking the wrong tool* or *guessing parameters*. Follow this manual instead of guessing.

---

## How to Read This Manual

- **Section A** — A query → tool decision table. Match the user's intent to a row, then run the chain left-to-right.
- **Section B** — Implementation rules every LLM must obey (data types, period codes, formatting).
- **Section C** — Named scenario chains for common workflows.
- **Section D** — Anti-patterns. Do not do these.

KO: A 섹션에서 사용자 질의에 맞는 행을 찾아 좌→우 순서대로 도구를 호출하세요. B의 규칙은 항상 지키고, D의 안티패턴은 피하세요.

---

## Section A — Query → Tool Decision Table / 질의→도구 결정 표

| # | 한국어 질의 예시 | English query example | First tool | Then | Then |
|:-:|------------------|-----------------------|------------|------|------|
| 1 | "전국 인구 추이 보여줘" | "Show national population trend" | `search_statistics_tables` | `get_statistics_data` (PRD_DE range) | `execute_visualization` (line) |
| 2 | "서울 vs 부산 인구 비교" | "Compare Seoul vs Busan population" | `search_statistics_tables` | `get_available_values` (regions) | `get_statistics_data` (objL1=서울,부산) → `execute_visualization` (grouped bar) |
| 3 | "최근 5년 GDP 변화율" | "GDP change rate over the last 5 years" | `search_statistics_tables` (GDP) | `get_statistics_data` (PRD_DE last 5y) | `execute_analysis` (`calc_change_rate` / `calc_cagr`) |
| 4 | "출산율 상위 10개 시군구" | "Top 10 municipalities by fertility rate" | `search_statistics_tables` (fertility) | `get_statistics_data` (all regions) | `aggregate_statistics` (sort, top-N) → `execute_table` |
| 5 | "한국 가계 부채 규모는?" | "What is Korea's household debt level?" | `search_statistics_tables` (가계 부채) | `get_statistics_data` (latest PRD_DE) | summarize 1 number with units |
| 6 | "분기별 실업률" | "Quarterly unemployment rate" | `search_statistics_tables` (실업률) | `get_statistics_data` (prdSe=Q, PRD_DE="2024Q1") | `execute_visualization` (line, x=PRD_DE) |
| 7 | "반기별 고용 통계" | "Half-year employment statistics" | `search_statistics_tables` (고용) | `get_statistics_data` (prdSe=H, PRD_DE="2024H1") | `execute_table` |
| 8 | "통계청 발표 보고서 목록" | "List statistics published by Statistics Korea" | `browse_by_organization` (ORG=통계청) | `search_statistics_tables` within results | `get_table_metadata` |
| 9 | "인구·가구 부문 전체 목록" | "All tables in the Population & Households theme" | `browse_by_theme` (theme=인구·가구) | iterate / paginate | `get_table_metadata` |
| 10 | "월별 소비자물가 지수" | "Monthly CPI" | `search_statistics_tables` (CPI/소비자물가) | `get_statistics_data` (prdSe=M, PRD_DE="202401") | `execute_visualization` (line) |
| 11 | "이 통계표에 어떤 분류 값이 있어?" | "What classification values does this table have?" | `get_available_values` (orgId, tblId) | (use values to filter) | `get_statistics_data` |
| 12 | "이 통계표 상세 메타" | "Detailed metadata for this table" | `get_table_metadata` (orgId, tblId) | `get_available_values` | — |
| 13 | "결과 데이터 일부만 차트로 그려줘" | "Chart only part of the result data" | `read_stored_data` (resource_id, slice) | `execute_visualization` | — |
| 14 | "지역별 합계만 뽑아줘" | "Aggregate sum by region" | `aggregate_statistics` (group_by=C1_NM, agg=sum) | `execute_table` or `execute_visualization` | — |
| 15 | "내가 받은 데이터 다시 보여줘" | "Show me the data I got earlier" | `list_stored_data` | `read_stored_data` (resource_id) | — |
| 16 | "이 통계 수치 진짜 맞아?" | "Are these statistic values actually correct?" | `verify_statistics` *(upcoming, US-005)* | (cross-check) | report verification status |
| 17 | "이 도구 말고 더 있어?" | "Are there other tools available?" | `discover_tools` | (filter by category) | call relevant tool |

> Notes / 비고
> - `search_statistics_tables` uses KOSIS `statisticsSearch.do` natively, with optional PG FTS augmentation.
> - "First tool" is the **starting** point. Always prefer the leftmost cell unless the user already gave you the next-stage inputs (e.g. they pasted a `tblId`).
> - Tool 16 (`verify_statistics`) is being added in US-005 — if it is not registered yet, fall back to "ask user to confirm against the KOSIS site URL" rather than fabricating verification.

---

## Section B — Critical Implementation Rules / 핵심 구현 규칙

LLM clients **must** obey these rules. Violations cause silent data corruption or user confusion.

### B.1 `DT` is a string / `DT`는 문자열이다
KOSIS returns `DT` as a string: `"9411211"`, `"-"`, `"*"`, etc. Always coerce carefully.

```python
# OK
df["DT"] = pd.to_numeric(df["DT"], errors="coerce")  # "-", "*" → NaN

# NOT OK
df["DT"] = df["DT"].astype(int)   # crashes on "-"
```

KO: `DT`는 항상 문자열입니다. `"-"`, `"*"` 같은 특수값을 NaN으로 변환한 뒤 사용하세요.

### B.2 Period codes M / Q / H / Y / 기간 코드
KOSIS uses period codes for `prdSe`:

| Code | Meaning | `PRD_DE` example |
|------|---------|------------------|
| `Y`  | Yearly  | `"2024"` |
| `H`  | Half-year | `"2024H1"`, `"2024H2"` |
| `Q`  | Quarter | `"2024Q1"` … `"2024Q4"` |
| `M`  | Monthly | `"202401"` |
| `D`  | Daily   | `"20240115"` |

**Quarterly = `"Q"` suffix, Half-year = `"H"` suffix.** Do not encode quarters as months.

KO: 분기는 반드시 `2024Q1` 형식, 반기는 `2024H1` 형식으로 보내세요. `2024-03` 같은 임의 형식은 금지.

### B.3 Don't manually iterate `objL1`–`objL8` / `objL` 수동 반복 금지
The server has a 7-step automatic fallback strategy for the `objL1`…`objL8` parameters. Pass what the user asked for and **trust the server**. Do not loop them yourself.

KO: `objL1`–`objL8`은 서버가 7단계로 자동 fallback 합니다. LLM이 직접 반복하면 안 됩니다.

### B.4 Local-government tables and `no_data` / 지자체 테이블과 `no_data`
지자체(local-government) tables sometimes return `no_data` even with the fallback strategy. Treat `no_data` as **deprecated / discontinued** and tell the user — do not retry blindly.

```
Status: no_data → "이 통계표는 더 이상 발표되지 않을 수 있습니다."
```

### B.5 Number formatting / 숫자 포맷
Always thousand separators. Never scientific notation.

| Where | Rule |
|-------|------|
| Altair Y-axis | `axis=alt.Axis(format=",.0f")` |
| Inline text | `f"{value:,.0f}"` |
| Population & large counts | report in 천명 (thousand persons), e.g. `"9,386천 명"` |
| Forbidden | `5.17e+7` and any scientific notation |

### B.6 Don't pull whole tables into LLM context / 전체 데이터 컨텍스트 로드 금지
The server stores results and returns a **summary + resource_id**. Use that summary to answer simple questions; for chart/analysis use `read_stored_data` to fetch the chunk you actually need.

```
Wrong:  data = get_statistics_data(...); LLM reads all 50,000 rows
Right:  summary, resource_id = get_statistics_data(...);
        rows = read_stored_data(resource_id, offset=0, limit=200);
        execute_visualization(rows)
```

KO: 결과 전체를 LLM 컨텍스트에 올리지 마세요. 요약 + `resource_id`만 받고 필요한 청크만 `read_stored_data`로 가져오세요.

---

## Section C — Scenario Chains / 시나리오 체인

Named workflows. Each is a one-line description plus the canonical tool chain.

| Name | Description / 설명 | Canonical chain |
|------|-------|------|
| `population_trend` | Single region over time / 단일 지역 시계열 | `search_statistics_tables` → `get_statistics_data` (objL1=region, prdSe=Y) → `execute_visualization` (line) |
| `regional_compare` | Same metric across regions / 지역 간 동일 지표 비교 | `search_statistics_tables` → `get_available_values` → `get_statistics_data` (objL1=multi) → `execute_visualization` (grouped bar) |
| `yoy_change` | Year-over-year change rate / 전년 대비 변화율 | `get_statistics_data` (PRD_DE last 2y) → `execute_analysis` (`calc_change_rate`) |
| `ranking` | Top-N or bottom-N by metric / 상·하위 N | `get_statistics_data` (all regions, latest PRD_DE) → `aggregate_statistics` (sort) → `execute_table` |
| `composition` | Pie/treemap of category breakdown / 구성비 | `get_statistics_data` (one PRD_DE, multi-category) → `execute_visualization` (arc/treemap) |
| `cross_period_analysis` | Different time scales (M/Q/Y) / 시간 단위 비교 | `get_statistics_data` (prdSe=M) + `get_statistics_data` (prdSe=Y) → `execute_analysis` to align → `execute_visualization` (dual axis or facet) |

---

## Section D — Anti-patterns / 안티패턴

Do not do these. Each is a real failure mode observed in the wild.

- ❌ **Loading entire `data` into LLM context** / `data`를 통째로 LLM 컨텍스트에 로드
  → Token explosion. Use `summary + resource_id` + `read_stored_data` chunks.

- ❌ **Calling multiple tools by guessing** / 여러 도구를 추측으로 호출
  → Wastes turns. Match the query to Section A first; pick exactly one starting tool.

- ❌ **Requesting quarterly data with `prdSe=Y`** / 분기 데이터를 `Y`로 요청
  → Returns yearly aggregates and confuses the user. Use `prdSe=Q` and `PRD_DE="2024Q1"`.

- ❌ **Trying to use a hybrid-search tool** / Hybrid search 도구 사용 시도
  → Removed in US-001b. There is no `hybrid_search` / `vector_search` tool. Use `search_statistics_tables` (KOSIS native search).

- ❌ **Writing directly into `outputs/`** / `outputs/` 디렉토리에 직접 쓰기
  → Forbidden. Only the server writes there. LLMs read via `read_stored_data` only.

- ❌ **Manually iterating `objL1`…`objL8`** / `objL` 수동 반복
  → The server already does a 7-step fallback. Manual iteration both duplicates work and breaks the strategy.

- ❌ **Coercing `DT` with `astype(int)`** / `DT.astype(int)` 사용
  → Crashes on `"-"` / `"*"`. Always `pd.to_numeric(..., errors="coerce")`.

- ❌ **Reporting raw counts like `9386320`** / 큰 수를 원시값 그대로 보고
  → Use thousand separators and 천명 unit: `9,386천 명`. Never scientific notation.

- ❌ **Treating `no_data` as a transient error** / `no_data`를 일시적 오류로 처리
  → It typically means the table is deprecated or never had data. Tell the user; do not retry.

---

*Last updated: 2026-04 (US-004 bilingual routing manual)*
