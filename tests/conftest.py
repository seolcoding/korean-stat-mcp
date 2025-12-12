"""
pytest 공통 fixtures.

테스트 전반에서 사용되는 공통 설정, mock 객체, fixture를 정의합니다.
"""

import pytest

from kosis_tools.config import KosisConfig


@pytest.fixture
def test_config() -> KosisConfig:
    """
    테스트용 KosisConfig fixture.

    Rate limiting과 retry를 비활성화하여 빠른 테스트를 가능하게 합니다.
    """
    return KosisConfig(
        api_key="test-api-key",
        base_url="https://kosis.kr/openapi",
        rate_limit_delay=0,  # 테스트에서는 딜레이 없음
        timeout=5,
        max_retries=0,  # 테스트에서는 재시도 없음
        retry_delay=0,
    )


@pytest.fixture
def sample_malformed_json() -> str:
    """KOSIS의 비표준 JSON 응답 예시."""
    return '{TBL_ID:"DT_1B040A3",TBL_NM:"행정구역별 인구수",ORG_ID:"101"}'


@pytest.fixture
def sample_valid_json() -> str:
    """정상적인 JSON 응답 예시."""
    return '{"TBL_ID":"DT_1B040A3","TBL_NM":"행정구역별 인구수","ORG_ID":"101"}'


@pytest.fixture
def sample_list_response() -> str:
    """KOSIS 통계 목록 응답 예시 (비표준 JSON)."""
    return """[
        {TBL_ID:"DT_1B040A3",TBL_NM:"행정구역별 인구수",ORG_ID:"101",ORG_NM:"통계청"},
        {TBL_ID:"DT_1B040B3",TBL_NM:"연령별 인구수",ORG_ID:"101",ORG_NM:"통계청"}
    ]"""


@pytest.fixture
def sample_error_response() -> str:
    """KOSIS API 에러 응답 예시."""
    return '{errMsg:"해당 데이터가 없습니다.",errCode:"ERR001"}'
