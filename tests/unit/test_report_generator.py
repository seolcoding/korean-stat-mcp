"""
kosis_tools.report_generator 모듈 유닛 테스트.

테스트 범위:
    - ReportGenerator: 동적 리포트 생성
    - UserQuery: 쿼리 파싱
    - 편의 함수: create_report, create_llm_prompt, generate_html_report
    - HTML 아티팩트 생성
"""

import pytest
from pathlib import Path
import tempfile

from kosis_tools.report_generator import (
    ReportGenerator,
    UserQuery,
    create_report,
    create_llm_prompt,
    generate_html_report,
)


@pytest.fixture
def sample_data() -> list[dict]:
    """테스트용 KOSIS 응답 데이터 샘플."""
    return [
        {"PRD_DE": "2020", "C1_NM": "전국", "DT": "50000000", "ITM_NM": "인구수"},
        {"PRD_DE": "2020", "C1_NM": "서울", "DT": "10000000", "ITM_NM": "인구수"},
        {"PRD_DE": "2020", "C1_NM": "부산", "DT": "3500000", "ITM_NM": "인구수"},
        {"PRD_DE": "2021", "C1_NM": "전국", "DT": "49500000", "ITM_NM": "인구수"},
        {"PRD_DE": "2021", "C1_NM": "서울", "DT": "9800000", "ITM_NM": "인구수"},
        {"PRD_DE": "2021", "C1_NM": "부산", "DT": "3400000", "ITM_NM": "인구수"},
        {"PRD_DE": "2022", "C1_NM": "전국", "DT": "49000000", "ITM_NM": "인구수"},
        {"PRD_DE": "2022", "C1_NM": "서울", "DT": "9600000", "ITM_NM": "인구수"},
        {"PRD_DE": "2022", "C1_NM": "부산", "DT": "3300000", "ITM_NM": "인구수"},
    ]


@pytest.fixture
def generator(sample_data: list[dict]) -> ReportGenerator:
    """테스트용 ReportGenerator 인스턴스."""
    return ReportGenerator(sample_data)


class TestUserQuery:
    """UserQuery 데이터클래스 테스트."""

    def test_default_values(self):
        """기본값 확인."""
        query = UserQuery(raw_query="테스트")
        assert query.raw_query == "테스트"
        assert query.target_regions == []
        assert query.target_periods == []
        assert query.comparison_type == "temporal"
        assert query.analysis_depth == "standard"
        assert query.include_visualization is True


class TestReportGeneratorParsing:
    """ReportGenerator 쿼리 파싱 테스트."""

    def test_parse_region(self, generator: ReportGenerator):
        """지역 파싱 테스트."""
        query = generator.parse_user_query("서울과 부산 인구 비교")
        assert "서울" in query.target_regions
        assert "부산" in query.target_regions
        assert query.comparison_type == "regional"

    def test_parse_period(self, generator: ReportGenerator):
        """기간 파싱 테스트."""
        query = generator.parse_user_query("2020-2021 인구 추이")
        assert "2020" in query.target_periods
        assert "2021" in query.target_periods
        assert query.comparison_type == "temporal"

    def test_parse_ranking(self, generator: ReportGenerator):
        """순위 파싱 테스트."""
        query = generator.parse_user_query("인구 상위 순위")
        assert query.comparison_type == "ranking"

    def test_parse_depth(self, generator: ReportGenerator):
        """분석 깊이 파싱 테스트."""
        query = generator.parse_user_query("자세히 분석해주세요")
        assert query.analysis_depth == "deep"


class TestReportGeneratorMarkdown:
    """ReportGenerator Markdown 리포트 테스트."""

    def test_generate_basic(self, generator: ReportGenerator):
        """기본 리포트 생성."""
        report = generator.generate(user_query="전체 데이터 분석")
        assert "# 📊 KOSIS 데이터 분석 리포트" in report
        assert "전체 데이터 분석" in report

    def test_generate_with_sections(self, generator: ReportGenerator):
        """섹션 지정 리포트 생성."""
        report = generator.generate(
            user_query="테스트",
            sections=["summary", "stats"]
        )
        assert "데이터 요약" in report
        assert "주요 통계" in report

    def test_generate_regional_comparison(self, generator: ReportGenerator):
        """지역별 비교 리포트."""
        report = generator.generate(user_query="서울과 부산 비교")
        assert "서울" in report or "부산" in report


