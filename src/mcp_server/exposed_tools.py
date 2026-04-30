"""Curated allow-list of MCP tools exposed to LLM clients.

Internal tools remain available via discover_tools() and execute_tool().
This list is the single source of truth for the public tool surface.

Layer taxonomy:
    DISCOVER  - Find / browse statistics tables
    FETCH     - Retrieve / filter / aggregate raw data
    DATA      - Inspect server-stored artifacts
    META      - Tool introspection (escape hatch)
    VERIFY    - Sanity-check numbers against the source (US-005, future)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExposedTool:
    name: str
    layer: str  # "DISCOVER" | "FETCH" | "VERIFY" | "DATA" | "META"
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
    # ---- KEY INDICATORS / 통계주요지표 (KOSIS dev guide §2.7) -----------
    ExposedTool(
        "get_key_indicator",
        "DISCOVER",
        "통계주요지표 설명자료 조회 (id 또는 이름 기준)",
        "Get key-indicator explanation by id or name",
    ),
    ExposedTool(
        "list_key_indicators",
        "DISCOVER",
        "통계주요지표 카테고리·수록주기별 목록",
        "List key indicators by category or period",
    ),
    ExposedTool(
        "search_key_indicators",
        "DISCOVER",
        "통계주요지표 이름·고유번호 검색",
        "Search key indicators by name or id",
    ),
    ExposedTool(
        "get_key_indicator_details",
        "FETCH",
        "통계주요지표 시계열 상세 데이터",
        "Fetch key-indicator time-series details",
    ),
)


V1_EXPOSED_NAMES: frozenset[str] = frozenset(t.name for t in V1_EXPOSED)
