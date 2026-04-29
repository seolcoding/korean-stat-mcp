#!/usr/bin/env python3
"""Verify onepager issue data against live KOSIS API.

The API key is read from KOSIS_API_KEY and is never written to disk.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "kosis-onepager"
ITEMS = OUT / "items"
LIVE = OUT / "live"
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kosis_tools.config import KosisConfig  # noqa: E402
from kosis_tools.data import StatisticsData  # noqa: E402


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def to_float(value: Any) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def flatten_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and "TBL_ID" in item and "DT" in item:
                records.append(item)
            else:
                records.extend(flatten_records(item))
    elif isinstance(value, dict):
        if "TBL_ID" in value and "DT" in value:
            records.append(value)
        for child in value.values():
            records.extend(flatten_records(child))
    return records


def primary_points(item: dict[str, Any]) -> list[dict[str, Any]]:
    series = item.get("series")
    if isinstance(series, list) and series:
        first = series[0]
        if isinstance(first, dict):
            for key in ("values", "points", "records"):
                if isinstance(first.get(key), list):
                    return first[key]
            if "year" in first:
                return [
                    {"period": str(row.get("year")), "value": row.get("value", row.get("annual_compounded_change_pct"))}
                    for row in series
                    if isinstance(row, dict)
                ]
    if isinstance(series, dict):
        for value in series.values():
            if isinstance(value, list):
                return value
    return []


def match_source_record(item: dict[str, Any]) -> dict[str, Any] | None:
    source_file = item.get("source_file")
    if item.get("id") == "energy":
        source_file = "kosis-reports/data/report_010_energy.json"
    if not source_file:
        return None
    source_path = ROOT / source_file
    if not source_path.exists():
        return None
    source_records = flatten_records(load_json(source_path))
    table_ids = set(map(str, item.get("table_ids", [])))
    points = primary_points(item)
    if not source_records or not points:
        return None
    candidates = [r for r in source_records if not table_ids or str(r.get("TBL_ID")) in table_ids]
    for point in points:
        period = str(point.get("period", ""))
        value = to_float(point.get("value"))
        if not period or value is None:
            continue
        for row in candidates:
            row_period = str(row.get("PRD_DE", ""))
            row_value = to_float(row.get("DT"))
            if row_period == period and row_value is not None and abs(row_value - value) < 0.001:
                return row
    return candidates[0] if candidates else None


def request_params_from_row(row: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    points = primary_points(item)
    periods = sorted(str(p.get("period")) for p in points if p.get("period"))
    prd_se = str(row.get("PRD_SE") or "Y")
    if prd_se == "A":
        prd_se = "Y"
    params: dict[str, Any] = {
        "org_id": str(row.get("ORG_ID")),
        "tbl_id": str(row.get("TBL_ID")),
        "start_date": periods[0] if periods else str(row.get("PRD_DE")),
        "end_date": periods[-1] if periods else str(row.get("PRD_DE")),
        "prd_se": prd_se,
        "itm_id": str(row.get("ITM_ID") or "ALL"),
    }
    for level in range(1, 9):
        code = row.get(f"C{level}")
        if code:
            params[f"obj_l{level}"] = str(code)
    params.setdefault("obj_l1", "ALL")
    return params


def main() -> int:
    LIVE.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("KOSIS_API_KEY")
    if not key:
        print("KOSIS_API_KEY is required", file=sys.stderr)
        return 2
    client = StatisticsData(KosisConfig(api_key=key, rate_limit_delay=0.05, timeout=30))
    results = []
    for item_path in sorted(ITEMS.glob("*.json")):
        item = load_json(item_path)
        row = match_source_record(item)
        if not row:
            results.append({"id": item.get("id"), "status": "no_source_match"})
            continue
        params = request_params_from_row(row, item)
        call_params = dict(params)
        obj_kwargs = {k: call_params.pop(k) for k in list(call_params) if k.startswith("obj_l")}
        try:
            records = client.get_data(**call_params, **obj_kwargs)
            sample = records[:5]
            status = "ok" if records else "empty"
            result = {
                "id": item.get("id"),
                "status": status,
                "endpoint": "https://kosis.kr/openapi/Param/statisticsParameterData.do",
                "params": {
                    "orgId": params["org_id"],
                    "tblId": params["tbl_id"],
                    "prdSe": params["prd_se"],
                    "startPrdDe": params["start_date"],
                    "endPrdDe": params["end_date"],
                    "itmId": params["itm_id"],
                    **{f"objL{k[-1]}": v for k, v in params.items() if k.startswith("obj_l")},
                },
                "record_count": len(records),
                "sample": sample,
            }
        except Exception as exc:
            result = {
                "id": item.get("id"),
                "status": "error",
                "endpoint": "https://kosis.kr/openapi/Param/statisticsParameterData.do",
                "params": {
                    "orgId": params["org_id"],
                    "tblId": params["tbl_id"],
                    "prdSe": params["prd_se"],
                    "startPrdDe": params["start_date"],
                    "endPrdDe": params["end_date"],
                    "itmId": params["itm_id"],
                    **{f"objL{k[-1]}": v for k, v in params.items() if k.startswith("obj_l")},
                },
                "error": str(exc),
            }
        results.append(result)
        (LIVE / f"{item['id']}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (LIVE / "index.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": sum(1 for r in results if r.get("status") == "ok"), "total": len(results)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
