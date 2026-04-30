"""
MCP 가이드라인 준수 테스트.

MCP_PATTERN.md에 정의된 대용량 데이터 처리 패턴을 준수하는지 검증합니다.

테스트 범위:
    - 응답 길이 제한: summary 모드가 컴팩트한지 확인
    - 응답 구조 검증: summary, next_step 등 필수 필드 확인
    - 안티패턴 탐지: format="summary"에서 전체 데이터 덤프 방지
    - 토큰 효율성: 대용량 데이터에서 90%+ 토큰 절감 확인

참조:
    - MCP_PATTERN.md: 대용량 데이터 처리 패턴 문서
    - server.py: MCP 서버 도구 구현
"""

import json
import pytest
from typing import Any, Dict, List

from kosis_tools.report_tools import (
    format_data_for_llm,
    filter_data,
    aggregate_data,
)


# =============================================================================
# 상수 정의
# =============================================================================

# 토큰 추정: 한글 1자 ≈ 2토큰, 영어/숫자 1자 ≈ 0.25토큰
# JSON 구조 오버헤드 포함하여 문자 수 × 0.5 ≈ 토큰 수로 대략 추정
MAX_SUMMARY_CHARS = 10_000  # summary 모드 최대 문자 수 (~5,000 토큰)
MAX_SAMPLE_ROWS = 50  # 샘플 데이터 최대 행 수
TOKEN_REDUCTION_TARGET = 0.90  # 목표 토큰 절감률 (90%+)


# =============================================================================
# 테스트 데이터 Fixtures
# =============================================================================


@pytest.fixture
def large_dataset() -> List[Dict[str, Any]]:
    """
    대용량 데이터셋 (1,000건).

    실제 KOSIS API 응답과 유사한 구조.
    """
    data = []
    regions = [
        "서울특별시",
        "부산광역시",
        "대구광역시",
        "인천광역시",
        "광주광역시",
        "대전광역시",
        "울산광역시",
        "세종특별자치시",
        "경기도",
        "강원특별자치도",
        "충청북도",
        "충청남도",
        "전라북도",
        "전라남도",
        "경상북도",
        "경상남도",
        "제주특별자치도",
    ]
    years = [str(y) for y in range(2010, 2024)]  # 14년
    items = ["인구수", "세대수", "인구밀도", "면적"]

    for year in years:
        for region in regions:
            for item in items:
                data.append(
                    {
                        "TBL_ID": "DT_TEST001",
                        "TBL_NM": "테스트 통계표",
                        "ORG_ID": "101",
                        "ORG_NM": "통계청",
                        "PRD_DE": year,
                        "PRD_SE": "Y",
                        "C1_NM": region,
                        "C1": f"R{regions.index(region):02d}",
                        "ITM_NM": item,
                        "ITM_ID": f"I{items.index(item):02d}",
                        "DT": str(1000000 + hash((year, region, item)) % 9000000),
                        "UNIT_NM": "명" if item == "인구수" else "개",
                    }
                )

    return data  # 17지역 × 14년 × 4항목 = 952건


@pytest.fixture
def small_dataset() -> List[Dict[str, Any]]:
    """소규모 데이터셋 (16건)."""
    data = []
    regions = ["서울특별시", "부산광역시", "대구광역시", "인천광역시"]
    years = ["2020", "2021", "2022", "2023"]

    for year in years:
        for region in regions:
            data.append(
                {
                    "TBL_ID": "DT_TEST002",
                    "TBL_NM": "소규모 테스트",
                    "ORG_ID": "101",
                    "ORG_NM": "통계청",
                    "PRD_DE": year,
                    "C1_NM": region,
                    "ITM_NM": "인구수",
                    "DT": str(5000000 + hash((year, region)) % 5000000),
                    "UNIT_NM": "명",
                }
            )

    return data


