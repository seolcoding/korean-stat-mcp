# KOSIS OpenAPI Coverage Matrix

> Generated: 2026-04-30 — iteration 3 audit (US-002a)
> Source of truth: `docs/KOSIS_API_REFERENCE.md` and `docs/KOSIS_API_IMPLEMENTATION_PLAN.md` (Korean, in-repo).
> External verification deferred — the KOSIS portal (`https://kosis.kr/openapi/index/index.jsp` and the `devGuide_*` pages) is JavaScript-rendered and only exposes index/category routes (e.g. `devGuide_0101List.do`) — it does not enumerate the actual API `.do` endpoints in static HTML reachable by WebFetch. Recommend a manual portal review before US-008 release.

## Summary

- Total public OpenAPI endpoints: **14** (across 7 product categories)
- Implemented: **14** (14/14 = **100%** functional coverage)
- Missing: **0** endpoints — but several **parameter-level gaps** exist (see "Parameter coverage" and "Gaps")

> "Implemented" here means: a Python wrapper exists in `src/kosis_tools/` that hits the endpoint over HTTP and returns parsed results. "Parameter gaps" are documented KOSIS query parameters that our wrapper does not yet plumb through to callers.

## Endpoint matrix

| # | Endpoint path                                       | Category         | Purpose                                                       | Implemented? | Module / class                                            | Coverage notes                                                                                                          |
|---|-----------------------------------------------------|------------------|---------------------------------------------------------------|:------------:|-----------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|
| 1 | `/statisticsList.do?method=getList`                 | 통계목록         | Browse statistics tree by view code (subject/org/region)      | ✅           | `kosis_tools.list_categories.CategoryList`                | 3 helpers (`list_by_org`, `list_by_theme`, `list_statistics`); `format=sdmx` not exposed                                |
| 2 | `/Param/statisticsParameterData.do?method=getList`  | 통계자료         | Fetch actual data values for a table                          | ✅           | `kosis_tools.data.StatisticsData`                         | All `objL1`–`objL8`, `prdSe` Y/H/Q/M/S/F/IR, `startPrdDe`/`endPrdDe` covered; `newEstPrdCnt`/`prdInterval` NOT exposed   |
| 3 | `/statisticsData.do?method=getMeta&type=TBL`        | 메타자료         | Table name (KO/EN)                                            | ✅           | `table_meta.TableMetadata.get_table_info`                 | Full param coverage; `content=html` not exposed                                                                         |
| 4 | `/statisticsData.do?method=getMeta&type=ORG`        | 메타자료         | Organization info                                             | ✅           | `table_meta.TableMetadata.get_org_info`                   | Full coverage                                                                                                           |
| 5 | `/statisticsData.do?method=getMeta&type=PRD`        | 메타자료         | Period info                                                   | ✅           | `table_meta.TableMetadata.get_prd_info`                   | Full coverage                                                                                                           |
| 6 | `/statisticsData.do?method=getMeta&type=ITM`        | 메타자료         | Item / classification variables                               | ✅           | `table_meta.TableMetadata.get_itm_vars` + `get_obj_vars`  | Two helpers cover ITM and OBJ variants                                                                                  |
| 7 | `/statisticsData.do?method=getMeta&type=CMMT`       | 메타자료         | Comments / annotations                                        | ✅           | `table_meta.TableMetadata.get_comments`                   | Full coverage                                                                                                           |
| 8 | `/statisticsData.do?method=getMeta&type=UNIT`       | 메타자료         | Unit                                                          | ✅           | `table_meta.TableMetadata.get_unit`                       | Full coverage                                                                                                           |
| 9 | `/statisticsData.do?method=getMeta&type=SOURCE`     | 메타자료         | Source                                                        | ✅           | `table_meta.TableMetadata.get_source`                     | Full coverage                                                                                                           |
|10 | `/statisticsData.do?method=getMeta&type=WGT`        | 메타자료         | Weighting                                                     | ✅           | `table_meta.TableMetadata.get_weight`                     | Full coverage                                                                                                           |
|11 | `/statisticsData.do?method=getMeta&type=NCD`        | 메타자료         | Last-update date                                              | ✅           | `table_meta.TableMetadata.get_update_date`                | Full coverage                                                                                                           |
|12 | `/statisticsBigData.do`                             | 대용량 통계자료  | SDMX / CSV bulk download (>40K rows)                          | ✅           | `kosis_tools.big_data.StatisticsBigData`                  | `fetch_sdmx`, `fetch_csv`, `fetch_dsd` cover DSD / Generic / StructureSpecific; **XLS format not implemented**          |
|13 | `/statisticsExplData.do?method=getList`             | 통계설명         | Survey-level metadata (purpose, period, etc., 27 metaItm)     | ✅           | `kosis_tools.stats_explanation.StatsExplanation`          | All 27 `metaItm` codes selectable via `MetaItem`; full coverage                                                         |
|14 | `/statisticsSearch.do?method=getList`               | 통합검색         | Keyword search                                                | ✅           | `kosis_tools.search.StatisticsSearch`                     | `searchNm`, `resultCount`, `startCount` covered; **`sort=RANK/DATE` NOT exposed**                                       |

