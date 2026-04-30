"""
KOSIS 대용량 통계자료 모듈.

이 모듈은 KOSIS OpenAPI의 statisticsBigData.do 엔드포인트를 사용하여
대용량 통계 데이터를 조회합니다.

주요 기능:
    - SDMX 형식 데이터 조회 (DSD, Generic, StructureSpecific)
    - CSV/XLS 형식 데이터 조회
    - 다중계열, 여러 시점 데이터 처리

제약사항:
    - userStatsId가 필요하며, KOSIS 웹사이트에서 미리 등록해야 발급됨
    - 개발가이드 > 대용량 통계자료 > URL생성 > 자료등록 에서 등록

Example:
    기본 사용:
    >>> from kosis_tools.big_data import StatisticsBigData
    >>> big_data = StatisticsBigData()
    >>> result = big_data.fetch_sdmx(
    ...     user_stats_id="openapisample/101/DT_1IN1502/2/1/20191106094026_1",
    ...     sdmx_type="Generic",
    ...     prd_se="Y",
    ...     new_est_prd_cnt=5
    ... )

API Reference:
    - Endpoint: statisticsBigData.do
    - 지원 형식: SDMX (DSD/Generic/StructureSpecific), CSV/XLS
"""

from __future__ import annotations

import csv
import io
import logging
import xml.etree.ElementTree as ET
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from .base import KosisBaseClient

logger = logging.getLogger(__name__)


class SdmxType(str, Enum):
    """SDMX 출력 유형."""

    DSD = "DSD"  # Data Structure Definition
    GENERIC = "Generic"  # Generic Data
    STRUCTURE_SPECIFIC = "StructureSpecific"  # Structure Specific Data


class BigDataFormat(str, Enum):
    """대용량 데이터 출력 형식."""

    JSON = "json"
    SDMX = "sdmx"
    CSV = "csv"
    XLS = "xls"


