"""시각화 검증 로직 테스트.

execute_code에서 빈 차트 데이터를 감지하고
클라이언트에게 에러와 데이터 시그니처를 반환하는지 테스트합니다.
"""

import pytest
from kosis_tools.code_executor import CodeExecutor

pytestmark = pytest.mark.skip(reason="Native visualization was removed from core MCP.")


@pytest.fixture
def executor():
    """CodeExecutor 인스턴스."""
    return CodeExecutor()


@pytest.fixture
def sample_kosis_data():
    """샘플 KOSIS 데이터."""
    return [
        {
            "PRD_DE": "2021",
            "C1_NM": "서울",
            "DT": "9500000",
            "ITM_NM": "총인구",
            "UNIT_NM": "명",
        },
        {
            "PRD_DE": "2022",
            "C1_NM": "서울",
            "DT": "9400000",
            "ITM_NM": "총인구",
            "UNIT_NM": "명",
        },
        {
            "PRD_DE": "2023",
            "C1_NM": "서울",
            "DT": "9300000",
            "ITM_NM": "총인구",
            "UNIT_NM": "명",
        },
        {
            "PRD_DE": "2021",
            "C1_NM": "경기",
            "DT": "13000000",
            "ITM_NM": "총인구",
            "UNIT_NM": "명",
        },
        {
            "PRD_DE": "2022",
            "C1_NM": "경기",
            "DT": "13200000",
            "ITM_NM": "총인구",
            "UNIT_NM": "명",
        },
        {
            "PRD_DE": "2023",
            "C1_NM": "경기",
            "DT": "13500000",
            "ITM_NM": "총인구",
            "UNIT_NM": "명",
        },
    ]


class TestVisualizationValidation:
    """시각화 검증 테스트."""

    def test_valid_chart_passes_validation(self, executor, sample_kosis_data):
        """정상적인 차트 데이터는 검증 통과."""
        code = """
df = prepare_data(data, numeric_fields=["DT"])
chart = alt.Chart(df).mark_line().encode(
    x='PRD_DE:N',
    y='DT:Q',
    color='C1_NM:N'
).properties(width=600, height=400)
return chart_to_json(chart)
"""
        result = executor.execute(code, data=sample_kosis_data)

        assert result["success"] is True
        assert (
            "validation_details" not in result
            or result.get("validation_details") is None
        )

    def test_empty_chart_fails_validation(self, executor, sample_kosis_data):
        """빈 차트 데이터는 검증 실패."""
        # 존재하지 않는 지역으로 필터링 → 빈 DataFrame
        code = """
df = prepare_data(data, numeric_fields=["DT"])
df = df[df["C1_NM"] == "존재하지않는지역"]  # 빈 결과
chart = alt.Chart(df).mark_line().encode(
    x='PRD_DE:N',
    y='DT:Q'
).properties(width=600, height=400)
return chart_to_json(chart)
"""
        result = executor.execute(code, data=sample_kosis_data)

        # 검증 실패 확인
        assert result["success"] is False
        assert "validation_details" in result
        assert result["validation_details"]["issue_type"] == "EMPTY_CHART_DATA"
        assert len(result["validation_details"]["empty_charts"]) > 0

    def test_validation_includes_data_signature(self, executor, sample_kosis_data):
        """검증 실패 시 데이터 시그니처 포함."""
        code = """
df = prepare_data(data, numeric_fields=["DT"])
df = df[df["C1_NM"] == "없는지역"]  # 빈 결과
chart = alt.Chart(df).mark_bar().encode(x='C1_NM:N', y='DT:Q')
return chart_to_json(chart)
"""
        result = executor.execute(code, data=sample_kosis_data)

        assert result["success"] is False
        assert "validation_details" in result

        # 데이터 시그니처 확인
        signature = result["validation_details"]["data_signature"]
        assert "total_records" in signature
        assert signature["total_records"] == 6
        assert "fields" in signature
        assert "PRD_DE" in signature["fields"]
        assert "C1_NM" in signature["fields"]
        assert "DT" in signature["fields"]

        # 샘플 레코드 확인
        assert "sample_records" in signature
        assert len(signature["sample_records"]) <= 3

    def test_validation_includes_fix_hints(self, executor, sample_kosis_data):
        """검증 실패 시 수정 힌트 포함."""
        code = """
df = prepare_data(data, numeric_fields=["DT"])
df = df.head(0)  # 의도적으로 빈 DataFrame
chart = alt.Chart(df).mark_line().encode(x='PRD_DE:N', y='DT:Q')
return chart_to_json(chart)
"""
        result = executor.execute(code, data=sample_kosis_data)

        assert result["success"] is False
        assert "validation_details" in result
        assert "fix_hints" in result["validation_details"]
        assert len(result["validation_details"]["fix_hints"]) > 0

    def test_kosis_hints_in_signature(self, executor, sample_kosis_data):
        """데이터 시그니처에 KOSIS 힌트 포함."""
        code = """
df = prepare_data(data, numeric_fields=["DT"])
df = df[df["DT"] > 99999999999]  # 불가능한 조건
chart = alt.Chart(df).mark_bar().encode(x='C1_NM:N', y='DT:Q')
return chart_to_json(chart)
"""
        result = executor.execute(code, data=sample_kosis_data)

        assert result["success"] is False
        signature = result["validation_details"]["data_signature"]

        # KOSIS 필드 힌트 확인
        assert "kosis_hints" in signature
        assert "PRD_DE" in signature["kosis_hints"]
        assert "DT" in signature["kosis_hints"]
        assert "문자열" in signature["kosis_hints"]["DT"]  # DT가 문자열임을 알려줌


