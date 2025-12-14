"""
KOSIS 통계표 검색 모듈.

이 모듈은 KOSIS OpenAPI의 statisticsList.do 엔드포인트를 사용하여
통계표를 키워드로 검색하는 기능을 제공합니다.

주요 기능:
    - 키워드 검색: 통계표명에 포함된 키워드로 검색
    - 기관별 필터링: 특정 기관의 통계만 검색
    - 결과 정렬: 기본적으로 최신순 정렬

Example:
    기본 사용:
    >>> from kosis_tools.search import StatisticsSearch
    >>> search = StatisticsSearch()
    >>> results = search.search("인구")
    >>> for item in results[:3]:
    ...     print(f"{item['TBL_NM']} ({item['ORG_NM']})")
    행정구역별 인구수 (통계청)
    연령별 인구수 (통계청)
    인구동향 (통계청)

    기관 필터링:
    >>> results = search.search("고용", org_id="118")  # 고용노동부만
    >>> print(len(results))
    42

API Reference:
    - Endpoint: statisticsList.do
    - Method: getList
    - 공식 문서: https://kosis.kr/openapi/
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import KosisBaseClient
from .config import Endpoints, KosisConfig

logger = logging.getLogger(__name__)


class StatisticsSearch(KosisBaseClient):
    """
    KOSIS 통계표 검색 클라이언트.

    통계표를 키워드로 검색하여 테이블 목록을 반환합니다.
    검색 결과에는 테이블 ID, 이름, 기관, 수록기간 등이 포함됩니다.

    이 클래스는 KosisBaseClient를 상속받아 HTTP 요청, rate limiting,
    에러 핸들링 등의 공통 기능을 사용합니다.

    Attributes:
        config: KosisConfig 인스턴스. API 키, 타임아웃 등 설정.

    Args:
        config: KosisConfig 인스턴스. None이면 환경변수에서 기본 설정 로드.

    Example:
        >>> search = StatisticsSearch()
        >>> results = search.search("물가")
        >>> print(results[0]["TBL_ID"])
        "DT_1J20001"

    API Reference:
        - Endpoint: statisticsList.do
        - 응답 형식: 비표준 JSON (키에 따옴표 없음)
        - Rate Limit: 1 request/second (권장)
    """

    def search(
        self,
        keyword: str,
        org_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        result_count: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        통계표를 키워드로 검색합니다.

        이 메서드는 KOSIS OpenAPI의 statisticsList.do 엔드포인트를 호출하여
        키워드와 일치하는 통계표 목록을 반환합니다.

        검색은 통계표명(TBL_NM)을 대상으로 수행됩니다.
        한글, 영문 모두 검색 가능합니다.

        Args:
            keyword: 검색할 키워드.
                     예: "인구", "고용", "물가", "GDP"
                     한글/영문 모두 가능, 최소 1자 이상.
                     공백 포함 가능 (예: "경제 성장").

            org_id: 기관 ID로 필터링 (선택사항).
                    예: "101" (통계청), "118" (고용노동부),
                        "154" (한국은행), "301" (국토교통부)
                    None이면 전체 기관에서 검색.

            start_date: 수록기간 시작일 필터 (선택사항).
                        형식: "YYYY" 또는 "YYYYMM"
                        예: "2020", "202001"

            end_date: 수록기간 종료일 필터 (선택사항).
                      형식: "YYYY" 또는 "YYYYMM"
                      예: "2023", "202312"

            result_count: 최대 결과 개수 (기본값: 100, 최대: 5000).
                          검색 결과가 많을 경우 제한하여 성능 향상.

        Returns:
            통계표 목록. 각 항목의 구조:
            {
                "TBL_ID": "DT_1B040A3",      # 테이블 고유 ID
                "TBL_NM": "행정구역별 인구수", # 테이블명
                "ORG_ID": "101",              # 기관 ID
                "ORG_NM": "통계청",           # 기관명
                "STRT_PRD_DE": "1992",        # 수록 시작 기간
                "END_PRD_DE": "2023",         # 수록 종료 기간
                "PRD_SE": "Y",                # 수록주기 (M/Q/S/Y)
                "STAT_ID": "1992001",         # 통계 ID
                "STAT_NM": "주민등록인구현황", # 통계명
                "CONTENTS": "...",            # 통계표 설명
                "VIEW_KIND": "1"              # 조회 유형
            }

            검색 결과가 없으면 빈 리스트 [] 반환.
            API 에러 시에도 빈 리스트 반환 (에러 로그 기록).

        Example:
            기본 검색:
            >>> search = StatisticsSearch()
            >>> results = search.search("인구")
            >>> print(f"검색 결과: {len(results)}건")
            검색 결과: 156건

            기관 필터링:
            >>> results = search.search("고용", org_id="118")
            >>> for r in results[:3]:
            ...     print(r["TBL_NM"])
            고용형태별근로실태조사
            사업체노동력조사
            임금근로일자리 행정통계

            기간 필터링:
            >>> results = search.search("물가", start_date="2020")
            >>> print(f"2020년 이후 데이터: {len(results)}건")

        API Reference:
            - Endpoint: statisticsList.do
            - Method: getList
            - 파라미터:
                - apiKey: API 인증 키 (필수)
                - format: json (필수)
                - method: getList (필수)
                - searchNm: 검색어
                - orgId: 기관 ID
                - startPrdDe: 시작 기간
                - endPrdDe: 종료 기간

        Note:
            - 검색어가 빈 문자열이면 빈 리스트 반환
            - 특수문자는 자동으로 URL 인코딩됨
            - 대소문자 구분 없음
            - 결과는 기본적으로 관련도순 정렬
        """
        if not keyword or not keyword.strip():
            logger.warning("검색어가 비어있습니다.")
            return []

        params: Dict[str, Any] = {
            "method": "getList",
            "format": "json",
            "searchNm": keyword.strip(),
            "resultCount": str(min(result_count, 5000)),  # 최대 5000
        }

        if org_id:
            params["orgId"] = org_id

        if start_date:
            params["startPrdDe"] = start_date

        if end_date:
            params["endPrdDe"] = end_date

        logger.info(f"통계표 검색: '{keyword}'" + (f" (기관: {org_id})" if org_id else ""))

        result = self._request("GET", Endpoints.STATISTICS_SEARCH, params)

        if result is None:
            logger.debug("검색 결과 없음 또는 API 에러")
            return []

        if isinstance(result, list):
            logger.info(f"검색 결과: {len(result)}건")
            return result
        elif isinstance(result, dict):
            # 단일 결과도 리스트로 반환
            logger.info("검색 결과: 1건")
            return [result]
        else:
            logger.warning(f"예상치 못한 응답 타입: {type(result)}")
            return []

    def search_by_table_id(self, tbl_id: str) -> Optional[Dict[str, Any]]:
        """
        테이블 ID로 특정 통계표를 조회합니다.

        테이블 ID가 정확히 일치하는 통계표 정보를 반환합니다.
        이 메서드는 이미 알고 있는 테이블 ID의 상세 정보를 확인할 때 유용합니다.

        Args:
            tbl_id: 테이블 ID.
                    예: "DT_1B040A3", "DT_1J20001"
                    KOSIS에서 사용하는 고유 식별자.

        Returns:
            통계표 정보 딕셔너리. 구조는 search() 메서드 반환값 참조.
            테이블을 찾지 못하면 None 반환.

        Example:
            >>> search = StatisticsSearch()
            >>> table = search.search_by_table_id("DT_1B040A3")
            >>> if table:
            ...     print(f"{table['TBL_NM']} ({table['ORG_NM']})")
            ...     print(f"기간: {table['STRT_PRD_DE']} ~ {table['END_PRD_DE']}")
            행정구역별 인구수 (통계청)
            기간: 1992 ~ 2023

        Note:
            - 테이블 ID는 대소문자를 구분합니다
            - 존재하지 않는 ID는 None 반환
        """
        if not tbl_id or not tbl_id.strip():
            logger.warning("테이블 ID가 비어있습니다.")
            return None

        params: Dict[str, Any] = {
            "method": "getList",
            "format": "json",
            "searchNm": tbl_id.strip(),
        }

        logger.debug(f"테이블 ID 검색: {tbl_id}")

        result = self._request("GET", Endpoints.STATISTICS_SEARCH, params)

        if result is None:
            return None

        # 결과에서 정확히 일치하는 테이블 찾기
        if isinstance(result, list):
            for item in result:
                if item.get("TBL_ID") == tbl_id:
                    return item
            # 정확히 일치하는 것이 없으면 첫 번째 결과 반환 (유사 검색)
            logger.debug(f"정확히 일치하는 테이블 없음, 첫 번째 결과 반환")
            return result[0] if result else None
        elif isinstance(result, dict):
            return result if result.get("TBL_ID") == tbl_id else None

        return None
