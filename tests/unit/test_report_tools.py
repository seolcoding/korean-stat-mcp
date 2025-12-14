"""
kosis_tools.report_tools 모듈 유닛 테스트.

테스트 범위:
    - Layer 1: DISCOVER 도구 (search_tables, browse_categories, get_table_meta, get_available_values)
    - Layer 2: FETCH 도구 (filter_data, aggregate_data)
    - Layer 3: PRESENT 도구 (viz_*, analyze_*, text_*, layout_*, assemble_report)
"""

import pytest
from pathlib import Path
import tempfile

from kosis_tools.report_tools import (
    # 데이터 클래스
    ReportComponent,
    AnalysisResult,
    # Layer 1: DISCOVER
    get_available_values,
    # Layer 2: FETCH
    filter_data,
    aggregate_data,
    # Layer 3: PRESENT - Visualization
    viz_line_trend,
    viz_bar_comparison,
    viz_kpi_card,
    viz_pie_composition,
    viz_heatmap,
    # Layer 3: PRESENT - Analysis
    analyze_trend,
    analyze_comparison,
    analyze_ranking,
    analyze_stats,
    # Layer 3: PRESENT - Text
    text_headline,
    text_summary,
    text_insight,
    text_data_note,
    # Layer 3: PRESENT - Layout
    layout_section,
    layout_card_grid,
    layout_two_column,
    layout_highlight_box,
    layout_table,
    # Layer 3: PRESENT - Assembly
    assemble_report,
    quick_report,
)


# =============================================================================
# 테스트 데이터 Fixtures
# =============================================================================

@pytest.fixture
def sample_population_data() -> list[dict]:
    """인구 데이터 샘플 (지역별, 연도별)."""
    return [
        {"PRD_DE": "2020", "C1_NM": "서울특별시", "DT": "9668465", "ITM_NM": "인구수"},
        {"PRD_DE": "2020", "C1_NM": "부산광역시", "DT": "3391946", "ITM_NM": "인구수"},
        {"PRD_DE": "2020", "C1_NM": "대구광역시", "DT": "2418346", "ITM_NM": "인구수"},
        {"PRD_DE": "2020", "C1_NM": "인천광역시", "DT": "2942828", "ITM_NM": "인구수"},
        {"PRD_DE": "2021", "C1_NM": "서울특별시", "DT": "9509458", "ITM_NM": "인구수"},
        {"PRD_DE": "2021", "C1_NM": "부산광역시", "DT": "3350380", "ITM_NM": "인구수"},
        {"PRD_DE": "2021", "C1_NM": "대구광역시", "DT": "2385412", "ITM_NM": "인구수"},
        {"PRD_DE": "2021", "C1_NM": "인천광역시", "DT": "2948375", "ITM_NM": "인구수"},
        {"PRD_DE": "2022", "C1_NM": "서울특별시", "DT": "9411211", "ITM_NM": "인구수"},
        {"PRD_DE": "2022", "C1_NM": "부산광역시", "DT": "3314183", "ITM_NM": "인구수"},
        {"PRD_DE": "2022", "C1_NM": "대구광역시", "DT": "2357570", "ITM_NM": "인구수"},
        {"PRD_DE": "2022", "C1_NM": "인천광역시", "DT": "2967314", "ITM_NM": "인구수"},
        {"PRD_DE": "2023", "C1_NM": "서울특별시", "DT": "9329812", "ITM_NM": "인구수"},
        {"PRD_DE": "2023", "C1_NM": "부산광역시", "DT": "3271987", "ITM_NM": "인구수"},
        {"PRD_DE": "2023", "C1_NM": "대구광역시", "DT": "2321478", "ITM_NM": "인구수"},
        {"PRD_DE": "2023", "C1_NM": "인천광역시", "DT": "2985137", "ITM_NM": "인구수"},
    ]


