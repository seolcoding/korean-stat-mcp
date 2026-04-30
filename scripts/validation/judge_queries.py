"""20 user-style queries with expected tool routing.

Each query: a Korean OR English question a user might ask. The expected
first tool is what the LLM should call FIRST given only the routing manual
and the V1_EXPOSED tool list. Subsequent tools may vary; the judge only
scores the first-call decision.

Tool name policy
----------------
``expected_first_tool`` always uses a name from ``V1_EXPOSED_NAMES``.
The bilingual routing manual contains a few legacy names
(``search_statistics_tables``, ``browse_by_organization``, ``browse_by_theme``)
that the judge prompt rewrites onto their V1 equivalents
(``search_statistics``, ``browse_categories``) before scoring, so the
expectations here remain the canonical V1 surface.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JudgeCase:
    id: str
    lang: str  # "ko" | "en"
    query: str
    expected_first_tool: str
    rationale: str  # 1-line explanation; not shown to the LLM


CASES: tuple[JudgeCase, ...] = (
    # --- DISCOVER: search_statistics (4) ---------------------------------
    JudgeCase(
        "c01",
        "ko",
        "서울 인구 추이 보고싶어",
        "search_statistics",
        "User has a topic but no tblId — first step is finding the right table",
    ),
    JudgeCase(
        "c02",
        "en",
        "Show me Korea's quarterly unemployment rate trend",
        "search_statistics",
        "Topic-only query; need to locate the unemployment table first",
    ),
    JudgeCase(
        "c03",
        "ko",
        "최근 5년 GDP 변화율 알려줘",
        "search_statistics",
        "No tblId provided; start with table discovery",
    ),
    JudgeCase(
        "c04",
        "en",
        "What KOSIS tables exist about household debt?",
        "search_statistics",
        "Explicit table search by keyword",
    ),
    # --- DISCOVER: browse_categories (1) ---------------------------------
    JudgeCase(
        "c05",
        "ko",
        "통계청에서 발표하는 통계 목록 전체 둘러보고 싶어",
        "browse_categories",
        "Browsing by organization rather than keyword search",
    ),
    # --- DISCOVER: get_table_metadata (2) --------------------------------
    JudgeCase(
        "c06",
        "ko",
        "테이블 orgId=101, tblId=DT_1B040A3 의 상세 메타데이터 알려줘",
        "get_table_metadata",
        "User already has org/tbl ids and wants table-level metadata",
    ),
    JudgeCase(
        "c07",
        "en",
        "Give me the detailed metadata (publisher, update cycle, units) for table 101/DT_1B040A3",
        "get_table_metadata",
        "Explicit metadata request for a known table id",
    ),
    # --- DISCOVER: get_available_values (1) ------------------------------
    JudgeCase(
        "c08",
        "en",
        "For table 101/DT_1B040A3, what classification values (regions, items) can I filter on?",
        "get_available_values",
        "User wants the filterable dimension values of a known table",
    ),
    # --- FETCH: get_statistics_data (4) ----------------------------------
    JudgeCase(
        "c09",
        "ko",
        "테이블 orgId=101, tblId=DT_1B040A3 에서 2020~2023 데이터 가져와줘",
        "get_statistics_data",
        "User has tblId and a period range — go straight to data fetch",
    ),
    JudgeCase(
        "c10",
        "en",
        "Fetch the 2024 monthly CPI data from table 101/DT_1J17001",
        "get_statistics_data",
        "Direct data fetch with known table and period",
    ),
    JudgeCase(
        "c11",
        "ko",
        "이 통계표(orgId=101, tblId=DT_1IN1502)의 2024Q1 분기 데이터 좀 받아줘",
        "get_statistics_data",
        "Quarterly fetch with table id provided",
    ),
    JudgeCase(
        "c12",
        "en",
        "Pull the latest available value from table 101/DT_1B040A3 for the whole country",
        "get_statistics_data",
        "Latest-data fetch, table id provided",
    ),
    # --- FETCH: filter_statistics (1) ------------------------------------
    JudgeCase(
        "c13",
        "ko",
        "방금 받은 데이터(resource_id=ds_001) 에서 서울만 필터링해줘",
        "filter_statistics",
        "Stored resource_id present; pure server-side filter",
    ),
    # --- FETCH: aggregate_statistics (1) ---------------------------------
    JudgeCase(
        "c14",
        "en",
        "Group the stored dataset (resource_id=ds_001) by region and sum the values",
        "aggregate_statistics",
        "Stored data + group/agg request",
    ),
    # --- PRESENT: execute_visualization (2) ------------------------------
    JudgeCase(
        "c15",
        "en",
        "I already have ds_002 loaded — draw a line chart of population by year",
        "execute_visualization",
        "Stored data + explicit chart request",
    ),
    JudgeCase(
        "c16",
        "ko",
        "ds_003 데이터로 지역별 막대 차트 만들어줘",
        "execute_visualization",
        "Stored data + chart request (bar)",
    ),
    # --- PRESENT: execute_analysis (1) -----------------------------------
    JudgeCase(
        "c17",
        "ko",
        "ds_004 데이터의 2019→2023 변화율과 CAGR 계산해줘",
        "execute_analysis",
        "Numeric analysis (change-rate / CAGR) on stored data",
    ),
    # --- PRESENT: execute_report (1) -------------------------------------
    JudgeCase(
        "c18",
        "en",
        "Build a full HTML report (chart + analysis + table) from stored ds_005 about national population",
        "execute_report",
        "Composite report request — chart + analysis + table",
    ),
    # --- VERIFY: verify_statistics (2) -----------------------------------
    JudgeCase(
        "c19",
        "ko",
        "내가 '2023년 한국 총인구는 5,177만 명'이라고 썼는데 KOSIS 원본이랑 진짜 일치해?",
        "verify_statistics",
        "User wants a numeric claim cross-checked against KOSIS",
    ),
    JudgeCase(
        "c20",
        "en",
        "Are there other MCP tools available beyond the ones you've already shown me?",
        "discover_tools",
        "Meta question about the available tool surface",
    ),
)
