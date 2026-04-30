"""KOSIS 메타데이터 캐시 빌더.

전체 캐시 빌드 및 업데이트를 위한 통합 모듈.

Usage:
    # 전체 빌드 (처음부터)
    uv run python -m src.kosis_tools.cache_builder --full

    # 이어서 빌드 (중단된 경우)
    uv run python -m src.kosis_tools.cache_builder --resume

    # 보강만 실행 (기존 테이블에 추가 정보)
    uv run python -m src.kosis_tools.cache_builder --enrich-only

    # 영문명만 보강
    uv run python -m src.kosis_tools.cache_builder --english-only
"""

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .metadata_enricher import MetadataEnricher
from .metadata_fetcher import AsyncMetadataFetcher
from .metadata_models import (
    DataSource,
    StatisticsTable,
    TablesFile,
    TablesMetadata,
)


@dataclass
class BuildProgress:
    """빌드 진행 상태."""

    # 단계
    step: str = "init"  # init, fetch, enrich_stats, enrich_eng, done

    # 수집 단계
    completed_vw_codes: list[str] = field(default_factory=list)
    tables_count: int = 0

    # 보강 단계
    stats_enriched: bool = False
    eng_enriched: bool = False

    # 통계
    total_requests: int = 0
    total_errors: int = 0
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "completed_vw_codes": self.completed_vw_codes,
            "tables_count": self.tables_count,
            "stats_enriched": self.stats_enriched,
            "eng_enriched": self.eng_enriched,
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "elapsed_seconds": self.elapsed_seconds,
            "updated_at": date.today().isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BuildProgress":
        return cls(
            step=data.get("step", "init"),
            completed_vw_codes=data.get("completed_vw_codes", []),
            tables_count=data.get("tables_count", 0),
            stats_enriched=data.get("stats_enriched", False),
            eng_enriched=data.get("eng_enriched", False),
            total_requests=data.get("total_requests", 0),
            total_errors=data.get("total_errors", 0),
            elapsed_seconds=data.get("elapsed_seconds", 0.0),
        )


