"""
KOSIS MCP Server.

FastMCP를 사용하여 KOSIS 도구들을 MCP 프로토콜로 노출합니다.

Usage (로컬 테스트):
    uv run fastmcp run src/kosis_tools/mcp_server.py

Usage (Claude Desktop 설치):
    fastmcp install claude-desktop src/kosis_tools/mcp_server.py

Usage (uvx 배포 후):
    uvx kosis-mcp
"""

from __future__ import annotations

import os
import logging
from typing import Any, Optional

from fastmcp import FastMCP

# KOSIS 도구 임포트 (절대 import 사용 - fastmcp 실행 호환)
from kosis_tools.search import StatisticsSearch
from kosis_tools.list_categories import CategoryList, OrgCode, ThemeCode
from kosis_tools.table_meta import TableMetadata
from kosis_tools.data import StatisticsData
from kosis_tools.transform import KosisTransformer, to_dataframe
from kosis_tools.report_tools import (
    ReportComponent,
    AnalysisResult,
    get_available_values,
    filter_data,
    aggregate_data,
    viz_line_trend,
    viz_bar_comparison,
    viz_kpi_card,
    viz_pie_composition,
    analyze_trend,
    analyze_comparison,
    analyze_ranking,
    analyze_stats,
    text_headline,
    text_summary,
    text_insight,
    text_data_note,
    layout_section,
    layout_card_grid,
    layout_table,
    assemble_report,
    quick_report,
    format_data_for_llm,
    save_raw_data,
    load_raw_data,
    list_saved_data,
)

logger = logging.getLogger(__name__)

# =============================================================================
# MCP 서버 초기화
# =============================================================================

mcp = FastMCP(
    name="KOSIS MCP Server",
    instructions="""
    KOSIS(국가통계포털) 데이터를 조회하고 분석하는 도구입니다.

    ## 워크플로우
    1. DISCOVER: search_statistics, list_organizations 등으로 데이터 탐색
    2. FETCH: get_statistics_data로 데이터 조회
    3. PRESENT: analyze_*, visualize_*, create_report로 분석/시각화

    ## 주요 도구
    - search_statistics: 키워드로 통계표 검색
    - get_statistics_data: 통계 데이터 조회
    - analyze_trend: 추세 분석
    - create_quick_report: 원클릭 리포트 생성

    ## 환경 변수
    - KOSIS_API_KEY: KOSIS OpenAPI 키 (필수)
    """,
)


# =============================================================================
# Layer 1: DISCOVER - 데이터 탐색 도구
# =============================================================================

