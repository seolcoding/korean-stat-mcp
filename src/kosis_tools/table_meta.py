"""
KOSIS 통계표 메타데이터 모듈.

이 모듈은 KOSIS OpenAPI의 statisticsData.do 엔드포인트를 사용하여
통계표의 메타데이터(테이블명, 분류항목, 수록정보 등)를 조회합니다.

주요 기능:
    - 통계표 기본 정보 조회 (국문/영문명)
    - 분류항목(OBJ_VAR) 조회
    - 항목(ITM_VAR) 조회
    - 수록정보 조회 (기간, 주기)

Example:
    기본 사용:
    >>> from kosis_tools.table_meta import TableMetadata
    >>> meta = TableMetadata()
    >>> info = meta.get_table_info("101", "DT_1IN0001")
    >>> print(info["TBL_NM"])
    총조사인구 총괄(읍면동/성/연령별)

    분류항목 조회:
    >>> obj_vars = meta.get_obj_vars("101", "DT_1IN0001")
    >>> for var in obj_vars:
    ...     print(f"{var['OBJ_ID']}: {var['OBJ_NM']}")

API Reference:
    - Endpoint: statisticsData.do
    - Method: getMeta
    - Type: TBL (테이블), PRD (수록기간), OBJ_VAR (분류), ITM_VAR (항목)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import KosisBaseClient
from .config import Endpoints, KosisConfig

logger = logging.getLogger(__name__)


class TableMetadata(KosisBaseClient):
    """
    KOSIS 통계표 메타데이터 클라이언트.

    통계표의 메타데이터(테이블명, 분류항목, 항목, 수록정보)를 조회합니다.
    이 정보는 데이터 조회 전 테이블 구조를 파악하는 데 필수적입니다.

    이 클래스는 KosisBaseClient를 상속받아 HTTP 요청, rate limiting,
    에러 핸들링 등의 공통 기능을 사용합니다.

    Attributes:
        config: KosisConfig 인스턴스. API 키, 타임아웃 등 설정.

    Args:
        config: KosisConfig 인스턴스. None이면 환경변수에서 기본 설정 로드.

    Example:
        >>> meta = TableMetadata()
        >>> info = meta.get_table_info("101", "DT_1B040A3")
        >>> print(f"{info['TBL_NM']} ({info.get('TBL_NM_ENG', '')})")
        행정구역별 인구수 (Population by administrative district)

    API Reference:
        - Endpoint: statisticsData.do
        - Method: getMeta
        - 응답 형식: 비표준 JSON (키에 따옴표 없음)
    """

    def get_table_info(
        self,
        org_id: str,
        tbl_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        통계표 기본 정보를 조회합니다.

        테이블의 국문/영문 명칭을 반환합니다.
        데이터 조회 전 테이블이 존재하는지 확인할 때 유용합니다.

        Args:
            org_id: 기관 ID.
                    예: "101" (통계청), "154" (한국은행)

            tbl_id: 통계표 ID.
                    예: "DT_1B040A3", "DT_1IN0001"
                    KOSIS에서 사용하는 테이블 고유 식별자.

        Returns:
            통계표 정보 딕셔너리:
            {
                "TBL_NM": "총조사인구 총괄(읍면동/성/연령별)",  # 국문명
                "TBL_NM_ENG": "Summary of Census Population..."  # 영문명
            }

            테이블을 찾지 못하면 None 반환.

        Example:
            >>> meta = TableMetadata()
            >>> info = meta.get_table_info("101", "DT_1IN0001")
            >>> if info:
            ...     print(f"국문: {info['TBL_NM']}")
            ...     print(f"영문: {info.get('TBL_NM_ENG', 'N/A')}")
            국문: 총조사인구 총괄(읍면동/성/연령별)
            영문: Summary of Census Population(By administrative district/sex/age)

        API Reference:
            - Endpoint: statisticsData.do
            - Method: getMeta
            - Type: TBL
            - 파라미터: orgId, tblId

        Note:
            - org_id나 tbl_id가 빈 문자열이면 None 반환
            - 존재하지 않는 테이블은 None 반환
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return None

        if not tbl_id or not tbl_id.strip():
            logger.warning("테이블 ID가 비어있습니다.")
            return None

        params: Dict[str, Any] = {
            "method": "getMeta",
            "type": "TBL",
            "format": "json",
            "orgId": org_id.strip(),
            "tblId": tbl_id.strip(),
        }

        logger.info(f"통계표 정보 조회: org_id={org_id}, tbl_id={tbl_id}")

        result = self._request("GET", Endpoints.STATISTICS_TABLE_META, params)

        if result is None:
            return None

        if isinstance(result, list) and len(result) > 0:
            return result[0]
        elif isinstance(result, dict):
            return result

        return None

    def get_obj_vars(
        self,
        org_id: str,
        tbl_id: str,
    ) -> List[Dict[str, Any]]:
        """
        통계표의 분류항목(OBJ_VAR)을 조회합니다.

        분류항목은 데이터 조회 시 objL1, objL2 등의 파라미터에 사용됩니다.
        예를 들어 "행정구역별", "성별", "연령별" 등이 분류항목입니다.

        Args:
            org_id: 기관 ID.
                    예: "101" (통계청)

            tbl_id: 통계표 ID.
                    예: "DT_1B040A3"

        Returns:
            분류항목 목록. 각 항목 구조:
            {
                "OBJ_ID": "ITEM",         # 분류 ID (objL1에 사용)
                "OBJ_NM": "행정구역별",    # 분류명
                "OBJ_NM_ENG": "By region", # 영문 분류명
                "OBJ_LV": "1",             # 분류 레벨 (1~8)
                "UP_OBJ_ID": "",           # 상위 분류 ID
                "OBJ_VAR_CNT": "250"       # 분류값 개수
            }

            결과가 없으면 빈 리스트 반환.

        Example:
            >>> meta = TableMetadata()
            >>> obj_vars = meta.get_obj_vars("101", "DT_1B040A3")
            >>> for var in obj_vars:
            ...     print(f"objL{var['OBJ_LV']}: {var['OBJ_NM']} ({var['OBJ_VAR_CNT']}개)")
            objL1: 행정구역별 (250개)
            objL2: 성별 (3개)

        API Reference:
            - Endpoint: statisticsData.do
            - Method: getMeta
            - Type: OBJ_VAR

        Note:
            - 분류 레벨(OBJ_LV)은 데이터 조회 시 objL1~objL8에 대응
            - 일부 테이블은 분류가 1개만 있고, 최대 8개까지 가능
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return []

        if not tbl_id or not tbl_id.strip():
            logger.warning("테이블 ID가 비어있습니다.")
            return []

        params: Dict[str, Any] = {
            "method": "getMeta",
            "type": "OBJ_VAR",
            "format": "json",
            "orgId": org_id.strip(),
            "tblId": tbl_id.strip(),
        }

        logger.info(f"분류항목 조회: org_id={org_id}, tbl_id={tbl_id}")

        result = self._request("GET", Endpoints.STATISTICS_TABLE_META, params)

        if result is None:
            return []

        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]

        return []

    def get_itm_vars(
        self,
        org_id: str,
        tbl_id: str,
    ) -> List[Dict[str, Any]]:
        """
        통계표의 항목(ITM_VAR)을 조회합니다.

        항목은 데이터 조회 시 itmId 파라미터에 사용됩니다.
        예를 들어 "총인구", "남자", "여자", "65세이상" 등이 항목입니다.

        Args:
            org_id: 기관 ID.
                    예: "101" (통계청)

            tbl_id: 통계표 ID.
                    예: "DT_1B040A3"

        Returns:
            항목 목록. 각 항목 구조:
            {
                "ITM_ID": "T001",         # 항목 ID (itmId에 사용)
                "ITM_NM": "총인구",        # 항목명
                "ITM_NM_ENG": "Total",    # 영문 항목명
                "UP_ITM_ID": "",          # 상위 항목 ID
                "UNIT_NM": "명",           # 단위
                "UNIT_NM_ENG": "Persons"  # 영문 단위
            }

            결과가 없으면 빈 리스트 반환.

        Example:
            >>> meta = TableMetadata()
            >>> items = meta.get_itm_vars("101", "DT_1B040A3")
            >>> for itm in items[:5]:
            ...     print(f"{itm['ITM_ID']}: {itm['ITM_NM']} ({itm.get('UNIT_NM', '')})")
            T001: 총인구 (명)
            T002: 남자 (명)
            T003: 여자 (명)

        API Reference:
            - Endpoint: statisticsData.do
            - Method: getMeta
            - Type: ITM_VAR

        Note:
            - 데이터 조회 시 특정 항목만 조회하려면 ITM_ID 사용
            - "ALL"로 조회하면 모든 항목 데이터 반환
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return []

        if not tbl_id or not tbl_id.strip():
            logger.warning("테이블 ID가 비어있습니다.")
            return []

        params: Dict[str, Any] = {
            "method": "getMeta",
            "type": "ITM_VAR",
            "format": "json",
            "orgId": org_id.strip(),
            "tblId": tbl_id.strip(),
        }

        logger.info(f"항목 조회: org_id={org_id}, tbl_id={tbl_id}")

        result = self._request("GET", Endpoints.STATISTICS_TABLE_META, params)

        if result is None:
            return []

        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]

        return []

    def get_prd_info(
        self,
        org_id: str,
        tbl_id: str,
    ) -> List[Dict[str, Any]]:
        """
        통계표의 수록기간 정보를 조회합니다.

        테이블에 데이터가 수록된 기간과 주기를 확인할 수 있습니다.
        데이터 조회 전 유효한 기간 범위를 파악하는 데 유용합니다.

        Args:
            org_id: 기관 ID.
                    예: "101" (통계청)

            tbl_id: 통계표 ID.
                    예: "DT_1B040A3"

        Returns:
            수록기간 정보 목록. 각 항목 구조:
            {
                "PRD_SE": "Y",           # 수록주기 (M/Q/S/Y/F/IR)
                "PRD_DE": "2023",        # 기간
                "PRD_NM": "2023년",       # 기간명
                "STRT_PRD_DE": "1992",   # 시작 기간
                "END_PRD_DE": "2023"     # 종료 기간
            }

            결과가 없으면 빈 리스트 반환.

        Example:
            >>> meta = TableMetadata()
            >>> prd_info = meta.get_prd_info("101", "DT_1B040A3")
            >>> if prd_info:
            ...     info = prd_info[0]
            ...     print(f"주기: {info['PRD_SE']}")
            ...     print(f"기간: {info.get('STRT_PRD_DE', 'N/A')} ~ {info.get('END_PRD_DE', 'N/A')}")
            주기: Y
            기간: 1992 ~ 2023

        API Reference:
            - Endpoint: statisticsData.do
            - Method: getMeta
            - Type: PRD

        Note:
            - PRD_SE 값: M(월간), Q(분기), S(반기), Y(연간), F(다년), IR(부정기)
            - 일부 테이블은 여러 주기를 지원 (예: 월간 + 연간)
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return []

        if not tbl_id or not tbl_id.strip():
            logger.warning("테이블 ID가 비어있습니다.")
            return []

        params: Dict[str, Any] = {
            "method": "getMeta",
            "type": "PRD",
            "format": "json",
            "orgId": org_id.strip(),
            "tblId": tbl_id.strip(),
        }

        logger.info(f"수록기간 조회: org_id={org_id}, tbl_id={tbl_id}")

        result = self._request("GET", Endpoints.STATISTICS_TABLE_META, params)

        if result is None:
            return []

        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]

        return []

    def get_comments(
        self,
        org_id: str,
        tbl_id: str,
    ) -> List[Dict[str, Any]]:
        """
        통계표의 주석(CMMT) 정보를 조회합니다.

        데이터 해석에 필요한 부가 설명, 특이사항 등의 주석을 조회합니다.

        Args:
            org_id: 기관 ID. 예: "101" (통계청)
            tbl_id: 통계표 ID. 예: "DT_1B040A3"

        Returns:
            주석 목록. 각 항목 구조:
            {
                "CMMT_NM": "주석유형",     # 주석 유형
                "CMMT_DC": "주석 내용",    # 주석 설명
                "OBJ_ID": "분류 ID",       # 관련 분류 ID (선택)
                "OBJ_NM": "분류명",        # 관련 분류명 (선택)
                "ITM_ID": "항목 ID",       # 관련 항목 ID (선택)
                "ITM_NM": "항목명"         # 관련 항목명 (선택)
            }

        Example:
            >>> meta = TableMetadata()
            >>> comments = meta.get_comments("101", "DT_1B040A3")
            >>> for c in comments:
            ...     print(f"{c.get('CMMT_NM', 'N/A')}: {c.get('CMMT_DC', '')}")

        API Reference:
            - Endpoint: statisticsData.do
            - Method: getMeta
            - Type: CMMT
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return []

        if not tbl_id or not tbl_id.strip():
            logger.warning("테이블 ID가 비어있습니다.")
            return []

        params: Dict[str, Any] = {
            "method": "getMeta",
            "type": "CMMT",
            "format": "json",
            "orgId": org_id.strip(),
            "tblId": tbl_id.strip(),
        }

        logger.info(f"주석 정보 조회: org_id={org_id}, tbl_id={tbl_id}")

        result = self._request("GET", Endpoints.STATISTICS_TABLE_META, params)

        if result is None:
            return []

        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]

        return []

    def get_source(
        self,
        org_id: str,
        tbl_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        통계표의 출처(SOURCE) 정보를 조회합니다.

        통계 작성 기관, 담당부서, 연락처 등의 정보를 조회합니다.

        Args:
            org_id: 기관 ID. 예: "101" (통계청)
            tbl_id: 통계표 ID. 예: "DT_1B040A3"

        Returns:
            출처 정보 딕셔너리:
            {
                "JOSA_NM": "조사명",          # 통계조사명
                "DEPT_NM": "담당부서",        # 담당 부서명
                "DEPT_PHONE": "연락처",       # 부서 전화번호
                "STAT_ID": "통계조사ID"       # 통계조사 고유 ID
            }

            정보가 없으면 None 반환.

        Example:
            >>> meta = TableMetadata()
            >>> source = meta.get_source("101", "DT_1B040A3")
            >>> if source:
            ...     print(f"조사명: {source.get('JOSA_NM', 'N/A')}")
            ...     print(f"담당: {source.get('DEPT_NM', 'N/A')}")

        API Reference:
            - Endpoint: statisticsData.do
            - Method: getMeta
            - Type: SOURCE
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return None

        if not tbl_id or not tbl_id.strip():
            logger.warning("테이블 ID가 비어있습니다.")
            return None

        params: Dict[str, Any] = {
            "method": "getMeta",
            "type": "SOURCE",
            "format": "json",
            "orgId": org_id.strip(),
            "tblId": tbl_id.strip(),
        }

        logger.info(f"출처 정보 조회: org_id={org_id}, tbl_id={tbl_id}")

        result = self._request("GET", Endpoints.STATISTICS_TABLE_META, params)

        if result is None:
            return None

        if isinstance(result, list) and len(result) > 0:
            return result[0]
        elif isinstance(result, dict):
            return result

        return None

    def get_weight(
        self,
        org_id: str,
        tbl_id: str,
        obj_codes: Optional[Dict[str, str]] = None,
        itm_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        통계표의 가중치(WGT) 정보를 조회합니다.

        표본조사 등에서 사용되는 가중치 값을 조회합니다.

        Args:
            org_id: 기관 ID. 예: "101" (통계청)
            tbl_id: 통계표 ID. 예: "DT_1B040A3"
            obj_codes: 분류코드 딕셔너리 (선택).
                       예: {"C1": "00", "C2": "01"}
            itm_id: 항목 ID (선택). 예: "T001"

        Returns:
            가중치 목록. 각 항목 구조:
            {
                "C1": "분류값1",          # 분류1 ID
                "C1_NM": "분류값1 명",    # 분류1 명칭
                "C2": "분류값2",          # 분류2 ID (있는 경우)
                ...
                "ITM_ID": "항목 ID",      # 항목 ID
                "ITM_NM": "항목명",       # 항목명
                "WGT_CO": 1.5            # 가중치 값 (NUMBER)
            }

        Example:
            >>> meta = TableMetadata()
            >>> weights = meta.get_weight("101", "DT_1B040A3")
            >>> for w in weights:
            ...     print(f"{w.get('ITM_NM', 'N/A')}: {w.get('WGT_CO', 0)}")

        API Reference:
            - Endpoint: statisticsData.do
            - Method: getMeta
            - Type: WGT
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return []

        if not tbl_id or not tbl_id.strip():
            logger.warning("테이블 ID가 비어있습니다.")
            return []

        params: Dict[str, Any] = {
            "method": "getMeta",
            "type": "WGT",
            "format": "json",
            "orgId": org_id.strip(),
            "tblId": tbl_id.strip(),
        }

        # 분류코드 추가
        if obj_codes:
            for key, value in obj_codes.items():
                params[key] = value

        # 항목 ID 추가
        if itm_id:
            params["ITEM"] = itm_id

        logger.info(f"가중치 정보 조회: org_id={org_id}, tbl_id={tbl_id}")

        result = self._request("GET", Endpoints.STATISTICS_TABLE_META, params)

        if result is None:
            return []

        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]

        return []

    def get_update_date(
        self,
        org_id: str,
        tbl_id: str,
        prd_se: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        통계표의 자료갱신일(NCD) 정보를 조회합니다.

        데이터가 마지막으로 업데이트된 날짜를 확인합니다.

        Args:
            org_id: 기관 ID. 예: "101" (통계청)
            tbl_id: 통계표 ID. 예: "DT_1B040A3"
            prd_se: 수록주기 (선택). "Y", "M", "Q" 등

        Returns:
            자료갱신일 목록. 각 항목 구조:
            {
                "ORG_NM": "통계청",       # 기관명
                "TBL_NM": "통계표명",     # 통계표명
                "PRD_SE": "Y",           # 수록주기
                "PRD_DE": "2023",        # 수록시점
                "SEND_DE": "2024-01-15"  # 자료갱신일
            }

        Example:
            >>> meta = TableMetadata()
            >>> updates = meta.get_update_date("101", "DT_1B040A3")
            >>> for u in updates:
            ...     print(f"{u.get('PRD_DE', 'N/A')}: {u.get('SEND_DE', 'N/A')}")

        API Reference:
            - Endpoint: statisticsData.do
            - Method: getMeta
            - Type: NCD
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return []

        if not tbl_id or not tbl_id.strip():
            logger.warning("테이블 ID가 비어있습니다.")
            return []

        params: Dict[str, Any] = {
            "method": "getMeta",
            "type": "NCD",
            "format": "json",
            "orgId": org_id.strip(),
            "tblId": tbl_id.strip(),
        }

        if prd_se:
            params["prdSe"] = prd_se

        logger.info(f"자료갱신일 조회: org_id={org_id}, tbl_id={tbl_id}")

        result = self._request("GET", Endpoints.STATISTICS_TABLE_META, params)

        if result is None:
            return []

        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]

        return []

    def get_unit(
        self,
        org_id: str,
        tbl_id: str,
    ) -> List[Dict[str, Any]]:
        """
        통계표의 단위(UNIT) 정보를 조회합니다.

        데이터 값의 단위 (명, 원, % 등)를 조회합니다.

        Args:
            org_id: 기관 ID. 예: "101" (통계청)
            tbl_id: 통계표 ID. 예: "DT_1B040A3"

        Returns:
            단위 목록. 각 항목 구조:
            {
                "UNIT_NM": "명",          # 단위 국문명
                "UNIT_NM_ENG": "Persons"  # 단위 영문명
            }

        Example:
            >>> meta = TableMetadata()
            >>> units = meta.get_unit("101", "DT_1B040A3")
            >>> for u in units:
            ...     print(f"{u.get('UNIT_NM', 'N/A')} ({u.get('UNIT_NM_ENG', '')})")

        API Reference:
            - Endpoint: statisticsData.do
            - Method: getMeta
            - Type: UNIT
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return []

        if not tbl_id or not tbl_id.strip():
            logger.warning("테이블 ID가 비어있습니다.")
            return []

        params: Dict[str, Any] = {
            "method": "getMeta",
            "type": "UNIT",
            "format": "json",
            "orgId": org_id.strip(),
            "tblId": tbl_id.strip(),
        }

        logger.info(f"단위 정보 조회: org_id={org_id}, tbl_id={tbl_id}")

        result = self._request("GET", Endpoints.STATISTICS_TABLE_META, params)

        if result is None:
            return []

        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return [result]

        return []

    def get_org_info(
        self,
        org_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        기관 명칭(ORG) 정보를 조회합니다.

        Args:
            org_id: 기관 ID. 예: "101" (통계청)

        Returns:
            기관 정보 딕셔너리:
            {
                "orgNm": "통계청",              # 기관 국문명
                "orgNmEng": "Statistics Korea"  # 기관 영문명
            }

            정보가 없으면 None 반환.

        Example:
            >>> meta = TableMetadata()
            >>> org = meta.get_org_info("101")
            >>> if org:
            ...     print(f"{org.get('orgNm', 'N/A')} ({org.get('orgNmEng', '')})")

        API Reference:
            - Endpoint: statisticsData.do
            - Method: getMeta
            - Type: ORG
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return None

        params: Dict[str, Any] = {
            "method": "getMeta",
            "type": "ORG",
            "format": "json",
            "orgId": org_id.strip(),
        }

        logger.info(f"기관 정보 조회: org_id={org_id}")

        result = self._request("GET", Endpoints.STATISTICS_TABLE_META, params)

        if result is None:
            return None

        if isinstance(result, list) and len(result) > 0:
            return result[0]
        elif isinstance(result, dict):
            return result

        return None

    def get_all_metadata(
        self,
        org_id: str,
        tbl_id: str,
        include_extended: bool = False,
    ) -> Dict[str, Any]:
        """
        통계표의 전체 메타데이터를 한 번에 조회합니다.

        테이블 정보, 분류항목, 항목, 수록기간을 모두 조회하여
        하나의 딕셔너리로 반환합니다.

        Args:
            org_id: 기관 ID.
                    예: "101" (통계청)

            tbl_id: 통계표 ID.
                    예: "DT_1B040A3"

            include_extended: 확장 메타데이터 포함 여부.
                             True면 주석, 출처, 단위, 갱신일도 조회.
                             기본값: False

        Returns:
            전체 메타데이터 딕셔너리:
            {
                "table_info": {...},      # get_table_info() 결과
                "obj_vars": [...],        # get_obj_vars() 결과
                "itm_vars": [...],        # get_itm_vars() 결과
                "prd_info": [...],        # get_prd_info() 결과
                "org_id": "101",          # 기관 ID
                "tbl_id": "DT_1B040A3",   # 테이블 ID
                # include_extended=True일 때 추가:
                "comments": [...],        # get_comments() 결과
                "source": {...},          # get_source() 결과
                "units": [...],           # get_unit() 결과
                "update_dates": [...]     # get_update_date() 결과
            }

        Example:
            >>> meta = TableMetadata()
            >>> all_meta = meta.get_all_metadata("101", "DT_1B040A3")
            >>> print(f"테이블: {all_meta['table_info']['TBL_NM']}")
            >>> print(f"분류항목: {len(all_meta['obj_vars'])}개")
            >>> print(f"항목: {len(all_meta['itm_vars'])}개")
            테이블: 행정구역별 인구수
            분류항목: 2개
            항목: 10개

        Note:
            - 기본: 4개의 API 호출 (rate limiting 적용)
            - include_extended=True: 8개의 API 호출
            - 데이터 조회 전 테이블 구조 파악에 유용
        """
        logger.info(f"전체 메타데이터 조회: org_id={org_id}, tbl_id={tbl_id}, extended={include_extended}")

        result = {
            "table_info": self.get_table_info(org_id, tbl_id),
            "obj_vars": self.get_obj_vars(org_id, tbl_id),
            "itm_vars": self.get_itm_vars(org_id, tbl_id),
            "prd_info": self.get_prd_info(org_id, tbl_id),
            "org_id": org_id,
            "tbl_id": tbl_id,
        }

        if include_extended:
            result["comments"] = self.get_comments(org_id, tbl_id)
            result["source"] = self.get_source(org_id, tbl_id)
            result["units"] = self.get_unit(org_id, tbl_id)
            result["update_dates"] = self.get_update_date(org_id, tbl_id)

        return result
