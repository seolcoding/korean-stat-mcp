"""
kosis_tools.list_categories 모듈 유닛 테스트.

테스트 범위:
    - CategoryList.list_by_org: 기관별 통계 목록
    - CategoryList.list_by_theme: 주제별 통계 목록
    - CategoryList.list_statistics: 기관의 상위 통계 목록
    - OrgCode, ThemeCode 상수
"""

import pytest
import responses

from kosis_tools.config import KosisConfig
from kosis_tools.list_categories import CategoryList, OrgCode, ThemeCode


@pytest.fixture
def category_client(test_config: KosisConfig) -> CategoryList:
    """테스트용 카테고리 클라이언트."""
    return CategoryList(test_config)


@pytest.fixture
def sample_list_response() -> str:
    """목록 조회 결과 샘플 (KOSIS 비표준 JSON)."""
    return """[
        {TBL_ID:"DT_1B040A3",TBL_NM:"행정구역별 인구수",ORG_ID:"101",ORG_NM:"통계청",STAT_ID:"1992001"},
        {TBL_ID:"DT_1B040B3",TBL_NM:"연령별 인구수",ORG_ID:"101",ORG_NM:"통계청",STAT_ID:"1992001"},
        {TBL_ID:"DT_1J20001",TBL_NM:"소비자물가지수",ORG_ID:"101",ORG_NM:"통계청",STAT_ID:"1992002"}
    ]"""


@pytest.fixture
def sample_stat_list_response() -> str:
    """통계 목록 조회 결과 샘플."""
    return """[
        {STAT_ID:"1992001",STAT_NM:"주민등록인구현황",ORG_ID:"101",ORG_NM:"통계청",TBL_CNT:"5"},
        {STAT_ID:"1992002",STAT_NM:"소비자물가조사",ORG_ID:"101",ORG_NM:"통계청",TBL_CNT:"12"}
    ]"""


class TestOrgCode:
    """OrgCode 상수 테스트."""

    def test_kostat_code(self):
        """통계청 코드."""
        assert OrgCode.KOSTAT == "101"

    def test_bok_code(self):
        """한국은행 코드."""
        assert OrgCode.BOK == "154"

    def test_moel_code(self):
        """고용노동부 코드."""
        assert OrgCode.MOEL == "118"


class TestThemeCode:
    """ThemeCode 상수 테스트."""

    def test_population_code(self):
        """인구 주제 코드."""
        assert ThemeCode.POPULATION == "A"

    def test_economy_code(self):
        """경제 주제 코드."""
        assert ThemeCode.ECONOMY == "H"

    def test_health_code(self):
        """보건 주제 코드."""
        assert ThemeCode.HEALTH == "J"