class TestCheckVegaSpec:
    """_check_vega_spec 메서드 테스트."""

    def test_detects_empty_values_in_data(self, executor):
        """data.values가 빈 배열인 경우 감지."""
        spec = {
            "data": {"values": []},
            "mark": "line",
            "encoding": {"x": {"field": "x"}, "y": {"field": "y"}},
        }

        result = executor._check_vega_spec(spec, "test_chart")

        assert result is not None
        assert result["chart_id"] == "test_chart"
        assert "빈 데이터" in result["issue"]

    def test_detects_empty_values_in_layer(self, executor):
        """layer 내부의 빈 데이터 감지."""
        spec = {
            "layer": [
                {"data": {"values": []}, "mark": "line"},
                {"data": {"values": [{"x": 1, "y": 2}]}, "mark": "point"},
            ]
        }

        result = executor._check_vega_spec(spec, "layered_chart")

        assert result is not None
        assert "layer[0]" in result["path"]

    def test_valid_spec_returns_none(self, executor):
        """정상 스펙은 None 반환."""
        spec = {
            "data": {"values": [{"x": 1, "y": 2}, {"x": 2, "y": 4}]},
            "mark": "line",
            "encoding": {"x": {"field": "x"}, "y": {"field": "y"}},
        }

        result = executor._check_vega_spec(spec, "valid_chart")

        assert result is None


class TestGenerateDataSignature:
    """_generate_data_signature 메서드 테스트."""

    def test_generates_signature_from_data(self, executor, sample_kosis_data):
        """데이터로부터 시그니처 생성."""
        signature = executor._generate_data_signature(sample_kosis_data)

        assert signature["total_records"] == 6
        assert len(signature["sample_records"]) == 3
        assert "PRD_DE" in signature["fields"]
        assert "C1_NM" in signature["fields"]

    def test_handles_empty_data(self, executor):
        """빈 데이터 처리."""
        signature = executor._generate_data_signature([])

        assert "error" in signature or signature["total_records"] == 0

    def test_handles_none_data(self, executor):
        """None 데이터 처리."""
        signature = executor._generate_data_signature(None)

        assert "error" in signature
        assert "hint" in signature


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
