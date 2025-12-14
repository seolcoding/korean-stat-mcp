"""
LLM/MCP 워크플로우 E2E 테스트.

이 테스트는 LLM이 MCP 도구를 사용하여 전체 워크플로우를 수행하는 시나리오를 시뮬레이션합니다.
각 시나리오는:
1. 유저 쿼리 해석
2. DISCOVER: 데이터 탐색 및 구조 파악
3. FETCH: 데이터 조회 및 필터링
4. PRESENT: 분석, 시각화, 리포트 생성

테스트는 실제 API 호출 없이 샘플 데이터로 진행됩니다.
"""

import pytest
from pathlib import Path
import tempfile
import json

from kosis_tools.report_tools import (
    # 데이터 클래스
    ReportComponent,
    AnalysisResult,
    # Layer 1: DISCOVER
    get_available_values,
    # Layer 2: FETCH
    filter_data,
    aggregate_data,
    # Layer 3: PRESENT - Visualization
    viz_line_trend,
    viz_bar_comparison,
    viz_kpi_card,
    viz_pie_composition,
    viz_heatmap,
    # Layer 3: PRESENT - Analysis
    analyze_trend,
    analyze_comparison,
    analyze_ranking,
    analyze_stats,
    # Layer 3: PRESENT - Text
    text_headline,
    text_summary,
    text_insight,
    text_data_note,
    # Layer 3: PRESENT - Layout
    layout_section,
    layout_card_grid,
    layout_two_column,
    layout_highlight_box,
    layout_table,
    # Layer 3: PRESENT - Assembly
    assemble_report,
    quick_report,
)


# =============================================================================
# 테스트용 Mock 데이터
# =============================================================================

@pytest.fixture
def population_data() -> list[dict]:
    """전국 시도별 인구 데이터 (2019-2023, 17개 시도)."""
    regions = [
        "서울특별시", "부산광역시", "대구광역시", "인천광역시",
        "광주광역시", "대전광역시", "울산광역시", "세종특별자치시",
        "경기도", "강원특별자치도", "충청북도", "충청남도",
        "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도"
    ]

    # 2023년 실제 인구 (대략적 수치)
    pop_2023 = {
        "서울특별시": 9411211,
        "부산광역시": 3314183,
        "대구광역시": 2357570,
        "인천광역시": 2967314,
        "광주광역시": 1434282,
        "대전광역시": 1445543,
        "울산광역시": 1106463,
        "세종특별자치시": 380543,
        "경기도": 13639666,
        "강원특별자치도": 1533937,
        "충청북도": 1597179,
        "충청남도": 2121029,
        "전라북도": 1760977,
        "전라남도": 1819284,
        "경상북도": 2604527,
        "경상남도": 3277053,
        "제주특별자치도": 674635,
    }

    data = []
    for year in range(2019, 2024):
        for region in regions:
            # 서울, 부산, 대구 감소 / 경기, 세종, 인천 증가 트렌드 반영
            base_pop = pop_2023[region]
            year_diff = year - 2023

            if region in ["서울특별시", "부산광역시", "대구광역시"]:
                # 연간 약 1-2% 감소
                pop = int(base_pop * (1 + 0.015 * year_diff))
            elif region in ["경기도", "세종특별자치시", "인천광역시"]:
                # 연간 약 1-2% 증가 (과거가 더 적었음)
                pop = int(base_pop * (1 - 0.012 * (-year_diff)))
            else:
                # 소폭 변동
                pop = int(base_pop * (1 + 0.003 * year_diff))

            data.append({
                "PRD_DE": str(year),
                "C1_NM": region,
                "DT": str(pop),
                "ITM_NM": "총인구",
                "UNIT_NM": "명",
            })

    return data