@pytest.fixture
def sample_simple_data() -> list[dict]:
    """단순 데이터 샘플."""
    return [
        {"PRD_DE": "2022", "C1_NM": "항목A", "DT": "100", "ITM_NM": "수치"},
        {"PRD_DE": "2022", "C1_NM": "항목B", "DT": "200", "ITM_NM": "수치"},
        {"PRD_DE": "2023", "C1_NM": "항목A", "DT": "150", "ITM_NM": "수치"},
        {"PRD_DE": "2023", "C1_NM": "항목B", "DT": "250", "ITM_NM": "수치"},
    ]


# =============================================================================
# 데이터 클래스 테스트
# =============================================================================

class TestReportComponent:
    """ReportComponent 데이터클래스 테스트."""

    def test_create_basic(self):
        """기본 생성."""
        comp = ReportComponent(
            type="chart",
            html="<div>Test</div>",
        )
        assert comp.type == "chart"
        assert comp.html == "<div>Test</div>"
        assert comp.priority == 50  # 기본값

    def test_create_with_all_fields(self):
        """모든 필드로 생성."""
        comp = ReportComponent(
            type="text",
            html="<p>Hello</p>",
            data={"key": "value"},
            summary="Test summary",
            metadata={"source": "test"},
            priority=10,
            tags=["text", "headline"],
        )
        assert comp.type == "text"
        assert comp.summary == "Test summary"
        assert comp.priority == 10
        assert "headline" in comp.tags


class TestAnalysisResult:
    """AnalysisResult 데이터클래스 테스트."""

    def test_create_basic(self):
        """기본 생성."""
        result = AnalysisResult(
            type="trend",
            findings=["증가 추세"],
        )
        assert result.type == "trend"
        assert len(result.findings) == 1

    def test_create_with_metrics(self):
        """메트릭 포함 생성."""
        result = AnalysisResult(
            type="comparison",
            findings=["A가 B보다 큼"],
            metrics={"gap": 100, "ratio": 2.5},
            interpretation="A가 2.5배",
        )
        assert result.metrics["ratio"] == 2.5
        assert "2.5배" in result.interpretation


# =============================================================================
# Layer 1: DISCOVER 도구 테스트
# =============================================================================

class TestGetAvailableValues:
    """get_available_values 테스트."""

    def test_get_periods(self, sample_population_data):
        """기간 값 조회."""
        periods = get_available_values(sample_population_data, "PRD_DE")
        assert len(periods) == 4
        assert "2020" in periods
        assert "2023" in periods

    def test_get_regions(self, sample_population_data):
        """지역 값 조회."""
        regions = get_available_values(sample_population_data, "C1_NM")
        assert len(regions) == 4
        assert "서울특별시" in regions
        assert "부산광역시" in regions

    def test_empty_data(self):
        """빈 데이터 처리."""
        values = get_available_values([], "C1_NM")
        assert values == []

    def test_nonexistent_field(self, sample_population_data):
        """존재하지 않는 필드."""
        values = get_available_values(sample_population_data, "NONEXISTENT")
        assert values == []


# =============================================================================
# Layer 2: FETCH 도구 테스트
# =============================================================================

class TestFilterData:
    """filter_data 테스트."""

    def test_filter_by_regions(self, sample_population_data):
        """지역 필터링."""
        filtered = filter_data(
            sample_population_data,
            regions=["서울특별시", "부산광역시"]
        )
        assert len(filtered) == 8  # 4년 * 2지역
        regions = {r["C1_NM"] for r in filtered}
        assert regions == {"서울특별시", "부산광역시"}

    def test_filter_by_periods(self, sample_population_data):
        """기간 필터링."""
        filtered = filter_data(
            sample_population_data,
            periods=["2022", "2023"]
        )
        assert len(filtered) == 8  # 2년 * 4지역
        periods = {r["PRD_DE"] for r in filtered}
        assert periods == {"2022", "2023"}

    def test_filter_combined(self, sample_population_data):
        """복합 필터링."""
        filtered = filter_data(
            sample_population_data,
            regions=["서울특별시"],
            periods=["2023"]
        )
        assert len(filtered) == 1
        assert filtered[0]["C1_NM"] == "서울특별시"
        assert filtered[0]["PRD_DE"] == "2023"

    def test_filter_custom(self, sample_population_data):
        """커스텀 필터."""
        filtered = filter_data(
            sample_population_data,
            custom_filter=lambda r: int(r["DT"]) > 5000000
        )
        # 서울만 5백만 이상
        assert all(r["C1_NM"] == "서울특별시" for r in filtered)


