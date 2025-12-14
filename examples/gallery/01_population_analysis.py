"""
예제 1: 대한민국 인구 통계 분석

이 예제는 KOSIS API를 통해 대한민국 인구 데이터를 조회하고 분석합니다.

📊 지표 정보:
    - 지표명: 행정구역별 인구수
    - 출처: 통계청 (orgId: 101)
    - 테이블 ID: DT_1B040A3
    - 주기: 연간(Y)
    - 수록기간: 1992년 ~ 현재

📝 분석 내용:
    1. 기초 설명 - 인구 통계 개요
    2. EDA - 컬럼 구조 및 데이터 탐색
    3. 주요 통계 - 전국/지역별 통계량
    4. 시각화 - 인구 추이, 지역 비교
    5. 인사이트 - 인구 변화 트렌드 분석

실행 방법:
    uv run python examples/gallery/01_population_analysis.py
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from kosis_tools import StatisticsData, StatisticsSearch
from kosis_tools.transform import KosisTransformer, Fields, get_llm_context
from kosis_tools.visualize import KosisVisualizer, quick_line, quick_bar


def print_section(title: str):
    """섹션 제목 출력"""
    print("\n" + "=" * 60)
    print(f"📊 {title}")
    print("=" * 60)


def main():
    """인구 통계 분석 예제 실행"""

    # =========================================================================
    # 1. 기초 설명
    # =========================================================================
    print_section("1. 지표 기초 설명")

    description = """
    📌 행정구역별 인구수 (DT_1B040A3)

    이 통계는 주민등록에 기초하여 전국 행정구역(시도/시군구/읍면동)별
    인구수를 집계한 자료입니다.

    ▶ 작성기관: 통계청
    ▶ 작성주기: 월간 / 연간
    ▶ 수록기간: 1992년 ~ 현재
    ▶ 분류항목: 행정구역, 성별
    ▶ 측정단위: 명

    ▶ 활용분야:
       - 인구정책 수립
       - 지역개발 계획
       - 선거구 획정
       - 사회복지 예산 배분
    """
    print(description)

    # =========================================================================
    # 2. 데이터 조회
    # =========================================================================
    print_section("2. 데이터 조회")

    data_client = StatisticsData()

    # 최근 5년 연간 인구 데이터 조회
    print(">>> 최근 5년 인구 데이터 조회 중...")
    records = data_client.get_data(
        org_id="101",
        tbl_id="DT_1B040A3",
        start_date="2019",
        end_date="2023",
        prd_se="Y",
    )

    print(f"✅ 조회 완료: {len(records):,}건")

    # =========================================================================
    # 3. EDA - 데이터 탐색
    # =========================================================================
    print_section("3. EDA - 데이터 탐색")

    tx = KosisTransformer(records)

    # 3-1. 필드 구조
    print("\n📋 필드 정보:")
    field_info = tx.get_field_info()
    for field, info in field_info.items():
        print(f"  - {field}: {info['dtype']}, 고유값 {info['nunique']}개")

    # 3-2. 차원 정보
    print("\n📐 데이터 차원:")
    periods = tx.get_unique_values(Fields.PERIOD)
    regions = tx.get_unique_values(Fields.C1_NM)
    print(f"  - 기간: {len(periods)}개 ({periods[0]} ~ {periods[-1]})")
    print(f"  - 지역: {len(regions)}개")
    print(f"    (예: {', '.join(regions[:5])}...)")

    # 3-3. 샘플 데이터
    print("\n📝 샘플 데이터:")
    df = tx.to_dataframe()
    sample_cols = [Fields.PERIOD, Fields.C1_NM, Fields.VALUE]
    available_cols = [c for c in sample_cols if c in df.columns]
    print(df[available_cols].head(10).to_string(index=False))

    # =========================================================================
    # 4. 주요 통계
    # =========================================================================
    print_section("4. 주요 통계")

    # 4-1. 전체 요약 통계
    print("\n📈 전체 요약 통계:")
    stats = tx.get_summary_stats()
    print(f"  - 데이터 건수: {int(stats['count'].iloc[0]):,}")
    print(f"  - 평균: {stats['mean'].iloc[0]:,.0f}")
    print(f"  - 표준편차: {stats['std'].iloc[0]:,.0f}")
    print(f"  - 최소값: {stats['min'].iloc[0]:,.0f}")
    print(f"  - 최대값: {stats['max'].iloc[0]:,.0f}")

    # 4-2. 연도별 전국 인구
    print("\n📊 연도별 전국 인구:")
    nation_data = tx.filter_by(Fields.C1_NM, "전국")
    for row in nation_data.to_records():
        print(f"  {row['PRD_DE']}: {row['DT']:,.0f} 명")

    # 4-3. 지역별 인구 순위 (2023년)
    print("\n🏆 지역별 인구 순위 (2023년, 상위 10개):")
    data_2023 = tx.filter_by(Fields.PERIOD, "2023")
    ranked = data_2023.rank_by(Fields.VALUE, top_n=10)
    for idx, row in enumerate(ranked.to_dict("records"), 1):
        print(f"  {idx}. {row['C1_NM']}: {row['DT']:,.0f} 명")

    # 4-4. 인구 증감률
    print("\n📉 전국 인구 증감률:")
    nation_growth = nation_data.calculate_growth()
    for row in nation_growth.to_dict("records")[1:]:  # 첫 해는 증감률 없음
        pct = row.get("growth_pct", 0)
        symbol = "↗️" if pct > 0 else "↘️" if pct < 0 else "→"
        print(f"  {row['PRD_DE']}: {pct:+.2f}% {symbol}")

    # =========================================================================
    # 5. 시각화
    # =========================================================================
    print_section("5. 시각화 생성")

    viz = KosisVisualizer()
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # 5-1. 전국 인구 추이 라인 차트
    print("\n📈 전국 인구 추이 차트 생성...")
    fig1 = viz.line_chart(
        nation_data.to_records(),
        x=Fields.PERIOD,
        y=Fields.VALUE,
        title="대한민국 인구 추이 (2019-2023)",
        xaxis_title="연도",
        yaxis_title="인구수 (명)",
    )
    path1 = viz.save_chart(fig1, output_dir / "population_trend.html")
    print(f"  ✅ 저장: {path1}")

    # 5-2. 주요 지역 인구 비교 (2023)
    print("\n📊 주요 지역 인구 비교 차트 생성...")
    major_regions = ["전국", "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시"]
    regional_2023 = tx.filter_by(Fields.PERIOD, "2023").filter_by(Fields.C1_NM, major_regions)

    fig2 = viz.bar_chart(
        regional_2023.to_records(),
        x=Fields.C1_NM,
        y=Fields.VALUE,
        title="주요 지역 인구 비교 (2023년)",
        xaxis_title="지역",
        yaxis_title="인구수 (명)",
    )
    path2 = viz.save_chart(fig2, output_dir / "regional_comparison.html")
    print(f"  ✅ 저장: {path2}")

    # 5-3. 주요 지역 연도별 추이
    print("\n📈 주요 지역 연도별 추이 차트 생성...")
    regional_trend = tx.filter_by(Fields.C1_NM, major_regions[1:])  # 전국 제외

    fig3 = viz.line_chart(
        regional_trend.to_records(),
        x=Fields.PERIOD,
        y=Fields.VALUE,
        color=Fields.C1_NM,
        title="주요 지역 인구 추이 (2019-2023)",
        xaxis_title="연도",
        yaxis_title="인구수 (명)",
    )
    path3 = viz.save_chart(fig3, output_dir / "regional_trend.html")
    print(f"  ✅ 저장: {path3}")

    # 5-4. 인구 구성 파이 차트
    print("\n🥧 지역 인구 구성 파이 차트 생성...")
    fig4 = viz.pie_chart(
        regional_2023.filter_by(Fields.C1_NM, major_regions[1:]).to_records(),
        values=Fields.VALUE,
        names=Fields.C1_NM,
        title="주요 지역 인구 구성비 (2023년)",
        hole=0.4,
    )
    path4 = viz.save_chart(fig4, output_dir / "regional_pie.html")
    print(f"  ✅ 저장: {path4}")

    # =========================================================================
    # 6. 인사이트
    # =========================================================================
    print_section("6. 인사이트")

    insights = """
    📍 주요 발견사항:

    1️⃣ 인구 감소 추세
       - 2019년 이후 지속적인 인구 감소 추세
       - 저출산 및 고령화 영향

    2️⃣ 수도권 집중 현상
       - 서울 + 수도권이 전체 인구의 약 50% 차지
       - 지방 인구 유출 지속

    3️⃣ 지역별 격차
       - 광역시 인구: 서울 > 부산 > 인천 > 대구 순
       - 특별시/광역시 외 지역은 상대적 감소세

    💡 시사점:
       - 저출산 대책 및 지방 활성화 정책 필요
       - 인구 이동 패턴 모니터링 중요
       - 세대별 인구 구조 변화 주시 필요
    """
    print(insights)

    # =========================================================================
    # 7. LLM 컨텍스트
    # =========================================================================
    print_section("7. LLM 컨텍스트")

    context = get_llm_context(records)
    print(context[:1500] + "..." if len(context) > 1500 else context)

    # =========================================================================
    # 완료
    # =========================================================================
    print("\n" + "=" * 60)
    print("✅ 인구 통계 분석 완료!")
    print(f"📁 출력 파일: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
