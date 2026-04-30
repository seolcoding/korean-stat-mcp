"""KOSIS 메타데이터 보강 모듈.

statisticsExplData API를 사용하여 조사목적, 조사항목 등 상세 정보 추가.
"""

import asyncio
import json
import time
from datetime import date
from pathlib import Path
from typing import Optional

import aiohttp
import json5

from .config import load_config
from .metadata_models import StatisticsTable, TablesFile, TablesMetadata


class MetadataEnricher:
    """통계설명 API로 메타데이터 보강."""

    def __init__(self, concurrency: int = 10, rate_limit: float = 0.05):
        self.config = load_config()
        self.base_url = self.config.base_url
        self.concurrency = concurrency
        self.rate_limit = rate_limit
        self.semaphore: asyncio.Semaphore = None
        self._request_count = 0
        self._error_count = 0

    # 요청할 메타 항목 (개별 요청 필요)
    # 기본 필드 (7개) - 이전 버전 호환
    META_ITEMS_BASIC = [
        ("statsNm", "stats_nm"),
        ("writingPurps", "writing_purps"),
        ("statsPeriod", "stats_period"),
        ("examinObjrange", "examin_obj_range"),
        ("josaItm", "josa_itm"),
        ("mainTermExpl", "main_term_expl"),
        ("confmNo", "confm_no"),
    ]

    # 확장 필드 (19개 추가) - 전체 메타데이터
    META_ITEMS_EXTENDED = [
        ("statsKind", "stats_kind"),
        ("statsEnd", "stats_end"),
        ("statsContinue", "stats_continue"),
        ("basisLaw", "basis_law"),
        ("examinPd", "examin_pd"),
        ("writingSystem", "writing_system"),
        ("writingTel", "writing_tel"),
        ("statsField", "stats_field"),
        ("examinObjArea", "examin_obj_area"),
        ("josaUnit", "josa_unit"),
        ("applyGroup", "apply_group"),
        ("pubPeriod", "pub_period"),
        ("pubExtent", "pub_extent"),
        ("pubDate", "pub_date"),
        ("publictMth", "publict_mth"),
        ("examinTrgetPd", "examin_trget_pd"),
        ("dataUserNote", "data_user_note"),
        ("dataCollectMth", "data_collect_mth"),
        ("examinHistory", "examin_history"),
        ("confmDt", "confm_dt"),
    ]

    # 전체 필드 (기본 + 확장)
    META_ITEMS = META_ITEMS_BASIC + META_ITEMS_EXTENDED

    async def _fetch_single_meta(
        self,
        session: aiohttp.ClientSession,
        stat_id: str,
        meta_itm: str,
    ) -> Optional[str]:
        """단일 메타 항목 조회."""
        async with self.semaphore:
            await asyncio.sleep(self.rate_limit)
            self._request_count += 1

            url = f"{self.base_url}/statisticsExplData.do"
            params = {
                "method": "getList",
                "apiKey": self.config.api_key,
                "format": "json",
                "statId": stat_id,
                "metaItm": meta_itm,
            }

            try:
                async with session.get(url, params=params, timeout=30) as resp:
                    if resp.status != 200:
                        return None
                    text = await resp.text()
                    if not text or text.strip() in ["", "[]", "{}"]:
                        return None
                    data = json5.loads(text)
                    if isinstance(data, list) and len(data) > 0:
                        return data[0].get(meta_itm)
                    return None
            except Exception:
                return None

    async def fetch_stat_explanation(
        self,
        session: aiohttp.ClientSession,
        stat_id: str,
    ) -> Optional[dict]:
        """통계설명 API 호출 (모든 메타 항목)."""
        result = {}

        # 모든 메타 항목을 병렬로 조회
        tasks = [
            self._fetch_single_meta(session, stat_id, api_key)
            for api_key, _ in self.META_ITEMS
        ]
        values = await asyncio.gather(*tasks)

        for (api_key, field_name), value in zip(self.META_ITEMS, values):
            if value:
                result[field_name] = value

        return result if result else None

    async def fetch_table_meta(
        self,
        session: aiohttp.ClientSession,
        org_id: str,
        tbl_id: str,
    ) -> Optional[dict]:
        """통계표설명 API 호출 (영문명 조회)."""
        async with self.semaphore:
            await asyncio.sleep(self.rate_limit)
            self._request_count += 1

            url = f"{self.base_url}/statisticsData.do"
            params = {
                "method": "getMeta",
                "type": "TBL",
                "apiKey": self.config.api_key,
                "format": "json",
                "orgId": org_id,
                "tblId": tbl_id,
            }

            try:
                async with session.get(url, params=params, timeout=30) as resp:
                    if resp.status != 200:
                        self._error_count += 1
                        return None
                    text = await resp.text()
                    if not text or text.strip() in ["", "[]", "{}"]:
                        return None
                    data = json5.loads(text)
                    if isinstance(data, list) and len(data) > 0:
                        return data[0]
                    return data if isinstance(data, dict) else None
            except Exception:
                self._error_count += 1
                return None

    async def enrich_with_stat_explanations(
        self,
        tables: list[StatisticsTable],
        callback=None,
    ) -> list[StatisticsTable]:
        """stat_id 기준으로 통계설명 보강."""
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self._request_count = 0
        self._error_count = 0

        # stat_id별로 그룹핑
        stat_id_to_tables: dict[str, list[int]] = {}
        for i, table in enumerate(tables):
            if table.stat_id:
                if table.stat_id not in stat_id_to_tables:
                    stat_id_to_tables[table.stat_id] = []
                stat_id_to_tables[table.stat_id].append(i)

        unique_stat_ids = list(stat_id_to_tables.keys())
        total = len(unique_stat_ids)
        enriched_count = 0

        async with aiohttp.ClientSession() as session:
            # 배치로 처리
            batch_size = 50
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch_ids = unique_stat_ids[batch_start:batch_end]

                tasks = [
                    self.fetch_stat_explanation(session, stat_id)
                    for stat_id in batch_ids
                ]
                results = await asyncio.gather(*tasks)

                for stat_id, result in zip(batch_ids, results):
                    if result:
                        enriched_count += 1
                        # 해당 stat_id를 가진 모든 테이블에 적용
                        for table_idx in stat_id_to_tables[stat_id]:
                            table = tables[table_idx]
                            # 기본 필드
                            table.stats_nm = result.get("stats_nm")
                            table.writing_purps = result.get("writing_purps")
                            table.stats_period = result.get("stats_period")
                            table.examin_obj_range = result.get("examin_obj_range")
                            table.josa_itm = result.get("josa_itm")
                            table.main_term_expl = result.get("main_term_expl")
                            table.confm_no = result.get("confm_no")
                            # 확장 필드
                            table.stats_kind = result.get("stats_kind")
                            table.stats_end = result.get("stats_end")
                            table.stats_continue = result.get("stats_continue")
                            table.basis_law = result.get("basis_law")
                            table.examin_pd = result.get("examin_pd")
                            table.writing_system = result.get("writing_system")
                            table.writing_tel = result.get("writing_tel")
                            table.stats_field = result.get("stats_field")
                            table.examin_obj_area = result.get("examin_obj_area")
                            table.josa_unit = result.get("josa_unit")
                            table.apply_group = result.get("apply_group")
                            table.pub_period = result.get("pub_period")
                            table.pub_extent = result.get("pub_extent")
                            table.pub_date = result.get("pub_date")
                            table.publict_mth = result.get("publict_mth")
                            table.examin_trget_pd = result.get("examin_trget_pd")
                            table.data_user_note = result.get("data_user_note")
                            table.data_collect_mth = result.get("data_collect_mth")
                            table.examin_history = result.get("examin_history")
                            table.confm_dt = result.get("confm_dt")

                if callback:
                    callback(
                        batch_end,
                        total,
                        enriched_count,
                        self._request_count,
                        self._error_count,
                    )

        return tables

    async def enrich_with_english_names(
        self,
        tables: list[StatisticsTable],
        cache_file: Path = None,
        callback=None,
    ) -> list[StatisticsTable]:
        """영문명 보강 (getMeta API)."""
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self._request_count = 0
        self._error_count = 0

        # 캐시 로드
        cache: dict[str, str] = {}
        if cache_file and cache_file.exists():
            with open(cache_file, encoding="utf-8") as f:
                cache = json.load(f)
            print(f"캐시 로드: {len(cache):,}개 영문명")

        # 이미 영문명이 있거나 캐시에 있는 테이블 제외
        to_fetch: list[tuple[int, str, str]] = []  # (index, org_id, tbl_id)
        for i, table in enumerate(tables):
            if table.tbl_nm_eng:
                continue
            if table.tbl_id in cache:
                table.tbl_nm_eng = cache[table.tbl_id]
                continue
            if table.org_id and table.tbl_id:
                to_fetch.append((i, table.org_id, table.tbl_id))

        total = len(to_fetch)
        print(f"조회 대상: {total:,}개 (캐시 적용 후)")
        enriched_count = len(cache)

        async with aiohttp.ClientSession() as session:
            batch_size = 100
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch = to_fetch[batch_start:batch_end]

                tasks = [
                    self.fetch_table_meta(session, org_id, tbl_id)
                    for _, org_id, tbl_id in batch
                ]
                results = await asyncio.gather(*tasks)

                for (idx, org_id, tbl_id), result in zip(batch, results):
                    if result and result.get("TBL_NM_ENG"):
                        eng_name = result["TBL_NM_ENG"]
                        tables[idx].tbl_nm_eng = eng_name
                        cache[tbl_id] = eng_name
                        enriched_count += 1

                # 주기적으로 캐시 저장 (1000개마다)
                if cache_file and batch_end % 1000 == 0:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(cache, f, ensure_ascii=False)

                if callback:
                    callback(
                        batch_end,
                        total,
                        enriched_count,
                        self._request_count,
                        self._error_count,
                    )

        # 최종 캐시 저장
        if cache_file:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
            print(f"캐시 저장: {len(cache):,}개")

        return tables

    async def fetch_search_info(
        self,
        session: aiohttp.ClientSession,
        tbl_nm: str,
    ) -> Optional[dict]:
        """검색 API로 추가 정보 조회 (MT_ATITLE, CONTENTS 등)."""
        async with self.semaphore:
            await asyncio.sleep(self.rate_limit)
            self._request_count += 1

            url = f"{self.base_url}/statisticsSearch.do"
            params = {
                "method": "getList",
                "apiKey": self.config.api_key,
                "format": "json",
                "searchNm": tbl_nm[:50],  # 검색어 길이 제한
                "resultCount": 5,
            }

            try:
                async with session.get(url, params=params, timeout=30) as resp:
                    if resp.status != 200:
                        self._error_count += 1
                        return None
                    text = await resp.text()
                    if not text or text.strip() in ["", "[]", "{}"]:
                        return None
                    data = json5.loads(text)
                    if isinstance(data, list) and len(data) > 0:
                        return data[0]  # 첫 번째 결과 반환
                    return None
            except Exception:
                self._error_count += 1
                return None

    async def enrich_with_search_info(
        self,
        tables: list[StatisticsTable],
        cache_file: Path = None,
        callback=None,
    ) -> list[StatisticsTable]:
        """검색 API로 MT_ATITLE, CONTENTS 등 보강."""
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self._request_count = 0
        self._error_count = 0

        # 캐시 로드
        cache: dict[str, dict] = {}
        if cache_file and cache_file.exists():
            with open(cache_file, encoding="utf-8") as f:
                cache = json.load(f)
            print(f"캐시 로드: {len(cache):,}개 검색 결과")

        # 이미 MT_ATITLE이 있거나 캐시에 있는 테이블 제외
        to_fetch: list[tuple[int, str, str]] = []  # (index, tbl_id, tbl_nm)
        for i, table in enumerate(tables):
            if table.mt_atitle:
                continue
            if table.tbl_id in cache:
                cached = cache[table.tbl_id]
                table.mt_atitle = cached.get("mt_atitle")
                table.contents = cached.get("contents")
                table.item03 = cached.get("item03")
                table.tbl_view_url = cached.get("tbl_view_url")
                table.stat_db_cnt = cached.get("stat_db_cnt")
                continue
            if table.tbl_nm:
                to_fetch.append((i, table.tbl_id, table.tbl_nm))

        total = len(to_fetch)
        print(f"검색 API 조회 대상: {total:,}개 (캐시 적용 후)")
        enriched_count = len(cache)

        async with aiohttp.ClientSession() as session:
            batch_size = 50
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch = to_fetch[batch_start:batch_end]

                tasks = [
                    self.fetch_search_info(session, tbl_nm) for _, _, tbl_nm in batch
                ]
                results = await asyncio.gather(*tasks)

                for (idx, tbl_id, tbl_nm), result in zip(batch, results):
                    if result:
                        # TBL_ID가 일치하는지 확인
                        if result.get("TBL_ID") == tbl_id:
                            enriched_count += 1
                            tables[idx].mt_atitle = result.get("MT_ATITLE")
                            tables[idx].contents = result.get("CONTENTS")
                            tables[idx].item03 = result.get("ITEM03")
                            tables[idx].tbl_view_url = result.get("TBL_VIEW_URL")
                            tables[idx].stat_db_cnt = result.get("STAT_DB_CNT")

                            cache[tbl_id] = {
                                "mt_atitle": result.get("MT_ATITLE"),
                                "contents": result.get("CONTENTS"),
                                "item03": result.get("ITEM03"),
                                "tbl_view_url": result.get("TBL_VIEW_URL"),
                                "stat_db_cnt": result.get("STAT_DB_CNT"),
                            }

                # 주기적으로 캐시 저장
                if cache_file and batch_end % 500 == 0:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(cache, f, ensure_ascii=False)

                if callback:
                    callback(
                        batch_end,
                        total,
                        enriched_count,
                        self._request_count,
                        self._error_count,
                    )

        # 최종 캐시 저장
        if cache_file:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
            print(f"캐시 저장: {len(cache):,}개")

        return tables

    async def fetch_org_source_meta(
        self,
        session: aiohttp.ClientSession,
        org_id: str,
        tbl_id: str,
    ) -> Optional[dict]:
        """ORG, SOURCE 메타 API 호출."""
        result = {}

        for meta_type in ["ORG", "SOURCE"]:
            async with self.semaphore:
                await asyncio.sleep(self.rate_limit)
                self._request_count += 1

                url = f"{self.base_url}/statisticsData.do"
                params = {
                    "method": "getMeta",
                    "type": meta_type,
                    "apiKey": self.config.api_key,
                    "format": "json",
                    "orgId": org_id,
                    "tblId": tbl_id,
                }

                try:
                    async with session.get(url, params=params, timeout=30) as resp:
                        if resp.status != 200:
                            continue
                        text = await resp.text()
                        if not text or text.strip() in ["", "[]", "{}"]:
                            continue
                        data = json5.loads(text)
                        if isinstance(data, list) and len(data) > 0:
                            if meta_type == "ORG":
                                result["org_nm_eng"] = data[0].get("ORG_NM_ENG")
                            elif meta_type == "SOURCE":
                                result["source_josa_nm"] = data[0].get("JOSA_NM")
                                result["source_dept_nm"] = data[0].get("DEPT_NM")
                                result["source_dept_phone"] = data[0].get("DEPT_PHONE")
                except Exception:
                    self._error_count += 1
                    continue

        return result if result else None

    async def enrich_with_org_source(
        self,
        tables: list[StatisticsTable],
        cache_file: Path = None,
        callback=None,
    ) -> list[StatisticsTable]:
        """ORG(기관영문명), SOURCE(출처) 보강."""
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self._request_count = 0
        self._error_count = 0

        # 캐시 로드
        cache: dict[str, dict] = {}
        if cache_file and cache_file.exists():
            with open(cache_file, encoding="utf-8") as f:
                cache = json.load(f)
            print(f"캐시 로드: {len(cache):,}개")

        # 이미 보강된 테이블 제외
        to_fetch: list[tuple[int, str, str]] = []
        for i, table in enumerate(tables):
            if table.org_nm_eng or table.source_josa_nm:
                continue
            if table.tbl_id in cache:
                cached = cache[table.tbl_id]
                table.org_nm_eng = cached.get("org_nm_eng")
                table.source_josa_nm = cached.get("source_josa_nm")
                table.source_dept_nm = cached.get("source_dept_nm")
                table.source_dept_phone = cached.get("source_dept_phone")
                continue
            if table.org_id and table.tbl_id:
                to_fetch.append((i, table.org_id, table.tbl_id))

        total = len(to_fetch)
        print(f"ORG/SOURCE 조회 대상: {total:,}개")
        enriched_count = len(cache)

        async with aiohttp.ClientSession() as session:
            batch_size = 50
            for batch_start in range(0, total, batch_size):
                batch_end = min(batch_start + batch_size, total)
                batch = to_fetch[batch_start:batch_end]

                tasks = [
                    self.fetch_org_source_meta(session, org_id, tbl_id)
                    for _, org_id, tbl_id in batch
                ]
                results = await asyncio.gather(*tasks)

                for (idx, org_id, tbl_id), result in zip(batch, results):
                    if result:
                        enriched_count += 1
                        tables[idx].org_nm_eng = result.get("org_nm_eng")
                        tables[idx].source_josa_nm = result.get("source_josa_nm")
                        tables[idx].source_dept_nm = result.get("source_dept_nm")
                        tables[idx].source_dept_phone = result.get("source_dept_phone")
                        cache[tbl_id] = result

                if cache_file and batch_end % 1000 == 0:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(cache, f, ensure_ascii=False)

                if callback:
                    callback(
                        batch_end,
                        total,
                        enriched_count,
                        self._request_count,
                        self._error_count,
                    )

        if cache_file:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
            print(f"캐시 저장: {len(cache):,}개")

        return tables