class TestAggregateData:
    """aggregate_data 테스트."""

    def test_aggregate_by_region(self, sample_population_data):
        """지역별 집계."""
        agg = aggregate_data(
            sample_population_data,
            group_by="C1_NM",
            agg_func="sum"
        )
        assert len(agg) == 4  # 4개 지역

    def test_aggregate_by_period(self, sample_population_data):
        """연도별 집계."""
        agg = aggregate_data(
            sample_population_data,
            group_by="PRD_DE",
            agg_func="sum"
        )
        assert len(agg) == 4  # 4개 연도

    def test_aggregate_mean(self, sample_simple_data):
        """평균 집계."""
        agg = aggregate_data(
            sample_simple_data,
            group_by="C1_NM",
            agg_func="mean"
        )
        # 항목A: (100+150)/2 = 125, 항목B: (200+250)/2 = 225
        assert len(agg) == 2


# =============================================================================
# Layer 3: PRESENT - 시각화 도구 테스트
# =============================================================================

class TestVizLineTrend:
    """viz_line_trend 테스트."""

    def test_basic_chart(self, sample_population_data):
        """기본 라인 차트 생성."""
        comp = viz_line_trend(sample_population_data, title="인구 추이")
        assert comp.type == "chart"
        assert "chart-container" in comp.html
        assert "인구 추이" in comp.metadata.get("title", "")

    def test_returns_report_component(self, sample_population_data):
        """ReportComponent 반환 확인."""
        comp = viz_line_trend(sample_population_data)
        assert isinstance(comp, ReportComponent)
        assert comp.tags == ["visualization", "line", "trend"]

    def test_summary_generated(self, sample_population_data):
        """요약 생성 확인."""
        comp = viz_line_trend(sample_population_data)
        assert "추이" in comp.summary or "라인" in comp.summary


class TestVizBarComparison:
    """viz_bar_comparison 테스트."""

    def test_basic_chart(self, sample_population_data):
        """기본 막대 차트."""
        # 2023년 데이터만
        filtered = filter_data(sample_population_data, periods=["2023"])
        comp = viz_bar_comparison(filtered, title="지역별 인구")
        assert comp.type == "chart"
        assert "chart-container" in comp.html

    def test_top_n(self, sample_population_data):
        """Top N 처리."""
        filtered = filter_data(sample_population_data, periods=["2023"])
        comp = viz_bar_comparison(filtered, top_n=2)
        assert "상위 2개" in comp.summary

    def test_sorted(self, sample_population_data):
        """정렬 확인."""
        filtered = filter_data(sample_population_data, periods=["2023"])
        comp = viz_bar_comparison(filtered, sort=True)
        assert comp.metadata.get("sorted") is True


class TestVizKpiCard:
    """viz_kpi_card 테스트."""

    def test_basic_card(self):
        """기본 KPI 카드."""
        comp = viz_kpi_card(value=1000000, label="총 인구")
        assert comp.type == "card"
        assert "1,000,000" in comp.html
        assert "총 인구" in comp.html

    def test_with_change(self):
        """변동률 포함."""
        comp = viz_kpi_card(
            value=5000,
            label="매출",
            change=-5.5,
            change_label="전월 대비"
        )
        assert "-5.5%" in comp.html
        assert "전월 대비" in comp.html

    def test_with_icon(self):
        """아이콘 포함."""
        comp = viz_kpi_card(value=100, label="테스트", icon="📊")
        assert "📊" in comp.html

    def test_priority(self):
        """우선순위 확인 (KPI는 높은 우선순위)."""
        comp = viz_kpi_card(value=100, label="테스트")
        assert comp.priority == 10


