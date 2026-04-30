"""
KOSIS MCP Server - 한국 통계 데이터 MCP 서버.

이 서버는 KOSIS(국가통계포털) OpenAPI를 MCP 도구로 래핑하여
AI 에이전트가 한국 통계 데이터를 탐색, 조회, 시각화할 수 있게 합니다.

도구 구성:
    Layer 1 - DISCOVER: 데이터 탐색
    Layer 2 - FETCH: 데이터 조회
    Layer 3 - PRESENT: 시각화/리포트 생성

Example:
    # stdio 모드로 실행 (기본)
    python -m mcp_server

    # HTTP 모드로 실행
    fastmcp run src/mcp_server/server.py --transport http --port 8000
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Optional
from pathlib import Path

from fastmcp import FastMCP

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 아티팩트 설정
ARTIFACTS_DIR = os.environ.get("KOSIS_ARTIFACTS_DIR", "/tmp/kosis_artifacts")
BASE_URL = os.environ.get("KOSIS_BASE_URL", "http://localhost:8000")

# FastMCP 서버 생성 (json_response=True for standard MCP JSON responses)
mcp = FastMCP(
    name="kosis-stats",
    json_response=True,  # MCP 표준 JSON 응답 형식 사용
    instructions="""
    KOSIS(국가통계포털) 통계 데이터 서버입니다.

    사용 가능한 도구:

    🔍 DISCOVER (데이터 탐색):
    - search_statistics: 키워드로 통계표 검색
    - browse_categories: 기관/주제별 통계 목록
    - get_table_metadata: 테이블 상세 정보
    - get_available_values: 필터링 가능한 값 조회

    📥 FETCH (데이터 조회):
    - get_statistics_data: 통계 데이터 조회 (요약 반환, 원본은 파일 저장)
    - filter_statistics: 데이터 필터링
    - aggregate_statistics: 데이터 집계

    💻 CODE EXECUTION (코드 실행) ⭐ 권장:
    - execute_code: Python 코드를 서버에서 실행
      * 대용량 데이터 분석 시 토큰 98.7% 절감
      * pandas, altair, numpy 사용 가능
      * 시각화, 집계, 분석 등 자유롭게 코드 작성

    📊 PRESENT (미리 정의된 분석):
    - analyze_trend: 추세 분석
    - analyze_comparison: 비교 분석
    - analyze_ranking: 순위 분석
    - create_quick_report: HTML 리포트 생성

    💾 DATA ACCESS:
    - list_stored_data: 저장된 파일 목록
    - read_stored_data: 원본 데이터 읽기

    권장 워크플로우:
    1. search_statistics로 데이터 찾기
    2. get_statistics_data로 조회 (data_id 획득)
    3. execute_code로 분석/시각화 코드 실행 ← 핵심!
       예: execute_code('''
           df = prepare_data(data)
           chart = alt.Chart(df).mark_line()...
           return save_chart(chart, "result.html")
       ''', data_id="...")
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
) -> dict:
    """
    KOSIS 통계표를 키워드로 검색합니다.

    원하는 통계 데이터를 찾을 때 첫 번째로 사용하는 도구입니다.
    검색 결과에서 org_id와 tbl_id를 얻어 다음 단계에 사용합니다.

    Args:
        keyword: 검색 키워드 (예: "인구", "고용", "물가", "GDP")
        org_id: 기관 ID로 필터링 (선택)
                "101"=통계청, "154"=고용노동부, "301"=한국은행
        limit: 최대 결과 수 (기본 10)

    Returns:
        {
            "query": "인구",
            "result_count": 10,
            "results": [...],
            "org_distribution": {"통계청": 5, "한국은행": 3, ...},
            "next_step": "get_table_metadata(org_id, tbl_id)로 테이블 구조 확인"
        }

    Example:
        >>> search_statistics("인구")
        >>> search_statistics("고용", org_id="154")
    """
    from kosis_tools.report_tools import search_tables

    try:
        results = search_tables(keyword, org_id=org_id, limit=limit)

        # 기관별 분포 계산
        org_dist = {}
        for r in results:
            org_nm = r.get("org_nm", "기타")
            org_dist[org_nm] = org_dist.get(org_nm, 0) + 1

        return {
            "query": keyword,
            "filter": {"org_id": org_id} if org_id else None,
            "result_count": len(results),
            "results": results,
            "org_distribution": org_dist,
            "next_step": "get_table_metadata(org_id, tbl_id)로 테이블 구조를 확인하세요",
        }
    except Exception as e:
        logger.error(f"search_statistics error: {e}")
        return {"error": str(e)}


@mcp.tool
def browse_categories(
    by: str = "org",
    code: Optional[str] = None,
) -> dict:
    """
    기관별 또는 주제별로 통계 목록을 탐색합니다.

    특정 기관이나 주제 분야의 통계를 찾을 때 사용합니다.

    Args:
        by: 탐색 기준
            - "org": 기관별 (통계청, 고용노동부 등)
            - "theme": 주제별 (인구, 경제, 사회 등)
        code: 기관 코드 또는 주제 코드 (선택)
              None이면 전체 목록 반환

    Returns:
        {
            "browse_type": "org",
            "code": null,
            "count": 8,
            "categories": [...],
            "usage": "code를 지정하면 해당 카테고리의 통계표 목록 조회"
        }

    Example:
        >>> browse_categories(by="org")  # 전체 기관 목록
        >>> browse_categories(by="org", code="101")  # 통계청 통계 목록
        >>> browse_categories(by="theme")  # 주제 목록
    """
    from kosis_tools.report_tools import browse_categories as _browse

    try:
        results = _browse(by=by, code=code)

        # 응답 구조화
        response = {
            "browse_type": by,
            "code": code,
            "count": len(results),
        }

        if code:
            # 특정 카테고리의 통계표 목록
            response["statistics"] = results
            response["next_step"] = (
                "get_table_metadata(org_id, tbl_id)로 테이블 구조를 확인하세요"
            )
        else:
            # 카테고리 목록
            response["categories"] = results
            response["usage"] = (
                f"browse_categories(by='{by}', code='코드')로 해당 카테고리의 통계표 목록을 조회하세요"
            )

        return response
    except Exception as e:
        logger.error(f"browse_categories error: {e}")
        return {"error": str(e)}


@mcp.tool
def get_table_metadata(
    org_id: str,
    tbl_id: str,
) -> dict:
    """
    통계표의 메타데이터(구조 정보)를 조회합니다.

    테이블의 분류항목, 항목, 기간 정보를 파악할 때 사용합니다.
    데이터 조회 전에 어떤 필터가 가능한지 확인하는 데 유용합니다.

    Args:
        org_id: 기관 ID (예: "101")
        tbl_id: 테이블 ID (예: "DT_1B040A3")

    Returns:
        {
            "table_info": {
                "tbl_id": "DT_1B040A3",
                "tbl_nm": "행정구역별 인구수",
                "org_nm": "통계청",
                "prd_se": "Y",
                "period_range": "1992~2023"
            },
            "structure": {
                "dimensions": [...],
                "dimension_count": 1,
                "items": [...],
                "item_count": 1
            },
            "suggested_query": {
                "example": "get_statistics_data('101', 'DT_1B040A3', '2019', '2023')",
                "available_periods": "1992~2023"
            }
        }

    Example:
        >>> get_table_metadata("101", "DT_1B040A3")
    """
    from kosis_tools.report_tools import get_table_meta

    try:
        result = get_table_meta(org_id, tbl_id)
        # raw 필드 제거 (너무 큼)
        if "raw" in result:
            del result["raw"]

        # 응답 구조화
        response = {
            "table_info": {
                "tbl_id": result.get("tbl_id", tbl_id),
                "tbl_nm": result.get("tbl_nm", ""),
                "org_id": result.get("org_id", org_id),
                "org_nm": result.get("org_nm", ""),
                "prd_se": result.get("prd_se", "Y"),
                "period_range": f"{result.get('start_prd', '')}~{result.get('end_prd', '')}",
            },
            "structure": {
                "dimensions": result.get("dimensions", []),
                "dimension_count": len(result.get("dimensions", [])),
                "items": result.get("items", []),
                "item_count": len(result.get("items", [])),
            },
            "suggested_query": {
                "example": f"get_statistics_data('{org_id}', '{tbl_id}', '{result.get('start_prd', '2020')}', '{result.get('end_prd', '2023')}')",
                "prd_se_options": {"Y": "연간", "M": "월간", "Q": "분기", "S": "반기"},
            },
        }

        return response
    except Exception as e:
        logger.error(f"get_table_metadata error: {e}")
        return {"error": str(e)}


