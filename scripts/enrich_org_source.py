"""ORG/SOURCE 메타데이터 보강 스크립트.

기존 tables.json에 기관 영문명, 출처 정보를 추가합니다.

Usage:
    uv run python scripts/enrich_org_source.py
"""
import asyncio
import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.kosis_tools.metadata_enricher import MetadataEnricher
from src.kosis_tools.metadata_models import StatisticsTable, TablesFile, TablesMetadata


async def main():
    input_file = Path("data/metadata_api/tables.json")
    output_file = input_file
    cache_file = input_file.parent / "org_source_cache.json"

    print(f"Loading {input_file}...", flush=True)
    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    tables = [StatisticsTable(**t) for t in data["tables"]]
    print(f"Loaded {len(tables):,} tables", flush=True)

    print("\n" + "=" * 60)
    print("ORG/SOURCE 메타 API 보강")
    print("  - ORG: 기관 영문명")
    print("  - SOURCE: 조사기관, 담당부서, 연락처")
    print("=" * 60)

    enricher = MetadataEnricher(concurrency=20, rate_limit=0.03)

    def progress(done, total, enriched, requests, errors):
        print(
            f"  [{done:,}/{total:,}] 보강: {enriched:,}개, "
            f"요청: {requests:,}회, 에러: {errors}개",
            flush=True,
        )

    start = time.time()
    tables = await enricher.enrich_with_org_source(
        tables, cache_file=cache_file, callback=progress
    )
    elapsed = time.time() - start

    # 통계
    org_count = sum(1 for t in tables if t.org_nm_eng)
    source_count = sum(1 for t in tables if t.source_josa_nm)

    print(f"\n완료: ({elapsed:.1f}초)")
    print(f"  - 기관 영문명: {org_count:,}개")
    print(f"  - 출처 정보: {source_count:,}개")

    # 저장
    print("\n저장 중...", flush=True)
    tables_file = TablesFile(
        tables=tables,
        metadata=TablesMetadata(
            version=date.today().isoformat(),
            total_count=len(tables),
            sources=data.get("metadata", {}).get("sources", {}),
        ),
    )

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tables_file.model_dump(), f, ensure_ascii=False, indent=2)
    print(f"Saved: {output_file}", flush=True)

    # 최종 통계
    print("\n" + "=" * 60)
    print("=== 필드별 보강 현황 ===")
    fields = [
        ("org_nm_eng (기관영문명)", sum(1 for t in tables if t.org_nm_eng)),
        ("source_josa_nm (조사기관)", sum(1 for t in tables if t.source_josa_nm)),
        ("source_dept_nm (담당부서)", sum(1 for t in tables if t.source_dept_nm)),
        ("source_dept_phone (연락처)", sum(1 for t in tables if t.source_dept_phone)),
    ]
    for name, count in fields:
        pct = count / len(tables) * 100
        print(f"  {name}: {count:,}개 ({pct:.1f}%)")


if __name__ == "__main__":
    asyncio.run(main())
