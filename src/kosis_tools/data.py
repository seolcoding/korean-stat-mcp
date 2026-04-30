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

from .base import KosisBaseClient, build_format_param
from .config import Endpoints, PeriodType

# PRD_SE 한글 → API 코드 변환에 PeriodType.from_korean() 사용

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
        - Rate Limit: 없음 (계정/IP 제한 없음)
        - 1회 호출당 최대: 40,000건 (셀 수 기준)
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
        obj_l3: Optional[str] = None,
        obj_l4: Optional[str] = None,
        obj_l5: Optional[str] = None,
        obj_l6: Optional[str] = None,
        obj_l7: Optional[str] = None,
        obj_l8: Optional[str] = None,
        itm_id: str = "ALL",
        *,
        new_est_prd_cnt: int | None = None,
        prd_interval: int | None = None,
        response_format: str | None = None,
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
            "format": build_format_param(response_format),  # type: ignore[arg-type]
            "orgId": org_id,
            "tblId": tbl_id,
            "objL1": obj_l1,
            "objL": obj_l1,  # 구 API 호환성 (일부 테이블은 objL 파라미터 필요)
            "itmId": itm_id,
            "prdSe": prd_se,
            "startPrdDe": start_date,
            "endPrdDe": end_date,
        }

        # 최신 N 시점 / 시점 간격 (Gap 1: KOSIS newEstPrdCnt, prdInterval)
        if new_est_prd_cnt is not None:
            params["newEstPrdCnt"] = str(new_est_prd_cnt)
        if prd_interval is not None:
            params["prdInterval"] = str(prd_interval)

        # objL2~objL8 추가 (값이 있는 경우만)
        obj_levels = [
            ("objL2", obj_l2),
            ("objL3", obj_l3),
            ("objL4", obj_l4),
            ("objL5", obj_l5),
            ("objL6", obj_l6),
            ("objL7", obj_l7),
            ("objL8", obj_l8),
        ]
        for param_name, param_value in obj_levels:
            if param_value:
                params[param_name] = param_value

        logger.debug(
            f"데이터 조회: {tbl_id}, 주기={prd_se}, 기간={start_date}~{end_date}"
        )

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

    def get_data_with_smart_retry(
        self,
        org_id: str,
        tbl_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        prd_se: Optional[str] = None,
        itm_id: str = "ALL",
    ) -> List[Dict[str, Any]]:
        """
        메타데이터 기반 스마트 데이터 조회.

        OBJ_VAR 메타데이터를 활용하여 올바른 objL 파라미터를 자동으로 구성합니다.
        KOSIS API에서 objL1은 필수 파라미터이며, 테이블에 따라 objL2~objL8도 필요할 수 있습니다.

        전략:
        1. OBJ_VAR 메타데이터 조회로 분류 구조 파악
        2. 각 분류 레벨에 대해 'ALL' 또는 첫 번째 값 사용
        3. 40,000셀 초과 시 더 제한적인 분류값으로 재시도
        4. 기간은 최신 데이터 위주로 제한

        Args:
            org_id: 기관 ID
            tbl_id: 테이블 ID
            start_date: 시작 기간 (None이면 메타데이터에서 자동 결정)
            end_date: 종료 기간 (None이면 메타데이터에서 자동 결정)
            prd_se: 주기 (None이면 메타데이터에서 자동 결정)
            itm_id: 항목 ID

        Returns:
            데이터 레코드 리스트
        """
        from .table_meta import TableMetadata

        meta = TableMetadata(self.config)

        # 1. 메타데이터로 기간 정보 조회
        prd_info = meta.get_prd_info(org_id, tbl_id)
        if not prd_info:
            logger.warning(f"메타데이터 조회 실패: {tbl_id}")
            # 메타데이터 없어도 사용자가 직접 기간 지정했으면 시도
            if start_date and end_date and prd_se:
                return self.get_data(
                    org_id, tbl_id, start_date, end_date, prd_se, itm_id=itm_id
                )
            return []

        # 첫 번째 주기 정보 사용 (보통 가장 세밀한 주기)
        info = prd_info[0]

        # prd_se 결정: 메타데이터의 한글 주기명을 API 코드로 변환
        korean_prd_se = info.get("PRD_SE", "년")
        actual_prd_se = prd_se or PeriodType.from_korean(korean_prd_se)
        logger.debug(f"PRD_SE 변환: '{korean_prd_se}' -> '{actual_prd_se}'")

        # 기간 결정
        def normalize_period(p: str, period_type: str = "Y") -> str:
            """
            기간 문자열을 API 형식으로 변환.

            KOSIS 메타데이터 형식:
            - 분기: "2025 3/4" → "202503" (Q3)
            - 반기: "2025 1/2" → "202501" (H1)
            - 월간: "2025.01" → "202501"
            - 연간: "2025" → "2025"
            """
            if not p:
                return p

            # 분기 형식: "YYYY Q/4" → "YYYYQQ"
            import re

            quarter_match = re.match(r"(\d{4})\s*(\d)/4", p)
            if quarter_match:
                year = quarter_match.group(1)
                quarter = quarter_match.group(2)
                return f"{year}{quarter.zfill(2)}"

            # 반기 형식: "YYYY H/2" → "YYYYHH"
            semi_match = re.match(r"(\d{4})\s*(\d)/2", p)
            if semi_match:
                year = semi_match.group(1)
                half = semi_match.group(2)
                return f"{year}{half.zfill(2)}"

            # 기존 형식: 점(.) 제거
            return p.replace(".", "")

        strt_prd = normalize_period(info.get("STRT_PRD_DE", ""))
        end_prd = normalize_period(info.get("END_PRD_DE", ""))

        if not strt_prd or not end_prd:
            logger.warning(f"기간 정보 없음: {tbl_id}")
            if start_date and end_date:
                actual_start = start_date
                actual_end = end_date
            else:
                return []
        else:
            actual_start, actual_end = self._determine_period_range(
                start_date, end_date, strt_prd, end_prd, actual_prd_se
            )

        logger.info(
            f"스마트 조회: {tbl_id}, 주기={actual_prd_se}, 기간={actual_start}~{actual_end}"
        )

        # 2. OBJ_VAR 메타데이터 조회 - 분류 구조 파악
        obj_vars = meta.get_obj_vars(org_id, tbl_id)
        obj_levels = len(obj_vars)
        logger.debug(f"분류 레벨 수: {obj_levels}")

        # 3. 분류 레벨에 맞는 retry 전략 실행
        result = self._execute_with_obj_retry(
            org_id, tbl_id, actual_start, actual_end, actual_prd_se, obj_vars, itm_id
        )

        if result:
            return result

        # 4. 반기(S) 실패 시 년간(Y) 폴백 시도
        if actual_prd_se == "S" and len(prd_info) > 1:
            # 메타데이터에서 년간 주기 정보 찾기
            yearly_info = next((p for p in prd_info if p.get("PRD_SE") == "년"), None)
            if yearly_info:
                yearly_start = normalize_period(yearly_info.get("STRT_PRD_DE", ""))
                yearly_end = normalize_period(yearly_info.get("END_PRD_DE", ""))
                if yearly_start and yearly_end:
                    # 최신 2년만 조회
                    try:
                        end_year = int(yearly_end[:4])
                        start_year = max(int(yearly_start[:4]), end_year - 1)
                        fallback_start = str(start_year)
                        fallback_end = str(end_year)
                    except (ValueError, IndexError):
                        fallback_start, fallback_end = yearly_start, yearly_end

                    logger.info(
                        f"반기→년간 폴백: {tbl_id}, 기간={fallback_start}~{fallback_end}"
                    )
                    result = self._execute_with_obj_retry(
                        org_id,
                        tbl_id,
                        fallback_start,
                        fallback_end,
                        "Y",
                        obj_vars,
                        itm_id,
                    )
                    if result:
                        return result

        # 5. OBJ 메타데이터 없는 테이블용 추가 전략 (월간/지자체 테이블 등)
        if obj_levels == 0:
            logger.debug(f"OBJ 메타데이터 없음, 추가 전략 시도: {tbl_id}")
            result = self._try_no_obj_metadata_strategies(
                org_id, tbl_id, actual_start, actual_end, actual_prd_se, itm_id
            )
            if result:
                return result

        return []

    def _determine_period_range(
        self,
        start_date: Optional[str],
        end_date: Optional[str],
        strt_prd: str,
        end_prd: str,
        prd_se: str,
    ) -> Tuple[str, str]:
        """기간 범위를 결정합니다."""
        if start_date and end_date:
            return start_date, end_date

        try:
            if prd_se == "Y" or prd_se == "F":
                end_year = int(end_prd[:4])
                start_year = max(int(strt_prd[:4]), end_year - 1)  # 최신 2년
                return str(start_year), str(end_year)
            elif prd_se == "M":
                # 월간은 최신 12개월
                end_year = int(end_prd[:4])
                end_month = int(end_prd[4:6]) if len(end_prd) >= 6 else 12
                start_year = end_year if end_month > 12 else end_year - 1
                start_month = (end_month - 11) % 12 or 12
                return f"{start_year}{start_month:02d}", end_prd
            elif prd_se == "Q":
                # 분기는 최신 4분기
                end_year = int(end_prd[:4])
                return f"{end_year - 1}01", end_prd
            else:
                # 기타 주기는 최신 2년
                end_year = int(end_prd[:4])
                start_year = max(int(strt_prd[:4]), end_year - 1)
                return str(start_year), end_prd[:4] if len(end_prd) >= 4 else end_prd
        except (ValueError, IndexError):
            return strt_prd, end_prd

    def _execute_with_obj_retry(
        self,
        org_id: str,
        tbl_id: str,
        start_date: str,
        end_date: str,
        prd_se: str,
        obj_vars: List[Dict[str, Any]],
        itm_id: str,
    ) -> List[Dict[str, Any]]:
        """
        OBJ_VAR 메타데이터 기반 retry 전략을 실행합니다.

        전략 순서:
        1. objL1만 ALL
        2. objL1~objL2 ALL
        3. objL1~objL3 ALL (점진적 확장)
        4. objL1~objL4 ALL
        5. 테이블명에서 분류 개수 추론 후 시도
        6. 공통 fallback 값 시도
        """
        obj_count = len(obj_vars)

        # 분류별 첫 번째 값 추출 (fallback용)
        first_values = self._extract_first_obj_values(obj_vars)
        logger.debug(f"분류 레벨 수: {obj_count}, 첫 번째 값들: {first_values}")

        # 전략 1~4: 점진적으로 objL 레벨 확장 (핵심 전략!)
        # 많은 테이블이 objL2, objL3, objL4까지 ALL이 필요함
        for max_level in range(1, 5):
            obj_params = {f"obj_l{i}": "ALL" for i in range(1, max_level + 1)}
            logger.debug(f"전략 {max_level} - objL1~objL{max_level} ALL: {obj_params}")
            data = self._try_get_data(
                org_id, tbl_id, start_date, end_date, prd_se, obj_params, itm_id
            )
            if data:
                return data

        # 전략 5: 메타데이터 기반 분류 개수 시도
        if obj_count > 0:
            obj_params = {f"obj_l{i + 1}": "ALL" for i in range(min(obj_count, 8))}
            logger.debug(f"전략 5 - 메타데이터 기반 {obj_count}개 분류: {obj_params}")
            data = self._try_get_data(
                org_id, tbl_id, start_date, end_date, prd_se, obj_params, itm_id
            )
            if data:
                return data

        # 전략 6: 기간 축소 + objL1~objL3
        try:
            reduced_start = end_date[:4] if len(end_date) >= 4 else end_date
            if reduced_start != start_date:
                logger.debug(f"전략 6 - 기간 축소: {reduced_start}~{end_date}")
                for max_level in [2, 3, 4]:
                    obj_params = {f"obj_l{i}": "ALL" for i in range(1, max_level + 1)}
                    data = self._try_get_data(
                        org_id,
                        tbl_id,
                        reduced_start,
                        end_date,
                        prd_se,
                        obj_params,
                        itm_id,
                    )
                    if data:
                        return data
        except (ValueError, IndexError):
            pass

        # 전략 7: 일반적인 fallback 값 시도 ('00'=전국, '0'=계 등)
        # 5년 주기(F) 테이블은 특히 obj_l1='00'만으로 성공하는 경우 많음
        common_fallbacks = ["00", "0", "T", "1"]
        for fallback in common_fallbacks:
            # obj_l1만 fallback (5년 주기 등 단순 테이블용)
            obj_params = {"obj_l1": fallback}
            logger.debug(f"전략 7a - objL1='{fallback}' 단독")
            data = self._try_get_data(
                org_id, tbl_id, start_date, end_date, prd_se, obj_params, itm_id
            )
            if data:
                return data

            # obj_l1=fallback + objL2~3 ALL
            logger.debug(f"전략 7b - objL1='{fallback}' + objL2~3 ALL")
            for max_level in [2, 3]:
                obj_params = {"obj_l1": fallback}
                for i in range(2, max_level + 1):
                    obj_params[f"obj_l{i}"] = "ALL"
                data = self._try_get_data(
                    org_id, tbl_id, start_date, end_date, prd_se, obj_params, itm_id
                )
                if data:
                    return data

        # 전략 8: objL5~objL8까지 확장 (드문 케이스)
        for max_level in range(5, 9):
            obj_params = {f"obj_l{i}": "ALL" for i in range(1, max_level + 1)}
            logger.debug(f"전략 8 - objL1~objL{max_level} ALL (확장)")
            data = self._try_get_data(
                org_id, tbl_id, start_date, end_date, prd_se, obj_params, itm_id
            )
            if data:
                return data

        logger.warning(f"모든 전략 실패: {tbl_id}")
        return []

    def _extract_first_obj_values(
        self, obj_vars: List[Dict[str, Any]]
    ) -> Dict[int, str]:
        """OBJ_VAR 메타데이터에서 각 분류의 첫 번째 값을 추출합니다."""
        first_values: Dict[int, str] = {}

        for obj in obj_vars:
            try:
                level = int(obj.get("OBJ_LV", 0))
                obj_id = obj.get("OBJ_ID", "")
                if level > 0 and obj_id:
                    # OBJ_ID에서 첫 번째 값 추출 (예: "ITEM" -> 사용)
                    # 실제 분류값은 별도 API 호출 필요하지만, OBJ_ID를 힌트로 사용
                    first_values[level] = obj_id
            except (ValueError, TypeError):
                continue

        return first_values

    def _try_no_obj_metadata_strategies(
        self,
        org_id: str,
        tbl_id: str,
        start_date: str,
        end_date: str,
        prd_se: str,
        itm_id: str,
    ) -> List[Dict[str, Any]]:
        """
        OBJ 메타데이터가 없는 테이블을 위한 추가 전략.

        일부 지자체 테이블(DT_B* 등)은 OBJ 메타데이터 API에서 조회되지 않지만
        실제 API 호출 시 objL 파라미터가 필요합니다.

        전략:
        1. 지역 코드 기반 objL1 시도 (지자체 테이블)
        2. 연령/성별 분류 시도
        3. 기간 단축 후 재시도
        """
        # 지자체 테이블용 지역 코드 (부산=26, 서울=11, 등)
        region_codes = {
            "202": ["26"],  # 부산광역시
            "201": ["11"],  # 서울특별시
            "203": ["27"],  # 대구광역시
            "204": ["28"],  # 인천광역시
            "205": ["29"],  # 광주광역시
            "206": ["30"],  # 대전광역시
            "207": ["31"],  # 울산광역시
        }

        # 전략 1: 지자체 테이블 - 지역 코드 + 연령/성별 분류
        if org_id in region_codes:
            for region_code in region_codes[org_id]:
                # objL1=지역코드, objL2=연령(ALL), objL3=성별(ALL)
                test_params = [
                    {"obj_l1": region_code, "obj_l2": "ALL", "obj_l3": "ALL"},
                    {"obj_l1": region_code, "obj_l2": "ALL"},
                    {"obj_l1": "ALL", "obj_l2": region_code, "obj_l3": "ALL"},
                ]
                for params in test_params:
                    logger.debug(f"지자체 전략: {params}")
                    data = self._try_get_data(
                        org_id, tbl_id, start_date, end_date, prd_se, params, itm_id
                    )
                    if data:
                        return data

        # 전략 2: 일반적인 분류 코드 시도
        common_codes = [
            {"obj_l1": "00", "obj_l2": "ALL", "obj_l3": "ALL"},  # 전국/전체
            {"obj_l1": "T", "obj_l2": "ALL", "obj_l3": "ALL"},  # Total
            {"obj_l1": "0", "obj_l2": "ALL", "obj_l3": "ALL"},  # 계
            {"obj_l1": "ALL", "obj_l2": "00", "obj_l3": "ALL"},
            {"obj_l1": "ALL", "obj_l2": "0", "obj_l3": "ALL"},
        ]
        for params in common_codes:
            logger.debug(f"일반 분류 전략: {params}")
            data = self._try_get_data(
                org_id, tbl_id, start_date, end_date, prd_se, params, itm_id
            )
            if data:
                return data

        # 전략 3: 기간 단축 (최신 1개월/1분기만)
        try:
            if prd_se == "M" and len(end_date) >= 6:
                short_start = end_date  # 마지막 1개월만
                for max_level in [2, 3, 4]:
                    params = {f"obj_l{i}": "ALL" for i in range(1, max_level + 1)}
                    logger.debug(f"기간 단축 전략 (1개월): {short_start}")
                    data = self._try_get_data(
                        org_id, tbl_id, short_start, end_date, prd_se, params, itm_id
                    )
                    if data:
                        return data
        except (ValueError, IndexError):
            pass

        return []

    def _try_get_data(
        self,
        org_id: str,
        tbl_id: str,
        start_date: str,
        end_date: str,
        prd_se: str,
        obj_params: Dict[str, str],
        itm_id: str,
    ) -> List[Dict[str, Any]]:
        """주어진 파라미터로 데이터 조회를 시도합니다."""
        try:
            # obj_params를 get_data 호출 형식으로 변환 (obj_l1 ~ obj_l8 지원)
            obj_l1 = obj_params.get("obj_l1", "ALL")
            obj_l2 = obj_params.get("obj_l2")
            obj_l3 = obj_params.get("obj_l3")
            obj_l4 = obj_params.get("obj_l4")
            obj_l5 = obj_params.get("obj_l5")
            obj_l6 = obj_params.get("obj_l6")
            obj_l7 = obj_params.get("obj_l7")
            obj_l8 = obj_params.get("obj_l8")

            data = self.get_data(
                org_id=org_id,
                tbl_id=tbl_id,
                start_date=start_date,
                end_date=end_date,
                prd_se=prd_se,
                obj_l1=obj_l1,
                obj_l2=obj_l2,
                obj_l3=obj_l3,
                obj_l4=obj_l4,
                obj_l5=obj_l5,
                obj_l6=obj_l6,
                obj_l7=obj_l7,
                obj_l8=obj_l8,
                itm_id=itm_id,
            )
            return data if data else []
        except Exception as e:
            logger.debug(f"데이터 조회 실패: {e}")
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

    def get_data_paginated(
        self,
        org_id: str,
        tbl_id: str,
        start_date: str,
        end_date: str,
        prd_se: str = "Y",
        obj_l1: str = "ALL",
        obj_l2: Optional[str] = None,
        itm_id: str = "ALL",
        max_records_per_call: int = 35000,
    ) -> List[Dict[str, Any]]:
        """
        대용량 데이터를 기간 분할하여 조회합니다.

        KOSIS API는 1회 호출당 최대 40,000건까지만 반환합니다.
        이 메서드는 기간을 자동으로 분할하여 여러 번 호출하고
        결과를 병합하여 반환합니다.

        Args:
            org_id: 기관 ID
            tbl_id: 테이블 ID
            start_date: 시작 기간 (YYYY 형식)
            end_date: 종료 기간 (YYYY 형식)
            prd_se: 수록주기 (기본: "Y")
            obj_l1: 분류항목 1 (기본: "ALL")
            obj_l2: 분류항목 2 (기본: None)
            itm_id: 항목 ID (기본: "ALL")
            max_records_per_call: 1회 호출당 최대 레코드 수 (기본: 35,000)
                                  40,000건 제한에 여유를 두어 35,000으로 설정

        Returns:
            병합된 전체 데이터 레코드 목록

        Example:
            >>> data = StatisticsData()
            >>> # 50년치 대용량 데이터 조회
            >>> records = data.get_data_paginated(
            ...     org_id="101",
            ...     tbl_id="DT_1B040A3",
            ...     start_date="1970",
            ...     end_date="2023",
            ...     prd_se="Y"
            ... )
            >>> print(f"총 {len(records)}건 조회됨")

        Note:
            - 연간(Y) 데이터 기준으로 기간을 분할합니다.
            - 월간(M) 데이터는 년도 단위로 분할됩니다.
            - 각 분할 호출 사이에 rate limiting이 적용됩니다.
        """
        # 먼저 1회 호출 시도
        first_result = self.get_data(
            org_id=org_id,
            tbl_id=tbl_id,
            start_date=start_date,
            end_date=end_date,
            prd_se=prd_se,
            obj_l1=obj_l1,
            obj_l2=obj_l2,
            itm_id=itm_id,
        )

        # 40,000건 미만이면 그대로 반환
        if len(first_result) < max_records_per_call:
            if len(first_result) >= 35000:
                logger.warning(
                    f"결과가 {len(first_result)}건으로 40,000건 제한에 근접합니다. "
                    "일부 데이터가 누락되었을 수 있습니다."
                )
            return first_result

        # 40,000건에 근접하면 기간 분할 필요
        logger.info(
            f"결과가 {len(first_result)}건으로 40,000건 제한에 도달. "
            "기간을 분할하여 재조회합니다."
        )

        return self._fetch_with_period_split(
            org_id=org_id,
            tbl_id=tbl_id,
            start_date=start_date,
            end_date=end_date,
            prd_se=prd_se,
            obj_l1=obj_l1,
            obj_l2=obj_l2,
            itm_id=itm_id,
            max_records_per_call=max_records_per_call,
        )

    def _fetch_with_period_split(
        self,
        org_id: str,
        tbl_id: str,
        start_date: str,
        end_date: str,
        prd_se: str,
        obj_l1: str,
        obj_l2: Optional[str],
        itm_id: str,
        max_records_per_call: int,
    ) -> List[Dict[str, Any]]:
        """
        기간을 분할하여 데이터를 조회하고 병합합니다.

        Args:
            (get_data_paginated와 동일)

        Returns:
            병합된 전체 데이터 레코드 목록
        """
        all_data: List[Dict[str, Any]] = []

        # 연도 추출
        start_year = int(re.sub(r"[^0-9]", "", start_date)[:4])
        end_year = int(re.sub(r"[^0-9]", "", end_date)[:4])

        # 주기에 따른 분할 단위 결정
        if prd_se == "M":
            # 월간: 1년씩 분할
            chunk_years = 1
        elif prd_se == "Q":
            # 분기: 2년씩 분할
            chunk_years = 2
        elif prd_se == "S":
            # 반기: 3년씩 분할
            chunk_years = 3
        else:
            # 연간/다년/부정기: 10년씩 분할
            chunk_years = 10

        current_start = start_year
        chunk_num = 1

        while current_start <= end_year:
            current_end = min(current_start + chunk_years - 1, end_year)

            # 날짜 형식 조정
            chunk_start_str = self._format_date_for_period(str(current_start), prd_se)
            chunk_end_str = self._format_date_for_period(str(current_end), prd_se)

            # 종료일이 월간/분기인 경우 12월/4분기로 설정
            if prd_se == "M":
                chunk_end_str = f"{current_end}12"
            elif prd_se == "Q":
                chunk_end_str = f"{current_end}04"
            elif prd_se == "S":
                chunk_end_str = f"{current_end}02"

            logger.info(f"분할 조회 #{chunk_num}: {chunk_start_str} ~ {chunk_end_str}")

            chunk_data = self.get_data(
                org_id=org_id,
                tbl_id=tbl_id,
                start_date=chunk_start_str,
                end_date=chunk_end_str,
                prd_se=prd_se,
                obj_l1=obj_l1,
                obj_l2=obj_l2,
                itm_id=itm_id,
            )

            if chunk_data:
                all_data.extend(chunk_data)
                logger.info(f"분할 #{chunk_num}: {len(chunk_data)}건 조회됨")

                # 이 분할에서도 한계에 도달하면 더 작게 분할
                if len(chunk_data) >= max_records_per_call:
                    logger.warning(
                        f"분할 #{chunk_num}에서도 {len(chunk_data)}건으로 한계 도달. "
                        "더 작은 기간으로 분할이 필요할 수 있습니다."
                    )

            current_start = current_end + 1
            chunk_num += 1

        # 중복 제거 (PRD_DE + 모든 분류 키 기준)
        unique_data = self._deduplicate_records(all_data)

        logger.info(
            f"분할 조회 완료: 총 {len(unique_data)}건 (중복 제거 전: {len(all_data)}건)"
        )
        return unique_data

    def _deduplicate_records(
        self, records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        데이터 레코드에서 중복을 제거합니다.

        PRD_DE, C1~C8, ITM_ID 조합을 키로 사용하여 중복을 판별합니다.

        Args:
            records: 데이터 레코드 목록

        Returns:
            중복이 제거된 레코드 목록
        """
        seen = set()
        unique = []

        for record in records:
            # 고유 키 생성
            key_parts = [
                record.get("PRD_DE", ""),
                record.get("ITM_ID", ""),
            ]
            # 분류 코드 추가 (C1 ~ C8)
            for i in range(1, 9):
                key_parts.append(record.get(f"C{i}", ""))

            key = tuple(key_parts)

            if key not in seen:
                seen.add(key)
                unique.append(record)

        return unique
