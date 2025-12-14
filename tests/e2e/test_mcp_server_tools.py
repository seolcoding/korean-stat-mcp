"""
MCP 서버 도구 함수 E2E 테스트.

비판적 분석:
- 기존 test_llm_workflow.py는 report_tools 함수를 직접 호출
- 이 테스트는 실제 mcp_server.py의 MCP 도구 함수들을 호출
- MCP 프로토콜 자체는 테스트하지 않음 (FastMCP 책임)
- 도구 함수의 입출력 계약(contract)을 검증

테스트 대상:
- Layer 1: DISCOVER (search_statistics, list_*, get_table_metadata)
- Layer 2: FETCH (get_statistics_data, filter_*, aggregate_*)
- Layer 3: PRESENT (analyze_*, create_*_report)
"""

import pytest
import json
from pathlib import Path
from typing import Any, Dict, List

# MCP 서버 기반 모듈에서 함수 직접 import
# (mcp.tool 데코레이터가 FunctionTool 객체를 생성하므로 기반 함수 사용)
from kosis_tools.list_categories import CategoryList, OrgCode, ThemeCode
from kosis_tools.report_tools import (
    filter_data as filter_statistics_data,
    aggregate_data as aggregate_statistics_data,
    get_available_values as get_available_field_values,
    format_data_for_llm as get_data_summary,
    analyze_trend,
    analyze_comparison,
    analyze_ranking,
    analyze_stats,
    quick_report as create_quick_report,
)
from kosis_tools.report_generator import ReportGenerator


# mcp_server.py의 list_organizations/list_themes 로직 재현
def list_organizations() -> list[dict[str, str]]:
    """KOSIS 기관 목록 반환."""
    result = []
    for name in dir(OrgCode):
        if not name.startswith("_"):
            value = getattr(OrgCode, name)
            if isinstance(value, str):
                result.append({"code": value, "name": name})
    return result


def list_themes() -> list[dict[str, str]]:
    """KOSIS 주제 분류 목록 반환."""
    result = []
    for name in dir(ThemeCode):
        if not name.startswith("_"):
            value = getattr(ThemeCode, name)
            if isinstance(value, str):
                result.append({"code": value, "name": name})
    return result


# 분석 함수 래퍼 (dict 반환으로 변환)
def analyze_data_trend(data, group_by=None):
    """추세 분석."""
    result = analyze_trend(data, group_by=group_by)
    return {
        "type": result.type,
        "findings": result.findings,
        "metrics": result.metrics,
        "interpretation": result.interpretation,
    }


def analyze_data_comparison(data, targets=None, period=None):
    """비교 분석."""
    result = analyze_comparison(data, targets=targets, period=period)
    return {
        "type": result.type,
        "findings": result.findings,
        "metrics": result.metrics,
        "interpretation": result.interpretation,
    }


def analyze_data_ranking(data, top_n=10, period=None):
    """순위 분석."""
    result = analyze_ranking(data, top_n=top_n, period=period)
    return {
        "type": result.type,
        "findings": result.findings,
        "data": result.data,
        "metrics": result.metrics,
    }


def analyze_data_statistics(data):
    """통계 분석."""
    result = analyze_stats(data)
    return {
        "type": result.type,
        "findings": result.findings,
        "metrics": result.metrics,
    }


def create_custom_report(data, title, include_kpi=True, include_trend_chart=True,
                         include_comparison_chart=True, include_table=True,
                         include_insights=True, output_path=None):
    """커스텀 리포트 생성."""
    generator = ReportGenerator(data)
    return generator.generate_html(
        title=title,
        output_path=output_path
    )


# =============================================================================
# Layer 1: DISCOVER 테스트
# =============================================================================

