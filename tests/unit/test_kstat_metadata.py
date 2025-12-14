"""
kosis_tools.kstat_metadata 모듈 유닛 테스트.

테스트 범위:
    - KstatMetadata.get_kstat_url: k-stat URL 추출
    - KstatMetadata.get_stats_confm_no: 승인번호 추출
    - KstatMetadata.fetch_metadata: 메타데이터 조회
    - KstatMetadata.get_metadata_by_table: 통합 조회
    - KstatMetadata.has_kstat_link: 링크 존재 확인
"""

import pytest
import responses

from kosis_tools.config import KosisConfig
from kosis_tools.kstat_metadata import KstatMetadata


@pytest.fixture
def kstat_client(test_config: KosisConfig) -> KstatMetadata:
    """테스트용 k-stat 클라이언트."""
    return KstatMetadata(test_config)


@pytest.fixture
def sample_html_with_kstat() -> str:
    """k-stat URL이 포함된 HTML 샘플."""
    return """
    <html>
    <body>
        <div class="info">
            <a href="https://www.k-stat.go.kr/metasvc/msba100/statsdcdta?statsConfmNo=101001">
                통계설명자료
            </a>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_without_kstat() -> str:
    """k-stat URL이 없는 HTML 샘플."""
    return """
    <html>
    <body>
        <div class="info">
            <p>통계표 정보</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_kstat_html() -> str:
    """k-stat.go.kr 메타데이터 페이지 HTML 샘플."""
    return """
    <html>
    <body>
        <table>
            <tr><th>통계명</th><td>주민등록인구현황</td></tr>
            <tr><th>작성기관</th><td>행정안전부</td></tr>
            <tr><th>작성주기</th><td>월</td></tr>
            <tr><th>작성목적</th><td>주민등록 인구 현황 파악</td></tr>
            <tr><th>법적근거</th><td>주민등록법</td></tr>
            <tr><th>조사대상</th><td>전국 주민</td></tr>
            <tr><th>공표주기</th><td>월</td></tr>
            <tr><th>승인번호</th><td>101001</td></tr>
        </table>
    </body>
    </html>
    """