@pytest.fixture
def employment_data() -> list[dict]:
    """고용 통계 데이터 (산업별, 분기별)."""
    industries = ["제조업", "건설업", "도소매업", "숙박음식업", "IT서비스업", "금융보험업"]

    data = []
    for year in [2022, 2023]:
        for quarter in [1, 2, 3, 4]:
            for industry in industries:
                # 산업별 기본 고용자 수 (만명 단위)
                base_emp = {
                    "제조업": 450,
                    "건설업": 200,
                    "도소매업": 380,
                    "숙박음식업": 220,
                    "IT서비스업": 120,
                    "금융보험업": 85,
                }[industry]

                # 계절 변동 + 트렌드
                seasonal = 1 + (quarter - 2.5) * 0.02  # 2분기가 평균
                trend = 1 + (year - 2022) * 0.03 + (quarter - 1) * 0.005

                # IT는 급성장
                if industry == "IT서비스업":
                    trend *= 1.05
                # 숙박음식은 변동 큼
                if industry == "숙박음식업":
                    seasonal = 1 + (quarter - 2) * 0.08

                emp = int(base_emp * seasonal * trend * 10000)

                data.append({
                    "PRD_DE": f"{year}Q{quarter}",
                    "C1_NM": industry,
                    "DT": str(emp),
                    "ITM_NM": "취업자수",
                    "UNIT_NM": "명",
                })

    return data


@pytest.fixture
def cpi_data() -> list[dict]:
    """소비자물가지수 데이터 (월별)."""
    items = ["총지수", "식료품", "주거", "교통", "교육"]

    data = []
    for year in [2022, 2023]:
        for month in range(1, 13):
            for item in items:
                # 기본 물가지수 (2020=100 기준)
                base_idx = 100

                # 2022-2023 인플레이션 반영
                inflation = {
                    "총지수": 0.003,
                    "식료품": 0.005,
                    "주거": 0.004,
                    "교통": 0.006,
                    "교육": 0.002,
                }[item]

                months_from_base = (year - 2020) * 12 + month
                idx = base_idx * (1 + inflation) ** (months_from_base / 12)

                data.append({
                    "PRD_DE": f"{year}{month:02d}",
                    "C1_NM": item,
                    "DT": f"{idx:.1f}",
                    "ITM_NM": "소비자물가지수",
                    "UNIT_NM": "지수",
                })

    return data


# =============================================================================
# 시나리오 1: 유저 쿼리 - "서울과 경기도 인구 비교해줘"
# =============================================================================

