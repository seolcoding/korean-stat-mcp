#!/usr/bin/env python3
"""
MCP 패턴 활용 예시.

이 스크립트는 KOSIS MCP 서버의 모범적인 사용 패턴을 보여줍니다.
LLM이 어떻게 MCP 도구들을 호출하는지 시뮬레이션합니다.

핵심 원칙:
  - 데이터는 서버에, 요약만 모델에
  - summary → sample → chunk 순으로 점진적 공개
  - 서버사이드 처리 우선, 결과만 반환

사용법:
    uv run python examples/mcp_pattern_examples.py
    uv run python examples/mcp_pattern_examples.py --scenario drill_down
    uv run python examples/mcp_pattern_examples.py --all
    uv run python examples/mcp_pattern_examples.py --live  # 실제 API 호출
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from kosis_tools.report_tools import (
    filter_data,
    aggregate_data,
    analyze_trend,
    analyze_comparison,
    analyze_ranking,
    save_raw_data,
    load_raw_data,
    format_data_for_llm,
)

# API 키 확인
USE_LIVE_API = bool(os.environ.get("KOSIS_API_KEY"))


def get_mock_data() -> list[dict]:
    """모의 인구 데이터 생성."""
    regions = [
        "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시",
        "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원도",
        "충청북도", "충청남도", "전라북도", "전라남도", "경상북도", "경상남도", "제주특별자치도",
    ]
    years = ["2019", "2020", "2021", "2022", "2023"]

    # 기준 인구 (2023년)
    base_pop = {
        "서울특별시": 9411000, "부산광역시": 3314000, "대구광역시": 2357000,
        "인천광역시": 2978000, "광주광역시": 1433000, "대전광역시": 1445000,
        "울산광역시": 1106000, "세종특별자치시": 387000, "경기도": 13639000,
        "강원도": 1525000, "충청북도": 1598000, "충청남도": 2125000,
        "전라북도": 1763000, "전라남도": 1815000, "경상북도": 2597000,
        "경상남도": 3273000, "제주특별자치도": 674000,
    }

    records = []
    for year_idx, year in enumerate(years):
        for region in regions:
            # 연도별 변동 시뮬레이션
            pop = base_pop.get(region, 1000000)
            variation = 1 - (4 - year_idx) * 0.005  # 과거로 갈수록 약간 감소
            value = int(pop * variation)

            records.append({
                "TBL_ID": "DT_1B040A3",
                "TBL_NM": "행정구역(시도)별 인구수",
                "PRD_DE": year,
                "C1_NM": region,
                "ITM_NM": "인구수",
                "DT": str(value),
                "UNIT_NM": "명",
            })

    return records


def get_data(use_live: bool = False) -> list[dict]:
    """데이터 조회 (실제 API 또는 모의 데이터)."""
    if use_live and USE_LIVE_API:
        from kosis_tools import StatisticsData
        client = StatisticsData()
        return client.get_data(
            org_id="101",
            tbl_id="DT_1B040A3",
            start_date="2019",
            end_date="2023",
            prd_se="Y",
        ) or []
    return get_mock_data()


def print_header(title: str) -> None:
    """섹션 헤더 출력."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_json(data: dict, max_items: int = 5) -> None:
    """JSON 예쁘게 출력 (데이터 제한)."""
    # data 배열이 있으면 제한
    if isinstance(data, dict) and "data" in data:
        data = data.copy()
        if isinstance(data["data"], list) and len(data["data"]) > max_items:
            data["data"] = data["data"][:max_items]
            data["_truncated"] = f"...외 {len(data['data']) - max_items}건"
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


# =============================================================================
# 시나리오 1: 기본 워크플로우 (DISCOVER → FETCH → PRESENT)
# =============================================================================