@mcp.tool
def search_statistics(
    keyword: str,
    org_id: Optional[str] = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    KOSIS 통계표를 키워드로 검색합니다.

    Args:
        keyword: 검색 키워드 (예: "인구", "고용", "물가")
        org_id: 기관 ID로 필터링 (선택)
                "101"=통계청, "154"=고용노동부 등
        limit: 최대 결과 수 (기본 10)

    Returns:
        통계표 목록:
        [
            {
                "tbl_id": "DT_1B040A3",
                "tbl_nm": "행정구역별 인구수",
                "org_id": "101",
                "org_nm": "통계청",
                "start_prd": "1992",
                "end_prd": "2023",
                "prd_se": "Y"
            },
            ...
        ]

    Example:
        >>> tables = search_statistics("인구", org_id="101")
    """
    client = StatisticsSearch()
    results = client.search(keyword)

    if org_id:
        results = [r for r in results if r.get("ORG_ID") == org_id]

    normalized = []
    for r in results[:limit]:
        prd_de = r.get("PRD_DE", "")
        normalized.append({
            "tbl_id": r.get("TBL_ID", ""),
            "tbl_nm": r.get("TBL_NM", ""),
            "org_id": r.get("ORG_ID", ""),
            "org_nm": r.get("ORG_NM", ""),
            "start_prd": prd_de.split("~")[0].strip() if "~" in prd_de else prd_de,
            "end_prd": prd_de.split("~")[-1].strip() if "~" in prd_de else prd_de,
            "prd_se": r.get("PRD_SE", "Y"),
        })

    return normalized


@mcp.tool
def list_organizations() -> list[dict[str, str]]:
    """
    KOSIS에 등록된 통계 작성 기관 목록을 반환합니다.

    Returns:
        기관 목록:
        [
            {"code": "101", "name": "통계청"},
            {"code": "154", "name": "고용노동부"},
            ...
        ]
    """
    # OrgCode는 일반 클래스이므로 클래스 속성을 순회
    result = []
    for name in dir(OrgCode):
        if not name.startswith("_"):
            value = getattr(OrgCode, name)
            if isinstance(value, str):
                result.append({"code": value, "name": name})
    return result


@mcp.tool
def list_themes() -> list[dict[str, str]]:
    """
    KOSIS 통계 주제 분류 목록을 반환합니다.

    Returns:
        주제 목록:
        [
            {"code": "A", "name": "인구"},
            {"code": "B", "name": "노동"},
            ...
        ]
    """
    # ThemeCode는 일반 클래스이므로 클래스 속성을 순회
    result = []
    for name in dir(ThemeCode):
        if not name.startswith("_"):
            value = getattr(ThemeCode, name)
            if isinstance(value, str):
                result.append({"code": value, "name": name})
    return result


@mcp.tool
def list_statistics_by_org(org_id: str) -> list[dict[str, Any]]:
    """
    특정 기관의 통계 목록을 조회합니다.

    Args:
        org_id: 기관 코드 (예: "101"=통계청)

    Returns:
        해당 기관의 통계표 목록
    """
    client = CategoryList()
    return client.list_by_org(org_id)


@mcp.tool
def get_table_metadata(org_id: str, tbl_id: str) -> dict[str, Any]:
    """
    통계표의 메타데이터(구조, 분류항목, 기간 등)를 조회합니다.

    Args:
        org_id: 기관 ID (예: "101")
        tbl_id: 테이블 ID (예: "DT_1B040A3")

    Returns:
        메타데이터:
        {
            "tbl_nm": "행정구역별 인구수",
            "org_nm": "통계청",
            "dimensions": [
                {"id": "C1", "name": "행정구역별", "values": ["전국", "서울", ...]},
                ...
            ],
            "items": [{"id": "T1", "name": "인구수"}, ...],
            "prd_se": "Y",
            "start_prd": "1992",
            "end_prd": "2023"
        }
    """
    client = TableMetadata()
    raw_meta = client.get_metadata(org_id, tbl_id)

    if not raw_meta:
        return {}

    dimensions = []
    for key in ["OBJ_VAR", "OBJ_VAR_2", "OBJ_VAR_3"]:
        if key in raw_meta and raw_meta[key]:
            items = raw_meta[key]
            if isinstance(items, list) and len(items) > 0:
                dim_info = {
                    "id": key.replace("OBJ_VAR", "C").replace("_", ""),
                    "name": items[0].get("OBJ_NM", ""),
                    "values": [v.get("ITM_NM", "") for v in items],
                }
                dimensions.append(dim_info)

    items = []
    if "ITM_VAR" in raw_meta and raw_meta["ITM_VAR"]:
        for itm in raw_meta["ITM_VAR"]:
            items.append({
                "id": itm.get("ITM_ID", ""),
                "name": itm.get("ITM_NM", ""),
            })

    prd_de = raw_meta.get("PRD_DE", "")

    return {
        "tbl_id": tbl_id,
        "tbl_nm": raw_meta.get("TBL_NM", ""),
        "org_id": org_id,
        "org_nm": raw_meta.get("ORG_NM", ""),
        "prd_se": raw_meta.get("PRD_SE", "Y"),
        "start_prd": prd_de.split("~")[0].strip() if prd_de else "",
        "end_prd": prd_de.split("~")[-1].strip() if prd_de else "",
        "dimensions": dimensions,
        "items": items,
    }


# =============================================================================
# Layer 2: FETCH - 데이터 조회 도구
# =============================================================================

@mcp.tool
def get_statistics_data(
    org_id: str,
    tbl_id: str,
    start_period: str,
    end_period: str,
    period_type: str = "Y",
    view: str = "summary",
    chunk_index: int = 0,
    chunk_size: int = 50,
) -> dict[str, Any]:
    """
    KOSIS에서 통계 데이터를 조회합니다.

    ⚠️ MCP 패턴: 기본값(view="summary")은 요약만 반환하여 토큰을 절약합니다.
    전체 데이터가 필요하면 view="full"을 사용하세요.

    Args:
        org_id: 기관 ID (예: "101")
        tbl_id: 테이블 ID (예: "DT_1B040A3")
        start_period: 시작 기간 (예: "2019", "202301")
        end_period: 종료 기간 (예: "2023", "202312")
        period_type: 기간 유형 "Y"=연간, "M"=월간, "Q"=분기, "S"=반기
        view: 응답 형식 (토큰 효율성)
              - "summary": 메타데이터 + 집계 요약만 (기본, 권장)
              - "sample": 요약 + 최근 샘플 20건
              - "chunk": 특정 청크만 (chunk_index로 지정)
              - "full": 전체 데이터 (대용량 주의!)
        chunk_index: 청크 인덱스 (view="chunk" 시 사용)
        chunk_size: 청크 크기 (기본 50건)

    Returns:
        view에 따른 응답:
        - summary: {total_records, metadata, aggregations, statistics, available_views}
        - sample: {total_records, sample_count, data}
        - chunk: {chunk_index, chunk_size, total_chunks, data, has_more}
        - full: {total_records, data, warning}

    Example:
        >>> # 1. 요약 먼저 조회 (권장)
        >>> summary = get_statistics_data("101", "DT_1B040A3", "2020", "2023")
        >>> # 2. 필요시 샘플 확인
        >>> sample = get_statistics_data("101", "DT_1B040A3", "2020", "2023", view="sample")
        >>> # 3. 전체 데이터 필요시
        >>> full = get_statistics_data("101", "DT_1B040A3", "2020", "2023", view="full")
    """
    client = StatisticsData()
    records = client.get_data(
        org_id=org_id,
        tbl_id=tbl_id,
        start_date=start_period,
        end_date=end_period,
        prd_se=period_type,
    )

    if not records:
        return {"error": "데이터 없음", "total_records": 0}

    total = len(records)

    # ============================================
    # view="summary": 메타데이터 + 집계 요약만
    # ============================================
    if view == "summary":
        # 기간별 집계
        periods = sorted(set(r.get("PRD_DE", "") for r in records))
        regions = sorted(set(r.get("C1_NM", "") for r in records if r.get("C1_NM")))
        items = sorted(set(r.get("ITM_NM", "") for r in records if r.get("ITM_NM")))

        # 수치 통계
        values = []
        for r in records:
            try:
                v = float(r.get("DT", 0))
                values.append(v)
            except (ValueError, TypeError):
                pass

        stats = {}
        if values:
            stats = {
                "count": len(values),
                "sum": sum(values),
                "mean": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
            }

        return {
            "status": "summary",
            "total_records": total,
            "metadata": {
                "org_id": org_id,
                "tbl_id": tbl_id,
                "period_range": f"{start_period}~{end_period}",
                "period_type": period_type,
            },
            "dimensions": {
                "periods": periods,
                "regions": regions[:20],  # 최대 20개
                "regions_total": len(regions),
                "items": items,
            },
            "statistics": stats,
            "available_views": ["sample", "chunk", "full"],
            "hint": "상세 데이터가 필요하면 view='sample' 또는 view='chunk' 사용",
        }

    # ============================================
    # view="sample": 요약 + 최근 샘플
    # ============================================
    elif view == "sample":
        # 최근 기간 기준 샘플
        sample = sorted(records, key=lambda x: x.get("PRD_DE", ""), reverse=True)[:20]
        return {
            "status": "sample",
            "total_records": total,
            "sample_count": len(sample),
            "data": sample,
            "hint": "전체 데이터: view='full', 청크별: view='chunk'",
        }

    # ============================================
    # view="chunk": 페이지네이션
    # ============================================
    elif view == "chunk":
        total_chunks = (total + chunk_size - 1) // chunk_size
        start = chunk_index * chunk_size
        end = min(start + chunk_size, total)

        if chunk_index >= total_chunks:
            return {"error": f"청크 인덱스 초과: {chunk_index} >= {total_chunks}"}

        return {
            "status": "chunk",
            "chunk_index": chunk_index,
            "chunk_size": end - start,
            "total_chunks": total_chunks,
            "total_records": total,
            "data": records[start:end],
            "has_more": end < total,
            "next_hint": f"다음 청크: chunk_index={chunk_index + 1}" if end < total else None,
        }

    # ============================================
    # view="full": 전체 데이터 (주의!)
    # ============================================
    else:
        # 원본 데이터 파일 저장 (MCP 패턴)
        storage_info = save_raw_data(records)

        return {
            "status": "full",
            "warning": f"⚠️ 전체 {total}건 반환 - 토큰 사용량 주의",
            "total_records": total,
            "data": records,
            "storage": {
                "data_id": storage_info.get("data_id"),
                "hint": "나중에 read_stored_data로 다시 접근 가능",
            },
        }


@mcp.tool
def filter_statistics_data(
    data: list[dict[str, Any]],
    regions: Optional[list[str]] = None,
    periods: Optional[list[str]] = None,
    items: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """
    통계 데이터를 필터링합니다.

    Args:
        data: 원본 데이터 (get_statistics_data 결과)
        regions: 포함할 지역/분류 목록 (C1_NM 필드)
                 예: ["서울특별시", "부산광역시"]
        periods: 포함할 기간 목록 (PRD_DE 필드)
                 예: ["2022", "2023"]
        items: 포함할 항목 목록 (ITM_NM 필드)
               예: ["인구수", "세대수"]

    Returns:
        필터링된 데이터 리스트
    """
    return filter_data(data, regions=regions, periods=periods, items=items)


@mcp.tool
def aggregate_statistics_data(
    data: list[dict[str, Any]],
    group_by: str,
    agg_func: str = "sum",
) -> list[dict[str, Any]]:
    """
    통계 데이터를 그룹별로 집계합니다.

    Args:
        data: 원본 데이터
        group_by: 그룹핑 필드
                  예: "C1_NM" (지역별), "PRD_DE" (기간별)
        agg_func: 집계 함수
                  "sum", "mean", "min", "max", "count"

    Returns:
        집계된 데이터 리스트
    """
    return aggregate_data(data, group_by=group_by, agg_func=agg_func)


@mcp.tool
def get_data_summary(data: list[dict[str, Any]]) -> dict[str, Any]:
    """
    데이터의 요약 정보를 반환합니다 (LLM 컨텍스트용).

    대용량 데이터를 LLM 친화적 형태로 압축하여 반환합니다.
    원본 데이터는 서버에 저장되고 요약/샘플만 반환합니다 (MCP 패턴).

    Args:
        data: 통계 데이터

    Returns:
        데이터 요약:
        {
            "summary": {
                "total_records": 100,
                "periods": ["2020", "2021", "2022", "2023"],
                "regions": ["서울특별시", "부산광역시", ...],
                "items": ["인구수"]
            },
            "metadata": {...},
            "data_preview": [...],
            "pivot_summary": {...},
            "raw_data_file": {
                "data_id": "...",
                "file_path": "...",
                "access_hint": "load_raw_data('...')로 전체 데이터 접근"
            }
        }
    """
    return format_data_for_llm(data, max_rows=50, save_raw=True)


# =============================================================================
# Layer 3: PRESENT - 분석 도구
# =============================================================================

@mcp.tool
def analyze_data_trend(
    data: list[dict[str, Any]],
    group_by: Optional[str] = None,
) -> dict[str, Any]:
    """
    데이터의 추세를 분석합니다.

    Args:
        data: 분석할 데이터
        group_by: 그룹별 분석 필드 (선택)
                  예: "C1_NM" (지역별 추세)

    Returns:
        추세 분석 결과:
        {
            "type": "trend",
            "findings": ["서울: 4년간 -5.2% 감소 (연평균 -1.3%)"],
            "metrics": {
                "direction": "감소",
                "total_change_pct": -5.2,
                "cagr": -1.3
            },
            "interpretation": "지속적인 감소 추세..."
        }
    """
    result = analyze_trend(data, group_by=group_by)
    return {
        "type": result.type,
        "findings": result.findings,
        "metrics": result.metrics,
        "interpretation": result.interpretation,
    }


@mcp.tool
def analyze_data_comparison(
    data: list[dict[str, Any]],
    targets: Optional[list[str]] = None,
    period: Optional[str] = None,
) -> dict[str, Any]:
    """
    데이터 항목들을 비교 분석합니다.

    Args:
        data: 분석할 데이터
        targets: 비교 대상 목록 (예: ["서울특별시", "부산광역시"])
        period: 특정 기간으로 필터 (예: "2023")

    Returns:
        비교 분석 결과:
        {
            "type": "comparison",
            "findings": ["서울이 부산보다 2.8배 많음"],
            "metrics": {
                "max": {"name": "서울", "value": 9411211},
                "min": {"name": "부산", "value": 3314183},
                "gap": 6097028,
                "rankings": [...]
            }
        }
    """
    result = analyze_comparison(data, targets=targets, period=period)
    return {
        "type": result.type,
        "findings": result.findings,
        "metrics": result.metrics,
        "interpretation": result.interpretation,
    }


@mcp.tool
def analyze_data_ranking(
    data: list[dict[str, Any]],
    top_n: int = 10,
    period: Optional[str] = None,
) -> dict[str, Any]:
    """
    데이터의 순위를 분석합니다.

    Args:
        data: 분석할 데이터
        top_n: 상위 N개 (기본: 10)
        period: 특정 기간으로 필터 (선택)

    Returns:
        순위 분석 결과:
        {
            "type": "ranking",
            "findings": ["1위: 경기도 (13,639,666)"],
            "data": [{순위 테이블}],
            "metrics": {"top_1": {...}, "top_n": 10}
        }
    """
    result = analyze_ranking(data, top_n=top_n, period=period)
    return {
        "type": result.type,
        "findings": result.findings,
        "data": result.data,
        "metrics": result.metrics,
    }


@mcp.tool
def analyze_data_statistics(data: list[dict[str, Any]]) -> dict[str, Any]:
    """
    데이터의 기술 통계를 계산합니다.

    Args:
        data: 분석할 데이터

    Returns:
        통계 결과:
        {
            "type": "stats",
            "findings": ["평균: 3,456,789", "중앙값: 2,345,678"],
            "metrics": {
                "count": 100,
                "mean": 3456789,
                "std": 1234567,
                "min": 123456,
                "max": 9876543,
                "median": 2345678
            }
        }
    """
    result = analyze_stats(data)
    return {
        "type": result.type,
        "findings": result.findings,
        "metrics": result.metrics,
    }


# =============================================================================
# Layer 3: PRESENT - 리포트 생성 도구
# =============================================================================

@mcp.tool
def create_quick_report(
    data: list[dict[str, Any]],
    title: str = "데이터 분석 리포트",
    output_path: Optional[str] = None,
) -> str:
    """
    데이터를 자동 분석하여 HTML 리포트를 생성합니다.

    KPI 카드, 추이 차트, 비교 차트, 인사이트가 포함됩니다.

    Args:
        data: 통계 데이터
        title: 리포트 제목
        output_path: 저장 경로 (선택, None이면 HTML 반환)

    Returns:
        HTML 문자열 또는 저장된 파일 경로

    Example:
        >>> html = create_quick_report(data, "인구 분석", "report.html")
    """
    return quick_report(data, title=title, output_path=output_path)


@mcp.tool
def create_custom_report(
    data: list[dict[str, Any]],
    title: str,
    include_kpi: bool = True,
    include_trend_chart: bool = True,
    include_comparison_chart: bool = True,
    include_table: bool = True,
    include_insights: bool = True,
    output_path: Optional[str] = None,
) -> str:
    """
    커스텀 설정으로 HTML 리포트를 생성합니다.

    Args:
        data: 통계 데이터
        title: 리포트 제목
        include_kpi: KPI 카드 포함 여부
        include_trend_chart: 추이 차트 포함 여부
        include_comparison_chart: 비교 차트 포함 여부
        include_table: 데이터 테이블 포함 여부
        include_insights: 인사이트 포함 여부
        output_path: 저장 경로 (선택)

    Returns:
        HTML 문자열 또는 저장된 파일 경로
    """
    components = []

    # KPI 카드
    if include_kpi:
        kpi_cards = []

        # 총 데이터 수
        kpi_cards.append(viz_kpi_card(
            value=len(data),
            label="총 데이터",
            icon="📊"
        ))

        # 기간 수
        periods = get_available_values(data, "PRD_DE")
        if periods:
            kpi_cards.append(viz_kpi_card(
                value=len(periods),
                label=f"기간 ({periods[0]}~{periods[-1]})",
                icon="📅"
            ))

        # 분류 수
        regions = get_available_values(data, "C1_NM")
        if regions:
            kpi_cards.append(viz_kpi_card(
                value=len(regions),
                label="분류 항목",
                icon="📍"
            ))

        if kpi_cards:
            components.append(layout_card_grid(kpi_cards, columns=min(3, len(kpi_cards))))

    # 추이 차트
    if include_trend_chart:
        components.append(viz_line_trend(data, title="추이 분석"))

    # 비교 차트
    if include_comparison_chart:
        components.append(viz_bar_comparison(data, title="항목별 비교", top_n=10))

    # 인사이트
    if include_insights:
        trend_analysis = analyze_trend(data)
        components.append(text_insight(trend_analysis))

    # 테이블
    if include_table:
        components.append(layout_table(
            data[:20],
            columns=["PRD_DE", "C1_NM", "DT", "ITM_NM"],
            column_labels={"PRD_DE": "기간", "C1_NM": "분류", "DT": "값", "ITM_NM": "항목"}
        ))

    # 데이터 노트
    components.append(text_data_note(data))

    return assemble_report(
        components,
        title=title,
        output_path=output_path,
    )


# =============================================================================
# 유틸리티 도구
# =============================================================================

@mcp.tool
def get_available_field_values(
    data: list[dict[str, Any]],
    field: str,
) -> list[str]:
    """
    데이터에서 특정 필드의 사용 가능한 값 목록을 조회합니다.

    Args:
        data: 통계 데이터
        field: 필드명 (예: "C1_NM", "PRD_DE", "ITM_NM")

    Returns:
        고유값 리스트 (정렬됨)

    Example:
        >>> regions = get_available_field_values(data, "C1_NM")
        >>> ["강원도", "경기도", "경상남도", ...]
    """
    return get_available_values(data, field)


# =============================================================================
# Layer 4: DATA STORAGE - 저장된 데이터 관리 (MCP 패턴)
# =============================================================================

@mcp.tool
def read_stored_data(
    data_id: str,
    chunk_index: Optional[int] = None,
    chunk_size: int = 50,
) -> dict[str, Any]:
    """
    저장된 원본 데이터를 읽어옵니다.

    get_statistics_data(view="full")로 조회한 데이터는 자동으로 저장됩니다.
    이 도구로 저장된 데이터를 청크 단위로 다시 조회할 수 있습니다.

    Args:
        data_id: 데이터 ID (get_statistics_data 결과의 storage.data_id)
        chunk_index: 청크 인덱스 (None이면 전체 데이터)
        chunk_size: 청크 크기 (기본 50건)

    Returns:
        {
            "data_id": "20231213_abc12345",
            "meta": {테이블 메타데이터},
            "data": [데이터 레코드들],
            "chunk_info": {  # chunk_index 지정 시
                "chunk_index": 0,
                "chunk_size": 50,
                "total_chunks": 20,
                "has_more": True
            }
        }

    Example:
        >>> # 1. 먼저 전체 데이터 조회 (자동 저장됨)
        >>> result = get_statistics_data("101", "DT_1B040A3", "2020", "2023", view="full")
        >>> data_id = result["storage"]["data_id"]
        >>>
        >>> # 2. 나중에 저장된 데이터 청크별 읽기
        >>> chunk = read_stored_data(data_id, chunk_index=0)
    """
    return load_raw_data(data_id, chunk_index=chunk_index, chunk_size=chunk_size)


@mcp.tool
def list_stored_data() -> list[dict[str, Any]]:
    """
    저장된 데이터 파일 목록을 조회합니다.

    get_statistics_data(view="full")로 조회한 데이터 목록을 반환합니다.
    이 목록에서 data_id를 확인하여 read_stored_data로 다시 접근할 수 있습니다.

    Returns:
        [
            {
                "data_id": "20231213_abc12345",
                "file_path": "/tmp/kosis_data/20231213_abc12345.json",
                "file_size_kb": 256.5,
                "record_count": 1000,
                "created_at": "2023-12-13T10:30:00",
                "tbl_id": "DT_1B040A3",
                "tbl_nm": "행정구역별 인구수"
            },
            ...
        ]

    Example:
        >>> # 저장된 데이터 목록 확인
        >>> stored = list_stored_data()
        >>> for item in stored:
        ...     print(f"{item['tbl_nm']}: {item['record_count']}건")
    """
    return list_saved_data()


# =============================================================================
# 서버 실행
# =============================================================================

if __name__ == "__main__":
    mcp.run()
