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
from typing import Optional
from pathlib import Path

from fastmcp import FastMCP

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastMCP 서버 생성
mcp = FastMCP(
    name="kosis-stats",
    instructions="""
    KOSIS(국가통계포털) 통계 데이터 서버입니다.

    사용 가능한 도구:

    🔍 DISCOVER (데이터 탐색):
    - search_statistics: 키워드로 통계표 검색
    - browse_categories: 기관/주제별 통계 목록
    - get_table_metadata: 테이블 상세 정보
    - get_available_values: 필터링 가능한 값 조회

    📥 FETCH (데이터 조회):
    - get_statistics_data: 통계 데이터 조회 (원본은 파일에 자동 저장)
    - filter_statistics: 데이터 필터링
    - aggregate_statistics: 데이터 집계

    📊 PRESENT (시각화/리포트):
    - create_quick_report: 빠른 HTML 리포트 생성
    - analyze_trend: 추세 분석
    - analyze_comparison: 비교 분석
    - analyze_ranking: 순위 분석

    💾 DATA ACCESS (저장 데이터 접근):
    - list_stored_data: 저장된 데이터 파일 목록
    - read_stored_data: 저장된 원본 데이터 읽기 (청크 지원)

    일반적인 워크플로우:
    1. search_statistics로 원하는 데이터 찾기
    2. get_table_metadata로 테이블 구조 파악
    3. get_statistics_data로 데이터 조회 (요약만 반환, 원본은 파일에 저장)
    4. 필요시 read_stored_data로 원본 데이터 접근
    5. analyze_* 또는 create_quick_report로 결과 생성
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
) -> str:
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

        return json.dumps({
            "query": keyword,
            "filter": {"org_id": org_id} if org_id else None,
            "result_count": len(results),
            "results": results,
            "org_distribution": org_dist,
            "next_step": "get_table_metadata(org_id, tbl_id)로 테이블 구조를 확인하세요"
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"search_statistics error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool
def browse_categories(
    by: str = "org",
    code: Optional[str] = None,
) -> str:
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
            response["next_step"] = "get_table_metadata(org_id, tbl_id)로 테이블 구조를 확인하세요"
        else:
            # 카테고리 목록
            response["categories"] = results
            response["usage"] = f"browse_categories(by='{by}', code='코드')로 해당 카테고리의 통계표 목록을 조회하세요"

        return json.dumps(response, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"browse_categories error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool
def get_table_metadata(
    org_id: str,
    tbl_id: str,
) -> str:
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

        return json.dumps(response, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"get_table_metadata error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool
def get_available_values(
    data_json: str,
    field: str,
) -> str:
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

        return json.dumps({
            "field": field,
            "field_description": field_descriptions.get(field, field),
            "count": len(values),
            "values": values[:50] if len(values) > 50 else values,  # 최대 50개
            "truncated": len(values) > 50,
            "filter_example": filter_examples.get(field, "filter_statistics(data, ...)"),
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"get_available_values error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


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
) -> str:
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
            return json.dumps(data, ensure_ascii=False, indent=2)

        # 기본: LLM 친화적 요약 형식
        formatted = format_data_for_llm(data, max_rows=50)
        return json.dumps(formatted, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"get_statistics_data error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool
def filter_statistics(
    regions: Optional[str] = None,
    periods: Optional[str] = None,
    items: Optional[str] = None,
    format: str = "summary",
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> str:
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
                return json.dumps(loaded, ensure_ascii=False)
            data = loaded["data"]
        elif data_json:
            data = json.loads(data_json)
        else:
            return json.dumps({"error": "data_id 또는 data_json 중 하나를 제공해야 합니다"}, ensure_ascii=False)

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
            return json.dumps(filtered, ensure_ascii=False, indent=2)

        # 기본: LLM 친화적 요약 형식 (필터 결과는 파일 저장 안 함)
        formatted = format_data_for_llm(filtered, max_rows=50, save_raw=False)
        return json.dumps(formatted, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"filter_statistics error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool
def aggregate_statistics(
    group_by: str,
    agg_func: str = "sum",
    format: str = "summary",
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> str:
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
    from kosis_tools.report_tools import aggregate_data, format_data_for_llm, load_raw_data

    try:
        # data_id 우선 사용 (서버 사이드 처리)
        if data_id:
            loaded = load_raw_data(data_id)
            if "error" in loaded:
                return json.dumps(loaded, ensure_ascii=False)
            data = loaded["data"]
        elif data_json:
            data = json.loads(data_json)
        else:
            return json.dumps({"error": "data_id 또는 data_json 중 하나를 제공해야 합니다"}, ensure_ascii=False)

        group_by_list = [g.strip() for g in group_by.split(",")]

        if len(group_by_list) == 1:
            group_by_list = group_by_list[0]

        aggregated = aggregate_data(data, group_by=group_by_list, agg_func=agg_func)

        if format == "raw":
            return json.dumps(aggregated, ensure_ascii=False, indent=2)

        # 기본: LLM 친화적 요약 형식
        formatted = format_data_for_llm(aggregated, max_rows=50, save_raw=False)
        return json.dumps(formatted, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"aggregate_statistics error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


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
            return None, json.dumps(loaded, ensure_ascii=False)
        return loaded["data"], None
    elif data_json:
        try:
            return json.loads(data_json), None
        except json.JSONDecodeError as e:
            return None, json.dumps({"error": f"JSON 파싱 오류: {e}"}, ensure_ascii=False)
    else:
        return None, json.dumps({"error": "data_id 또는 data_json 중 하나를 제공해야 합니다"}, ensure_ascii=False)


@mcp.tool
def analyze_trend(
    group_by: Optional[str] = None,
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> str:
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
            # 그룹별 분석
            groups = metrics.get("groups", {})
            directions = [g.get("direction", "") for g in groups.values()]
            summary = f"{len(groups)}개 그룹 분석 완료"
        else:
            direction = metrics.get("direction", "")
            cagr = metrics.get("cagr", 0)
            summary = f"전반적으로 {direction} 추세 (연평균 {cagr:+.1f}%)" if direction else "추세 분석 완료"

        return json.dumps({
            "analysis_type": result.type,
            "summary": summary,
            "group_by": group_by,
            "findings": result.findings[:10],  # 최대 10개
            "metrics": result.metrics,
            "interpretation": result.interpretation,
            "visualization_suggestion": "create_quick_report()로 차트 포함 리포트 생성 가능",
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"analyze_trend error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool
def analyze_comparison(
    targets: Optional[str] = None,
    period: Optional[str] = None,
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> str:
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

        return json.dumps({
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
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"analyze_comparison error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool
def analyze_ranking(
    top_n: int = 10,
    period: Optional[str] = None,
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> str:
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
        for item in (result.data[:top_n] if result.data else []):
            rankings.append({
                "rank": item.get("rank", 0),
                "name": item.get("C1_NM", item.get("name", "")),
                "value": item.get("DT", item.get("value", 0)),
            })

        # 요약 생성
        top_1 = result.metrics.get("top_1", {})
        summary = f"1위 {top_1.get('C1_NM', '')}, 상위 {top_n}개 분석" if top_1 else f"상위 {top_n}개 순위 분석"

        return json.dumps({
            "analysis_type": result.type,
            "summary": summary,
            "period": result.metrics.get("period", period),
            "top_n": top_n,
            "total_count": result.metrics.get("total_count", 0),
            "rankings": rankings,
            "findings": result.findings[:5],  # 상위 5개 발견사항만
            "interpretation": result.interpretation,
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"analyze_ranking error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool
def create_quick_report(
    title: str = "데이터 분석 리포트",
    output_path: Optional[str] = None,
    data_id: Optional[str] = None,
    data_json: Optional[str] = None,
) -> str:
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
            "components": ["KPI 카드 (3개)", "추이 라인 차트", "비교 막대 차트", "인사이트 박스", "데이터 출처"],
        }

        if output_path:
            return json.dumps({
                "status": "success",
                "report_info": report_info,
                "file_path": result,
                "message": f"HTML 리포트가 '{result}'에 저장되었습니다. 브라우저에서 열어 확인하세요.",
            }, ensure_ascii=False, indent=2)
        else:
            # output_path 없으면 저장 권장
            return json.dumps({
                "status": "success",
                "report_info": report_info,
                "html_size": f"{len(result):,} bytes",
                "message": "HTML 리포트가 생성되었습니다. output_path를 지정하여 파일로 저장하세요.",
                "suggestion": "create_quick_report(data, title='제목', output_path='report.html')",
            }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"create_quick_report error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# =============================================================================
# Layer 4: DATA ACCESS - 저장된 데이터 접근 도구
# =============================================================================

@mcp.tool
def list_stored_data() -> str:
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
        return json.dumps({
            "stored_files": files[:20],  # 최근 20개만
            "total_files": len(files),
            "hint": "read_stored_data(data_id)로 전체 데이터 접근, "
                   "read_stored_data(data_id, chunk_index=0)로 청크별 접근",
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"list_stored_data error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


@mcp.tool
def read_stored_data(
    data_id: str,
    chunk_index: Optional[int] = None,
    chunk_size: int = 50,
) -> str:
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
            return json.dumps(result, ensure_ascii=False)

        # 전체 데이터가 너무 크면 경고
        if chunk_index is None and len(result.get("data", [])) > 100:
            return json.dumps({
                "warning": f"대용량 데이터 ({len(result['data'])}건). 청크별로 읽는 것을 권장합니다.",
                "data_id": data_id,
                "record_count": len(result.get("data", [])),
                "suggestion": f"read_stored_data('{data_id}', chunk_index=0)로 청크별 접근",
                "meta": result.get("meta", {}),
            }, ensure_ascii=False, indent=2)

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"read_stored_data error: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


# =============================================================================
# Resources - 정적 데이터 리소스
# =============================================================================

@mcp.resource("kosis://regions")
def get_regions_resource() -> str:
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
    return json.dumps(regions, ensure_ascii=False, indent=2)


@mcp.resource("kosis://org-codes")
def get_org_codes_resource() -> str:
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
    return json.dumps(orgs, ensure_ascii=False, indent=2)


@mcp.resource("kosis://period-types")
def get_period_types_resource() -> str:
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
    return json.dumps(period_types, ensure_ascii=False, indent=2)


# =============================================================================
# 엔트리포인트
# =============================================================================

def main():
    """MCP 서버 실행."""
    mcp.run()


if __name__ == "__main__":
    main()