@pytest.fixture
def medium_dataset() -> List[Dict[str, Any]]:
    """중간 규모 데이터셋 (200건)."""
    data = []
    regions = ["서울", "부산", "대구", "인천", "광주"]
    years = [str(y) for y in range(2014, 2024)]  # 10년
    items = ["값A", "값B", "값C", "값D"]

    for year in years:
        for region in regions:
            for item in items:
                data.append(
                    {
                        "TBL_ID": "DT_TEST003",
                        "TBL_NM": "중간 규모 테스트",
                        "ORG_ID": "101",
                        "ORG_NM": "통계청",
                        "PRD_DE": year,
                        "C1_NM": region,
                        "ITM_NM": item,
                        "DT": str(100 + hash((year, region, item)) % 900),
                        "UNIT_NM": "단위",
                    }
                )

    return data  # 5지역 × 10년 × 4항목 = 200건


# =============================================================================
# 응답 길이 테스트
# =============================================================================


class TestResponseLength:
    """응답 길이 제한 테스트."""

    def test_summary_mode_compact(self, large_dataset):
        """
        summary 모드가 컴팩트한지 확인.

        1,000건 데이터도 summary 모드에서는 MAX_SUMMARY_CHARS 이하여야 함.
        """
        result = format_data_for_llm(large_dataset, max_rows=50)
        result_json = json.dumps(result, ensure_ascii=False)

        assert len(result_json) < MAX_SUMMARY_CHARS, (
            f"Summary 응답이 너무 큼: {len(result_json):,}자 > {MAX_SUMMARY_CHARS:,}자 제한"
        )

    def test_sample_rows_limited(self, large_dataset):
        """
        샘플 데이터 행 수 제한 확인.

        data_preview는 max_rows 이하여야 함.
        """
        result = format_data_for_llm(large_dataset, max_rows=50)

        preview = result.get("data_preview", [])
        assert len(preview) <= MAX_SAMPLE_ROWS, (
            f"샘플 데이터가 너무 많음: {len(preview)}행 > {MAX_SAMPLE_ROWS}행 제한"
        )

    def test_available_values_truncated(self, large_dataset):
        """
        사용 가능한 값 목록 제한 확인.

        각 필드별로 20개까지만 반환해야 함.
        """
        result = format_data_for_llm(large_dataset)

        available = result.get("available_values", {})
        for field, values in available.items():
            assert len(values) <= 20, (
                f"available_values[{field}]가 너무 많음: {len(values)}개 > 20개 제한"
            )

    def test_pivot_summary_limited(self, large_dataset):
        """
        피벗 요약 제한 확인.

        by_period는 최근 5개, by_c1은 상위 10개로 제한.
        """
        result = format_data_for_llm(large_dataset)

        pivot = result.get("pivot_summary", {})

        by_period = pivot.get("by_period", {})
        assert len(by_period) <= 5, (
            f"by_period가 너무 많음: {len(by_period)}개 > 5개 제한"
        )

        by_c1 = pivot.get("by_c1", {})
        assert len(by_c1) <= 10, f"by_c1이 너무 많음: {len(by_c1)}개 > 10개 제한"


# =============================================================================
# 토큰 효율성 테스트
# =============================================================================


class TestTokenEfficiency:
    """토큰 효율성 테스트."""

    def test_token_reduction_90_percent(self, large_dataset):
        """
        90% 이상 토큰 절감 확인.

        raw 데이터 대비 summary 모드가 90% 이상 작아야 함.
        """
        # Raw 데이터 크기
        raw_json = json.dumps(large_dataset, ensure_ascii=False)
        raw_size = len(raw_json)

        # Summary 데이터 크기
        summary = format_data_for_llm(large_dataset, max_rows=50)
        summary_json = json.dumps(summary, ensure_ascii=False)
        summary_size = len(summary_json)

        # 절감률 계산
        reduction = 1 - (summary_size / raw_size)

        assert reduction >= TOKEN_REDUCTION_TARGET, (
            f"토큰 절감률 미달: {reduction:.1%} < {TOKEN_REDUCTION_TARGET:.0%} 목표\n"
            f"Raw: {raw_size:,}자, Summary: {summary_size:,}자"
        )

    def test_medium_data_efficiency(self, medium_dataset):
        """
        중간 규모 데이터에서도 효율적인지 확인.

        200건 데이터도 80% 이상 절감.
        """
        raw_json = json.dumps(medium_dataset, ensure_ascii=False)
        raw_size = len(raw_json)

        summary = format_data_for_llm(medium_dataset, max_rows=50)
        summary_json = json.dumps(summary, ensure_ascii=False)
        summary_size = len(summary_json)

        reduction = 1 - (summary_size / raw_size)

        assert reduction >= 0.80, (
            f"중간 규모 데이터 절감률 미달: {reduction:.1%} < 80%\n"
            f"Raw: {raw_size:,}자, Summary: {summary_size:,}자"
        )

    def test_small_data_reasonable(self, small_dataset):
        """
        소규모 데이터는 오버헤드 없이 처리.

        16건 데이터는 summary가 raw보다 커질 수 있지만
        메타데이터 오버헤드는 합리적이어야 함.
        """
        raw_json = json.dumps(small_dataset, ensure_ascii=False)
        raw_size = len(raw_json)

        summary = format_data_for_llm(small_dataset, max_rows=50)
        summary_json = json.dumps(summary, ensure_ascii=False)
        summary_size = len(summary_json)

        # 소규모 데이터는 2배 이하의 오버헤드만 허용
        assert summary_size <= raw_size * 2, (
            f"소규모 데이터 오버헤드 과다: {summary_size:,}자 > {raw_size * 2:,}자"
        )


