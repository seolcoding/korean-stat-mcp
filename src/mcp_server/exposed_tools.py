"""Curated allow-list of MCP tools exposed to LLM clients.

Internal tools remain available via discover_tools() and execute_tool().
This list is the single source of truth for the public tool surface.

Layer taxonomy:
    DISCOVER  - Find / browse statistics tables
    FETCH     - Retrieve / filter / aggregate raw data
    PRESENT   - Visualize, analyze, tabulate, report
    DATA      - Inspect server-stored artifacts
    META      - Tool introspection (escape hatch)
    VERIFY    - Sanity-check numbers against the source (US-005, future)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExposedTool:
    name: str
    layer: str  # "DISCOVER" | "FETCH" | "PRESENT" | "VERIFY" | "DATA" | "META"
    purpose_ko: str
    purpose_en: str


V1_EXPOSED: tuple[ExposedTool, ...] = (
    # ---- DISCOVER -------------------------------------------------------
    ExposedTool(
        "search_statistics",
        "DISCOVER",
        "키워드로 KOSIS 통계표 검색",
        "Keyword search across KOSIS statistics tables",
    ),
    ExposedTool(
        "browse_categories",
        "DISCOVER",
        "기관/주제별 통계 카테고리 탐색",
        "Browse statistics by org / subject category",
    ),
    ExposedTool(
        "get_table_metadata",
        "DISCOVER",
        "통계표 상세 메타데이터 조회",
        "Fetch detailed metadata for a statistics table",
    ),
    ExposedTool(
        "get_available_values",
        "DISCOVER",
        "테이블의 필터링 가능한 분류 값 조회",
        "List filterable classification values for a table",
    ),
    # ---- FETCH ----------------------------------------------------------
    ExposedTool(
        "get_statistics_data",
        "FETCH",
        "통계 데이터 조회 (요약 반환, 원본은 서버 저장)",
        "Fetch statistics data (summary returned; raw stored server-side)",
    ),
    ExposedTool(
        "filter_statistics",
        "FETCH",
        "저장된 데이터에 필터 적용",
        "Apply filters to stored statistics data",
    ),
    ExposedTool(
        "aggregate_statistics",
        "FETCH",
        "저장된 데이터를 그룹/집계 연산",
        "Group and aggregate stored statistics data",
    ),
    # ---- PRESENT --------------------------------------------------------
    ExposedTool(
        "execute_visualization",
        "PRESENT",
        "Altair 차트 생성 (천 단위 포맷, 과학적 표기 금지)",
        "Generate Altair charts (thousands format, no scientific notation)",
    ),
    ExposedTool(
        "execute_analysis",
        "PRESENT",
        "통계 분석 (변화율, CAGR 등 헬퍼 포함)",
        "Statistical analysis (helpers for change-rate, CAGR, etc.)",
    ),
    ExposedTool(
        "execute_table",
        "PRESENT",
        "스타일이 적용된 HTML 테이블 생성",
        "Render styled HTML tables",
    ),
    ExposedTool(
        "execute_report",
        "PRESENT",
        "차트/분석/테이블을 결합한 종합 리포트 생성",
        "Build composite report combining charts, analysis, tables",
    ),
    # ---- DATA -----------------------------------------------------------
    ExposedTool(
        "list_stored_data",
        "DATA",
        "서버에 저장된 데이터 파일 목록",
        "List server-stored data artifacts",
    ),
    ExposedTool(
        "read_stored_data",
        "DATA",
        "저장된 원본 데이터 청크 단위로 읽기",
        "Read stored raw data in chunks",
    ),
    # ---- META -----------------------------------------------------------
    ExposedTool(
        "discover_tools",
        "META",
        "노출/내부 도구 전체 목록과 메타정보 조회",
        "List all exposed and internal tools with metadata",
    ),
    ExposedTool(
        "execute_tool",
        "META",
        "이름으로 임의의 등록된 도구 호출 (파워유저용)",
        "Invoke any registered tool by name (power-user escape hatch)",
    ),
    # ---- VERIFY ---------------------------------------------------------
    ExposedTool(
        "verify_statistics",
        "VERIFY",
        "LLM이 생성한 숫자 주장을 KOSIS 원본 데이터와 대조 검증",
        "Cross-check LLM-produced numeric claims against KOSIS source data",
    ),
)


V1_EXPOSED_NAMES: frozenset[str] = frozenset(t.name for t in V1_EXPOSED)
