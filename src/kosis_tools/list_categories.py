"""
KOSIS 카테고리별 통계 목록 모듈.

이 모듈은 KOSIS OpenAPI의 statisticsList.do 엔드포인트를 사용하여
기관별, 주제별로 통계 목록을 조회하는 기능을 제공합니다.

주요 기능:
    - 기관별 목록: 특정 기관의 모든 통계표 조회
    - 주제별 목록: 특정 주제(인구, 경제, 교육 등) 통계표 조회
    - 통계별 목록: 상위 통계에 속한 하위 통계표 조회

Example:
    기관별 목록:
    >>> from kosis_tools.list_categories import CategoryList
    >>> categories = CategoryList()
    >>> tables = categories.list_by_org("101")  # 통계청
    >>> print(f"통계청 통계표: {len(tables)}개")
    통계청 통계표: 1234개

    주제별 목록:
    >>> tables = categories.list_by_theme("A")  # 인구
    >>> print(f"인구 관련 통계표: {len(tables)}개")
    인구 관련 통계표: 89개

API Reference:
    - Endpoint: statisticsList.do
    - Method: getList
    - vwCd 파라미터로 조회 유형 구분
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import KosisBaseClient, build_format_param
from .config import Endpoints

logger = logging.getLogger(__name__)


# 주요 기관 코드 상수
class OrgCode:
    """
    주요 기관 코드 상수.

    KOSIS에 등록된 주요 기관의 ID입니다.
    기관별 통계 조회 시 사용합니다.

    Example:
        >>> categories = CategoryList()
        >>> tables = categories.list_by_org(OrgCode.KOSTAT)  # 통계청
        >>> tables = categories.list_by_org(OrgCode.BOK)     # 한국은행
    """

    KOSTAT = "101"  # 통계청
    MOF = "103"  # 기획재정부
    MOEL = "118"  # 고용노동부
    BOK = "154"  # 한국은행
    MOLIT = "301"  # 국토교통부
    MOE = "112"  # 교육부
    MOHW = "117"  # 보건복지부
    ME = "106"  # 환경부


# 주제 코드 상수
class ThemeCode:
    """
    주제 코드 상수.

    KOSIS의 주제별 분류 코드입니다.
    주제별 통계 조회 시 vwCd 파라미터에 사용합니다.

    Example:
        >>> categories = CategoryList()
        >>> tables = categories.list_by_theme(ThemeCode.POPULATION)
        >>> tables = categories.list_by_theme(ThemeCode.ECONOMY)
    """

    POPULATION = "A"  # 인구
    LABOR = "B"  # 고용/노동/임금
    AGRICULTURE = "C"  # 농림수산업
    MINING = "D"  # 광업/제조업/에너지
    CONSTRUCTION = "E"  # 건설
    TRANSPORT = "F"  # 교통/정보통신
    TRADE = "G"  # 도소매/서비스업
    ECONOMY = "H"  # 경기/기업경영
    FINANCE = "I"  # 물가/가계/소비
    HEALTH = "J"  # 보건/사회/복지
    EDUCATION = "K"  # 교육/문화/과학
    SAFETY = "L"  # 환경/재해/안전
    ADMIN = "M"  # 행정/사법
    NATIONAL_ACCOUNT = "N"  # 국민계정/재정/금융
    INTERNATIONAL = "O"  # 국제/북한


class CategoryList(KosisBaseClient):
    """
    KOSIS 카테고리별 통계 목록 클라이언트.

    기관별, 주제별로 통계표 목록을 조회합니다.
    특정 조건에 맞는 모든 통계표를 리스팅할 때 사용합니다.

    이 클래스는 KosisBaseClient를 상속받아 HTTP 요청, rate limiting,
    에러 핸들링 등의 공통 기능을 사용합니다.

    Attributes:
        config: KosisConfig 인스턴스. API 키, 타임아웃 등 설정.

    Args:
        config: KosisConfig 인스턴스. None이면 환경변수에서 기본 설정 로드.

    Example:
        >>> categories = CategoryList()
        >>> # 통계청의 모든 통계표
        >>> kostat_tables = categories.list_by_org("101")
        >>> # 인구 주제의 모든 통계표
        >>> pop_tables = categories.list_by_theme("A")
    """

    def list_by_org(
        self,
        org_id: str,
        parent_stat_id: Optional[str] = None,
        *,
        response_format: str | None = None,
    ) -> List[Dict[str, Any]]:
        """
        특정 기관의 통계표 목록을 조회합니다.

        지정한 기관에서 제공하는 모든 통계표 목록을 반환합니다.
        parent_stat_id를 지정하면 해당 상위 통계에 속한 하위 통계표만 조회합니다.

        Args:
            org_id: 기관 ID.
                    예: "101" (통계청), "118" (고용노동부)
                    OrgCode 클래스의 상수를 사용할 수 있습니다.

            parent_stat_id: 상위 통계 ID (선택사항).
                            특정 통계에 속한 하위 테이블만 조회할 때 사용.
                            예: "1992001" (주민등록인구현황의 하위 테이블들)

        Returns:
            통계표 목록. 각 항목의 구조:
            {
                "TBL_ID": "DT_1B040A3",      # 테이블 고유 ID
                "TBL_NM": "행정구역별 인구수", # 테이블명
                "ORG_ID": "101",              # 기관 ID
                "ORG_NM": "통계청",           # 기관명
                "STAT_ID": "1992001",         # 통계 ID
                "STAT_NM": "주민등록인구현황", # 통계명
                "STRT_PRD_DE": "1992",        # 수록 시작 기간
                "END_PRD_DE": "2023",         # 수록 종료 기간
                "PRD_SE": "Y",                # 수록주기
                "CONTENTS": "..."             # 설명
            }

            결과가 없으면 빈 리스트 [] 반환.

        Example:
            통계청의 모든 통계표:
            >>> categories = CategoryList()
            >>> tables = categories.list_by_org(OrgCode.KOSTAT)
            >>> print(f"통계청 통계표: {len(tables)}개")
            통계청 통계표: 1234개

            특정 통계의 하위 테이블:
            >>> tables = categories.list_by_org("101", parent_stat_id="1992001")
            >>> for t in tables:
            ...     print(t["TBL_NM"])

        API Reference:
            - Endpoint: statisticsList.do
            - Method: getList
            - 파라미터:
                - orgId: 기관 ID (필수)
                - parentStatId: 상위 통계 ID (선택)

        Note:
            - org_id가 빈 문자열이면 빈 리스트 반환
            - 존재하지 않는 기관 ID는 빈 결과 반환
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return []

        params: Dict[str, Any] = {
            "method": "getList",
            "format": build_format_param(response_format),  # type: ignore[arg-type]
            "vwCd": "MT_OTITLE",  # 기관별 통계 뷰
            "parentListId": org_id.strip(),  # 기관 ID를 parentListId로 전달
        }

        if parent_stat_id:
            params["parentListId"] = parent_stat_id  # 하위 통계 조회 시 덮어씀

        logger.info(f"기관별 통계 목록 조회: org_id={org_id}")

        result = self._request("GET", Endpoints.STATISTICS_LIST, params)

        if result is None:
            return []

        if isinstance(result, list):
            logger.info(f"조회 결과: {len(result)}개")
            return result
        elif isinstance(result, dict):
            return [result]
        else:
            return []

    def list_by_theme(
        self,
        vw_cd: str,
        *,
        response_format: str | None = None,
    ) -> List[Dict[str, Any]]:
        """
        특정 주제의 통계표 목록을 조회합니다.

        KOSIS의 주제별 분류에 따른 통계표 목록을 반환합니다.
        주제 코드는 ThemeCode 클래스의 상수를 사용할 수 있습니다.

        Args:
            vw_cd: 주제 코드.
                   예: "A" (인구), "H" (경제), "J" (보건)
                   ThemeCode 클래스의 상수를 사용할 수 있습니다.

        Returns:
            통계표 목록. 구조는 list_by_org() 메서드 반환값과 동일.
            결과가 없으면 빈 리스트 [] 반환.

        Example:
            인구 주제의 통계표:
            >>> categories = CategoryList()
            >>> tables = categories.list_by_theme(ThemeCode.POPULATION)
            >>> print(f"인구 통계표: {len(tables)}개")
            인구 통계표: 89개

            경제 주제의 통계표:
            >>> tables = categories.list_by_theme(ThemeCode.ECONOMY)
            >>> for t in tables[:5]:
            ...     print(f"{t['TBL_NM']} - {t['ORG_NM']}")

        API Reference:
            - Endpoint: statisticsList.do
            - Method: getList
            - 파라미터:
                - vwCd: 주제 코드

        Note:
            - vw_cd가 빈 문자열이면 빈 리스트 반환
            - 유효하지 않은 주제 코드는 빈 결과 반환
        """
        if not vw_cd or not vw_cd.strip():
            logger.warning("주제 코드가 비어있습니다.")
            return []

        params: Dict[str, Any] = {
            "method": "getList",
            "format": build_format_param(response_format),  # type: ignore[arg-type]
            "vwCd": "MT_ZTITLE",  # 주제별 통계 뷰
            "parentListId": vw_cd.strip(),  # 주제 코드를 parentListId로 전달
        }

        logger.info(f"주제별 통계 목록 조회: vw_cd={vw_cd}")

        result = self._request("GET", Endpoints.STATISTICS_LIST, params)

        if result is None:
            return []

        if isinstance(result, list):
            logger.info(f"조회 결과: {len(result)}개")
            return result
        elif isinstance(result, dict):
            return [result]
        else:
            return []

    def list_statistics(
        self,
        org_id: str,
        *,
        response_format: str | None = None,
    ) -> List[Dict[str, Any]]:
        """
        기관의 상위 통계 목록을 조회합니다.

        기관에서 제공하는 상위 통계(STAT) 목록을 반환합니다.
        각 통계에는 여러 개의 통계표(TBL)가 포함될 수 있습니다.

        Args:
            org_id: 기관 ID.
                    예: "101" (통계청)

        Returns:
            통계 목록. 각 항목의 구조:
            {
                "STAT_ID": "1992001",         # 통계 ID
                "STAT_NM": "주민등록인구현황", # 통계명
                "ORG_ID": "101",              # 기관 ID
                "ORG_NM": "통계청",           # 기관명
                "TBL_CNT": "5"                # 하위 테이블 수
            }

        Example:
            >>> categories = CategoryList()
            >>> stats = categories.list_statistics("101")
            >>> for s in stats[:5]:
            ...     print(f"{s['STAT_NM']} ({s.get('TBL_CNT', '?')}개 테이블)")
            주민등록인구현황 (5개 테이블)
            인구동태조사 (12개 테이블)

        Note:
            - 이 메서드는 테이블이 아닌 상위 통계 단위를 조회합니다
            - 특정 통계의 하위 테이블은 list_by_org(org_id, parent_stat_id) 사용
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return []

        params: Dict[str, Any] = {
            "method": "getList",
            "format": build_format_param(response_format),  # type: ignore[arg-type]
            "vwCd": "MT_OTITLE",  # 기관별 통계 뷰
            "parentListId": org_id.strip(),  # 기관 ID를 parentListId로 전달
        }

        logger.info(f"기관 통계 목록 조회: org_id={org_id}")

        result = self._request("GET", Endpoints.STATISTICS_LIST, params)

        if result is None:
            return []

        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]
        else:
            return []
