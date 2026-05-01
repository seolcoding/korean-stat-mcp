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


class TestPeriodHelpers:
    """get_data with newEstPrdCnt / prdInterval keyword-only args."""

    @responses.activate
    def test_new_est_prd_cnt_passthrough(self, data_client: StatisticsData):
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body="[]",
            status=200,
        )
        data_client.get_data(
            org_id="101",
            tbl_id="DT_1B040A3",
            start_date="",
            end_date="",
            prd_se="Y",
            new_est_prd_cnt=5,
        )
        url = responses.calls[0].request.url
        assert "newEstPrdCnt=5" in url

    @responses.activate
    def test_prd_interval_passthrough(self, data_client: StatisticsData):
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body="[]",
            status=200,
        )
        data_client.get_data(
            org_id="101",
            tbl_id="DT_1B040A3",
            start_date="2010",
            end_date="2023",
            prd_se="Y",
            prd_interval=2,
        )
        url = responses.calls[0].request.url
        assert "prdInterval=2" in url

    @responses.activate
    def test_omitted_when_none(self, data_client: StatisticsData):
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body="[]",
            status=200,
        )
        data_client.get_data(
            org_id="101",
            tbl_id="DT_1B040A3",
            start_date="2023",
            end_date="2023",
            prd_se="Y",
        )
        url = responses.calls[0].request.url
        assert "newEstPrdCnt" not in url
        assert "prdInterval" not in url


# =============================================================================
# Smart-retry FSM coverage (data.py 24% → 60%+ goal, QA report A3)
# =============================================================================


class TestExecuteWithObjRetry:
    """_execute_with_obj_retry 점진적 objL 확장 전략 검증.

    이 함수는 objL1~objL4를 순차로 확장(strategies 1-4)하다 데이터가 잡히면
    조기 반환하므로, 모킹할 때 strategy 단계마다 응답을 다르게 줘야 한다.
    """

    @responses.activate
    def test_strategy_1_objL1_all_succeeds(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """첫 시도(strategy 1: objL1=ALL)에서 데이터를 받으면 추가 호출 없이 반환."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )

        result = data_client._execute_with_obj_retry(
            org_id="101",
            tbl_id="DT_1B040A3",
            start_date="2022",
            end_date="2023",
            prd_se="Y",
            obj_vars=[{"OBJ_ID": "ITEM", "OBJ_LV": "1"}],
            itm_id="ALL",
        )

        assert len(result) == 3
        # strategy 1만 호출됨 (전국 단일 첫 attempt 성공)
        assert len(responses.calls) == 1
        url = responses.calls[0].request.url
        assert "objL1=ALL" in url
        assert "objL2" not in url

    @responses.activate
    def test_strategy_falls_through_to_objL2(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """strategy 1(objL1만) 빈 결과 → strategy 2(objL1+objL2 ALL)에서 성공."""
        # 1차: 빈 결과
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body="[]",
            status=200,
        )
        # 2차: 성공
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )

        result = data_client._execute_with_obj_retry(
            org_id="101",
            tbl_id="DT_1B040A3",
            start_date="2022",
            end_date="2023",
            prd_se="Y",
            obj_vars=[{"OBJ_ID": "ITEM", "OBJ_LV": "1"}],
            itm_id="ALL",
        )

        assert len(result) == 3
        assert len(responses.calls) == 2
        # 두번째 호출에 objL2=ALL 포함
        url2 = responses.calls[1].request.url
        assert "objL1=ALL" in url2
        assert "objL2=ALL" in url2


class TestNoObjMetadataStrategies:
    """_try_no_obj_metadata_strategies — OBJ 메타가 없는 테이블 fallback."""

    @responses.activate
    def test_regional_table_first_pattern_succeeds(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """org_id="202" (부산) → region_code "26"으로 첫 시도 패턴 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )

        result = data_client._try_no_obj_metadata_strategies(
            org_id="202",
            tbl_id="DT_B_PUSAN",
            start_date="2022",
            end_date="2023",
            prd_se="Y",
            itm_id="ALL",
        )

        assert len(result) == 3
        url = responses.calls[0].request.url
        assert "objL1=26" in url  # 부산 지역 코드


class TestFetchWithPeriodSplit:
    """_fetch_with_period_split — 대용량 결과를 기간 분할로 회피."""

    @responses.activate
    def test_yearly_split_into_decade_chunks(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """연간(Y) prd_se: 10년 단위 분할 후 결과 병합."""
        # 연간이라 10년 chunk_years. 2010~2025는 2 chunks (2010-2019 + 2020-2025).
        # 호출 횟수 = 2.
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )

        result = data_client._fetch_with_period_split(
            org_id="101",
            tbl_id="DT_1B040A3",
            start_date="2010",
            end_date="2025",
            prd_se="Y",
            obj_l1="ALL",
            obj_l2=None,
            itm_id="ALL",
            max_records_per_call=10000,
        )

        # 두 chunk 호출 발생
        assert len(responses.calls) == 2
        # _deduplicate_records로 중복 키 (PRD_DE+C1+ITM_ID) 정리: 두 응답이 동일하므로 3건
        assert len(result) == 3

    @responses.activate
    def test_monthly_split_uses_yearly_chunks(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """월간(M) prd_se: 1년씩 chunk_years=1 분할."""
        # 2022-2023: 2 chunks 발생
        for _ in range(2):
            responses.add(
                responses.GET,
                "https://kosis.kr/openapi/Param/statisticsParameterData.do",
                body=sample_data_response,
                status=200,
            )

        data_client._fetch_with_period_split(
            org_id="101",
            tbl_id="DT_M",
            start_date="202201",
            end_date="202312",
            prd_se="M",
            obj_l1="ALL",
            obj_l2=None,
            itm_id="ALL",
            max_records_per_call=10000,
        )

        assert len(responses.calls) == 2
        # 첫 chunk 종료일이 12월로 보정되는지 확인
        url1 = responses.calls[0].request.url
        assert "endPrdDe=202212" in url1


class TestSmartRetryShortCircuit:
    """get_data_with_smart_retry: newEstPrdCnt/prdInterval 지정 시 메타 우회."""

    @responses.activate
    def test_short_circuit_with_new_est_prd_cnt(
        self, data_client: StatisticsData, sample_data_response: str
    ):
        """new_est_prd_cnt 가 있으면 TableMetadata.get_prd_info 호출 없이 바로 get_data."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/Param/statisticsParameterData.do",
            body=sample_data_response,
            status=200,
        )

        result = data_client.get_data_with_smart_retry(
            org_id="101",
            tbl_id="DT_1B040A3",
            prd_se="Y",
            new_est_prd_cnt=3,
        )

        # KOSIS 메타 호출 없음 — 단일 데이터 호출만.
        assert len(responses.calls) == 1
        url = responses.calls[0].request.url
        assert "newEstPrdCnt=3" in url
        assert "statisticsData.do" not in url  # getMeta 안 침
        assert len(result) == 3
