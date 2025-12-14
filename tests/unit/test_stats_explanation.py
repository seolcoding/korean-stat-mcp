"""
kosis_tools.stats_explanation 모듈 유닛 테스트.

테스트 범위:
    - StatsExplanation.get_by_stat_id: 통계 ID로 조회
    - StatsExplanation.get_by_table: 테이블 ID로 조회
    - StatsExplanation.get_survey_purpose: 조사목적 조회
    - StatsExplanation.get_llm_context: LLM 컨텍스트 조회
    - MetaItem 상수
"""

import pytest
import responses

from kosis_tools.config import KosisConfig
from kosis_tools.stats_explanation import StatsExplanation, MetaItem


@pytest.fixture
def expl_client(test_config: KosisConfig) -> StatsExplanation:
    """테스트용 통계설명 클라이언트."""
    return StatsExplanation(test_config)


@pytest.fixture
def sample_expl_response() -> str:
    """통계설명 응답 샘플 (KOSIS 비표준 JSON)."""
    return """[{
        statsNm:"가계동향조사",
        statsKind:"조사통계",
        statsPeriod:"분기",
        confmNo:"101006",
        writingPurps:"가구에 대한 가계수지 실태를 파악하여 국민의 소득과 소비 수준변화의 측정",
        examinObjrange:"전국 가구",
        examinObjArea:"전국",
        josaItm:"소득, 지출, 가구구성",
        mainTermExpl:"소득: 가구에 유입된 금액",
        dataUserNote:"조사 방법 변경으로 시계열 비교 주의"
    }]"""


@pytest.fixture
def sample_purpose_response() -> str:
    """조사목적만 포함된 응답."""
    return """[{writingPurps:"가구에 대한 가계수지 실태를 파악"}]"""


class TestMetaItem:
    """MetaItem 상수 테스트."""

    def test_all_constant(self):
        """ALL 상수 확인."""
        assert MetaItem.ALL == "All"

    def test_stats_nm_constant(self):
        """조사명 상수 확인."""
        assert MetaItem.STATS_NM == "statsNm"

    def test_writing_purps_constant(self):
        """조사목적 상수 확인."""
        assert MetaItem.WRITING_PURPS == "writingPurps"

    def test_main_term_expl_constant(self):
        """주요용어 상수 확인."""
        assert MetaItem.MAIN_TERM_EXPL == "mainTermExpl"


class TestStatsExplanationGetByStatId:
    """StatsExplanation.get_by_stat_id 테스트."""

    def test_empty_stat_id_returns_none(self, expl_client: StatsExplanation):
        """빈 통계 ID는 None을 반환해야 함."""
        result = expl_client.get_by_stat_id("")
        assert result is None

    @responses.activate
    def test_get_by_stat_id_success(self, expl_client: StatsExplanation, sample_expl_response: str):
        """통계 ID로 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsExplData.do",
            body=sample_expl_response,
            status=200,
        )

        result = expl_client.get_by_stat_id("1962009")

        assert result is not None
        assert result["statsNm"] == "가계동향조사"
        assert result["statsKind"] == "조사통계"
        assert result["statsPeriod"] == "분기"
        # 파라미터 확인
        assert "method=getList" in responses.calls[0].request.url
        assert "statId=1962009" in responses.calls[0].request.url
        assert "metaItm=All" in responses.calls[0].request.url

    @responses.activate
    def test_get_by_stat_id_with_meta_items(self, expl_client: StatsExplanation, sample_purpose_response: str):
        """특정 메타 항목만 조회."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsExplData.do",
            body=sample_purpose_response,
            status=200,
        )

        result = expl_client.get_by_stat_id("1962009", [MetaItem.WRITING_PURPS])

        assert result is not None
        assert "writingPurps" in result
        # 파라미터 확인
        assert "metaItm=writingPurps" in responses.calls[0].request.url

    @responses.activate
    def test_get_by_stat_id_not_found(self, expl_client: StatsExplanation):
        """존재하지 않는 통계 ID."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsExplData.do",
            json={"errMsg": "데이터가 없습니다"},
            status=200,
        )

        result = expl_client.get_by_stat_id("9999999")

        assert result is None


class TestStatsExplanationGetByTable:
    """StatsExplanation.get_by_table 테스트."""

    def test_empty_org_id_returns_none(self, expl_client: StatsExplanation):
        """빈 기관 ID는 None을 반환해야 함."""
        result = expl_client.get_by_table("", "DT_1L9H001")
        assert result is None

    def test_empty_tbl_id_returns_none(self, expl_client: StatsExplanation):
        """빈 테이블 ID는 None을 반환해야 함."""
        result = expl_client.get_by_table("101", "")
        assert result is None

    @responses.activate
    def test_get_by_table_success(self, expl_client: StatsExplanation, sample_expl_response: str):
        """테이블 ID로 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsExplData.do",
            body=sample_expl_response,
            status=200,
        )

        result = expl_client.get_by_table("101", "DT_1L9H001")

        assert result is not None
        assert result["statsNm"] == "가계동향조사"
        # 파라미터 확인
        assert "orgId=101" in responses.calls[0].request.url
        assert "tblId=DT_1L9H001" in responses.calls[0].request.url


class TestStatsExplanationConvenienceMethods:
    """편의 메서드 테스트."""

    @responses.activate
    def test_get_survey_purpose(self, expl_client: StatsExplanation, sample_purpose_response: str):
        """조사목적 조회."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsExplData.do",
            body=sample_purpose_response,
            status=200,
        )

        result = expl_client.get_survey_purpose(stat_id="1962009")

        assert result is not None
        assert "가계수지" in result

    def test_get_survey_purpose_no_ids(self, expl_client: StatsExplanation):
        """ID 없이 조회 시 None 반환."""
        result = expl_client.get_survey_purpose()
        assert result is None

    @responses.activate
    def test_get_llm_context(self, expl_client: StatsExplanation, sample_expl_response: str):
        """LLM 컨텍스트 조회."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsExplData.do",
            body=sample_expl_response,
            status=200,
        )

        result = expl_client.get_llm_context(stat_id="1962009")

        assert result is not None
        assert result["name"] == "가계동향조사"
        assert result["kind"] == "조사통계"
        assert result["period"] == "분기"
        assert "가계수지" in result["purpose"]
        assert result["target"] == "전국 가구"
        assert result["area"] == "전국"

    def test_get_llm_context_no_ids(self, expl_client: StatsExplanation):
        """ID 없이 조회 시 None 반환."""
        result = expl_client.get_llm_context()
        assert result is None