class TestVizPieComposition:
    """viz_pie_composition 테스트."""

    def test_basic_pie(self, sample_population_data):
        """기본 파이 차트."""
        filtered = filter_data(sample_population_data, periods=["2023"])
        comp = viz_pie_composition(filtered, title="지역별 구성비")
        assert comp.type == "chart"
        assert "chart-container" in comp.html

    def test_top_n_with_others(self, sample_population_data):
        """Top N + 기타 처리."""
        filtered = filter_data(sample_population_data, periods=["2023"])
        comp = viz_pie_composition(filtered, top_n=2)
        # top_n=2이면 나머지는 "기타"로
        assert "상위 2개" in comp.summary


class TestVizHeatmap:
    """viz_heatmap 테스트."""

    def test_basic_heatmap(self, sample_population_data):
        """기본 히트맵."""
        comp = viz_heatmap(sample_population_data, title="지역-연도 히트맵")
        assert comp.type == "chart"
        assert "heatmap" in comp.metadata.get("chart_type", "")


# =============================================================================
# Layer 3: PRESENT - 분석 도구 테스트
# =============================================================================

class TestAnalyzeTrend:
    """analyze_trend 테스트."""

    def test_overall_trend(self, sample_population_data):
        """전체 추세 분석."""
        # 서울 데이터만 (감소 추세)
        filtered = filter_data(sample_population_data, regions=["서울특별시"])
        result = analyze_trend(filtered)
        assert result.type == "trend"
        assert len(result.findings) > 0
        # 서울은 감소 추세
        assert "감소" in result.metrics.get("direction", "") or result.metrics.get("total_change_pct", 0) < 0

    def test_group_trend(self, sample_population_data):
        """그룹별 추세 분석."""
        result = analyze_trend(sample_population_data, group_by="C1_NM")
        assert result.type == "trend"
        assert "groups" in result.metrics


class TestAnalyzeComparison:
    """analyze_comparison 테스트."""

    def test_basic_comparison(self, sample_population_data):
        """기본 비교 분석."""
        result = analyze_comparison(
            sample_population_data,
            targets=["서울특별시", "부산광역시"],
            period="2023"
        )
        assert result.type == "comparison"
        assert "max" in result.metrics
        assert "min" in result.metrics
        # 서울이 최대
        assert result.metrics["max"]["name"] == "서울특별시"

    def test_ranking_included(self, sample_population_data):
        """순위 포함 확인."""
        result = analyze_comparison(sample_population_data, period="2023")
        assert "rankings" in result.metrics
        assert len(result.metrics["rankings"]) == 4


class TestAnalyzeRanking:
    """analyze_ranking 테스트."""

    def test_basic_ranking(self, sample_population_data):
        """기본 순위 분석."""
        result = analyze_ranking(sample_population_data, top_n=5)
        assert result.type == "ranking"
        assert len(result.findings) > 0
        # 1위는 서울
        assert "서울" in result.findings[0]

    def test_top_n_limit(self, sample_population_data):
        """Top N 제한 확인."""
        result = analyze_ranking(sample_population_data, top_n=2)
        assert result.metrics["top_n"] == 2


class TestAnalyzeStats:
    """analyze_stats 테스트."""

    def test_basic_stats(self, sample_population_data):
        """기본 통계 분석."""
        result = analyze_stats(sample_population_data)
        assert result.type == "stats"
        assert "mean" in result.metrics
        assert "std" in result.metrics
        assert "min" in result.metrics
        assert "max" in result.metrics

    def test_findings_format(self, sample_population_data):
        """발견사항 포맷."""
        result = analyze_stats(sample_population_data)
        assert any("평균" in f for f in result.findings)