def scenario_basic_workflow(use_live: bool = False):
    """
    기본 워크플로우 시나리오.

    LLM이 데이터를 탐색하고, 조회하고, 분석하는 전체 흐름을 보여줍니다.
    """
    print_header("시나리오 1: 기본 워크플로우 (DISCOVER → FETCH → PRESENT)")

    # ─────────────────────────────────────────────
    # Step 1: DISCOVER - 통계표 검색
    # ─────────────────────────────────────────────
    print("\n📌 Step 1: DISCOVER - 통계표 검색")
    print("   LLM 호출: search_statistics('인구')")

    # 모의 검색 결과
    tables = [
        {"TBL_NM": "행정구역(시도)별 인구수", "TBL_ID": "DT_1B040A3"},
        {"TBL_NM": "시군구별 인구동향", "TBL_ID": "DT_1B8000I"},
        {"TBL_NM": "인구동태통계", "TBL_ID": "DT_1B040B1"},
    ]

    print(f"\n   결과: {len(tables)}개 통계표 발견")
    for t in tables:
        print(f"   - {t.get('TBL_NM', '')} ({t.get('TBL_ID', '')})")

    # ─────────────────────────────────────────────
    # Step 2: FETCH - 요약 먼저 조회 (MCP 패턴!)
    # ─────────────────────────────────────────────
    print("\n📌 Step 2: FETCH - 요약 먼저 조회 (view='summary')")
    print("   LLM 호출: get_statistics_data('101', 'DT_1B040A3', '2019', '2023', view='summary')")

    records = get_data(use_live)

    if records:
        # view="summary" 시뮬레이션
        periods = sorted(set(r.get("PRD_DE", "") for r in records))
        regions = sorted(set(r.get("C1_NM", "") for r in records if r.get("C1_NM")))

        summary = {
            "status": "summary",
            "total_records": len(records),
            "metadata": {"org_id": "101", "tbl_id": "DT_1B040A3", "period_range": "2019~2023"},
            "dimensions": {
                "periods": periods,
                "regions_count": len(regions),
                "regions_preview": regions[:5],
            },
            "hint": "상세 데이터가 필요하면 view='sample' 또는 view='chunk' 사용",
        }

        print("\n   응답 (토큰 절약!):")
        print_json(summary)

    # ─────────────────────────────────────────────
    # Step 3: PRESENT - 서버사이드 분석
    # ─────────────────────────────────────────────
    print("\n📌 Step 3: PRESENT - 서버사이드 분석")
    print("   LLM 호출: analyze_data_trend(data)")

    if records:
        trend = analyze_trend(records)
        print("\n   분석 결과 (데이터 없이 인사이트만!):")
        print(f"   - 유형: {trend.type}")
        print(f"   - 발견: {trend.findings[:2]}")
        print(f"   - 해석: {trend.interpretation[:100]}...")


# =============================================================================
# 시나리오 2: 점진적 Drill-down (summary → sample → chunk)
# =============================================================================

def scenario_drill_down(use_live: bool = False):
    """
    점진적 Drill-down 시나리오.

    MCP 패턴의 핵심: 처음부터 전체 데이터를 가져오지 않고,
    필요한 만큼만 점진적으로 확장합니다.
    """
    print_header("시나리오 2: 점진적 Drill-down (summary → sample → chunk)")

    records = get_data(use_live)

    if not records:
        print("❌ 데이터 조회 실패")
        return

    total = len(records)

    # ─────────────────────────────────────────────
    # Level 1: Summary (최소 토큰)
    # ─────────────────────────────────────────────
    print("\n📌 Level 1: summary (최소 토큰)")
    print(f"   전체 {total}건 중 메타데이터만 반환")

    periods = sorted(set(r.get("PRD_DE", "") for r in records))
    regions = sorted(set(r.get("C1_NM", "") for r in records if r.get("C1_NM")))
    values = [float(r.get("DT", 0)) for r in records if r.get("DT", "").replace("-", "").isdigit()]

    summary_response = {
        "status": "summary",
        "total_records": total,
        "periods": periods,
        "regions_count": len(regions),
        "statistics": {
            "mean": round(sum(values) / len(values), 0) if values else 0,
            "min": min(values) if values else 0,
            "max": max(values) if values else 0,
        },
        "estimated_tokens": "~500 tokens",  # 실제 데이터 없음
    }
    print_json(summary_response)

    # ─────────────────────────────────────────────
    # Level 2: Sample (중간 토큰)
    # ─────────────────────────────────────────────
    print("\n📌 Level 2: sample (중간 토큰)")
    print(f"   전체 {total}건 중 최근 20건 샘플 반환")

    sample = sorted(records, key=lambda x: x.get("PRD_DE", ""), reverse=True)[:5]

    sample_response = {
        "status": "sample",
        "total_records": total,
        "sample_count": 5,
        "data": [{k: v for k, v in r.items() if k in ["PRD_DE", "C1_NM", "DT", "ITM_NM"]} for r in sample],
        "estimated_tokens": "~2,500 tokens",
    }
    print_json(sample_response)

    # ─────────────────────────────────────────────
    # Level 3: Chunk (페이지네이션)
    # ─────────────────────────────────────────────
    print("\n📌 Level 3: chunk (페이지네이션)")
    chunk_size = 50
    total_chunks = (total + chunk_size - 1) // chunk_size
    print(f"   전체 {total}건을 {chunk_size}건씩 {total_chunks}청크로 분할")

    chunk_response = {
        "status": "chunk",
        "chunk_index": 0,
        "chunk_size": min(chunk_size, total),
        "total_chunks": total_chunks,
        "total_records": total,
        "has_more": True,
        "next_hint": "chunk_index=1로 다음 청크 조회",
        "data": [{"PRD_DE": r.get("PRD_DE"), "C1_NM": r.get("C1_NM"), "DT": r.get("DT")} for r in records[:3]],
        "_data_truncated": f"...외 {chunk_size - 3}건",
    }
    print_json(chunk_response)


