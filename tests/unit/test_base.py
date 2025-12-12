"""
kosis_tools.base 모듈 유닛 테스트.

테스트 범위:
    - fix_malformed_json: KOSIS 비표준 JSON 파싱
    - KosisBaseClient: HTTP 요청, rate limiting, 재시도 로직
"""

import pytest
import responses
from responses import matchers

from kosis_tools.base import KosisBaseClient, fix_malformed_json
from kosis_tools.config import KosisConfig


class TestFixMalformedJson:
    """fix_malformed_json 함수 테스트."""

    def test_empty_string_returns_none(self):
        """빈 문자열은 None을 반환해야 함."""
        assert fix_malformed_json("") is None

    def test_whitespace_only_returns_none(self):
        """공백만 있는 문자열은 None을 반환해야 함."""
        assert fix_malformed_json("   ") is None

    def test_none_returns_none(self):
        """None 입력은 None을 반환해야 함 (타입 에러 방지)."""
        # Python에서는 None에 대해 strip() 호출 시 에러 발생
        # 함수가 이를 처리하는지 확인
        assert fix_malformed_json(None) is None

    def test_valid_json_parsed_correctly(self, sample_valid_json: str):
        """정상적인 JSON은 그대로 파싱되어야 함."""
        result = fix_malformed_json(sample_valid_json)
        assert result is not None
        assert result["TBL_ID"] == "DT_1B040A3"
        assert result["TBL_NM"] == "행정구역별 인구수"

    def test_malformed_json_fixed_and_parsed(self, sample_malformed_json: str):
        """KOSIS 비표준 JSON이 수정 후 파싱되어야 함."""
        result = fix_malformed_json(sample_malformed_json)
        assert result is not None
        assert result["TBL_ID"] == "DT_1B040A3"
        assert result["TBL_NM"] == "행정구역별 인구수"
        assert result["ORG_ID"] == "101"

    def test_malformed_list_response(self, sample_list_response: str):
        """KOSIS 비표준 JSON 배열 응답이 파싱되어야 함."""
        result = fix_malformed_json(sample_list_response)
        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["TBL_ID"] == "DT_1B040A3"
        assert result[1]["TBL_ID"] == "DT_1B040B3"

    def test_error_response_parsed(self, sample_error_response: str):
        """API 에러 응답도 파싱되어야 함 (errMsg 포함)."""
        result = fix_malformed_json(sample_error_response)
        assert result is not None
        assert "errMsg" in result
        assert result["errMsg"] == "해당 데이터가 없습니다."

    def test_invalid_json_returns_none(self):
        """완전히 잘못된 JSON은 None을 반환해야 함."""
        result = fix_malformed_json("this is not json at all")
        assert result is None

    def test_nested_object(self):
        """중첩 객체도 파싱되어야 함."""
        nested = '{outer:{inner:"value",num:123}}'
        result = fix_malformed_json(nested)
        assert result is not None
        assert result["outer"]["inner"] == "value"
        assert result["outer"]["num"] == 123


class TestKosisConfig:
    """KosisConfig 테스트."""

    def test_config_requires_api_key(self):
        """api_key는 필수 필드."""
        with pytest.raises(TypeError):
            KosisConfig()  # api_key 없이 생성 시도

    def test_config_empty_api_key_raises_error(self):
        """빈 api_key는 ValueError 발생."""
        with pytest.raises(ValueError, match="api_key는 필수"):
            KosisConfig(api_key="")

    def test_config_default_values(self):
        """기본값이 올바르게 설정되어야 함."""
        config = KosisConfig(api_key="test-key")
        assert config.base_url == "https://kosis.kr/openapi"
        assert config.rate_limit_delay == 1.0
        assert config.timeout == 60
        assert config.max_retries == 3
        assert config.retry_delay == 2.0

    def test_config_custom_values(self):
        """커스텀 값이 올바르게 설정되어야 함."""
        config = KosisConfig(
            api_key="my-key",
            base_url="https://custom.url",
            rate_limit_delay=0.5,
            timeout=30,
            max_retries=5,
            retry_delay=1.0,
        )
        assert config.api_key == "my-key"
        assert config.base_url == "https://custom.url"
        assert config.rate_limit_delay == 0.5
        assert config.timeout == 30
        assert config.max_retries == 5
        assert config.retry_delay == 1.0

    def test_config_negative_rate_limit_raises_error(self):
        """음수 rate_limit_delay는 ValueError 발생."""
        with pytest.raises(ValueError, match="rate_limit_delay"):
            KosisConfig(api_key="test", rate_limit_delay=-1)

    def test_config_zero_timeout_raises_error(self):
        """0 이하 timeout은 ValueError 발생."""
        with pytest.raises(ValueError, match="timeout"):
            KosisConfig(api_key="test", timeout=0)