class StatisticsBigData(KosisBaseClient):
    """
    KOSIS 대용량 통계자료 클라이언트.

    대용량 통계 데이터(40,000건 이상)를 조회합니다.
    SDMX, CSV, XLS 형식을 지원합니다.

    중요: userStatsId는 KOSIS 웹사이트에서 미리 등록해야 합니다.
    - 개발가이드 > 대용량 통계자료 > URL생성 > 자료등록

    Attributes:
        config: KosisConfig 인스턴스.

    Args:
        config: KosisConfig 인스턴스. None이면 환경변수에서 기본 설정 로드.

    Example:
        >>> big_data = StatisticsBigData()
        >>> # SDMX Generic 형식으로 조회
        >>> result = big_data.fetch_sdmx(
        ...     user_stats_id="your_registered_id",
        ...     sdmx_type=SdmxType.GENERIC,
        ...     prd_se="Y",
        ...     start_prd_de="2020",
        ...     end_prd_de="2023"
        ... )

    API Reference:
        - Endpoint: statisticsBigData.do
        - 필수: apiKey, userStatsId, format
    """

    ENDPOINT = "statisticsBigData.do"

    def fetch_sdmx(
        self,
        user_stats_id: str,
        sdmx_type: Union[SdmxType, str] = SdmxType.GENERIC,
        prd_se: str = "Y",
        start_prd_de: Optional[str] = None,
        end_prd_de: Optional[str] = None,
        new_est_prd_cnt: Optional[int] = None,
        prd_interval: Optional[int] = None,
        as_json: bool = True,
    ) -> Union[Dict[str, Any], str]:
        """
        SDMX 형식으로 대용량 데이터를 조회합니다.

        Args:
            user_stats_id: 사용자 등록 통계표 ID (KOSIS 웹에서 발급).
                          예: "openapisample/101/DT_1IN1502/2/1/20191106094026_1"

            sdmx_type: SDMX 유형.
                      - DSD: Data Structure Definition (메타데이터)
                      - Generic: 일반 데이터
                      - StructureSpecific: 구조 특화 데이터
                      기본값: Generic

            prd_se: 수록주기 (필수).
                   "Y" (연간), "M" (월간), "Q" (분기) 등

            start_prd_de: 시작 수록시점 (선택).
                         예: "2020", "202001"

            end_prd_de: 종료 수록시점 (선택).
                       예: "2023", "202312"

            new_est_prd_cnt: 최근 수록시점 개수 (선택).
                            start/end 대신 사용 가능.
                            예: 5 (최근 5개 시점)

            prd_interval: 수록시점 간격 (선택).
                         예: 2 (2개 간격으로 조회)

            as_json: True면 JSON 형식, False면 SDMX XML 원본 반환.
                    기본값: True

        Returns:
            as_json=True: 파싱된 데이터 딕셔너리
            as_json=False: SDMX XML 문자열

        Raises:
            ValueError: 필수 파라미터 누락 또는 잘못된 값

        Example:
            >>> result = big_data.fetch_sdmx(
            ...     user_stats_id="your_id",
            ...     sdmx_type="Generic",
            ...     prd_se="Y",
            ...     new_est_prd_cnt=10
            ... )
            >>> print(result["header"]["name"])
        """
        if not user_stats_id or not user_stats_id.strip():
            raise ValueError("user_stats_id는 필수입니다.")

        if not prd_se:
            raise ValueError("prd_se(수록주기)는 필수입니다.")

        # sdmx_type 검증
        if isinstance(sdmx_type, str):
            try:
                sdmx_type = SdmxType(sdmx_type)
            except ValueError:
                valid_types = [t.value for t in SdmxType]
                raise ValueError(
                    f"잘못된 sdmx_type: {sdmx_type}. 가능한 값: {valid_types}"
                )

        # DSD는 기간 파라미터 불필요
        if sdmx_type == SdmxType.DSD:
            params: Dict[str, Any] = {
                "format": "sdmx" if not as_json else "json",
                "type": sdmx_type.value,
                "userStatsId": user_stats_id.strip(),
            }
        else:
            params = {
                "format": "sdmx" if not as_json else "json",
                "type": sdmx_type.value,
                "userStatsId": user_stats_id.strip(),
                "prdSe": prd_se,
            }

            # 기간 설정 (시점기준 또는 최신자료기준 택1)
            if new_est_prd_cnt is not None:
                params["newEstPrdCnt"] = str(new_est_prd_cnt)
            elif start_prd_de and end_prd_de:
                params["startPrdDe"] = start_prd_de
                params["endPrdDe"] = end_prd_de
            elif start_prd_de or end_prd_de:
                raise ValueError(
                    "시점기준 조회 시 startPrdDe와 endPrdDe 모두 필요합니다."
                )

            if prd_interval is not None:
                params["prdInterval"] = str(prd_interval)

        logger.info(
            f"대용량 SDMX 조회: type={sdmx_type.value}, user_stats_id={user_stats_id}"
        )

        result = self._request("GET", self.ENDPOINT, params)

        if result is None:
            return {} if as_json else ""

        if as_json:
            return result if isinstance(result, dict) else {"data": result}
        else:
            return result if isinstance(result, str) else str(result)

    def fetch_csv(
        self,
        user_stats_id: str,
        prd_se: str = "Y",
        start_prd_de: Optional[str] = None,
        end_prd_de: Optional[str] = None,
        new_est_prd_cnt: Optional[int] = None,
        prd_interval: Optional[int] = None,
        as_dataframe: bool = False,
    ) -> Union[List[Dict[str, str]], Any]:
        """
        CSV 형식으로 대용량 데이터를 조회합니다.

        Args:
            user_stats_id: 사용자 등록 통계표 ID.

            prd_se: 수록주기 (필수).

            start_prd_de: 시작 수록시점 (선택).

            end_prd_de: 종료 수록시점 (선택).

            new_est_prd_cnt: 최근 수록시점 개수 (선택).

            prd_interval: 수록시점 간격 (선택).

            as_dataframe: True면 pandas DataFrame으로 반환.
                         pandas가 설치되어 있어야 함.
                         기본값: False

        Returns:
            as_dataframe=False: List[Dict] 형태의 데이터
            as_dataframe=True: pandas DataFrame

        Example:
            >>> data = big_data.fetch_csv(
            ...     user_stats_id="your_id",
            ...     prd_se="Y",
            ...     new_est_prd_cnt=5
            ... )
            >>> for row in data[:3]:
            ...     print(row)
        """
        if not user_stats_id or not user_stats_id.strip():
            raise ValueError("user_stats_id는 필수입니다.")

        if not prd_se:
            raise ValueError("prd_se(수록주기)는 필수입니다.")

        params: Dict[str, Any] = {
            "format": "csv",
            "userStatsId": user_stats_id.strip(),
            "prdSe": prd_se,
        }

        # 기간 설정
        if new_est_prd_cnt is not None:
            params["newEstPrdCnt"] = str(new_est_prd_cnt)
        elif start_prd_de and end_prd_de:
            params["startPrdDe"] = start_prd_de
            params["endPrdDe"] = end_prd_de

        if prd_interval is not None:
            params["prdInterval"] = str(prd_interval)

        logger.info(f"대용량 CSV 조회: user_stats_id={user_stats_id}")

        # CSV는 raw response 필요
        result = self._request_raw("GET", self.ENDPOINT, params)

        if result is None:
            return [] if not as_dataframe else None

        # CSV 파싱
        data = self._parse_csv(result)

        if as_dataframe:
            try:
                import pandas as pd

                return pd.DataFrame(data)
            except ImportError:
                logger.warning("pandas가 설치되지 않아 List[Dict]로 반환합니다.")
                return data

        return data

    def fetch_xls(
        self,
        user_stats_id: str,
        prd_se: str = "Y",
        start_prd_de: str | None = None,
        end_prd_de: str | None = None,
        new_est_prd_cnt: int | None = None,
        prd_interval: int | None = None,
    ) -> bytes:
        """
        XLS 형식으로 대용량 데이터를 조회합니다 (Gap 4).

        KOSIS의 statisticsBigData.do는 ``format=xls`` 를 지원하지만 응답이
        바이너리이므로 ``bytes`` 를 그대로 반환합니다. 호출 측에서 파일로
        저장하거나 ``openpyxl`` / ``pandas.read_excel`` 등으로 파싱하세요.

        Args:
            user_stats_id: 사용자 등록 통계표 ID.
            prd_se: 수록주기 (필수).
            start_prd_de: 시작 수록시점 (선택).
            end_prd_de: 종료 수록시점 (선택).
            new_est_prd_cnt: 최근 수록시점 개수 (선택).
            prd_interval: 수록시점 간격 (선택).

        Returns:
            XLS 파일 바이트. 실패 시 빈 ``b""``.
        """
        if not user_stats_id or not user_stats_id.strip():
            raise ValueError("user_stats_id는 필수입니다.")
        if not prd_se:
            raise ValueError("prd_se(수록주기)는 필수입니다.")

        params: Dict[str, Any] = {
            "format": BigDataFormat.XLS.value,
            "userStatsId": user_stats_id.strip(),
            "prdSe": prd_se,
        }
        if new_est_prd_cnt is not None:
            params["newEstPrdCnt"] = str(new_est_prd_cnt)
        elif start_prd_de and end_prd_de:
            params["startPrdDe"] = start_prd_de
            params["endPrdDe"] = end_prd_de
        if prd_interval is not None:
            params["prdInterval"] = str(prd_interval)

        logger.info(f"대용량 XLS 조회: user_stats_id={user_stats_id}")
        return self._request_raw_bytes(self.ENDPOINT, params) or b""

    def fetch_dsd(
        self,
        user_stats_id: str,
    ) -> Dict[str, Any]:
        """
        DSD (Data Structure Definition) 메타데이터를 조회합니다.

        데이터 구조 정의만 조회하며, 실제 데이터는 포함되지 않습니다.
        코드리스트, 컨셉, 데이터 구조 등을 확인할 수 있습니다.

        Args:
            user_stats_id: 사용자 등록 통계표 ID.

        Returns:
            DSD 메타데이터 딕셔너리:
            {
                "header": {...},
                "codelists": [...],
                "concepts": [...],
                "data_structures": [...]
            }

        Example:
            >>> dsd = big_data.fetch_dsd("your_id")
            >>> print(dsd["header"]["name"])
        """
        return self.fetch_sdmx(
            user_stats_id=user_stats_id,
            sdmx_type=SdmxType.DSD,
            prd_se="Y",  # DSD에서는 무시되지만 필요할 수 있음
            as_json=True,
        )

    def _request_raw(
        self,
        method: str,
        endpoint: str,
        params: Dict[str, Any],
    ) -> Optional[str]:
        """
        Raw HTTP 응답을 반환합니다 (CSV/XLS용).

        기본 _request는 JSON 파싱을 시도하므로,
        CSV 등 비-JSON 응답은 이 메서드를 사용합니다.
        """
        import time
        import requests

        # Rate limiting
        time.sleep(self.config.rate_limit_delay)

        url = f"{self.config.base_url}/{endpoint}"
        params["apiKey"] = self.config.api_key

        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"HTTP 요청 실패: {e}")
            return None

    def _request_raw_bytes(
        self,
        endpoint: str,
        params: Dict[str, Any],
    ) -> Optional[bytes]:
        """Raw bytes 응답 (XLS 등 바이너리용)."""
        import time
        import requests

        time.sleep(self.config.rate_limit_delay)

        url = f"{self.config.base_url}/{endpoint}"
        params["apiKey"] = self.config.api_key

        try:
            response = requests.get(
                url,
                params=params,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            logger.error(f"HTTP 요청 실패: {e}")
            return None

    def _parse_csv(self, csv_text: str) -> List[Dict[str, str]]:
        """
        CSV 텍스트를 파싱합니다.

        Args:
            csv_text: CSV 형식 문자열

        Returns:
            List[Dict] 형태의 데이터
        """
        if not csv_text or not csv_text.strip():
            return []

        try:
            reader = csv.DictReader(io.StringIO(csv_text))
            return list(reader)
        except Exception as e:
            logger.error(f"CSV 파싱 실패: {e}")
            return []

    def parse_sdmx_xml(self, xml_text: str) -> Dict[str, Any]:
        """
        SDMX XML을 파싱합니다.

        Args:
            xml_text: SDMX XML 문자열

        Returns:
            파싱된 데이터 딕셔너리
        """
        if not xml_text or not xml_text.strip():
            return {}

        try:
            root = ET.fromstring(xml_text)

            # 네임스페이스 처리
            ns = {
                "message": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message",
                "common": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common",
                "data": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/data/generic",
            }

            result: Dict[str, Any] = {
                "header": {},
                "series": [],
            }

            # Header 파싱
            header = root.find(".//message:Header", ns)
            if header is None:
                header = root.find(".//Header")
            if header is not None:
                result["header"] = self._parse_element_to_dict(header)

            # Series 파싱 (Generic/StructureSpecific)
            for series in root.findall(".//data:Series", ns) + root.findall(
                ".//Series"
            ):
                series_data: Dict[str, Any] = {
                    "keys": {},
                    "observations": [],
                }

                # SeriesKey
                for key in series.findall(".//data:Value", ns) + series.findall(
                    ".//Value"
                ):
                    key_id = key.get("id") or key.get("Id")
                    key_value = key.get("value") or key.text
                    if key_id:
                        series_data["keys"][key_id] = key_value

                # Observations
                for obs in series.findall(".//data:Obs", ns) + series.findall(".//Obs"):
                    obs_data = {}
                    for child in obs:
                        tag = child.tag.split("}")[-1]  # 네임스페이스 제거
                        obs_data[tag] = child.get("value") or child.text
                    if obs_data:
                        series_data["observations"].append(obs_data)

                result["series"].append(series_data)

            return result

        except ET.ParseError as e:
            logger.error(f"XML 파싱 실패: {e}")
            return {}

    def _parse_element_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """XML Element를 딕셔너리로 변환합니다."""
        result: Dict[str, Any] = {}

        # 속성
        result.update(element.attrib)

        # 텍스트
        if element.text and element.text.strip():
            result["_text"] = element.text.strip()

        # 자식 요소
        for child in element:
            tag = child.tag.split("}")[-1]  # 네임스페이스 제거
            child_data = self._parse_element_to_dict(child)

            if tag in result:
                # 이미 존재하면 리스트로
                if not isinstance(result[tag], list):
                    result[tag] = [result[tag]]
                result[tag].append(child_data)
            else:
                result[tag] = child_data

        return result

    def get_registered_stats_info(self, user_stats_id: str) -> Dict[str, Any]:
        """
        등록된 통계표의 기본 정보를 조회합니다.

        DSD를 통해 통계표 메타데이터를 확인합니다.

        Args:
            user_stats_id: 사용자 등록 통계표 ID.

        Returns:
            통계표 기본 정보:
            {
                "user_stats_id": "...",
                "name": "통계표명",
                "org": "기관명",
                "codelists_count": 5,
                "valid": True/False
            }
        """
        try:
            dsd = self.fetch_dsd(user_stats_id)

            info = {
                "user_stats_id": user_stats_id,
                "name": None,
                "org": None,
                "valid": bool(dsd),
            }

            if dsd and "header" in dsd:
                header = dsd["header"]
                info["name"] = header.get("Name") or header.get("name")
                if "Sender" in header:
                    info["org"] = header["Sender"].get("Name") or header["Sender"].get(
                        "name"
                    )

            return info

        except Exception as e:
            logger.error(f"등록 통계표 정보 조회 실패: {e}")
            return {
                "user_stats_id": user_stats_id,
                "valid": False,
                "error": str(e),
            }