class TestCategoryListByOrg:
    """CategoryList.list_by_org 테스트."""

    def test_empty_org_id_returns_empty_list(self, category_client: CategoryList):
        """빈 기관 ID는 빈 리스트를 반환해야 함."""
        result = category_client.list_by_org("")
        assert result == []

    @responses.activate
    def test_list_by_org_success(
        self, category_client: CategoryList, sample_list_response: str
    ):
        """기관별 목록 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsList.do",
            body=sample_list_response,
            status=200,
        )

        result = category_client.list_by_org("101")

        assert len(result) == 3
        assert result[0]["ORG_ID"] == "101"
        # vwCd=MT_OTITLE (기관별)과 parentListId=101 확인
        assert "vwCd=MT_OTITLE" in responses.calls[0].request.url
        assert "parentListId=101" in responses.calls[0].request.url

    @responses.activate
    def test_list_by_org_with_parent_stat_id(
        self, category_client: CategoryList, sample_list_response: str
    ):
        """상위 통계 ID로 필터링."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsList.do",
            body=sample_list_response,
            status=200,
        )

        category_client.list_by_org("101", parent_stat_id="1992001")

        # parent_stat_id가 지정되면 parentListId가 해당 값으로 덮어씀
        assert "parentListId=1992001" in responses.calls[0].request.url

    @responses.activate
    def test_list_by_org_empty_result(self, category_client: CategoryList):
        """결과 없음."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsList.do",
            json={"errMsg": "데이터가 없습니다"},
            status=200,
        )

        result = category_client.list_by_org("999")

        assert result == []


class TestCategoryListByTheme:
    """CategoryList.list_by_theme 테스트."""

    def test_empty_theme_code_returns_empty_list(self, category_client: CategoryList):
        """빈 주제 코드는 빈 리스트를 반환해야 함."""
        result = category_client.list_by_theme("")
        assert result == []

    @responses.activate
    def test_list_by_theme_success(
        self, category_client: CategoryList, sample_list_response: str
    ):
        """주제별 목록 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsList.do",
            body=sample_list_response,
            status=200,
        )

        result = category_client.list_by_theme("A")

        assert len(result) == 3
        # vwCd=MT_ZTITLE (주제별)과 parentListId=A 확인
        assert "vwCd=MT_ZTITLE" in responses.calls[0].request.url
        assert "parentListId=A" in responses.calls[0].request.url

    @responses.activate
    def test_list_by_theme_with_constant(
        self, category_client: CategoryList, sample_list_response: str
    ):
        """ThemeCode 상수 사용."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsList.do",
            body=sample_list_response,
            status=200,
        )

        result = category_client.list_by_theme(ThemeCode.POPULATION)

        assert len(result) == 3


class TestCategoryListStatistics:
    """CategoryList.list_statistics 테스트."""

    def test_empty_org_id_returns_empty_list(self, category_client: CategoryList):
        """빈 기관 ID는 빈 리스트를 반환해야 함."""
        result = category_client.list_statistics("")
        assert result == []

    @responses.activate
    def test_list_statistics_success(
        self, category_client: CategoryList, sample_stat_list_response: str
    ):
        """기관 통계 목록 조회 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsList.do",
            body=sample_stat_list_response,
            status=200,
        )

        result = category_client.list_statistics("101")

        assert len(result) == 2
        assert result[0]["STAT_ID"] == "1992001"
        assert result[0]["STAT_NM"] == "주민등록인구현황"
        # getList 메서드와 MT_OTITLE 뷰 사용 확인
        assert "method=getList" in responses.calls[0].request.url
        assert "vwCd=MT_OTITLE" in responses.calls[0].request.url


class TestListByView:
    """CategoryList.list_by_view: 12개 vwCd 직접 호출."""

    @pytest.mark.parametrize(
        "view_code",
        [
            "MT_ZTITLE",
            "MT_OTITLE",
            "MT_GTITLE01",
            "MT_GTITLE02",
            "MT_CHOSUN_TITLE",
            "MT_HANKUK_TITLE",
            "MT_STOP_TITLE",
            "MT_RTITLE",
            "MT_BUKHAN",
            "MT_TM1_TITLE",
            "MT_TM2_TITLE",
            "MT_ETITLE",
        ],
    )
    @responses.activate
    def test_each_documented_view_code_passes_through(
        self, category_client: CategoryList, view_code: str
    ):
        """KOSIS 공식 12개 vwCd 모두 URL에 그대로 전달되는지 확인."""
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsList.do",
            body="[]",
            status=200,
        )

        category_client.list_by_view(view_code)

        url = responses.calls[0].request.url
        assert f"vwCd={view_code}" in url
        assert "method=getList" in url

    @responses.activate
    def test_list_by_view_with_parent_list_id(self, category_client: CategoryList):
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsList.do",
            body="[]",
            status=200,
        )

        category_client.list_by_view("MT_BUKHAN", parent_list_id="A")

        url = responses.calls[0].request.url
        assert "vwCd=MT_BUKHAN" in url
        assert "parentListId=A" in url

    @responses.activate
    def test_list_by_view_omits_parent_when_none(self, category_client: CategoryList):
        responses.add(
            responses.GET,
            "https://kosis.kr/openapi/statisticsList.do",
            body="[]",
            status=200,
        )

        category_client.list_by_view("MT_ETITLE")

        url = responses.calls[0].request.url
        assert "parentListId" not in url

    def test_list_by_view_empty_code_returns_empty(self, category_client: CategoryList):
        assert category_client.list_by_view("") == []
        assert category_client.list_by_view("   ") == []


def test_view_code_constants_match_official_12():
    from kosis_tools.list_categories import ViewCode

    assert len(ViewCode.ALL) == 12
    assert "MT_ZTITLE" in ViewCode.ALL
    assert "MT_BUKHAN" in ViewCode.ALL
    assert "MT_ETITLE" in ViewCode.ALL
    # named accessors map correctly
    assert ViewCode.NORTH_KOREA == "MT_BUKHAN"
    assert ViewCode.ENGLISH_KOSIS == "MT_ETITLE"
    assert ViewCode.PRE_LIBERATION == "MT_CHOSUN_TITLE"