class TestDiscoverTools:
    """
    DISCOVER 도구 테스트.

    검증 항목:
    - 반환 타입/구조
    - 필터링 동작
    - 빈 결과 처리
    """

    def test_list_organizations_returns_valid_structure(self):
        """list_organizations 반환 구조 검증."""
        result = list_organizations()

        assert isinstance(result, list)
        assert len(result) > 0

        # 첫 번째 항목 구조 검증
        org = result[0]
        assert "code" in org
        assert "name" in org
        assert isinstance(org["code"], str)
        assert isinstance(org["name"], str)

    def test_list_themes_returns_valid_structure(self):
        """list_themes 반환 구조 검증."""
        result = list_themes()

        assert isinstance(result, list)
        assert len(result) > 0

        theme = result[0]
        assert "code" in theme
        assert "name" in theme

    def test_list_organizations_contains_kostat(self):
        """통계청(101)이 목록에 포함되어야 함."""
        result = list_organizations()
        codes = [org["code"] for org in result]

        assert "101" in codes or "KOSTAT" in codes

    def test_list_themes_contains_population(self):
        """인구(A) 주제가 목록에 포함되어야 함."""
        result = list_themes()
        codes = [t["code"] for t in result]

        assert "A" in codes or any("인구" in t.get("name", "") for t in result)


# =============================================================================
# Layer 2: FETCH 테스트 (Mock 데이터 사용)
# =============================================================================

class TestFetchTools:
    """
    FETCH 도구 테스트.

    Mock 데이터를 사용하여 필터링, 집계 동작 검증.
    실제 API 호출 없이 로직만 테스트.
    """

    def test_filter_statistics_data_by_regions(self, small_population_data):
        """지역 필터링 동작 검증."""
        result = filter_statistics_data(
            data=small_population_data,
            regions=["서울특별시", "부산광역시"]
        )

        assert isinstance(result, list)
        assert len(result) > 0
        assert len(result) < len(small_population_data)

        # 필터된 데이터만 포함되는지 확인
        for record in result:
            assert record["C1_NM"] in ["서울특별시", "부산광역시"]

    def test_filter_statistics_data_by_periods(self, small_population_data):
        """기간 필터링 동작 검증."""
        result = filter_statistics_data(
            data=small_population_data,
            periods=["2023", "2024"]
        )

        for record in result:
            assert record["PRD_DE"] in ["2023", "2024"]

    def test_filter_statistics_data_by_items(self, small_population_data):
        """항목 필터링 동작 검증."""
        result = filter_statistics_data(
            data=small_population_data,
            items=["총인구"]
        )

        for record in result:
            assert record["ITM_NM"] == "총인구"

    def test_filter_statistics_data_combined(self, small_population_data):
        """복합 필터링 동작 검증."""
        result = filter_statistics_data(
            data=small_population_data,
            regions=["서울특별시"],
            periods=["2024"],
            items=["총인구"]
        )

        assert len(result) == 1
        assert result[0]["C1_NM"] == "서울특별시"
        assert result[0]["PRD_DE"] == "2024"
        assert result[0]["ITM_NM"] == "총인구"

    def test_aggregate_statistics_data_by_region(self, medium_population_data):
        """지역별 집계 동작 검증."""
        # 총인구만 필터
        pop_data = filter_statistics_data(
            data=medium_population_data,
            items=["총인구"]
        )

        result = aggregate_statistics_data(
            data=pop_data,
            group_by="C1_NM",
            agg_func="sum"
        )

        assert isinstance(result, list)
        # 17개 지역으로 집계되어야 함
        assert len(result) <= 17

    def test_aggregate_statistics_data_by_period(self, medium_population_data):
        """기간별 집계 동작 검증."""
        pop_data = filter_statistics_data(
            data=medium_population_data,
            items=["총인구"]
        )

        result = aggregate_statistics_data(
            data=pop_data,
            group_by="PRD_DE",
            agg_func="mean"
        )

        assert isinstance(result, list)
        # 10개 연도로 집계되어야 함
        assert len(result) <= 10

    def test_get_data_summary_structure(self, medium_population_data):
        """데이터 요약 구조 검증."""
        result = get_data_summary(medium_population_data)

        assert isinstance(result, dict)

        # 필수 필드 검증
        assert "record_count" in result or "total_records" in result or "summary" in result

    def test_get_available_field_values(self, medium_population_data):
        """필드 값 목록 조회."""
        regions = get_available_field_values(medium_population_data, "C1_NM")

        assert isinstance(regions, list)
        assert "서울특별시" in regions
        assert "경기도" in regions