class TestScenario1_RegionalComparison:
    """
    유저 쿼리: "서울과 경기도 인구 비교해줘"

    LLM 워크플로우:
    1. 쿼리 파싱: 서울, 경기도 식별 / 비교 분석 필요
    2. DISCOVER: 데이터에서 서울, 경기도 존재 확인
    3. FETCH: 두 지역 데이터 필터링
    4. PRESENT: 비교 차트, 분석, 인사이트 생성
    """

    def test_full_workflow(self, population_data, tmp_path):
        """전체 워크플로우 테스트."""
        # ====================================================================
        # Step 1: LLM이 쿼리 해석 (시뮬레이션)
        # ====================================================================
        user_query = "서울과 경기도 인구 비교해줘"
        target_regions = ["서울특별시", "경기도"]
        analysis_type = "comparison"

        # ====================================================================
        # Step 2: DISCOVER - 데이터 탐색
        # ====================================================================
        available_regions = get_available_values(population_data, "C1_NM")
        available_periods = get_available_values(population_data, "PRD_DE")

        # 요청한 지역이 데이터에 있는지 확인
        assert all(r in available_regions for r in target_regions)

        # ====================================================================
        # Step 3: FETCH - 데이터 조회
        # ====================================================================
        filtered_data = filter_data(population_data, regions=target_regions)
        assert len(filtered_data) > 0

        # 최신 연도 데이터
        latest_year = max(available_periods)
        latest_data = filter_data(filtered_data, periods=[latest_year])

        # ====================================================================
        # Step 4: PRESENT - 분석 및 시각화
        # ====================================================================

        # 4-1. 비교 분석
        comparison = analyze_comparison(
            filtered_data,
            compare_field="C1_NM",
            targets=target_regions,
            period=latest_year
        )
        assert comparison.type == "comparison"
        assert comparison.metrics["max"]["name"] == "경기도"  # 경기도가 더 많음

        # 4-2. 추세 분석
        trend = analyze_trend(filtered_data, group_by="C1_NM")
        assert "groups" in trend.metrics

        # 4-3. KPI 카드 생성
        kpi_cards = []
        for region in target_regions:
            region_latest = filter_data(latest_data, regions=[region])[0]
            pop = int(region_latest["DT"])

            # 전년 대비 변화율 계산
            prev_year = str(int(latest_year) - 1)
            prev_data = filter_data(filtered_data, regions=[region], periods=[prev_year])
            if prev_data:
                prev_pop = int(prev_data[0]["DT"])
                change_pct = ((pop - prev_pop) / prev_pop) * 100
            else:
                change_pct = 0

            kpi_cards.append(viz_kpi_card(
                value=pop,
                label=f"{region} 인구",
                change=change_pct,
                change_label="전년 대비",
                icon="👥"
            ))

        # 4-4. 추이 차트
        trend_chart = viz_line_trend(
            filtered_data,
            title="서울-경기도 인구 추이 비교",
            x="PRD_DE",
            y="DT",
            color="C1_NM"
        )

        # 4-5. 막대 차트 (최신 연도)
        bar_chart = viz_bar_comparison(
            latest_data,
            title=f"{latest_year}년 인구 비교",
            x="C1_NM",
            y="DT"
        )

        # 4-6. 텍스트 생성
        headline = text_headline(comparison, style="news")
        insight = text_insight(comparison, depth="standard")
        note = text_data_note(filtered_data)

        # ====================================================================
        # Step 5: ASSEMBLE - 리포트 조립
        # ====================================================================

        # 섹션 구성
        kpi_grid = layout_card_grid(kpi_cards, columns=2)

        section_overview = layout_section(
            "핵심 지표",
            [kpi_grid],
            icon="📊"
        )

        section_trend = layout_section(
            "인구 추이",
            [trend_chart],
            icon="📈"
        )

        section_comparison = layout_section(
            "비교 분석",
            [bar_chart, headline, insight],
            icon="⚖️"
        )

        # 최종 조립
        output_path = tmp_path / "scenario1_regional_comparison.html"

        report = assemble_report(
            [section_overview, section_trend, section_comparison, note],
            title="서울-경기도 인구 비교 분석",
            subtitle=f"분석 기간: {min(available_periods)}~{max(available_periods)}",
            output_path=str(output_path)
        )

        # ====================================================================
        # 검증
        # ====================================================================
        assert output_path.exists()

        content = output_path.read_text(encoding="utf-8")
        assert "서울-경기도 인구 비교 분석" in content
        assert "Plotly.newPlot" in content  # 차트가 포함됨
        assert "서울특별시" in content
        assert "경기도" in content
        assert "인사이트" in content


# =============================================================================
# 시나리오 2: 유저 쿼리 - "최근 5년 인구 감소가 심한 지역 top 5"
# =============================================================================

