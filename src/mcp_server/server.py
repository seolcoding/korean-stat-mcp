"""
KOSIS MCP Server - 한국 통계 데이터 MCP 서버.

이 서버는 KOSIS(국가통계포털) OpenAPI를 MCP 도구로 래핑하여
AI 에이전트가 한국 통계 데이터를 탐색하고 조회할 수 있게 합니다.

도구 구성:
    Layer 1 - DISCOVER: 데이터 탐색
    Layer 2 - FETCH: 데이터 조회
    DATA - 저장된 원본 데이터 접근

Example:
    # stdio 모드로 실행 (기본)
    korean-stat-mcp

    # HTTP 모드로 실행
    korean-stat-mcp --http
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Optional

from fastmcp import FastMCP

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastMCP 서버 생성.
#
# Keep the server instance transport-neutral: local CLI defaults to stdio, while
# HTTP-specific options such as json_response are applied only when creating the
# Streamable HTTP ASGI app.
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
    - get_statistics_data: 통계 데이터 조회 (요약 반환, 원본은 파일 저장)
    - filter_statistics: 데이터 필터링
    - aggregate_statistics: 데이터 집계

    💾 DATA ACCESS:
    - list_stored_data: 저장된 파일 목록
    - read_stored_data: 원본 데이터 읽기

    권장 워크플로우:
    1. search_statistics로 데이터 찾기
    2. get_statistics_data로 조회 (data_id 획득)
    3. 필요한 경우 read_stored_data로 청크를 읽고 클라이언트에서 분석/시각화
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
    sort: Optional[str] = None,
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
        sort: 정렬 기준 (선택)
              - "RANK": 관련도 순 (KOSIS 기본)
              - "DATE": 최신 갱신일 순 — verify_statistics 같이 최신 데이터가
                중요할 때 권장
              None이면 KOSIS 기본(RANK).

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
        >>> search_statistics("최저임금", sort="DATE")  # 최신 갱신 순
    """
    from kosis_tools.errors import error_to_dict
    from kosis_tools.report_tools import search_tables
    from kosis_tools.search import StatisticsSearch

    try:
        client = StatisticsSearch()
        results = search_tables(
            keyword, org_id=org_id, limit=limit, sort=sort, client=client
        )

        # 기관별 분포 계산
        org_dist = {}
        for r in results:
            org_nm = r.get("org_nm", "기타")
            org_dist[org_nm] = org_dist.get(org_nm, 0) + 1

        response: dict = {
            "query": keyword,
            "filter": {"org_id": org_id} if org_id else None,
            "result_count": len(results),
            "results": results,
            "org_distribution": org_dist,
            "next_step": "get_table_metadata(org_id, tbl_id)로 테이블 구조를 확인하세요",
        }
        # Surface KOSIS-classified error if results came back empty due to a
        # known errMsg path (auth / quota / query 30 etc.). LLM should follow
        # the action field rather than treat empty as 'no data'.
        if env := error_to_dict(client._last_error):
            response["error"] = env
        return response
    except Exception as e:
        logger.error(f"search_statistics error: {e}")
        return {"error": str(e)}


