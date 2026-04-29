#!/usr/bin/env python3
"""Build a KOSIS OpenAPI capability and statistics catalog report.

Reads KOSIS_API_KEY from the environment. The key is only sent to KOSIS and is
never written to output files.
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import json5
import requests


OUT = Path(__file__).resolve().parent
BASE = "https://kosis.kr/openapi"

VIEW_CODES = {
    "MT_ZTITLE": "국내통계 주제별",
    "MT_OTITLE": "국내통계 기관별",
    "MT_GTITLE01": "e-지방지표 주제별",
    "MT_RTITLE01": "국제/북한통계",
}

API_GROUPS = [
    {
        "group": "통계목록",
        "endpoint": "/statisticsList.do",
        "formats": "JSON, SDMX",
        "purpose": "주제별/기관별/지방지표/국제·북한 통계 분류와 통계표 목록 탐색",
        "main_params": "method, apiKey, format, vwCd, parentListId",
    },
    {
        "group": "통계자료",
        "endpoint": "/Param/statisticsParameterData.do, /statisticsData.do",
        "formats": "JSON, SDMX",
        "purpose": "통계표 수치 데이터 조회",
        "main_params": "orgId, tblId, itmId, objL1~objL8, prdSe, startPrdDe, endPrdDe, newEstPrdCnt",
    },
    {
        "group": "대용량 통계자료",
        "endpoint": "/statisticsBigData.do",
        "formats": "SDMX, XLS",
        "purpose": "대용량 통계자료 조회. 사전 등록된 userStatsId 흐름에 적합",
        "main_params": "userStatsId, prdSe, startPrdDe/endPrdDe 또는 newEstPrdCnt",
    },
    {
        "group": "통계설명자료",
        "endpoint": "/statisticsExplData.do",
        "formats": "JSON, XML",
        "purpose": "조사명, 작성유형, 법적근거, 조사목적, 조사주기, 공표방법 등 설명 메타데이터 조회",
        "main_params": "statId 또는 orgId+tblId, metaItm",
    },
    {
        "group": "통계표설명/메타",
        "endpoint": "/statisticsData.do?method=getMeta",
        "formats": "JSON",
        "purpose": "통계표명, 기관, 수록기간, 분류, 항목, 주석, 단위, 출처, 갱신일 조회",
        "main_params": "type=TBL|ORG|PRD|OBJ_VAR|ITM_VAR|CMMT|UNIT|SOURCE|WGT|NCD, orgId, tblId",
    },
    {
        "group": "KOSIS 통합검색",
        "endpoint": "/statisticsSearch.do",
        "formats": "JSON",
        "purpose": "키워드 기반 통계표 검색, 경로/설명/링크 보강",
        "main_params": "searchNm, sort, startCount, resultCount",
    },
    {
        "group": "통계주요지표",
        "endpoint": "/pkNumberService.do 등 6개 지표 API",
        "formats": "JSON, XML",
        "purpose": "주요지표 설명, 목록, 지표명 검색, 고유번호별 상세 시계열 조회",
        "main_params": "jipyoId, statName, orgId, prdSe 등 엔드포인트별 상이",
    },
]


@dataclass
class CrawlResult:
    view_code: str
    view_name: str
    request_count: int
    category_count: int
    table_count: int
    tables: list[dict[str, Any]]
    root_categories: list[dict[str, str]]


def call_list(api_key: str, vw_cd: str, parent_id: str | None) -> list[dict[str, Any]]:
    params = {
        "method": "getList",
        "apiKey": api_key,
        "format": "json",
        "vwCd": vw_cd,
    }
    if parent_id:
        params["parentListId"] = parent_id
    response = requests.get(f"{BASE}/statisticsList.do", params=params, timeout=30)
    response.raise_for_status()
    text = response.text.strip()
    if not text or text in {"[]", "{}"}:
        return []
    parsed = json5.loads(text)
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    return []


def crawl_view(api_key: str, vw_cd: str, *, max_nodes: int | None = None) -> CrawlResult:
    view_name = VIEW_CODES[vw_cd]
    queue: deque[tuple[str | None, list[str], list[str]]] = deque([(None, [], [])])
    seen: set[str] = set()
    tables: list[dict[str, Any]] = []
    categories: list[dict[str, Any]] = []
    root_categories: list[dict[str, str]] = []
    request_count = 0

    while queue:
        parent_id, path_names, path_ids = queue.popleft()
        seen_key = parent_id or "__root__"
        if seen_key in seen:
            continue
        seen.add(seen_key)

        items = call_list(api_key, vw_cd, parent_id)
        request_count += 1

        for item in items:
            if item.get("TBL_ID"):
                record = {
                    "tbl_id": item.get("TBL_ID"),
                    "tbl_nm": item.get("TBL_NM") or item.get("LIST_NM"),
                    "org_id": item.get("ORG_ID"),
                    "stat_id": item.get("STAT_ID"),
                    "vw_cd": item.get("VW_CD") or vw_cd,
                    "vw_nm": item.get("VW_NM") or view_name,
                    "send_de": item.get("SEND_DE"),
                    "rec_tbl_se": item.get("REC_TBL_SE"),
                    "path": " > ".join(path_names),
                    "path_ids": path_ids,
                }
                tables.append(record)
            elif item.get("LIST_ID"):
                list_id = item["LIST_ID"]
                list_nm = item.get("LIST_NM", "")
                category = {
                    "list_id": list_id,
                    "list_nm": list_nm,
                    "vw_cd": item.get("VW_CD") or vw_cd,
                    "vw_nm": item.get("VW_NM") or view_name,
                    "parent_id": parent_id,
                    "path": " > ".join(path_names + [list_nm]),
                }
                categories.append(category)
                if parent_id is None:
                    root_categories.append({"list_id": list_id, "list_nm": list_nm})
                queue.append((list_id, path_names + [list_nm], path_ids + [list_id]))

        if max_nodes and request_count >= max_nodes:
            break
        time.sleep(0.04)

    return CrawlResult(
        view_code=vw_cd,
        view_name=view_name,
        request_count=request_count,
        category_count=len(categories),
        table_count=len(tables),
        tables=tables,
        root_categories=root_categories,
    )


def write_outputs(results: list[CrawlResult]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}

    for result in results:
        source_counts[result.view_code] = result.table_count
        path = OUT / f"tables-{result.view_code}.json"
        path.write_text(json.dumps(result.tables, ensure_ascii=False, indent=2), encoding="utf-8")
        all_rows.extend(result.tables)

    by_id: dict[str, dict[str, Any]] = {}
    for row in all_rows:
        by_id.setdefault(row["tbl_id"], row)

    unique_tables = list(by_id.values())
    unique_tables.sort(key=lambda x: ((x.get("path") or ""), x.get("tbl_nm") or ""))
    (OUT / "tables-all-unique.json").write_text(
        json.dumps(unique_tables, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    view_summary = [
        {
            "view_code": r.view_code,
            "view_name": r.view_name,
            "requests": r.request_count,
            "categories": r.category_count,
            "tables": r.table_count,
            "root_categories": r.root_categories,
        }
        for r in results
    ]

    path_counter = Counter()
    org_counter = Counter()
    stat_counter = Counter()
    for row in unique_tables:
        top = (row.get("path") or "미분류").split(" > ")[0]
        path_counter[top] += 1
        if row.get("org_id"):
            org_counter[row["org_id"]] += 1
        if row.get("stat_id"):
            stat_counter[row["stat_id"]] += 1

    summary = {
        "generated_at": date.today().isoformat(),
        "api_base": BASE,
        "view_summary": view_summary,
        "total_rows_by_view": source_counts,
        "unique_table_count": len(unique_tables),
        "top_category_counts": path_counter.most_common(),
        "top_org_counts": org_counter.most_common(30),
        "top_stat_counts": stat_counter.most_common(30),
        "api_groups": API_GROUPS,
    }
    (OUT / "catalog-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md = []
    md.append("# KOSIS OpenAPI 기능 및 조회 가능 통계 카탈로그\n")
    md.append(f"- 생성일: {date.today().isoformat()}")
    md.append(f"- 기준 API: `{BASE}`")
    md.append("- 인증키는 환경변수에서 읽어 API 호출에만 사용했고, 산출물에는 저장하지 않았습니다.")
    md.append("")
    md.append("## 1. 사용 가능한 API 기능")
    md.append("| 구분 | 엔드포인트 | 형식 | 주요 용도 | 주요 파라미터 |")
    md.append("|---|---|---|---|---|")
    for group in API_GROUPS:
        md.append(
            f"| {group['group']} | `{group['endpoint']}` | {group['formats']} | "
            f"{group['purpose']} | `{group['main_params']}` |"
        )
    md.append("")
    md.append("## 2. 통계목록 뷰별 수집 결과")
    md.append("| 뷰 코드 | 뷰 이름 | API 요청 | 분류 수 | 통계표 행 수 |")
    md.append("|---|---:|---:|---:|---:|")
    for r in results:
        md.append(f"| `{r.view_code}` | {r.view_name} | {r.request_count:,} | {r.category_count:,} | {r.table_count:,} |")
    md.append(f"\n- 중복 제거 후 고유 통계표 수: **{len(unique_tables):,}개**")
    md.append("")
    md.append("## 3. 국내통계 주제별 최상위 분류")
    domestic = next((r for r in results if r.view_code == "MT_ZTITLE"), None)
    if domestic:
        md.append("| 코드 | 분류명 |")
        md.append("|---|---|")
        for item in domestic.root_categories:
            md.append(f"| `{item['list_id']}` | {item['list_nm']} |")
    md.append("")
    md.append("## 4. 주요 분류별 통계표 수")
    md.append("| 분류 | 통계표 수 |")
    md.append("|---|---:|")
    for name, count in path_counter.most_common(60):
        md.append(f"| {name} | {count:,} |")
    md.append("")
    md.append("## 5. 통계표 예시")
    md.append("| 통계표 ID | 통계표명 | 뷰 | 경로 |")
    md.append("|---|---|---|---|")
    for row in unique_tables[:120]:
        md.append(
            f"| `{row.get('tbl_id')}` | {row.get('tbl_nm') or ''} | "
            f"{row.get('vw_nm') or row.get('vw_cd') or ''} | {row.get('path') or ''} |"
        )
    md.append("")
    md.append("## 6. 원본 산출물")
    md.append("- `catalog-summary.json`: API 기능/수집 요약")
    md.append("- `tables-all-unique.json`: 중복 제거 통계표 전체 목록")
    md.append("- `tables-MT_ZTITLE.json`, `tables-MT_OTITLE.json`, `tables-MT_GTITLE01.json`, `tables-MT_RTITLE01.json`: 뷰별 원본 목록")
    (OUT / "KOSIS_API_CATALOG_REPORT.md").write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    api_key = os.environ.get("KOSIS_API_KEY")
    if not api_key:
        raise SystemExit("KOSIS_API_KEY is required")

    results: list[CrawlResult] = []
    for vw_cd in VIEW_CODES:
        print(f"수집 시작: {vw_cd} {VIEW_CODES[vw_cd]}", flush=True)
        result = crawl_view(api_key, vw_cd)
        print(
            f"수집 완료: {vw_cd} 요청 {result.request_count:,}회, "
            f"분류 {result.category_count:,}개, 통계표 {result.table_count:,}개",
            flush=True,
        )
        results.append(result)

    write_outputs(results)
    print(OUT / "KOSIS_API_CATALOG_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
