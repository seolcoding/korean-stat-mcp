"""Core KOSIS data helpers used by the MCP server.

This module intentionally keeps only discovery, fetch, filtering, aggregation,
and stored-data access. Native visualization/report generation belongs in the
client or in a dedicated downstream workflow.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Union

from .config import DataStorageConfig


def _generate_data_id(data: list[dict[str, Any]]) -> str:
    first = data[0] if data else {}
    last = data[-1] if data else {}
    content = (
        f"{len(data)}:{first.get('TBL_ID', '')}:{first.get('PRD_DE', '')}:"
        f"{last.get('PRD_DE', '')}"
    )
    suffix = hashlib.md5(content.encode()).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{suffix}"


def save_raw_data(
    data: list[dict[str, Any]],
    data_id: Optional[str] = None,
) -> dict[str, Any]:
    """Store raw KOSIS records and return a compact reference."""
    if not data:
        return {"error": "저장할 데이터가 없습니다", "data_id": None}

    data_id = data_id or _generate_data_id(data)
    file_path = Path(DataStorageConfig.get_data_dir()) / f"{data_id}.json"
    storage_obj = {
        "meta": {
            "data_id": data_id,
            "record_count": len(data),
            "created_at": datetime.now().isoformat(),
            "tbl_id": data[0].get("TBL_ID", ""),
            "tbl_nm": data[0].get("TBL_NM", ""),
        },
        "data": data,
    }

    with file_path.open("w", encoding="utf-8") as f:
        json.dump(storage_obj, f, ensure_ascii=False, indent=2)

    return {
        "data_id": data_id,
        "file_path": str(file_path),
        "record_count": len(data),
        "file_size_kb": round(file_path.stat().st_size / 1024, 1),
        "created_at": storage_obj["meta"]["created_at"],
    }


def load_raw_data(
    data_id: str,
    chunk_index: Optional[int] = None,
    chunk_size: int = 50,
) -> dict[str, Any]:
    """Load stored raw records, optionally by chunk."""
    file_path = Path(DataStorageConfig.get_data_dir()) / f"{data_id}.json"
    if not file_path.exists():
        return {"error": f"데이터를 찾을 수 없습니다: {data_id}", "data_id": data_id}

    with file_path.open("r", encoding="utf-8") as f:
        storage_obj = json.load(f)

    meta = storage_obj.get("meta", {})
    data = storage_obj.get("data", [])

    if chunk_index is None:
        return {"data_id": data_id, "meta": meta, "data": data}

    total_records = len(data)
    total_chunks = (total_records + chunk_size - 1) // chunk_size
    if chunk_index >= total_chunks:
        return {
            "error": f"청크 인덱스 초과: {chunk_index} >= {total_chunks}",
            "data_id": data_id,
        }

    start = chunk_index * chunk_size
    end = min(start + chunk_size, total_records)
    return {
        "data_id": data_id,
        "meta": meta,
        "data": data[start:end],
        "chunk_info": {
            "chunk_index": chunk_index,
            "chunk_size": len(data[start:end]),
            "total_chunks": total_chunks,
            "total_records": total_records,
            "has_more": end < total_records,
        },
    }


def list_saved_data() -> list[dict[str, Any]]:
    """Return stored raw-data files."""
    data_dir = Path(DataStorageConfig.get_data_dir())
    result: list[dict[str, Any]] = []

    for file_path in sorted(data_dir.glob("*.json"), reverse=True):
        try:
            with file_path.open("r", encoding="utf-8") as f:
                storage_obj = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        meta = storage_obj.get("meta", {})
        result.append(
            {
                "data_id": meta.get("data_id", file_path.stem),
                "file_path": str(file_path),
                "file_size_kb": round(file_path.stat().st_size / 1024, 1),
                "created_at": meta.get("created_at", ""),
                "record_count": meta.get("record_count", 0),
                "tbl_id": meta.get("tbl_id", ""),
                "tbl_nm": meta.get("tbl_nm", ""),
            }
        )

    return result


def search_tables(
    keyword: str,
    org_id: Optional[str] = None,
    limit: int = 10,
    *,
    sort: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Search KOSIS statistics tables by keyword.

    Args:
        sort: KOSIS-native ordering — "RANK" (relevance, default) or
            "DATE" (most recently updated tables first). None defers to
            KOSIS's default (RANK).
    """
    from .search import StatisticsSearch

    results = StatisticsSearch().search(keyword, sort=sort)  # type: ignore[arg-type]
    if org_id:
        results = [r for r in results if r.get("ORG_ID") == org_id]

    normalized: list[dict[str, Any]] = []
    for row in results[:limit]:
        period = row.get("PRD_DE", "")
        start_prd, end_prd = (
            [p.strip() for p in period.split("~", maxsplit=1)]
            if "~" in period
            else (period, period)
        )
        normalized.append(
            {
                "tbl_id": row.get("TBL_ID", ""),
                "tbl_nm": row.get("TBL_NM", ""),
                "org_id": row.get("ORG_ID", ""),
                "org_nm": row.get("ORG_NM", ""),
                "start_prd": start_prd,
                "end_prd": end_prd,
                "prd_se": row.get("PRD_SE", "Y"),
            }
        )

    return normalized