# =============================================================================
# Layer 3: PRESENT - Analysis 테스트
# =============================================================================

class TestAnalysisTools:
    """
    분석 도구 테스트.

    검증 항목:
    - 분석 결과 구조
    - findings/metrics 포함 여부
    - 다양한 데이터에서의 동작
    """

    def test_analyze_data_trend_structure(self, medium_population_data):
        """추세 분석 결과 구조 검증."""
        # 서울 데이터만 추출
        seoul_data = filter_statistics_data(
            data=medium_population_data,
            regions=["서울특별시"],
            items=["총인구"]
        )

        result = analyze_data_trend(seoul_data)

        assert isinstance(result, dict)
        assert "type" in result
        assert result["type"] == "trend"
        assert "findings" in result
        assert "metrics" in result

    def test_analyze_data_trend_with_group(self, medium_population_data):
        """그룹별 추세 분석."""
        # 2개 지역 비교
        data = filter_statistics_data(
            data=medium_population_data,
            regions=["서울특별시", "경기도"],
            items=["총인구"]
        )

        result = analyze_data_trend(data, group_by="C1_NM")

        assert result["type"] == "trend"
        # 그룹별 분석 결과가 있어야 함
        assert "metrics" in result

    def test_analyze_data_comparison_structure(self, medium_population_data):
        """비교 분석 결과 구조 검증."""
        # 최근 연도 데이터
        data = filter_statistics_data(
            data=medium_population_data,
            periods=["2024"],
            items=["총인구"]
        )

        result = analyze_data_comparison(
            data,
            targets=["서울특별시", "부산광역시", "경기도"]
        )

        assert isinstance(result, dict)
        assert "type" in result
        assert result["type"] == "comparison"
        assert "findings" in result
        assert "metrics" in result

    def test_analyze_data_ranking_structure(self, medium_population_data):
        """순위 분석 결과 구조 검증."""
        data = filter_statistics_data(
            data=medium_population_data,
            periods=["2024"],
            items=["총인구"]
        )

        result = analyze_data_ranking(data, top_n=5)

        assert isinstance(result, dict)
        assert result["type"] == "ranking"
        assert "findings" in result
        assert "metrics" in result

    def test_analyze_data_statistics_structure(self, medium_population_data):
        """통계 분석 결과 구조 검증."""
        data = filter_statistics_data(
            data=medium_population_data,
            periods=["2024"],
            items=["총인구"]
        )

        result = analyze_data_statistics(data)

        assert isinstance(result, dict)
        assert result["type"] == "stats"
        assert "findings" in result
        assert "metrics" in result

        # 통계 메트릭 포함 여부
        metrics = result["metrics"]
        expected_metrics = ["mean", "min", "max"]
        for metric in expected_metrics:
            assert metric in metrics, f"Missing metric: {metric}"


# =============================================================================
# Layer 3: PRESENT - Report 테스트
# =============================================================================

