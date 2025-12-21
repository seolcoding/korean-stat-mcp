"""
KOSIS API 베이스 클라이언트 모듈.

모든 KOSIS API 도구의 공통 기능을 제공하는 베이스 클래스입니다.
HTTP 요청, JSON 파싱, 에러 핸들링, Rate limiting 등의 공통 로직을 포함합니다.

주요 기능:
    - HTTP 세션 관리 (requests.Session)
    - KOSIS 비표준 JSON 파싱 (키에 따옴표 없는 응답 처리)
    - Rate limiting (설정에 따른 요청 간 딜레이)
    - 재시도 로직 (네트워크 오류 시 자동 재시도)
    - 에러 핸들링 및 로깅

Example:
    직접 사용하지 않고 상속받아 사용:
    >>> from kosis_tools.base import KosisBaseClient
    >>> class MyTool(KosisBaseClient):
    ...     def my_method(self):
    ...         return self._request("GET", "/some/endpoint", {"param": "value"})

Design Principles:
    - 코어 로직과 설정 분리: 모든 설정은 config.py의 KosisConfig로 주입
    - 순수 함수 우선: JSON 파싱 등은 인스턴스 상태에 의존하지 않는 순수 함수
    - 테스트 용이성: mock config 주입으로 단위 테스트 가능
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Union

import json5
import requests
from requests.exceptions import RequestException

from .config import KosisConfig, load_config

logger = logging.getLogger(__name__)


def fix_malformed_json(response_text: str) -> Optional[Union[Dict, List]]:
    """
    KOSIS의 비표준 JSON 응답을 파싱합니다.

    KOSIS API는 JSON 키에 따옴표가 없는 비표준 형식의 응답을 반환합니다.
    이 함수는 정규표현식을 사용하여 키에 따옴표를 추가한 후 파싱합니다.

    이 함수는 순수 함수(pure function)로, 인스턴스 상태에 의존하지 않습니다.
    테스트 시 독립적으로 테스트할 수 있습니다.

    Args:
        response_text: API로부터 받은 원시 응답 텍스트.
                       예: '{TBL_ID:"DT_1B040A3", TBL_NM:"인구"}'

    Returns:
        파싱된 JSON 객체 (dict 또는 list).
        파싱 실패 또는 빈 응답인 경우 None 반환.

    Example:
        >>> text = '{TBL_ID:"DT_1B040A3", TBL_NM:"인구"}'
        >>> result = fix_malformed_json(text)
        >>> print(result)
        {"TBL_ID": "DT_1B040A3", "TBL_NM": "인구"}

        >>> result = fix_malformed_json("")
        >>> print(result)
        None

    Note:
        - 빈 문자열이나 공백만 있는 경우 None 반환
        - JSON 파싱 실패 시 에러 로그 기록 후 None 반환
        - 정규표현식 패턴: ([{,])\\s*([a-zA-Z_][a-zA-Z0-9_]*)\\s*:
          이 패턴은 '{key:' 또는 ',key:' 형태를 '{"key":' 또는 ',"key":'로 변환
    """
    if not response_text or response_text.strip() == "":
        return None

    try:
        # json5 라이브러리 사용: 따옴표 없는 키 등 비표준 JSON을 자동 처리
        # KOSIS API는 {TBL_ID:"값"} 형태의 비표준 JSON을 반환하므로 json5 사용
        return json5.loads(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"JSON 파싱 실패: {e}")
        logger.debug(f"응답 미리보기: {response_text[:500]}...")
        return None


class KosisBaseClient:
    """
    KOSIS API 기본 클라이언트.

    모든 KOSIS API 도구의 베이스 클래스입니다.
    설정은 외부에서 주입받아 코어 로직과 분리됩니다.

    이 클래스는 직접 사용하지 않고, 각 도구 클래스에서 상속받아 사용합니다.

    Attributes:
        config: KosisConfig 인스턴스. API 키, 타임아웃, rate limit 등 설정.
        session: requests.Session 인스턴스. HTTP 연결 재사용.

    Args:
        config: KosisConfig 인스턴스.
                None이면 환경변수에서 기본 설정을 로드합니다.

    Example:
        커스텀 설정으로 클라이언트 생성:
        >>> from kosis_tools.config import KosisConfig
        >>> config = KosisConfig(api_key="your-key", rate_limit_delay=0.5)
        >>> client = KosisBaseClient(config)

        기본 설정 사용 (환경변수에서 로드):
        >>> client = KosisBaseClient()

        테스트용 mock 설정:
        >>> test_config = KosisConfig(
        ...     api_key="test-key",
        ...     rate_limit_delay=0,  # 테스트에서는 딜레이 없음
        ... )
        >>> client = KosisBaseClient(test_config)

    API Reference:
        KOSIS OpenAPI 문서: https://kosis.kr/openapi/

    Note:
        - 모든 HTTP 요청은 rate limiting이 적용됩니다
        - 네트워크 오류 시 max_retries만큼 자동 재시도합니다
        - 세션을 재사용하므로 성능이 향상됩니다
    """

    def __init__(self, config: Optional[KosisConfig] = None) -> None:
        """
        베이스 클라이언트 초기화.

        Args:
            config: KosisConfig 인스턴스. None이면 환경변수에서 로드.

        Raises:
            ValueError: config가 None이고 KOSIS_API_KEY 환경변수가 없는 경우
        """
        self.config = config or load_config()
        self._session = requests.Session()
        self._last_request_time: float = 0.0

    def _apply_rate_limit(self) -> None:
        """
        Rate limiting 적용.

        마지막 요청 이후 설정된 딜레이만큼 대기합니다.
        KOSIS API 서버 부하 방지를 위해 필요합니다.
        """
        if self.config.rate_limit_delay <= 0:
            return

        elapsed = time.time() - self._last_request_time
        if elapsed < self.config.rate_limit_delay:
            sleep_time = self.config.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: {sleep_time:.2f}초 대기")
            time.sleep(sleep_time)

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[Union[Dict, List]]:
        """
        HTTP 요청을 수행하고 JSON 응답을 반환합니다.

        Rate limiting, 재시도, 에러 핸들링을 자동으로 처리합니다.
        KOSIS의 비표준 JSON 응답도 자동으로 파싱합니다.

        Args:
            method: HTTP 메서드 ("GET", "POST" 등)
            endpoint: API 엔드포인트 경로 (예: "statisticsList.do")
            params: 쿼리 파라미터 딕셔너리
            **kwargs: requests 라이브러리에 전달할 추가 인자

        Returns:
            파싱된 JSON 응답 (dict 또는 list).
            실패 시 None 반환.

        Example:
            >>> result = self._request(
            ...     "GET",
            ...     "statisticsList.do",
            ...     {"method": "getList", "searchNm": "인구"}
            ... )

        Note:
            - 요청 전 rate limiting이 적용됩니다
            - 네트워크 오류 시 max_retries만큼 재시도합니다
            - API 에러 응답 (errMsg 포함) 시 None 반환하고 경고 로그 기록
        """
        url = f"{self.config.base_url}/{endpoint}"

        # API 키 추가
        if params is None:
            params = {}
        params["apiKey"] = self.config.api_key

        for attempt in range(self.config.max_retries + 1):
            try:
                # Rate limiting 적용
                self._apply_rate_limit()

                # 요청 URL 로깅 (디버그용)
                prepared = self._session.prepare_request(
                    requests.Request(method, url, params=params)
                )
                logger.debug(f"API 요청: {prepared.url}")

                # HTTP 요청
                response = self._session.request(
                    method,
                    url,
                    params=params,
                    timeout=self.config.timeout,
                    **kwargs,
                )
                self._last_request_time = time.time()

                # HTTP 에러 체크
                response.raise_for_status()

                # JSON 파싱
                data = fix_malformed_json(response.text)

                # API 에러 체크 (errMsg 필드)
                # Note: retry 전략에서 여러 번 호출되므로 DEBUG 레벨 사용
                # 최종 실패 시 상위 호출자(data.py)에서 WARNING 로그 출력
                if isinstance(data, dict) and "errMsg" in data:
                    logger.debug(f"API 에러: {data.get('errMsg')}")
                    return None

                return data

            except RequestException as e:
                logger.warning(
                    f"요청 실패 (시도 {attempt + 1}/{self.config.max_retries + 1}): {e}"
                )

                if attempt < self.config.max_retries:
                    sleep_time = self.config.retry_delay * (2**attempt)  # 지수 백오프
                    logger.debug(f"재시도 전 {sleep_time:.1f}초 대기")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"최대 재시도 횟수 초과: {url}")
                    return None

            except Exception as e:
                logger.error(f"예상치 못한 오류: {e}")
                return None

        return None

    def close(self) -> None:
        """
        HTTP 세션을 종료합니다.

        컨텍스트 매니저 또는 명시적 종료 시 호출합니다.
        """
        self._session.close()

    def __enter__(self) -> "KosisBaseClient":
        """컨텍스트 매니저 진입."""
        return self

    def __exit__(self, *args: Any) -> None:
        """컨텍스트 매니저 종료."""
        self.close()