# =============================================================================
# Layer 3: PRESENT - 텍스트 생성 도구 테스트
# =============================================================================

class TestTextHeadline:
    """text_headline 테스트."""

    def test_from_trend_analysis(self, sample_population_data):
        """추세 분석 결과로 헤드라인."""
        filtered = filter_data(sample_population_data, regions=["서울특별시"])
        analysis = analyze_trend(filtered)
        comp = text_headline(analysis, style="news")
        assert comp.type == "text"
        assert "<h2" in comp.html

    def test_styles(self, sample_population_data):
        """스타일별 생성."""
        analysis = analyze_trend(sample_population_data)
        for style in ["news", "formal", "casual"]:
            comp = text_headline(analysis, style=style)
            assert comp.metadata["style"] == style


class TestTextSummary:
    """text_summary 테스트."""

    def test_basic_summary(self, sample_population_data):
        """기본 요약."""
        comp = text_summary(sample_population_data)
        assert comp.type == "text"
        assert "<p" in comp.html
        # 기간 정보 포함
        assert "2020" in comp.html or "2023" in comp.html

    def test_with_analysis(self, sample_population_data):
        """분석 결과 포함 요약."""
        analysis = analyze_trend(sample_population_data)
        comp = text_summary(sample_population_data, analysis=analysis)
        assert len(comp.data["sentences"]) > 0


class TestTextInsight:
    """text_insight 테스트."""

    def test_basic_insight(self, sample_population_data):
        """기본 인사이트."""
        filtered = filter_data(sample_population_data, regions=["서울특별시"])
        analysis = analyze_trend(filtered)
        comp = text_insight(analysis)
        assert comp.type == "text"
        assert "인사이트" in comp.html

    def test_depth_levels(self, sample_population_data):
        """깊이 레벨."""
        analysis = analyze_trend(sample_population_data)
        for depth in ["quick", "standard", "deep"]:
            comp = text_insight(analysis, depth=depth)
            assert comp.metadata["depth"] == depth


class TestTextDataNote:
    """text_data_note 테스트."""

    def test_basic_note(self, sample_population_data):
        """기본 데이터 주석."""
        comp = text_data_note(sample_population_data)
        assert comp.type == "text"
        assert "출처" in comp.html
        assert "KOSIS" in comp.html

    def test_with_caveats(self, sample_population_data):
        """주의사항 포함."""
        comp = text_data_note(
            sample_population_data,
            caveats=["속보 데이터로 향후 수정될 수 있음"]
        )
        assert "속보" in comp.html


# =============================================================================
# Layer 3: PRESENT - 레이아웃 도구 테스트
# =============================================================================

class TestLayoutSection:
    """layout_section 테스트."""

    def test_basic_section(self, sample_population_data):
        """기본 섹션."""
        chart = viz_line_trend(sample_population_data)
        summary = text_summary(sample_population_data)
        section = layout_section("분석 결과", [chart, summary], icon="📊")
        assert section.type == "section"
        assert "분석 결과" in section.html
        assert "📊" in section.html

    def test_priority_sorting(self, sample_population_data):
        """우선순위 정렬."""
        # KPI (priority=10)가 차트(priority=30)보다 먼저
        kpi = viz_kpi_card(100, "테스트")
        chart = viz_line_trend(sample_population_data)
        section = layout_section("테스트", [chart, kpi])
        # KPI가 먼저 나오는지 확인 (HTML 순서)
        kpi_pos = section.html.find("kpi-card")
        chart_pos = section.html.find("chart-container")
        assert kpi_pos < chart_pos