class TestReportGeneratorHTML:
    """ReportGenerator HTML 아티팩트 테스트."""

    def test_generate_html_string(self, generator: ReportGenerator):
        """HTML 문자열 생성."""
        html = generator.generate_html(user_query="인구 추이 분석")
        assert "<!DOCTYPE html>" in html
        assert "<html lang=\"ko\">" in html
        assert "vegaEmbed" in html or "vega-lite" in html.lower()

    def test_generate_html_file(self, generator: ReportGenerator):
        """HTML 파일 저장."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_report.html"
            result = generator.generate_html(
                user_query="테스트",
                output_path=output_path
            )
            assert output_path.exists()
            assert result == str(output_path)
            content = output_path.read_text(encoding="utf-8")
            assert "<!DOCTYPE html>" in content

    def test_html_contains_vega_chart(self, generator: ReportGenerator):
        """Vega-Lite 차트 임베드 확인."""
        html = generator.generate_html(user_query="추이 분석")
        assert "vega-lite" in html.lower() or "cdn.jsdelivr.net/npm/vega" in html
        assert "vegaEmbed" in html

    def test_html_korean_fonts(self, generator: ReportGenerator):
        """한글 폰트 적용 확인."""
        html = generator.generate_html(user_query="테스트")
        assert "Noto Sans KR" in html
        assert "Malgun Gothic" in html

    def test_html_sections(self, generator: ReportGenerator):
        """HTML 섹션 포함 확인."""
        html = generator.generate_html(user_query="인구 추이")
        # 데이터 요약 카드
        assert "데이터 요약" in html
        # 통계 섹션
        assert "주요 통계" in html or "stat-value" in html

    def test_html_with_custom_title(self, generator: ReportGenerator):
        """커스텀 제목 테스트."""
        html = generator.generate_html(
            user_query="테스트",
            title="커스텀 제목 테스트"
        )
        assert "커스텀 제목 테스트" in html


class TestConvenienceFunctions:
    """편의 함수 테스트."""

    def test_create_report(self, sample_data: list[dict]):
        """create_report 함수."""
        report = create_report(sample_data, "전체 분석")
        assert "KOSIS 데이터 분석 리포트" in report

    def test_create_llm_prompt(self, sample_data: list[dict]):
        """create_llm_prompt 함수."""
        prompt = create_llm_prompt(sample_data, "서울 인구 분석")
        assert "KOSIS 통계 데이터를 분석" in prompt
        assert "서울 인구 분석" in prompt
        assert "샘플 데이터" in prompt

    def test_generate_html_report(self, sample_data: list[dict]):
        """generate_html_report 함수."""
        html = generate_html_report(sample_data, "테스트 쿼리")
        assert "<!DOCTYPE html>" in html
        assert "vegaEmbed" in html or "vega-lite" in html.lower()

    def test_generate_html_report_to_file(self, sample_data: list[dict]):
        """generate_html_report 파일 저장."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.html"
            result = generate_html_report(
                sample_data,
                "테스트",
                output_path=str(output_path)
            )
            assert Path(result).exists()


class TestLLMContext:
    """LLM 컨텍스트 생성 테스트."""

    def test_create_llm_context(self, generator: ReportGenerator):
        """LLM 컨텍스트 생성."""
        context = generator.create_llm_context("서울 인구 분석")
        assert "user_query" in context
        assert "parsed_query" in context
        assert "data_info" in context
        assert "available_dimensions" in context
        assert "suggested_analysis" in context

    def test_llm_context_dimensions(self, generator: ReportGenerator):
        """LLM 컨텍스트 차원 정보."""
        context = generator.create_llm_context("테스트")
        assert "periods" in context["available_dimensions"]
        assert "regions" in context["available_dimensions"]
        assert "2020" in context["available_dimensions"]["periods"]
        assert "서울" in context["available_dimensions"]["regions"]

    def test_llm_context_sample_data(self, generator: ReportGenerator):
        """LLM 컨텍스트 샘플 데이터."""
        context = generator.create_llm_context("테스트", include_data_sample=True)
        assert "sample_data" in context
        assert len(context["sample_data"]) > 0
