"""
kosis_tools.visualize 모듈 유닛 테스트.

테스트 범위:
    - prepare_data: 데이터 변환
    - save_chart: 차트 저장
    - chart_to_json, chart_to_html: 변환 함수
"""

import pytest
import altair as alt
import pandas as pd
import tempfile
from pathlib import Path

from kosis_tools.visualize import (
    prepare_data,
    save_chart,
    chart_to_json,
    chart_to_html,
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
    ]


class TestPrepareData:
    """prepare_data 함수 테스트."""

    def test_basic_conversion(self, sample_data):
        """기본 변환."""
        df = prepare_data(sample_data)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 6

    def test_numeric_conversion(self, sample_data):
        """숫자 변환."""
        df = prepare_data(sample_data, numeric_fields=["DT"])
        # int64 또는 float64 모두 유효한 숫자형
        assert df["DT"].dtype in [float, "float64", "int64", int]
        assert df["DT"].iloc[0] == 50000000

    def test_special_values(self):
        """특수값 처리."""
        data = [
            {"DT": "1,000"},
            {"DT": "-"},
            {"DT": ""},
            {"DT": "*"},
        ]
        df = prepare_data(data, numeric_fields=["DT"])
        assert df["DT"].iloc[0] == 1000.0
        assert pd.isna(df["DT"].iloc[1])
        assert pd.isna(df["DT"].iloc[2])
        assert pd.isna(df["DT"].iloc[3])


class TestSaveChart:
    """save_chart 함수 테스트."""

    def test_save_html(self, sample_data):
        """HTML 저장."""
        df = prepare_data(sample_data, numeric_fields=["DT"])
        chart = alt.Chart(df).mark_line().encode(x="PRD_DE:N", y="DT:Q")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = save_chart(chart, "test.html", output_dir=tmpdir)
            assert result["format"] == "html"
            assert Path(result["path"]).exists()

    def test_save_svg(self, sample_data):
        """SVG 저장."""
        df = prepare_data(sample_data, numeric_fields=["DT"])
        chart = alt.Chart(df).mark_bar().encode(x="C1_NM:N", y="DT:Q")

        with tempfile.TemporaryDirectory() as tmpdir:
            result = save_chart(chart, "test.svg", output_dir=tmpdir)
            assert result["format"] == "svg"
            assert Path(result["path"]).exists()


class TestChartConversion:
    """차트 변환 함수 테스트."""

    def test_chart_to_json(self, sample_data):
        """JSON 변환."""
        df = prepare_data(sample_data, numeric_fields=["DT"])
        chart = alt.Chart(df).mark_line().encode(x="PRD_DE:N", y="DT:Q")

        json_str = chart_to_json(chart)
        assert isinstance(json_str, str)
        assert '"mark"' in json_str

    def test_chart_to_html(self, sample_data):
        """HTML 변환."""
        df = prepare_data(sample_data, numeric_fields=["DT"])
        chart = alt.Chart(df).mark_line().encode(x="PRD_DE:N", y="DT:Q")

        html = chart_to_html(chart, title="Test Chart")
        assert "<!DOCTYPE html>" in html
        assert "vega-embed" in html
        assert "Test Chart" in html