### 통계주요지표 (Key Indicators) — sub-matrix

All six endpoints are implemented in `kosis_tools.key_indicators.KeyIndicators` (counted as a single product category, not as 6 distinct rows above to keep the matrix aligned with the KOSIS portal's product taxonomy):

| Endpoint                          | Method                              | Notes                       |
|-----------------------------------|-------------------------------------|-----------------------------|
| `/pkNumberService.do`             | `get_explanation_by_id`             | Indicator explanation by ID |
| `/indExpService.do`               | `get_explanation_by_name`           | Indicator explanation by NM |
| `/indiListService.do`             | `get_by_list`                       | Indicators in a list        |
| `/indListSearchRequest.do`        | `search_by_name`, `search_by_id`    | Search by name/id           |
| `/indIdDetailSearchRequest.do`    | `get_detail`                        | Detail time-series          |
| `/prListSearchRequest.do`         | `search_by_period_type`             | Filter by period            |

### Auxiliary (non-OpenAPI) endpoints already wrapped

These are not part of the public OpenAPI proper but are used by the codebase against `kosis.kr` / `k-stat.go.kr` and worth listing for completeness:

| Endpoint                                                          | Module                                | Notes                                       |
|-------------------------------------------------------------------|---------------------------------------|---------------------------------------------|
| `/statHtml/statHtmlContent.do`                                    | `kosis_tools.kstat_metadata`          | Scrape HTML to extract `statsConfmNo`       |
| `https://www.k-stat.go.kr/metasvc/msba100/statsdcdta`             | `kosis_tools.kstat_metadata`          | Stats-approval metadata page (HTML scrape)  |

## Parameter coverage by endpoint

For each endpoint, ✅ supported / ⚠️ partial / ❌ missing.

### `/statisticsList.do`
| Param          | Status | Notes                                                                        |
|----------------|:-----:|-------------------------------------------------------------------------------|
| `apiKey`       | ✅    | from config                                                                   |
| `vwCd`         | ✅    | `MT_ZTITLE`, `MT_OTITLE`, `MT_GTITLE01`, `MT_RTITLE01` covered                |
| `parentListId` | ✅    | passed through                                                                |
| `format`       | ⚠️    | hard-coded `json` — `sdmx` not exposed                                        |

### `/Param/statisticsParameterData.do`
| Param           | Status | Notes                                                                       |
|-----------------|:-----:|------------------------------------------------------------------------------|
| `orgId`/`tblId` | ✅    | required                                                                     |
| `objL1`–`objL8` | ✅    | progressive expansion strategy implemented                                   |
| `itmId`         | ✅    | default `ALL`                                                                |
| `prdSe`         | ✅    | M/Q/S/Y/F/IR all mapped via `PeriodType`                                     |
| `startPrdDe`/`endPrdDe` | ✅ | with auto-format helper                                                |
| `newEstPrdCnt`  | ❌    | KOSIS supports "latest N periods" — not exposed                              |
| `prdInterval`   | ❌    | period-stride not exposed                                                    |
| `format`        | ⚠️    | hard-coded `json` — `sdmx`/`xml` not exposed                                 |

### `/statisticsData.do?method=getMeta` (all 8 types)
| Param   | Status | Notes                                                              |
|---------|:-----:|---------------------------------------------------------------------|
| `type`  | ✅    | TBL, ORG, PRD, ITM, OBJ, CMMT, UNIT, SOURCE, WGT, NCD               |
| `orgId`/`tblId` | ✅ | required                                                          |
| `content` | ⚠️ | `html` variant not exposed (only json)                              |

### `/statisticsBigData.do`
| Param           | Status | Notes                                                              |
|-----------------|:-----:|---------------------------------------------------------------------|
| `userStatsId`   | ✅    | required                                                            |
| `format`        | ⚠️    | `json`, `sdmx`, `csv` supported; **`xls` not implemented**          |
| `type`          | ✅    | `DSD`, `Generic`, `StructureSpecific`                               |
| `prdSe`         | ✅    |                                                                     |
| `startPrdDe`/`endPrdDe` | ✅ |                                                                  |
| `newEstPrdCnt`  | ✅    |                                                                     |
| `prdInterval`   | ✅    |                                                                     |

### `/statisticsExplData.do`
| Param      | Status | Notes                                                              |
|------------|:-----:|---------------------------------------------------------------------|
| `statId`   | ✅    | or `orgId+tblId`                                                    |
| `metaItm`  | ✅    | All 27 codes selectable via `MetaItem` enum                         |
| `content`  | ⚠️    | `html` not exposed                                                  |

### `/statisticsSearch.do`
| Param          | Status | Notes                                                            |
|----------------|:-----:|-------------------------------------------------------------------|
| `searchNm`     | ✅    | required                                                          |
| `resultCount`  | ✅    | up to 5000                                                        |
| `startCount`   | ✅    | for paging                                                        |
| `sort`         | ❌    | `RANK`/`DATE` ordering not exposed — relevant for `verify_statistics` (US-005) |
| `format`       | ⚠️    | hard-coded `json`                                                 |

### Key Indicators (all 6 endpoints)
Parameters specific to each endpoint (e.g. `statJipyoId`, `statJipyoNm`, `listId`, `prdSe`, `startPrdDe`/`endPrdDe`) are all plumbed through. No known parameter gaps.

## Gaps

All gaps are parameter-level, not endpoint-level. Each is actionable for iteration 4.

1. **`statisticsParameterData.do` — `newEstPrdCnt` / `prdInterval`** — Effort **S**. Add two optional kwargs to `StatisticsData.get_data` and forward them when set; mutually exclusive with `start_date`/`end_date`. Module: `src/kosis_tools/data.py`. Unlocks "latest N periods" without callers needing to know calendar formats.
2. **`statisticsSearch.do` — `sort=RANK|DATE`** — Effort **S**. Add `sort: Literal["RANK","DATE"] | None = None` to `StatisticsSearch.search`. Module: `src/kosis_tools/search.py`. Required for `verify_statistics` (US-005) to surface the most-recently-updated table.
3. **`statisticsList.do`, `statisticsParameterData.do`, `statisticsExplData.do`, `statisticsData.do(getMeta)`, `statisticsSearch.do` — `format=sdmx|xml|html`** — Effort **M** (one shared helper change in `base.KosisBaseClient` + per-endpoint param). All five wrappers currently hard-code `format=json`. Most callers won't need this, but `verify_statistics`/SDMX-consuming clients (US-005, US-007) may. Suggest exposing a `response_format: Literal["json","sdmx","xml"] = "json"` on the base client and only the public-facing methods that legitimately need it.
4. **`statisticsBigData.do` — `xls` format** — Effort **S**. Add `fetch_xls` to `StatisticsBigData` parallel to `fetch_csv` (returns raw bytes). Module: `src/kosis_tools/big_data.py`. Lower priority; XLS is rarely a better choice than CSV for downstream tooling.
5. **`statisticsData.do(getMeta) — content=html`** — Effort **S**. Add `content: Literal["json","html"] = "json"` to the eight `get_*` helpers in `table_meta.py`. Lowest priority — primary consumer is the LLM, which prefers JSON.

> No new module under `src/kosis_tools/endpoints/` is needed — the existing module layout already covers every endpoint. Iteration 4's work is "parameter completeness within existing modules" rather than "new endpoint wrappers."

## Reliability evidence

The current implementation is documented at **99.38% success rate** on a **10,000-table sample** from internal pre-release validation. The 62 failures were all `no_data` (deprecated tables or tables with no data), not API-call failures. US-002 work (parameter additions above) **must not regress** this number:

- All new parameters must be **optional** with `None` defaults so existing call paths are byte-identical.
- The existing `_execute_with_obj_retry` 7-stage `objL` strategy in `data.py` and the period-fallback logic must remain the default path.
- US-007 (Validation harness) should rerun the 10K sample after iteration 4 lands and gate the v0.1.0 release on ≥99.38%.

---

*Audit produced 2026-04-30 by US-002a. No source code, tests, README, or CLAUDE files were modified.*