@mcp.tool
def get_available_values(
    data_json: str,
    field: str,
) -> dict:
    """
    데이터에서 특정 필드의 사용 가능한 값을 조회합니다.

    필터링 옵션을 확인하거나, 어떤 값으로 필터링할지 결정할 때 사용합니다.

    Args:
        data_json: KOSIS 데이터 JSON 문자열 (get_statistics_data 결과)
        field: 필드명 (예: "C1_NM", "PRD_DE", "ITM_NM")
               - C1_NM: 분류1 (보통 지역명)
               - PRD_DE: 기간
               - ITM_NM: 항목명

    Returns:
        {
            "field": "C1_NM",
            "field_description": "분류1 (지역/카테고리)",
            "count": 17,
            "values": ["강원도", "경기도", ...],
            "filter_example": "filter_statistics(data, regions='서울특별시,부산광역시')"
        }

    Example:
        >>> get_available_values(data, "C1_NM")
    """
    from kosis_tools.report_tools import get_available_values as _get_values

    try:
        data = json.loads(data_json)
        values = _get_values(data, field)

        # 필드 설명 매핑
        field_descriptions = {
            "C1_NM": "분류1 (지역/카테고리)",
            "C2_NM": "분류2 (세부분류)",
            "C3_NM": "분류3 (상세분류)",
            "PRD_DE": "기간 (연도/월)",
            "ITM_NM": "항목명 (측정 지표)",
            "DT": "데이터 값",
        }

        # 필터 예시 생성
        filter_examples = {
            "C1_NM": f"filter_statistics(data, regions='{values[0] if values else ''}')",
            "PRD_DE": f"filter_statistics(data, periods='{values[-1] if values else ''}')",
            "ITM_NM": f"filter_statistics(data, items='{values[0] if values else ''}')",
        }

        return {
            "field": field,
            "field_description": field_descriptions.get(field, field),
            "count": len(values),
            "values": values[:50] if len(values) > 50 else values,  # 최대 50개
            "truncated": len(values) > 50,
            "filter_example": filter_examples.get(
                field, "filter_statistics(data, ...)"
            ),
        }
    except Exception as e:
        logger.error(f"get_available_values error: {e}")
        return {"error": str(e)}


# =============================================================================
# Layer 2: FETCH - 데이터 조회 도구
# =============================================================================


@mcp.tool
def get_statistics_data(
    org_id: str,
    tbl_id: str,
    start_date: str,
    end_date: str,
    prd_se: str = "Y",
    format: str = "summary",
) -> dict | list[dict]:
    """
    KOSIS에서 통계 데이터를 조회합니다.

    search_statistics나 get_table_metadata로 확인한 테이블의
    실제 데이터를 가져옵니다.

    Args:
        org_id: 기관 ID (예: "101")
        tbl_id: 테이블 ID (예: "DT_1B040A3")
        start_date: 시작 기간 (예: "2019", "202301")
        end_date: 종료 기간 (예: "2023", "202312")
        prd_se: 기간 유형
                "Y"=연간, "M"=월간, "Q"=분기, "S"=반기
        format: 응답 형식
                "summary" (기본): LLM 친화적 요약 형식 (메타데이터 + 피벗 요약 + 샘플)
                "raw": 전체 원본 데이터 (주의: 컨텍스트 초과 가능)

    Returns:
        format="summary" (기본):
        {
            "summary": {
                "total_records": 850,
                "period_range": "2019~2023",
                "dimensions": ["행정구역별"],
                "items": ["인구수"]
            },
            "metadata": {
                "tbl_id": "DT_1B040A3",
                "tbl_nm": "행정구역별 인구수",
                "org_nm": "통계청",
                "unit": "명"
            },
            "pivot_summary": {
                "by_period": {"2019": 51849861, "2023": 51558034},
                "by_c1": {"경기도": 68123456, "서울특별시": 47056789, ...}
            },
            "data_preview": [최근 기간 샘플 50건],
            "available_values": {
                "PRD_DE": ["2019", "2020", "2021", "2022", "2023"],
                "C1_NM": ["서울특별시", "부산광역시", ...]
            }
        }

        format="raw": 전체 API 응답 (배열 형태)

    Example:
        >>> get_statistics_data("101", "DT_1B040A3", "2019", "2023")
        >>> get_statistics_data("101", "DT_1B040A3", "2019", "2023", format="raw")
    """
    from kosis_tools.report_tools import fetch_data, format_data_for_llm

    try:
        data = fetch_data(
            org_id=org_id,
            tbl_id=tbl_id,
            start_date=start_date,
            end_date=end_date,
            prd_se=prd_se,
        )

        if format == "raw":
            return data

        # 기본: LLM 친화적 요약 형식
        formatted = format_data_for_llm(data, max_rows=50)
        return formatted

    except Exception as e:
        logger.error(f"get_statistics_data error: {e}")
        return {"error": str(e)}