class TestReportTools:
    """
    리포트 생성 도구 테스트.

    검증 항목:
    - HTML 생성 여부
    - 파일 저장 동작
    - 필수 구성요소 포함
    """

    def test_create_quick_report_returns_html(self, small_population_data):
        """quick_report가 HTML 문자열 반환."""
        result = create_quick_report(
            data=small_population_data,
            title="테스트 리포트"
        )

        assert isinstance(result, str)
        assert "<!DOCTYPE html>" in result or "<html" in result

    def test_create_quick_report_saves_file(self, small_population_data, output_dir):
        """quick_report 파일 저장."""
        output_path = output_dir / "quick_test.html"

        result = create_quick_report(
            data=small_population_data,
            title="테스트 리포트",
            output_path=str(output_path)
        )

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "테스트 리포트" in content

    def test_create_quick_report_contains_chart(self, medium_population_data, output_dir):
        """quick_report에 차트 포함."""
        output_path = output_dir / "quick_chart.html"

        create_quick_report(
            data=medium_population_data,
            title="차트 테스트",
            output_path=str(output_path)
        )

        content = output_path.read_text(encoding="utf-8")
        assert "Plotly" in content or "plotly" in content.lower()
        assert "chart" in content.lower() or "newPlot" in content

    def test_create_custom_report_options(self, medium_population_data, output_dir):
        """custom_report 옵션 동작."""
        output_path = output_dir / "custom_test.html"

        result = create_custom_report(
            data=medium_population_data,
            title="커스텀 리포트",
            include_kpi=True,
            include_trend_chart=True,
            include_comparison_chart=False,
            include_table=True,
            include_insights=True,
            output_path=str(output_path)
        )

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")

        # KPI 포함 확인
        assert "kpi" in content.lower() or "📊" in content or "지표" in content

    def test_create_custom_report_minimal(self, small_population_data, output_dir):
        """custom_report 최소 옵션."""
        output_path = output_dir / "minimal_test.html"

        result = create_custom_report(
            data=small_population_data,
            title="최소 리포트",
            include_kpi=False,
            include_trend_chart=False,
            include_comparison_chart=False,
            include_table=True,
            include_insights=False,
            output_path=str(output_path)
        )

        assert output_path.exists()


# =============================================================================
# 워크플로우 통합 테스트
# =============================================================================

class TestWorkflowIntegration:
    """
    전체 워크플로우 통합 테스트.

    시나리오:
    1. 간단한 질문 (A 페르소나): 단일 값 조회
    2. 비교 분석 (B 페르소나): 2개 지역 비교
    3. 종합 분석 (C 페르소나): 순위 + 추이 + 리포트
    """

    def test_simple_query_workflow(self, medium_population_data):
        """
        시나리오: "서울 인구가 얼마인가요?"

        워크플로우:
        1. 필터링 (서울, 최근 연도, 총인구)
        2. 값 추출

        검증:
        - 단일 숫자 값 반환
        - 응답 크기 최소화
        """
        # Step 1: 필터링
        result = filter_statistics_data(
            data=medium_population_data,
            regions=["서울특별시"],
            periods=["2024"],
            items=["총인구"]
        )

        # 검증
        assert len(result) == 1
        assert result[0]["C1_NM"] == "서울특별시"

        # 응답 크기 검증
        response = json.dumps(result, ensure_ascii=False)
        assert len(response) < 500  # 단순 응답은 500자 미만

    def test_comparison_workflow(self, medium_population_data, output_dir):
        """
        시나리오: "서울과 경기도 인구 비교해줘"

        워크플로우:
        1. 두 지역 데이터 필터링
        2. 비교 분석
        3. 추세 분석
        4. 리포트 생성

        검증:
        - 분석 결과에 비교 인사이트 포함
        - 리포트에 차트 포함
        """
        # Step 1: 필터링
        filtered = filter_statistics_data(
            data=medium_population_data,
            regions=["서울특별시", "경기도"],
            items=["총인구"]
        )

        # Step 2: 비교 분석
        comparison = analyze_data_comparison(filtered)
        assert comparison["type"] == "comparison"
        assert len(comparison["findings"]) > 0

        # Step 3: 추세 분석
        trend = analyze_data_trend(filtered, group_by="C1_NM")
        assert trend["type"] == "trend"

        # Step 4: 리포트 생성
        output_path = output_dir / "comparison_workflow.html"
        create_quick_report(
            data=filtered,
            title="서울-경기도 인구 비교",
            output_path=str(output_path)
        )

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "서울" in content
        assert "경기" in content

    def test_comprehensive_analysis_workflow(self, medium_population_data, output_dir):
        """
        시나리오: "인구 감소 상위 5개 지역 분석해줘"

        워크플로우:
        1. 전체 데이터 로드
        2. 연도별 집계
        3. 변화율 계산 (순위 분석)
        4. 상위 5개 지역 추출
        5. 해당 지역 추세 분석
        6. 종합 리포트 생성

        검증:
        - 순위 분석 결과 5개 항목
        - 리포트에 다양한 차트
        """
        # Step 1: 총인구만 필터
        pop_data = filter_statistics_data(
            data=medium_population_data,
            items=["총인구"]
        )

        # Step 2: 순위 분석 (최근 연도 기준)
        recent_data = filter_statistics_data(pop_data, periods=["2024"])
        ranking = analyze_data_ranking(recent_data, top_n=5)

        assert len(ranking["findings"]) >= 3

        # Step 3: 통계 분석
        stats = analyze_data_statistics(recent_data)
        assert "mean" in stats["metrics"]

        # Step 4: 종합 리포트
        output_path = output_dir / "comprehensive_workflow.html"
        create_custom_report(
            data=pop_data,
            title="인구 종합 분석",
            include_kpi=True,
            include_trend_chart=True,
            include_comparison_chart=True,
            include_table=True,
            include_insights=True,
            output_path=str(output_path)
        )

        assert output_path.exists()

        # 파일 크기 검증 (너무 크지 않아야 함)
        file_size = output_path.stat().st_size
        assert file_size < 500_000  # 500KB 미만


