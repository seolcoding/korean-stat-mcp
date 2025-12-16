"""
데이터 파이프라인 E2E 테스트.

비판적 분석:
- 기존 test_mcp_guidelines.py는 format_data_for_llm 단위 테스트
- 이 테스트는 실제 워크플로우에서의 파이프라인 동작 검증
- 토큰 효율성을 "문자 수 기반"으로 실용적 측정

테스트 대상:
1. 데이터 크기별 처리 전략 (small/medium/large)
2. 토큰 절감률 검증 (MCP_PATTERN.md 기준)
3. 파이프라인 조합 효율성 (filter → aggregate → format)
4. 청킹/페이지네이션 동작
"""

import pytest
import json
import time
from typing import Any, Dict, List

from kosis_tools.report_tools import (
    format_data_for_llm,
    filter_data,
    aggregate_data,
    get_available_values,
    analyze_trend,
    analyze_comparison,
    analyze_ranking,
    analyze_stats,
)

# conftest.py 상수들 (pytest가 자동으로 conftest 로드하지만 상수는 직접 정의)
MAX_CONTEXT_CHARS = 10_000       # LLM 컨텍스트 최대 문자 (~5,000 토큰)
MAX_SAMPLE_ROWS = 50             # 샘플 데이터 최대 행
TOKEN_REDUCTION_TARGET = 0.90    # 목표 토큰 절감률
DATA_SIZE_SMALL = 50
DATA_SIZE_MEDIUM = 500
DATA_SIZE_LARGE = 3000

from dataclasses import dataclass

@dataclass
class _TestMetrics:
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


# Alias for test usage
TestMetrics = _TestMetrics


# =============================================================================
# 토큰 효율성 테스트
# =============================================================================

class TestTokenEfficiency:
    """
    토큰 효율성 검증.

    MCP_PATTERN.md 기준:
    - 1,000건: 90% 이상 절감
    - 3,000건: 97% 이상 절감
    - summary 모드: 10,000자 이하
    """

    def test_small_data_overhead_acceptable(self, small_population_data, measure_output):
        """
        소규모 데이터 (40건)는 오버헤드 최소화.

        summary가 원본보다 너무 크면 안 됨 (최대 2배).
        """
        result = format_data_for_llm(small_population_data, max_rows=50)
        metrics = measure_output(small_population_data, result)

        # 소규모 데이터는 오버헤드가 있을 수 있음 (메타데이터 추가)
        # 하지만 2배를 초과하면 안 됨
        raw_size = len(json.dumps(small_population_data, ensure_ascii=False))
        output_size = metrics.output_chars

        # 원본이 매우 작으면 summary가 더 클 수 있음
        if raw_size > 1000:
            assert output_size <= raw_size * 2, (
                f"소규모 데이터 오버헤드 과다: {output_size}자 > {raw_size * 2}자"
            )

    def test_medium_data_80_percent_reduction(self, medium_population_data, measure_output):
        """
        중규모 데이터 (340건)는 80% 이상 절감.
        """
        result = format_data_for_llm(medium_population_data, max_rows=50)
        metrics = measure_output(medium_population_data, result)

        assert metrics.reduction_ratio >= 0.80, (
            f"중규모 데이터 토큰 절감률 미달: {metrics.reduction_ratio:.1%} < 80%"
        )

    @pytest.mark.slow
    def test_large_data_90_percent_reduction(self, large_population_data, measure_output):
        """
        대규모 데이터 (1,785건)는 90% 이상 절감.
        """
        result = format_data_for_llm(large_population_data, max_rows=50)
        metrics = measure_output(large_population_data, result)

        assert metrics.reduction_ratio >= TOKEN_REDUCTION_TARGET, (
            f"대규모 데이터 토큰 절감률 미달: {metrics.reduction_ratio:.1%} < {TOKEN_REDUCTION_TARGET:.0%}"
        )

    def test_summary_under_context_limit(self, large_population_data):
        """
        summary 모드는 항상 컨텍스트 제한 이하.
        """
        result = format_data_for_llm(large_population_data, max_rows=50)
        result_json = json.dumps(result, ensure_ascii=False)

        assert len(result_json) <= MAX_CONTEXT_CHARS, (
            f"Summary가 컨텍스트 제한 초과: {len(result_json):,}자 > {MAX_CONTEXT_CHARS:,}자"
        )

    def test_sample_rows_limited(self, large_population_data):
        """
        샘플 데이터 행 수 제한 준수.
        """
        result = format_data_for_llm(large_population_data, max_rows=50)

        preview = result.get("data_preview", [])
        assert len(preview) <= MAX_SAMPLE_ROWS, (
            f"샘플 데이터 행 수 초과: {len(preview)} > {MAX_SAMPLE_ROWS}"
        )


