"""
kosis_tools.search 모듈 유닛 테스트.

테스트 범위:
    - StatisticsSearch.search: 키워드 검색
    - StatisticsSearch.search_by_table_id: 테이블 ID로 검색
"""

import pytest
import responses

from kosis_tools.config import KosisConfig
from kosis_tools.search import StatisticsSearch


@pytest.fixture
def search_client(test_config: KosisConfig) -> StatisticsSearch:
    """테스트용 검색 클라이언트."""
    return StatisticsSearch(test_config)


@pytest.fixture
def sample_search_response() -> str:
    """검색 결과 샘플 (KOSIS 비표준 JSON)."""
    return """[
        {TBL_ID:"DT_1B040A3",TBL_NM:"행정구역별 인구수",ORG_ID:"101",ORG_NM:"통계청",STRT_PRD_DE:"1992",END_PRD_DE:"2023"},
        {TBL_ID:"DT_1B040B3",TBL_NM:"연령별 인구수",ORG_ID:"101",ORG_NM:"통계청",STRT_PRD_DE:"1995",END_PRD_DE:"2023"}
    ]"""


@pytest.fixture
def single_result_response() -> str:
    """단일 검색 결과 샘플."""
    return '{TBL_ID:"DT_1B040A3",TBL_NM:"행정구역별 인구수",ORG_ID:"101"}'


class TestStatisticsSearch:
    """StatisticsSearch 클래스 테스트."""

    def test_search_empty_keyword_returns_empty_list(self, search_client: StatisticsSearch):
        """빈 키워드는 빈 리스트를 반환해야 함."""
        result = search_client.search("")
        assert result == []

    def test_search_whitespace_keyword_returns_empty_list(self, search_client: StatisticsSearch):
        """공백만 있는 키워드는 빈 리스트를 반환해야 함."""
        result = search_client.search("   ")
        assert result == []

    @responses.activate
    def test_search_success(self, search_client: StatisticsSearch, sample_search_response: str):
        """성공적인 검색."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsSearch.do",
            body=sample_search_response,
            status=200,
        )

        result = search_client.search("인구")

        assert len(result) == 2
        assert result[0]["TBL_ID"] == "DT_1B040A3"
        assert result[0]["TBL_NM"] == "행정구역별 인구수"
        assert result[1]["TBL_ID"] == "DT_1B040B3"

    @responses.activate
    def test_search_with_org_filter(self, search_client: StatisticsSearch, sample_search_response: str):
        """기관 필터링 검색."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsSearch.do",
            body=sample_search_response,
            status=200,
        )

        result = search_client.search("인구", org_id="101")

        assert len(result) == 2
        # 요청에 orgId 파라미터가 포함되었는지 확인
        assert "orgId=101" in responses.calls[0].request.url

    @responses.activate
    def test_search_single_result(self, search_client: StatisticsSearch, single_result_response: str):
        """단일 결과 검색 (dict 반환을 list로 변환)."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsSearch.do",
            body=single_result_response,
            status=200,
        )

        result = search_client.search("인구")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["TBL_ID"] == "DT_1B040A3"

    @responses.activate
    def test_search_no_results(self, search_client: StatisticsSearch):
        """검색 결과 없음 (API 에러 응답)."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsSearch.do",
            json={"errMsg": "데이터가 없습니다", "errCode": "ERR001"},
            status=200,
        )

        result = search_client.search("존재하지않는검색어xyz")

        assert result == []

    @responses.activate
    def test_search_http_error(self, search_client: StatisticsSearch):
        """HTTP 에러 시 빈 리스트 반환."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsSearch.do",
            status=500,
        )

        result = search_client.search("인구")

        assert result == []

    @responses.activate
    def test_search_api_key_included(self, search_client: StatisticsSearch, sample_search_response: str):
        """요청에 API 키가 포함되어야 함."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsSearch.do",
            body=sample_search_response,
            status=200,
        )

        search_client.search("테스트")

        assert "apiKey=test-api-key" in responses.calls[0].request.url


class TestSearchByTableId:
    """search_by_table_id 메서드 테스트."""

    def test_empty_table_id_returns_none(self, search_client: StatisticsSearch):
        """빈 테이블 ID는 None을 반환해야 함."""
        result = search_client.search_by_table_id("")
        assert result is None

    @responses.activate
    def test_search_by_table_id_exact_match(self, search_client: StatisticsSearch, sample_search_response: str):
        """테이블 ID 정확히 일치하는 결과 반환."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsSearch.do",
            body=sample_search_response,
            status=200,
        )

        result = search_client.search_by_table_id("DT_1B040A3")

        assert result is not None
        assert result["TBL_ID"] == "DT_1B040A3"
        assert result["TBL_NM"] == "행정구역별 인구수"

    @responses.activate
    def test_search_by_table_id_not_found(self, search_client: StatisticsSearch):
        """테이블을 찾지 못한 경우 None 반환."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsSearch.do",
            json={"errMsg": "데이터가 없습니다"},
            status=200,
        )

        result = search_client.search_by_table_id("NOT_EXIST_ID")

        assert result is None