async def enrich_with_search(
    input_file: Path,
    output_file: Path = None,
    cache_file: Path = None,
    concurrency: int = 20,
    rate_limit: float = 0.05,
) -> dict:
    """검색 API로 보강 실행."""
    if output_file is None:
        output_file = input_file
    if cache_file is None:
        cache_file = input_file.parent / "search_cache.json"

    print(f"Loading {input_file}...", flush=True)
    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    tables = [StatisticsTable(**t) for t in data["tables"]]
    print(f"Loaded {len(tables):,} tables", flush=True)

    enricher = MetadataEnricher(concurrency=concurrency, rate_limit=rate_limit)

    def progress(done, total, enriched, requests, errors):
        print(
            f"  [{done:,}/{total:,}] 검색: {enriched:,}개, "
            f"요청: {requests:,}회, 에러: {errors}개",
            flush=True,
        )

    print("\n=== 검색 API로 보강 중 (MT_ATITLE, CONTENTS) ===", flush=True)
    start = time.time()
    tables = await enricher.enrich_with_search_info(
        tables, cache_file=cache_file, callback=progress
    )
    elapsed = time.time() - start

    enriched_count = sum(1 for t in tables if t.mt_atitle)
    print(f"\n완료: {enriched_count:,}개 보강 ({elapsed:.1f}초)", flush=True)

    # 저장
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

    return {
        "total_tables": len(tables),
        "enriched_count": enriched_count,
        "requests": enricher._request_count,
        "errors": enricher._error_count,
        "elapsed": elapsed,
    }


