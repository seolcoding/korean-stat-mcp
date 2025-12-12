"""
KOSIS API 클라이언트 설정 모듈.

이 모듈은 KOSIS API 클라이언트의 모든 설정을 관리합니다.
코어 비즈니스 로직과 설정을 분리하여 테스트 용이성을 높이고,
환경별로 다른 설정을 주입할 수 있도록 합니다.

주요 기능:
    - API 인증 설정 (api_key)
    - HTTP 요청 설정 (timeout, base_url)
    - Rate limiting 설정 (rate_limit_delay)
    - 재시도 설정 (max_retries, retry_delay)

Example:
    기본 설정 사용:
    >>> config = load_config()
    >>> client = KosisBaseClient(config)

    커스텀 설정 사용:
    >>> custom_config = KosisConfig(
    ...     api_key="your-api-key",
    ...     rate_limit_delay=0.5,  # 더 빠른 요청
    ...     timeout=30
    ... )
    >>> client = KosisBaseClient(custom_config)

    테스트용 설정:
    >>> test_config = KosisConfig(
    ...     api_key="test-key",
    ...     rate_limit_delay=0,  # 테스트에서는 딜레이 없음
    ...     max_retries=0
    ... )
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KosisConfig:
    """
    KOSIS API 클라이언트 설정.

    코어 로직과 분리된 설정 클래스로, 환경별로 다른 설정을
    주입하거나 테스트 시 mock 설정을 사용할 수 있습니다.

    Attributes:
        api_key: KOSIS API 인증 키.
                 https://kosis.kr/openapi/ 에서 발급받을 수 있습니다.
                 환경변수 KOSIS_API_KEY에서 로드됩니다.

        base_url: KOSIS API 기본 URL.
                  기본값: "https://kosis.kr/openapi"
                  환경변수 KOSIS_API_ENDPOINT로 오버라이드 가능.

        rate_limit_delay: API 요청 간 딜레이 (초).
                          KOSIS API는 과도한 요청 시 차단될 수 있으므로
                          적절한 딜레이가 필요합니다.
                          기본값: 1.0초

        timeout: HTTP 요청 타임아웃 (초).
                 KOSIS API는 대용량 데이터 요청 시 응답이 느릴 수 있습니다.
                 기본값: 60초

        max_retries: 요청 실패 시 최대 재시도 횟수.
                     네트워크 오류나 일시적인 서버 오류 시 재시도합니다.
                     기본값: 3회

        retry_delay: 재시도 간 대기 시간 (초).
                     지수 백오프(exponential backoff)를 적용할 수 있습니다.
                     기본값: 2.0초

    Example:
        >>> config = KosisConfig(api_key="your-api-key")
        >>> print(config.base_url)
        "https://kosis.kr/openapi"
        >>> print(config.rate_limit_delay)
        1.0
    """

    api_key: str
    base_url: str = "https://kosis.kr/openapi"
    rate_limit_delay: float = 1.0
    timeout: int = 60
    max_retries: int = 3
    retry_delay: float = 2.0

    def __post_init__(self) -> None:
        """설정값 유효성 검사."""
        if not self.api_key:
            raise ValueError("api_key는 필수입니다.")
        if self.rate_limit_delay < 0:
            raise ValueError("rate_limit_delay는 0 이상이어야 합니다.")
        if self.timeout <= 0:
            raise ValueError("timeout은 0보다 커야 합니다.")
        if self.max_retries < 0:
            raise ValueError("max_retries는 0 이상이어야 합니다.")
        if self.retry_delay < 0:
            raise ValueError("retry_delay는 0 이상이어야 합니다.")


def load_config() -> KosisConfig:
    """
    환경변수에서 KOSIS API 설정을 로드합니다.

    필수 환경변수:
        KOSIS_API_KEY: API 인증 키

    선택 환경변수:
        KOSIS_API_ENDPOINT: API 기본 URL (기본값: https://kosis.kr/openapi)
        KOSIS_RATE_LIMIT: 요청 간 딜레이 초 (기본값: 1.0)
        KOSIS_TIMEOUT: HTTP 타임아웃 초 (기본값: 60)
        KOSIS_MAX_RETRIES: 최대 재시도 횟수 (기본값: 3)
        KOSIS_RETRY_DELAY: 재시도 딜레이 초 (기본값: 2.0)

    Returns:
        KosisConfig: 설정 객체

    Raises:
        ValueError: KOSIS_API_KEY 환경변수가 설정되지 않은 경우

    Example:
        >>> # .env 파일 또는 환경변수 설정
        >>> # KOSIS_API_KEY=your-api-key
        >>> config = load_config()
        >>> print(config.api_key)
        "your-api-key"

    Note:
        python-dotenv를 사용하면 .env 파일에서 환경변수를 로드할 수 있습니다:
        >>> from dotenv import load_dotenv
        >>> load_dotenv()
        >>> config = load_config()
    """
    api_key = os.getenv("KOSIS_API_KEY")
    if not api_key:
        raise ValueError(
            "KOSIS_API_KEY 환경변수가 설정되지 않았습니다. "
            ".env 파일이나 환경변수에 API 키를 설정해주세요."
        )

    return KosisConfig(
        api_key=api_key,
        base_url=os.getenv("KOSIS_API_ENDPOINT", "https://kosis.kr/openapi"),
        rate_limit_delay=float(os.getenv("KOSIS_RATE_LIMIT", "1.0")),
        timeout=int(os.getenv("KOSIS_TIMEOUT", "60")),
        max_retries=int(os.getenv("KOSIS_MAX_RETRIES", "3")),
        retry_delay=float(os.getenv("KOSIS_RETRY_DELAY", "2.0")),
    )


# API 엔드포인트 상수
# 각 도구 모듈에서 사용할 엔드포인트 경로
class Endpoints:
    """
    KOSIS API 엔드포인트 상수.

    각 API 엔드포인트의 경로를 정의합니다.
    base_url과 결합하여 전체 URL을 구성합니다.

    Example:
        >>> config = load_config()
        >>> full_url = f"{config.base_url}/{Endpoints.STATISTICS_LIST}"
        >>> print(full_url)
        "https://kosis.kr/openapi/statisticsList.do"

    Attributes:
        STATISTICS_LIST: 통계 목록 조회 (검색, 카테고리 목록)
        STATISTICS_DATA: 통계 데이터 조회
        STATISTICS_META: 통계표 메타데이터 조회
        STATISTICS_EXPLANATION: 통계설명 조회
        STAT_HTML_CONTENT: HTML 콘텐츠 (k-stat URL 추출용)
    """

    STATISTICS_LIST = "statisticsList.do"
    STATISTICS_DATA = "Param/statisticsParameterData.do"
    STATISTICS_META = "statisticsMetaData.do"
    STATISTICS_EXPLANATION = "statisticsExplanation.do"
    STAT_HTML_CONTENT = "statHtml/statHtmlContent.do"


# 수록주기 상수
class PeriodType:
    """
    KOSIS 데이터 수록주기 타입.

    API 요청 시 prdSe 파라미터에 사용되는 주기 코드입니다.
    데이터 조회 시 적절한 주기를 선택해야 합니다.

    Attributes:
        MONTHLY: 월간 데이터 (YYYYMM 형식, 예: 202301)
        QUARTERLY: 분기 데이터 (YYYYQQ 형식, 예: 202301 = 1분기)
        SEMI_ANNUAL: 반기 데이터 (YYYYHH 형식, 예: 202301 = 상반기)
        YEARLY: 연간 데이터 (YYYY 형식, 예: 2023)
        MULTI_YEAR: 다년 데이터 (YYYY 형식, 2/3/4/5/10년 주기)
        IRREGULAR: 부정기 데이터 (날짜 형식 다양)

    Example:
        >>> from kosis_tools.data import StatisticsData
        >>> data = StatisticsData()
        >>> result = data.get_data(
        ...     org_id="101",
        ...     tbl_id="DT_1B040A3",
        ...     start_date="2020",
        ...     end_date="2023",
        ...     prd_se=PeriodType.YEARLY
        ... )
    """

    MONTHLY = "M"  # 월간 (격월도 동일 코드)
    QUARTERLY = "Q"  # 분기
    SEMI_ANNUAL = "S"  # 반기 (H와 동일)
    YEARLY = "Y"  # 연간
    MULTI_YEAR = "F"  # 다년
    IRREGULAR = "IR"  # 부정기

    # 주기 우선순위 (세밀한 데이터부터 탐색)
    PRIORITY_ORDER = [MONTHLY, QUARTERLY, SEMI_ANNUAL, YEARLY, MULTI_YEAR, IRREGULAR]

    # 한글 이름 매핑
    NAMES = {
        MONTHLY: "월간",
        QUARTERLY: "분기",
        SEMI_ANNUAL: "반기",
        YEARLY: "연간",
        MULTI_YEAR: "다년",
        IRREGULAR: "부정기",
    }
