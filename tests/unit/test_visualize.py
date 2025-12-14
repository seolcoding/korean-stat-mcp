"""
kosis_tools.visualize 모듈 유닛 테스트.

테스트 범위:
    - KosisVisualizer: 차트 생성 (라인, 막대, 파이, 히트맵)
    - 한글 레이아웃 적용
    - 편의 함수: quick_line, quick_bar, quick_pie
"""

import pytest
import plotly.graph_objects as go

from kosis_tools.visualize import (
    KosisVisualizer,
    quick_line,
    quick_bar,
    quick_pie,
    FONT_FAMILY,
)


@pytest.fixture
def sample_data() -> list[dict]:
    """테스트용 KOSIS 응답 데이터 샘플."""
    return [
        {"PRD_DE": "2020", "C1_NM": "전국", "DT": "50000000"},
        {"PRD_DE": "2020", "C1_NM": "서울", "DT": "10000000"},
        {"PRD_DE": "2020", "C1_NM": "부산", "DT": "3500000"},
        {"PRD_DE": "2021", "C1_NM": "전국", "DT": "49500000"},
        {"PRD_DE": "2021", "C1_NM": "서울", "DT": "9800000"},
        {"PRD_DE": "2021", "C1_NM": "부산", "DT": "3400000"},
        {"PRD_DE": "2022", "C1_NM": "전국", "DT": "49000000"},
        {"PRD_DE": "2022", "C1_NM": "서울", "DT": "9600000"},
        {"PRD_DE": "2022", "C1_NM": "부산", "DT": "3300000"},
    ]


@pytest.fixture
def visualizer() -> KosisVisualizer:
    """테스트용 KosisVisualizer 인스턴스."""
    return KosisVisualizer()


class TestKosisVisualizerInit:
    """KosisVisualizer 초기화 테스트."""

    def test_default_init(self):
        """기본 초기화."""
        viz = KosisVisualizer()
        assert viz.font_family == FONT_FAMILY
        assert viz.template == "plotly_white"
        assert viz.default_height == 500
        assert viz.default_width == 900

    def test_custom_init(self):
        """커스텀 초기화."""
        viz = KosisVisualizer(
            font_family="Arial",
            template="plotly_dark",
            default_height=600,
            default_width=1000,
        )
        assert viz.font_family == "Arial"
        assert viz.template == "plotly_dark"


class TestKosisVisualizerLineChart:
    """KosisVisualizer 라인 차트 테스트."""

    def test_line_chart_basic(self, visualizer: KosisVisualizer, sample_data: list[dict]):
        """기본 라인 차트."""
        fig = visualizer.line_chart(sample_data, x="PRD_DE", y="DT")
        assert isinstance(fig, go.Figure)

    def test_line_chart_with_color(self, visualizer: KosisVisualizer, sample_data: list[dict]):
        """색상 구분 라인 차트."""
        fig = visualizer.line_chart(sample_data, x="PRD_DE", y="DT", color="C1_NM")
        assert isinstance(fig, go.Figure)

    def test_line_chart_with_title(self, visualizer: KosisVisualizer, sample_data: list[dict]):
        """제목 포함 라인 차트."""
        fig = visualizer.line_chart(
            sample_data,
            x="PRD_DE",
            y="DT",
            title="인구 추이",
            xaxis_title="연도",
            yaxis_title="인구수",
        )
        assert fig.layout.title.text == "인구 추이"


class TestKosisVisualizerBarChart:
    """KosisVisualizer 막대 차트 테스트."""

    def test_bar_chart_basic(self, visualizer: KosisVisualizer, sample_data: list[dict]):
        """기본 막대 차트."""
        fig = visualizer.bar_chart(sample_data, x="C1_NM", y="DT")
        assert isinstance(fig, go.Figure)

    def test_bar_chart_grouped(self, visualizer: KosisVisualizer, sample_data: list[dict]):
        """그룹 막대 차트."""
        fig = visualizer.bar_chart(
            sample_data,
            x="C1_NM",
            y="DT",
            color="PRD_DE",
            barmode="group",
        )
        assert isinstance(fig, go.Figure)


class TestKosisVisualizerPieChart:
    """KosisVisualizer 파이 차트 테스트."""

    def test_pie_chart_basic(self, visualizer: KosisVisualizer, sample_data: list[dict]):
        """기본 파이 차트."""
        # 2020년 데이터만
        data_2020 = [d for d in sample_data if d["PRD_DE"] == "2020"]
        fig = visualizer.pie_chart(data_2020, values="DT", names="C1_NM")
        assert isinstance(fig, go.Figure)

    def test_donut_chart(self, visualizer: KosisVisualizer, sample_data: list[dict]):
        """도넛 차트."""
        data_2020 = [d for d in sample_data if d["PRD_DE"] == "2020"]
        fig = visualizer.pie_chart(data_2020, values="DT", names="C1_NM", hole=0.4)
        assert isinstance(fig, go.Figure)


class TestKosisVisualizerHeatmap:
    """KosisVisualizer 히트맵 테스트."""

    def test_heatmap_basic(self, visualizer: KosisVisualizer, sample_data: list[dict]):
        """기본 히트맵."""
        fig = visualizer.heatmap(sample_data, x="PRD_DE", y="C1_NM", z="DT")
        assert isinstance(fig, go.Figure)


class TestKosisVisualizerScatterChart:
    """KosisVisualizer 산점도 테스트."""

    def test_scatter_basic(self, visualizer: KosisVisualizer, sample_data: list[dict]):
        """기본 산점도."""
        fig = visualizer.scatter_chart(sample_data, x="PRD_DE", y="DT")
        assert isinstance(fig, go.Figure)


class TestKosisVisualizerMultiLineChart:
    """KosisVisualizer 패싯 차트 테스트."""

    def test_multi_line_chart(self, visualizer: KosisVisualizer, sample_data: list[dict]):
        """패싯 라인 차트."""
        fig = visualizer.multi_line_chart(
            sample_data,
            x="PRD_DE",
            y="DT",
            facet_col="C1_NM",
        )
        assert isinstance(fig, go.Figure)


class TestKosisVisualizerNumericConversion:
    """숫자 변환 테스트."""

    def test_convert_numeric(self, visualizer: KosisVisualizer):
        """문자열 숫자 변환."""
        data = [
            {"DT": "1,000"},
            {"DT": "2000"},
            {"DT": "-"},
            {"DT": ""},
        ]
        converted = visualizer._convert_numeric(data, "DT")
        assert converted[0]["DT"] == 1000.0
        assert converted[1]["DT"] == 2000.0
        assert converted[2]["DT"] is None
        assert converted[3]["DT"] is None


class TestConvenienceFunctions:
    """편의 함수 테스트."""

    def test_quick_line(self, sample_data: list[dict]):
        """quick_line 함수."""
        fig = quick_line(sample_data, title="테스트 차트")
        assert isinstance(fig, go.Figure)

    def test_quick_bar(self, sample_data: list[dict]):
        """quick_bar 함수."""
        fig = quick_bar(sample_data, x="C1_NM")
        assert isinstance(fig, go.Figure)

    def test_quick_pie(self, sample_data: list[dict]):
        """quick_pie 함수."""
        data_2020 = [d for d in sample_data if d["PRD_DE"] == "2020"]
        fig = quick_pie(data_2020)
        assert isinstance(fig, go.Figure)