async def enrich_english_names(
    input_file: Path,
    output_file: Path = None,
    cache_file: Path = None,
    concurrency: int = 20,
    rate_limit: float = 0.02,
) -> dict:
    """영문명 보강 실행.

    Args:
        input_file: 입력 tables.json 경로
        output_file: 출력 경로 (기본: 입력 파일 덮어쓰기)
        cache_file: 중간 캐시 파일 경로
        concurrency: 동시 요청 수
        rate_limit: 요청 간 딜레이

    Returns:
        보강 결과 통계
    """
    if output_file is None:
        output_file = input_file
    if cache_file is None:
        cache_file = input_file.parent / "eng_name_cache.json"

    # 기존 데이터 로드
    print(f"Loading {input_file}...", flush=True)
    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    tables = [StatisticsTable(**t) for t in data["tables"]]
    print(f"Loaded {len(tables):,} tables", flush=True)

    # 보강 실행
    enricher = MetadataEnricher(concurrency=concurrency, rate_limit=rate_limit)

    def progress(done, total, enriched, requests, errors):
        print(
            f"  [{done:,}/{total:,}] 영문명: {enriched:,}개, "
            f"요청: {requests:,}회, 에러: {errors}개",
            flush=True,
        )

    print("\n=== 영문명 API로 보강 중... ===", flush=True)
    start = time.time()
    tables = await enricher.enrich_with_english_names(
        tables, cache_file=cache_file, callback=progress
    )
    elapsed = time.time() - start

    # 보강된 테이블 수 계산
    enriched_count = sum(1 for t in tables if t.tbl_nm_eng)
    print(f"\n완료: {enriched_count:,}개 영문명 ({elapsed:.1f}초)", flush=True)

    # 저장
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

    return {
        "total_tables": len(tables),
        "enriched_count": enriched_count,
        "requests": enricher._request_count,
        "errors": enricher._error_count,
        "elapsed": elapsed,
    }