class CacheBuilder:
    """KOSIS 메타데이터 캐시 빌더."""

    # 수집 대상 뷰 코드
    VW_CODES = ["MT_ZTITLE", "MT_OTITLE", "MT_GTITLE01", "MT_RTITLE01"]

    def __init__(
        self,
        output_dir: Path,
        concurrency: int = 20,
        rate_limit: float = 0.02,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.concurrency = concurrency
        self.rate_limit = rate_limit

        # 파일 경로
        self.tables_file = self.output_dir / "tables.json"
        self.progress_file = self.output_dir / "build_progress.json"
        self.fetch_cache_file = self.output_dir / "fetch_cache.json"
        self.eng_cache_file = self.output_dir / "eng_name_cache.json"

        self.progress = BuildProgress()

    def _load_progress(self) -> BuildProgress:
        """진행 상태 로드."""
        if self.progress_file.exists():
            with open(self.progress_file, encoding="utf-8") as f:
                data = json.load(f)
            return BuildProgress.from_dict(data)
        return BuildProgress()

    def _save_progress(self):
        """진행 상태 저장."""
        with open(self.progress_file, "w", encoding="utf-8") as f:
            json.dump(self.progress.to_dict(), f, ensure_ascii=False, indent=2)

    def _load_tables(self) -> list[StatisticsTable]:
        """테이블 목록 로드."""
        if self.tables_file.exists():
            with open(self.tables_file, encoding="utf-8") as f:
                data = json.load(f)
            return [StatisticsTable(**t) for t in data.get("tables", [])]
        return []

    def _save_tables(self, tables: list[StatisticsTable], source_counts: dict = None):
        """테이블 목록 저장."""
        if source_counts is None:
            source_counts = {}
            for t in tables:
                src = (
                    t.data_source
                    if isinstance(t.data_source, str)
                    else t.data_source.value
                )
                source_counts[src] = source_counts.get(src, 0) + 1

        tables_file = TablesFile(
            tables=tables,
            metadata=TablesMetadata(
                version=date.today().isoformat(),
                total_count=len(tables),
                sources=source_counts,
            ),
        )

        with open(self.tables_file, "w", encoding="utf-8") as f:
            json.dump(tables_file.model_dump(), f, ensure_ascii=False, indent=2)

    async def fetch_all(self, resume: bool = True) -> list[StatisticsTable]:
        """모든 뷰 코드에서 테이블 수집."""
        print("\n" + "=" * 50)
        print("1단계: 통계표 목록 수집 (statisticsList API)")
        print("=" * 50)

        fetcher = AsyncMetadataFetcher(
            concurrency=self.concurrency,
            rate_limit=self.rate_limit,
        )

        # 캐시 로드
        all_tables: list[StatisticsTable] = []
        source_counts: dict[str, int] = {}

        if resume and self.fetch_cache_file.exists():
            with open(self.fetch_cache_file, encoding="utf-8") as f:
                cache_data = json.load(f)
            all_tables = [StatisticsTable(**t) for t in cache_data.get("tables", [])]
            self.progress.completed_vw_codes = cache_data.get("completed_vw_codes", [])
            source_counts = cache_data.get("source_counts", {})
            print(
                f"캐시 로드: {len(all_tables):,}개, 완료된 뷰: {self.progress.completed_vw_codes}"
            )

        def progress_callback(count, msg):
            print(f"  [{count:,}개] {msg}", flush=True)

        for vw_cd in self.VW_CODES:
            if vw_cd in self.progress.completed_vw_codes:
                print(f"\n[{vw_cd}] 이미 완료됨 (스킵)")
                continue

            print(f"\n[{vw_cd}] 수집 중...")
            start = time.time()

            tables = await fetcher.fetch_all_tables(
                vw_cd, max_depth=15, callback=progress_callback
            )
            all_tables.extend(tables)

            source = fetcher.VW_CD_MAP.get(vw_cd, DataSource.SUBJECT)
            source_counts[source.value] = source_counts.get(source.value, 0) + len(
                tables
            )

            elapsed = time.time() - start
            self.progress.total_requests += fetcher._request_count
            self.progress.completed_vw_codes.append(vw_cd)
            print(f"  완료: {len(tables):,}개 ({elapsed:.1f}초)")

            # 뷰 코드별 캐시 저장
            cache_data = {
                "tables": [t.model_dump() for t in all_tables],
                "completed_vw_codes": self.progress.completed_vw_codes,
                "source_counts": source_counts,
            }
            with open(self.fetch_cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False)

        # 중복 제거
        seen_ids: set[str] = set()
        unique_tables = []
        for table in all_tables:
            if table.tbl_id not in seen_ids:
                seen_ids.add(table.tbl_id)
                unique_tables.append(table)

        print(f"\n중복 제거: {len(all_tables):,} → {len(unique_tables):,}")

        self.progress.tables_count = len(unique_tables)
        self.progress.step = "fetch"
        self._save_progress()
        self._save_tables(unique_tables, source_counts)

        return unique_tables

    async def enrich_stats(
        self, tables: list[StatisticsTable]
    ) -> list[StatisticsTable]:
        """통계설명 API로 보강."""
        print("\n" + "=" * 50)
        print("2단계: 통계설명 보강 (statisticsExplData API)")
        print("=" * 50)

        enricher = MetadataEnricher(
            concurrency=self.concurrency,
            rate_limit=self.rate_limit,
        )

        def progress_callback(done, total, enriched, requests, errors):
            print(
                f"  [{done:,}/{total:,}] 보강: {enriched:,}개, 요청: {requests:,}회",
                flush=True,
            )

        start = time.time()
        tables = await enricher.enrich_with_stat_explanations(
            tables, callback=progress_callback
        )
        elapsed = time.time() - start

        enriched_count = sum(1 for t in tables if t.stats_nm or t.writing_purps)
        print(f"\n완료: {enriched_count:,}개 보강됨 ({elapsed:.1f}초)")

        self.progress.stats_enriched = True
        self.progress.total_requests += enricher._request_count
        self.progress.step = "enrich_stats"
        self._save_progress()
        self._save_tables(tables)

        return tables

    async def enrich_english(
        self, tables: list[StatisticsTable]
    ) -> list[StatisticsTable]:
        """영문명 보강."""
        print("\n" + "=" * 50)
        print("3단계: 영문명 보강 (getMeta API)")
        print("=" * 50)

        enricher = MetadataEnricher(
            concurrency=self.concurrency,
            rate_limit=self.rate_limit,
        )

        def progress_callback(done, total, enriched, requests, errors):
            print(
                f"  [{done:,}/{total:,}] 영문명: {enriched:,}개, 요청: {requests:,}회",
                flush=True,
            )

        start = time.time()
        tables = await enricher.enrich_with_english_names(
            tables, cache_file=self.eng_cache_file, callback=progress_callback
        )
        elapsed = time.time() - start

        enriched_count = sum(1 for t in tables if t.tbl_nm_eng)
        print(f"\n완료: {enriched_count:,}개 영문명 ({elapsed:.1f}초)")

        self.progress.eng_enriched = True
        self.progress.total_requests += enricher._request_count
        self.progress.step = "enrich_eng"
        self._save_progress()
        self._save_tables(tables)

        return tables

    async def build(
        self,
        resume: bool = True,
        fetch: bool = True,
        enrich_stats: bool = True,
        enrich_eng: bool = True,
    ) -> dict:
        """전체 빌드 실행."""
        total_start = time.time()

        if resume:
            self.progress = self._load_progress()
            print(f"진행 상태: {self.progress.step}")

        tables = []

        # 1단계: 수집
        if fetch and self.progress.step in ["init", "fetch"]:
            tables = await self.fetch_all(resume=resume)
        else:
            tables = self._load_tables()
            print(f"기존 테이블 로드: {len(tables):,}개")

        if not tables:
            print("테이블이 없습니다. --full 옵션으로 처음부터 빌드하세요.")
            return {}

        # 2단계: 통계설명 보강
        if enrich_stats and not self.progress.stats_enriched:
            tables = await self.enrich_stats(tables)

        # 3단계: 영문명 보강
        if enrich_eng and not self.progress.eng_enriched:
            tables = await self.enrich_english(tables)

        # 완료
        self.progress.step = "done"
        self.progress.elapsed_seconds = time.time() - total_start
        self._save_progress()

        # 캐시 파일 정리
        if self.fetch_cache_file.exists():
            self.fetch_cache_file.unlink()

        print("\n" + "=" * 50)
        print("빌드 완료!")
        print("=" * 50)
        print(f"총 테이블: {len(tables):,}개")
        print(f"총 요청: {self.progress.total_requests:,}회")
        print(f"총 소요: {self.progress.elapsed_seconds:.1f}초")
        print(f"출력 파일: {self.tables_file}")

        return {
            "total_tables": len(tables),
            "total_requests": self.progress.total_requests,
            "elapsed_seconds": self.progress.elapsed_seconds,
        }


async def main():
    """CLI 엔트리포인트."""
    parser = argparse.ArgumentParser(
        description="KOSIS 메타데이터 캐시 빌더",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 전체 빌드 (처음부터)
  uv run python -m src.kosis_tools.cache_builder --full

  # 이어서 빌드 (중단된 경우)
  uv run python -m src.kosis_tools.cache_builder --resume

  # 보강만 실행
  uv run python -m src.kosis_tools.cache_builder --enrich-only

  # 영문명만 보강
  uv run python -m src.kosis_tools.cache_builder --english-only
        """,
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="처음부터 전체 빌드 (기존 캐시 무시)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="중단된 빌드 이어서 실행 (기본값)",
    )
    parser.add_argument(
        "--enrich-only",
        action="store_true",
        help="기존 테이블에 보강만 실행 (수집 스킵)",
    )
    parser.add_argument(
        "--english-only",
        action="store_true",
        help="영문명 보강만 실행",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/metadata_api"),
        help="출력 디렉토리 (기본: data/metadata_api)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=20,
        help="동시 요청 수 (기본: 20)",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.02,
        help="요청 간 딜레이 초 (기본: 0.02)",
    )

    args = parser.parse_args()

    # .env 로드
    from dotenv import load_dotenv

    load_dotenv()

    builder = CacheBuilder(
        output_dir=args.output_dir,
        concurrency=args.concurrency,
        rate_limit=args.rate_limit,
    )

    # 옵션에 따른 빌드 실행
    if args.full:
        # 처음부터 전체 빌드
        result = await builder.build(resume=False)
    elif args.enrich_only:
        # 보강만 실행
        result = await builder.build(
            resume=True, fetch=False, enrich_stats=True, enrich_eng=True
        )
    elif args.english_only:
        # 영문명만 보강
        builder.progress = builder._load_progress()
        builder.progress.stats_enriched = True  # 통계설명 스킵
        result = await builder.build(
            resume=True, fetch=False, enrich_stats=False, enrich_eng=True
        )
    else:
        # 기본: resume
        result = await builder.build(resume=True)

    return result


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
