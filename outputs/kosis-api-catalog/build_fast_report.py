#!/usr/bin/env python3
"""Fast KOSIS OpenAPI capability and table catalog report.

This uses:
- statisticsSearch.do with a blank-space query to retrieve the API-visible
  table catalog page, up to the API's returned maximum.
- statisticsList.do root calls to list available top-level views/categories.

KOSIS_API_KEY is read from the environment and never persisted.
"""

from __future__ import annotations

import json
import os
from collections import Counter
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
    ["통계목록", "statisticsList.do", "JSON, SDMX", "분류 트리와 통계표 목록 탐색"],
    ["통계자료", "Param/statisticsParameterData.do / statisticsData.do", "JSON, SDMX", "수치 데이터 조회"],
    ["대용량 통계자료", "statisticsBigData.do", "SDMX, XLS", "사전 등록 기반 대용량 조회"],
    ["통계설명자료", "statisticsExplData.do", "JSON, XML", "조사 목적, 작성 유형, 법적 근거, 조사 주기 등 설명"],
    ["통계표설명/메타", "statisticsData.do?method=getMeta", "JSON", "통계표명, 기관, 분류, 항목, 기간, 단위, 출처, 갱신일"],
    ["KOSIS 통합검색", "statisticsSearch.do", "JSON", "키워드 기반 통계표 검색과 링크/경로 보강"],
    ["통계주요지표", "pkNumberService.do 등", "JSON, XML", "주요지표 설명, 목록, 상세 시계열"],
]

META_TYPES = [
    ["TBL", "통계표 기본 정보"],
    ["ORG", "기관 정보"],
    ["PRD", "수록기간/주기"],
    ["OBJ_VAR", "분류 차원"],
    ["ITM_VAR", "항목"],
    ["CMMT", "주석"],
    ["UNIT", "단위"],
    ["SOURCE", "출처"],
    ["WGT", "가중치"],
    ["NCD", "자료갱신일"],
]

EXPLANATION_ITEMS = [
    "All", "statsNm", "statsKind", "statsEnd", "statsContinue", "basisLaw",
    "writingPurps", "examinPd", "statsPeriod", "writingSystem", "writingTel",
    "statsField", "examinObjrange", "examinObjArea", "josaUnit", "applyGroup",
    "josaItm", "pubPeriod", "pubExtent", "pubDate", "publictMth",
    "examinTrgetPd", "dataUserNote", "mainTermExpl", "dataCollectMth",
    "examinHistory", "confmNo", "confmDt",
]


def request_json(api_key: str, endpoint: str, params: dict[str, Any]) -> Any:
    params = dict(params)
    params["apiKey"] = api_key
    params.setdefault("format", "json")
    res = requests.get(f"{BASE}/{endpoint}", params=params, timeout=60)
    res.raise_for_status()
    return json5.loads(res.text)


def as_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "err" not in data:
        return [data]
    return []


def fetch_catalog(api_key: str) -> list[dict[str, Any]]:
    data = request_json(
        api_key,
        "statisticsSearch.do",
        {
            "method": "getList",
            "searchNm": " ",
            "resultCount": 5000,
            "startCount": 1,
        },
    )
    rows = as_list(data)

    # Confirm whether pagination continues beyond 5,000.
    next_page = request_json(
        api_key,
        "statisticsSearch.do",
        {
            "method": "getList",
            "searchNm": " ",
            "resultCount": 5000,
            "startCount": 5001,
        },
    )
    if as_list(next_page):
        rows.extend(as_list(next_page))

    return rows


def fetch_roots(api_key: str) -> dict[str, list[dict[str, Any]]]:
    roots = {}
    for code in VIEW_CODES:
        rows = request_json(
            api_key,
            "statisticsList.do",
            {"method": "getList", "vwCd": code},
        )
        roots[code] = as_list(rows)
    return roots


def norm(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "org_id": row.get("ORG_ID"),
        "org_nm": row.get("ORG_NM"),
        "tbl_id": row.get("TBL_ID"),
        "tbl_nm": row.get("TBL_NM"),
        "stat_id": row.get("STAT_ID"),
        "stat_nm": row.get("STAT_NM"),
        "vw_cd": row.get("VW_CD"),
        "category_path": row.get("MT_ATITLE"),
        "full_path_id": row.get("FULL_PATH_ID"),
        "contents": row.get("CONTENTS"),
        "start_period": row.get("STRT_PRD_DE"),
        "end_period": row.get("END_PRD_DE"),
        "source_note": row.get("ITEM03"),
        "table_url": row.get("LINK_URL"),
        "view_url": row.get("TBL_VIEW_URL"),
        "rec_tbl_se": row.get("REC_TBL_SE"),
        "stat_db_cnt": row.get("STAT_DB_CNT"),
    }


