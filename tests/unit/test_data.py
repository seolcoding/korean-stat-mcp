"""
kosis_tools.data 모듈 유닛 테스트.

테스트 범위:
    - StatisticsData.get_data: 직접 데이터 조회
    - StatisticsData.get_data_with_retry: 재시도 로직
    - StatisticsData.get_data_auto_period: 자동 주기 탐색
    - _format_date_for_period: 날짜 포맷팅
"""

import pytest
import responses

from kosis_tools.config import KosisConfig, PeriodType
from kosis_tools.data import StatisticsData


@pytest.fixture
def data_client(test_config: KosisConfig) -> StatisticsData:
    """테스트용 데이터 클라이언트."""
    return StatisticsData(test_config)


@pytest.fixture
def sample_data_response() -> str:
    """데이터 조회 결과 샘플 (KOSIS 비표준 JSON)."""
    return """[
        {TBL_ID:"DT_1B040A3",PRD_DE:"2023",C1:"00",C1_NM:"전국",ITM_ID:"T20",ITM_NM:"인구수",DT:"51823154",UNIT_NM:"명"},
        {TBL_ID:"DT_1B040A3",PRD_DE:"2023",C1:"11",C1_NM:"서울특별시",ITM_ID:"T20",ITM_NM:"인구수",DT:"9411453",UNIT_NM:"명"},
        {TBL_ID:"DT_1B040A3",PRD_DE:"2022",C1:"00",C1_NM:"전국",ITM_ID:"T20",ITM_NM:"인구수",DT:"51628117",UNIT_NM:"명"}
    ]"""


@pytest.fixture
def single_data_response() -> str:
    """단일 데이터 결과 샘플."""
    return '{TBL_ID:"DT_1B040A3",PRD_DE:"2023",C1:"00",C1_NM:"전국",DT:"51823154"}'


class TestStatisticsDataGetData:
    """StatisticsData.get_data 테스트."""

    def test_empty_org_id_returns_empty_list(self, data_client: StatisticsData):
        """빈 org_id는 빈 리스트를 반환해야 함."""
        result = data_client.get_data("", "DT_123", "2020", "2023")
        assert result == []

    def test_empty_tbl_id_returns_empty_list(self, data_client: StatisticsData):
        """빈 tbl_id는 빈 리스트를 반환해야 함."""
        result = data_client.get_data("101", "", "2020", "2023")
        assert result == []

    @responses.activate
    def test_get_data_success(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """데이터 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )

        result = data_client.get_data("101", "DT_1B040A3", "2020", "2023")

        assert len(result) == 3
        assert result[0]["DT"] == "51823154"
        assert result[0]["C1_NM"] == "전국"
        assert result[1]["C1_NM"] == "서울특별시"

    @responses.activate
    def test_get_data_with_period_type(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """주기 타입 지정 조회."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )

        data_client.get_data("101", "DT_1B040A3", "2020", "2023", prd_se="Y")

        assert "prdSe=Y" in responses.calls[0].request.url

    @responses.activate
    def test_get_data_with_obj_l2(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """objL2 파라미터 포함 조회."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )

        data_client.get_data("101", "DT_1B040A3", "2020", "2023", obj_l2="ALL")

        assert "objL2=ALL" in responses.calls[0].request.url

    @responses.activate
    def test_get_data_single_result(
        self, data_client: StatisticsData, single_data_response: str
    ):
        """단일 결과 조회 (dict 반환을 list로 변환)."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=single_data_response,
            status=200,
        )

        result = data_client.get_data("101", "DT_1B040A3", "2023", "2023")

        assert isinstance(result, list)
        assert len(result) == 1

    @responses.activate
    def test_get_data_empty_result(self, data_client: StatisticsData):
        """결과 없음."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            json={"errMsg": "데이터가 없습니다"},
            status=200,
        )

        result = data_client.get_data("101", "DT_123", "2020", "2023")

        assert result == []


class TestStatisticsDataWithRetry:
    """StatisticsData.get_data_with_retry 테스트."""

    @responses.activate
    def test_first_attempt_success(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """첫 번째 시도 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )

        result = data_client.get_data_with_retry("101", "DT_1B040A3", "2020", "2023")

        assert len(result) == 3
        # 첫 번째 시도만 수행됨
        assert len(responses.calls) == 1
        assert "objL2" not in responses.calls[0].request.url

    @responses.activate
    def test_second_attempt_success(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """첫 번째 실패 후 두 번째 성공."""
        # 첫 번째 시도: 실패
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            json={"errMsg": "데이터가 없습니다"},
            status=200,
        )
        # 두 번째 시도: 성공
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )

        result = data_client.get_data_with_retry("101", "DT_1B040A3", "2020", "2023")

        assert len(result) == 3
        assert len(responses.calls) == 2
        # 두 번째 시도에 objL2 포함
        assert "objL2=ALL" in responses.calls[1].request.url

    @responses.activate
    def test_both_attempts_fail(self, data_client: StatisticsData):
        """두 번 모두 실패."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            json={"errMsg": "데이터가 없습니다"},
            status=200,
        )
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            json={"errMsg": "데이터가 없습니다"},
            status=200,
        )

        result = data_client.get_data_with_retry("101", "DT_1B040A3", "2020", "2023")

        assert result == []
        assert len(responses.calls) == 2


class TestStatisticsDataAutoPeriod:
    """StatisticsData.get_data_auto_period 테스트."""

    @responses.activate
    def test_auto_period_first_try_success(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """첫 번째 주기(월간)에서 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )

        result = data_client.get_data_auto_period("101", "DT_1B040A3", "2020", "2023")

        assert result is not None
        assert result["period_type"] == "M"
        assert result["period_name"] == "월간"
        assert len(result["data"]) == 3

    @responses.activate
    def test_auto_period_yearly_success(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """월간, 분기, 반기 실패 후 연간 성공."""
        # M, Q, S 실패 (각각 2번씩 시도 = 6회)
        for _ in range(6):
            responses.add(
                responses.GET,
                "https://kosis.kr/openapi/Param/statisticsParameterData.do",
                json={"errMsg": "데이터가 없습니다"},
                status=200,
            )
        # Y 성공
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )

        result = data_client.get_data_auto_period("101", "DT_1B040A3", "2020", "2023")

        assert result is not None
        assert result["period_type"] == "Y"
        assert result["period_name"] == "연간"

    @responses.activate
    def test_auto_period_all_fail(self, data_client: StatisticsData):
        """모든 주기에서 실패."""
        # 6개 주기 * 2회 시도 = 12회 실패
        for _ in range(12):
            responses.add(
                responses.GET,
                "https://kosis.kr/openapi/Param/statisticsParameterData.do",
                json={"errMsg": "데이터가 없습니다"},
                status=200,
            )

        result = data_client.get_data_auto_period("101", "DT_1B040A3", "2020", "2023")

        assert result is None