@mcp.tool
def filter_statistics(
    regions: Optional[str] = None,
    periods: Optional[str] = None,
    items: Optional[str] = None,
    format: str = "summary",
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> dict | list[dict]:
    """
    통계 데이터를 필터링합니다.

    서버에 저장된 데이터(data_id) 또는 직접 전달된 데이터(data_json)를 사용합니다.
    data_id 사용 시 LLM 컨텍스트에 데이터를 포함하지 않아 효율적입니다.

    Args:
        regions: 포함할 지역 목록 (쉼표 구분)
                 예: "서울특별시,부산광역시"
        periods: 포함할 기간 목록 (쉼표 구분)
                 예: "2022,2023"
        items: 포함할 항목 목록 (쉼표 구분)
               예: "인구수,세대수"
        format: 응답 형식 ("summary" 또는 "raw")
        data_id: 저장된 데이터 ID (get_statistics_data 결과에서 확인)
        data_json: KOSIS 데이터 JSON 문자열 (data_id 없을 때 사용)

    Returns:
        JSON 문자열: 필터링된 데이터 (summary 형식이면 요약 포함)

    Example:
        # 권장: data_id 사용 (서버에서 파일 읽음)
        >>> filter_statistics(regions="서울특별시,부산광역시", data_id="20231213_abc12345")

        # 대안: data_json 직접 전달
        >>> filter_statistics(regions="서울특별시,부산광역시", data_json=data)
    """
    from kosis_tools.report_tools import filter_data, format_data_for_llm, load_raw_data

    try:
        # data_id 우선 사용 (서버 사이드 처리)
        if data_id:
            loaded = load_raw_data(data_id)
            if "error" in loaded:
                return loaded
            data = loaded["data"]
        elif data_json:
            data = json.loads(data_json)
        else:
            return {"error": "data_id 또는 data_json 중 하나를 제공해야 합니다"}

        regions_list = [r.strip() for r in regions.split(",")] if regions else None
        periods_list = [p.strip() for p in periods.split(",")] if periods else None
        items_list = [i.strip() for i in items.split(",")] if items else None

        filtered = filter_data(
            data,
            regions=regions_list,
            periods=periods_list,
            items=items_list,
        )

        if format == "raw":
            return filtered

        # 기본: LLM 친화적 요약 형식 (필터 결과는 파일 저장 안 함)
        formatted = format_data_for_llm(filtered, max_rows=50, save_raw=False)
        return formatted

    except Exception as e:
        logger.error(f"filter_statistics error: {e}")
        return {"error": str(e)}


@mcp.tool
def aggregate_statistics(
    group_by: str,
    agg_func: str = "sum",
    format: str = "summary",
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> dict | list[dict]:
    """
    통계 데이터를 그룹별로 집계합니다.

    서버에 저장된 데이터(data_id) 또는 직접 전달된 데이터(data_json)를 사용합니다.
    data_id 사용 시 LLM 컨텍스트에 데이터를 포함하지 않아 효율적입니다.

    Args:
        group_by: 그룹핑 필드 (쉼표로 여러 개 가능)
                  예: "C1_NM" 또는 "C1_NM,PRD_DE"
        agg_func: 집계 함수
                  "sum", "mean", "min", "max", "count"
        format: 응답 형식 ("summary" 또는 "raw")
        data_id: 저장된 데이터 ID (get_statistics_data 결과에서 확인)
        data_json: KOSIS 데이터 JSON 문자열 (data_id 없을 때 사용)

    Returns:
        JSON 문자열: 집계된 데이터 (summary 형식이면 요약 포함)

    Example:
        # 권장: data_id 사용 (서버에서 파일 읽음)
        >>> aggregate_statistics(group_by="C1_NM", data_id="20231213_abc12345")

        # 대안: data_json 직접 전달
        >>> aggregate_statistics(group_by="C1_NM", data_json=data)
    """
    from kosis_tools.report_tools import (
        aggregate_data,
        format_data_for_llm,
        load_raw_data,
    )

    try:
        # data_id 우선 사용 (서버 사이드 처리)
        if data_id:
            loaded = load_raw_data(data_id)
            if "error" in loaded:
                return loaded
            data = loaded["data"]
        elif data_json:
            data = json.loads(data_json)
        else:
            return {"error": "data_id 또는 data_json 중 하나를 제공해야 합니다"}

        group_by_list = [g.strip() for g in group_by.split(",")]

        if len(group_by_list) == 1:
            group_by_list = group_by_list[0]

        aggregated = aggregate_data(data, group_by=group_by_list, agg_func=agg_func)

        if format == "raw":
            return aggregated

        # 기본: LLM 친화적 요약 형식
        formatted = format_data_for_llm(aggregated, max_rows=50, save_raw=False)
        return formatted

    except Exception as e:
        logger.error(f"aggregate_statistics error: {e}")
        return {"error": str(e)}


# =============================================================================
# Layer 3: PRESENT - 분석/시각화 도구
# =============================================================================


def _load_data_from_id_or_json(
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> tuple:
    """
    data_id 또는 data_json에서 데이터를 로드합니다.

    Returns:
        (data, error_response) - 성공 시 (data, None), 실패 시 (None, error_json)
    """
    from kosis_tools.report_tools import load_raw_data

    if data_id:
        loaded = load_raw_data(data_id)
        if "error" in loaded:
            return None, loaded
        return loaded["data"], None
    elif data_json:
        try:
            return json.loads(data_json), None
        except json.JSONDecodeError as e:
            return None, {"error": f"JSON 파싱 오류: {e}"}
    else:
        return None, {"error": "data_id 또는 data_json 중 하나를 제공해야 합니다"}


@mcp.tool
def analyze_trend(
    group_by: Optional[str] = None,
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> dict:
    """
    데이터의 추세를 분석합니다.

    서버에 저장된 데이터(data_id) 또는 직접 전달된 데이터(data_json)를 사용합니다.
    기간별 증감률, 방향, 연평균 성장률(CAGR) 등을 계산합니다.

    Args:
        group_by: 그룹별 분석 필드 (선택, 예: "C1_NM")
        data_id: 저장된 데이터 ID (get_statistics_data 결과에서 확인)
        data_json: KOSIS 데이터 JSON 문자열 (data_id 없을 때 사용)

    Returns:
        {
            "analysis_type": "trend",
            "summary": "전반적으로 감소 추세 (연평균 -1.3%)",
            "findings": [...],
            "metrics": {...},
            "visualization_suggestion": "viz_line_trend()로 시각화 권장"
        }

    Example:
        # 권장: data_id 사용
        >>> analyze_trend(data_id="20231213_abc12345")
        >>> analyze_trend(group_by="C1_NM", data_id="20231213_abc12345")
    """
    from kosis_tools.report_tools import analyze_trend as _analyze

    try:
        data, error = _load_data_from_id_or_json(data_id, data_json)
        if error:
            return error

        result = _analyze(data, group_by=group_by)

        # 요약 생성
        metrics = result.metrics
        if group_by and "groups" in metrics:
            groups = metrics.get("groups", {})
            summary = f"{len(groups)}개 그룹 분석 완료"
        else:
            direction = metrics.get("direction", "")
            cagr = metrics.get("cagr", 0)
            summary = (
                f"전반적으로 {direction} 추세 (연평균 {cagr:+.1f}%)"
                if direction
                else "추세 분석 완료"
            )

        return {
            "analysis_type": result.type,
            "summary": summary,
            "group_by": group_by,
            "findings": result.findings[:10],  # 최대 10개
            "metrics": result.metrics,
            "interpretation": result.interpretation,
            "visualization_suggestion": "create_quick_report()로 차트 포함 리포트 생성 가능",
        }
    except Exception as e:
        logger.error(f"analyze_trend error: {e}")
        return {"error": str(e)}


@mcp.tool
def analyze_comparison(
    targets: Optional[str] = None,
    period: Optional[str] = None,
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> dict:
    """
    데이터를 비교 분석합니다.

    서버에 저장된 데이터(data_id) 또는 직접 전달된 데이터(data_json)를 사용합니다.
    두 개 이상의 항목을 비교하여 차이와 비율을 계산합니다.

    Args:
        targets: 비교 대상 (쉼표 구분, 선택)
                 예: "서울특별시,부산광역시"
        period: 특정 기간으로 필터 (선택)
                예: "2023"
        data_id: 저장된 데이터 ID (get_statistics_data 결과에서 확인)
        data_json: KOSIS 데이터 JSON 문자열 (data_id 없을 때 사용)

    Returns:
        {
            "analysis_type": "comparison",
            "summary": "서울특별시가 1위, 최대-최소 격차 6,097,028",
            "comparison_targets": [...],
            "period": "2023",
            "findings": [...],
            "metrics": {...}
        }

    Example:
        # 권장: data_id 사용
        >>> analyze_comparison(targets="서울특별시,부산광역시", data_id="20231213_abc12345")
    """
    from kosis_tools.report_tools import analyze_comparison as _analyze

    try:
        data, error = _load_data_from_id_or_json(data_id, data_json)
        if error:
            return error

        targets_list = [t.strip() for t in targets.split(",")] if targets else None

        result = _analyze(data, targets=targets_list, period=period)

        # 요약 생성
        metrics = result.metrics
        max_info = metrics.get("max", {})
        gap = metrics.get("gap", 0)
        summary = f"{max_info.get('name', '')}가 1위" if max_info else "비교 분석 완료"
        if gap:
            summary += f", 최대-최소 격차 {gap:,.0f}"

        return {
            "analysis_type": result.type,
            "summary": summary,
            "comparison_targets": targets_list,
            "period": period,
            "compared_count": metrics.get("count", 0),
            "findings": result.findings,
            "metrics": {
                "top_1": metrics.get("max"),
                "bottom_1": metrics.get("min"),
                "gap": metrics.get("gap"),
                "rankings_preview": metrics.get("rankings", [])[:5],  # 상위 5개만
            },
            "interpretation": result.interpretation,
        }
    except Exception as e:
        logger.error(f"analyze_comparison error: {e}")
        return {"error": str(e)}


@mcp.tool
def analyze_ranking(
    top_n: int = 10,
    period: Optional[str] = None,
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> dict:
    """
    데이터의 순위를 분석합니다.

    서버에 저장된 데이터(data_id) 또는 직접 전달된 데이터(data_json)를 사용합니다.
    상위/하위 N개 항목을 추출하고 순위를 매깁니다.

    Args:
        top_n: 상위 N개 (기본 10)
        period: 특정 기간으로 필터 (선택)
        data_id: 저장된 데이터 ID (get_statistics_data 결과에서 확인)
        data_json: KOSIS 데이터 JSON 문자열 (data_id 없을 때 사용)

    Returns:
        {
            "analysis_type": "ranking",
            "summary": "1위 경기도, 상위 10개 분석",
            "period": "2023",
            "top_n": 10,
            "rankings": [{"rank": 1, "name": "경기도", "value": 13639666}, ...],
            "findings": [...]
        }

    Example:
        # 권장: data_id 사용
        >>> analyze_ranking(top_n=5, data_id="20231213_abc12345")
    """
    from kosis_tools.report_tools import analyze_ranking as _analyze

    try:
        data, error = _load_data_from_id_or_json(data_id, data_json)
        if error:
            return error

        result = _analyze(data, top_n=top_n, period=period)

        # 순위 데이터 정리 (간결하게)
        rankings = []
        for item in result.data[:top_n] if result.data else []:
            rankings.append(
                {
                    "rank": item.get("rank", 0),
                    "name": item.get("C1_NM", item.get("name", "")),
                    "value": item.get("DT", item.get("value", 0)),
                }
            )

        # 요약 생성
        top_1 = result.metrics.get("top_1", {})
        summary = (
            f"1위 {top_1.get('C1_NM', '')}, 상위 {top_n}개 분석"
            if top_1
            else f"상위 {top_n}개 순위 분석"
        )

        return {
            "analysis_type": result.type,
            "summary": summary,
            "period": result.metrics.get("period", period),
            "top_n": top_n,
            "total_count": result.metrics.get("total_count", 0),
            "rankings": rankings,
            "findings": result.findings[:5],  # 상위 5개 발견사항만
            "interpretation": result.interpretation,
        }
    except Exception as e:
        logger.error(f"analyze_ranking error: {e}")
        return {"error": str(e)}


@mcp.tool
def create_quick_report(
    title: str = "데이터 분석 리포트",
    output_path: Optional[str] = None,
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> dict:
    """
    데이터로 빠른 HTML 리포트를 생성합니다.

    서버에 저장된 데이터(data_id) 또는 직접 전달된 데이터(data_json)를 사용합니다.
    데이터만 넣으면 자동으로 KPI, 차트, 분석, 인사이트를 생성합니다.

    Args:
        title: 리포트 제목
        output_path: HTML 저장 경로 (선택)
                     None이면 상태 정보 반환
        data_id: 저장된 데이터 ID (get_statistics_data 결과에서 확인)
        data_json: KOSIS 데이터 JSON 문자열 (data_id 없을 때 사용)

    Returns:
        {
            "status": "success",
            "report_info": {
                "title": "인구 분석",
                "data_records": 850,
                "components": ["KPI 카드", "추이 차트", "비교 차트", "인사이트"]
            },
            "file_path": "report.html" (output_path 지정 시),
            "message": "..."
        }

    Example:
        # 권장: data_id 사용
        >>> create_quick_report(title="인구 분석", output_path="report.html", data_id="20231213_abc12345")
    """
    from kosis_tools.report_tools import quick_report, get_available_values

    try:
        data, error = _load_data_from_id_or_json(data_id, data_json)
        if error:
            return error

        # 리포트 생성
        result = quick_report(data, title=title, output_path=output_path)

        # 데이터 요약 정보
        periods = get_available_values(data, "PRD_DE")
        regions = get_available_values(data, "C1_NM")

        report_info = {
            "title": title,
            "data_records": len(data),
            "period_range": f"{periods[0]}~{periods[-1]}" if periods else "N/A",
            "region_count": len(regions),
            "components": [
                "KPI 카드 (3개)",
                "추이 라인 차트",
                "비교 막대 차트",
                "인사이트 박스",
                "데이터 출처",
            ],
        }

        if output_path:
            return {
                "status": "success",
                "report_info": report_info,
                "file_path": result,
                "message": f"HTML 리포트가 '{result}'에 저장되었습니다. 브라우저에서 열어 확인하세요.",
            }
        else:
            # output_path 없으면 저장 권장
            return {
                "status": "success",
                "report_info": report_info,
                "html_size": f"{len(result):,} bytes",
                "message": "HTML 리포트가 생성되었습니다. output_path를 지정하여 파일로 저장하세요.",
                "suggestion": "create_quick_report(data, title='제목', output_path='report.html')",
            }

    except Exception as e:
        logger.error(f"create_quick_report error: {e}")
        return {"error": str(e)}


# =============================================================================
# Layer 4: DATA ACCESS - 저장된 데이터 접근 도구
# =============================================================================


@mcp.tool
def list_stored_data() -> dict:
    """
    저장된 원본 데이터 파일 목록을 조회합니다.

    get_statistics_data로 조회한 대용량 데이터는 자동으로 파일에 저장됩니다.
    이 도구로 저장된 파일 목록을 확인하고, read_stored_data로 접근할 수 있습니다.

    Returns:
        {
            "stored_files": [
                {
                    "data_id": "20231213_abc12345",
                    "file_path": "/tmp/kosis_data/...",
                    "record_count": 1000,
                    "tbl_nm": "행정구역별 인구수",
                    "created_at": "2023-12-13T10:30:00"
                },
                ...
            ],
            "total_files": 5,
            "hint": "read_stored_data(data_id)로 데이터 접근"
        }

    Example:
        >>> list_stored_data()
    """
    from kosis_tools.report_tools import list_saved_data

    try:
        files = list_saved_data()
        return {
            "stored_files": files[:20],  # 최근 20개만
            "total_files": len(files),
            "hint": "read_stored_data(data_id)로 전체 데이터 접근, "
            "read_stored_data(data_id, chunk_index=0)로 청크별 접근",
        }
    except Exception as e:
        logger.error(f"list_stored_data error: {e}")
        return {"error": str(e)}


@mcp.tool
def read_stored_data(
    data_id: str,
    chunk_index: Optional[int] = None,
    chunk_size: int = 50,
) -> dict:
    """
    저장된 원본 데이터를 읽습니다.

    대용량 데이터는 청크 단위로 읽을 수 있습니다.
    chunk_index를 지정하지 않으면 전체 데이터를 반환합니다.

    Args:
        data_id: 데이터 ID (list_stored_data 또는 get_statistics_data에서 확인)
        chunk_index: 청크 인덱스 (0부터 시작, 선택)
        chunk_size: 청크 크기 (기본 50건)

    Returns:
        {
            "data_id": "20231213_abc12345",
            "meta": {
                "tbl_id": "DT_1B040A3",
                "tbl_nm": "행정구역별 인구수",
                "record_count": 1000
            },
            "data": [...],  # 요청한 데이터
            "chunk_info": {  # chunk_index 지정 시
                "chunk_index": 0,
                "chunk_size": 50,
                "total_chunks": 20,
                "has_more": True
            }
        }

    Example:
        # 전체 데이터 읽기
        >>> read_stored_data("20231213_abc12345")

        # 청크별로 읽기
        >>> read_stored_data("20231213_abc12345", chunk_index=0)
        >>> read_stored_data("20231213_abc12345", chunk_index=1)
    """
    from kosis_tools.report_tools import load_raw_data

    try:
        result = load_raw_data(data_id, chunk_index=chunk_index, chunk_size=chunk_size)

        if "error" in result:
            return result

        # 전체 데이터가 너무 크면 경고
        if chunk_index is None and len(result.get("data", [])) > 100:
            return {
                "warning": f"대용량 데이터 ({len(result['data'])}건). 청크별로 읽는 것을 권장합니다.",
                "data_id": data_id,
                "record_count": len(result.get("data", [])),
                "suggestion": f"read_stored_data('{data_id}', chunk_index=0)로 청크별 접근",
                "meta": result.get("meta", {}),
            }

        return result

    except Exception as e:
        logger.error(f"read_stored_data error: {e}")
        return {"error": str(e)}


# =============================================================================
# Layer 4: CODE EXECUTION - LLM 코드 실행
# =============================================================================


@mcp.tool
def execute_code(
    code: str,
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> dict:
    """
    Python 코드를 서버에서 실행합니다. 대용량 데이터 분석 시 토큰 98.7% 절감.

    사용 가능: pd, alt, np, prepare_data, save_chart, save_report, build_report

    빠른 시작:
        df = prepare_data(data, numeric_fields=["DT"])
        chart = alt.Chart(df).mark_line().encode(x='PRD_DE:N', y='DT:Q')
        return save_report(build_report("제목", [{"type":"chart","vega_spec":chart.to_dict()}]), "report")

    가이드: get_report_templates() → get_template_guide("trend") → get_element_guide("line_chart")

    품질 피드백: 실행 성공 시 quality_warnings 필드에 개선 제안이 포함될 수 있습니다.

    Args:
        code: Python 코드 (return 또는 마지막 표현식이 결과)
        data_id: 저장된 데이터 ID (get_statistics_data 결과)
        data_json: KOSIS 데이터 JSON (data_id 없을 때)
    """
    from kosis_tools.code_executor import execute_code as _execute

    try:
        # 데이터 로드
        data = None
        if data_id:
            from kosis_tools.report_tools import load_raw_data

            result = load_raw_data(data_id)
            if "error" not in result:
                data = result.get("data", [])
            else:
                return result
        elif data_json:
            data = json.loads(data_json) if isinstance(data_json, str) else data_json

        # 코드 실행
        result = _execute(code=code, data=data)

        # 검증 에러 시 클라이언트에게 명확한 피드백 제공
        if not result.get("success") and "validation_details" in result:
            validation = result["validation_details"]
            error_response = {
                "success": False,
                "error": "VISUALIZATION_VALIDATION_ERROR",
                "message": validation["message"],
                "issue_type": validation.get("issue_type"),
                "empty_charts": validation.get("empty_charts", []),
                "fix_hints": validation.get("fix_hints", []),
                "data_signature": validation.get("data_signature", {}),
                "action_required": "데이터 시그니처를 확인하고 시각화 코드를 수정해서 다시 실행하세요.",
                "code_example": """
# 올바른 코드 패턴 예시:
df = prepare_data(data, numeric_fields=["DT"])

# 필터링 전 데이터 확인
print(f"전체 레코드: {len(df)}")

# 빈 DataFrame 방지
if len(df) == 0:
    raise ValueError("필터링 후 데이터가 없습니다. 조건을 확인하세요.")

# 차트 생성
chart = alt.Chart(df).mark_line().encode(
    x='PRD_DE:N',
    y='DT:Q',
    color='C1_NM:N'
).properties(width=600, height=400)

# 차트 데이터 확인
spec = chart.to_dict()
if not spec.get("data", {}).get("values"):
    raise ValueError("차트 데이터가 비어있습니다.")

return save_report(build_report("리포트", [{"type": "chart", "vega_spec": spec}]), "report")
""",
            }
            return error_response

        return result

    except Exception as e:
        logger.error(f"execute_code error: {e}")
        # 오류 시 모범 사례/코드 템플릿 제공
        return {
            "success": False,
            "result": None,
            "stdout": "",
            "error": str(e),
            "code_templates": {
                "data_aggregation": """
# 데이터 집계 예시
df = prepare_data(data, numeric_fields=["DT"])
result = df.groupby("C1_NM")["DT"].sum().sort_values(ascending=False)
return result.head(10).to_dict()
""",
                "line_chart": """
# 라인 차트 예시
df = prepare_data(data, numeric_fields=["DT"])
chart = alt.Chart(df).mark_line(point=True).encode(
    x='PRD_DE:N',
    y='DT:Q',
    color='C1_NM:N'
).properties(title="추이", width=600, height=400)
return chart_to_json(chart)
""",
                "bar_chart": """
# 막대 차트 예시
df = prepare_data(data, numeric_fields=["DT"])
chart = alt.Chart(df).mark_bar().encode(
    x=alt.X('C1_NM:N', sort='-y'),
    y='DT:Q'
).properties(title="비교", width=600, height=400)
return save_chart(chart, "result.html")
""",
                "statistics": """
# 통계 분석 예시
df = prepare_data(data, numeric_fields=["DT"])
stats = {
    "count": len(df),
    "mean": df["DT"].mean(),
    "std": df["DT"].std(),
    "min": df["DT"].min(),
    "max": df["DT"].max()
}
return stats
""",
            },
            "available_modules": ["pd (pandas)", "alt (altair)", "np (numpy)"],
            "available_functions": [
                "prepare_data(data, numeric_fields=['DT']) → DataFrame",
                "save_chart(chart, filename) → {'path': ..., 'format': ...}",
                "chart_to_json(chart) → Vega-Lite JSON",
                "chart_to_html(chart, title) → HTML 문자열",
            ],
        }


# =============================================================================
# Layer 4.1: MODULAR EXECUTORS - 특화된 코드 실행
# =============================================================================


@mcp.tool
def execute_visualization(
    code: str,
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> dict:
    """
    시각화 코드를 실행합니다. 차트/그래프 생성에 특화.

    ## 필수 가이드라인 (자동 적용)
    - 숫자 단위: 천 명/천 원/천 개 (1,000 기준)
    - Y축 포맷: format=",.0f" 사용, 과학적 표기법 절대 금지
    - 축 제목: 단위 반드시 명시 (예: "인구 (천 명)")
    - 시리즈: 5개 이하 권장

    ## 예시
    ```python
    df = prepare_data(data, numeric_fields=["DT"])
    df["인구_천명"] = df["DT"] / 1000

    chart = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X("PRD_DE:N", title="연도"),
        y=alt.Y("인구_천명:Q", title="인구 (천 명)", axis=alt.Axis(format=",.0f")),
        color="C1_NM:N"
    ).properties(title="인구 추이", width=600, height=350)

    return save_chart(chart, "population.html")
    ```

    Args:
        code: Python 시각화 코드
        data_id: 저장된 데이터 ID
        data_json: KOSIS 데이터 JSON
    """
    from kosis_tools.executors.visualization import execute_visualization as _execute

    try:
        data = None
        if data_id:
            from kosis_tools.report_tools import load_raw_data

            result = load_raw_data(data_id)
            if "error" not in result:
                data = result.get("data", [])
            else:
                return result
        elif data_json:
            data = json.loads(data_json) if isinstance(data_json, str) else data_json

        result = _execute(code=code, data=data)
        return result

    except Exception as e:
        logger.error(f"execute_visualization error: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool
def execute_analysis(
    code: str,
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> dict:
    """
    데이터 분석 코드를 실행합니다. 통계/집계에 특화.

    ## 필수 가이드라인 (자동 적용)
    - KOSIS 결측치 처리: "-", "*", "" 자동 변환
    - 숫자 단위: 천 (1,000) 기준
    - 결과: 딕셔너리로 반환 (리포트에서 사용)

    ## 사용 가능 헬퍼
    - prepare_data(data, numeric_fields): 데이터 변환
    - calc_change_rate(current, previous): 증감률 (%)
    - calc_cagr(start, end, years): 연평균 성장률 (%)
    - calc_ratio(value, total): 구성비 (%)
    - to_thousand(value): 천 단위 변환

    ## 예시
    ```python
    df = prepare_data(data, numeric_fields=["DT"])

    total_2023 = df[df["PRD_DE"] == "2023"]["DT"].sum()
    total_2019 = df[df["PRD_DE"] == "2019"]["DT"].sum()

    return {
        "summary": {
            "total_2023": to_thousand(total_2023),
            "change_rate": calc_change_rate(total_2023, total_2019),
        },
        "insights": ["인구 감소 추세 지속", "수도권 집중 심화"]
    }
    ```

    Args:
        code: Python 분석 코드
        data_id: 저장된 데이터 ID
        data_json: KOSIS 데이터 JSON
    """
    from kosis_tools.executors.analysis import execute_analysis as _execute

    try:
        data = None
        if data_id:
            from kosis_tools.report_tools import load_raw_data

            result = load_raw_data(data_id)
            if "error" not in result:
                data = result.get("data", [])
            else:
                return result
        elif data_json:
            data = json.loads(data_json) if isinstance(data_json, str) else data_json

        result = _execute(code=code, data=data)
        return result

    except Exception as e:
        logger.error(f"execute_analysis error: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool
def execute_table(
    code: str,
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> dict:
    """
    테이블 생성 코드를 실행합니다. 예쁜 HTML 테이블 생성에 특화.

    ## 필수 가이드라인 (자동 적용)
    - 숫자 포맷: 천 단위 구분자 (12,345)
    - 컬럼명: 한글로 명확하게 (PRD_DE → 연도)
    - 단위 명시: 인구 (천 명)
    - 정렬: 숫자 우측, 텍스트 좌측 (자동)

    ## 예시
    ```python
    df = prepare_data(data, numeric_fields=["DT"])
    df["인구_천명"] = df["DT"] / 1000

    return create_table(
        df[["PRD_DE", "C1_NM", "인구_천명"]],
        title="연도별 지역별 인구",
        columns={"PRD_DE": "연도", "C1_NM": "지역", "인구_천명": "인구 (천 명)"},
        number_format={"인구 (천 명)": ",.0f"},
        max_rows=20,
    )
    ```

    Args:
        code: Python 테이블 생성 코드
        data_id: 저장된 데이터 ID
        data_json: KOSIS 데이터 JSON
    """
    from kosis_tools.executors.table import execute_table as _execute

    try:
        data = None
        if data_id:
            from kosis_tools.report_tools import load_raw_data

            result = load_raw_data(data_id)
            if "error" not in result:
                data = result.get("data", [])
            else:
                return result
        elif data_json:
            data = json.loads(data_json) if isinstance(data_json, str) else data_json

        result = _execute(code=code, data=data)
        return result

    except Exception as e:
        logger.error(f"execute_table error: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool
def execute_report(
    code: str,
    analysis_json: Optional[str] = None,
    charts_json: Optional[str] = None,
    tables_json: Optional[str] = None,
    data_id: Optional[str] = None,
) -> dict | str:
    """
    리포트 생성 코드를 실행합니다. 시각화+분석+테이블을 조합.

    ## 워크플로우
    1. execute_analysis → analysis 결과 획득
    2. execute_visualization → charts 결과 획득
    3. execute_table → tables 결과 획득
    4. execute_report → 위 결과들을 조합해서 리포트 생성

    ## 예시
    ```python
    return build_report(
        title="인구 분석 리포트",
        analysis=analysis,   # {"summary": {...}, "insights": [...]}
        charts=charts,       # [{"vega_spec": {...}, "title": "인구 추이"}]
        tables=tables,       # [{"html": "...", "title": "상세 데이터"}]
        source="통계청 KOSIS",
    )
    ```

    Args:
        code: Python 리포트 생성 코드
        analysis_json: 분석 결과 JSON (execute_analysis 출력)
        charts_json: 차트 목록 JSON (execute_visualization 출력들)
        tables_json: 테이블 목록 JSON (execute_table 출력들)
        data_id: 원본 데이터 ID (필요시)
    """
    from kosis_tools.executors.report import execute_report as _execute

    try:
        data = None
        if data_id:
            from kosis_tools.report_tools import load_raw_data

            result = load_raw_data(data_id)
            if "error" not in result:
                data = result.get("data", [])

        analysis = json.loads(analysis_json) if analysis_json else None
        charts = json.loads(charts_json) if charts_json else None
        tables = json.loads(tables_json) if tables_json else None

        result = _execute(
            code=code,
            data=data,
            analysis=analysis,
            charts=charts,
            tables=tables,
        )
        return result

    except Exception as e:
        logger.error(f"execute_report error: {e}")
        return {"success": False, "error": str(e)}


@mcp.tool
def get_executor_guide(executor_type: str) -> dict:
    """
    특화 실행기의 가이드라인을 조회합니다.

    Args:
        executor_type: 실행기 유형 (visualization, analysis, table, report)

    Returns:
        해당 실행기의 상세 가이드라인 및 예제
    """
    from kosis_tools.executors import (
        VISUALIZATION_GUIDE,
        ANALYSIS_GUIDE,
        TABLE_GUIDE,
        REPORT_GUIDE,
    )

    guides = {
        "visualization": VISUALIZATION_GUIDE,
        "analysis": ANALYSIS_GUIDE,
        "table": TABLE_GUIDE,
        "report": REPORT_GUIDE,
    }

    guide = guides.get(executor_type)
    if guide:
        return guide
    else:
        return {
            "error": f"알 수 없는 실행기 유형: {executor_type}",
            "available_types": list(guides.keys()),
        }


# =============================================================================
# Resources - 정적 데이터 리소스
# =============================================================================


@mcp.resource("kosis://regions")
def get_regions_resource() -> dict:
    """
    시도/시군구 코드 매핑 데이터.

    지역 코드와 이름 매핑 정보를 제공합니다.
    """
    # 주요 시도 코드
    regions = {
        "00": "전국",
        "11": "서울특별시",
        "21": "부산광역시",
        "22": "대구광역시",
        "23": "인천광역시",
        "24": "광주광역시",
        "25": "대전광역시",
        "26": "울산광역시",
        "29": "세종특별자치시",
        "31": "경기도",
        "32": "강원특별자치도",
        "33": "충청북도",
        "34": "충청남도",
        "35": "전라북도",
        "36": "전라남도",
        "37": "경상북도",
        "38": "경상남도",
        "39": "제주특별자치도",
    }
    return regions


@mcp.resource("kosis://org-codes")
def get_org_codes_resource() -> dict:
    """
    주요 기관 코드 목록.

    자주 사용하는 기관의 코드 정보를 제공합니다.
    """
    orgs = {
        "101": "통계청",
        "154": "고용노동부",
        "301": "한국은행",
        "350": "금융위원회",
        "117": "국토교통부",
        "106": "행정안전부",
        "138": "농림축산식품부",
        "118": "해양수산부",
    }
    return orgs


@mcp.resource("kosis://period-types")
def get_period_types_resource() -> dict:
    """
    기간 유형 코드 설명.

    KOSIS API의 기간 유형(prd_se) 코드를 설명합니다.
    """
    period_types = {
        "Y": "연간 (Annual)",
        "M": "월간 (Monthly)",
        "Q": "분기 (Quarterly)",
        "S": "반기 (Semi-annual)",
        "D": "일간 (Daily)",
    }
    return period_types


# =============================================================================
# 템플릿 가이드 도구 (토큰 효율적 계층 구조)
# =============================================================================


@mcp.tool
def get_report_templates() -> dict:
    """
    리포트 템플릿 목록 조회 (토큰 효율적).

    사용 가능한 템플릿 ID와 간략 설명만 반환합니다.
    상세 가이드는 get_template_guide(template_id)로 조회하세요.

    Returns:
        템플릿 목록 (ID, 이름, 용도, 섹션 수)
    """
    from kosis_tools.story_templates import get_template_list

    templates = get_template_list()
    return {
        "templates": templates,
        "usage": "상세 가이드: get_template_guide(template_id)",
    }


@mcp.tool
def get_template_guide(
    template_id: str,
    step: Optional[int] = None,
) -> dict:
    """
    템플릿 가이드 조회 (단계별 또는 전체).

    Args:
        template_id: 템플릿 ID (trend, compare, composition, correlation, dashboard, ranking)
        step: 특정 단계만 조회 (1부터 시작). None이면 전체 구조.

    Returns:
        단계별 가이드 (현재 단계 + 다음 예고 + 코드 힌트)
    """
    from kosis_tools.story_templates import (
        get_template_guide as _get_guide,
        get_template_step,
    )

    if step is not None:
        # 특정 단계만 반환 (토큰 절약)
        result = get_template_step(template_id, step)
        if not result:
            return {
                "error": f"템플릿 '{template_id}' 또는 단계 {step}을 찾을 수 없습니다."
            }
        return result
    else:
        # 전체 구조 반환
        result = _get_guide(template_id)
        if not result:
            return {"error": f"템플릿 '{template_id}'을 찾을 수 없습니다."}
        return result


@mcp.tool
def get_element_guide(element_type: str) -> dict:
    """
    특정 요소(차트, 카드 등)의 상세 가이드.

    Args:
        element_type: 요소 유형
            - "line_chart": 라인 차트
            - "bar_chart": 막대 차트
            - "donut_chart": 도넛 차트
            - "stat_cards": 통계 카드
            - "insight_box": 인사이트 박스

    Returns:
        해당 요소의 when/must_have/code/avoid 가이드
    """
    from kosis_tools.story_templates import get_element_guide as _get_element

    result = _get_element(element_type)
    return result


@mcp.tool
def recommend_template(data_id: Optional[str] = None) -> dict | None:
    """
    데이터 특성 기반 템플릿 추천.

    저장된 데이터의 시그니처를 분석하여 최적 템플릿을 추천합니다.

    Args:
        data_id: 저장된 데이터 ID (선택). 없으면 일반 가이드 반환.

    Returns:
        {"recommended": "trend", "reason": "...", "alternatives": [...]}
    """
    from kosis_tools.story_templates import recommend_template as _recommend

    if data_id:
        from kosis_tools.report_tools import load_raw_data

        result = load_raw_data(data_id)
        if "error" in result:
            return result

        data = result.get("data", [])
        # 데이터 시그니처 생성
        from kosis_tools.code_executor import CodeExecutor

        executor = CodeExecutor()
        signature = executor._generate_data_signature(data)
        recommendation = _recommend(signature)
        recommendation["data_signature_preview"] = {
            "fields": list(signature.get("fields", {}).keys()),
            "records": signature.get("total_records", 0),
        }
        return recommendation
    else:
        # 일반 가이드
        return {
            "tip": "data_id를 제공하면 데이터 기반 추천을 받을 수 있습니다.",
            "available_templates": [
                "trend",
                "compare",
                "composition",
                "correlation",
                "dashboard",
                "ranking",
            ],
            "default": "dashboard",
        }


# =============================================================================
# 템플릿 리소스 (상세 참조용)
# =============================================================================


@mcp.resource("kosis://templates")
def get_templates_resource() -> dict:
    """
    리포트 템플릿 전체 목록 (리소스).

    각 템플릿의 ID, 이름, 용도, 섹션 수를 제공합니다.
    """
    from kosis_tools.story_templates import get_template_list

    return get_template_list()


@mcp.resource("kosis://templates/trend")
def get_trend_template_resource() -> dict:
    """트렌드 분석 템플릿 상세."""
    from kosis_tools.story_templates import get_template_guide

    return get_template_guide("trend")


@mcp.resource("kosis://templates/compare")
def get_compare_template_resource() -> dict:
    """비교 분석 템플릿 상세."""
    from kosis_tools.story_templates import get_template_guide

    return get_template_guide("compare")


@mcp.resource("kosis://templates/dashboard")
def get_dashboard_template_resource() -> dict:
    """대시보드 템플릿 상세."""
    from kosis_tools.story_templates import get_template_guide

    return get_template_guide("dashboard")


@mcp.resource("kosis://guide/charts")
def get_chart_guide_resource() -> dict:
    """차트 선택 가이드."""
    from kosis_tools.story_templates import CHART_GUIDE

    return CHART_GUIDE


@mcp.resource("kosis://guide/visualization")
def get_visualization_guide_resource() -> dict:
    """시각화 상세 가이드라인 - execute_code 사용 시 참조."""
    guide = {
        "title": "KOSIS 시각화 가이드라인",
        "sections": {
            "number_formatting": {
                "rule": "큰 숫자는 반드시 천 단위 구분",
                "how": "alt.Axis(format=',') 또는 format=',.0f'",
                "example": "9411211 → '9,411,211'",
            },
            "axis_labels": {
                "rule": "명확한 한글 제목 + 단위",
                "examples": [
                    "alt.X('PRD_DE:N', title='연도')",
                    "alt.Y('DT:Q', title='인구 (명)', axis=alt.Axis(format=','))",
                ],
            },
            "chart_title": {
                "rule": "구체적이고 한눈에 파악 가능",
                "example": ".properties(title='2015-2023년 서울 vs 경기 인구 변화 추이')",
                "tip": "제목만 보고 무슨 데이터인지 알 수 있게!",
            },
            "colors": {
                "rule": "의미 있는 색상 스킴 사용",
                "categorical": "scale=alt.Scale(scheme='category10')",
                "sequential": "scale=alt.Scale(scheme='blues')",
                "tip": "대비가 명확하게!",
            },
            "legend": {
                "rule": "항상 표시, 위치 조정",
                "example": "color=alt.Color('지역:N', legend=alt.Legend(title='지역'))",
                "tip": "범례 제목은 한글로!",
            },
            "chart_size": {
                "rule": "충분히 크게",
                "default": ".properties(width=600, height=400)",
                "mobile": "width=500",
            },
            "tooltip": {
                "rule": "상세 정보 제공",
                "example": "tooltip=['지역', '연도', alt.Tooltip('인구:Q', format=',')]",
            },
            "insights": {
                "rule": "핵심 발견을 텍스트로 강조",
                "example": "build_insight_box('경기도가 서울을 추월했습니다!')",
            },
        },
        "report_guidelines": {
            "structure": "인사이트 먼저, 차트 나중에 (결론 → 근거)",
            "stats": "핵심 수치는 build_stat_cards로 크게 강조",
            "tables": "테이블은 10행 이내로 (to_table_html, max_rows=10)",
            "printable": "프린트 가능한 형태로 구성",
        },
        "available_helpers": {
            "data": "prepare_data(data, numeric_fields=['DT']) → DataFrame",
            "chart_save": "save_chart(chart, name) → {'url': ...}",
            "chart_json": "chart_to_json(chart) → Vega-Lite JSON",
            "chart_html": "chart_to_html(chart) → HTML 문자열",
            "report": "save_report(html, name) → {'url': ...}",
            "data_save": "save_data(data, name, format) → {'url': ...}",
            "table": "to_table_html(df, max_rows=10, title='') → HTML 테이블",
            "build": "build_report(title, sections) → 완성 HTML",
            "stats": "build_stat_cards([{label, value, unit}]) → 통계 카드",
            "insight": "build_insight_box(content, title) → 인사이트 박스",
            "quick": "quick_report(title, chart_specs, tables, insights) → 빠른 리포트",
        },
        "quality_feedback": {
            "description": "execute_code 실행 시 자동 품질 검사 수행",
            "checks": [
                "빈 데이터 배열 감지",
                "차트 제목 누락",
                "축 라벨 누락",
                "숫자 포맷 누락",
                "너무 많은 시리즈/카테고리",
                "인사이트 누락",
                "데이터 출처 누락",
            ],
            "response_field": "quality_warnings, quality_summary",
        },
    }
    return guide


@mcp.resource("kosis://guide/code-patterns")
def get_code_patterns_resource() -> dict:
    """코드 패턴 예시 - 복사-붙여넣기 가능한 템플릿."""
    patterns = {
        "line_chart": """# 라인 차트 (트렌드)
df = prepare_data(data, numeric_fields=["DT"])
chart = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X('PRD_DE:N', title='연도'),
    y=alt.Y('DT:Q', title='값', axis=alt.Axis(format=',')),
    color=alt.Color('C1_NM:N', title='분류'),
    tooltip=['PRD_DE', 'C1_NM', alt.Tooltip('DT:Q', format=',')]
).properties(title='추이 분석', width=600, height=400)
return save_chart(chart, "trend")""",
        "bar_chart": """# 막대 차트 (비교)
df = prepare_data(data, numeric_fields=["DT"])
chart = alt.Chart(df).mark_bar().encode(
    x=alt.X('C1_NM:N', sort='-y', title='분류'),
    y=alt.Y('sum(DT):Q', title='합계', axis=alt.Axis(format=',')),
    color=alt.value('#667eea')
).properties(title='비교 분석', width=600, height=400)
return save_chart(chart, "comparison")""",
        "donut_chart": """# 도넛 차트 (비율)
df = prepare_data(data, numeric_fields=["DT"])
df_agg = df.groupby("C1_NM")["DT"].sum().reset_index()
chart = alt.Chart(df_agg).mark_arc(innerRadius=50).encode(
    theta="DT:Q",
    color=alt.Color("C1_NM:N", title="구성"),
    tooltip=["C1_NM", alt.Tooltip("DT:Q", format=",")]
).properties(title='구성 비율', width=400, height=400)
return save_chart(chart, "composition")""",
        "full_report": """# 완전한 리포트
df = prepare_data(data, numeric_fields=["DT"])

# 핵심 수치 계산
total = df["DT"].sum()
latest = df[df["PRD_DE"] == df["PRD_DE"].max()]["DT"].sum()

# 차트 생성
chart = alt.Chart(df).mark_line(point=True).encode(
    x='PRD_DE:N', y=alt.Y('DT:Q', axis=alt.Axis(format=',')), color='C1_NM:N'
).properties(title='추이', width=600, height=400)

# 리포트 조립
html = build_report(
    title='분석 리포트',
    sections=[
        {'type': 'stats', 'items': [
            {'label': '총합', 'value': f'{total:,.0f}', 'unit': '명'},
            {'label': '최신', 'value': f'{latest:,.0f}', 'unit': '명'},
        ]},
        {'type': 'chart', 'vega_spec': chart.to_dict(), 'title': '추이', 'description': '연도별 변화'},
        {'type': 'insight', 'content': '핵심 발견점을 여기에 작성', 'title': '인사이트'},
        {'type': 'table', 'html': to_table_html(df.head(10), title='상세 데이터')},
    ]
)
return save_report(html, 'analysis_report')""",
        "aggregation": """# 데이터 집계
df = prepare_data(data, numeric_fields=["DT"])
result = df.groupby("C1_NM")["DT"].agg(['sum', 'mean', 'count']).sort_values('sum', ascending=False)
return result.head(10).to_dict()""",
    }
    return patterns


# =============================================================================
# HTTP 앱 생성 (아티팩트 서빙 포함)
# =============================================================================


def create_http_app():
    """
    HTTP 모드용 FastAPI 앱 생성.

    MCP 엔드포인트와 아티팩트 정적 파일 서빙을 통합합니다.
    """
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware

    # 아티팩트 디렉토리 생성
    artifacts_path = Path(ARTIFACTS_DIR)
    for subdir in ["charts", "reports", "data"]:
        (artifacts_path / subdir).mkdir(parents=True, exist_ok=True)

    # FastAPI 앱 생성
    app = FastAPI(
        title="KOSIS MCP Server",
        description="한국 통계 데이터 MCP 서버 (아티팩트 호스팅 포함)",
        version="0.1.0",
    )

    # CORS 설정 (로컬 개발용)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 아티팩트 정적 파일 서빙
    app.mount(
        "/artifacts", StaticFiles(directory=str(artifacts_path)), name="artifacts"
    )

    # MCP 엔드포인트 마운트
    mcp_app = mcp.http_app(path="/mcp")
    app.mount("/mcp", mcp_app)

    # 서버 정보 엔드포인트
    @app.get("/")
    def root():
        return {
            "name": "KOSIS MCP Server",
            "version": "0.1.0",
            "mcp_endpoint": "/mcp",
            "artifacts_endpoint": "/artifacts",
            "artifacts_structure": {
                "charts": "/artifacts/charts/{filename}",
                "reports": "/artifacts/reports/{filename}",
                "data": "/artifacts/data/{filename}",
            },
        }

    return app


# =============================================================================
# Tool surface filtering (US-003): expose only V1_EXPOSED to LLM clients.
# Internal tools remain reachable via discover_tools() / execute_tool().
# =============================================================================

from .discover import _register_full_registry  # noqa: E402
from .discover import discover_tools as _discover_tools_impl  # noqa: E402
from .discover import execute_tool as _execute_tool_impl  # noqa: E402
from .exposed_tools import V1_EXPOSED_NAMES  # noqa: E402

from kosis_tools.verify import verify_statistics as _verify_statistics_impl  # noqa: E402


@mcp.tool
async def verify_statistics(
    claim: str,
    table_id: Optional[str] = None,
    tolerance: float = 0.01,
) -> dict:
    """LLM이 생성한 숫자 주장을 KOSIS 원본 데이터와 대조 검증합니다 (US-005).

    한국어/영문 자연어 주장에서 숫자 + 시점 + 지역 + 지표를 추출하여
    KOSIS의 실제 셀 값과 상대 오차 비교 후 일치 여부를 반환합니다.

    Args:
        claim: 검증할 주장 (예: "2023년 서울 인구는 9.4M명").
        table_id: 알고 있는 KOSIS TBL_ID. 'org_id:tbl_id' 형식도 허용.
            생략하면 키워드 검색으로 자동 추정합니다 (정확도 ↓).
        tolerance: 상대 허용 오차. 기본 0.01 (= 1%).

    Returns:
        VerifyResult dict: match, expected, actual, diff_pct, tolerance,
        table_id, source_url, confidence, explanation.
    """
    result = await _verify_statistics_impl(
        claim, table_id=table_id, tolerance=tolerance
    )
    return result.to_dict()


@mcp.tool
def discover_tools() -> dict:
    """노출/내부 도구 전체 목록 조회.

    LLM에 기본 노출되는 도구는 V1_EXPOSED 한정이지만, 모든 등록된
    내부 도구는 execute_tool(name, args)로 호출할 수 있습니다.

    Returns:
        dict with keys: exposed, internal, total, exposed_count.
    """
    return _discover_tools_impl()


@mcp.tool
def execute_tool(name: str, args: Optional[dict] = None) -> dict:
    """이름으로 임의의 등록된 도구를 호출 (파워유저 escape hatch).

    Args:
        name: 도구 이름 (discover_tools()로 확인 가능).
        args: 도구에 전달할 키워드 인자. 시그니처와 맞지 않으면 에러 반환.

    Returns:
        {"tool": name, "result": ...} 또는 {"tool": name, "error": ...}.
    """
    return _execute_tool_impl(name, args or {})


def _prune_unexposed_tools() -> None:
    """Remove tools not in V1_EXPOSED from the public MCP tools/list response.

    Functions remain importable and callable via execute_tool(); only the
    LLM-facing tools/list surface is trimmed.
    """
    import asyncio as _asyncio

    try:
        registered = _asyncio.run(mcp.get_tools())
    except RuntimeError:
        # Already inside an event loop (e.g. during tests). Skip pruning;
        # the harness will get the full surface, which is safe but verbose.
        logger.warning("event loop running at import time; skipping tool pruning")
        return

    # Snapshot the FULL registry BEFORE pruning so execute_tool can still
    # reach internal tools after they're hidden from tools/list.
    _register_full_registry(registered)

    removed = 0
    for tool_name in list(registered.keys()):
        if tool_name not in V1_EXPOSED_NAMES:
            try:
                mcp.remove_tool(tool_name)
                removed += 1
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(f"failed to hide tool {tool_name!r}: {exc}")

    logger.info(
        f"tool surface filtered: {len(V1_EXPOSED_NAMES)} exposed, "
        f"{removed} hidden (still reachable via execute_tool)"
    )


_prune_unexposed_tools()


# =============================================================================
# 엔트리포인트
# =============================================================================


def main():
    """MCP 서버 실행."""
    if "--http" in sys.argv:
        # HTTP 모드
        import uvicorn

        port = int(os.environ.get("KOSIS_PORT", "8000"))
        host = os.environ.get("KOSIS_HOST", "0.0.0.0")

        logger.info(f"Starting HTTP server at http://{host}:{port}")
        logger.info(f"  MCP endpoint: http://{host}:{port}/mcp")
        logger.info(f"  Artifacts: http://{host}:{port}/artifacts/")

        app = create_http_app()
        uvicorn.run(app, host=host, port=port)
    else:
        # stdio 모드 (기본)
        mcp.run()


if __name__ == "__main__":
    main()