class TestLayoutCardGrid:
    """layout_card_grid 테스트."""

    def test_three_column_grid(self):
        """3열 그리드."""
        cards = [
            viz_kpi_card(100, "A"),
            viz_kpi_card(200, "B"),
            viz_kpi_card(300, "C"),
        ]
        grid = layout_card_grid(cards, columns=3)
        assert grid.type == "layout"
        assert "grid-template-columns: repeat(3, 1fr)" in grid.html

    def test_summary(self):
        """요약 확인."""
        cards = [viz_kpi_card(i, f"Card {i}") for i in range(4)]
        grid = layout_card_grid(cards)
        assert "4개 KPI 카드" in grid.summary


class TestLayoutTwoColumn:
    """layout_two_column 테스트."""

    def test_basic_two_column(self, sample_population_data):
        """기본 2단 레이아웃."""
        chart = viz_line_trend(sample_population_data)
        text = text_summary(sample_population_data)
        layout = layout_two_column(chart, text)
        assert layout.type == "layout"
        assert "grid" in layout.html

    def test_ratio(self, sample_population_data):
        """비율 설정."""
        chart = viz_line_trend(sample_population_data)
        text = text_summary(sample_population_data)
        layout = layout_two_column(chart, text, ratio="2:1")
        assert "2fr" in layout.html
        assert "1fr" in layout.html


class TestLayoutHighlightBox:
    """layout_highlight_box 테스트."""

    def test_info_style(self):
        """정보 스타일."""
        box = layout_highlight_box("중요한 내용입니다.", style="info")
        assert box.type == "layout"
        assert "#2196F3" in box.html  # 파란색 테두리

    def test_warning_style(self):
        """경고 스타일."""
        box = layout_highlight_box("주의하세요!", style="warning")
        assert "#FFC107" in box.html  # 노란색 테두리

    def test_with_title(self):
        """제목 포함."""
        box = layout_highlight_box("내용", style="success", title="성공!")
        assert "성공!" in box.html


class TestLayoutTable:
    """layout_table 테스트."""

    def test_basic_table(self, sample_population_data):
        """기본 테이블."""
        table = layout_table(sample_population_data)
        assert table.type == "table"
        assert "<table" in table.html

    def test_column_selection(self, sample_population_data):
        """열 선택."""
        table = layout_table(
            sample_population_data,
            columns=["PRD_DE", "C1_NM", "DT"]
        )
        assert "PRD_DE" in table.metadata.get("columns", [])

    def test_column_labels(self, sample_population_data):
        """열 라벨 변환."""
        table = layout_table(
            sample_population_data,
            columns=["PRD_DE", "C1_NM", "DT"],
            column_labels={"PRD_DE": "연도", "C1_NM": "지역", "DT": "인구"}
        )
        assert "연도" in table.html or "지역" in table.html

    def test_max_rows(self, sample_population_data):
        """최대 행 수 제한."""
        table = layout_table(sample_population_data, max_rows=5)
        assert len(table.data) == 5

    def test_empty_data(self):
        """빈 데이터."""
        table = layout_table([])
        assert "데이터가 없습니다" in table.html


# =============================================================================
# Layer 3: PRESENT - 리포트 조립 테스트
# =============================================================================

