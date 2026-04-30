"""
KOSIS 통계설명 모듈.

이 모듈은 KOSIS OpenAPI의 statisticsExplData.do 엔드포인트를 사용하여
통계조사의 상세 메타데이터(조사목적, 조사주기, 조사대상, 연락처 등)를 조회합니다.

주요 기능:
    - 통계조사 상세 설명 조회
    - 조사목적, 조사대상, 조사항목 등 메타데이터 조회
    - LLM 컨텍스트 생성용 상세 정보 제공

Example:
    기본 사용:
    >>> from kosis_tools.stats_explanation import StatsExplanation
    >>> expl = StatsExplanation()
    >>> info = expl.get_by_stat_id("1962009")  # 가계동향조사
    >>> print(info["statsNm"])
    가계동향조사

    테이블 ID로 조회:
    >>> info = expl.get_by_table("101", "DT_1L9H001")
    >>> print(info.get("writingPurps", ""))
    가구에 대한 가계수지 실태를 파악하여...

API Reference:
    - Endpoint: statisticsExplData.do
    - Method: getList
    - metaItm: All (전체) 또는 개별 항목
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .base import KosisBaseClient, build_format_param
from .config import Endpoints

logger = logging.getLogger(__name__)


class MetaItem:
    """
    통계설명 메타 항목 상수.

    metaItm 파라미터에 사용되는 항목 코드입니다.
    ALL을 사용하면 모든 항목을 조회합니다.

    Example:
        >>> expl = StatsExplanation()
        >>> info = expl.get_by_stat_id("1962009", meta_items=[MetaItem.STATS_NM, MetaItem.WRITING_PURPS])
    """

    ALL = "All"  # 전체 항목
    STATS_NM = "statsNm"  # 조사명
    STATS_KIND = "statsKind"  # 작성유형
    STATS_END = "statsEnd"  # 통계종류
    STATS_CONTINUE = "statsContinue"  # 계속여부
    BASIS_LAW = "basisLaw"  # 법적근거
    WRITING_PURPS = "writingPurps"  # 조사목적
    EXAMIN_PD = "examinPd"  # 조사기간
    STATS_PERIOD = "statsPeriod"  # 조사주기
    WRITING_SYSTEM = "writingSystem"  # 조사체계
    WRITING_TEL = "writingTel"  # 연락처
    STATS_FIELD = "statsField"  # 통계(활용)분야·실태
    EXAMIN_OBJ_RANGE = "examinObjrange"  # 조사 대상범위
    EXAMIN_OBJ_AREA = "examinObjArea"  # 조사 대상지역
    JOSA_UNIT = "josaUnit"  # 조사단위 및 조사대상규모
    APPLY_GROUP = "applyGroup"  # 적용분류
    JOSA_ITM = "josaItm"  # 조사항목
    PUB_PERIOD = "pubPeriod"  # 공표주기
    PUB_EXTENT = "pubExtent"  # 공표범위
    PUB_DATE = "pubDate"  # 공표시기
    PUBLICT_MTH = "publictMth"  # 공표방법 및 URL
    EXAMIN_TRGET_PD = "examinTrgetPd"  # 조사대상기간 및 조사기준시점
    DATA_USER_NOTE = "dataUserNote"  # 자료이용시 유의사항
    MAIN_TERM_EXPL = "mainTermExpl"  # 주요 용어해설
    DATA_COLLECT_MTH = "dataCollectMth"  # 자료 수집방법
    EXAMIN_HISTORY = "examinHistory"  # 조사연혁
    CONFM_NO = "confmNo"  # 승인번호
    CONFM_DT = "confmDt"  # 승인일자


class StatsExplanation(KosisBaseClient):
    """
    KOSIS 통계설명 클라이언트.

    통계조사의 상세 메타데이터를 조회합니다.
    조사목적, 조사주기, 조사대상 등 LLM 컨텍스트 생성에 필요한
    상세 정보를 제공합니다.

    이 클래스는 KosisBaseClient를 상속받아 HTTP 요청, rate limiting,
    에러 핸들링 등의 공통 기능을 사용합니다.

    Attributes:
        config: KosisConfig 인스턴스. API 키, 타임아웃 등 설정.

    Args:
        config: KosisConfig 인스턴스. None이면 환경변수에서 기본 설정 로드.

    Example:
        >>> expl = StatsExplanation()
        >>> info = expl.get_by_stat_id("1962009")  # 가계동향조사
        >>> print(f"조사명: {info['statsNm']}")
        >>> print(f"조사주기: {info['statsPeriod']}")
        조사명: 가계동향조사
        조사주기: 분기

    API Reference:
        - Endpoint: statisticsExplData.do
        - Method: getList
        - 응답 형식: 비표준 JSON (키에 따옴표 없음)
    """

    def get_by_stat_id(
        self,
        stat_id: str,
        meta_items: Optional[List[str]] = None,
        *,
        response_format: str | None = None,
    ) -> Optional[Dict[str, Any]]:
        """
        통계 ID로 통계설명을 조회합니다.

        통계 ID(statId)를 알고 있는 경우 직접 조회할 수 있습니다.
        통계 ID는 검색 결과나 목록 조회에서 STAT_ID 필드로 확인할 수 있습니다.

        Args:
            stat_id: 통계 ID.
                     예: "1962001" (인구총조사), "1962009" (가계동향조사)
                     검색 결과의 STAT_ID 필드 값.

            meta_items: 조회할 메타 항목 목록 (선택사항).
                        예: [MetaItem.STATS_NM, MetaItem.WRITING_PURPS]
                        None이면 전체 항목(All) 조회.

        Returns:
            통계설명 정보 딕셔너리:
            {
                "statsNm": "가계동향조사",           # 조사명
                "statsKind": "조사통계",            # 작성유형
                "statsPeriod": "분기",              # 조사주기
                "confmNo": "101006",               # 승인번호
                "writingPurps": "가구에 대한...",   # 조사목적
                "examinObjrange": "전국 가구",      # 조사대상범위
                "examinObjArea": "전국",           # 조사대상지역
                "josaItm": "소득, 지출, ...",       # 조사항목
                "pubPeriod": "분기",               # 공표주기
                ...
            }

            결과가 없으면 None 반환.

        Example:
            >>> expl = StatsExplanation()
            >>> # 전체 항목 조회
            >>> info = expl.get_by_stat_id("1962009")
            >>> print(info["statsNm"])
            가계동향조사
            >>> # 특정 항목만 조회
            >>> info = expl.get_by_stat_id("1962009", [MetaItem.STATS_NM, MetaItem.STATS_PERIOD])

        API Reference:
            - Endpoint: statisticsExplData.do
            - Method: getList
            - 파라미터: statId, metaItm

        Note:
            - stat_id가 빈 문자열이면 None 반환
            - 존재하지 않는 통계 ID는 None 반환
        """
        if not stat_id or not stat_id.strip():
            logger.warning("통계 ID가 비어있습니다.")
            return None

        # metaItm 설정
        meta_itm = MetaItem.ALL
        if meta_items:
            meta_itm = ",".join(meta_items)

        params: Dict[str, Any] = {
            "method": "getList",
            "format": build_format_param(response_format),  # type: ignore[arg-type]
            "statId": stat_id.strip(),
            "metaItm": meta_itm,
        }

        logger.info(f"통계설명 조회: stat_id={stat_id}")

        result = self._request("GET", Endpoints.STATISTICS_EXPLANATION, params)

        if result is None:
            return None

        if isinstance(result, list) and len(result) > 0:
            return result[0]
        elif isinstance(result, dict):
            return result

        return None

    def get_by_table(
        self,
        org_id: str,
        tbl_id: str,
        meta_items: Optional[List[str]] = None,
        *,
        response_format: str | None = None,
    ) -> Optional[Dict[str, Any]]:
        """
        기관 ID와 테이블 ID로 통계설명을 조회합니다.

        통계 ID를 모르는 경우 기관 ID와 테이블 ID로 조회할 수 있습니다.
        검색 결과에서 ORG_ID와 TBL_ID를 사용하여 조회합니다.

        Args:
            org_id: 기관 ID.
                    예: "101" (통계청), "154" (한국은행)

            tbl_id: 통계표 ID.
                    예: "DT_1B040A3", "DT_1L9H001"

            meta_items: 조회할 메타 항목 목록 (선택사항).
                        None이면 전체 항목(All) 조회.

        Returns:
            통계설명 정보 딕셔너리. 구조는 get_by_stat_id() 반환값과 동일.
            결과가 없으면 None 반환.

        Example:
            >>> expl = StatsExplanation()
            >>> info = expl.get_by_table("101", "DT_1L9H001")
            >>> if info:
            ...     print(f"조사명: {info['statsNm']}")
            ...     print(f"목적: {info.get('writingPurps', 'N/A')[:100]}...")
            조사명: 가계동향조사
            목적: 가구에 대한 가계수지 실태를 파악하여...

        API Reference:
            - Endpoint: statisticsExplData.do
            - Method: getList
            - 파라미터: orgId, tblId, metaItm

        Note:
            - org_id나 tbl_id가 빈 문자열이면 None 반환
            - API가 statId 또는 orgId+tblId 조합 중 하나를 요구함
        """
        if not org_id or not org_id.strip():
            logger.warning("기관 ID가 비어있습니다.")
            return None

        if not tbl_id or not tbl_id.strip():
            logger.warning("테이블 ID가 비어있습니다.")
            return None

        # metaItm 설정
        meta_itm = MetaItem.ALL
        if meta_items:
            meta_itm = ",".join(meta_items)

        params: Dict[str, Any] = {
            "method": "getList",
            "format": build_format_param(response_format),  # type: ignore[arg-type]
            "orgId": org_id.strip(),
            "tblId": tbl_id.strip(),
            "metaItm": meta_itm,
        }

        logger.info(f"통계설명 조회: org_id={org_id}, tbl_id={tbl_id}")

        result = self._request("GET", Endpoints.STATISTICS_EXPLANATION, params)

        if result is None:
            return None

        if isinstance(result, list) and len(result) > 0:
            return result[0]
        elif isinstance(result, dict):
            return result

        return None

    def get_survey_purpose(
        self,
        stat_id: Optional[str] = None,
        org_id: Optional[str] = None,
        tbl_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        조사목적만 간단히 조회합니다.

        LLM 프롬프트나 컨텍스트에 조사목적만 필요한 경우
        이 메서드를 사용하여 효율적으로 조회합니다.

        Args:
            stat_id: 통계 ID (선택).
            org_id: 기관 ID (선택).
            tbl_id: 테이블 ID (선택).

            stat_id 또는 (org_id + tbl_id) 조합 중 하나는 필수.

        Returns:
            조사목적 문자열.
            결과가 없으면 None 반환.

        Example:
            >>> expl = StatsExplanation()
            >>> purpose = expl.get_survey_purpose(stat_id="1962009")
            >>> print(purpose[:100])
            가구에 대한 가계수지 실태를 파악하여 국민의 소득과...

            >>> purpose = expl.get_survey_purpose(org_id="101", tbl_id="DT_1L9H001")
            >>> print(purpose[:100])

        Note:
            - writingPurps 항목만 조회하여 API 응답 크기 최소화
        """
        meta_items = [MetaItem.WRITING_PURPS]

        if stat_id:
            info = self.get_by_stat_id(stat_id, meta_items)
        elif org_id and tbl_id:
            info = self.get_by_table(org_id, tbl_id, meta_items)
        else:
            logger.warning("stat_id 또는 (org_id + tbl_id) 조합이 필요합니다.")
            return None

        if info:
            return info.get("writingPurps")

        return None

    def get_key_terms(
        self,
        stat_id: Optional[str] = None,
        org_id: Optional[str] = None,
        tbl_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        주요 용어해설만 간단히 조회합니다.

        통계 데이터 해석에 필요한 주요 용어 정의를 조회합니다.

        Args:
            stat_id: 통계 ID (선택).
            org_id: 기관 ID (선택).
            tbl_id: 테이블 ID (선택).

            stat_id 또는 (org_id + tbl_id) 조합 중 하나는 필수.

        Returns:
            주요 용어해설 문자열.
            결과가 없으면 None 반환.

        Example:
            >>> expl = StatsExplanation()
            >>> terms = expl.get_key_terms(stat_id="1962009")
            >>> if terms:
            ...     print(terms[:200])

        Note:
            - mainTermExpl 항목만 조회하여 API 응답 크기 최소화
        """
        meta_items = [MetaItem.MAIN_TERM_EXPL]

        if stat_id:
            info = self.get_by_stat_id(stat_id, meta_items)
        elif org_id and tbl_id:
            info = self.get_by_table(org_id, tbl_id, meta_items)
        else:
            logger.warning("stat_id 또는 (org_id + tbl_id) 조합이 필요합니다.")
            return None

        if info:
            return info.get("mainTermExpl")

        return None

    def get_data_notes(
        self,
        stat_id: Optional[str] = None,
        org_id: Optional[str] = None,
        tbl_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        자료이용 시 유의사항만 간단히 조회합니다.

        데이터 해석 시 주의해야 할 사항을 조회합니다.

        Args:
            stat_id: 통계 ID (선택).
            org_id: 기관 ID (선택).
            tbl_id: 테이블 ID (선택).

            stat_id 또는 (org_id + tbl_id) 조합 중 하나는 필수.

        Returns:
            자료이용 유의사항 문자열.
            결과가 없으면 None 반환.

        Example:
            >>> expl = StatsExplanation()
            >>> notes = expl.get_data_notes(stat_id="1962009")
            >>> if notes:
            ...     print(notes[:200])

        Note:
            - dataUserNote 항목만 조회하여 API 응답 크기 최소화
        """
        meta_items = [MetaItem.DATA_USER_NOTE]

        if stat_id:
            info = self.get_by_stat_id(stat_id, meta_items)
        elif org_id and tbl_id:
            info = self.get_by_table(org_id, tbl_id, meta_items)
        else:
            logger.warning("stat_id 또는 (org_id + tbl_id) 조합이 필요합니다.")
            return None

        if info:
            return info.get("dataUserNote")

        return None

    def get_llm_context(
        self,
        stat_id: Optional[str] = None,
        org_id: Optional[str] = None,
        tbl_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        LLM 컨텍스트 생성에 필요한 핵심 정보를 조회합니다.

        AI 모델이 통계 데이터를 이해하고 해석하는 데 필요한
        핵심 메타데이터를 한 번에 조회합니다.

        Args:
            stat_id: 통계 ID (선택).
            org_id: 기관 ID (선택).
            tbl_id: 테이블 ID (선택).

            stat_id 또는 (org_id + tbl_id) 조합 중 하나는 필수.

        Returns:
            LLM 컨텍스트용 딕셔너리:
            {
                "name": "가계동향조사",           # 조사명
                "kind": "조사통계",              # 작성유형
                "period": "분기",               # 조사주기
                "purpose": "가구에 대한...",     # 조사목적
                "target": "전국 가구",           # 조사대상
                "area": "전국",                 # 조사지역
                "items": "소득, 지출, ...",      # 조사항목
                "terms": "...",                 # 주요 용어
                "notes": "...",                 # 유의사항
                "approval_no": "101006"         # 승인번호
            }

            결과가 없으면 None 반환.

        Example:
            >>> expl = StatsExplanation()
            >>> ctx = expl.get_llm_context(stat_id="1962009")
            >>> if ctx:
            ...     print(f"조사: {ctx['name']}")
            ...     print(f"목적: {ctx['purpose'][:100]}...")
            ...     print(f"주기: {ctx['period']}")
            조사: 가계동향조사
            목적: 가구에 대한 가계수지 실태를 파악하여...
            주기: 분기

        Note:
            - LLM 프롬프트에 직접 사용 가능한 구조화된 정보 제공
            - 필요한 항목만 선택적으로 조회하여 효율적
        """
        meta_items = [
            MetaItem.STATS_NM,
            MetaItem.STATS_KIND,
            MetaItem.STATS_PERIOD,
            MetaItem.WRITING_PURPS,
            MetaItem.EXAMIN_OBJ_RANGE,
            MetaItem.EXAMIN_OBJ_AREA,
            MetaItem.JOSA_ITM,
            MetaItem.MAIN_TERM_EXPL,
            MetaItem.DATA_USER_NOTE,
            MetaItem.CONFM_NO,
        ]

        if stat_id:
            info = self.get_by_stat_id(stat_id, meta_items)
        elif org_id and tbl_id:
            info = self.get_by_table(org_id, tbl_id, meta_items)
        else:
            logger.warning("stat_id 또는 (org_id + tbl_id) 조합이 필요합니다.")
            return None

        if not info:
            return None

        return {
            "name": info.get("statsNm"),
            "kind": info.get("statsKind"),
            "period": info.get("statsPeriod"),
            "purpose": info.get("writingPurps"),
            "target": info.get("examinObjrange"),
            "area": info.get("examinObjArea"),
            "items": info.get("josaItm"),
            "terms": info.get("mainTermExpl"),
            "notes": info.get("dataUserNote"),
            "approval_no": info.get("confmNo"),
        }