class TestScenario2_RankingAnalysis:
    """
    유저 쿼리: "최근 5년 인구 감소가 심한 지역 top 5"

    LLM 워크플로우:
    1. 쿼리 파싱: 감소율 계산 / 순위 분석 필요
    2. DISCOVER: 전체 지역, 기간 확인
    3. FETCH: 전체 데이터 + 증감률 계산
    4. PRESENT: 순위 테이블, 하락 추이 차트
    """

    def test_full_workflow(self, population_data, tmp_path):
        """전체 워크플로우 테스트."""
        # ====================================================================
        # Step 1: LLM이 쿼리 해석
        # ====================================================================
        user_query = "최근 5년 인구 감소가 심한 지역 top 5"
        top_n = 5
        analysis_type = "ranking"

        # ====================================================================
        # Step 2: DISCOVER
        # ====================================================================
        regions = get_available_values(population_data, "C1_NM")
        periods = sorted(get_available_values(population_data, "PRD_DE"))

        first_year = periods[0]
        last_year = periods[-1]

        # ====================================================================
        # Step 3: FETCH + 변화율 계산
        # ====================================================================
        change_data = []

        for region in regions:
            first_data = filter_data(population_data, regions=[region], periods=[first_year])
            last_data = filter_data(population_data, regions=[region], periods=[last_year])

            if first_data and last_data:
                first_pop = int(first_data[0]["DT"])
                last_pop = int(last_data[0]["DT"])
                change_pct = ((last_pop - first_pop) / first_pop) * 100

                change_data.append({
                    "C1_NM": region,
                    "first_pop": first_pop,
                    "last_pop": last_pop,
                    "change_pct": change_pct,
                    "DT": change_pct,  # 정렬용
                })

        # 감소율 기준 정렬 (가장 많이 감소한 순)
        change_data_sorted = sorted(change_data, key=lambda x: x["change_pct"])
        top_declining = change_data_sorted[:top_n]

        # ====================================================================
        # Step 4: PRESENT
        # ====================================================================

        # 4-1. 감소 지역들의 추이 데이터
        declining_regions = [r["C1_NM"] for r in top_declining]
        declining_trend_data = filter_data(population_data, regions=declining_regions)

        # 4-2. 추이 차트
        trend_chart = viz_line_trend(
            declining_trend_data,
            title=f"인구 감소 상위 {top_n}개 지역 추이",
            color="C1_NM"
        )

        # 4-3. 감소율 막대 차트 (음수로 표시)
        for item in top_declining:
            item["DT"] = str(abs(item["change_pct"]))

        decline_chart = viz_bar_comparison(
            top_declining,
            x="C1_NM",
            y="DT",
            title=f"{first_year}-{last_year} 인구 감소율 (%)",
            horizontal=True
        )

        # 4-4. 순위 테이블
        table_data = []
        for i, item in enumerate(top_declining, 1):
            table_data.append({
                "순위": i,
                "지역": item["C1_NM"],
                f"{first_year}년": f"{item['first_pop']:,}",
                f"{last_year}년": f"{item['last_pop']:,}",
                "변화율": f"{item['change_pct']:.2f}%"
            })

        ranking_table = layout_table(
            table_data,
            columns=["순위", "지역", f"{first_year}년", f"{last_year}년", "변화율"]
        )

        # 4-5. 강조 박스
        worst = top_declining[0]
        highlight = layout_highlight_box(
            f"가장 큰 감소를 보인 지역은 <strong>{worst['C1_NM']}</strong>로, "
            f"{first_year}년 대비 {abs(worst['change_pct']):.1f}% 감소했습니다.",
            style="warning",
            title="주요 발견"
        )

        # 4-6. 인사이트
        trend_analysis = analyze_trend(declining_trend_data, group_by="C1_NM")
        insight = text_insight(trend_analysis, depth="deep", perspective="policy")

        note = text_data_note(population_data)

        # ====================================================================
        # Step 5: ASSEMBLE
        # ====================================================================
        output_path = tmp_path / "scenario2_ranking.html"

        report = assemble_report(
            [highlight, ranking_table, trend_chart, decline_chart, insight, note],
            title="인구 감소 지역 분석",
            subtitle=f"분석 기간: {first_year}~{last_year}",
            output_path=str(output_path)
        )

        # 검증
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "인구 감소 지역 분석" in content
        assert worst["C1_NM"] in content


# =============================================================================
# 시나리오 3: 유저 쿼리 - "2023년 산업별 고용 현황 대시보드"
# =============================================================================