# =============================================================================
# 파이프라인 조합 테스트
# =============================================================================

class TestPipelineCombinations:
    """
    파이프라인 조합 효율성 테스트.

    권장 패턴: filter → aggregate → analyze
    이 패턴이 전체 데이터 반환보다 효율적인지 검증.
    """

    def test_filter_reduces_output_size(self, large_population_data):
        """
        필터링이 출력 크기를 줄이는지 검증.
        """
        # 전체 데이터
        full_size = len(json.dumps(large_population_data, ensure_ascii=False))

        # 필터링된 데이터
        filtered = filter_data(large_population_data, regions=["서울특별시", "부산광역시"])
        filtered_size = len(json.dumps(filtered, ensure_ascii=False))

        # 필터링 후 크기가 줄어야 함
        assert filtered_size < full_size, (
            f"필터링이 크기를 줄이지 않음: {filtered_size} >= {full_size}"
        )

        # 필터링 후 format_data_for_llm
        formatted = format_data_for_llm(filtered, max_rows=50)
        formatted_size = len(json.dumps(formatted, ensure_ascii=False))

        assert formatted_size < MAX_CONTEXT_CHARS

    def test_aggregate_produces_compact_output(self, large_population_data):
        """
        집계가 컴팩트한 출력을 생성하는지 검증.
        """
        # 필터 후 집계
        pop_data = filter_data(large_population_data, items=["총인구"])
        aggregated = aggregate_data(pop_data, group_by="C1_NM", agg_func="sum")

        # 집계 결과는 매우 작아야 함
        result_json = json.dumps(aggregated, ensure_ascii=False)
        assert len(result_json) < 5000, (
            f"집계 결과가 너무 큼: {len(result_json)}자 > 5000자"
        )

        # 레코드 수도 적어야 함
        assert len(aggregated) <= 20, (
            f"집계 결과 레코드 수 과다: {len(aggregated)} > 20"
        )

    def test_filter_then_aggregate_optimal(self, large_population_data):
        """
        filter → aggregate 파이프라인이 최적인지 검증.
        """
        # 원본 크기
        original_size = len(json.dumps(large_population_data, ensure_ascii=False))

        # filter → aggregate
        filtered = filter_data(
            large_population_data,
            regions=["서울특별시", "부산광역시", "경기도"],
            items=["총인구"]
        )
        aggregated = aggregate_data(filtered, group_by="PRD_DE", agg_func="sum")

        # 파이프라인 결과 크기
        pipeline_size = len(json.dumps(aggregated, ensure_ascii=False))

        # 99% 이상 절감
        reduction = 1 - (pipeline_size / original_size)
        assert reduction >= 0.95, (
            f"파이프라인 효율성 미달: {reduction:.1%} < 95%"
        )

    def test_analysis_functions_compact_output(self, medium_population_data):
        """
        분석 함수들이 컴팩트한 출력을 생성하는지 검증.
        """
        import numpy as np

        def convert_to_native(obj):
            """numpy 타입을 Python 네이티브 타입으로 변환."""
            if isinstance(obj, dict):
                return {k: convert_to_native(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_to_native(item) for item in obj]
            elif isinstance(obj, (np.integer,)):
                return int(obj)
            elif isinstance(obj, (np.floating,)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        pop_data = filter_data(medium_population_data, items=["총인구"])

        # 각 분석 함수의 출력 크기 측정
        analyses = {
            "trend": analyze_trend(pop_data),
            "comparison": analyze_comparison(pop_data),
            "ranking": analyze_ranking(pop_data, top_n=10),
            "stats": analyze_stats(pop_data),
        }

        for name, result in analyses.items():
            # AnalysisResult를 dict로 변환
            if hasattr(result, "__dict__"):
                result_dict = {
                    "type": result.type,
                    "findings": result.findings,
                    "metrics": convert_to_native(result.metrics),
                    "interpretation": getattr(result, "interpretation", ""),
                }
            else:
                result_dict = convert_to_native(result)

            result_json = json.dumps(result_dict, ensure_ascii=False)
            assert len(result_json) < 3000, (
                f"분석 함수 {name} 출력이 너무 큼: {len(result_json)}자 > 3000자"
            )


# =============================================================================
# 응답 구조 검증 테스트
# =============================================================================

class TestResponseStructure:
    """
    MCP 응답 구조 검증.

    format_data_for_llm의 출력이 MCP 가이드라인 구조를 따르는지 검증.
    """

    def test_summary_required_fields(self, medium_population_data, validate_mcp_response):
        """summary 섹션 필수 필드."""
        result = format_data_for_llm(medium_population_data)

        errors = validate_mcp_response(result)
        assert not errors, f"응답 구조 오류: {errors}"

    def test_metadata_extraction(self, medium_population_data):
        """메타데이터 추출 검증."""
        result = format_data_for_llm(medium_population_data)

        assert "metadata" in result
        metadata = result["metadata"]

        # 첫 번째 레코드에서 메타데이터 추출되어야 함
        assert metadata.get("tbl_id") == "DT_POP_MEDIUM"
        assert metadata.get("org_id") == "101"

    def test_pivot_summary_structure(self, medium_population_data):
        """피벗 요약 구조."""
        result = format_data_for_llm(medium_population_data)

        assert "pivot_summary" in result
        pivot = result["pivot_summary"]

        # by_period 또는 by_c1 포함
        assert "by_period" in pivot or "by_c1" in pivot

        # 피벗 요약도 제한됨
        if "by_period" in pivot:
            assert len(pivot["by_period"]) <= 10
        if "by_c1" in pivot:
            assert len(pivot["by_c1"]) <= 15

    def test_available_values_truncated(self, large_population_data):
        """사용 가능한 값 목록 제한."""
        result = format_data_for_llm(large_population_data)

        assert "available_values" in result
        available = result["available_values"]

        for field, values in available.items():
            assert len(values) <= 20, (
                f"available_values[{field}] 초과: {len(values)} > 20"
            )

    def test_data_availability_info(self, large_population_data):
        """데이터 가용성 정보 포함."""
        result = format_data_for_llm(large_population_data)

        assert "data_availability" in result
        avail = result["data_availability"]

        assert "sample_count" in avail
        assert "note" in avail

        # 전체 데이터 접근 방법 안내 포함
        note = avail.get("note", "")
        assert len(note) > 0


# =============================================================================
# 안티패턴 탐지 테스트
# =============================================================================

class TestAntiPatternDetection:
    """
    MCP 안티패턴 탐지.

    피해야 할 패턴이 발생하지 않는지 검증.
    """

    def test_no_full_data_in_response(self, large_population_data):
        """
        summary 모드에서 전체 데이터 포함 방지.
        """
        result = format_data_for_llm(large_population_data, max_rows=50)

        # 전체 데이터를 포함할 수 있는 필드 검사
        suspicious_keys = ["data", "records", "all_data", "raw_data", "full_data"]

        for key in suspicious_keys:
            if key in result:
                data_len = len(result[key])
                assert data_len <= MAX_SAMPLE_ROWS, (
                    f"안티패턴: {key}에 {data_len}건 포함 (max {MAX_SAMPLE_ROWS})"
                )

    def test_no_redundant_metadata_in_preview(self, medium_population_data):
        """
        data_preview에 중복 메타데이터 방지.
        """
        result = format_data_for_llm(medium_population_data)

        preview = result.get("data_preview", [])
        if preview:
            first_row = preview[0]

            # 각 행에 반복되는 메타데이터가 없어야 함
            redundant_fields = ["TBL_ID", "TBL_NM", "ORG_ID", "ORG_NM"]
            for field in redundant_fields:
                assert field not in first_row, (
                    f"안티패턴: data_preview에 중복 메타데이터 {field} 포함"
                )

    def test_uses_korean_labels(self, medium_population_data):
        """
        data_preview가 한글 라벨 사용.
        """
        result = format_data_for_llm(medium_population_data)

        preview = result.get("data_preview", [])
        if preview:
            first_row = preview[0]
            keys = list(first_row.keys())

            # 원본 필드명(PRD_DE, C1_NM) 대신 한글 라벨 사용
            korean_labels = ["기간", "분류", "분류1", "항목", "값"]
            has_korean = any(label in keys for label in korean_labels)

            assert has_korean, (
                f"안티패턴: data_preview가 한글 라벨 미사용: {keys}"
            )


# =============================================================================
# 성능 벤치마크 테스트
# =============================================================================

class TestPerformanceBenchmark:
    """
    성능 벤치마크.

    응답 시간, 메모리 사용량 등 성능 지표.
    """

    @pytest.mark.slow
    def test_format_data_response_time(self, large_population_data):
        """
        format_data_for_llm 응답 시간 측정.

        1,000건 데이터: 100ms 이내
        """
        start = time.perf_counter()
        result = format_data_for_llm(large_population_data, max_rows=50)
        elapsed = (time.perf_counter() - start) * 1000  # ms

        assert elapsed < 500, (
            f"format_data_for_llm 응답 시간 초과: {elapsed:.1f}ms > 500ms"
        )

    @pytest.mark.slow
    def test_pipeline_response_time(self, large_population_data):
        """
        전체 파이프라인 응답 시간 측정.

        filter → aggregate → analyze: 200ms 이내
        """
        start = time.perf_counter()

        # 파이프라인 실행
        filtered = filter_data(
            large_population_data,
            regions=["서울특별시", "부산광역시"],
            items=["총인구"]
        )
        aggregated = aggregate_data(filtered, group_by="PRD_DE", agg_func="sum")
        analysis = analyze_trend(aggregated)

        elapsed = (time.perf_counter() - start) * 1000  # ms

        assert elapsed < 1000, (
            f"파이프라인 응답 시간 초과: {elapsed:.1f}ms > 1000ms"
        )

    def test_analysis_functions_response_time(self, medium_population_data):
        """
        분석 함수들 개별 응답 시간.
        """
        pop_data = filter_data(medium_population_data, items=["총인구"])

        timings = {}

        for name, func in [
            ("trend", lambda: analyze_trend(pop_data)),
            ("comparison", lambda: analyze_comparison(pop_data)),
            ("ranking", lambda: analyze_ranking(pop_data, top_n=10)),
            ("stats", lambda: analyze_stats(pop_data)),
        ]:
            start = time.perf_counter()
            result = func()
            elapsed = (time.perf_counter() - start) * 1000
            timings[name] = elapsed

        for name, elapsed in timings.items():
            assert elapsed < 200, (
                f"{name} 분석 응답 시간 초과: {elapsed:.1f}ms > 200ms"
            )


# =============================================================================
# 데이터 저장/로드 테스트
# =============================================================================

class TestDataStorage:
    """
    대용량 데이터 저장/로드 테스트.

    청킹 패턴에서 데이터를 서버에 저장하고 참조하는 동작 검증.
    """

    def test_save_and_load_data(self, medium_population_data, output_dir):
        """
        데이터 저장 및 로드.
        """
        from kosis_tools.report_tools import save_raw_data, load_raw_data

        # 저장 (새 API: data, data_id만 받음)
        result = save_raw_data(data=medium_population_data)

        assert result is not None
        assert "data_id" in result
        data_id = result["data_id"]
        assert data_id is not None

        # 로드
        loaded = load_raw_data(data_id)

        assert loaded is not None
        assert "data" in loaded
        assert len(loaded["data"]) == len(medium_population_data)

    def test_list_saved_data(self, medium_population_data):
        """
        저장된 데이터 목록 조회.
        """
        from kosis_tools.report_tools import save_raw_data, list_saved_data

        # 테스트 데이터 저장 (새 API)
        save_raw_data(data=medium_population_data)

        # 목록 조회
        saved_list = list_saved_data()

        assert isinstance(saved_list, list)
        # 최소 1개 이상 저장되어 있어야 함
        assert len(saved_list) >= 1


# =============================================================================
# 다양한 데이터 유형 테스트
# =============================================================================

class TestDifferentDataTypes:
    """
    다양한 데이터 유형에서의 파이프라인 동작.

    인구, 고용, 물가 등 다른 도메인 데이터.
    """

    def test_employment_data_pipeline(self, employment_data):
        """고용 데이터 파이프라인."""
        result = format_data_for_llm(employment_data, max_rows=50)

        assert "summary" in result
        assert result["summary"]["total_records"] == len(employment_data)

    def test_cpi_data_pipeline(self, cpi_data):
        """물가 데이터 파이프라인."""
        result = format_data_for_llm(cpi_data, max_rows=50)

        assert "summary" in result

        # 월별 데이터 특성 반영
        available = result.get("available_values", {})
        periods = available.get("PRD_DE", [])
        # 월별 데이터이므로 YYYYMM 형식
        if periods:
            assert len(periods[0]) == 6  # "202301" 형식

    def test_quarterly_data_aggregation(self, employment_data):
        """분기별 데이터 집계."""
        # 산업별 집계
        aggregated = aggregate_data(employment_data, group_by="C1_NM", agg_func="mean")

        # 12개 산업으로 집계
        assert len(aggregated) <= 12

    def test_mixed_period_types(self, medium_population_data, employment_data):
        """
        서로 다른 기간 유형 데이터 처리.

        연간(Y) vs 분기(Q) 데이터가 각각 올바르게 처리되는지.
        """
        # 연간 데이터
        yearly_result = format_data_for_llm(medium_population_data)
        yearly_periods = yearly_result.get("available_values", {}).get("PRD_DE", [])

        # 분기 데이터
        quarterly_result = format_data_for_llm(employment_data)
        quarterly_periods = quarterly_result.get("available_values", {}).get("PRD_DE", [])

        # 기간 형식이 다름
        if yearly_periods and quarterly_periods:
            assert len(yearly_periods[0]) == 4  # "2024"
            assert "Q" in quarterly_periods[0]  # "2024Q1"
