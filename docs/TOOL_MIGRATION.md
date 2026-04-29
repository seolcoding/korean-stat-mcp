# Tool Surface Migration (US-003)

## 기존 25개 도구 → V1 노출 15개

### KO

`korean-stat-mcp`는 LLM 클라이언트가 가장 자주 쓰는 15개 도구만 기본
노출하고, 나머지 내부 도구는 `execute_tool(name, args)` 한 곳으로 모아
숨깁니다. 이렇게 하면 LLM의 도구 선택 정확도가 올라가고, 프롬프트에
실리는 도구 스키마 토큰이 줄어듭니다.

> 단일 진실 공급원: `src/mcp_server/exposed_tools.py`의 `V1_EXPOSED`.

### EN

`korean-stat-mcp` exposes only the 15 most useful tools to LLM clients
by default; the rest stay reachable through a single `execute_tool(name, args)`
escape hatch. Result: better tool-selection accuracy and fewer schema tokens
in the prompt.

> Single source of truth: `V1_EXPOSED` in `src/mcp_server/exposed_tools.py`.

---

## Tool Mapping Table

| #  | Tool name              | Exposed | Layer    | Purpose (KO)                               | Purpose (EN)                                 |
|----|------------------------|:-------:|----------|--------------------------------------------|----------------------------------------------|
| 1  | search_statistics      | YES     | DISCOVER | 키워드로 KOSIS 통계표 검색                  | Keyword search across KOSIS tables           |
| 2  | browse_categories      | YES     | DISCOVER | 기관/주제별 통계 카테고리 탐색              | Browse stats by org / subject category       |
| 3  | get_table_metadata     | YES     | DISCOVER | 통계표 상세 메타데이터 조회                 | Fetch detailed table metadata                |
| 4  | get_available_values   | YES     | DISCOVER | 필터링 가능한 분류 값 조회                  | List filterable classification values        |
| 5  | get_statistics_data    | YES     | FETCH    | 통계 데이터 조회 (요약 반환)                | Fetch data (summary returned)                |
| 6  | filter_statistics      | YES     | FETCH    | 저장된 데이터에 필터 적용                   | Filter stored data                           |
| 7  | aggregate_statistics   | YES     | FETCH    | 데이터 그룹/집계 연산                       | Group / aggregate stored data                |
| 8  | execute_visualization  | YES     | PRESENT  | Altair 차트 생성                            | Generate Altair charts                       |
| 9  | execute_analysis       | YES     | PRESENT  | 통계 분석 (변화율, CAGR 등)                 | Statistical analysis helpers                 |
| 10 | execute_table          | YES     | PRESENT  | 스타일 적용된 HTML 테이블 생성              | Render styled HTML tables                    |
| 11 | execute_report         | YES     | PRESENT  | 종합 리포트 생성 (차트+분석+테이블)         | Composite report builder                     |
| 12 | list_stored_data       | YES     | DATA     | 저장된 데이터 파일 목록                     | List server-stored artifacts                 |
| 13 | read_stored_data       | YES     | DATA     | 저장된 원본 데이터 청크 읽기                | Read stored raw data in chunks               |
| 14 | discover_tools         | YES     | META     | 노출/내부 도구 전체 목록 조회               | List all exposed and internal tools          |
| 15 | execute_tool           | YES     | META     | 이름으로 임의 도구 호출 (escape hatch)      | Invoke any registered tool by name           |
| 16 | execute_code           | hidden  | -        | 범용 Python 코드 실행 (4 specialized 권장)  | Generic Python exec (use specialized 4)      |
| 17 | analyze_trend          | hidden  | -        | 사전 정의 추세 분석 (legacy)                | Pre-baked trend analysis (legacy)            |
| 18 | analyze_comparison     | hidden  | -        | 사전 정의 비교 분석 (legacy)                | Pre-baked comparison analysis (legacy)       |
| 19 | analyze_ranking        | hidden  | -        | 사전 정의 순위 분석 (legacy)                | Pre-baked ranking analysis (legacy)          |
| 20 | create_quick_report    | hidden  | -        | 빠른 HTML 리포트 (legacy)                   | Quick HTML report (legacy)                   |
| 21 | get_executor_guide     | hidden  | -        | executor 사용법 가이드                      | Executor usage guide                         |
| 22 | get_report_templates   | hidden  | -        | 리포트 템플릿 목록                          | Report template catalog                      |
| 23 | get_template_guide     | hidden  | -        | 템플릿 단계별 가이드                        | Template step-by-step guide                  |
| 24 | get_element_guide      | hidden  | -        | 요소(차트/카드) 가이드                      | Element (chart/card) guide                   |
| 25 | recommend_template     | hidden  | -        | 데이터 기반 템플릿 추천                     | Data-driven template recommendation          |

> `verify_statistics` (US-005)가 추가되면 노출 도구는 16개가 됩니다.
> `verify_statistics` will be added in US-005, bumping the exposed count to 16.

---

## Power user 가이드 / Power user guide

### KO — 숨겨진 내부 도구를 호출하려면

1. `discover_tools()` 호출 → `internal[]` 배열에서 도구 이름 확인.
2. `execute_tool(name="execute_code", args={"code": "...", "data_id": "..."})` 형태로 호출.
3. 인자 검증은 시그니처 기반. 잘못된 키워드는 `error: invalid arguments` 응답.
4. 반환은 항상 `{"tool": <name>, "result": <value>}` 또는 `{"tool": <name>, "error": <msg>}`.

```json
{
  "tool": "execute_tool",
  "args": {
    "name": "create_quick_report",
    "args": {"data_id": "DT_1B040A3_2024", "title": "인구 리포트"}
  }
}
```

### EN — Calling hidden internal tools

1. Call `discover_tools()` → read names from `internal[]`.
2. Invoke as `execute_tool(name="execute_code", args={"code": "...", "data_id": "..."})`.
3. Argument validation is signature-based. Unknown kwargs return `error: invalid arguments`.
4. Response is always `{"tool": <name>, "result": <value>}` or `{"tool": <name>, "error": <msg>}`.

```json
{
  "tool": "execute_tool",
  "args": {
    "name": "create_quick_report",
    "args": {"data_id": "DT_1B040A3_2024", "title": "Population report"}
  }
}
```

---

## Implementation notes

- Filtering: `mcp.remove_tool(name)` is invoked at server-import time for every
  registered tool not in `V1_EXPOSED_NAMES`. The full pre-prune registry is
  snapshotted into `discover._FULL_REGISTRY` so `execute_tool` can still reach
  hidden tools.
- No tool implementation is removed or rewritten — only the public MCP
  `tools/list` response is trimmed.
- Tests: see `tests/unit/test_exposed_tools.py` for regression guards
  (count, schema completeness, `search_tables_hybrid` exclusion, etc.).