# =============================================================================
# 응답 구조 테스트
# =============================================================================


class TestResponseStructure:
    """응답 구조 검증 테스트."""

    def test_summary_required_fields(self, large_dataset):
        """
        summary 섹션 필수 필드 확인.
        """
        result = format_data_for_llm(large_dataset)

        assert "summary" in result, "summary 필드 누락"
        summary = result["summary"]

        required_fields = ["total_records", "period_range", "dimensions", "items"]
        for field in required_fields:
            assert field in summary, f"summary.{field} 필드 누락"

    def test_metadata_required_fields(self, large_dataset):
        """
        metadata 섹션 필수 필드 확인.
        """
        result = format_data_for_llm(large_dataset)

        assert "metadata" in result, "metadata 필드 누락"
        metadata = result["metadata"]

        required_fields = ["tbl_id", "tbl_nm", "org_id", "org_nm"]
        for field in required_fields:
            assert field in metadata, f"metadata.{field} 필드 누락"

    def test_data_availability_info(self, large_dataset):
        """
        데이터 가용성 정보 확인.

        전체 데이터가 있음을 알리는 정보 포함.
        """
        result = format_data_for_llm(large_dataset)

        assert "data_availability" in result, "data_availability 필드 누락"
        availability = result["data_availability"]

        assert "full_data_available" in availability
        assert "sample_count" in availability
        assert "note" in availability

    def test_pivot_summary_structure(self, large_dataset):
        """
        피벗 요약 구조 확인.
        """
        result = format_data_for_llm(large_dataset)

        assert "pivot_summary" in result, "pivot_summary 필드 누락"
        pivot = result["pivot_summary"]

        # 기간별 또는 분류별 요약 중 하나는 있어야 함
        assert "by_period" in pivot or "by_c1" in pivot, (
            "pivot_summary에 by_period 또는 by_c1 누락"
        )

    def test_available_values_structure(self, large_dataset):
        """
        사용 가능한 값 구조 확인.
        """
        result = format_data_for_llm(large_dataset)

        assert "available_values" in result, "available_values 필드 누락"
        available = result["available_values"]

        # 주요 필드가 포함되어야 함
        assert any(
            k.startswith("PRD") or k.startswith("C") for k in available.keys()
        ), "available_values에 기간 또는 분류 필드 누락"


# =============================================================================
# 안티패턴 탐지 테스트
# =============================================================================


