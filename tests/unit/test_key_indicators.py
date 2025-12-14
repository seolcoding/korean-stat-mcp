"""
kosis_tools.key_indicators 모듈 유닛 테스트.

테스트 범위:
    - KeyIndicators.get_explanation_by_id: 지표 고유번호별 설명 조회
    - KeyIndicators.get_explanation_by_name: 지표명별 설명 조회
    - KeyIndicators.get_by_list: 목록별 지표 조회
    - KeyIndicators.search_by_name: 지표명별 목록 조회
    - KeyIndicators.search_by_id: 고유번호별 목록 조회
    - KeyIndicators.get_detail: 고유번호별 지표 상세 조회
    - KeyIndicators.search_by_period_type: 수록주기별 목록 조회
    - 데이터 클래스 변환 테스트
"""

import pytest
import responses

from kosis_tools.config import KosisConfig
from kosis_tools.key_indicators import (
    KeyIndicators,
    IndicatorEndpoint,
    IndicatorExplanation,
    IndicatorListItem,
    IndicatorSearchResult,
    IndicatorDetailData,
)


@pytest.fixture
def indicator_client(test_config: KosisConfig) -> KeyIndicators:
    """테스트용 통계주요지표 클라이언트."""
    return KeyIndicators(test_config)


@pytest.fixture
def sample_explanation_response() -> dict:
    """지표 설명 응답 샘플."""
    return {
        "response": {
            "body": {
                "items": {
                    "item": [
                        {
                            "statJipyoId": 12345,
                            "statJipyoNm": "실업률",
                            "jipyoExplan": "실업률 설명",
                            "jipyoExplan1": "경제활동인구 중 실업자가 차지하는 비율",
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def sample_list_item_response() -> dict:
    """목록별 지표 응답 샘플."""
    return {
        "response": {
            "body": {
                "items": {
                    "item": [
                        {
                            "listId": "100",
                            "listNm": "경제지표",
                            "statJipyoId": 12345,
                            "statJipyoNm": "실업률",
                            "unit": "%",
                            "areaTypeName": "전국",
                            "prdSeName": "월간",
                            "strtPrdDe": "199901",
                            "endPrdDe": "202312",
                            "rn": 300,
                            "prdDe": "2023년 12월",
                            "repJipyoId": 12345,
                            "repJipyoNm": "실업률",
                            "repJipyoUrl": "http://example.com/indicator",
                            "explainUrl": "http://example.com/explain",
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def sample_search_result_response() -> dict:
    """지표 검색 결과 응답 샘플."""
    return {
        "response": {
            "body": {
                "items": {
                    "item": [
                        {
                            "statJipyoId": 12345,
                            "statJipyoNm": "실업률",
                            "unit": "%",
                            "areaTypeName": "전국",
                            "prdSeName": "월간",
                            "strtPrdDe": "199901",
                            "endPrdDe": "202312",
                            "rn": 300,
                            "prdDe": "2023년 12월 (월간)",
                        }
                    ]
                }
            }
        }
    }


@pytest.fixture
def sample_detail_response() -> dict:
    """지표 상세 데이터 응답 샘플."""
    return {
        "response": {
            "body": {
                "items": {
                    "item": [
                        {
                            "statJipyoId": 12345,
                            "statJipyoNm": "실업률",
                            "prdSe": "M",
                            "prdDe": "202312",
                            "itmNm": "전체",
                            "val": 2.8,
                        },
                        {
                            "statJipyoId": 12345,
                            "statJipyoNm": "실업률",
                            "prdSe": "M",
                            "prdDe": "202311",
                            "itmNm": "전체",
                            "val": 2.7,
                        },
                    ]
                }
            }
        }
    }


class TestKeyIndicatorsValidation:
    """KeyIndicators 파라미터 검증 테스트."""

    def test_get_explanation_by_id_empty_raises_error(self, indicator_client: KeyIndicators):
        """빈 jipyo_id는 ValueError를 발생시켜야 함."""
        with pytest.raises(ValueError, match="jipyo_id는 필수"):
            indicator_client.get_explanation_by_id("")

    def test_get_explanation_by_name_empty_raises_error(self, indicator_client: KeyIndicators):
        """빈 jipyo_nm은 ValueError를 발생시켜야 함."""
        with pytest.raises(ValueError, match="jipyo_nm은 필수"):
            indicator_client.get_explanation_by_name("")

    def test_get_by_list_empty_raises_error(self, indicator_client: KeyIndicators):
        """빈 list_id는 ValueError를 발생시켜야 함."""
        with pytest.raises(ValueError, match="list_id는 필수"):
            indicator_client.get_by_list("")

    def test_search_by_name_empty_raises_error(self, indicator_client: KeyIndicators):
        """빈 jipyo_nm은 ValueError를 발생시켜야 함."""
        with pytest.raises(ValueError, match="jipyo_nm은 필수"):
            indicator_client.search_by_name("")

    def test_search_by_id_empty_raises_error(self, indicator_client: KeyIndicators):
        """빈 jipyo_id는 ValueError를 발생시켜야 함."""
        with pytest.raises(ValueError, match="jipyo_id는 필수"):
            indicator_client.search_by_id("")

    def test_get_detail_empty_raises_error(self, indicator_client: KeyIndicators):
        """빈 jipyo_id는 ValueError를 발생시켜야 함."""
        with pytest.raises(ValueError, match="jipyo_id는 필수"):
            indicator_client.get_detail("")

    def test_search_by_period_type_empty_raises_error(self, indicator_client: KeyIndicators):
        """빈 prd_se는 ValueError를 발생시켜야 함."""
        with pytest.raises(ValueError, match="prd_se는 필수"):
            indicator_client.search_by_period_type("")


class TestGetExplanationById:
    """KeyIndicators.get_explanation_by_id 테스트."""

    @responses.activate
    def test_success(
        self,
        indicator_client: KeyIndicators,
        sample_explanation_response: dict,
    ):
        """지표 ID로 설명 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/pkNumberService.do",
            json=sample_explanation_response,
            status=200,
        )

        result = indicator_client.get_explanation_by_id("12345")

        assert len(result) == 1
        assert result[0].jipyo_id == "12345"
        assert result[0].jipyo_nm == "실업률"
        assert "경제활동인구" in result[0].concept

        # 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "jipyoId=12345" in request_url
        assert "service=1" in request_url
        assert "serviceDetail=pkAll" in request_url

    @responses.activate
    def test_empty_response(self, indicator_client: KeyIndicators):
        """빈 응답 처리."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/pkNumberService.do",
            json={},
            status=200,
        )

        result = indicator_client.get_explanation_by_id("99999")
        assert result == []


class TestGetExplanationByName:
    """KeyIndicators.get_explanation_by_name 테스트."""

    @responses.activate
    def test_success(
        self,
        indicator_client: KeyIndicators,
        sample_explanation_response: dict,
    ):
        """지표명으로 설명 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/indExpService.do",
            json=sample_explanation_response,
            status=200,
        )

        result = indicator_client.get_explanation_by_name("실업률")

        assert len(result) == 1
        assert result[0].jipyo_nm == "실업률"

        # 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "service=2" in request_url
        assert "serviceDetail=indAll" in request_url


class TestGetByList:
    """KeyIndicators.get_by_list 테스트."""

    @responses.activate
    def test_success(
        self,
        indicator_client: KeyIndicators,
        sample_list_item_response: dict,
    ):
        """목록별 지표 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/indiListService.do",
            json=sample_list_item_response,
            status=200,
        )

        result = indicator_client.get_by_list("100")

        assert len(result) == 1
        assert result[0].list_id == "100"
        assert result[0].list_nm == "경제지표"
        assert result[0].jipyo_nm == "실업률"
        assert result[0].unit == "%"
        assert result[0].period_count == 300
        assert result[0].explain_url == "http://example.com/explain"

        # 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "listId=100" in request_url
        assert "service=3" in request_url


class TestSearchByName:
    """KeyIndicators.search_by_name 테스트."""

    @responses.activate
    def test_success(
        self,
        indicator_client: KeyIndicators,
        sample_search_result_response: dict,
    ):
        """지표명별 목록 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/indListSearchRequest.do",
            json=sample_search_result_response,
            status=200,
        )

        result = indicator_client.search_by_name("인구")

        assert len(result) == 1
        assert result[0].jipyo_nm == "실업률"
        assert result[0].unit == "%"
        assert result[0].period_type == "월간"

        # 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "serviceDetail=indList" in request_url
        assert "service=4" in request_url


class TestSearchById:
    """KeyIndicators.search_by_id 테스트."""

    @responses.activate
    def test_success(
        self,
        indicator_client: KeyIndicators,
        sample_search_result_response: dict,
    ):
        """고유번호별 목록 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/indListSearchRequest.do",
            json=sample_search_result_response,
            status=200,
        )

        result = indicator_client.search_by_id("12345")

        assert len(result) == 1
        assert result[0].jipyo_id == "12345"

        # 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "jipyoId=12345" in request_url


class TestGetDetail:
    """KeyIndicators.get_detail 테스트."""

    @responses.activate
    def test_success_with_period_range(
        self,
        indicator_client: KeyIndicators,
        sample_detail_response: dict,
    ):
        """시점 기준으로 상세 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/indIdDetailSearchRequest.do",
            json=sample_detail_response,
            status=200,
        )

        result = indicator_client.get_detail(
            jipyo_id="12345",
            start_prd_de="202301",
            end_prd_de="202312",
        )

        assert len(result) == 2
        assert result[0].jipyo_id == "12345"
        assert result[0].period == "202312"
        assert result[0].value == 2.8
        assert result[1].value == 2.7

        # 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "serviceDetail=indIdDetail" in request_url
        assert "startPrdDe=202301" in request_url
        assert "endPrdDe=202312" in request_url

    @responses.activate
    def test_success_with_latest_count(
        self,
        indicator_client: KeyIndicators,
        sample_detail_response: dict,
    ):
        """최신자료 기준으로 상세 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/indIdDetailSearchRequest.do",
            json=sample_detail_response,
            status=200,
        )

        result = indicator_client.get_detail(
            jipyo_id="12345",
            srv_rn=5,
        )

        assert len(result) == 2

        # 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "srvRn=5" in request_url


class TestSearchByPeriodType:
    """KeyIndicators.search_by_period_type 테스트."""

    @responses.activate
    def test_success(
        self,
        indicator_client: KeyIndicators,
        sample_search_result_response: dict,
    ):
        """수록주기별 목록 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/prListSearchRequest.do",
            json=sample_search_result_response,
            status=200,
        )

        result = indicator_client.search_by_period_type("Y")

        assert len(result) == 1

        # 파라미터 확인
        request_url = responses.calls[0].request.url
        assert "prdSe=Y" in request_url
        assert "serviceDetail=prList" in request_url


class TestIndicatorExplanationDataclass:
    """IndicatorExplanation 데이터클래스 테스트."""

    def test_from_api_success(self):
        """API 응답에서 객체 생성 성공."""
        data = {
            "statJipyoId": 12345,
            "statJipyoNm": "실업률",
            "jipyoExplan": "설명 제목",
            "jipyoExplan1": "개념 설명",
        }

        result = IndicatorExplanation.from_api(data)

        assert result.jipyo_id == "12345"
        assert result.jipyo_nm == "실업률"
        assert result.title == "설명 제목"
        assert result.concept == "개념 설명"

    def test_from_api_missing_fields(self):
        """누락된 필드 처리."""
        data = {"statJipyoId": 12345}

        result = IndicatorExplanation.from_api(data)

        assert result.jipyo_id == "12345"
        assert result.jipyo_nm == ""
        assert result.title == ""
        assert result.concept == ""


class TestIndicatorListItemDataclass:
    """IndicatorListItem 데이터클래스 테스트."""

    def test_from_api_full_data(self):
        """전체 데이터로 객체 생성."""
        data = {
            "listId": "100",
            "listNm": "경제지표",
            "statJipyoId": 12345,
            "statJipyoNm": "실업률",
            "unit": "%",
            "areaTypeName": "전국",
            "prdSeName": "월간",
            "strtPrdDe": "199901",
            "endPrdDe": "202312",
            "rn": 300,
            "prdDe": "2023년 12월",
            "repJipyoId": 12345,
            "repJipyoNm": "대표지표",
            "repJipyoUrl": "http://rep.url",
            "explainUrl": "http://exp.url",
        }

        result = IndicatorListItem.from_api(data)

        assert result.list_id == "100"
        assert result.rep_jipyo_id == "12345"
        assert result.explain_url == "http://exp.url"

    def test_from_api_optional_fields_none(self):
        """선택 필드가 없는 경우."""
        data = {
            "listId": "100",
            "listNm": "경제지표",
            "statJipyoId": 12345,
            "statJipyoNm": "실업률",
            "unit": "%",
            "areaTypeName": "전국",
            "prdSeName": "월간",
            "strtPrdDe": "199901",
            "endPrdDe": "202312",
            "rn": 300,
            "prdDe": "2023년 12월",
        }

        result = IndicatorListItem.from_api(data)

        assert result.rep_jipyo_id is None
        assert result.rep_jipyo_nm is None
        assert result.explain_url is None


class TestIndicatorDetailDataDataclass:
    """IndicatorDetailData 데이터클래스 테스트."""

    def test_from_api_with_value(self):
        """값이 있는 경우."""
        data = {
            "statJipyoId": 12345,
            "statJipyoNm": "실업률",
            "prdSe": "M",
            "prdDe": "202312",
            "itmNm": "전체",
            "val": 2.8,
        }

        result = IndicatorDetailData.from_api(data)

        assert result.value == 2.8
        assert result.period == "202312"

    def test_from_api_with_null_value(self):
        """값이 null인 경우."""
        data = {
            "statJipyoId": 12345,
            "statJipyoNm": "실업률",
            "prdSe": "M",
            "prdDe": "202312",
            "itmNm": "전체",
            "val": None,
        }

        result = IndicatorDetailData.from_api(data)

        assert result.value is None

    def test_from_api_with_empty_string_value(self):
        """값이 빈 문자열인 경우."""
        data = {
            "statJipyoId": 12345,
            "statJipyoNm": "실업률",
            "prdSe": "M",
            "prdDe": "202312",
            "itmNm": "전체",
            "val": "",
        }

        result = IndicatorDetailData.from_api(data)

        assert result.value is None

    def test_from_api_with_invalid_value(self):
        """값이 변환 불가능한 경우."""
        data = {
            "statJipyoId": 12345,
            "statJipyoNm": "실업률",
            "prdSe": "M",
            "prdDe": "202312",
            "itmNm": "전체",
            "val": "-",
        }

        result = IndicatorDetailData.from_api(data)

        assert result.value is None


class TestIndicatorEndpointEnum:
    """IndicatorEndpoint enum 테스트."""

    def test_endpoint_values(self):
        """엔드포인트 값 확인."""
        assert IndicatorEndpoint.PK_NUMBER.value == "pkNumberService.do"
        assert IndicatorEndpoint.IND_EXP.value == "indExpService.do"
        assert IndicatorEndpoint.INDI_LIST.value == "indiListService.do"
        assert IndicatorEndpoint.IND_LIST_SEARCH.value == "indListSearchRequest.do"
        assert IndicatorEndpoint.IND_ID_DETAIL.value == "indIdDetailSearchRequest.do"
        assert IndicatorEndpoint.PR_LIST_SEARCH.value == "prListSearchRequest.do"


class TestExtractItems:
    """KeyIndicators._extract_items 테스트."""

    def test_extract_from_list(self, indicator_client: KeyIndicators):
        """리스트 응답에서 추출."""
        response = [{"id": 1}, {"id": 2}]
        result = indicator_client._extract_items(response)
        assert len(result) == 2

    def test_extract_from_nested_response(self, indicator_client: KeyIndicators):
        """중첩된 response 형식에서 추출."""
        response = {
            "response": {
                "body": {
                    "items": {
                        "item": [{"id": 1}]
                    }
                }
            }
        }
        result = indicator_client._extract_items(response)
        assert len(result) == 1

    def test_extract_from_body_items(self, indicator_client: KeyIndicators):
        """body > items 형식에서 추출."""
        response = {
            "body": {
                "items": {
                    "item": [{"id": 1}, {"id": 2}]
                }
            }
        }
        result = indicator_client._extract_items(response)
        assert len(result) == 2

    def test_extract_single_item_as_dict(self, indicator_client: KeyIndicators):
        """단일 항목이 dict인 경우."""
        response = {
            "response": {
                "body": {
                    "items": {
                        "item": {"id": 1}
                    }
                }
            }
        }
        result = indicator_client._extract_items(response)
        assert len(result) == 1
        assert result[0]["id"] == 1

    def test_extract_empty_dict(self, indicator_client: KeyIndicators):
        """빈 딕셔너리에서 추출."""
        response = {}
        result = indicator_client._extract_items(response)
        assert result == []

    def test_extract_from_items_direct(self, indicator_client: KeyIndicators):
        """items 직접 형식에서 추출."""
        response = {
            "items": [{"id": 1}]
        }
        result = indicator_client._extract_items(response)
        assert len(result) == 1