def write_report(rows: list[dict[str, Any]], roots: dict[str, list[dict[str, Any]]]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    tables = [norm(r) for r in rows if r.get("TBL_ID")]
    seen = {}
    for row in tables:
        seen.setdefault(row["tbl_id"], row)
    unique = list(seen.values())

    view_counts = Counter(row.get("vw_cd") or "미상" for row in unique)
    org_counts = Counter((row.get("org_nm") or row.get("org_id") or "미상") for row in unique)
    stat_counts = Counter((row.get("stat_nm") or row.get("stat_id") or "미상") for row in unique)
    category_counts = Counter((row.get("category_path") or "미분류").split(" > ")[0] for row in unique)
    period_counts = Counter()
    for row in unique:
        end = row.get("end_period")
        if end:
            period_counts[str(end)[:4]] += 1

    unique.sort(key=lambda r: ((r.get("category_path") or ""), r.get("tbl_nm") or ""))

    summary = {
        "generated_at": date.today().isoformat(),
        "api_base": BASE,
        "catalog_source": "statisticsSearch.do?searchNm=<space>&resultCount=5000",
        "returned_rows": len(rows),
        "unique_table_count": len(unique),
        "view_counts": view_counts,
        "top_org_counts": org_counts.most_common(50),
        "top_stat_counts": stat_counts.most_common(50),
        "top_category_counts": category_counts.most_common(100),
        "end_period_counts": period_counts.most_common(30),
        "root_categories": {
            code: [
                {
                    "list_id": item.get("LIST_ID"),
                    "list_nm": item.get("LIST_NM"),
                    "vw_nm": item.get("VW_NM"),
                    "vw_cd": item.get("VW_CD"),
                }
                for item in items
            ]
            for code, items in roots.items()
        },
        "api_groups": API_GROUPS,
        "metadata_types": META_TYPES,
        "statistics_explanation_items": EXPLANATION_ITEMS,
    }

    (OUT / "kosis-table-catalog.json").write_text(
        json.dumps(unique, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUT / "kosis-api-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = []
    lines.append("# KOSIS OpenAPI 기능/API/조회 가능 통계 전체 보고\n")
    lines.append(f"- 생성일: {date.today().isoformat()}")
    lines.append(f"- 기준 API: `{BASE}`")
    lines.append("- 사용한 실제 API: `statisticsSearch.do`, `statisticsList.do`")
    lines.append("- 인증키는 환경변수에서 읽어 호출에만 사용했고 산출물에는 저장하지 않았습니다.")
    lines.append(f"- 검색 API 반환 통계표: **{len(rows):,}행**, 중복 제거 후 **{len(unique):,}개 통계표**")
    lines.append("")
    lines.append("## 1. 사용 가능한 API 기능")
    lines.append("| 구분 | 엔드포인트 | 제공 형식 | 가능한 작업 |")
    lines.append("|---|---|---|---|")
    for group, endpoint, formats, purpose in API_GROUPS:
        lines.append(f"| {group} | `{endpoint}` | {formats} | {purpose} |")
    lines.append("")
    lines.append("## 2. 통계자료 조회 파라미터")
    lines.append("- 필수 축: `orgId`, `tblId`, `itmId`, `prdSe`, 기간(`startPrdDe`/`endPrdDe` 또는 `newEstPrdCnt`)")
    lines.append("- 분류 축: `objL1`~`objL8`까지 테이블별 사용")
    lines.append("- 기간 주기: `Y` 연간, `M` 월간, `Q` 분기, `S/H` 반기, `F` 다년, `IR` 불규칙")
    lines.append("- 제한: 분당 1,000회, 일반 통계자료 요청당 40,000셀, 대용량 XLS 200,000셀")
    lines.append("")
    lines.append("## 3. 메타데이터 조회 가능 항목")
    lines.append("| type | 의미 |")
    lines.append("|---|---|")
    for code, desc in META_TYPES:
        lines.append(f"| `{code}` | {desc} |")
    lines.append("")
    lines.append("## 4. 통계설명 조회 가능 항목")
    lines.append(", ".join(f"`{x}`" for x in EXPLANATION_ITEMS))
    lines.append("")
    lines.append("## 5. 통계목록 최상위 뷰")
    for code, name in VIEW_CODES.items():
        lines.append(f"### {name} (`{code}`)")
        lines.append("| ID | 이름 |")
        lines.append("|---|---|")
        for item in roots.get(code, []):
            lines.append(f"| `{item.get('LIST_ID')}` | {item.get('LIST_NM')} |")
        lines.append("")
    lines.append("## 6. 조회 가능한 통계 분야 요약")
    lines.append("| 분야/경로 최상위 | 통계표 수 |")
    lines.append("|---|---:|")
    for name, count in category_counts.most_common(100):
        lines.append(f"| {name} | {count:,} |")
    lines.append("")
    lines.append("## 7. 기관별 상위 통계표 수")
    lines.append("| 기관 | 통계표 수 |")
    lines.append("|---|---:|")
    for name, count in org_counts.most_common(50):
        lines.append(f"| {name} | {count:,} |")
    lines.append("")
    lines.append("## 8. 조회 가능한 통계표 목록 샘플")
    lines.append("| 통계표 ID | 통계표명 | 기관 | 통계명 | 수록기간 | 경로 |")
    lines.append("|---|---|---|---|---|---|")
    for row in unique[:300]:
        period = f"{row.get('start_period') or ''}~{row.get('end_period') or ''}".strip("~")
        lines.append(
            f"| `{row.get('tbl_id')}` | {row.get('tbl_nm') or ''} | "
            f"{row.get('org_nm') or ''} | {row.get('stat_nm') or ''} | "
            f"{period} | {row.get('category_path') or ''} |"
        )
    lines.append("")
    lines.append("## 9. 전체 목록 파일")
    lines.append("- `kosis-table-catalog.json`: 조회 가능한 통계표 전체 반환 목록")
    lines.append("- `kosis-api-summary.json`: API 기능, 분류, 집계 요약")
    (OUT / "KOSIS_API_FULL_REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    api_key = os.environ.get("KOSIS_API_KEY")
    if not api_key:
        raise SystemExit("KOSIS_API_KEY is required")
    rows = fetch_catalog(api_key)
    roots = fetch_roots(api_key)
    write_report(rows, roots)
    print(OUT / "KOSIS_API_FULL_REPORT.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