@mcp.tool
def browse_categories(
    by: str = "org",
    code: Optional[str] = None,
) -> dict:
    """
    기관별 / 주제별 / 임의 view 로 KOSIS 통계 목록을 탐색합니다.

    Args:
        by: 탐색 기준
            - "org": 기관별 (통계청, 고용노동부 등) — 일반 사용
            - "theme": 주제별 (인구, 경제, 사회 등) — 일반 사용
            - "view": 임의 vwCd (광복이전 / 북한 / 영문 / e-지방지표 / 국제 등 12종)
        code: by="org"면 기관 코드(101, 118, ...).
              by="theme"이면 주제 코드(A, B, C, ...).
              by="view"이면 vwCd 본문(MT_ETITLE, MT_BUKHAN, MT_CHOSUN_TITLE,
              MT_HANKUK_TITLE, MT_STOP_TITLE, MT_RTITLE, MT_TM1_TITLE,
              MT_TM2_TITLE, MT_GTITLE01, MT_GTITLE02, MT_OTITLE, MT_ZTITLE).
              None이면 view 루트 목록 반환.

    Returns:
        {
            "browse_type": "org" | "theme" | "view",
            "code": <입력 그대로>,
            "count": <int>,
            "categories" 또는 "statistics": [...],
            "usage" 또는 "next_step": <안내 문구>
        }

    Example:
        >>> browse_categories(by="org")
        >>> browse_categories(by="org", code="101")
        >>> browse_categories(by="theme")
        >>> browse_categories(by="view", code="MT_ETITLE")     # 영문 KOSIS
        >>> browse_categories(by="view", code="MT_BUKHAN")     # 북한통계
    """
    from kosis_tools.errors import error_to_dict
    from kosis_tools.list_categories import CategoryList, ViewCode
    from kosis_tools.report_tools import browse_categories as _browse

    try:
        if by == "view":
            view_code = (code or "").strip()
            if not view_code:
                return {
                    "browse_type": "view",
                    "code": None,
                    "count": 0,
                    "categories": [],
                    "usage": (
                        "browse_categories(by='view', code='<vwCd>')로 호출. "
                        f"가능한 vwCd: {', '.join(ViewCode.ALL)}"
                    ),
                    "supported_view_codes": list(ViewCode.ALL),
                }
            if view_code not in ViewCode.ALL:
                return {
                    "browse_type": "view",
                    "code": view_code,
                    "error": f"지원하지 않는 vwCd: {view_code}",
                    "supported_view_codes": list(ViewCode.ALL),
                }
            client = CategoryList()
            results = client.list_by_view(view_code)
            response: dict = {
                "browse_type": "view",
                "code": view_code,
                "count": len(results),
                "statistics": results,
                "next_step": (
                    "결과의 ORG_ID/TBL_ID로 get_table_metadata 또는 "
                    "get_statistics_data 호출"
                ),
            }
            if env := error_to_dict(client._last_error):
                response["error"] = env
            return response

        client = CategoryList()
        results = _browse(by=by, code=code, client=client)

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

        if env := error_to_dict(client._last_error):
            response["error"] = env
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
    from kosis_tools.errors import error_to_dict
    from kosis_tools.report_tools import get_table_meta
    from kosis_tools.table_meta import TableMetadata

    try:
        client = TableMetadata()
        result = get_table_meta(org_id, tbl_id, client=client)
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
                "prd_se_options": {"Y": "연간", "M": "월간", "Q": "분기", "H": "반기"},
            },
        }

        if env := error_to_dict(client._last_error):
            response["error"] = env
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
    new_est_prd_cnt: Optional[int] = None,
    prd_interval: Optional[int] = None,
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
                "Y"=연간, "M"=월간, "Q"=분기, "H"=반기
        format: 응답 형식
                "summary" (기본): LLM 친화적 요약 형식 (메타데이터 + 피벗 요약 + 샘플)
                "raw": 전체 원본 데이터 (주의: 컨텍스트 초과 가능)
        new_est_prd_cnt: 최근 N개 시점만 반환 (선택). KOSIS `newEstPrdCnt` 매핑.
                         예: 5 → 가장 최근 5개 기간만. start_date/end_date를 자동
                         제한하므로 "최근 5년만" 같은 자연어 쿼리에 직접 사용.
        prd_interval: 기간 stride (선택). KOSIS `prdInterval` 매핑.
                      예: prd_se="Y" + prd_interval=2 → 격년 데이터.

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
    from kosis_tools.data import StatisticsData
    from kosis_tools.errors import error_to_dict
    from kosis_tools.report_tools import fetch_data, format_data_for_llm

    try:
        client = StatisticsData()
        data = fetch_data(
            org_id=org_id,
            tbl_id=tbl_id,
            start_date=start_date,
            end_date=end_date,
            prd_se=prd_se,
            new_est_prd_cnt=new_est_prd_cnt,
            prd_interval=prd_interval,
            client=client,
        )

        if format == "raw":
            # raw 모드에서는 list 직접 반환이라 error envelope 부착할 곳이 없음.
            # 빈 결과 + 에러가 있으면 dict 한 항목으로 wrap해서 정보 보존.
            env = error_to_dict(client._last_error)
            if env and not data:
                return [{"_kosis_error": env}]
            return data

        # 기본: LLM 친화적 요약 형식
        formatted = format_data_for_llm(data, max_rows=50)
        if env := error_to_dict(client._last_error):
            if isinstance(formatted, dict):
                formatted["error"] = env
            else:
                formatted = {"data": formatted, "error": env}  # fallback wrap
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
# DATA ACCESS - 저장된 데이터 접근 도구
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
        "H": "반기 (Semi-annual)",
        "D": "일간 (Daily)",
    }
    return period_types


# =============================================================================
# HTTP 앱 생성 (아티팩트 서빙 포함)
# =============================================================================


def create_http_app():
    """Create the single production-compatible HTTP ASGI app."""
    from .app import app

    return app


# =============================================================================
# Tool surface filtering (US-003): expose only V1_EXPOSED to LLM clients.
# Internal tools remain reachable via discover_tools() / execute_tool().
# =============================================================================