class TestAssembleReport:
    """assemble_report 테스트."""

    def test_basic_assembly(self, sample_population_data):
        """기본 조립."""
        chart = viz_line_trend(sample_population_data)
        note = text_data_note(sample_population_data)

        html = assemble_report(
            [chart, note],
            title="테스트 리포트"
        )

        assert "<!DOCTYPE html>" in html
        assert "테스트 리포트" in html
        assert "chart-container" in html

    def test_priority_ordering(self, sample_population_data):
        """우선순위 정렬."""
        # note (priority=90)이 chart (priority=30)보다 뒤에
        chart = viz_line_trend(sample_population_data)
        note = text_data_note(sample_population_data)

        html = assemble_report([note, chart], title="테스트")

        chart_pos = html.find("chart-container")
        note_pos = html.find("출처")
        assert chart_pos < note_pos

    def test_with_subtitle(self, sample_population_data):
        """부제목 포함."""
        chart = viz_line_trend(sample_population_data)

        html = assemble_report(
            [chart],
            title="메인 제목",
            subtitle="부제목 테스트"
        )

        assert "부제목 테스트" in html

    def test_plotly_cdn_included(self, sample_population_data):
        """Plotly CDN 포함."""
        chart = viz_line_trend(sample_population_data)
        html = assemble_report([chart], title="테스트")
        assert "cdn.plot.ly/plotly" in html

    def test_korean_fonts(self, sample_population_data):
        """한글 폰트 포함."""
        chart = viz_line_trend(sample_population_data)
        html = assemble_report([chart], title="테스트")
        assert "Noto Sans KR" in html

    def test_save_to_file(self, sample_population_data):
        """파일 저장."""
        chart = viz_line_trend(sample_population_data)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_report.html"
            result = assemble_report(
                [chart],
                title="테스트",
                output_path=str(output_path)
            )

            assert output_path.exists()
            assert result == str(output_path)

            content = output_path.read_text(encoding="utf-8")
            assert "<!DOCTYPE html>" in content

    def test_templates(self, sample_population_data):
        """템플릿 스타일."""
        chart = viz_line_trend(sample_population_data)

        for template in ["standard", "dashboard", "article", "minimal"]:
            html = assemble_report([chart], title="테스트", template=template)
            assert "<!DOCTYPE html>" in html


class TestQuickReport:
    """quick_report 테스트."""

    def test_basic_quick_report(self, sample_population_data):
        """기본 빠른 리포트."""
        html = quick_report(sample_population_data, title="빠른 분석")

        assert "<!DOCTYPE html>" in html
        assert "빠른 분석" in html
        # KPI 카드, 차트 등 포함
        assert "kpi-card" in html
        assert "chart-container" in html

    def test_save_quick_report(self, sample_population_data):
        """빠른 리포트 저장."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "quick_report.html"
            result = quick_report(
                sample_population_data,
                title="저장 테스트",
                output_path=str(output_path)
            )

            assert output_path.exists()


# =============================================================================
# 통합 테스트
# =============================================================================

class TestFullWorkflow:
    """전체 워크플로우 통합 테스트."""

    def test_complete_report_workflow(self, sample_population_data):
        """완전한 리포트 생성 워크플로우."""
        # 1. 데이터 필터링
        filtered = filter_data(
            sample_population_data,
            regions=["서울특별시", "부산광역시"]
        )

        # 2. 분석
        trend = analyze_trend(filtered, group_by="C1_NM")
        comparison = analyze_comparison(filtered, period="2023")

        # 3. 시각화
        line_chart = viz_line_trend(filtered, title="인구 추이")
        bar_chart = viz_bar_comparison(
            filter_data(filtered, periods=["2023"]),
            title="2023년 인구 비교"
        )

        # 4. 텍스트
        headline = text_headline(trend, style="news")
        insight = text_insight(comparison)
        note = text_data_note(filtered)

        # 5. KPI
        seoul_2023 = filter_data(filtered, regions=["서울특별시"], periods=["2023"])[0]
        kpi = viz_kpi_card(
            value=int(seoul_2023["DT"]),
            label="서울 인구 (2023)",
            icon="👥"
        )

        # 6. 레이아웃
        section1 = layout_section("핵심 지표", [kpi], icon="📊")
        section2 = layout_section("추이 분석", [headline, line_chart], icon="📈")
        section3 = layout_section("비교 분석", [bar_chart, insight], icon="📊")

        # 7. 조립
        html = assemble_report(
            [section1, section2, section3, note],
            title="서울-부산 인구 분석",
            subtitle="2020-2023년 데이터 기준",
        )

        # 검증
        assert "<!DOCTYPE html>" in html
        assert "서울-부산 인구 분석" in html
        assert "chart-container" in html
        assert "인사이트" in html
        assert "출처" in html