class TestScenario3_Dashboard:
    """
    유저 쿼리: "2023년 산업별 고용 현황 대시보드"

    LLM 워크플로우:
    1. 대시보드 형식 요청 -> 여러 차트/KPI 필요
    2. DISCOVER: 산업 목록 확인
    3. FETCH: 2023년 데이터 추출
    4. PRESENT: KPI 그리드, 파이 차트, 막대 차트, 히트맵 조합
    """

    def test_full_workflow(self, employment_data, tmp_path):
        """전체 워크플로우 테스트."""
        # ====================================================================
        # Step 1: LLM이 쿼리 해석
        # ====================================================================
        user_query = "2023년 산업별 고용 현황 대시보드"
        target_year = "2023"

        # ====================================================================
        # Step 2: DISCOVER
        # ====================================================================
        industries = get_available_values(employment_data, "C1_NM")
        periods = get_available_values(employment_data, "PRD_DE")

        # 2023년 분기 데이터만 필터
        periods_2023 = [p for p in periods if p.startswith("2023")]

        # ====================================================================
        # Step 3: FETCH
        # ====================================================================
        data_2023 = filter_data(employment_data, periods=periods_2023)

        # 산업별 연간 합계
        annual_by_industry = aggregate_data(data_2023, group_by="C1_NM", agg_func="mean")

        # ====================================================================
        # Step 4: PRESENT - 대시보드 구성 요소
        # ====================================================================

        # 4-1. 총 고용자 수 KPI
        total_emp = sum(int(d["DT"]) for d in annual_by_industry)
        total_kpi = viz_kpi_card(
            value=total_emp,
            label="총 취업자수 (평균)",
            icon="👷"
        )

        # 4-2. 산업 수 KPI
        industry_count_kpi = viz_kpi_card(
            value=len(industries),
            label="분석 산업 수",
            icon="🏭"
        )

        # 4-3. 최다 고용 산업 KPI
        sorted_industries = sorted(annual_by_industry, key=lambda x: int(x["DT"]), reverse=True)
        top_industry = sorted_industries[0]
        top_kpi = viz_kpi_card(
            value=int(top_industry["DT"]),
            label=f"1위: {top_industry['C1_NM']}",
            icon="🏆"
        )

        # KPI 그리드
        kpi_grid = layout_card_grid([total_kpi, industry_count_kpi, top_kpi], columns=3)

        # 4-4. 산업별 비중 파이 차트
        pie_chart = viz_pie_composition(
            annual_by_industry,
            values="DT",
            names="C1_NM",
            title="산업별 고용 비중",
            top_n=6
        )

        # 4-5. 산업별 막대 차트
        bar_chart = viz_bar_comparison(
            annual_by_industry,
            x="C1_NM",
            y="DT",
            title="산업별 평균 취업자수",
            sort=True
        )

        # 4-6. 분기별 히트맵
        heatmap = viz_heatmap(
            data_2023,
            x="PRD_DE",
            y="C1_NM",
            z="DT",
            title="산업-분기별 고용 현황"
        )

        # 4-7. 분기별 추이 (라인)
        trend_chart = viz_line_trend(
            data_2023,
            title="2023년 분기별 산업별 추이",
            x="PRD_DE",
            y="DT",
            color="C1_NM"
        )

        # 4-8. 순위 분석
        ranking = analyze_ranking(annual_by_industry, top_n=6)
        ranking_text = text_headline(ranking, style="formal")

        # 4-9. 통계 요약
        stats = analyze_stats(annual_by_industry)
        stats_summary = layout_highlight_box(
            f"평균 취업자수: {stats.metrics['mean']:,.0f}명 | "
            f"최대: {stats.metrics['max']:,.0f}명 | "
            f"최소: {stats.metrics['min']:,.0f}명",
            style="info",
            title="통계 요약"
        )

        note = text_data_note(employment_data, source="고용노동부 KOSIS")

        # ====================================================================
        # Step 5: ASSEMBLE - 대시보드 레이아웃
        # ====================================================================

        # 2단 레이아웃: 파이 + 막대
        two_col = layout_two_column(pie_chart, bar_chart, ratio="1:1")

        # 섹션 구성
        section_kpi = layout_section("핵심 지표", [kpi_grid], icon="📊")
        section_distribution = layout_section("산업별 분포", [two_col], icon="📈")
        section_trend = layout_section("분기별 추이", [trend_chart, heatmap], icon="📅")
        section_analysis = layout_section("분석", [ranking_text, stats_summary], icon="🔍")

        output_path = tmp_path / "scenario3_dashboard.html"

        report = assemble_report(
            [section_kpi, section_distribution, section_trend, section_analysis, note],
            title="2023년 산업별 고용 현황 대시보드",
            template="dashboard",
            output_path=str(output_path)
        )

        # 검증
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "대시보드" in content
        assert "제조업" in content
        assert "IT서비스업" in content


# =============================================================================
# 시나리오 4: 유저 쿼리 - "물가 상승률 분석"
# =============================================================================