async def enrich_metadata(
    input_file: Path,
    output_file: Path = None,
    concurrency: int = 10,
    rate_limit: float = 0.05,
) -> dict:
    """메타데이터 보강 실행.

    Args:
        input_file: 입력 tables.json 경로
        output_file: 출력 경로 (기본: 입력 파일 덮어쓰기)
        concurrency: 동시 요청 수
        rate_limit: 요청 간 딜레이

    Returns:
        보강 결과 통계
    """
    if output_file is None:
        output_file = input_file

    # 기존 데이터 로드
    print(f"Loading {input_file}...")
    with open(input_file, encoding="utf-8") as f:
        data = json.load(f)

    tables = [StatisticsTable(**t) for t in data["tables"]]
    print(f"Loaded {len(tables):,} tables")

    # 보강 실행
    enricher = MetadataEnricher(concurrency=concurrency, rate_limit=rate_limit)

    def progress(done, total, enriched, requests, errors):
        print(
            f"  [{done:,}/{total:,}] 보강: {enriched:,}개, "
            f"요청: {requests:,}회, 에러: {errors}개",
            flush=True,
        )

    print("\n=== 통계설명 API로 보강 중... ===")
    start = time.time()
    tables = await enricher.enrich_with_stat_explanations(tables, callback=progress)
    elapsed = time.time() - start

    # 보강된 테이블 수 계산
    enriched_count = sum(1 for t in tables if t.stats_nm or t.writing_purps)
    print(f"\n완료: {enriched_count:,}개 보강됨 ({elapsed:.1f}초)")

    # 저장
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
    print(f"Saved: {output_file}")

    return {
        "total_tables": len(tables),
        "enriched_count": enriched_count,
        "requests": enricher._request_count,
        "errors": enricher._error_count,
        "elapsed": elapsed,
    }


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    input_file = Path("data/metadata_api/tables.json")
    result = asyncio.run(
        enrich_metadata(
            input_file,
            concurrency=10,
            rate_limit=0.05,
        )
    )
    print(f"\n결과: {result}")
