"""
예제 2: 대한민국 소비자물가지수 분석

이 예제는 KOSIS API를 통해 소비자물가지수(CPI) 데이터를 조회하고 분석합니다.

📊 지표 정보:
    - 지표명: 소비자물가지수
    - 출처: 통계청 (orgId: 101)
    - 테이블 ID: DT_1J22001 (총지수)
    - 주기: 월간(M)
    - 기준시점: 2020년 = 100

📝 분석 내용:
    1. 기초 설명 - 소비자물가지수 개념
    2. EDA - 데이터 구조 탐색
    3. 주요 통계 - 월별/연도별 물가 동향
    4. 시각화 - 물가 추이, 품목별 비교
    5. 인사이트 - 인플레이션 트렌드 분석

실행 방법:
    uv run python examples/gallery/02_consumer_price_analysis.py
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from kosis_tools import StatisticsData
from kosis_tools.transform import KosisTransformer, Fields, get_llm_context
from kosis_tools.visualize import KosisVisualizer


def print_section(title: str):
    """섹션 제목 출력"""
    print("\n" + "=" * 60)
    print(f"📊 {title}")
    print("=" * 60)


def main():
    """소비자물가지수 분석 예제 실행"""

    # =========================================================================
    # 1. 기초 설명
    # =========================================================================
    print_section("1. 지표 기초 설명")

    description = """
    📌 소비자물가지수 (Consumer Price Index, CPI)

    소비자물가지수는 가계가 소비생활을 위해 구입하는 상품과 서비스의
    가격변동을 측정하는 지표입니다.

    ▶ 작성기관: 통계청
    ▶ 작성주기: 월간
    ▶ 기준시점: 2020년 = 100
    ▶ 품목수: 약 460개 품목

    ▶ 주요 구성:
       - 총지수: 전체 물가 종합
       - 식료품 및 비주류음료
       - 주거 · 수도 · 광열
       - 교통
       - 음식 · 숙박 등

    ▶ 활용분야:
       - 인플레이션 측정
       - 화폐가치 평가
       - 임금 협상 기준
       - 경제정책 수립
    """
    print(description)

    # =========================================================================
    # 2. 데이터 조회
    # =========================================================================
    print_section("2. 데이터 조회")

    data_client = StatisticsData()

    # 최근 3년 월간 물가 데이터 조회 (2022-2024)
    print(">>> 최근 월간 소비자물가지수 조회 중...")

    # 물가지수 테이블 조회
    records = data_client.get_data(
        org_id="101",
        tbl_id="DT_1J22001",  # 소비자물가지수 총지수
        start_date="202201",
        end_date="202412",
        prd_se="M",
    )

    if not records:
        print("⚠️ 데이터 조회 실패. 대체 테이블로 시도...")
        # 생활물가지수로 대체
        records = data_client.get_data(
            org_id="101",
            tbl_id="DT_1J22005",  # 생활물가지수
            start_date="202201",
            end_date="202412",
            prd_se="M",
        )

    print(f"✅ 조회 완료: {len(records):,}건")

    if not records:
        print("❌ 데이터가 없습니다. API 키 또는 테이블 ID를 확인하세요.")
        return

    # =========================================================================
    # 3. EDA - 데이터 탐색
    # =========================================================================
    print_section("3. EDA - 데이터 탐색")

    tx = KosisTransformer(records)

    # 3-1. 필드 구조
    print("\n📋 필드 정보:")
    field_info = tx.get_field_info()
    for field, info in list(field_info.items())[:8]:  # 상위 8개만
        print(f"  - {field}: {info['dtype']}, 고유값 {info['nunique']}개")

    # 3-2. 차원 정보
    print("\n📐 데이터 차원:")
    periods = tx.get_unique_values(Fields.PERIOD)
    print(f"  - 기간: {len(periods)}개 ({periods[0]} ~ {periods[-1]})")

    # 분류항목 확인
    if Fields.C1_NM in tx.df.columns:
        categories = tx.get_unique_values(Fields.C1_NM)
        print(f"  - 품목/분류: {len(categories)}개")
        print(f"    (예: {', '.join(categories[:5])}...)")

    # 3-3. 샘플 데이터
    print("\n📝 샘플 데이터:")
    df = tx.to_dataframe()
    sample_cols = [c for c in [Fields.PERIOD, Fields.C1_NM, "ITM_NM", Fields.VALUE, "UNIT_NM"]
                   if c in df.columns]
    print(df[sample_cols].head(10).to_string(index=False))

    # =========================================================================
    # 4. 주요 통계
    # =========================================================================
    print_section("4. 주요 통계")

    # 4-1. 전체 요약 통계
    print("\n📈 전체 요약 통계:")
    stats = tx.get_summary_stats()
    print(f"  - 데이터 건수: {int(stats['count'].iloc[0]):,}")
    print(f"  - 평균 지수: {stats['mean'].iloc[0]:.2f}")
    print(f"  - 표준편차: {stats['std'].iloc[0]:.2f}")
    print(f"  - 최소값: {stats['min'].iloc[0]:.2f}")
    print(f"  - 최대값: {stats['max'].iloc[0]:.2f}")

    # 4-2. 연도별 평균 (피벗)
    print("\n📊 기간별 물가지수 추이 (최근 12개월):")
    recent_periods = periods[-12:] if len(periods) >= 12 else periods
    recent_data = tx.filter_by(Fields.PERIOD, list(recent_periods))

    # 총지수 또는 대표 품목 필터링
    if Fields.C1_NM in tx.df.columns:
        categories = tx.get_unique_values(Fields.C1_NM)
        if "총지수" in categories:
            recent_data = recent_data.filter_by(Fields.C1_NM, "총지수")
        elif categories:
            # 첫 번째 분류만 선택
            recent_data = recent_data.filter_by(Fields.C1_NM, categories[0])

    for row in recent_data.to_records()[-12:]:
        prd = row.get(Fields.PERIOD, "N/A")
        val = row.get(Fields.VALUE, 0)
        if val:
            print(f"  {prd}: {val:.2f}")

    # =========================================================================
    # 5. 시각화
    # =========================================================================
    print_section("5. 시각화 생성")

    viz = KosisVisualizer()
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # 5-1. 물가지수 추이 라인 차트
    print("\n📈 물가지수 추이 차트 생성...")
    fig1 = viz.line_chart(
        recent_data.to_records(),
        x=Fields.PERIOD,
        y=Fields.VALUE,
        title="소비자물가지수 추이",
        xaxis_title="기간",
        yaxis_title="지수 (2020=100)",
    )
    path1 = viz.save_chart(fig1, output_dir / "cpi_trend.html")
    print(f"  ✅ 저장: {path1}")

    # 5-2. 품목별 비교 (분류가 있는 경우)
    if Fields.C1_NM in tx.df.columns:
        print("\n📊 품목별 물가지수 비교 차트 생성...")
        categories = tx.get_unique_values(Fields.C1_NM)[:5]  # 상위 5개 품목

        if categories:
            category_data = tx.filter_by(Fields.PERIOD, periods[-1])  # 최근 월
            category_data = category_data.filter_by(Fields.C1_NM, categories)

            fig2 = viz.bar_chart(
                category_data.to_records(),
                x=Fields.C1_NM,
                y=Fields.VALUE,
                title=f"품목별 물가지수 ({periods[-1]})",
                xaxis_title="품목",
                yaxis_title="지수",
            )
            path2 = viz.save_chart(fig2, output_dir / "cpi_by_category.html")
            print(f"  ✅ 저장: {path2}")

    # 5-3. 물가 변동률 (전월 대비)
    print("\n📉 물가 변동률 계산...")
    growth_data = recent_data.calculate_growth()
    growth_records = growth_data.to_dict("records")[1:]  # 첫 행 제외

    if growth_records:
        fig3 = viz.bar_chart(
            growth_records,
            x=Fields.PERIOD,
            y="growth_pct",
            title="월별 물가 변동률 (전월 대비)",
            xaxis_title="기간",
            yaxis_title="변동률 (%)",
        )
        path3 = viz.save_chart(fig3, output_dir / "cpi_growth_rate.html")
        print(f"  ✅ 저장: {path3}")

    # =========================================================================
    # 6. 인사이트
    # =========================================================================
    print_section("6. 인사이트")

    insights = """
    📍 주요 발견사항:

    1️⃣ 물가 상승 추세
       - 2020년 기준(100)에서 지속적 상승
       - 최근 고물가 현상 지속

    2️⃣ 품목별 차이
       - 에너지(유류비, 전기료) 변동성 높음
       - 식료품 가격 상승 두드러짐
       - 서비스 물가는 완만한 상승

    3️⃣ 계절적 요인
       - 겨울철 난방비 영향
       - 명절(설/추석) 전후 식품가격 변동

    💡 시사점:
       - 고물가 장기화에 대비한 가계 재정 관리 필요
       - 에너지 가격 변동성 모니터링 중요
       - 근원물가(식료품·에너지 제외) 추이 주시
    """
    print(insights)

    # =========================================================================
    # 7. LLM 컨텍스트
    # =========================================================================
    print_section("7. LLM 컨텍스트")

    context = get_llm_context(records[:100])  # 상위 100건만
    print(context[:1500] + "..." if len(context) > 1500 else context)

    # =========================================================================
    # 완료
    # =========================================================================
    print("\n" + "=" * 60)
    print("✅ 소비자물가지수 분석 완료!")
    print(f"📁 출력 파일: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