class TestFormatDateForPeriod:
    """_format_date_for_period 메서드 테스트."""

    def test_monthly_with_year_only(self, data_client: StatisticsData):
        """월간: 연도만 있으면 01월 추가."""
        result = data_client._format_date_for_period("2023", "M")
        assert result == "202301"

    def test_monthly_with_full_date(self, data_client: StatisticsData):
        """월간: 이미 월이 있으면 그대로."""
        result = data_client._format_date_for_period("202312", "M")
        assert result == "202312"

    def test_quarterly_with_year_only(self, data_client: StatisticsData):
        """분기: 연도만 있으면 01분기 추가."""
        result = data_client._format_date_for_period("2023", "Q")
        assert result == "202301"

    def test_yearly_strips_month(self, data_client: StatisticsData):
        """연간: 월 정보 제거."""
        result = data_client._format_date_for_period("202312", "Y")
        assert result == "2023"

    def test_yearly_with_year_only(self, data_client: StatisticsData):
        """연간: 연도만 있으면 그대로."""
        result = data_client._format_date_for_period("2023", "Y")
        assert result == "2023"

    def test_multi_year_same_as_yearly(self, data_client: StatisticsData):
        """다년: 연간과 동일."""
        result = data_client._format_date_for_period("202312", "F")
        assert result == "2023"

    def test_irregular_with_full_date(self, data_client: StatisticsData):
        """부정기: 전체 날짜."""
        result = data_client._format_date_for_period("20231215", "IR")
        assert result == "20231215"

    def test_irregular_with_year_only(self, data_client: StatisticsData):
        """부정기: 연도만 있으면 그대로."""
        result = data_client._format_date_for_period("2023", "IR")
        assert result == "2023"

    def test_removes_non_numeric(self, data_client: StatisticsData):
        """비숫자 문자 제거."""
        result = data_client._format_date_for_period("2023-12", "M")
        assert result == "202312"


class TestPeriodTypeConstants:
    """PeriodType 상수 테스트."""

    def test_period_codes(self):
        """주기 코드 확인."""
        assert PeriodType.MONTHLY == "M"
        assert PeriodType.QUARTERLY == "Q"
        assert PeriodType.SEMI_ANNUAL == "S"
        assert PeriodType.YEARLY == "Y"
        assert PeriodType.MULTI_YEAR == "F"
        assert PeriodType.IRREGULAR == "IR"

    def test_priority_order(self):
        """주기 우선순위 순서."""
        assert PeriodType.PRIORITY_ORDER == ["M", "Q", "S", "Y", "F", "IR"]

    def test_names_mapping(self):
        """한글 이름 매핑."""
        assert PeriodType.NAMES["M"] == "월간"
        assert PeriodType.NAMES["Y"] == "연간"
