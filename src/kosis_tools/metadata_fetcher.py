"""KOSIS 메타데이터 API 기반 캐싱.

XLS 파일 대신 API로 메타데이터를 직접 가져와서 캐싱합니다.
비동기 병렬 처리로 빠른 수집 지원.
"""

import asyncio
import json
import re
import time
from datetime import date
from pathlib import Path
from typing import Optional

import aiohttp
import json5

from .config import Endpoints, load_config
from .metadata_models import (
    DataSource,
    PeriodType,
    StatisticsTable,
    TablesFile,
    TablesMetadata,
)


class AsyncMetadataFetcher:
    """KOSIS API 기반 메타데이터 수집기 (비동기 버전).

    병렬 처리로 빠른 메타데이터 수집.
    """

    VW_CD_MAP = {
        "MT_ZTITLE": DataSource.SUBJECT,
        "MT_OTITLE": DataSource.ORGANIZATION,
        "MT_GTITLE01": DataSource.LOCAL_INDICATOR,
        "MT_RTITLE01": DataSource.INTERNATIONAL,
    }

    def __init__(self, concurrency: int = 10, rate_limit: float = 0.05):
        """
        Args:
            concurrency: 동시 요청 수
            rate_limit: 요청 간 최소 딜레이 (초)
        """
        self.config = load_config()
        self.base_url = self.config.base_url
        self.concurrency = concurrency
        self.rate_limit = rate_limit
        self.semaphore: asyncio.Semaphore = None
        self._request_count = 0

    async def _request(
        self, session: aiohttp.ClientSession, endpoint: str, params: dict
    ) -> dict | list:
        """비동기 API 요청."""
        params["apiKey"] = self.config.api_key
        params["format"] = "json"
        url = f"{self.base_url}/{endpoint}"

        async with self.semaphore:
            await asyncio.sleep(self.rate_limit)
            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
                self._request_count += 1
                return json5.loads(text)

    async def fetch_statistics_list(
        self,
        session: aiohttp.ClientSession,
        vw_cd: str,
        parent_id: Optional[str] = None,
    ) -> list[dict]:
        """통계 목록 비동기 조회."""
        params = {"method": "getList", "vwCd": vw_cd}
        if parent_id:
            params["parentListId"] = parent_id

        try:
            data = await self._request(session, Endpoints.STATISTICS_LIST, params)
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"Warning: {vw_cd}/{parent_id} 조회 실패 - {e}")
            return []

    async def fetch_all_tables(
        self,
        vw_cd: str,
        max_depth: int = 15,
        callback=None,
    ) -> list[StatisticsTable]:
        """전체 통계표 목록 비동기 수집.

        Worker pool 패턴으로 진정한 병렬 처리.
        """
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self._request_count = 0
        data_source = self.VW_CD_MAP.get(vw_cd, DataSource.SUBJECT)

        tables: list[StatisticsTable] = []
        visited: set[str] = set()
        queue: asyncio.Queue = asyncio.Queue()
        active_workers = 0
        lock = asyncio.Lock()

        # 시작 항목 추가
        await queue.put((None, [], [], 1))

        async def worker(session: aiohttp.ClientSession):
            nonlocal active_workers
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    break

                parent_id, path_names, path_ids, depth = item

                if depth > max_depth:
                    queue.task_done()
                    continue

                cache_key = f"{vw_cd}:{parent_id or 'root'}"
                async with lock:
                    if cache_key in visited:
                        queue.task_done()
                        continue
                    visited.add(cache_key)
                    active_workers += 1

                try:
                    node_tables, children = await self._process_node(
                        session,
                        vw_cd,
                        parent_id,
                        path_names,
                        path_ids,
                        depth,
                        data_source,
                    )

                    async with lock:
                        tables.extend(node_tables)
                        for child in children:
                            await queue.put(child)

                        if callback and len(tables) % 5000 == 0:
                            callback(
                                len(tables),
                                f"수집 중... (요청 {self._request_count}회, 대기 {queue.qsize()})",
                            )

                except Exception as e:
                    print(f"Error: {e}", flush=True)
                finally:
                    async with lock:
                        active_workers -= 1
                    queue.task_done()

        async with aiohttp.ClientSession() as session:
            # 워커 시작
            workers = [
                asyncio.create_task(worker(session)) for _ in range(self.concurrency)
            ]

            # 큐가 비고 모든 작업 완료될 때까지 대기
            await queue.join()

            # 워커 정리
            for w in workers:
                w.cancel()

        if callback:
            callback(
                len(tables), f"완료! {len(tables)}개 수집, 요청 {self._request_count}회"
            )

        return tables

    async def _process_node(
        self,
        session: aiohttp.ClientSession,
        vw_cd: str,
        parent_id: Optional[str],
        path_names: list[str],
        path_ids: list[str],
        depth: int,
        data_source: DataSource,
    ) -> tuple[list[StatisticsTable], list[tuple]]:
        """단일 노드 처리: 테이블 추출 + 하위 카테고리 반환."""
        tables = []
        children = []

        items = await self.fetch_statistics_list(session, vw_cd, parent_id)

        for item in items:
            tbl_id = item.get("TBL_ID")
            list_id = item.get("LIST_ID")
            list_nm = item.get("LIST_NM", "")

            current_path_names = path_names + [list_nm]
            current_path_ids = path_ids + [list_id] if list_id else path_ids
            path_str = " > ".join(current_path_names)

            if tbl_id:  # 통계표
                tbl_nm = item.get("TBL_NM") or list_nm  # TBL_NM 우선, 없으면 LIST_NM
                table = StatisticsTable(
                    # API 원본 필드
                    tbl_id=tbl_id,
                    tbl_nm=tbl_nm,
                    org_id=item.get("ORG_ID"),
                    org_nm=item.get("ORG_NM"),
                    stat_id=item.get("STAT_ID"),
                    vw_cd=item.get("VW_CD") or vw_cd,
                    list_id=list_id,
                    strt_prd_de=item.get("STRT_PRD_DE"),
                    end_prd_de=item.get("END_PRD_DE"),
                    prd_se=item.get("PRD_SE"),
                    rec_tbl_se=item.get("REC_TBL_SE"),
                    send_de=item.get("SEND_DE"),
                    # 가공 필드
                    data_source=data_source,
                    level=depth,
                    path=path_str,
                    path_ids=current_path_ids,
                    keywords=self._generate_keywords(tbl_nm, path_str),
                )
                tables.append(table)
            else:  # 카테고리 - 다음 레벨에서 처리
                children.append(
                    (list_id, current_path_names, current_path_ids, depth + 1)
                )

        return tables, children

    def _parse_period_type(self, prd_se: Optional[str]) -> Optional[PeriodType]:
        """주기 코드 파싱."""
        if not prd_se:
            return None
        mapping = {
            "Y": PeriodType.YEAR,
            "A": PeriodType.YEAR,
            "M": PeriodType.MONTH,
            "Q": PeriodType.QUARTER,
            "S": PeriodType.HALF,
            "H": PeriodType.HALF,
        }
        return mapping.get(prd_se.upper())

    def _generate_keywords(self, name: str, path: str) -> list[str]:
        """검색 키워드 생성."""
        keywords = set()
        for text in [name, path]:
            parts = re.split(r"[>()/_,\s]+", text)
            keywords.update(p for p in parts if len(p) >= 2)
        stopwords = {"통계표", "보기", "Level", "NaN"}
        return sorted(keywords - stopwords)