class TestKosisBaseClient:
    """KosisBaseClient 테스트."""

    def test_client_initialization_with_config(self, test_config: KosisConfig):
        """config를 주입받아 클라이언트 초기화."""
        client = KosisBaseClient(test_config)
        assert client.config.api_key == "test-api-key"
        assert client.config.rate_limit_delay == 0

    def test_client_context_manager(self, test_config: KosisConfig):
        """컨텍스트 매니저로 사용 가능해야 함."""
        with KosisBaseClient(test_config) as client:
            assert client is not None

    @responses.activate
    def test_request_success(self, test_config: KosisConfig):
        """성공적인 HTTP 요청."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/test.do",
            json={"TBL_ID": "DT_123", "TBL_NM": "테스트"},
            status=200,
        )

        client = KosisBaseClient(test_config)
        result = client._request("GET", "test.do", {"param": "value"})

        assert result is not None
        assert result["TBL_ID"] == "DT_123"
        assert len(responses.calls) == 1
        assert "apiKey=test-api-key" in responses.calls[0].request.url

    @responses.activate
    def test_request_with_malformed_json(self, test_config: KosisConfig):
        """비표준 JSON 응답 처리."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/test.do",
            body='{TBL_ID:"DT_123",TBL_NM:"테스트"}',
            status=200,
        )

        client = KosisBaseClient(test_config)
        result = client._request("GET", "test.do")

        assert result is not None
        assert result["TBL_ID"] == "DT_123"

    @responses.activate
    def test_request_api_error_returns_none(self, test_config: KosisConfig):
        """API 에러 응답(errMsg)은 None 반환."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/test.do",
            json={"errMsg": "데이터가 없습니다", "errCode": "ERR001"},
            status=200,
        )

        client = KosisBaseClient(test_config)
        result = client._request("GET", "test.do")

        assert result is None

    @responses.activate
    def test_request_http_error_returns_none(self, test_config: KosisConfig):
        """HTTP 에러(4xx, 5xx)는 None 반환."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/test.do",
            status=500,
        )

        client = KosisBaseClient(test_config)
        result = client._request("GET", "test.do")

        assert result is None

    @responses.activate
    def test_request_retry_on_failure(self):
        """네트워크 오류 시 재시도."""
        import requests as req

        # 첫 번째는 실패 (ConnectionError), 두 번째는 성공
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/test.do",
            body=req.exceptions.ConnectionError("Network error"),
        )
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/test.do",
            json={"success": True},
            status=200,
        )

        config = KosisConfig(
            api_key="test",
            rate_limit_delay=0,
            max_retries=1,
            retry_delay=0,
        )
        client = KosisBaseClient(config)
        result = client._request("GET", "test.do")

        assert result is not None
        assert result["success"] is True
        assert len(responses.calls) == 2

    @responses.activate
    def test_request_max_retries_exceeded(self):
        """최대 재시도 횟수 초과 시 None 반환."""
        import requests as req

        # 모든 요청 실패 (ConnectionError)
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/test.do",
            body=req.exceptions.ConnectionError("Network error"),
        )
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/test.do",
            body=req.exceptions.ConnectionError("Network error"),
        )

        config = KosisConfig(
            api_key="test",
            rate_limit_delay=0,
            max_retries=1,
            retry_delay=0,
        )
        client = KosisBaseClient(config)
        result = client._request("GET", "test.do")

        assert result is None
        assert len(responses.calls) == 2  # 초기 시도 + 1회 재시도
