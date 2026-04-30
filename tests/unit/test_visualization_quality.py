"""
시각화 품질 자동화 테스트.

이 테스트는 code_executor의 품질 검사 시스템을 검증합니다.
- 빈 차트 데이터 감지
- 차트 제목/축 라벨 검사
- 숫자 포맷 검사
- 리포트 구조 검사
"""

import pytest

from kosis_tools.code_executor import execute_code, CodeExecutor

pytestmark = pytest.mark.skip(reason="Native visualization was removed from core MCP.")


class TestVisualizationValidation:
    """시각화 검증 테스트"""

    @pytest.fixture
    def sample_data(self):
        """테스트용 KOSIS 데이터"""
        return [
            {
                "PRD_DE": "2020",
                "C1_NM": "서울특별시",
                "DT": "9668465",
                "ITM_NM": "총인구",
                "UNIT_NM": "명",
            },
            {
                "PRD_DE": "2021",
                "C1_NM": "서울특별시",
                "DT": "9509458",
                "ITM_NM": "총인구",
                "UNIT_NM": "명",
            },
            {
                "PRD_DE": "2022",
                "C1_NM": "서울특별시",
                "DT": "9428372",
                "ITM_NM": "총인구",
                "UNIT_NM": "명",
            },
            {
                "PRD_DE": "2020",
                "C1_NM": "부산광역시",
                "DT": "3391946",
                "ITM_NM": "총인구",
                "UNIT_NM": "명",
            },
            {
                "PRD_DE": "2021",
                "C1_NM": "부산광역시",
                "DT": "3350380",
                "ITM_NM": "총인구",
                "UNIT_NM": "명",
            },
            {
                "PRD_DE": "2022",
                "C1_NM": "부산광역시",
                "DT": "3314183",
                "ITM_NM": "총인구",
                "UNIT_NM": "명",
            },
        ]

    def test_empty_chart_detection(self, sample_data):
        """빈 차트 데이터 감지 테스트"""
        code = """
df = prepare_data(data, numeric_fields=["DT"])
# 존재하지 않는 지역으로 필터링 → 빈 DataFrame
df = df[df["C1_NM"] == "존재하지않는지역"]
chart = alt.Chart(df).mark_bar().encode(x='C1_NM:N', y='DT:Q')
return chart_to_json(chart)
"""
        result = execute_code(code, data=sample_data)

        assert result["success"] is False
        assert "validation_details" in result
        assert result["validation_details"]["issue_type"] == "EMPTY_CHART_DATA"
        assert "data_signature" in result["validation_details"]

    def test_successful_chart_with_quality_warnings(self, sample_data):
        """정상 차트이지만 품질 경고가 있는 경우"""
        code = """
df = prepare_data(data, numeric_fields=["DT"])
# 제목 없음, 축 포맷 없음
chart = alt.Chart(df).mark_line().encode(
    x='PRD_DE:N',
    y='DT:Q'
).properties(width=600, height=400)
return chart_to_json(chart)
"""
        result = execute_code(code, data=sample_data)

        assert result["success"] is True
        assert "quality_warnings" in result

        # 예상되는 경고들
        issues = [w["issue"] for w in result["quality_warnings"]]
        assert "missing_title" in issues
        assert "missing_number_format" in issues

    def test_high_quality_chart_no_warnings(self, sample_data):
        """고품질 차트는 경고가 적어야 함"""
        code = """
df = prepare_data(data, numeric_fields=["DT"])
chart = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X('PRD_DE:N', title='연도'),
    y=alt.Y('DT:Q', title='인구 (명)', axis=alt.Axis(format=',')),
    color=alt.Color('C1_NM:N', title='지역')
).properties(
    title='서울 vs 부산 인구 변화 추이',
    width=600,
    height=400
)
return chart_to_json(chart)
"""
        result = execute_code(code, data=sample_data)

        assert result["success"] is True
        # 고품질 차트는 경고가 없거나 적어야 함
        warnings = result.get("quality_warnings", [])
        high_severity = [w for w in warnings if w["severity"] == "high"]
        assert len(high_severity) == 0, (
            f"고품질 차트에 심각한 경고가 있습니다: {high_severity}"
        )


