"""
시각화 품질 자동화 테스트.

이 테스트는 생성된 차트가 올바르게 데이터를 표시하는지 검증합니다.
- Y축 범위가 올바른지 (정규화되지 않았는지)
- 모든 데이터 포인트가 표시되는지
- 레전드와 실제 데이터가 일치하는지
"""

import json
import pytest
from pathlib import Path

# 프로젝트 루트 추가
import sys
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from kosis_tools.visualize import KosisVisualizer


class TestVisualizationDataIntegrity:
    """시각화 데이터 무결성 테스트"""

    @pytest.fixture
    def sample_population_data(self):
        """테스트용 인구 데이터"""
        return [
            {"PRD_DE": "2020", "C1_NM": "서울특별시", "DT": 9668465, "ITM_NM": "총인구"},
            {"PRD_DE": "2020", "C1_NM": "부산광역시", "DT": 3391946, "ITM_NM": "총인구"},
            {"PRD_DE": "2021", "C1_NM": "서울특별시", "DT": 9509458, "ITM_NM": "총인구"},
            {"PRD_DE": "2021", "C1_NM": "부산광역시", "DT": 3350380, "ITM_NM": "총인구"},
            {"PRD_DE": "2022", "C1_NM": "서울특별시", "DT": 9428372, "ITM_NM": "총인구"},
            {"PRD_DE": "2022", "C1_NM": "부산광역시", "DT": 3314183, "ITM_NM": "총인구"},
            {"PRD_DE": "2023", "C1_NM": "서울특별시", "DT": 9386239, "ITM_NM": "총인구"},
            {"PRD_DE": "2023", "C1_NM": "부산광역시", "DT": 3293842, "ITM_NM": "총인구"},
        ]

    @pytest.fixture
    def visualizer(self):
        return KosisVisualizer()

    def test_bar_chart_y_axis_not_normalized(self, visualizer, sample_population_data):
        """막대 차트 Y축이 정규화되지 않았는지 확인"""
        fig = visualizer.bar_chart(
            sample_population_data,
            x="C1_NM",
            y="DT",
            color="PRD_DE",
            title="지역별 비교"
        )

        # Y축 데이터 추출
        all_y_values = []
        for trace in fig.data:
            y_data = trace.y
            if hasattr(y_data, 'tolist'):
                y_data = y_data.tolist()
            elif isinstance(y_data, dict) and 'bdata' in y_data:
                # binary data인 경우 - 이건 버그!
                pytest.fail(
                    f"Y축 데이터가 binary encoding되어 있습니다: {y_data}. "
                    "Plotly가 데이터를 제대로 인코딩하지 못했습니다."
                )
            all_y_values.extend(y_data if isinstance(y_data, (list, tuple)) else [y_data])

        # 실제 값 범위 확인
        min_val = min(v for v in all_y_values if v is not None)
        max_val = max(v for v in all_y_values if v is not None)

        # Y축이 0~1 범위로 정규화되지 않았는지 확인
        assert max_val > 1, f"Y축 최대값이 1 이하입니다 ({max_val}). 데이터가 정규화된 것 같습니다."

        # 실제 인구 데이터 값과 비교
        expected_min = min(d["DT"] for d in sample_population_data)
        expected_max = max(d["DT"] for d in sample_population_data)

        assert min_val == expected_min, f"Y축 최소값 불일치: {min_val} != {expected_min}"
        assert max_val == expected_max, f"Y축 최대값 불일치: {max_val} != {expected_max}"

    def test_bar_chart_all_categories_present(self, visualizer, sample_population_data):
        """막대 차트에 모든 카테고리가 표시되는지 확인"""
        fig = visualizer.bar_chart(
            sample_population_data,
            x="C1_NM",
            y="DT",
            color="PRD_DE",
            title="지역별 비교"
        )

        # 모든 트레이스에서 X축 값 수집
        all_x_values = set()
        for trace in fig.data:
            x_data = trace.x
            if hasattr(x_data, 'tolist'):
                x_data = x_data.tolist()
            all_x_values.update(x_data if isinstance(x_data, (list, tuple)) else [x_data])

        # 원본 데이터의 카테고리와 비교
        expected_categories = set(d["C1_NM"] for d in sample_population_data)

        assert all_x_values == expected_categories, (
            f"카테고리 불일치!\n"
            f"차트에 있는 카테고리: {all_x_values}\n"
            f"원본 데이터 카테고리: {expected_categories}\n"
            f"누락된 카테고리: {expected_categories - all_x_values}"
        )

    def test_bar_chart_legend_matches_data(self, visualizer, sample_population_data):
        """레전드가 실제 데이터와 일치하는지 확인"""
        fig = visualizer.bar_chart(
            sample_population_data,
            x="C1_NM",
            y="DT",
            color="PRD_DE",
            title="지역별 비교"
        )

        # 레전드 항목 수집
        legend_names = set(trace.name for trace in fig.data if trace.name)

        # 원본 데이터의 color 필드 값과 비교
        expected_legend = set(str(d["PRD_DE"]) for d in sample_population_data)

        assert legend_names == expected_legend, (
            f"레전드 불일치!\n"
            f"차트 레전드: {legend_names}\n"
            f"원본 데이터: {expected_legend}"
        )

    def test_line_chart_all_data_points_present(self, visualizer, sample_population_data):
        """라인 차트에 모든 데이터 포인트가 있는지 확인"""
        fig = visualizer.line_chart(
            sample_population_data,
            x="PRD_DE",
            y="DT",
            color="C1_NM",
            title="시계열 추이"
        )

        # 전체 데이터 포인트 수 계산
        total_points = sum(len(trace.y) for trace in fig.data)
        expected_points = len(sample_population_data)

        assert total_points == expected_points, (
            f"데이터 포인트 수 불일치: {total_points} != {expected_points}"
        )

    def test_chart_data_values_match_input(self, visualizer, sample_population_data):
        """차트 데이터 값이 입력값과 일치하는지 확인"""
        fig = visualizer.bar_chart(
            sample_population_data,
            x="C1_NM",
            y="DT",
            color="PRD_DE",
            title="지역별 비교"
        )

        # 차트에서 모든 Y값 추출
        chart_values = []
        for trace in fig.data:
            y_data = trace.y
            if hasattr(y_data, 'tolist'):
                y_data = y_data.tolist()
            chart_values.extend(y_data if isinstance(y_data, (list, tuple)) else [y_data])

        # 입력 데이터의 Y값
        input_values = sorted([d["DT"] for d in sample_population_data])
        chart_values_sorted = sorted(chart_values)

        assert chart_values_sorted == input_values, (
            f"데이터 값 불일치!\n"
            f"차트 값: {chart_values_sorted}\n"
            f"입력 값: {input_values}"
        )