class TestAntiPatternDetection:
    """안티패턴 탐지 테스트."""

    def test_no_full_data_in_summary(self, large_dataset):
        """
        summary 모드에서 전체 데이터 포함 방지.

        data 또는 records 필드에 전체 원본 데이터가 들어가면 안 됨.
        """
        result = format_data_for_llm(large_dataset, max_rows=50)

        # 전체 데이터가 포함된 필드 확인
        forbidden_full_data_keys = ["data", "records", "all_data", "raw_data"]
        for key in forbidden_full_data_keys:
            if key in result:
                data_len = len(result[key])
                assert data_len <= MAX_SAMPLE_ROWS, (
                    f"{key} 필드에 전체 데이터({data_len}건) 포함 - 안티패턴!"
                )

    def test_no_redundant_metadata(self, large_dataset):
        """
        중복 메타데이터 방지.

        각 레코드에 반복되는 TBL_NM, ORG_NM 등이 data_preview에 없어야 함.
        """
        result = format_data_for_llm(large_dataset)

        preview = result.get("data_preview", [])
        if preview:
            first_row = preview[0]
            # 메타데이터 필드가 각 행에 반복되면 안 됨
            redundant_fields = ["TBL_ID", "TBL_NM", "ORG_ID", "ORG_NM"]
            for field in redundant_fields:
                assert field not in first_row, (
                    f"data_preview에 중복 메타데이터 {field} 포함 - 안티패턴!"
                )

    def test_preview_uses_korean_labels(self, large_dataset):
        """
        data_preview가 한글 라벨 사용.

        PRD_DE → 기간, C1_NM → 분류1 등으로 변환되어야 함.
        """
        result = format_data_for_llm(large_dataset)

        preview = result.get("data_preview", [])
        if preview:
            first_row = preview[0]
            # 원본 필드명이 아닌 한글 라벨 사용
            korean_labels = ["기간", "분류1", "분류2", "항목", "값"]
            has_korean = any(label in first_row for label in korean_labels)
            assert has_korean, (
                f"data_preview가 한글 라벨 미사용: {list(first_row.keys())}"
            )


# =============================================================================
# 샘플 데이터 품질 테스트
# =============================================================================


class TestSampleDataQuality:
    """샘플 데이터 품질 테스트."""

    def test_sample_is_latest_period(self, large_dataset):
        """
        샘플 데이터가 가장 최근 기간인지 확인.
        """
        result = format_data_for_llm(large_dataset)

        preview = result.get("data_preview", [])
        availability = result.get("data_availability", {})

        if preview:
            sample_period = availability.get("sample_period")
            # 최근 기간(2023)이어야 함
            assert sample_period == "2023", (
                f"샘플이 최근 기간이 아님: {sample_period} (기대: 2023)"
            )

    def test_sample_representative(self, large_dataset):
        """
        샘플 데이터가 대표성을 갖는지 확인.

        여러 분류(지역)의 데이터가 포함되어야 함.
        """
        result = format_data_for_llm(large_dataset)

        preview = result.get("data_preview", [])
        if preview:
            # 분류1 (C1_NM → 분류1) 값 수집
            categories = set()
            for row in preview:
                cat = row.get("분류1") or row.get("C1_NM")
                if cat:
                    categories.add(cat)

            # 최소 2개 이상의 분류가 포함되어야 함
            assert len(categories) >= 2, (
                f"샘플 데이터 대표성 부족: {len(categories)}개 분류만 포함"
            )


# =============================================================================
# 엣지 케이스 테스트
# =============================================================================


class TestEdgeCases:
    """엣지 케이스 테스트."""

    def test_empty_data(self):
        """빈 데이터 처리."""
        result = format_data_for_llm([])

        assert "error" in result or result.get("total_records") == 0
        assert (
            result.get("summary", {}).get("total_records", -1) == 0 or "error" in result
        )

    def test_single_record(self):
        """단일 레코드 처리."""
        single = [
            {
                "TBL_ID": "TEST",
                "TBL_NM": "테스트",
                "ORG_ID": "101",
                "ORG_NM": "통계청",
                "PRD_DE": "2023",
                "C1_NM": "서울",
                "ITM_NM": "값",
                "DT": "1000",
                "UNIT_NM": "단위",
            }
        ]

        result = format_data_for_llm(single)

        assert result.get("summary", {}).get("total_records") == 1
        assert "metadata" in result

    def test_missing_fields(self):
        """필드 누락 데이터 처리."""
        incomplete = [
            {"PRD_DE": "2023", "DT": "100"},
            {"PRD_DE": "2022", "DT": "90"},
        ]

        result = format_data_for_llm(incomplete)

        # 에러 없이 처리되어야 함
        assert "summary" in result

    def test_non_numeric_values(self):
        """비숫자 값 처리."""
        text_values = [
            {
                "TBL_ID": "TEST",
                "TBL_NM": "테스트",
                "ORG_ID": "101",
                "ORG_NM": "통계청",
                "PRD_DE": "2023",
                "C1_NM": "서울",
                "ITM_NM": "상태",
                "DT": "양호",  # 비숫자
                "UNIT_NM": "-",
            }
        ]

        result = format_data_for_llm(text_values)

        # 에러 없이 처리되어야 함
        assert "summary" in result


