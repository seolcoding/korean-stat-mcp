"""
E2E 테스트용 공통 fixtures.

비판적 분석 기반 설계:
- 페르소나별 분리 대신 "시나리오 복잡도"와 "데이터 크기"로 구분
- 실제 MCP 서버 도구 함수 호출 테스트 지원
- 토큰 효율성은 문자 수 기반 실용적 측정
"""

import pytest
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Callable
from dataclasses import dataclass


# =============================================================================
# 상수 정의 (MCP 가이드라인 기준)
# =============================================================================

# MCP_PATTERN.md 기반 제한
MAX_CONTEXT_CHARS = 10_000       # LLM 컨텍스트 최대 문자 (~5,000 토큰)
MAX_SAMPLE_ROWS = 50             # 샘플 데이터 최대 행
TOKEN_REDUCTION_TARGET = 0.90    # 목표 토큰 절감률

# 데이터 크기별 분류
DATA_SIZE_SMALL = 50             # 소규모: 필터링 없이 전체 반환 가능
DATA_SIZE_MEDIUM = 500           # 중규모: 요약 필요
DATA_SIZE_LARGE = 3000           # 대규모: 청킹 필수


@dataclass
class TestMetrics:
    """테스트 측정 결과."""
    input_records: int
    output_chars: int
    output_records: int = 0
    reduction_ratio: float = 0.0
    execution_time_ms: float = 0.0

    @property
    def passes_size_limit(self) -> bool:
        return self.output_chars <= MAX_CONTEXT_CHARS

    @property
    def passes_reduction_target(self) -> bool:
        return self.reduction_ratio >= TOKEN_REDUCTION_TARGET


# =============================================================================
# 데이터 생성 Fixtures
# =============================================================================

@pytest.fixture
def small_population_data() -> List[Dict[str, Any]]:
    """
    소규모 인구 데이터 (40건).

    용도: 간단한 질문, 필터링 없이 전체 반환 가능한 케이스
    """
    regions = ["서울특별시", "부산광역시", "대구광역시", "인천광역시"]
    years = ["2020", "2021", "2022", "2023", "2024"]
    items = ["총인구", "남자인구"]

    base_pop = {
        "서울특별시": 9_400_000,
        "부산광역시": 3_300_000,
        "대구광역시": 2_400_000,
        "인천광역시": 2_900_000,
    }

    data = []
    for year in years:
        for region in regions:
            for item in items:
                year_factor = 1 - (2024 - int(year)) * 0.01
                gender_factor = 0.49 if item == "남자인구" else 1.0
                pop = int(base_pop[region] * year_factor * gender_factor)

                data.append({
                    "TBL_ID": "DT_POP_SMALL",
                    "TBL_NM": "행정구역별 인구",
                    "ORG_ID": "101",
                    "ORG_NM": "통계청",
                    "PRD_DE": year,
                    "PRD_SE": "Y",
                    "C1_NM": region,
                    "C1": f"R{list(base_pop.keys()).index(region):02d}",
                    "ITM_NM": item,
                    "ITM_ID": "T01" if item == "총인구" else "T02",
                    "DT": str(pop),
                    "UNIT_NM": "명",
                })

    return data  # 4 regions × 5 years × 2 items = 40건


@pytest.fixture
def medium_population_data() -> List[Dict[str, Any]]:
    """
    중규모 인구 데이터 (340건).

    용도: 비교 분석, 추세 분석, 요약 필요한 케이스
    """
    regions = [
        "서울특별시", "부산광역시", "대구광역시", "인천광역시",
        "광주광역시", "대전광역시", "울산광역시", "세종특별자치시",
        "경기도", "강원특별자치도", "충청북도", "충청남도",
        "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도"
    ]
    years = [str(y) for y in range(2015, 2025)]  # 10년
    items = ["총인구", "세대수"]

    base_pop = {
        "서울특별시": 9_400_000, "부산광역시": 3_300_000,
        "대구광역시": 2_400_000, "인천광역시": 2_900_000,
        "광주광역시": 1_400_000, "대전광역시": 1_400_000,
        "울산광역시": 1_100_000, "세종특별자치시": 380_000,
        "경기도": 13_600_000, "강원특별자치도": 1_500_000,
        "충청북도": 1_600_000, "충청남도": 2_100_000,
        "전라북도": 1_800_000, "전라남도": 1_800_000,
        "경상북도": 2_600_000, "경상남도": 3_300_000,
        "제주특별자치도": 670_000,
    }

    data = []
    for year in years:
        for region in regions:
            for item in items:
                year_factor = 1 - (2024 - int(year)) * 0.01

                # 감소/증가 트렌드 반영
                if region in ["서울특별시", "부산광역시"]:
                    year_factor *= 0.995  # 추가 감소
                elif region in ["경기도", "세종특별자치시"]:
                    year_factor *= 1.01   # 증가

                if item == "세대수":
                    pop = int(base_pop[region] * year_factor * 0.4)
                else:
                    pop = int(base_pop[region] * year_factor)

                data.append({
                    "TBL_ID": "DT_POP_MEDIUM",
                    "TBL_NM": "시도별 인구 및 세대",
                    "ORG_ID": "101",
                    "ORG_NM": "통계청",
                    "PRD_DE": year,
                    "PRD_SE": "Y",
                    "C1_NM": region,
                    "C1": f"R{list(base_pop.keys()).index(region):02d}",
                    "ITM_NM": item,
                    "ITM_ID": "T01" if item == "총인구" else "T02",
                    "DT": str(pop),
                    "UNIT_NM": "명" if item == "총인구" else "세대",
                })

    return data  # 17 regions × 10 years × 2 items = 340건


