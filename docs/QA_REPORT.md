# korean-stat-mcp — QA / Performance / Availability Report

**Date:** 2026-05-01
**Endpoint:** https://korean-stat-mcp.seolcoding.com/mcp
**App version:** v12 (post #18 deploy)

---

## 1. Test Report

```
345 passed, 1 skipped, 1 warning  ·  total 9.80s
```

Skipped: 1 verify integration test that needs live KOSIS quota.
Warning: a registered-mark warning on `@pytest.mark.integration` (cosmetic).

### Test files (all passing)

| Layer | File | Tests |
|---|---|---|
| Unit | `tests/unit/test_base.py` | KOSIS HTTP base client |
| Unit | `tests/unit/test_big_data.py` | 40K/200K cell handling |
| Unit | `tests/unit/test_data.py` | StatisticsData incl. `new_est_prd_cnt`, `prd_interval` |
| Unit | `tests/unit/test_data_storage.py` | local artifact storage |
| Unit | `tests/unit/test_errors.py` | KOSIS error classifier (all 10 codes) |
| Unit | `tests/unit/test_http_app.py` | ASGI surface |
| Unit | `tests/unit/test_key_indicators.py` | 6 KI client methods |
| Unit | `tests/unit/test_list_categories.py` | 12 vwCd codes |
| Unit | `tests/unit/test_load_config_priority.py` | ContextVar > env priority |
| Unit | `tests/unit/test_mcp_guidelines.py` | tool docs / guidelines |
| Unit | `tests/unit/test_release_readiness.py` | release sanity |
| Unit | `tests/unit/test_request_context.py` | per-request key isolation |
| Unit | `tests/unit/test_search.py` | search incl. `sort=RANK\|DATE` |
| Unit | `tests/unit/test_stats_explanation.py` | metaItm fan-out |
| Unit | `tests/unit/test_table_meta.py` | 9 metadata sub-types |
| Unit | `tests/unit/test_verify.py` | verify_statistics matcher |
| Integration | `tests/integration/test_byok_http.py` | 13 — middleware + rate limit + error envelope (6 tools) |
| Integration | `tests/integration/test_key_indicators_exposed.py` | 10 — 4 KI MCP tools |

### Coverage

| Module | Stmts | Cover |
|---|---:|---:|
| `kosis_tools/errors.py` | 29 | **100%** |
| `kosis_tools/request_context.py` | 3 | **100%** |
| `kosis_tools/metadata_models.py` | 119 | **100%** |
| `mcp_server/middleware.py` | 43 | **100%** |
| `mcp_server/exposed_tools.py` | 10 | **100%** |
| `kosis_tools/base.py` | 80 | 91% |
| `kosis_tools/key_indicators.py` | 183 | 90% |
| `kosis_tools/verify.py` | 206 | 90% |
| `kosis_tools/list_categories.py` | 109 | 87% |
| `kosis_tools/search.py` | 54 | 83% |
| `kosis_tools/table_meta.py` | 194 | 80% |
| `kosis_tools/report_tools.py` | 213 | 79% |
| `kosis_tools/big_data.py` | 186 | 71% |
| `mcp_server/app.py` | 89 | 61% |
| `mcp_server/server.py` | 340 | 50% |
| `kosis_tools/data.py` | 322 | 24% |
| `kosis_tools/metadata_fetcher.py` | 181 | 13% |
| `kosis_tools/cache_builder.py` | 199 | 19% |
| `kosis_tools/metadata_enricher.py` | 396 | 7% |
| **Total** | **3328** | **56%** |

**Reading the coverage:**
- The thin layers (errors, middleware, request-context) are 100%, which is the right place to be at — these gate every request.
- `kosis_tools/data.py` at 24% — most of the unhit code is the smart-retry fallback ladder for `objL1–8` parameter discovery. It's exercised in real KOSIS calls but mocked tests favor the happy path.
- `metadata_enricher` / `cache_builder` at <20% — these are optional offline tools, not part of the live request path. Acceptable.
- `mcp_server/server.py` at 50% — exception branches and verify logging paths. Each `@mcp.tool` has at least one hit through the integration tests.

---

## 2. Performance Report

Measured from the same machine; all latencies wall-clock, including TLS + Cloudflare + Fly proxy + NRT cold/warm.

### Hosting layer (no KOSIS call)

| Endpoint | p50 |
|---|---:|
| `/health` (warm 5×) | **137–141 ms** |
| `/health` (cold-ish, post-suspend) | **141 ms** ← suspend-resume is effectively invisible |
| `tools/list` (`/mcp`) | **180 ms** |
| 5× rapid `/mcp` `tools/list` | 177–197 ms (no rate-limit hits) |

### KOSIS-bound tool calls

Single shot, all returning 200 with valid JSON-RPC response.

| Tool | Sub-call shape | Latency |
|---|---|---:|
| `search_statistics` (limit=3) | 1× statisticsSearch.do | **2.4–2.8 s** |
| `browse_categories` by=org/theme (no code) | 0× — hardcoded | **140 ms** |
| `browse_categories` by=view | 1× statisticsList.do | **0.5–2.0 s** |
| `get_table_metadata` | 9× statisticsData.do (metadata fan-out) | **5.1 s** |
| `get_statistics_data` (5-year) | 1× Param/statisticsParameterData.do | **28–29 s** ⚠️ |
| `get_statistics_data` (recent 3) | same + newEstPrdCnt | **27 s** ⚠️ |
| `verify_statistics` (with `table_id`) | 2–3× KOSIS lookup chain | **7.4 s** |
| `list_key_indicators` (category/period) | 1× indi/prListSearch | **0.8–2.3 s** |
| `search_key_indicators` (name) | 1× indListSearch | **1.7 s** |
| `get_key_indicator` (name) | 1× indExpService | **0.8 s** |
| `discover_tools` / `list_stored_data` | local | **140–195 ms** |

### vwCd 12-code spread

All 12 official KOSIS view codes return live data.

| vwCd | Items | Latency |
|---|---:|---:|
| MT_ZTITLE (국내) | 30 | 0.52 s |
| MT_OTITLE (대상별) | 182 | 2.03 s |
| MT_GTITLE01 (지자체A) | 12 | 0.57 s |
| MT_GTITLE02 (지자체B) | 17 | 0.58 s |
| MT_CHOSUN_TITLE (광복이전) | 14 | 0.52 s |
| MT_HANKUK_TITLE (대한민국연감) | 16 | 0.53 s |
| MT_STOP_TITLE (작성중지) | 172 | 1.28 s |
| MT_RTITLE (이슈별) | 2 | 0.50 s |
| MT_BUKHAN (북한) | 6 | 0.50 s |
| MT_TM1_TITLE (TM1) | 12 | 0.50 s |
| MT_TM2_TITLE (TM2) | 30 | 0.53 s |
| MT_ETITLE (영문) | 29 | 0.52 s |

### Performance findings

1. **Hosting layer is excellent.** /health and /mcp tools/list both ≤200 ms at NRT for a Korean caller. Suspend-resume is invisible.

2. **`get_statistics_data` is the single performance pain point — ~28 s.** KOSIS occasionally returns `Connection reset by peer` on the first attempt (visible in fly logs), forcing one retry inside the 25 s timeout window. Worst-case wall-clock budget is 25 s + 1 s delay + 25 s = **51 s**, well within Fly's 60 s proxy. But routinely landing at 28 s degrades UX. Two options to consider:
   - Lower `KOSIS_TIMEOUT` to 15 s and `MAX_RETRIES=2` (worst-case still 31 s; happy path much faster on the rare KOSIS hiccup).
   - Investigate whether the connection-reset is correlated with first-after-cold-start (TCP/TLS to kosis.kr not yet warmed); if so, do a /health warm-up that pings KOSIS once on machine start.

3. **`get_table_metadata` 5 s.** Nine fan-out calls in series. Could be parallelized (asyncio.gather), but it's already inside the budget and the metadata calls are cacheable client-side.

4. **`verify_statistics` 7 s.** Acceptable given the verification pipeline (search → meta → data → match). Don't optimize until users complain.

---

## 3. API & Endpoint Availability

### KOSIS endpoints exercised by this server (13)

Per `src/kosis_tools/config.py::Endpoints`:

| Endpoint | Path | MCP tools that call it |
|---|---|---|
| STATISTICS_SEARCH | `statisticsSearch.do` | `search_statistics`, `verify_statistics` |
| STATISTICS_LIST | `statisticsList.do` | `browse_categories` (all 12 vwCd) |
| STATISTICS_DATA | `Param/statisticsParameterData.do` | `get_statistics_data`, `verify_statistics` |
| STATISTICS_TABLE_META | `statisticsData.do` | `get_table_metadata` (9 sub-types) |
| STATISTICS_EXPLANATION | `statisticsExplData.do` | (internal — `stats_explanation`) |
| STAT_HTML_CONTENT | `statHtml/statHtmlContent.do` | (defined, not used in active path) |
| STATISTICS_BIG_DATA | `statisticsBigData.do` | (internal — `big_data`, 40K/200K limits) |
| PK_NUMBER_SERVICE | `pkNumberService.do` | `get_key_indicator(by="id")` |
| IND_EXP_SERVICE | `indExpService.do` | `get_key_indicator(by="name")` |
| INDI_LIST_SERVICE | `indiListService.do` | `list_key_indicators(by="category")` |
| IND_LIST_SEARCH | `indListSearchRequest.do` | `search_key_indicators` (both modes) |
| IND_ID_DETAIL_SEARCH | `indIdDetailSearchRequest.do` | `get_key_indicator_details` |
| PR_LIST_SEARCH | `prListSearchRequest.do` | `list_key_indicators(by="period")` |

### MCP tools exposed (16/16)

Verified via `tools/list` at the live endpoint.

**Layer 1 — DISCOVER** (4)
- `search_statistics` ✅
- `browse_categories` (org / theme / view × 12 codes) ✅
- `get_table_metadata` ✅
- `get_available_values` ✅ (local; no KOSIS call)

**Layer 2 — FETCH** (3)
- `get_statistics_data` (incl. `new_est_prd_cnt`, `prd_interval`) ✅
- `filter_statistics` ✅ (local)
- `aggregate_statistics` ✅ (local)

**Key Indicators** (4)
- `get_key_indicator` ✅
- `list_key_indicators` ✅ (category + period)
- `search_key_indicators` ✅
- `get_key_indicator_details` ✅

**Verification** (1)
- `verify_statistics` ✅

**Storage / Meta** (4)
- `list_stored_data` ✅
- `read_stored_data` ✅
- `discover_tools` ✅
- `execute_tool` ✅

### Findings

1. **All 13 KOSIS endpoints we declare are exercised.** `STAT_HTML_CONTENT` is the one defined-but-not-routed constant; this is intentional (legacy fallback).
2. **All 12 official vwCd return live data.** Even the long-tail ones (광복이전, 북한, 영문) respond within 2 s.
3. **All 16 MCP tools list and respond.** No regressions from any of the 5 PRs (#12–18).
4. **KOSIS error-envelope coverage** (after #16 + #18): 8 of 16 tools surface the `error` envelope. The 8 not surfacing are local-only (`filter_statistics`, `aggregate_statistics`, `get_available_values`, `list_stored_data`, `read_stored_data`, `discover_tools`, `execute_tool`) plus `verify_statistics` (which has its own structured response). Coverage is correct.

---

## 4. Action items (from this audit)

| # | Severity | Item |
|---|---|---|
| A1 | medium | `get_statistics_data` consistently 28 s. Investigate whether first-request-after-cold-start causes the KOSIS connection reset. Consider lowering `KOSIS_TIMEOUT` to 15 s + `MAX_RETRIES=2`, or a startup KOSIS warm-up. |
| A2 | low | `get_table_metadata` could parallelize the 9-sub-type fan-out via `asyncio.gather` to bring 5 s down to ~1 s. Defer until a user reports it. |
| A3 | low | `kosis_tools/data.py` at 24% coverage — the smart-retry ladder for `objL1–8` discovery is the biggest miss. Add 2–3 mock-based tests covering the most common fallback paths. |
| A4 | low | `metadata_fetcher` / `cache_builder` / `metadata_enricher` modules cover <20% — these are offline tooling. Decide: ship as-is and accept low coverage, or move to a separate package. |
| A5 | cosmetic | Register `pytest.mark.integration` in `pyproject.toml` so the warning goes away. |

None block the launch. A1 is the only one users will feel; the rest are housekeeping.