from .discover import _register_full_registry  # noqa: E402
from .discover import _list_registered_tools  # noqa: E402
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
def get_key_indicator(
    by: str,
    value: str,
    page: int = 1,
    limit: int = 10,
) -> dict:
    """KOSIS 통계주요지표(Key Indicator)의 설명자료를 조회합니다.

    8개 KOSIS 통계주요지표 sub-service 중 설명자료 계열 두 가지를 by 인자로
    구분합니다 (KOSIS dev guide §2.7).

    Args:
        by: "id"  → 지표 고유번호로 조회 (pkNumberService.do)
            "name" → 지표명으로 조회 (indExpService.do)
        value: by="id" 면 지표 ID(jipyoId), by="name" 이면 지표명(jipyoNm).
        page: 페이지 번호 (기본 1).
        limit: 페이지당 결과 수 (기본 10).

    Returns:
        {"by": ..., "value": ..., "count": <int>, "results": [{...}, ...]}
        결과 항목은 IndicatorExplanation 의 dict 형태.

    Example:
        >>> get_key_indicator(by="id", value="160")
        >>> get_key_indicator(by="name", value="실업률")
    """
    from dataclasses import asdict
    from kosis_tools.errors import error_to_dict
    from kosis_tools.key_indicators import KeyIndicators

    if by not in ("id", "name"):
        return {"error": f"by must be 'id' or 'name', got {by!r}"}
    if not value:
        return {"error": "value (jipyoId / jipyoNm) is required"}

    try:
        client = KeyIndicators()
        if by == "id":
            items = client.get_explanation_by_id(value, page, limit)
        else:
            items = client.get_explanation_by_name(value, page, limit)
        response: dict = {
            "by": by,
            "value": value,
            "count": len(items),
            "results": [asdict(it) for it in items],
        }
        if env := error_to_dict(client._last_error):
            response["error"] = env
        return response
    except Exception as e:
        logger.error(f"get_key_indicator error: {e}")
        return {"error": str(e)}


@mcp.tool
def list_key_indicators(
    by: str = "category",
    value: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
) -> dict:
    """KOSIS 통계주요지표를 카테고리 또는 수록주기 기준으로 나열합니다.

    Args:
        by: "category" → 목록ID(listId)별 지표 (indiListService.do)
            "period"   → 수록주기(prdSe)별 지표 (prListSearchRequest.do)
        value: by="category" 면 listId(예: "A"). by="period" 면 prdSe(Y/M/Q/S).
        page: 페이지 번호.
        limit: 페이지당 결과 수.

    Returns:
        {"by": ..., "value": ..., "count": <int>, "results": [{...}, ...]}
    """
    from dataclasses import asdict
    from kosis_tools.errors import error_to_dict
    from kosis_tools.key_indicators import KeyIndicators

    if by not in ("category", "period"):
        return {"error": f"by must be 'category' or 'period', got {by!r}"}
    if not value:
        return {
            "error": "value is required",
            "hint": (
                "by='category' needs a listId (e.g. 'A'); "
                "by='period' needs prdSe in {Y, M, Q, S}"
            ),
        }

    try:
        client = KeyIndicators()
        if by == "category":
            items = client.get_by_list(value, page, limit)
        else:
            items = client.search_by_period_type(value, page, limit)
        response: dict = {
            "by": by,
            "value": value,
            "count": len(items),
            "results": [asdict(it) for it in items],
        }
        if env := error_to_dict(client._last_error):
            response["error"] = env
        return response
    except Exception as e:
        logger.error(f"list_key_indicators error: {e}")
        return {"error": str(e)}


@mcp.tool
def search_key_indicators(
    by: str,
    value: str,
    page: int = 1,
    limit: int = 10,
) -> dict:
    """KOSIS 통계주요지표를 이름 또는 고유번호로 검색합니다.

    Args:
        by: "name" → 지표명별 목록 검색 (indListSearchRequest.do, service=4)
            "id"   → 고유번호별 검색 (indListSearchRequest.do, service=4)
        value: by="name" 이면 지표명, by="id" 이면 jipyoId.
        page: 페이지 번호.
        limit: 페이지당 결과 수.

    Returns:
        {"by": ..., "value": ..., "count": <int>, "results": [{...}, ...]}
    """
    from dataclasses import asdict
    from kosis_tools.errors import error_to_dict
    from kosis_tools.key_indicators import KeyIndicators

    if by not in ("name", "id"):
        return {"error": f"by must be 'name' or 'id', got {by!r}"}
    if not value:
        return {"error": "value is required"}
    # by="id" expects a numeric jipyoId; non-numeric values always return
    # zero rows from KOSIS, so reject early to save the round-trip.
    if by == "id" and not value.isdigit():
        return {
            "error": "by='id' requires a numeric jipyoId (e.g. '160'). "
            "Use by='name' for textual lookup.",
            "by": by,
            "value": value,
            "count": 0,
            "results": [],
        }

    try:
        client = KeyIndicators()
        if by == "name":
            items = client.search_by_name(value, page, limit)
        else:
            items = client.search_by_id(value, page, limit)
        response: dict = {
            "by": by,
            "value": value,
            "count": len(items),
            "results": [asdict(it) for it in items],
        }
        if env := error_to_dict(client._last_error):
            response["error"] = env
        return response
    except Exception as e:
        logger.error(f"search_key_indicators error: {e}")
        return {"error": str(e)}