class TestScenario4_TrendAnalysis:
    """
    유저 쿼리: "물가 상승률 분석"

    LLM 워크플로우:
    1. 인플레이션/물가 분석 요청
    2. DISCOVER: 물가 품목 확인
    3. FETCH: 시계열 데이터
    4. PRESENT: 추세 분석, 품목별 비교
    """

    def test_full_workflow(self, cpi_data, tmp_path):
        """전체 워크플로우 테스트."""
        # ====================================================================
        # Step 1: LLM이 쿼리 해석
        # ====================================================================
        user_query = "물가 상승률 분석"

        # ====================================================================
        # Step 2: DISCOVER
        # ====================================================================
        items = get_available_values(cpi_data, "C1_NM")
        periods = sorted(get_available_values(cpi_data, "PRD_DE"))

        # ====================================================================
        # Step 3: FETCH
        # ====================================================================
        # 총지수 분석 (C1_NM 필드에 품목명이 있음)
        total_idx_data = filter_data(cpi_data, regions=["총지수"])

        # 최근 12개월
        recent_periods = periods[-12:]
        recent_data = filter_data(cpi_data, periods=recent_periods)

        # ====================================================================
        # Step 4: PRESENT
        # ====================================================================

        # 4-1. 총지수 추세
        total_trend = analyze_trend(total_idx_data)

        # 4-2. 현재 물가지수
        latest = filter_data(total_idx_data, periods=[periods[-1]])[0]
        current_kpi = viz_kpi_card(
            value=float(latest["DT"]),
            label="현재 물가지수",
            format_str="{:.1f}",
            icon="💰"
        )

        # 4-3. 전년 동월 대비 계산
        year_ago_period = periods[-13] if len(periods) > 12 else periods[0]
        year_ago = filter_data(total_idx_data, periods=[year_ago_period])
        if year_ago:
            yoy_change = ((float(latest["DT"]) - float(year_ago[0]["DT"]))
                         / float(year_ago[0]["DT"]) * 100)
        else:
            yoy_change = 0

        yoy_kpi = viz_kpi_card(
            value=yoy_change,
            label="전년 동월 대비",
            format_str="{:+.1f}%",
            icon="📈" if yoy_change > 0 else "📉"
        )

        kpi_grid = layout_card_grid([current_kpi, yoy_kpi], columns=2)

        # 4-4. 전체 추이 차트
        trend_chart = viz_line_trend(
            cpi_data,
            title="품목별 물가지수 추이",
            color="C1_NM"
        )

        # 4-5. 품목별 비교 (최근 월)
        latest_all = filter_data(cpi_data, periods=[periods[-1]])
        bar_chart = viz_bar_comparison(
            latest_all,
            x="C1_NM",
            y="DT",
            title=f"{periods[-1]} 품목별 물가지수"
        )

        # 4-6. 히트맵 (품목 x 월)
        heatmap = viz_heatmap(
            recent_data,
            x="PRD_DE",
            y="C1_NM",
            z="DT",
            title="최근 12개월 품목별 물가지수"
        )

        # 4-7. 텍스트 분석
        headline = text_headline(total_trend, style="news")
        insight = text_insight(total_trend, depth="standard", perspective="economic")
        summary = text_summary(cpi_data)
        note = text_data_note(cpi_data)

        # ====================================================================
        # Step 5: ASSEMBLE
        # ====================================================================
        output_path = tmp_path / "scenario4_cpi_analysis.html"

        report = assemble_report(
            [kpi_grid, headline, trend_chart, bar_chart, heatmap, insight, summary, note],
            title="소비자물가지수 분석",
            subtitle="물가 동향 및 품목별 비교",
            template="article",
            output_path=str(output_path)
        )

        # 검증
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "물가지수" in content or "물가" in content


# =============================================================================
# 시나리오 5: quick_report 원클릭 테스트
# =============================================================================

