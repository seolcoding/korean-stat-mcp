"""
KOSIS 통계주요지표 API 클라이언트.

KOSIS에서 제공하는 주요 통계지표를 조회하는 API 클라이언트입니다.
지표 ID, 지표명, 목록, 수록주기 등으로 통계지표를 검색하고
상세 데이터를 조회할 수 있습니다.

주요 기능:
    - 지표 고유번호별 설명 조회 (pkNumberService.do)
    - 지표명별 설명 조회 (indExpService.do)
    - 목록별 지표 조회 (indiListService.do)
    - 지표명/고유번호별 목록 조회 (indListSearchRequest.do)
    - 고유번호별 지표 상세 조회 (indIdDetailSearchRequest.do)
    - 수록주기별 목록 조회 (prListSearchRequest.do)

Example:
    >>> from kosis_tools import KeyIndicators
    >>> client = KeyIndicators()
    >>> # 지표명으로 검색
    >>> results = client.search_by_name("실업률")
    >>> # 고유번호로 상세 데이터 조회
    >>> detail = client.get_detail(jipyo_id="12345", start_prd_de="2020", end_prd_de="2023")
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from .base import KosisBaseClient
from .config import KosisConfig


class IndicatorEndpoint(str, Enum):
    """통계주요지표 API 엔드포인트."""

    PK_NUMBER = "pkNumberService.do"  # 지표 고유번호별 설명
    IND_EXP = "indExpService.do"  # 지표명별 설명
    INDI_LIST = "indiListService.do"  # 목록별 지표
    IND_LIST_SEARCH = "indListSearchRequest.do"  # 지표명/고유번호별 목록
    IND_ID_DETAIL = "indIdDetailSearchRequest.do"  # 고유번호별 상세
    PR_LIST_SEARCH = "prListSearchRequest.do"  # 수록주기별 목록


@dataclass
class IndicatorExplanation:
    """지표 설명 정보."""

    jipyo_id: str  # 지표 ID
    jipyo_nm: str  # 지표명
    title: str  # 설명자료 제목
    concept: str  # 개념

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "IndicatorExplanation":
        """API 응답에서 객체 생성."""
        return cls(
            jipyo_id=str(data.get("statJipyoId", "")),
            jipyo_nm=data.get("statJipyoNm", ""),
            title=data.get("jipyoExplan", ""),
            concept=data.get("jipyoExplan1", ""),
        )


@dataclass
class IndicatorListItem:
    """목록별 지표 정보."""

    list_id: str  # 세부목록 ID
    list_nm: str  # 세부부문명
    jipyo_id: str  # 지표 ID
    jipyo_nm: str  # 지표명
    unit: str  # 단위
    area_type: str  # 지역구분명
    period_type: str  # 수록주기명
    start_period: str  # 수록시작시점
    end_period: str  # 수록종료시점
    period_count: int  # 수록시점개수
    period: str  # 시점
    rep_jipyo_id: Optional[str] = None  # 대표지표 ID
    rep_jipyo_nm: Optional[str] = None  # 대표지표명
    rep_jipyo_url: Optional[str] = None  # 대표지표 URL
    explain_url: Optional[str] = None  # 지표설명 URL

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "IndicatorListItem":
        """API 응답에서 객체 생성."""
        return cls(
            list_id=data.get("listId", ""),
            list_nm=data.get("listNm", ""),
            jipyo_id=str(data.get("statJipyoId", "")),
            jipyo_nm=data.get("statJipyoNm", ""),
            unit=data.get("unit", ""),
            area_type=data.get("areaTypeName", ""),
            period_type=data.get("prdSeName", ""),
            start_period=data.get("strtPrdDe", ""),
            end_period=data.get("endPrdDe", ""),
            period_count=int(data.get("rn", 0)),
            period=data.get("prdDe", ""),
            rep_jipyo_id=str(data.get("repJipyoId"))
            if data.get("repJipyoId")
            else None,
            rep_jipyo_nm=data.get("repJipyoNm"),
            rep_jipyo_url=data.get("repJipyoUrl"),
            explain_url=data.get("explainUrl"),
        )


@dataclass
class IndicatorSearchResult:
    """지표 검색 결과."""

    jipyo_id: str  # 지표 ID
    jipyo_nm: str  # 지표명
    unit: str  # 단위
    area_type: str  # 지역구분명
    period_type: str  # 수록주기명
    start_period: str  # 수록시작시점
    end_period: str  # 수록종료시점
    period_count: int  # 수록시점개수
    period: str  # 종료시점+주기명

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "IndicatorSearchResult":
        """API 응답에서 객체 생성."""
        return cls(
            jipyo_id=str(data.get("statJipyoId", "")),
            jipyo_nm=data.get("statJipyoNm", ""),
            unit=data.get("unit", ""),
            area_type=data.get("areaTypeName", ""),
            period_type=data.get("prdSeName", ""),
            start_period=data.get("strtPrdDe", ""),
            end_period=data.get("endPrdDe", ""),
            period_count=int(data.get("rn", 0)),
            period=data.get("prdDe", ""),
        )


@dataclass
class IndicatorDetailData:
    """지표 상세 데이터."""

    jipyo_id: str  # 지표 ID
    jipyo_nm: str  # 지표명
    period_type: str  # 수록주기
    period: str  # 시점
    item_nm: str  # 항목
    value: Optional[float]  # 통계수치

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "IndicatorDetailData":
        """API 응답에서 객체 생성."""
        # 값이 None이거나 빈 문자열인 경우 처리
        val = data.get("val")
        value = None
        if val is not None and val != "":
            try:
                value = float(val)
            except (ValueError, TypeError):
                value = None

        return cls(
            jipyo_id=str(data.get("statJipyoId", "")),
            jipyo_nm=data.get("statJipyoNm", ""),
            period_type=data.get("prdSe", ""),
            period=data.get("prdDe", ""),
            item_nm=data.get("itmNm", ""),
            value=value,
        )


class KeyIndicators(KosisBaseClient):
    """
    KOSIS 통계주요지표 API 클라이언트.

    KOSIS의 주요 통계지표를 조회하는 6개의 API 엔드포인트를 지원합니다.

    Attributes:
        config: KOSIS API 설정

    Example:
        >>> client = KeyIndicators()
        >>> # 지표명으로 설명 조회
        >>> explanations = client.get_explanation_by_name("실업률")
        >>> for exp in explanations:
        ...     print(f"{exp.jipyo_nm}: {exp.concept[:100]}...")
        >>>
        >>> # 목록별 지표 조회
        >>> indicators = client.get_by_list("100")
        >>> for ind in indicators:
        ...     print(f"{ind.jipyo_nm} ({ind.unit})")
    """

    def __init__(self, config: Optional[KosisConfig] = None) -> None:
        """
        클라이언트 초기화.

        Args:
            config: API 설정. None이면 환경변수에서 로드.
        """
        super().__init__(config)

    def get_explanation_by_id(
        self,
        jipyo_id: str,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> List[IndicatorExplanation]:
        """
        지표 고유번호별 설명 조회.

        pkNumberService.do API를 호출하여 지표 ID로 설명자료를 조회합니다.

        Args:
            jipyo_id: 지표 ID (필수)
            page_no: 페이지 번호 (기본값: 1)
            num_of_rows: 출력 개수 (기본값: 10)

        Returns:
            지표 설명 목록

        Raises:
            ValueError: jipyo_id가 비어있는 경우

        Example:
            >>> explanations = client.get_explanation_by_id("12345")
            >>> print(explanations[0].concept)
        """
        if not jipyo_id:
            raise ValueError("jipyo_id는 필수입니다.")

        params = {
            "method": "getList",
            "service": "1",
            "serviceDetail": "pkAll",
            "apiKey": self.config.api_key,
            "jipyoId": jipyo_id,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows),
            "format": "json",
        }

        response = self._request(
            method="GET",
            endpoint=IndicatorEndpoint.PK_NUMBER.value,
            params=params,
        )

        if not response:
            return []

        items = self._extract_items(response)
        return [IndicatorExplanation.from_api(item) for item in items]

    def get_explanation_by_name(
        self,
        jipyo_nm: str,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> List[IndicatorExplanation]:
        """
        지표명별 설명 조회.

        indExpService.do API를 호출하여 지표명으로 설명자료를 조회합니다.

        Args:
            jipyo_nm: 지표명 (필수)
            page_no: 페이지 번호 (기본값: 1)
            num_of_rows: 출력 개수 (기본값: 10)

        Returns:
            지표 설명 목록

        Raises:
            ValueError: jipyo_nm이 비어있는 경우

        Example:
            >>> explanations = client.get_explanation_by_name("실업률")
            >>> for exp in explanations:
            ...     print(f"{exp.jipyo_nm}: {exp.title}")
        """
        if not jipyo_nm:
            raise ValueError("jipyo_nm은 필수입니다.")

        params = {
            "method": "getList",
            "service": "2",
            "serviceDetail": "indAll",
            "apiKey": self.config.api_key,
            "jipyoNm": jipyo_nm,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows),
            "format": "json",
        }

        response = self._request(
            method="GET",
            endpoint=IndicatorEndpoint.IND_EXP.value,
            params=params,
        )

        if not response:
            return []

        items = self._extract_items(response)
        return [IndicatorExplanation.from_api(item) for item in items]

    def get_by_list(
        self,
        list_id: str,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> List[IndicatorListItem]:
        """
        목록별 지표 조회.

        indiListService.do API를 호출하여 목록 ID로 지표를 조회합니다.

        Args:
            list_id: 목록 ID (필수)
            page_no: 페이지 번호 (기본값: 1)
            num_of_rows: 출력 개수 (기본값: 10)

        Returns:
            지표 목록

        Raises:
            ValueError: list_id가 비어있는 경우

        Example:
            >>> indicators = client.get_by_list("100")
            >>> for ind in indicators:
            ...     print(f"{ind.jipyo_nm}: {ind.start_period}~{ind.end_period}")
        """
        if not list_id:
            raise ValueError("list_id는 필수입니다.")

        params = {
            "method": "getList",
            "service": "3",
            "apiKey": self.config.api_key,
            "listId": list_id,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows),
            "format": "json",
        }

        response = self._request(
            method="GET",
            endpoint=IndicatorEndpoint.INDI_LIST.value,
            params=params,
        )

        if not response:
            return []

        items = self._extract_items(response)
        return [IndicatorListItem.from_api(item) for item in items]

    def search_by_name(
        self,
        jipyo_nm: str,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> List[IndicatorSearchResult]:
        """
        지표명별 목록 조회.

        indListSearchRequest.do API를 호출하여 지표명으로 목록을 검색합니다.

        Args:
            jipyo_nm: 지표명 (필수)
            page_no: 페이지 번호 (기본값: 1)
            num_of_rows: 출력 개수 (기본값: 10)

        Returns:
            지표 검색 결과 목록

        Raises:
            ValueError: jipyo_nm이 비어있는 경우

        Example:
            >>> results = client.search_by_name("인구")
            >>> for r in results:
            ...     print(f"{r.jipyo_nm} ({r.period_type})")
        """
        if not jipyo_nm:
            raise ValueError("jipyo_nm은 필수입니다.")

        params = {
            "method": "getList",
            "service": "4",
            "serviceDetail": "indList",
            "apiKey": self.config.api_key,
            "jipyoNm": jipyo_nm,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows),
            "format": "json",
        }

        response = self._request(
            method="GET",
            endpoint=IndicatorEndpoint.IND_LIST_SEARCH.value,
            params=params,
        )

        if not response:
            return []

        items = self._extract_items(response)
        return [IndicatorSearchResult.from_api(item) for item in items]

    def search_by_id(
        self,
        jipyo_id: str,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> List[IndicatorSearchResult]:
        """
        고유번호별 목록 조회.

        indListSearchRequest.do API를 호출하여 지표 ID로 목록을 검색합니다.

        Args:
            jipyo_id: 지표 ID (필수)
            page_no: 페이지 번호 (기본값: 1)
            num_of_rows: 출력 개수 (기본값: 10)

        Returns:
            지표 검색 결과 목록

        Raises:
            ValueError: jipyo_id가 비어있는 경우

        Example:
            >>> results = client.search_by_id("12345")
            >>> print(results[0].jipyo_nm)
        """
        if not jipyo_id:
            raise ValueError("jipyo_id는 필수입니다.")

        params = {
            "method": "getList",
            "service": "4",
            "serviceDetail": "indList",
            "apiKey": self.config.api_key,
            "jipyoId": jipyo_id,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows),
            "format": "json",
        }

        response = self._request(
            method="GET",
            endpoint=IndicatorEndpoint.IND_LIST_SEARCH.value,
            params=params,
        )

        if not response:
            return []

        items = self._extract_items(response)
        return [IndicatorSearchResult.from_api(item) for item in items]

    def get_detail(
        self,
        jipyo_id: str,
        start_prd_de: Optional[str] = None,
        end_prd_de: Optional[str] = None,
        rn: Optional[int] = None,
        srv_rn: Optional[int] = None,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> List[IndicatorDetailData]:
        """
        고유번호별 지표 상세 조회.

        indIdDetailSearchRequest.do API를 호출하여 지표의 상세 데이터를 조회합니다.
        시점 기준 또는 최신자료 기준으로 조회할 수 있습니다.

        Args:
            jipyo_id: 지표 ID (필수)
            start_prd_de: 조회 시작 시점 (시점 기준)
            end_prd_de: 조회 종료 시점 (시점 기준)
            rn: 조회 기준 시점 (최신자료 기준)
            srv_rn: 조회 시점 개수 (최신자료 기준)
            page_no: 페이지 번호 (기본값: 1)
            num_of_rows: 출력 개수 (기본값: 10)

        Returns:
            지표 상세 데이터 목록

        Raises:
            ValueError: jipyo_id가 비어있는 경우

        Example:
            >>> # 시점 기준 조회
            >>> data = client.get_detail("12345", start_prd_de="2020", end_prd_de="2023")
            >>> for d in data:
            ...     print(f"{d.period}: {d.value}")
            >>>
            >>> # 최신자료 기준 조회
            >>> data = client.get_detail("12345", srv_rn=5)  # 최근 5개 시점
        """
        if not jipyo_id:
            raise ValueError("jipyo_id는 필수입니다.")

        params = {
            "method": "getList",
            "service": "4",
            "serviceDetail": "indIdDetail",
            "apiKey": self.config.api_key,
            "jipyoId": jipyo_id,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows),
            "format": "json",
        }

        # 시점 기준 파라미터
        if start_prd_de:
            params["startPrdDe"] = start_prd_de
        if end_prd_de:
            params["endPrdDe"] = end_prd_de

        # 최신자료 기준 파라미터
        if rn is not None:
            params["rn"] = str(rn)
        if srv_rn is not None:
            params["srvRn"] = str(srv_rn)

        response = self._request(
            method="GET",
            endpoint=IndicatorEndpoint.IND_ID_DETAIL.value,
            params=params,
        )

        if not response:
            return []

        items = self._extract_items(response)
        return [IndicatorDetailData.from_api(item) for item in items]

    def search_by_period_type(
        self,
        prd_se: str,
        page_no: int = 1,
        num_of_rows: int = 10,
    ) -> List[IndicatorSearchResult]:
        """
        수록주기별 목록 조회.

        prListSearchRequest.do API를 호출하여 수록주기로 지표 목록을 조회합니다.

        Args:
            prd_se: 수록주기 (필수, 예: "Y"=연간, "M"=월간, "Q"=분기)
            page_no: 페이지 번호 (기본값: 1)
            num_of_rows: 출력 개수 (기본값: 10)

        Returns:
            지표 검색 결과 목록

        Raises:
            ValueError: prd_se가 비어있는 경우

        Example:
            >>> # 연간 지표 조회
            >>> results = client.search_by_period_type("Y")
            >>> for r in results:
            ...     print(f"{r.jipyo_nm}: {r.period_type}")
        """
        if not prd_se:
            raise ValueError("prd_se는 필수입니다.")

        params = {
            "method": "getList",
            "service": "4",
            "serviceDetail": "prList",
            "apiKey": self.config.api_key,
            "prdSe": prd_se,
            "pageNo": str(page_no),
            "numOfRows": str(num_of_rows),
            "format": "json",
        }

        response = self._request(
            method="GET",
            endpoint=IndicatorEndpoint.PR_LIST_SEARCH.value,
            params=params,
        )

        if not response:
            return []

        items = self._extract_items(response)
        return [IndicatorSearchResult.from_api(item) for item in items]

    def _extract_items(self, response: Union[Dict, List]) -> List[Dict]:
        """
        API 응답에서 항목 목록 추출.

        KOSIS API는 응답 형식이 일관되지 않을 수 있으므로
        다양한 형식을 처리합니다.

        Args:
            response: API 응답

        Returns:
            항목 목록
        """
        if isinstance(response, list):
            return response

        if isinstance(response, dict):
            # response > body > items 형식
            if "response" in response:
                body = response["response"].get("body", {})
                items = body.get("items", {})
                if isinstance(items, dict):
                    item_list = items.get("item", [])
                    if isinstance(item_list, dict):
                        return [item_list]
                    return item_list if item_list else []
                return items if isinstance(items, list) else []

            # body > items 형식
            if "body" in response:
                items = response["body"].get("items", {})
                if isinstance(items, dict):
                    item_list = items.get("item", [])
                    if isinstance(item_list, dict):
                        return [item_list]
                    return item_list if item_list else []
                return items if isinstance(items, list) else []

            # items 직접 형식
            if "items" in response:
                items = response["items"]
                if isinstance(items, dict):
                    item_list = items.get("item", [])
                    if isinstance(item_list, dict):
                        return [item_list]
                    return item_list if item_list else []
                return items if isinstance(items, list) else []

            # item 직접 형식
            if "item" in response:
                item = response["item"]
                if isinstance(item, list):
                    return item
                return [item]

        return []
