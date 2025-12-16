"""
kosis_tools.code_executor 모듈 유닛 테스트.

테스트 범위:
    - CodeExecutor: 코드 실행 엔진
    - validate_code: 보안 검증
    - execute_code: 편의 함수
"""

import pytest

from kosis_tools.code_executor import (
    CodeExecutor,
    CodeSecurityError,
    execute_code,
)


@pytest.fixture
def executor():
    """CodeExecutor 인스턴스."""
    return CodeExecutor(timeout=10)


@pytest.fixture
def sample_data():
    """테스트용 KOSIS 데이터."""
    return [
        {"PRD_DE": "2020", "C1_NM": "전국", "DT": "50000000"},
        {"PRD_DE": "2020", "C1_NM": "서울", "DT": "10000000"},
        {"PRD_DE": "2021", "C1_NM": "전국", "DT": "49500000"},
        {"PRD_DE": "2021", "C1_NM": "서울", "DT": "9800000"},
    ]


class TestCodeValidation:
    """보안 검증 테스트."""

    def test_block_os_import(self, executor):
        """os 모듈 import 차단."""
        code = "import os\nos.system('ls')"
        with pytest.raises(CodeSecurityError):
            executor.validate_code(code)

    def test_block_subprocess(self, executor):
        """subprocess 모듈 차단."""
        code = "import subprocess"
        with pytest.raises(CodeSecurityError):
            executor.validate_code(code)

    def test_block_eval(self, executor):
        """eval 함수 차단."""
        code = "result = eval('1+1')"
        with pytest.raises(CodeSecurityError):
            executor.validate_code(code)

    def test_block_open(self, executor):
        """open 함수 차단."""
        code = "f = open('/etc/passwd')"
        with pytest.raises(CodeSecurityError):
            executor.validate_code(code)

    def test_allow_safe_code(self, executor):
        """안전한 코드 허용."""
        code = """
df = pd.DataFrame(data)
result = df['DT'].sum()
"""
        executor.validate_code(code)  # 예외 없으면 통과


class TestCodeExecution:
    """코드 실행 테스트."""

    def test_simple_expression(self, executor, sample_data):
        """단순 표현식 실행."""
        result = executor.execute("len(data)", data=sample_data)
        assert result["success"] is True
        assert result["result"] == 4

    def test_pandas_operation(self, executor, sample_data):
        """pandas 연산."""
        code = """
df = pd.DataFrame(data)
df['DT'] = pd.to_numeric(df['DT'])
return df['DT'].sum()
"""
        result = executor.execute(code, data=sample_data)
        assert result["success"] is True
        # 50000000 + 10000000 + 49500000 + 9800000 = 119300000
        assert result["result"] == 119300000

    def test_prepare_data_helper(self, executor, sample_data):
        """prepare_data 헬퍼 사용."""
        code = """
df = prepare_data(data, numeric_fields=["DT"])
return df["DT"].mean()
"""
        result = executor.execute(code, data=sample_data)
        assert result["success"] is True
        assert result["result"] == 29825000.0

    def test_altair_chart(self, executor, sample_data):
        """Altair 차트 생성."""
        code = """
df = prepare_data(data, numeric_fields=["DT"])
chart = alt.Chart(df).mark_line().encode(x='PRD_DE:N', y='DT:Q')
return chart_to_json(chart)
"""
        result = executor.execute(code, data=sample_data)
        assert result["success"] is True
        assert '"mark"' in result["result"]

    def test_stdout_capture(self, executor, sample_data):
        """print 출력 캡처."""
        code = """
print("Hello, KOSIS!")
len(data)
"""
        result = executor.execute(code, data=sample_data)
        assert result["success"] is True
        assert "Hello, KOSIS!" in result["stdout"]

    def test_error_handling(self, executor):
        """오류 처리."""
        code = "1 / 0"
        result = executor.execute(code)
        assert result["success"] is False
        assert "ZeroDivisionError" in result["error"]

    def test_security_error_result(self, executor):
        """보안 오류 결과 형식."""
        code = "import os"
        result = executor.execute(code)
        assert result["success"] is False
        assert "금지된 패턴" in result["error"]


class TestConvenienceFunction:
    """execute_code 편의 함수 테스트."""

    def test_execute_code_function(self, sample_data):
        """execute_code 함수."""
        result = execute_code("len(data)", data=sample_data)
        assert result["success"] is True
        assert result["result"] == 4
