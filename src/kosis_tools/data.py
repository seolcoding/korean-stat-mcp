"""
KOSIS 통계 데이터 조회 모듈.

이 모듈은 KOSIS OpenAPI의 statisticsParameterData.do 엔드포인트를 사용하여
실제 통계 데이터를 조회하는 기능을 제공합니다.

주요 기능:
    - 직접 데이터 조회: 주기(prdSe) 지정하여 조회
    - 자동 주기 탐색: 최적의 주기를 자동으로 찾아 조회
    - objL1/objL2 재시도 로직: 단일 분류 실패 시 다중 분류로 재시도

Example:
    직접 데이터 조회:
    >>> from kosis_tools.data import StatisticsData
    >>> data = StatisticsData()
    >>> result = data.get_data(
    ...     org_id="101",
    ...     tbl_id="DT_1B040A3",
    ...     start_date="2020",
    ...     end_date="2023",
    ...     prd_se="Y"  # 연간
    ... )
    >>> print(f"조회된 레코드: {len(result)}건")

    자동 주기 탐색:
    >>> result = data.get_data_auto_period(
    ...     org_id="101",
    ...     tbl_id="DT_1B040A3",
    ...     start_date="2020",
    ...     end_date="2023"
    ... )
    >>> print(f"주기: {result['period_name']}, 레코드: {len(result['data'])}건")

API Reference:
    - Endpoint: statisticsParameterData.do
    - Method: getList
    - 공식 문서: https://kosis.kr/openapi/
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .base import KosisBaseClient
from .config import Endpoints, KosisConfig, PeriodType

logger = logging.getLogger(__name__)


class StatisticsData(KosisBaseClient):
    """
    KOSIS 통계 데이터 조회 클라이언트.

    통계표의 실제 데이터를 조회합니다.
    주기(월간/분기/연간 등)를 지정하거나 자동으로 탐색할 수 있습니다.

    이 클래스는 KosisBaseClient를 상속받아 HTTP 요청, rate limiting,
    에러 핸들링 등의 공통 기능을 사용합니다.

    Attributes:
        config: KosisConfig 인스턴스. API 키, 타임아웃 등 설정.

    Args:
        config: KosisConfig 인스턴스. None이면 환경변수에서 기본 설정 로드.

    Example:
        >>> data = StatisticsData()
        >>> records = data.get_data("101", "DT_1B040A3", "2020", "2023")
        >>> for r in records[:3]:
        ...     print(f"{r['C1_NM']}: {r['DT']}")

    API Reference:
        - Endpoint: Param/statisticsParameterData.do
        - 응답 형식: 비표준 JSON (키에 따옴표 없음)
        - Rate Limit: 1 request/second (권장)
    """

    def get_data(
        self,
        org_id: str,
        tbl_id: str,
        start_date: str,
        end_date: str,
        prd_se: str = "Y",
        obj_l1: str = "ALL",
        obj_l2: Optional[str] = None,
        itm_id: str = "ALL",
    ) -> List[Dict[str, Any]]:
        """
        통계 데이터를 조회합니다.

        지정한 테이블의 데이터를 주기(prdSe)와 기간에 맞게 조회합니다.
        분류항목(objL1, objL2)과 항목(itmId)으로 필터링할 수 있습니다.

        Args:
            org_id: 기관 ID.
                    예: "101" (통계청), "118" (고용노동부)

            tbl_id: 테이블 ID.
                    예: "DT_1B040A3" (행정구역별 인구수)
                    StatisticsSearch로 검색하여 얻을 수 있습니다.

            start_date: 조회 시작 기간.
                        주기에 따른 형식:
                        - 연간(Y): "2020"
                        - 월간(M): "202001"
                        - 분기(Q): "202001" (01=1분기)
                        - 반기(S): "202001" (01=상반기)

            end_date: 조회 종료 기간.
                      start_date와 동일한 형식.

            prd_se: 수록주기.
                    "M" (월간/격월), "Q" (분기), "S" (반기),
                    "Y" (연간), "F" (다년), "IR" (부정기)
                    PeriodType 클래스의 상수를 사용할 수 있습니다.
                    기본값: "Y" (연간)

            obj_l1: 분류항목 1 코드.
                    "ALL"이면 모든 분류 조회.
                    특정 코드 지정 시 해당 분류만 조회.
                    기본값: "ALL"

            obj_l2: 분류항목 2 코드 (선택사항).
                    일부 테이블은 2차원 분류가 필요합니다.
                    None이면 objL1만 사용.

            itm_id: 항목 ID.
                    "ALL"이면 모든 항목 조회.
                    특정 코드 지정 시 해당 항목만 조회.
                    기본값: "ALL"

        Returns:
            데이터 레코드 목록. 각 레코드의 구조:
            {
                "TBL_ID": "DT_1B040A3",    # 테이블 ID
                "TBL_NM": "행정구역별 인구수", # 테이블명
                "ORG_ID": "101",            # 기관 ID
                "PRD_DE": "2023",           # 기간 (주기에 따라 형식 다름)
                "PRD_SE": "Y",              # 주기
                "C1": "00",                 # 분류1 코드
                "C1_NM": "전국",            # 분류1 이름
                "C2": "01",                 # 분류2 코드 (있는 경우)
                "C2_NM": "서울특별시",      # 분류2 이름 (있는 경우)
                "ITM_ID": "T20",            # 항목 ID
                "ITM_NM": "인구수",         # 항목명
                "DT": "51823154",           # 데이터 값
                "UNIT_NM": "명"             # 단위
            }

            조회 실패 또는 결과 없음 시 빈 리스트 [] 반환.

        Example:
            연간 데이터 조회:
            >>> data = StatisticsData()
            >>> records = data.get_data(
            ...     org_id="101",
            ...     tbl_id="DT_1B040A3",
            ...     start_date="2020",
            ...     end_date="2023",
            ...     prd_se="Y"
            ... )
            >>> for r in records[:5]:
            ...     print(f"{r['PRD_DE']} {r['C1_NM']}: {r['DT']}")
            2023 전국: 51823154
            2023 서울특별시: 9411453
            ...

            월간 데이터 조회:
            >>> records = data.get_data(
            ...     org_id="101",
            ...     tbl_id="DT_1J20001",
            ...     start_date="202301",
            ...     end_date="202312",
            ...     prd_se="M"
            ... )

        API Reference:
            - Endpoint: Param/statisticsParameterData.do
            - Method: getList
            - 주요 파라미터:
                - orgId: 기관 ID (필수)
                - tblId: 테이블 ID (필수)
                - prdSe: 수록주기 (필수)
                - startPrdDe: 시작 기간 (필수)
                - endPrdDe: 종료 기간 (필수)
                - objL1: 분류항목1 (기본: ALL)
                - objL2: 분류항목2 (선택)
                - itmId: 항목 ID (기본: ALL)

        Note:
            - 일부 테이블은 objL2가 필수입니다. objL1만으로 실패 시
              get_data_with_retry() 또는 get_data_auto_period() 사용 권장.
            - 대용량 데이터 조회 시 API 응답이 느릴 수 있습니다.
            - rate limiting이 자동 적용됩니다.
        """
        if not org_id or not tbl_id:
            logger.warning("org_id와 tbl_id는 필수입니다.")
            return []

        params: Dict[str, Any] = {
            "method": "getList",
            "format": "json",
            "orgId": org_id,
            "tblId": tbl_id,
            "objL1": obj_l1,
            "itmId": itm_id,
            "prdSe": prd_se,
            "startPrdDe": start_date,
            "endPrdDe": end_date,
        }

        if obj_l2:
            params["objL2"] = obj_l2

        logger.debug(f"데이터 조회: {tbl_id}, 주기={prd_se}, 기간={start_date}~{end_date}")

        result = self._request("GET", Endpoints.STATISTICS_DATA, params)

        if result is None:
            return []

        if isinstance(result, list):
            logger.info(f"조회 결과: {len(result)}건")
            return result
        elif isinstance(result, dict):
            return [result]
        else:
            return []

    def get_data_with_retry(
        self,
        org_id: str,
        tbl_id: str,
        start_date: str,
        end_date: str,
        prd_se: str = "Y",
        itm_id: str = "ALL",
    ) -> List[Dict[str, Any]]:
        """
        데이터 조회를 재시도 로직과 함께 수행합니다.

        1차 시도: objL1="ALL"만 사용
        2차 시도: objL1="ALL", objL2="ALL" 함께 사용

        일부 KOSIS 테이블은 2차원 분류가 필수인데, API 문서에
        명확히 표시되지 않아 1차 시도 실패 시 재시도가 필요합니다.

        Args:
            org_id: 기관 ID
            tbl_id: 테이블 ID
            start_date: 시작 기간
            end_date: 종료 기간
            prd_se: 수록주기 (기본: "Y")
            itm_id: 항목 ID (기본: "ALL")

        Returns:
            데이터 레코드 목록. 구조는 get_data() 반환값과 동일.
            두 번의 시도 모두 실패 시 빈 리스트 반환.

        Example:
            >>> data = StatisticsData()
            >>> records = data.get_data_with_retry(
            ...     org_id="101",
            ...     tbl_id="DT_1B040A3",
            ...     start_date="2020",
            ...     end_date="2023"
            ... )
            >>> print(f"조회 결과: {len(records)}건")

        Note:
            - 이 메서드는 get_data()보다 성공률이 높습니다.
            - 2번의 API 호출이 발생할 수 있어 rate limiting에 주의.
        """
        logger.debug(f"1차 시도 (objL1만): {tbl_id}")
        data = self.get_data(
            org_id=org_id,
            tbl_id=tbl_id,
            start_date=start_date,
            end_date=end_date,
            prd_se=prd_se,
            obj_l1="ALL",
            obj_l2=None,
            itm_id=itm_id,
        )

        if data:
            return data

        logger.debug(f"2차 시도 (objL1 + objL2): {tbl_id}")
        data = self.get_data(
            org_id=org_id,
            tbl_id=tbl_id,
            start_date=start_date,
            end_date=end_date,
            prd_se=prd_se,
            obj_l1="ALL",
            obj_l2="ALL",
            itm_id=itm_id,
        )

        return data

    def get_data_auto_period(
        self,
        org_id: str,
        tbl_id: str,
        start_date: str,
        end_date: str,
        itm_id: str = "ALL",
    ) -> Optional[Dict[str, Any]]:
        """
        최적의 주기를 자동으로 찾아 데이터를 조회합니다.

        월간 → 분기 → 반기 → 연간 → 다년 → 부정기 순으로
        주기를 시도하여 데이터가 있는 첫 번째 주기로 조회합니다.

        KOSIS의 각 테이블은 특정 주기로만 데이터를 제공하는데,
        어떤 주기인지 미리 알기 어려울 때 이 메서드를 사용합니다.

        Args:
            org_id: 기관 ID
            tbl_id: 테이블 ID
            start_date: 시작 기간 (YYYY 형식 권장)
            end_date: 종료 기간 (YYYY 형식 권장)
            itm_id: 항목 ID (기본: "ALL")

        Returns:
            성공 시 딕셔너리:
            {
                "data": [...],          # 데이터 레코드 리스트
                "period_type": "Y",     # 성공한 주기 코드
                "period_name": "연간"   # 성공한 주기 한글명
            }

            모든 주기에서 실패 시 None 반환.

        Example:
            >>> data = StatisticsData()
            >>> result = data.get_data_auto_period(
            ...     org_id="101",
            ...     tbl_id="DT_1B040A3",
            ...     start_date="2020",
            ...     end_date="2023"
            ... )
            >>> if result:
            ...     print(f"주기: {result['period_name']}")
            ...     print(f"레코드 수: {len(result['data'])}")
            주기: 연간
            레코드 수: 680

        Note:
            - 최대 6번의 API 호출이 발생할 수 있습니다.
            - 각 주기 시도 사이에 rate limiting이 적용됩니다.
            - 세밀한 데이터(월간)부터 시도하므로 가능한 상세한 데이터를 얻습니다.
        """
        for prd_se in PeriodType.PRIORITY_ORDER:
            prd_name = PeriodType.NAMES.get(prd_se, prd_se)
            logger.info(f"주기 '{prd_name}'({prd_se}) 시도: {tbl_id}")

            # 주기에 맞게 날짜 포맷 조정
            formatted_start = self._format_date_for_period(start_date, prd_se)
            formatted_end = self._format_date_for_period(end_date, prd_se)

            data = self.get_data_with_retry(
                org_id=org_id,
                tbl_id=tbl_id,
                start_date=formatted_start,
                end_date=formatted_end,
                prd_se=prd_se,
                itm_id=itm_id,
            )

            if data:
                logger.info(f"성공: 주기 '{prd_name}'에서 {len(data)}건 조회")
                return {
                    "data": data,
                    "period_type": prd_se,
                    "period_name": prd_name,
                }

        logger.error(f"모든 주기에서 데이터 조회 실패: {tbl_id}")
        return None

    def _format_date_for_period(self, date_str: str, period_type: str) -> str:
        """
        주기에 맞게 날짜 문자열을 포맷팅합니다.

        KOSIS API는 주기별로 다른 날짜 형식을 요구합니다:
        - 월간(M): YYYYMM (예: 202301)
        - 분기(Q): YYYYQQ (예: 202301 = 1분기)
        - 반기(S): YYYYHH (예: 202301 = 상반기)
        - 연간(Y): YYYY (예: 2023)
        - 다년(F): YYYY (예: 2023)
        - 부정기(IR): YYYYMMDD 또는 YYYY

        Args:
            date_str: 원본 날짜 문자열 (숫자만 추출됨)
            period_type: 주기 코드 (M, Q, S, Y, F, IR)

        Returns:
            포맷팅된 날짜 문자열

        Example:
            >>> data = StatisticsData()
            >>> data._format_date_for_period("2023", "M")
            "202301"
            >>> data._format_date_for_period("2023", "Y")
            "2023"
            >>> data._format_date_for_period("202312", "Y")
            "2023"
        """
        # 숫자만 추출
        date_clean = re.sub(r"[^0-9]", "", date_str)

        if period_type == "M":
            # 월간: YYYYMM
            if len(date_clean) >= 6:
                return date_clean[:6]
            else:
                return date_clean[:4] + "01"

        elif period_type == "Q":
            # 분기: YYYYQQ
            if len(date_clean) >= 6:
                return date_clean[:6]
            else:
                return date_clean[:4] + "01"

        elif period_type == "S":
            # 반기: YYYYHH
            if len(date_clean) >= 6:
                return date_clean[:6]
            else:
                return date_clean[:4] + "01"

        elif period_type in ("Y", "F"):
            # 연간/다년: YYYY
            return date_clean[:4]

        elif period_type == "IR":
            # 부정기: YYYYMMDD 또는 YYYY
            if len(date_clean) >= 8:
                return date_clean[:8]
            else:
                return date_clean[:4]

        else:
            return date_clean
