#!/usr/bin/env python3
"""
KOSIS API 샘플 테스트.

무작위로 선별한 테이블을 테스트하여 전체 성공률 추정.
"""

import asyncio
import json
import random
import sys
import time
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
import argparse

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from kosis_tools.data import StatisticsData
from kosis_tools.table_meta import TableMetadata


async def test_table(data: StatisticsData, table: Dict[str, Any]) -> Dict[str, Any]:
    """단일 테이블 테스트."""
    tbl_id = table.get("tbl_id", "")
    org_id = table.get("org_id", "")
    prd_se = table.get("prd_se", "Y")

    start_time = time.time()
    try:
        result = await asyncio.to_thread(
            data.get_data_with_smart_retry,
            org_id, tbl_id
        )
        elapsed = time.time() - start_time

        if result and len(result) > 0:
            return {
                "success": True,
                "tbl_id": tbl_id,
                "org_id": org_id,
                "prd_se": prd_se,
                "count": len(result),
                "elapsed": round(elapsed, 2)
            }
        else:
            return {
                "success": False,
                "tbl_id": tbl_id,
                "org_id": org_id,
                "prd_se": prd_se,
                "error": "no_data",
                "elapsed": round(elapsed, 2)
            }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "success": False,
            "tbl_id": tbl_id,
            "org_id": org_id,
            "prd_se": prd_se,
            "error": str(e)[:100],
            "elapsed": round(elapsed, 2)
        }


async def run_tests(tables: List[Dict], parallel: int = 20) -> Dict[str, Any]:
    """병렬 테스트 실행."""
    data = StatisticsData()

    results = {
        "total": len(tables),
        "tested": 0,
        "success": 0,
        "failed": 0,
        "by_period": defaultdict(lambda: {"success": 0, "failed": 0}),
        "errors": [],
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    semaphore = asyncio.Semaphore(parallel)

    async def limited_test(table):
        async with semaphore:
            return await test_table(data, table)

    total = len(tables)
    batch_size = 100

    for i in range(0, total, batch_size):
        batch = tables[i:i+batch_size]
        tasks = [limited_test(t) for t in batch]
        batch_results = await asyncio.gather(*tasks)

        for r in batch_results:
            results["tested"] += 1
            prd_se = r.get("prd_se", "unknown")

            if r["success"]:
                results["success"] += 1
                results["by_period"][prd_se]["success"] += 1
            else:
                results["failed"] += 1
                results["by_period"][prd_se]["failed"] += 1
                results["errors"].append({
                    "tbl_id": r["tbl_id"],
                    "org_id": r["org_id"],
                    "prd_se": prd_se,
                    "error": r.get("error", "unknown")
                })

        # 진행 상황 출력
        tested = results["tested"]
        success = results["success"]
        rate = success / tested * 100 if tested > 0 else 0
        print(f"\r진행: {tested:,}/{total:,} ({tested/total*100:.1f}%) | 성공률: {rate:.1f}%", end="", flush=True)

    print()  # 줄바꿈
    results["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    results["by_period"] = dict(results["by_period"])

    return results


def load_metadata() -> List[Dict[str, Any]]:
    """메타데이터 로드."""
    meta_path = project_root / "data" / "metadata_api" / "tables.json"
    with open(meta_path) as f:
        data = json.load(f)
    return data.get("tables", [])


def main():
    parser = argparse.ArgumentParser(description="KOSIS API 샘플 테스트")
    parser.add_argument("--sample", type=int, default=10000, help="샘플 크기 (기본 10000)")
    parser.add_argument("--parallel", type=int, default=30, help="동시 실행 수 (기본 30)")
    parser.add_argument("--output", default="test_sample_result.json", help="결과 파일")
    parser.add_argument("--seed", type=int, default=42, help="랜덤 시드")
    parser.add_argument("--stratified", action="store_true", help="주기별 층화 샘플링")
    args = parser.parse_args()

    print(f"=== KOSIS API 샘플 테스트 ===")
    print(f"샘플 크기: {args.sample:,}")
    print(f"동시 실행: {args.parallel}")
    print()

    # 메타데이터 로드
    print("메타데이터 로드 중...")
    all_tables = load_metadata()
    print(f"전체 테이블: {len(all_tables):,}")

    # 샘플링
    random.seed(args.seed)

    if args.stratified:
        # 주기별 층화 샘플링
        by_period = defaultdict(list)
        for t in all_tables:
            prd = t.get("prd_se", "unknown")
            by_period[prd].append(t)

        sample_per_period = args.sample // len(by_period)
        samples = []
        for prd, tables in by_period.items():
            n = min(sample_per_period, len(tables))
            samples.extend(random.sample(tables, n))

        print(f"층화 샘플링: {len(samples):,}개 (주기 {len(by_period)}종)")
    else:
        # 단순 무작위 샘플링
        samples = random.sample(all_tables, min(args.sample, len(all_tables)))
        print(f"무작위 샘플링: {len(samples):,}개")

    # 샘플 주기 분포 출력
    prd_dist = defaultdict(int)
    for t in samples:
        prd_dist[t.get("prd_se", "unknown")] += 1
    print("\n샘플 주기 분포:")
    for prd, cnt in sorted(prd_dist.items(), key=lambda x: -x[1]):
        print(f"  {prd}: {cnt:,}")
    print()

    # 테스트 실행
    print("테스트 시작...")
    start = time.time()
    results = asyncio.run(run_tests(samples, args.parallel))
    elapsed = time.time() - start

    # 결과 저장
    with open(args.output, "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 결과 출력
    print()
    print("=" * 60)
    print("테스트 결과")
    print("=" * 60)
    print(f"총 테스트: {results['tested']:,}")
    print(f"성공: {results['success']:,}")
    print(f"실패: {results['failed']:,}")
    print(f"성공률: {results['success']/results['tested']*100:.2f}%")
    print(f"소요 시간: {elapsed/60:.1f}분")
    print()
    print("주기별 성공률:")
    print("-" * 40)
    for prd, stats in sorted(results["by_period"].items(), key=lambda x: -(x[1]["success"]+x[1]["failed"])):
        total = stats["success"] + stats["failed"]
        rate = stats["success"] / total * 100 if total > 0 else 0
        status = "✅" if rate >= 95 else ("⚠️" if rate >= 80 else "❌")
        print(f"{status} {prd}: {stats['success']}/{total} ({rate:.1f}%)")

    print()
    print(f"결과 저장: {args.output}")


if __name__ == "__main__":
    main()