class TestKstatMetadataGetKstatUrl:
    """KstatMetadata.get_kstat_url 테스트."""

    def test_empty_org_id_returns_none(self, kstat_client: KstatMetadata):
        """빈 기관 ID는 None을 반환해야 함."""
        result = kstat_client.get_kstat_url("", "DT_1IN1503")
        assert result is None

    def test_empty_tbl_id_returns_none(self, kstat_client: KstatMetadata):
        """빈 테이블 ID는 None을 반환해야 함."""
        result = kstat_client.get_kstat_url("101", "")
        assert result is None

    @responses.activate
    def test_get_kstat_url_success(self, kstat_client: KstatMetadata, sample_html_with_kstat: str):
        """k-stat URL 추출 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/statHtml/statHtmlContent.do",
            body=sample_html_with_kstat,
            status=200,
        )

        result = kstat_client.get_kstat_url("101", "DT_1IN1503")

        assert result is not None
        assert "k-stat.go.kr" in result
        assert "statsConfmNo=101001" in result

    @responses.activate
    def test_get_kstat_url_not_found(self, kstat_client: KstatMetadata, sample_html_without_kstat: str):
        """k-stat URL이 없는 경우."""
        responses.add(
            responses.GET,
            "https://kosis.kr/statHtml/statHtmlContent.do",
            body=sample_html_without_kstat,
            status=200,
        )

        result = kstat_client.get_kstat_url("101", "DT_SOME_TABLE")

        assert result is None

    @responses.activate
    def test_get_kstat_url_http_error(self, kstat_client: KstatMetadata):
        """HTTP 에러 시 None 반환."""
        responses.add(
            responses.GET,
            "https://kosis.kr/statHtml/statHtmlContent.do",
            status=500,
        )

        result = kstat_client.get_kstat_url("101", "DT_1IN1503")

        assert result is None


class TestKstatMetadataGetStatsConfmNo:
    """KstatMetadata.get_stats_confm_no 테스트."""

    @responses.activate
    def test_get_stats_confm_no_success(self, kstat_client: KstatMetadata, sample_html_with_kstat: str):
        """승인번호 추출 성공."""
        responses.add(
            responses.GET,
            "https://kosis.kr/statHtml/statHtmlContent.do",
            body=sample_html_with_kstat,
            status=200,
        )

        result = kstat_client.get_stats_confm_no("101", "DT_1IN1503")

        assert result == "101001"

    @responses.activate
    def test_get_stats_confm_no_not_found(self, kstat_client: KstatMetadata, sample_html_without_kstat: str):
        """승인번호가 없는 경우."""
        responses.add(
            responses.GET,
            "https://kosis.kr/statHtml/statHtmlContent.do",
            body=sample_html_without_kstat,
            status=200,
        )

        result = kstat_client.get_stats_confm_no("101", "DT_SOME_TABLE")

        assert result is None


class TestKstatMetadataFetchMetadata:
    """KstatMetadata.fetch_metadata 테스트."""

    def test_empty_confm_no_returns_none(self, kstat_client: KstatMetadata):
        """빈 승인번호는 None을 반환해야 함."""
        result = kstat_client.fetch_metadata("")
        assert result is None

    @responses.activate
    def test_fetch_metadata_success(self, kstat_client: KstatMetadata, sample_kstat_html: str):
        """메타데이터 조회 성공."""
        responses.add(
            responses.GET,
            "https://www.k-stat.go.kr/metasvc/msba100/statsdcdta",
            body=sample_kstat_html,
            status=200,
        )

        result = kstat_client.fetch_metadata("101001")

        assert result is not None
        assert result["stats_confm_no"] == "101001"
        assert result["stats_name"] == "주민등록인구현황"
        assert result["org_name"] == "행정안전부"
        assert result["period"] == "월"
        assert result["purpose"] == "주민등록 인구 현황 파악"
        assert result["legal_basis"] == "주민등록법"

    @responses.activate
    def test_fetch_metadata_http_error(self, kstat_client: KstatMetadata):
        """HTTP 에러 시 None 반환."""
        responses.add(
            responses.GET,
            "https://www.k-stat.go.kr/metasvc/msba100/statsdcdta",
            status=500,
        )

        result = kstat_client.fetch_metadata("101001")

        assert result is None


class TestKstatMetadataGetMetadataByTable:
    """KstatMetadata.get_metadata_by_table 테스트."""

    @responses.activate
    def test_get_metadata_by_table_success(
        self,
        kstat_client: KstatMetadata,
        sample_html_with_kstat: str,
        sample_kstat_html: str,
    ):
        """테이블 ID로 메타데이터 조회 성공."""
        # statHtmlContent.do 응답
        responses.add(
            responses.GET,
            "https://kosis.kr/statHtml/statHtmlContent.do",
            body=sample_html_with_kstat,
            status=200,
        )
        # k-stat.go.kr 응답
        responses.add(
            responses.GET,
            "https://www.k-stat.go.kr/metasvc/msba100/statsdcdta",
            body=sample_kstat_html,
            status=200,
        )

        result = kstat_client.get_metadata_by_table("101", "DT_1IN1503")

        assert result is not None
        assert result["stats_name"] == "주민등록인구현황"
        assert result["org_id"] == "101"
        assert result["tbl_id"] == "DT_1IN1503"

    @responses.activate
    def test_get_metadata_by_table_no_kstat_link(
        self,
        kstat_client: KstatMetadata,
        sample_html_without_kstat: str,
    ):
        """k-stat 링크가 없는 테이블."""
        responses.add(
            responses.GET,
            "https://kosis.kr/statHtml/statHtmlContent.do",
            body=sample_html_without_kstat,
            status=200,
        )

        result = kstat_client.get_metadata_by_table("101", "DT_SOME_TABLE")

        assert result is None


class TestKstatMetadataHasKstatLink:
    """KstatMetadata.has_kstat_link 테스트."""

    @responses.activate
    def test_has_kstat_link_true(self, kstat_client: KstatMetadata, sample_html_with_kstat: str):
        """k-stat 링크가 있는 경우."""
        responses.add(
            responses.GET,
            "https://kosis.kr/statHtml/statHtmlContent.do",
            body=sample_html_with_kstat,
            status=200,
        )

        result = kstat_client.has_kstat_link("101", "DT_1IN1503")

        assert result is True

    @responses.activate
    def test_has_kstat_link_false(self, kstat_client: KstatMetadata, sample_html_without_kstat: str):
        """k-stat 링크가 없는 경우."""
        responses.add(
            responses.GET,
            "https://kosis.kr/statHtml/statHtmlContent.do",
            body=sample_html_without_kstat,
            status=200,
        )

        result = kstat_client.has_kstat_link("101", "DT_SOME_TABLE")

        assert result is False
