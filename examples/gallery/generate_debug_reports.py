#!/usr/bin/env python3
"""
하이브리드 디버그 리포트 생성기.

MCP 호출 + 하드코딩 데이터를 조합하여 다양한 시나리오의
디버그 정보가 포함된 리포트를 생성합니다.

사용법:
    # 하드코딩 시나리오만 생성 (기본, 빠름)
    uv run python examples/gallery/generate_debug_reports.py

    # MCP 시나리오도 포함 (실제 API 호출)
    uv run python examples/gallery/generate_debug_reports.py --include-mcp

    # 특정 시나리오만
    uv run python examples/gallery/generate_debug_reports.py --scenario sample_trend

    # 모든 시나리오 목록
    uv run python examples/gallery/generate_debug_reports.py --list

출력:
    examples/gallery/output/
    ├── {scenario_id}.html
    ├── {scenario_id}.debug.json
    ├── ...
    └── manifest.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from scenarios import HARDCODED_SCENARIOS, MCP_SCENARIOS, SAMPLE_DATASETS


def generate_hardcoded_report(
    scenario_id: str,
    config: Dict,
    output_dir: Path,
) -> Optional[str]:
    """하드코딩된 데이터로 리포트 생성"""
    from kosis_tools import ReportGenerator

    data_key = config.get("data_key")
    if data_key not in SAMPLE_DATASETS:
        print(f"  ❌ 알 수 없는 데이터 키: {data_key}")
        return None

    data = SAMPLE_DATASETS[data_key]

    # 빈 데이터 처리
    if not data:
        print(f"  ⚠️  빈 데이터셋 - 스킵: {scenario_id}")
        # 빈 데이터용 더미 디버그 파일 생성
        debug_info = {
            "report_id": f"edge_{scenario_id}",
            "timestamp": "N/A",
            "user_query": config["query"],
            "parsed_query": {
                "raw_query": config["query"],
                "target_regions": [],
                "target_periods": [],
                "comparison_type": "unknown",
                "analysis_depth": "standard",
                "include_visualization": True,
            },
            "sections_determined": [],
            "processing_steps": [
                {"step": "check_data", "detail": "빈 데이터셋 감지", "duration_ms": 0}
            ],
            "data_info": {
                "total_records": 0,
                "filtered_records": 0,
                "columns": [],
                "unique_regions": 0,
                "unique_periods": 0,
            },
            "output_path": f"{scenario_id}.html",
            "total_duration_ms": 0,
            "error": "Empty dataset - no report generated"
        }

        debug_path = output_dir / f"{scenario_id}.debug.json"
        debug_path.write_text(
            json.dumps(debug_info, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return None

    print(f"  📊 데이터: {len(data)}건")

    try:
        generator = ReportGenerator(data)
        output_path = output_dir / f"{scenario_id}.html"

        result = generator.generate_html(
            user_query=config["query"],
            output_path=output_path,
            title=f"{config['name']}",
            save_debug_info=True,
        )

        print(f"  ✅ 생성: {result}")
        return result

    except Exception as e:
        print(f"  ❌ 오류: {e}")

        # 오류 시 디버그 파일 생성
        debug_info = {
            "report_id": f"error_{scenario_id}",
            "timestamp": "N/A",
            "user_query": config["query"],
            "error": str(e),
            "output_path": f"{scenario_id}.html",
        }

        debug_path = output_dir / f"{scenario_id}.debug.json"
        debug_path.write_text(
            json.dumps(debug_info, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        return None


def generate_mcp_report(
    scenario_id: str,
    config: Dict,
    output_dir: Path,
) -> Optional[str]:
    """MCP를 통해 실제 데이터를 조회하고 리포트 생성"""
    from kosis_tools import StatisticsData, ReportGenerator

    print(f"  📡 API 호출: {config['org_id']}/{config['tbl_id']}")

    try:
        data_client = StatisticsData()
        records = data_client.get_data(
            org_id=config["org_id"],
            tbl_id=config["tbl_id"],
            start_date=config["start_date"],
            end_date=config["end_date"],
            prd_se=config.get("prd_se", "Y"),
        )

        if not records:
            print(f"  ⚠️  데이터 없음")
            return None

        print(f"  📊 데이터: {len(records)}건")

        generator = ReportGenerator(records)
        output_path = output_dir / f"{scenario_id}.html"

        result = generator.generate_html(
            user_query=config["query"],
            output_path=output_path,
            title=f"{config['name']}",
            save_debug_info=True,
        )

        print(f"  ✅ 생성: {result}")
        return result

    except Exception as e:
        print(f"  ❌ 오류: {e}")
        return None


def generate_manifest(output_dir: Path, generated_reports: List[Dict]) -> str:
    """manifest.json 파일 생성"""
    manifest = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "total_reports": len(generated_reports),
        "reports": generated_reports,
    }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return str(manifest_path)


def list_scenarios():
    """모든 시나리오 목록 출력"""
    print("\n📋 하드코딩 시나리오:")
    print("-" * 60)
    for sid, config in HARDCODED_SCENARIOS.items():
        print(f"  [{sid}] {config['name']}")
        print(f"      카테고리: {config['category']}, 쿼리: {config['query'][:40]}...")

    print("\n📡 MCP 시나리오:")
    print("-" * 60)
    for sid, config in MCP_SCENARIOS.items():
        print(f"  [{sid}] {config['name']}")
        print(f"      테이블: {config['tbl_id']}, 쿼리: {config['query'][:40]}...")


def main():
    parser = argparse.ArgumentParser(
        description="KOSIS 디버그 리포트 생성기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  %(prog)s                           # 하드코딩 시나리오만 (기본)
  %(prog)s --include-mcp             # MCP 시나리오 포함
  %(prog)s --scenario sample_trend   # 특정 시나리오만
  %(prog)s --list                    # 시나리오 목록
        """,
    )
    parser.add_argument(
        "--scenario", "-s",
        help="특정 시나리오 ID만 생성",
    )
    parser.add_argument(
        "--include-mcp", "-m",
        action="store_true",
        help="MCP 시나리오도 포함 (실제 API 호출)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="출력 디렉토리 (기본: examples/gallery/output)",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="시나리오 목록 출력",
    )

    args = parser.parse_args()

    if args.list:
        list_scenarios()
        return

    # 출력 디렉토리
    output_dir = Path(args.output) if args.output else Path(__file__).parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("🎨 KOSIS 디버그 리포트 생성기")
    print("=" * 60)

    generated_reports = []

    # 특정 시나리오만
    if args.scenario:
        if args.scenario in HARDCODED_SCENARIOS:
            config = HARDCODED_SCENARIOS[args.scenario]
            print(f"\n📝 [{args.scenario}] {config['name']}")
            result = generate_hardcoded_report(args.scenario, config, output_dir)
            if result:
                generated_reports.append({
                    "id": args.scenario,
                    "name": config["name"],
                    "category": config["category"],
                    "type": "hardcoded",
                })
        elif args.scenario in MCP_SCENARIOS:
            config = MCP_SCENARIOS[args.scenario]
            print(f"\n📝 [{args.scenario}] {config['name']}")
            result = generate_mcp_report(args.scenario, config, output_dir)
            if result:
                generated_reports.append({
                    "id": args.scenario,
                    "name": config["name"],
                    "category": config["category"],
                    "type": "mcp",
                })
        else:
            print(f"❌ 알 수 없는 시나리오: {args.scenario}")
            print("사용 가능한 시나리오를 보려면 --list 옵션을 사용하세요.")
            return

    else:
        # 하드코딩 시나리오 생성
        print("\n📦 하드코딩 시나리오 생성")
        print("-" * 40)
        for scenario_id, config in HARDCODED_SCENARIOS.items():
            print(f"\n📝 [{scenario_id}] {config['name']}")
            result = generate_hardcoded_report(scenario_id, config, output_dir)
            if result:
                generated_reports.append({
                    "id": scenario_id,
                    "name": config["name"],
                    "category": config["category"],
                    "type": "hardcoded",
                })

        # MCP 시나리오 생성 (옵션)
        if args.include_mcp:
            print("\n📡 MCP 시나리오 생성")
            print("-" * 40)
            for scenario_id, config in MCP_SCENARIOS.items():
                print(f"\n📝 [{scenario_id}] {config['name']}")
                result = generate_mcp_report(scenario_id, config, output_dir)
                if result:
                    generated_reports.append({
                        "id": scenario_id,
                        "name": config["name"],
                        "category": config["category"],
                        "type": "mcp",
                    })

    # manifest.json 생성
    if generated_reports:
        manifest_path = generate_manifest(output_dir, generated_reports)
        print(f"\n📁 Manifest: {manifest_path}")

    print("\n" + "=" * 60)
    print(f"✅ 총 {len(generated_reports)}개 리포트 생성 완료")
    print(f"📂 출력 디렉토리: {output_dir}")
    print("=" * 60)

    # 디버그 뷰어 안내
    print("\n💡 디버그 뷰어 실행 방법:")
    print(f"   cd {output_dir.parent}")
    print("   python -m http.server 8080")
    print("   → http://localhost:8080/debug_viewer.html 에서 확인")


if __name__ == "__main__":
    main()