class TestScenario5_QuickReport:
    """
    유저 쿼리: "이 데이터 간단히 분석해줘"

    LLM 워크플로우:
    - quick_report 사용하여 자동 분석
    """

    def test_quick_report_population(self, population_data, tmp_path):
        """인구 데이터 빠른 분석."""
        output_path = tmp_path / "quick_population.html"

        result = quick_report(
            population_data,
            title="전국 인구 현황 분석",
            output_path=str(output_path)
        )

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")

        # 자동 생성된 요소 확인
        assert "kpi-card" in content
        assert "chart-container" in content
        assert "인사이트" in content

    def test_quick_report_employment(self, employment_data, tmp_path):
        """고용 데이터 빠른 분석."""
        output_path = tmp_path / "quick_employment.html"

        result = quick_report(
            employment_data,
            title="고용 현황",
            output_path=str(output_path)
        )

        assert output_path.exists()

    def test_quick_report_cpi(self, cpi_data, tmp_path):
        """물가 데이터 빠른 분석."""
        output_path = tmp_path / "quick_cpi.html"

        result = quick_report(
            cpi_data,
            title="물가 동향",
            output_path=str(output_path)
        )

        assert output_path.exists()


# =============================================================================
# 시나리오 6: 복합 쿼리 - 여러 분석 타입 조합
# =============================================================================

class TestScenario6_ComplexQuery:
    """
    유저 쿼리: "서울, 부산, 대구 인구 추이 보고 순위 변화도 분석해줘"

    LLM 워크플로우:
    - 추세 분석 + 비교 분석 + 순위 분석 조합
    """

    def test_multi_analysis_workflow(self, population_data, tmp_path):
        """다중 분석 타입 조합."""
        target_regions = ["서울특별시", "부산광역시", "대구광역시"]

        # FETCH
        filtered = filter_data(population_data, regions=target_regions)

        # 여러 분석 수행
        trend = analyze_trend(filtered, group_by="C1_NM")
        comparison = analyze_comparison(filtered)
        ranking = analyze_ranking(filtered, top_n=3)
        stats = analyze_stats(filtered)

        # 각 분석 결과로 컴포넌트 생성
        components = [
            text_headline(trend, style="news"),
            viz_line_trend(filtered, title="3대 도시 인구 추이"),
            text_insight(comparison, depth="standard"),
            layout_table(ranking.data, columns=["C1_NM", "DT"],
                        column_labels={"C1_NM": "지역", "DT": "인구"}),
            layout_highlight_box(
                f"3개 도시 평균 인구: {stats.metrics['mean']:,.0f}명",
                style="info"
            ),
            text_data_note(filtered)
        ]

        output_path = tmp_path / "scenario6_complex.html"

        report = assemble_report(
            components,
            title="3대 도시 인구 종합 분석",
            output_path=str(output_path)
        )

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "서울특별시" in content
        assert "부산광역시" in content
        assert "대구광역시" in content


# =============================================================================
# 통합 검증 테스트
# =============================================================================

class TestOutputValidation:
    """생성된 HTML 출력 검증."""

    def test_html_structure(self, population_data, tmp_path):
        """HTML 구조 검증."""
        output_path = tmp_path / "validation.html"
        quick_report(population_data, output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")

        # 필수 HTML 요소
        assert "<!DOCTYPE html>" in content
        assert "<html lang=\"ko\">" in content
        assert "<meta charset=\"UTF-8\">" in content

        # Plotly CDN
        assert "cdn.plot.ly/plotly" in content

        # 한글 폰트
        assert "Noto Sans KR" in content

        # KOSIS 출처
        assert "KOSIS" in content

    def test_all_component_types_render(self, population_data, tmp_path):
        """모든 컴포넌트 타입 렌더링."""
        # 모든 타입의 컴포넌트 생성
        components = [
            viz_kpi_card(100, "KPI"),
            viz_line_trend(filter_data(population_data, regions=["서울특별시"])),
            viz_bar_comparison(filter_data(population_data, periods=["2023"])),
            viz_pie_composition(filter_data(population_data, periods=["2023"])),
            text_summary(population_data),
            layout_highlight_box("테스트", style="info"),
            layout_table(population_data[:5]),
            text_data_note(population_data),
        ]

        output_path = tmp_path / "all_components.html"

        report = assemble_report(
            components,
            title="컴포넌트 테스트",
            output_path=str(output_path)
        )

        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")

        # 각 타입별 마커 확인
        assert "kpi-card" in content
        assert "chart-container" in content
        assert "report-table" in content