@mcp.tool
def get_key_indicator_details(
    jipyo_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    recent_n: Optional[int] = None,
    page: int = 1,
    limit: int = 10,
) -> dict:
    """KOSIS 통계주요지표의 시계열 상세 데이터를 조회합니다.

    indIdDetailSearchRequest.do (service=4 / serviceDetail=indIdDetail).

    Args:
        jipyo_id: 지표 ID (필수).
        start_date / end_date: 시점 기준 조회 (예: "2020", "2023").
        recent_n: 최신자료 기준으로 최근 N개 시점만. start/end 와 동시 지정 시
                  start/end 우선.
        page, limit: 페이지네이션.

    Returns:
        {"jipyo_id": ..., "count": <int>, "results": [{period, value, ...}]}
    """
    from dataclasses import asdict
    from kosis_tools.errors import error_to_dict
    from kosis_tools.key_indicators import KeyIndicators

    if not jipyo_id:
        return {"error": "jipyo_id is required"}

    try:
        client = KeyIndicators()
        items = client.get_detail(
            jipyo_id=jipyo_id,
            start_prd_de=start_date,
            end_prd_de=end_date,
            srv_rn=recent_n if (start_date is None and end_date is None) else None,
            page_no=page,
            num_of_rows=limit,
        )
        response: dict = {
            "jipyo_id": jipyo_id,
            "count": len(items),
            "results": [asdict(it) for it in items],
        }
        if env := error_to_dict(client._last_error):
            response["error"] = env
        return response
    except Exception as e:
        logger.error(f"get_key_indicator_details error: {e}")
        return {"error": str(e)}


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

    async def _prune_async() -> None:
        registered = await _list_registered_tools(mcp)

        # Snapshot the FULL registry BEFORE pruning so execute_tool can still
        # reach internal tools after they're hidden from tools/list.
        _register_full_registry(registered)

        removed = 0
        for tool_name in list(registered.keys()):
            if tool_name not in V1_EXPOSED_NAMES:
                try:
                    local_provider = getattr(mcp, "local_provider", None)
                    if local_provider is not None and hasattr(
                        local_provider, "remove_tool"
                    ):
                        local_provider.remove_tool(tool_name)
                    else:
                        mcp.remove_tool(tool_name)
                    removed += 1
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning(f"failed to hide tool {tool_name!r}: {exc}")

        logger.info(
            f"tool surface filtered: {len(V1_EXPOSED_NAMES)} exposed, "
            f"{removed} hidden (still reachable via execute_tool)"
        )

    try:
        loop = _asyncio.get_running_loop()
    except RuntimeError:
        _asyncio.run(_prune_async())
    else:
        loop.create_task(_prune_async())


_prune_unexposed_tools()


# =============================================================================
# 엔트리포인트
# =============================================================================


def _print_version() -> None:
    """Print package name + version. Read version from installed metadata."""
    try:
        from importlib.metadata import version as _v

        v = _v("korean-stat-mcp")
    except Exception:
        v = "unknown (not installed as a package)"
    print(f"korean-stat-mcp {v}")


def _print_help() -> None:
    print(
        """korean-stat-mcp — Korean Statistics (KOSIS) MCP server

Usage:
  korean-stat-mcp [--http] [--version] [--help]

Options:
  --http       Run as HTTP server (uvicorn). Defaults to stdio MCP mode.
  --version    Print version and exit.
  --help, -h   Show this message and exit.

Environment:
  KOSIS_API_KEY        Required. KOSIS OpenAPI key.
  KOSIS_PORT           HTTP port (default: 8000; with --http only).
  KOSIS_HOST           HTTP host (default: 0.0.0.0; with --http only).
  KOSIS_ARTIFACTS_DIR  Local artifact dir (default: /tmp/kosis_artifacts).
  DATABASE_URL         Optional Postgres URL (with [postgres] extra).

Docs: https://github.com/seolcoding/korean-stat-mcp
"""
    )


def main():
    """MCP 서버 실행 / CLI entrypoint."""
    if "--version" in sys.argv:
        _print_version()
        return
    if "--help" in sys.argv or "-h" in sys.argv:
        _print_help()
        return

    if "--http" in sys.argv:
        import uvicorn

        port = int(os.environ.get("KOSIS_PORT", "8000"))
        host = os.environ.get("KOSIS_HOST", "0.0.0.0")

        logger.info(f"Starting HTTP server at http://{host}:{port}")
        logger.info(f"  MCP endpoint: http://{host}:{port}/mcp")
        logger.info(f"  Artifacts: http://{host}:{port}/artifacts/")

        app = create_http_app()
        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