def browse_categories(
    by: str = "org",
    code: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Browse statistics by organization or theme."""
    from .list_categories import CategoryList, OrgCode, ThemeCode

    if by == "org" and not code:
        return [
            {"code": OrgCode.KOSTAT, "name": "통계청"},
            {"code": OrgCode.MOF, "name": "기획재정부"},
            {"code": OrgCode.MOEL, "name": "고용노동부"},
            {"code": OrgCode.BOK, "name": "한국은행"},
            {"code": OrgCode.MOLIT, "name": "국토교통부"},
            {"code": OrgCode.MOE, "name": "교육부"},
            {"code": OrgCode.MOHW, "name": "보건복지부"},
            {"code": OrgCode.ME, "name": "환경부"},
        ]
    if by == "theme" and not code:
        return [
            {"code": ThemeCode.POPULATION, "name": "인구"},
            {"code": ThemeCode.LABOR, "name": "고용/노동/임금"},
            {"code": ThemeCode.AGRICULTURE, "name": "농림수산업"},
            {"code": ThemeCode.MINING, "name": "광업/제조업/에너지"},
            {"code": ThemeCode.CONSTRUCTION, "name": "건설"},
            {"code": ThemeCode.TRANSPORT, "name": "교통/정보통신"},
            {"code": ThemeCode.TRADE, "name": "도소매/서비스업"},
            {"code": ThemeCode.ECONOMY, "name": "경기/기업경영"},
            {"code": ThemeCode.FINANCE, "name": "물가/가계/소비"},
            {"code": ThemeCode.HEALTH, "name": "보건/사회/복지"},
            {"code": ThemeCode.EDUCATION, "name": "교육/문화/과학"},
            {"code": ThemeCode.SAFETY, "name": "환경/재해/안전"},
            {"code": ThemeCode.ADMIN, "name": "행정/사법"},
            {"code": ThemeCode.NATIONAL_ACCOUNT, "name": "국민계정/재정/금융"},
            {"code": ThemeCode.INTERNATIONAL, "name": "국제/북한"},
        ]

    if not code:
        return []

    client = CategoryList()
    if by == "org":
        return client.list_by_org(code)
    if by == "theme":
        return client.list_by_theme(code)
    return []


def get_table_meta(org_id: str, tbl_id: str) -> dict[str, Any]:
    """Fetch KOSIS OpenAPI metadata for a table."""
    from collections import defaultdict

    from .table_meta import TableMetadata

    raw_meta = TableMetadata().get_all_metadata(org_id, tbl_id)
    if not raw_meta:
        return {}

    table_info = raw_meta.get("table_info") or {}
    dimensions = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in raw_meta.get("obj_vars") or []:
        grouped[item.get("OBJ_ID", "C1")].append(item)

    for obj_id, items in grouped.items():
        if items:
            dimensions.append(
                {
                    "id": obj_id,
                    "name": items[0].get("OBJ_NM", ""),
                    "values": [item.get("ITM_NM", "") for item in items],
                }
            )

    meta_items = [
        {"id": item.get("ITM_ID", ""), "name": item.get("ITM_NM", "")}
        for item in raw_meta.get("itm_vars") or []
    ]

    prd_info = raw_meta.get("prd_info") or []
    prd_se = "Y"
    start_prd = ""
    end_prd = ""
    if prd_info:
        first_prd = prd_info[0]
        prd_se = {"년": "Y", "월": "M", "분기": "Q", "반기": "S"}.get(
            first_prd.get("PRD_SE", "년"), "Y"
        )
        start_prd = first_prd.get("STRT_PRD_DE", "")
        end_prd = first_prd.get("END_PRD_DE", "")

    return {
        "tbl_id": tbl_id,
        "tbl_nm": table_info.get("TBL_NM", ""),
        "org_id": org_id,
        "org_nm": table_info.get("ORG_NM", ""),
        "prd_se": prd_se,
        "start_prd": start_prd,
        "end_prd": end_prd,
        "dimensions": dimensions,
        "items": meta_items,
        "raw": raw_meta,
    }


def get_available_values(data: list[dict[str, Any]], field: str) -> list[str]:
    """Return sorted unique values for a field."""
    return sorted({str(row[field]) for row in data if field in row and row[field]})


def format_data_for_llm(
    data: list[dict[str, Any]],
    max_rows: int = 50,
    include_sample: bool = True,
    save_raw: bool = True,
) -> dict[str, Any]:
    """Return a compact summary and optional raw-data reference."""
    if not data:
        return {"error": "데이터가 없습니다", "total_records": 0}

    first = data[0]
    metadata = {
        "tbl_id": first.get("TBL_ID", ""),
        "tbl_nm": first.get("TBL_NM", ""),
        "org_id": first.get("ORG_ID", ""),
        "org_nm": first.get("ORG_NM", ""),
        "unit": first.get("UNIT_NM", ""),
    }

    key_fields = ["PRD_DE", "C1_NM", "C2_NM", "C3_NM", "ITM_NM"]
    unique_values = {
        field: sorted({row[field] for row in data if row.get(field)})
        for field in key_fields
    }
    unique_values = {k: v for k, v in unique_values.items() if v}

    periods = unique_values.get("PRD_DE", [])
    period_range = (
        f"{periods[0]}~{periods[-1]}"
        if len(periods) > 1
        else (periods[0] if periods else "N/A")
    )
    dimensions = [
        first.get(field.replace("_NM", "_OBJ_NM"), field)
        for field in ["C1_NM", "C2_NM", "C3_NM"]
        if field in unique_values
    ]

    data_preview: list[dict[str, Any]] = []
    if include_sample:
        latest_period = periods[-1] if periods else None
        sample_data = [row for row in data if row.get("PRD_DE") == latest_period]
        if not sample_data:
            sample_data = data
        field_names = {
            "PRD_DE": "기간",
            "C1_NM": "분류1",
            "C2_NM": "분류2",
            "ITM_NM": "항목",
            "DT": "값",
        }
        for row in sample_data[:max_rows]:
            preview_row = {
                field_names.get(field, field): row[field]
                for field in ["PRD_DE", "C1_NM", "C2_NM", "ITM_NM", "DT"]
                if row.get(field)
            }
            if preview_row:
                data_preview.append(preview_row)

    pivot_summary: dict[str, Any] = {}
    if periods:
        by_period: dict[str, float] = {}
        for period in periods[-5:]:
            total = 0.0
            for row in data:
                if row.get("PRD_DE") != period:
                    continue
                try:
                    total += float(str(row.get("DT", "0")).replace(",", ""))
                except (TypeError, ValueError):
                    continue
            by_period[period] = total
        pivot_summary["by_period"] = by_period

    c1_values = unique_values.get("C1_NM", [])
    if c1_values:
        by_c1: dict[str, float] = {}
        for c1_value in c1_values[:10]:
            total = 0.0
            for row in data:
                if row.get("C1_NM") != c1_value:
                    continue
                try:
                    total += float(str(row.get("DT", "0")).replace(",", ""))
                except (TypeError, ValueError):
                    continue
            by_c1[c1_value] = total
        pivot_summary["by_c1"] = dict(
            sorted(by_c1.items(), key=lambda item: item[1], reverse=True)
        )

    raw_data_file = None
    if save_raw:
        save_result = save_raw_data(data)
        if "error" not in save_result:
            raw_data_file = {
                "data_id": save_result["data_id"],
                "file_path": save_result["file_path"],
                "record_count": save_result["record_count"],
                "file_size_kb": save_result["file_size_kb"],
                "access_hint": (
                    f"read_stored_data('{save_result['data_id']}')로 전체 데이터 접근, "
                    f"read_stored_data('{save_result['data_id']}', chunk_index=0)로 청크별 접근"
                ),
            }

    result: dict[str, Any] = {
        "summary": {
            "total_records": len(data),
            "period_range": period_range,
            "period_count": len(periods),
            "dimensions": dimensions,
            "dimension_counts": {
                field: len(values)
                for field, values in unique_values.items()
                if field.startswith("C") and field.endswith("_NM")
            },
            "items": unique_values.get("ITM_NM", []),
            "item_count": len(unique_values.get("ITM_NM", [])),
        },
        "metadata": metadata,
        "data_preview": data_preview,
        "pivot_summary": pivot_summary,
        "data_availability": {
            "full_data_available": True,
            "sample_period": periods[-1] if periods else None,
            "sample_count": len(data_preview),
            "note": (
                f"전체 {len(data)}건 중 샘플 {len(data_preview)}건 제공"
                if len(data) > max_rows
                else "전체 데이터 제공"
            ),
        },
        "available_values": {
            field: values[:20] if len(values) > 20 else values
            for field, values in unique_values.items()
        },
    }
    if raw_data_file:
        result["raw_data_file"] = raw_data_file
    return result


def fetch_data(
    org_id: str,
    tbl_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    prd_se: Optional[str] = None,
    *,
    new_est_prd_cnt: Optional[int] = None,
    prd_interval: Optional[int] = None,
    **filters: Any,
) -> list[dict[str, Any]]:
    """Fetch KOSIS records with the metadata-aware retry path.

    Period helpers (KOSIS native):
        new_est_prd_cnt: limit response to the most-recent N periods
            (KOSIS `newEstPrdCnt`). Bypasses metadata-driven retry so the
            user's "last N" intent is preserved exactly.
        prd_interval: stride in periods (KOSIS `prdInterval`); e.g. 2 with
            prd_se='Y' yields biennial data.
    """
    from .data import StatisticsData

    return (
        StatisticsData().get_data_with_smart_retry(
            org_id=org_id,
            tbl_id=tbl_id,
            start_date=start_date,
            end_date=end_date,
            prd_se=prd_se,
            new_est_prd_cnt=new_est_prd_cnt,
            prd_interval=prd_interval,
            **filters,
        )
        or []
    )


def filter_data(
    data: list[dict[str, Any]],
    regions: Optional[list[str]] = None,
    periods: Optional[list[str]] = None,
    items: Optional[list[str]] = None,
    custom_filter: Optional[Callable[[dict[str, Any]], bool]] = None,
) -> list[dict[str, Any]]:
    """Filter records by common KOSIS dimensions."""
    result = data
    if regions:
        result = [row for row in result if row.get("C1_NM") in regions]
    if periods:
        result = [row for row in result if row.get("PRD_DE") in periods]
    if items:
        result = [row for row in result if row.get("ITM_NM") in items]
    if custom_filter:
        result = [row for row in result if custom_filter(row)]
    return result


def aggregate_data(
    data: list[dict[str, Any]],
    group_by: Union[str, list[str]],
    value_field: str = "DT",
    agg_func: str = "sum",
) -> list[dict[str, Any]]:
    """Aggregate records without pulling in dataframe dependencies."""
    group_fields = [group_by] if isinstance(group_by, str) else group_by
    buckets: dict[tuple[Any, ...], list[float]] = {}

    for row in data:
        key = tuple(row.get(field) for field in group_fields)
        if agg_func == "count":
            value = 1.0
        else:
            try:
                value = float(str(row.get(value_field, "0")).replace(",", ""))
            except (TypeError, ValueError):
                continue
        buckets.setdefault(key, []).append(value)

    result: list[dict[str, Any]] = []
    for key, values in buckets.items():
        output = {field: key[index] for index, field in enumerate(group_fields)}
        if agg_func == "sum":
            aggregated = sum(values)
        elif agg_func == "mean":
            aggregated = sum(values) / len(values) if values else 0
        elif agg_func == "min":
            aggregated = min(values) if values else 0
        elif agg_func == "max":
            aggregated = max(values) if values else 0
        elif agg_func == "count":
            aggregated = len(values)
        else:
            raise ValueError(f"지원하지 않는 집계 함수: {agg_func}")
        output[value_field] = aggregated
        result.append(output)

    return result