# =============================================================================
# 시나리오 3: 서버사이드 처리 (Server-Side Processing)
# =============================================================================

def scenario_server_side(use_live: bool = False):
    """
    서버사이드 처리 시나리오.

    대용량 데이터를 LLM에 보내지 않고,
    서버에서 필터링/집계 후 결과만 반환합니다.
    """
    print_header("시나리오 3: 서버사이드 처리 (Server-Side Processing)")

    records = get_data(use_live)

    if not records:
        print("❌ 데이터 조회 실패")
        return

    print(f"\n   원본 데이터: {len(records)}건 (서버 메모리에만 존재)")

    # ─────────────────────────────────────────────
    # 서버사이드 필터링
    # ─────────────────────────────────────────────
    print("\n📌 서버사이드 필터링")
    print("   LLM 호출: filter_statistics_data(data, regions=['서울특별시', '부산광역시'])")

    filtered = filter_data(records, regions=["서울특별시", "부산광역시"])

    print(f"\n   결과: {len(records)}건 → {len(filtered)}건 (필터 후)")
    print(f"   토큰 절감: {(1 - len(filtered)/len(records)) * 100:.1f}%")

    # ─────────────────────────────────────────────
    # 서버사이드 집계
    # ─────────────────────────────────────────────
    print("\n📌 서버사이드 집계")
    print("   LLM 호출: aggregate_statistics_data(data, group_by='PRD_DE', agg_func='sum')")

    aggregated = aggregate_data(records, group_by="PRD_DE", agg_func="sum")

    print(f"\n   결과: {len(records)}건 → {len(aggregated)}건 (집계 후)")
    print("   집계 결과:")
    for row in aggregated[:3]:
        print(f"     {row.get('PRD_DE')}: {float(row.get('DT', 0)):,.0f}")

    # ─────────────────────────────────────────────
    # 서버사이드 분석
    # ─────────────────────────────────────────────
    print("\n📌 서버사이드 분석")
    print("   LLM 호출: analyze_data_ranking(data, top_n=5)")

    ranking = analyze_ranking(records, top_n=5, period="2023")

    print("\n   순위 분석 결과:")
    for finding in ranking.findings[:5]:
        print(f"     {finding}")


# =============================================================================
# 시나리오 4: 데이터 저장 및 재사용
# =============================================================================