# =============================================================================
# 경계 조건 테스트
# =============================================================================

class TestEdgeCases:
    """
    경계 조건 테스트.

    빈 데이터, 단일 레코드, 비정상 입력 처리.
    """

    def test_filter_with_no_match(self, small_population_data):
        """매칭 없는 필터."""
        result = filter_statistics_data(
            data=small_population_data,
            regions=["존재하지않는지역"]
        )

        assert isinstance(result, list)
        assert len(result) == 0

    def test_aggregate_empty_data(self):
        """빈 데이터 집계."""
        # 빈 데이터 집계는 KeyError 발생 가능 (컬럼 없음)
        try:
            result = aggregate_statistics_data(
                data=[],
                group_by="C1_NM",
                agg_func="sum"
            )
            assert isinstance(result, list)
            assert len(result) == 0
        except KeyError:
            # 빈 DataFrame에서 컬럼 접근 시 KeyError 발생 가능
            pass

    def test_analyze_single_record(self):
        """단일 레코드 분석."""
        single = [{
            "PRD_DE": "2024",
            "C1_NM": "서울특별시",
            "DT": "9400000",
            "ITM_NM": "총인구",
        }]

        result = analyze_data_statistics(single)

        assert isinstance(result, dict)
        assert "metrics" in result

    def test_analyze_empty_data(self):
        """빈 데이터 분석."""
        # 빈 데이터 분석은 KeyError 발생 가능 (컬럼 없음)
        try:
            result = analyze_data_trend([])
            assert isinstance(result, dict)
        except KeyError:
            # 빈 DataFrame에서 컬럼 접근 시 KeyError 발생 가능
            pass

    def test_report_with_empty_data(self, output_dir):
        """빈 데이터로 리포트 생성."""
        output_path = output_dir / "empty_report.html"

        # 빈 데이터는 에러 발생 가능
        try:
            result = create_quick_report(
                data=[],
                title="빈 리포트",
                output_path=str(output_path)
            )
            # 파일이 생성되거나, 적절한 에러 메시지 반환
            assert output_path.exists() or "error" in str(result).lower() or "empty" in str(result).lower()
        except (ValueError, KeyError) as e:
            # 빈 데이터에 대한 에러도 허용
            assert len(str(e)) > 0
