"""
동적 데이터 분석 갤러리.

이 스크립트는 유저 인풋을 받아 동적으로 KOSIS 데이터 분석 리포트를 생성합니다.
LLM이 호출하거나 CLI에서 직접 실행할 수 있습니다.

사용 방법:
    # CLI 대화형 모드
    uv run python examples/gallery/dynamic_analysis.py

    # 쿼리 직접 지정
    uv run python examples/gallery/dynamic_analysis.py "서울과 부산 인구 비교"

    # 특정 지표로 분석
    uv run python examples/gallery/dynamic_analysis.py --indicator population "2020-2023 인구 추이"

LLM 통합 예시:
    >>> from kosis_tools import StatisticsData, create_report, create_llm_prompt
    >>>
    >>> # 데이터 조회
    >>> data = StatisticsData().get_data("101", "DT_1B040A3", "2019", "2023")
    >>>
    >>> # 유저 쿼리로 리포트 생성
    >>> report = create_report(data, "서울 인구 변화 분석")
    >>> print(report)
    >>>
    >>> # LLM 프롬프트 생성
    >>> prompt = create_llm_prompt(data, "지역별 인구 순위")
    >>> # LLM에 prompt 전달
"""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from kosis_tools import StatisticsData, StatisticsSearch
from kosis_tools.report_generator import ReportGenerator, create_report, create_llm_prompt


# 사전 정의된 지표 설정
INDICATORS = {
    "population": {
        "name": "인구 통계",
        "org_id": "101",
        "tbl_id": "DT_1B040A3",
        "description": "행정구역별 인구수",
        "default_period": ("2019", "2023"),
    },
    "cpi": {
        "name": "소비자물가지수",
        "org_id": "101",
        "tbl_id": "DT_1J22001",
        "description": "소비자물가지수 총지수",
        "default_period": ("202201", "202412"),
        "prd_se": "M",
    },
    "employment": {
        "name": "고용 통계",
        "org_id": "101",
        "tbl_id": "DT_1ES2A01",
        "description": "경제활동인구 현황",
        "default_period": ("2019", "2023"),
    },
}


def fetch_data(indicator_key: str, start_date: str = None, end_date: str = None):
    """지표 데이터 조회"""
    indicator = INDICATORS.get(indicator_key)
    if not indicator:
        print(f"❌ 알 수 없는 지표: {indicator_key}")
        print(f"   사용 가능: {', '.join(INDICATORS.keys())}")
        return None

    data_client = StatisticsData()

    start = start_date or indicator["default_period"][0]
    end = end_date or indicator["default_period"][1]
    prd_se = indicator.get("prd_se", "Y")

    print(f"\n📊 데이터 조회 중: {indicator['name']}")
    print(f"   테이블: {indicator['tbl_id']} ({indicator['description']})")
    print(f"   기간: {start} ~ {end}")

    records = data_client.get_data(
        org_id=indicator["org_id"],
        tbl_id=indicator["tbl_id"],
        start_date=start,
        end_date=end,
        prd_se=prd_se,
    )

    if records:
        print(f"   ✅ 조회 완료: {len(records):,}건")
    else:
        print("   ❌ 데이터 조회 실패")

    return records


def interactive_mode():
    """대화형 분석 모드"""
    print("\n" + "=" * 60)
    print("🎯 KOSIS 동적 데이터 분석")
    print("=" * 60)

    # 지표 선택
    print("\n📋 사용 가능한 지표:")
    for key, info in INDICATORS.items():
        print(f"   [{key}] {info['name']} - {info['description']}")

    indicator_key = input("\n지표를 선택하세요 (기본: population): ").strip() or "population"

    # 데이터 조회
    records = fetch_data(indicator_key)
    if not records:
        return

    # 분석 쿼리 입력
    print("\n💬 분석 쿼리 예시:")
    print("   - '서울과 부산 인구 비교해줘'")
    print("   - '2020-2023 인구 추이 분석'")
    print("   - '지역별 인구 순위 알려줘'")
    print("   - '전체 데이터 요약'")

    user_query = input("\n분석 요청을 입력하세요: ").strip()
    if not user_query:
        user_query = "전체 데이터 분석"

    # 출력 디렉토리
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # 리포트 생성
    print("\n" + "=" * 60)
    print("📝 리포트 생성 중...")
    print("=" * 60)

    generator = ReportGenerator(records)

    # 쿼리 파싱 정보 출력
    parsed = generator.parse_user_query(user_query)
    print(f"\n🔍 쿼리 파싱 결과:")
    print(f"   - 대상 지역: {parsed.target_regions or '전체'}")
    print(f"   - 대상 기간: {parsed.target_periods or '전체'}")
    print(f"   - 비교 유형: {parsed.comparison_type}")
    print(f"   - 분석 깊이: {parsed.analysis_depth}")

    # 리포트 생성
    report = generator.generate(
        parsed_query=parsed,
        output_dir=output_dir,
    )

    print("\n" + report)

    # 저장
    report_path = output_dir / "dynamic_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n📁 리포트 저장됨: {report_path}")


def single_query_mode(query: str, indicator_key: str = "population"):
    """단일 쿼리 분석 모드"""
    records = fetch_data(indicator_key)
    if not records:
        return

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    report = create_report(records, query, str(output_dir))
    print(report)

    report_path = output_dir / "dynamic_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\n📁 리포트 저장됨: {report_path}")


def demo_llm_integration():
    """LLM 통합 데모"""
    print("\n" + "=" * 60)
    print("🤖 LLM 통합 데모")
    print("=" * 60)

    # 데이터 조회
    records = fetch_data("population")
    if not records:
        return

    queries = [
        "서울 인구 변화 추이를 분석해주세요",
        "부산과 대구의 인구를 비교해주세요",
        "인구 상위 5개 지역을 알려주세요",
    ]

    for query in queries:
        print(f"\n{'='*50}")
        print(f"💬 유저 쿼리: {query}")
        print("=" * 50)

        # LLM 프롬프트 생성
        prompt = create_llm_prompt(records, query)

        print("\n📄 생성된 LLM 프롬프트 (일부):")
        print("-" * 40)
        print(prompt[:800] + "..." if len(prompt) > 800 else prompt)
        print("-" * 40)

        input("\n[Enter를 눌러 다음 예시로...]")


def main():
    parser = argparse.ArgumentParser(
        description="KOSIS 동적 데이터 분석",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  %(prog)s                                    # 대화형 모드
  %(prog)s "서울 인구 분석"                    # 단일 쿼리
  %(prog)s --indicator cpi "물가 추이 분석"   # 물가 지표
  %(prog)s --demo                             # LLM 통합 데모
        """,
    )
    parser.add_argument("query", nargs="?", help="분석 쿼리 (없으면 대화형 모드)")
    parser.add_argument(
        "--indicator", "-i",
        choices=list(INDICATORS.keys()),
        default="population",
        help="분석할 지표 (기본: population)",
    )
    parser.add_argument("--demo", action="store_true", help="LLM 통합 데모 실행")

    args = parser.parse_args()

    if args.demo:
        demo_llm_integration()
    elif args.query:
        single_query_mode(args.query, args.indicator)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