# =============================================================================
# MCP 서버 응답 시뮬레이션 테스트
# =============================================================================


class TestMCPServerResponse:
    """MCP 서버 응답 형식 테스트."""

    def test_response_is_json_serializable(self, large_dataset):
        """
        응답이 JSON 직렬화 가능한지 확인.
        """
        result = format_data_for_llm(large_dataset)

        try:
            json_str = json.dumps(result, ensure_ascii=False)
            json.loads(json_str)  # 재파싱 가능해야 함
        except (TypeError, ValueError) as e:
            pytest.fail(f"JSON 직렬화 실패: {e}")

    def test_response_has_actionable_info(self, large_dataset):
        """
        응답에 다음 단계 정보가 있는지 확인.

        summary 모드는 다음 행동을 안내해야 함.
        """
        result = format_data_for_llm(large_dataset)

        availability = result.get("data_availability", {})

        # note 필드에 다음 행동 안내가 있어야 함
        note = availability.get("note", "")
        assert note, "data_availability.note가 비어 있음"

        # 샘플 제공 안내 포함
        assert "샘플" in note or "전체" in note, (
            f"data_availability.note에 샘플/전체 안내 없음: {note}"
        )

    def test_summary_counts_accurate(self, large_dataset):
        """
        요약 정보의 카운트가 정확한지 확인.
        """
        result = format_data_for_llm(large_dataset)

        summary = result.get("summary", {})
        total = summary.get("total_records", 0)

        assert total == len(large_dataset), (
            f"total_records 불일치: {total} != {len(large_dataset)}"
        )

    def test_period_range_format(self, large_dataset):
        """
        기간 범위 형식 확인.
        """
        result = format_data_for_llm(large_dataset)

        summary = result.get("summary", {})
        period_range = summary.get("period_range", "")

        # "시작~종료" 형식이어야 함
        assert "~" in period_range or period_range.isdigit(), (
            f"period_range 형식 이상: {period_range}"
        )


# =============================================================================
# filter_data, aggregate_data 가이드라인 테스트
# =============================================================================


class TestDataProcessingGuidelines:
    """데이터 처리 함수 가이드라인 테스트."""

    def test_filter_preserves_structure(self, large_dataset):
        """
        filter_data가 데이터 구조를 유지하는지 확인.
        """
        filtered = filter_data(large_dataset, regions=["서울특별시"])

        assert isinstance(filtered, list)
        if filtered:
            # 원본과 동일한 필드 구조
            original_keys = set(large_dataset[0].keys())
            filtered_keys = set(filtered[0].keys())
            assert original_keys == filtered_keys

    def test_aggregate_produces_summary(self, large_dataset):
        """
        aggregate_data가 요약 데이터를 생성하는지 확인.
        """
        aggregated = aggregate_data(large_dataset, group_by="C1_NM", agg_func="sum")

        # 집계 결과는 원본보다 적어야 함
        assert len(aggregated) < len(large_dataset), (
            f"집계 결과({len(aggregated)})가 원본({len(large_dataset)})보다 작지 않음"
        )

    def test_combined_processing_efficient(self, large_dataset):
        """
        filter + aggregate 조합이 효율적인지 확인.
        """
        # 필터링 후 집계
        filtered = filter_data(large_dataset, regions=["서울특별시", "부산광역시"])
        aggregated = aggregate_data(filtered, group_by="PRD_DE", agg_func="sum")

        # 최종 결과가 매우 컴팩트해야 함
        assert len(aggregated) <= 20, (
            f"filter+aggregate 결과가 너무 큼: {len(aggregated)}건"
        )

        # JSON 크기도 작아야 함
        result_json = json.dumps(aggregated, ensure_ascii=False)
        assert len(result_json) < 5000, (
            f"filter+aggregate JSON이 너무 큼: {len(result_json)}자"
        )