def _load_cache(
    cache_file: Path,
) -> tuple[list[StatisticsTable], set[str], dict[str, int]]:
    """캐시 파일 로드."""
    if not cache_file.exists():
        return [], set(), {}

    with open(cache_file, encoding="utf-8") as f:
        data = json.load(f)

    tables = [StatisticsTable(**t) for t in data.get("tables", [])]
    completed_vw_codes = set(data.get("completed_vw_codes", []))
    source_counts = data.get("source_counts", {})

    print(f"캐시 로드: {len(tables):,}개 테이블, 완료된 뷰: {completed_vw_codes}")
    return tables, completed_vw_codes, source_counts


def _save_cache(
    cache_file: Path,
    tables: list[StatisticsTable],
    completed_vw_codes: set[str],
    source_counts: dict[str, int],
):
    """캐시 파일 저장."""
    data = {
        "tables": [t.model_dump() for t in tables],
        "completed_vw_codes": list(completed_vw_codes),
        "source_counts": source_counts,
        "updated_at": date.today().isoformat(),
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"캐시 저장: {len(tables):,}개 ({cache_file.name})")


async def async_fetch_and_cache(
    output_dir: Path,
    vw_codes: list[str] = None,
    concurrency: int = 20,
    rate_limit: float = 0.02,
    resume: bool = True,
) -> dict:
    """비동기로 메타데이터 수집 후 캐싱.

    Args:
        output_dir: JSON 출력 디렉토리
        vw_codes: 수집할 뷰 코드 목록
        concurrency: 동시 요청 수
        rate_limit: 요청 간 딜레이
        resume: 이전 캐시에서 이어서 수집할지 여부

    Returns:
        수집 결과 통계
    """
    if vw_codes is None:
        vw_codes = ["MT_ZTITLE", "MT_OTITLE", "MT_GTITLE01", "MT_RTITLE01"]

    output_dir.mkdir(parents=True, exist_ok=True)
    cache_file = output_dir / "cache.json"
    fetcher = AsyncMetadataFetcher(concurrency=concurrency, rate_limit=rate_limit)

    # 캐시 로드 (resume 모드)
    if resume:
        all_tables, completed_vw_codes, source_counts = _load_cache(cache_file)
    else:
        all_tables, completed_vw_codes, source_counts = [], set(), {}

    total_requests = 0

    def progress(count, msg):
        print(f"  [{count:,}개] {msg}", flush=True)

    # 각 뷰 코드별로 수집
    for vw_cd in vw_codes:
        if vw_cd in completed_vw_codes:
            print(f"\n=== {vw_cd} 이미 완료됨 (스킵) ===")
            continue

        print(f"\n=== {vw_cd} 수집 중... ===")
        start = time.time()

        tables = await fetcher.fetch_all_tables(vw_cd, max_depth=15, callback=progress)
        all_tables.extend(tables)

        source = fetcher.VW_CD_MAP.get(vw_cd, DataSource.SUBJECT)
        source_counts[source.value] = source_counts.get(source.value, 0) + len(tables)
        total_requests += fetcher._request_count

        elapsed = time.time() - start
        print(
            f"  완료: {len(tables):,}개 ({elapsed:.1f}초, {fetcher._request_count}회 요청)"
        )

        # 뷰 코드 완료 후 캐시 저장
        completed_vw_codes.add(vw_cd)
        _save_cache(cache_file, all_tables, completed_vw_codes, source_counts)

    # 중복 제거
    seen_ids: set[str] = set()
    unique_tables = []
    for table in all_tables:
        if table.tbl_id not in seen_ids:
            seen_ids.add(table.tbl_id)
            unique_tables.append(table)

    print(f"\n중복 제거: {len(all_tables):,} → {len(unique_tables):,}")

    # tables.json 저장
    tables_file = TablesFile(
        tables=unique_tables,
        metadata=TablesMetadata(
            version=date.today().isoformat(),
            total_count=len(unique_tables),
            sources=source_counts,
        ),
    )

    with open(output_dir / "tables.json", "w", encoding="utf-8") as f:
        json.dump(tables_file.model_dump(), f, ensure_ascii=False, indent=2)
    print(f"Saved tables.json: {len(unique_tables):,} tables")

    # 캐시 파일 삭제 (완료 후)
    if cache_file.exists():
        cache_file.unlink()
        print("캐시 파일 삭제됨")

    return {
        "total_tables": len(unique_tables),
        "source_counts": source_counts,
        "total_requests": total_requests,
    }


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    output_dir = Path("data/metadata_api")
    result = asyncio.run(
        async_fetch_and_cache(
            output_dir,
            vw_codes=["MT_ZTITLE"],  # 테스트: 주제별통계만
            concurrency=20,
            rate_limit=0.02,
        )
    )
    print(f"\n완료: {result}")
