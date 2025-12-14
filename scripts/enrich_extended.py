"""확장 메타데이터 보강 스크립트.

기존 tables.json에 추가 필드들을 보강합니다:
1. 통계설명 API 확장 필드 (19개 추가)
2. 검색 API 필드 (MT_ATITLE, CONTENTS 등)

Usage:
    uv run python scripts/enrich_extended.py
"""
import asyncio
import json
import sys
import time
from datetime import date
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.kosis_tools.metadata_enricher import MetadataEnricher
from src.kosis_tools.metadata_models import StatisticsTable, TablesFile, TablesMetadata


async def enrich_extended_stats(
    tables: list[StatisticsTable],
    cache_file: Path,
    concurrency: int = 20,
    rate_limit: float = 0.02,
) -> tuple[list[StatisticsTable], dict]:
    """확장 통계설명 필드 보강 (19개 추가 필드)."""
    print("\n" + "=" * 60)
    print("1단계: 통계설명 API 확장 필드 보강 (26개 전체)")
    print("=" * 60)

    enricher = MetadataEnricher(concurrency=concurrency, rate_limit=rate_limit)

    # 확장 필드가 없는 테이블만 대상으로 (기본 필드는 이미 있음)
    # stat_id별로 그룹핑
    stat_id_to_tables: dict[str, list[int]] = {}
    for i, table in enumerate(tables):
        # 확장 필드가 하나라도 없으면 다시 조회
        if table.stat_id and not table.stats_kind:
            if table.stat_id not in stat_id_to_tables:
                stat_id_to_tables[table.stat_id] = []
            stat_id_to_tables[table.stat_id].append(i)

    unique_stat_ids = list(stat_id_to_tables.keys())
    total = len(unique_stat_ids)
    print(f"보강 대상 stat_id: {total:,}개")

    if total == 0:
        print("이미 모든 확장 필드가 보강되어 있습니다.")
        return tables, {"enriched": 0, "requests": 0, "elapsed": 0}

    enriched_count = 0
    start = time.time()

    def progress(done, total, enriched, requests, errors):
        print(
            f"  [{done:,}/{total:,}] 보강: {enriched:,}개, "
            f"요청: {requests:,}회",
            flush=True,
        )

    tables = await enricher.enrich_with_stat_explanations(tables, callback=progress)
    elapsed = time.time() - start

    # 확장 필드 보강된 수 계산
    enriched_count = sum(1 for t in tables if t.stats_kind)
    print(f"\n완료: {enriched_count:,}개 확장 필드 보강 ({elapsed:.1f}초)")

    return tables, {
        "enriched": enriched_count,
        "requests": enricher._request_count,
        "elapsed": elapsed,
    }


async def enrich_search_fields(
    tables: list[StatisticsTable],
    cache_file: Path,
    concurrency: int = 20,
    rate_limit: float = 0.05,
) -> tuple[list[StatisticsTable], dict]:
    """검색 API로 MT_ATITLE, CONTENTS 등 보강."""
    print("\n" + "=" * 60)
    print("2단계: 검색 API 보강 (MT_ATITLE, CONTENTS, ITEM03)")
    print("=" * 60)

    enricher = MetadataEnricher(concurrency=concurrency, rate_limit=rate_limit)

    def progress(done, total, enriched, requests, errors):
        print(
            f"  [{done:,}/{total:,}] 보강: {enriched:,}개, "
            f"요청: {requests:,}회, 에러: {errors}개",
            flush=True,
        )

    start = time.time()
    tables = await enricher.enrich_with_search_info(
        tables, cache_file=cache_file, callback=progress
    )
    elapsed = time.time() - start

    enriched_count = sum(1 for t in tables if t.mt_atitle)
    print(f"\n완료: {enriched_count:,}개 검색 정보 보강 ({elapsed:.1f}초)")

    return tables, {
        "enriched": enriched_count,
        "requests": enricher._request_count,
        "elapsed": elapsed,
    }


async def main():
    """메인 실행."""
    input_file = Path("data/metadata_api/tables.json")
    output_file = input_file  # 덮어쓰기
    stats_cache = input_file.parent / "stats_extended_cache.json"
    search_cache = input_file.parent / "search_cache.json"

    print(f"Loading {input_file}...", flush=True)
    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    tables = [StatisticsTable(**t) for t in data["tables"]]
    print(f"Loaded {len(tables):,} tables", flush=True)

    total_start = time.time()
    results = {}

    # 1단계: 확장 통계설명 필드 보강
    tables, stats_result = await enrich_extended_stats(
        tables, stats_cache, concurrency=30, rate_limit=0.02
    )
    results["stats_extended"] = stats_result

    # 중간 저장
    print("\n중간 저장 중...", flush=True)
    save_tables(tables, data, output_file)

    # 2단계: 검색 API 보강
    tables, search_result = await enrich_search_fields(
        tables, search_cache, concurrency=20, rate_limit=0.05
    )
    results["search"] = search_result

    # 최종 저장
    print("\n최종 저장 중...", flush=True)
    save_tables(tables, data, output_file)

    total_elapsed = time.time() - total_start

    print("\n" + "=" * 60)
    print("보강 완료!")
    print("=" * 60)
    print(f"총 테이블: {len(tables):,}개")
    print(f"확장 필드 보강: {results['stats_extended']['enriched']:,}개")
    print(f"검색 정보 보강: {results['search']['enriched']:,}개")
    print(f"총 소요 시간: {total_elapsed:.1f}초")
    print(f"출력 파일: {output_file}")

    # 통계 출력
    print("\n=== 필드별 보강 현황 ===")
    field_counts = {
        "stats_nm (조사명)": sum(1 for t in tables if t.stats_nm),
        "writing_purps (조사목적)": sum(1 for t in tables if t.writing_purps),
        "stats_kind (작성유형)": sum(1 for t in tables if t.stats_kind),
        "basis_law (법적근거)": sum(1 for t in tables if t.basis_law),
        "data_collect_mth (자료수집방법)": sum(1 for t in tables if t.data_collect_mth),
        "examin_history (조사연혁)": sum(1 for t in tables if t.examin_history),
        "tbl_nm_eng (영문명)": sum(1 for t in tables if t.tbl_nm_eng),
        "mt_atitle (분류경로)": sum(1 for t in tables if t.mt_atitle),
        "contents (데이터미리보기)": sum(1 for t in tables if t.contents),
    }
    for field, count in field_counts.items():
        pct = count / len(tables) * 100
        print(f"  {field}: {count:,}개 ({pct:.1f}%)")


def save_tables(tables: list[StatisticsTable], original_data: dict, output_file: Path):
    """테이블 저장."""
    tables_file = TablesFile(
        tables=tables,
        metadata=TablesMetadata(
            version=date.today().isoformat(),
            total_count=len(tables),
            sources=original_data.get("metadata", {}).get("sources", {}),
        ),
    )

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tables_file.model_dump(), f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