class TestQualityFeedbackDetails:
    """품질 피드백 상세 테스트"""

    @pytest.fixture
    def executor(self):
        return CodeExecutor()

    @pytest.fixture
    def sample_data(self):
        return [
            {"PRD_DE": "2023", "C1_NM": "서울", "DT": "9500000"},
        ]

    def test_quality_summary_structure(self, sample_data):
        """품질 요약 구조 확인"""
        code = """
df = prepare_data(data, numeric_fields=["DT"])
chart = alt.Chart(df).mark_bar().encode(x='C1_NM:N', y='DT:Q')
return chart_to_json(chart)
"""
        result = execute_code(code, data=sample_data)

        if "quality_summary" in result:
            summary = result["quality_summary"]
            assert "total_warnings" in summary
            assert "by_severity" in summary
            assert "high" in summary["by_severity"]
            assert "medium" in summary["by_severity"]
            assert "low" in summary["by_severity"]
            assert "recommendations" in summary

    def test_fix_hints_provided(self, sample_data):
        """수정 힌트가 제공되는지 확인"""
        code = """
df = prepare_data(data, numeric_fields=["DT"])
chart = alt.Chart(df).mark_bar().encode(x='C1_NM:N', y='DT:Q')
return chart_to_json(chart)
"""
        result = execute_code(code, data=sample_data)

        if "quality_warnings" in result:
            for warning in result["quality_warnings"]:
                assert "fix" in warning, f"경고에 fix 힌트가 없습니다: {warning}"


class TestDataSignature:
    """데이터 시그니처 테스트"""

    @pytest.fixture
    def executor(self):
        return CodeExecutor()

    def test_data_signature_generation(self, executor):
        """데이터 시그니처 생성 테스트"""
        data = [
            {"PRD_DE": "2023", "C1_NM": "서울", "DT": "9500000", "UNIT_NM": "명"},
            {"PRD_DE": "2022", "C1_NM": "부산", "DT": "3400000", "UNIT_NM": "명"},
        ]

        signature = executor._generate_data_signature(data)

        assert "total_records" in signature
        assert signature["total_records"] == 2
        assert "fields" in signature
        assert "PRD_DE" in signature["fields"]
        assert "sample_values" in signature["fields"]["PRD_DE"]
        assert "kosis_hints" in signature

    def test_empty_data_signature(self, executor):
        """빈 데이터 시그니처 테스트"""
        signature = executor._generate_data_signature(None)

        assert "error" in signature


class TestVegaSpecAnalysis:
    """Vega-Lite 스펙 분석 테스트"""

    @pytest.fixture
    def executor(self):
        return CodeExecutor()

    def test_empty_datasets_detection(self, executor):
        """빈 datasets 감지"""
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "datasets": {"data_0": []},
            "data": {"name": "data_0"},
            "mark": "bar",
            "encoding": {"x": {"field": "x"}, "y": {"field": "y"}},
        }

        result = executor._check_vega_spec(spec, "test_chart")

        assert result is not None
        assert "빈 데이터셋" in result["issue"]

    def test_empty_values_detection(self, executor):
        """빈 values 감지"""
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "data": {"values": []},
            "mark": "bar",
            "encoding": {"x": {"field": "x"}, "y": {"field": "y"}},
        }

        result = executor._check_vega_spec(spec, "test_chart")

        assert result is not None
        assert "빈 데이터" in result["issue"]

    def test_valid_data_passes(self, executor):
        """유효한 데이터는 통과"""
        spec = {
            "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
            "data": {"values": [{"x": 1, "y": 2}]},
            "mark": "bar",
            "encoding": {"x": {"field": "x"}, "y": {"field": "y"}},
        }

        result = executor._check_vega_spec(spec, "test_chart")

        assert result is None  # 문제 없음


class TestStoryTemplates:
    """스토리 템플릿 시스템 테스트"""

    def test_template_list(self):
        """템플릿 목록 조회"""
        from kosis_tools.story_templates import get_template_list

        templates = get_template_list()

        assert len(templates) >= 6  # 최소 6개 템플릿
        assert all("id" in t for t in templates)
        assert all("name" in t for t in templates)

    def test_template_guide(self):
        """템플릿 가이드 조회"""
        from kosis_tools.story_templates import get_template_guide

        guide = get_template_guide("trend")

        assert guide is not None
        assert "structure" in guide
        assert "code_pattern" in guide

    def test_template_step(self):
        """템플릿 단계별 가이드"""
        from kosis_tools.story_templates import get_template_step

        step = get_template_step("trend", 1)

        assert step is not None
        assert "current_step" in step
        assert "progress" in step
        assert "code_hint" in step

    def test_element_guide(self):
        """요소 가이드 조회"""
        from kosis_tools.story_templates import get_element_guide

        guide = get_element_guide("line_chart")

        assert "when" in guide
        assert "must_have" in guide
        assert "code" in guide
        assert "avoid" in guide


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