@pytest.fixture
def large_population_data() -> List[Dict[str, Any]]:
    """
    대규모 인구 데이터 (2,380건).

    용도: 청킹 테스트, 토큰 효율성 검증
    """
    regions = [
        "서울특별시", "부산광역시", "대구광역시", "인천광역시",
        "광주광역시", "대전광역시", "울산광역시", "세종특별자치시",
        "경기도", "강원특별자치도", "충청북도", "충청남도",
        "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도"
    ]
    years = [str(y) for y in range(2010, 2025)]  # 15년
    items = ["총인구", "남자인구", "여자인구", "세대수", "인구밀도", "면적", "인구증가율"]

    base_pop = {
        "서울특별시": 9_400_000, "부산광역시": 3_300_000,
        "대구광역시": 2_400_000, "인천광역시": 2_900_000,
        "광주광역시": 1_400_000, "대전광역시": 1_400_000,
        "울산광역시": 1_100_000, "세종특별자치시": 380_000,
        "경기도": 13_600_000, "강원특별자치도": 1_500_000,
        "충청북도": 1_600_000, "충청남도": 2_100_000,
        "전라북도": 1_800_000, "전라남도": 1_800_000,
        "경상북도": 2_600_000, "경상남도": 3_300_000,
        "제주특별자치도": 670_000,
    }

    data = []
    for year in years:
        for region in regions:
            for item in items:
                year_diff = 2024 - int(year)

                if item == "총인구":
                    val = int(base_pop[region] * (1 - year_diff * 0.01))
                elif item == "남자인구":
                    val = int(base_pop[region] * 0.49 * (1 - year_diff * 0.01))
                elif item == "여자인구":
                    val = int(base_pop[region] * 0.51 * (1 - year_diff * 0.01))
                elif item == "세대수":
                    val = int(base_pop[region] * 0.4)
                elif item == "인구밀도":
                    val = int(base_pop[region] / 1000)
                elif item == "면적":
                    val = 1000 + hash(region) % 20000
                else:  # 인구증가율
                    val = round(-1.5 + hash((region, year)) % 300 / 100, 1)

                data.append({
                    "TBL_ID": "DT_POP_LARGE",
                    "TBL_NM": "시도별 인구 종합",
                    "ORG_ID": "101",
                    "ORG_NM": "통계청",
                    "PRD_DE": year,
                    "PRD_SE": "Y",
                    "C1_NM": region,
                    "C1": f"R{list(base_pop.keys()).index(region):02d}",
                    "ITM_NM": item,
                    "ITM_ID": f"T{items.index(item):02d}",
                    "DT": str(val),
                    "UNIT_NM": "명" if "인구" in item else "%" if "율" in item else "km²",
                })

    return data  # 17 regions × 15 years × 7 items = 1,785건


@pytest.fixture
def employment_data() -> List[Dict[str, Any]]:
    """
    고용 통계 데이터 (분기별, 288건).

    용도: 다른 도메인 테스트, 분기별 데이터
    """
    industries = [
        "농림어업", "광제조업", "건설업", "도소매업",
        "숙박음식업", "운수창고업", "정보통신업", "금융보험업",
        "부동산업", "전문과학기술업", "사업시설관리업", "교육서비스업"
    ]

    base_emp = {
        "농림어업": 130, "광제조업": 440, "건설업": 200,
        "도소매업": 370, "숙박음식업": 230, "운수창고업": 110,
        "정보통신업": 95, "금융보험업": 85, "부동산업": 55,
        "전문과학기술업": 120, "사업시설관리업": 170, "교육서비스업": 180,
    }

    data = []
    for year in [2022, 2023, 2024]:
        for quarter in [1, 2, 3, 4]:
            if year == 2024 and quarter > 2:
                continue  # 2024 Q3, Q4는 아직 없음

            for industry in industries:
                # 계절 변동 + 트렌드
                seasonal = 1 + (quarter - 2.5) * 0.03
                trend = 1 + (year - 2022) * 0.02 + (quarter - 1) * 0.005
                emp = int(base_emp[industry] * seasonal * trend * 10000)

                data.append({
                    "TBL_ID": "DT_EMP_QUARTER",
                    "TBL_NM": "산업별 취업자",
                    "ORG_ID": "154",
                    "ORG_NM": "고용노동부",
                    "PRD_DE": f"{year}Q{quarter}",
                    "PRD_SE": "Q",
                    "C1_NM": industry,
                    "C1": f"I{industries.index(industry):02d}",
                    "ITM_NM": "취업자수",
                    "ITM_ID": "E01",
                    "DT": str(emp),
                    "UNIT_NM": "명",
                })

    return data