def scenario_data_storage(use_live: bool = False):
    """
    데이터 저장 및 재사용 시나리오.

    view="full"로 조회한 데이터는 자동 저장되며,
    나중에 data_id로 다시 접근할 수 있습니다.
    """
    print_header("시나리오 4: 데이터 저장 및 재사용")

    records = get_data(use_live)

    if not records:
        print("❌ 데이터 조회 실패")
        return

    # ─────────────────────────────────────────────
    # 데이터 저장
    # ─────────────────────────────────────────────
    print("\n📌 데이터 저장 (view='full' 호출 시 자동)")
    print("   LLM 호출: get_statistics_data(..., view='full')")

    storage_info = save_raw_data(records)

    print("\n   저장 결과:")
    print_json(storage_info)

    # ─────────────────────────────────────────────
    # 저장된 데이터 청크 조회
    # ─────────────────────────────────────────────
    print("\n📌 저장된 데이터 청크 조회")
    data_id = storage_info.get("data_id")
    print(f"   LLM 호출: read_stored_data('{data_id}', chunk_index=0)")

    chunk_result = load_raw_data(data_id, chunk_index=0, chunk_size=10)

    print("\n   청크 조회 결과:")
    if "chunk_info" in chunk_result:
        print(f"   - 청크 인덱스: {chunk_result['chunk_info']['chunk_index']}")
        print(f"   - 전체 청크 수: {chunk_result['chunk_info']['total_chunks']}")
        print(f"   - 다음 청크 있음: {chunk_result['chunk_info']['has_more']}")


# =============================================================================
# 시나리오 5: 토큰 효율성 비교
# =============================================================================

def scenario_token_efficiency(use_live: bool = False):
    """
    토큰 효율성 비교 시나리오.

    동일한 데이터에 대해 각 view 옵션의 토큰 사용량을 비교합니다.
    """
    print_header("시나리오 5: 토큰 효율성 비교")

    records = get_data(use_live)

    if not records:
        print("❌ 데이터 조회 실패")
        return

    total = len(records)

    # 각 view의 예상 응답 크기 계산
    full_json = json.dumps(records, ensure_ascii=False)
    full_tokens = len(full_json) // 4  # 대략적인 토큰 수

    # format_data_for_llm 사용
    llm_format = format_data_for_llm(records, max_rows=50, save_raw=False)
    llm_json = json.dumps(llm_format, ensure_ascii=False)
    llm_tokens = len(llm_json) // 4

    # summary만
    summary_data = {
        "total_records": total,
        "periods": sorted(set(r.get("PRD_DE", "") for r in records)),
        "regions_count": len(set(r.get("C1_NM", "") for r in records)),
        "statistics": {"mean": 1234567, "min": 100, "max": 9999999},
    }
    summary_json = json.dumps(summary_data, ensure_ascii=False)
    summary_tokens = len(summary_json) // 4

    # 청크 (50건)
    chunk_data = records[:50]
    chunk_json = json.dumps(chunk_data, ensure_ascii=False)
    chunk_tokens = len(chunk_json) // 4

    # 결과 출력
    print(f"\n   원본 데이터: {total}건")
    print("\n   ┌─────────────────────────────────────────────────────────────┐")
    print("   │        패턴        │   토큰    │   절감률   │     권장       │")
    print("   ├─────────────────────────────────────────────────────────────┤")
    print(f"   │ view='full'       │ {full_tokens:>7,} │     -     │  ⚠️ 주의     │")
    print(f"   │ format_data_for_llm │ {llm_tokens:>7,} │  {(1-llm_tokens/full_tokens)*100:>5.1f}%  │  ✅ 좋음     │")
    print(f"   │ view='chunk' (50건) │ {chunk_tokens:>7,} │  {(1-chunk_tokens/full_tokens)*100:>5.1f}%  │  ✅ 좋음     │")
    print(f"   │ view='summary'    │ {summary_tokens:>7,} │  {(1-summary_tokens/full_tokens)*100:>5.1f}%  │  ⭐ 최적     │")
    print("   └─────────────────────────────────────────────────────────────┘")

    print("\n   💡 권장 워크플로우:")
    print("      1. summary로 개요 파악")
    print("      2. 필요시 sample로 데이터 확인")
    print("      3. 분석 필요시 서버사이드 analyze_* 사용")
    print("      4. 전체 데이터 필요시에만 view='full' (자동 저장됨)")


# =============================================================================
# 시나리오 6: 실제 LLM 대화 시뮬레이션
# =============================================================================