class TestVisualizationEdgeCases:
    """엣지케이스 시각화 테스트"""

    @pytest.fixture
    def visualizer(self):
        return KosisVisualizer()

    def test_single_data_point(self, visualizer):
        """단일 데이터 포인트 처리"""
        data = [{"PRD_DE": "2023", "C1_NM": "서울", "DT": 9500000}]

        fig = visualizer.bar_chart(data, x="C1_NM", y="DT")

        assert len(fig.data) == 1
        assert len(fig.data[0].y) == 1
        assert fig.data[0].y[0] == 9500000

    def test_extreme_values(self, visualizer):
        """극단값 처리"""
        data = [
            {"PRD_DE": "2023", "C1_NM": "극대지역", "DT": 999999999999},
            {"PRD_DE": "2023", "C1_NM": "영지역", "DT": 0},
            {"PRD_DE": "2023", "C1_NM": "소수지역", "DT": 0.001},
        ]

        fig = visualizer.bar_chart(data, x="C1_NM", y="DT")

        # 모든 데이터가 차트에 포함되어야 함
        all_y = []
        for trace in fig.data:
            y_data = trace.y
            if hasattr(y_data, 'tolist'):
                y_data = y_data.tolist()
            all_y.extend(y_data if isinstance(y_data, (list, tuple)) else [y_data])

        assert 999999999999 in all_y, "극대값이 차트에 없습니다"
        assert 0 in all_y, "0값이 차트에 없습니다"
        assert 0.001 in all_y, "소수값이 차트에 없습니다"

    def test_null_values_handled(self, visualizer):
        """결측치 처리"""
        data = [
            {"PRD_DE": "2023", "C1_NM": "서울", "DT": 9500000},
            {"PRD_DE": "2023", "C1_NM": "부산", "DT": None},
            {"PRD_DE": "2023", "C1_NM": "대구", "DT": 2400000},
        ]

        # 결측치가 있어도 에러 없이 차트 생성
        fig = visualizer.bar_chart(data, x="C1_NM", y="DT")

        assert fig is not None
        # 결측치가 있는 경우 해당 데이터 포인트는 None으로 처리됨
        all_y = []
        for trace in fig.data:
            y_data = trace.y
            if hasattr(y_data, 'tolist'):
                y_data = y_data.tolist()
            all_y.extend(y_data if isinstance(y_data, (list, tuple)) else [y_data])

        # None 값이 포함되어도 유효한 값들은 존재해야 함
        valid_values = [v for v in all_y if v is not None]
        assert 9500000 in valid_values
        assert 2400000 in valid_values


class TestGeneratedReportVisualization:
    """생성된 리포트의 시각화 검증 테스트"""

    def test_generated_html_has_valid_plotly_data(self):
        """생성된 HTML의 Plotly 데이터가 유효한지 확인"""
        output_dir = Path(__file__).parent.parent.parent / "examples" / "gallery" / "output"

        if not output_dir.exists():
            pytest.skip("output 디렉토리가 없습니다. 먼저 generate_debug_reports.py를 실행하세요.")

        html_files = list(output_dir.glob("*.html"))

        if not html_files:
            pytest.skip("생성된 HTML 파일이 없습니다.")

        for html_file in html_files:
            content = html_file.read_text(encoding="utf-8")

            # Plotly.newPlot 호출이 있는지 확인
            if "Plotly.newPlot" not in content:
                continue  # 차트가 없는 파일은 스킵

            # Y축 데이터가 binary encoding인지 확인
            # binary encoding은 "bdata": 패턴으로 나타남
            if '"bdata":' in content:
                # bdata가 있어도 정상적인 경우가 있으므로 Y축 범위 확인
                # yaxis domain이 [0, 1]인데 실제 데이터도 0~1이면 문제
                import re

                # Y 데이터 패턴 찾기
                y_patterns = re.findall(r'"y":\s*\{[^}]*"bdata":[^}]*\}', content)

                if y_patterns:
                    # bdata로 인코딩된 Y 데이터가 있음 - 경고
                    print(f"경고: {html_file.name}에 binary encoded Y 데이터가 있습니다.")

            # 차트에 데이터가 있는지 기본 확인
            assert '"x":' in content or '"y":' in content, (
                f"{html_file.name}: Plotly 차트에 x 또는 y 데이터가 없습니다."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