@pytest.fixture
def cpi_data() -> List[Dict[str, Any]]:
    """
    소비자물가지수 데이터 (월별, 240건).

    용도: 월별 시계열 데이터 테스트
    """
    items = ["총지수", "식료품", "주거", "교통", "교육"]
    base_year = 2020

    data = []
    for year in [2022, 2023, 2024]:
        for month in range(1, 13):
            if year == 2024 and month > 6:
                continue

            for item in items:
                inflation = {"총지수": 0.003, "식료품": 0.005, "주거": 0.004,
                           "교통": 0.006, "교육": 0.002}[item]
                months_from_base = (year - base_year) * 12 + month
                idx = 100 * (1 + inflation) ** (months_from_base / 12)

                data.append({
                    "TBL_ID": "DT_CPI_MONTH",
                    "TBL_NM": "소비자물가지수",
                    "ORG_ID": "101",
                    "ORG_NM": "통계청",
                    "PRD_DE": f"{year}{month:02d}",
                    "PRD_SE": "M",
                    "C1_NM": item,
                    "C1": f"C{items.index(item):02d}",
                    "ITM_NM": "지수",
                    "ITM_ID": "I01",
                    "DT": f"{idx:.1f}",
                    "UNIT_NM": "지수",
                })

    return data


# =============================================================================
# 유틸리티 Fixtures
# =============================================================================

@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """테스트 출력 디렉토리."""
    output = tmp_path / "test_outputs"
    output.mkdir(exist_ok=True)
    return output


@pytest.fixture
def measure_output() -> Callable:
    """
    출력 크기 측정 유틸리티.

    Usage:
        metrics = measure_output(data, result)
        assert metrics.passes_size_limit
    """
    def _measure(
        input_data: List[Dict],
        output: Any,
        raw_data: List[Dict] = None,
    ) -> TestMetrics:
        input_json = json.dumps(input_data, ensure_ascii=False)

        if isinstance(output, str):
            output_json = output
        elif isinstance(output, (dict, list)):
            output_json = json.dumps(output, ensure_ascii=False)
        else:
            output_json = str(output)

        raw_size = len(input_json)
        output_size = len(output_json)

        return TestMetrics(
            input_records=len(input_data),
            output_chars=output_size,
            output_records=len(output) if isinstance(output, list) else 0,
            reduction_ratio=1 - (output_size / raw_size) if raw_size > 0 else 0,
        )

    return _measure


@pytest.fixture
def validate_html() -> Callable:
    """
    HTML 리포트 검증 유틸리티.

    Usage:
        errors = validate_html(html_content)
        assert not errors
    """
    def _validate(html: str) -> List[str]:
        errors = []

        # 필수 구조
        if "<!DOCTYPE html>" not in html:
            errors.append("Missing DOCTYPE")
        if '<html lang="ko">' not in html:
            errors.append("Missing Korean lang attribute")
        if '<meta charset="UTF-8">' not in html and 'charset="utf-8"' not in html.lower():
            errors.append("Missing UTF-8 charset")

        # Plotly CDN
        if "cdn.plot.ly/plotly" not in html and "plotly" not in html.lower():
            errors.append("Missing Plotly CDN")

        # 한글 폰트
        if "Noto Sans KR" not in html and "Pretendard" not in html:
            errors.append("Missing Korean font")

        # 컨텐츠 검증
        if "KOSIS" not in html and "통계청" not in html:
            errors.append("Missing data source attribution")

        return errors

    return _validate


@pytest.fixture
def validate_mcp_response() -> Callable:
    """
    MCP 응답 구조 검증 유틸리티.

    Usage:
        errors = validate_mcp_response(response)
        assert not errors
    """
    def _validate(response: Dict[str, Any]) -> List[str]:
        errors = []

        # summary 모드 필수 필드
        if "summary" in response:
            summary = response["summary"]
            for field in ["total_records", "period_range"]:
                if field not in summary:
                    errors.append(f"Missing summary.{field}")

        # metadata 필수 필드
        if "metadata" in response:
            metadata = response["metadata"]
            for field in ["tbl_id", "tbl_nm"]:
                if field not in metadata:
                    errors.append(f"Missing metadata.{field}")

        # data_availability 필수 필드
        if "data_availability" in response:
            avail = response["data_availability"]
            for field in ["sample_count", "note"]:
                if field not in avail:
                    errors.append(f"Missing data_availability.{field}")

        # 안티패턴 체크
        if "data" in response and isinstance(response["data"], list):
            if len(response["data"]) > MAX_SAMPLE_ROWS:
                errors.append(f"Antipattern: data has {len(response['data'])} rows (max {MAX_SAMPLE_ROWS})")

        return errors

    return _validate


# =============================================================================
# 마커 정의
# =============================================================================

def pytest_configure(config):
    """커스텀 마커 등록."""
    config.addinivalue_line("markers", "slow: 대용량 데이터 테스트 (시간 소요)")
    config.addinivalue_line("markers", "api: 실제 API 호출 테스트")
    config.addinivalue_line("markers", "report: 리포트 생성 테스트")