def scenario_llm_conversation(use_live: bool = False):
    """
    실제 LLM 대화 시뮬레이션.

    사용자 질문에 대해 LLM이 어떻게 MCP 도구를 호출하는지 보여줍니다.
    """
    print_header("시나리오 6: LLM 대화 시뮬레이션")

    print("\n👤 사용자: 2019~2023년 전국 인구 추이를 분석해줘")

    print("\n🤖 LLM 사고 과정:")
    print("   1. 인구 관련 통계표 검색 필요 → search_statistics('인구')")
    print("   2. 데이터 구조 확인 필요 → get_statistics_data(..., view='summary')")
    print("   3. 추세 분석 → analyze_data_trend(data)")
    print("   4. 시각화 생성 → create_quick_report(data)")

    records = get_data(use_live)

    if not records:
        print("❌ 데이터 조회 실패")
        return

    print("\n📡 MCP 도구 호출 로그:")

    # Step 1
    print("\n   [1] search_statistics('인구') → 5개 테이블 발견")

    # Step 2
    print("\n   [2] get_statistics_data('101', 'DT_1B040A3', '2019', '2023', view='summary')")
    print(f"       → {len(records)}건 데이터, 요약만 반환 (토큰 절약)")

    # Step 3
    trend = analyze_trend(records)
    print("\n   [3] analyze_data_trend(data)")
    print(f"       → 추세: {trend.findings[0] if trend.findings else 'N/A'}")

    # Step 4
    print("\n   [4] create_quick_report(data, '인구 추이 분석')")
    print("       → HTML 리포트 생성 (차트 + 인사이트)")

    print("\n🤖 LLM 응답:")
    print("   2019~2023년 전국 인구 추이 분석 결과입니다.")
    if trend.findings:
        for finding in trend.findings[:3]:
            print(f"   • {finding}")
    print(f"   \n   {trend.interpretation[:150]}...")


# =============================================================================
# 메인
# =============================================================================

SCENARIOS = {
    "basic": ("기본 워크플로우", scenario_basic_workflow),
    "drill_down": ("점진적 Drill-down", scenario_drill_down),
    "server_side": ("서버사이드 처리", scenario_server_side),
    "storage": ("데이터 저장/재사용", scenario_data_storage),
    "token": ("토큰 효율성 비교", scenario_token_efficiency),
    "conversation": ("LLM 대화 시뮬레이션", scenario_llm_conversation),
}


def main():
    parser = argparse.ArgumentParser(
        description="MCP 패턴 활용 예시",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  %(prog)s                           # 모든 시나리오 실행 (모의 데이터)
  %(prog)s --scenario basic          # 기본 워크플로우만
  %(prog)s --scenario token          # 토큰 효율성 비교만
  %(prog)s --live                    # 실제 API 호출 (KOSIS_API_KEY 필요)
  %(prog)s --list                    # 시나리오 목록
        """,
    )
    parser.add_argument(
        "--scenario", "-s",
        choices=list(SCENARIOS.keys()),
        help="실행할 시나리오",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="모든 시나리오 실행",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="실제 KOSIS API 호출 (KOSIS_API_KEY 환경변수 필요)",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="시나리오 목록 출력",
    )

    args = parser.parse_args()

    if args.list:
        print("\n📋 사용 가능한 시나리오:")
        for key, (name, _) in SCENARIOS.items():
            print(f"   {key:15} - {name}")
        return

    use_live = args.live and USE_LIVE_API
    data_mode = "실제 API" if use_live else "모의 데이터"

    print("=" * 70)
    print("  🚀 KOSIS MCP 패턴 활용 예시")
    print("  핵심: 데이터는 서버에, 요약만 모델에!")
    print(f"  데이터: {data_mode}")
    print("=" * 70)

    if args.scenario:
        name, func = SCENARIOS[args.scenario]
        func(use_live)
    elif args.all or not args.scenario:
        for key, (name, func) in SCENARIOS.items():
            try:
                func(use_live)
            except Exception as e:
                print(f"\n❌ 시나리오 '{key}' 실패: {e}")

    print("\n" + "=" * 70)
    print("  ✅ 완료")
    print("=" * 70)


if __name__ == "__main__":
    main()
