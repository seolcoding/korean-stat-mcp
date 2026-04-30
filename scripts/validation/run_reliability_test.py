# /// script
# requires-python = ">=3.11"
# dependencies = ["loguru"]
# ///
"""Reliability test for korean-stat-mcp KOSIS API coverage.

Picks a random sample of tables from the local metadata catalog and
verifies that get_statistics_data() returns a usable response. Tracks
pass/fail rates plus per-failure reason categorization (no_data,
api_error, timeout, parse_error).

Usage:
    # Pilot run (~2 minutes at 1 req/sec)
    uv run python scripts/validation/run_reliability_test.py --n 100

    # Full reliability gate (~3 hours)
    uv run python scripts/validation/run_reliability_test.py --n 10000

    # Dry run (no live calls; just validates the sampling logic)
    uv run python scripts/validation/run_reliability_test.py --dry-run --n 100
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

try:
    from loguru import logger  # type: ignore[import-not-found]

    _USING_LOGURU = True
except ModuleNotFoundError:  # pragma: no cover — fallback for envs without loguru
    import logging as _logging

    _USING_LOGURU = False

    class _StdlibLoggerShim:
        """Minimal loguru-compatible facade backed by stdlib logging."""

        def __init__(self) -> None:
            self._logger = _logging.getLogger("reliability_test")
            if not self._logger.handlers:
                handler = _logging.StreamHandler()
                handler.setFormatter(
                    _logging.Formatter(
                        "%(asctime)s | %(levelname)-7s | %(message)s",
                        datefmt="%H:%M:%S",
                    )
                )
                self._logger.addHandler(handler)
            self._logger.setLevel(_logging.INFO)

        def remove(self) -> None:
            for h in list(self._logger.handlers):
                self._logger.removeHandler(h)

        def add(
            self, sink: Any, *, level: str = "INFO", format: str | None = None
        ) -> None:  # noqa: A002
            handler = (
                _logging.StreamHandler(sink)
                if hasattr(sink, "write")
                else _logging.StreamHandler()
            )
            handler.setFormatter(
                _logging.Formatter(
                    "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%H:%M:%S"
                )
            )
            self._logger.addHandler(handler)
            self._logger.setLevel(getattr(_logging, level.upper(), _logging.INFO))

        def debug(self, msg: str) -> None:
            self._logger.debug(msg)

        def info(self, msg: str) -> None:
            self._logger.info(msg)

        def warning(self, msg: str) -> None:
            self._logger.warning(msg)

        def error(self, msg: str) -> None:
            self._logger.error(msg)

    logger = _StdlibLoggerShim()  # type: ignore[assignment]

# Make src/ importable so we can use the canonical fetch.
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

Category = Literal["success", "no_data", "api_error", "timeout", "parse_error"]

DEFAULT_CATALOG = REPO_ROOT / "data" / "metadata_api" / "tables.json"
FALLBACK_CATALOG = REPO_ROOT / "outputs" / "kosis-api-catalog" / "tables.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--n", type=int, default=100, help="Sample size (default 100, max 10000)"
    )
    p.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip live API calls; only validate sampling",
    )
    p.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Seconds between requests (default 1.0)",
    )
    p.add_argument(
        "--catalog-path", type=Path, default=DEFAULT_CATALOG, help="Path to tables.json"
    )
    p.add_argument("--out", type=Path, default=None, help="Output JSON path")
    p.add_argument(
        "--gate-threshold",
        type=float,
        default=0.99,
        help="Pass threshold for exit-code 0",
    )
    return p.parse_args()


def load_catalog(path: Path) -> tuple[list[dict[str, Any]], Path | None]:
    """Load catalog records. Falls back to outputs/kosis-api-catalog/tables.json.

    Returns (records, source_path). source_path is None if no catalog found.
    """
    candidates = [path]
    if path != FALLBACK_CATALOG:
        candidates.append(FALLBACK_CATALOG)

    for candidate in candidates:
        if not candidate.exists():
            logger.debug(f"Catalog not found: {candidate}")
            continue
        try:
            with candidate.open(encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Failed to read catalog {candidate}: {exc}")
            continue

        records: list[dict[str, Any]]
        if isinstance(raw, list):
            records = raw
        elif isinstance(raw, dict) and isinstance(raw.get("tables"), list):
            records = raw["tables"]
        else:
            logger.warning(f"Catalog {candidate} has unrecognized shape")
            continue

        if not records:
            logger.warning(f"Catalog {candidate} is empty")
            continue

        logger.info(f"Loaded {len(records)} records from {candidate}")
        return records, candidate

    return [], None


def sample_pairs(
    records: list[dict[str, Any]], n: int, seed: int
) -> list[tuple[str, str]]:
    """Sample (org_id, tbl_id) pairs without replacement."""
    valid = [
        (str(r["org_id"]), str(r["tbl_id"]))
        for r in records
        if r.get("org_id") and r.get("tbl_id")
    ]
    if not valid:
        return []
    rng = random.Random(seed)
    k = min(n, len(valid))
    if k < n:
        logger.warning(
            f"Requested n={n} but only {len(valid)} valid records; sampling all of them."
        )
    return rng.sample(valid, k)


def categorize_failure(exc: BaseException) -> tuple[Category, str]:
    """Map an exception to a coarse category + message."""
    msg = f"{type(exc).__name__}: {exc}"
    name = type(exc).__name__.lower()
    if "timeout" in name:
        return "timeout", msg
    if any(s in name for s in ("decode", "json", "parse", "value")):
        return "parse_error", msg
    return "api_error", msg


def run_one(fetcher: Any, org_id: str, tbl_id: str) -> tuple[Category, str | None]:
    """Fetch one table, returning (category, message)."""
    try:
        rows = fetcher.get_data_with_smart_retry(org_id=org_id, tbl_id=tbl_id)
    except BaseException as exc:  # noqa: BLE001 — we want to categorize anything
        cat, msg = categorize_failure(exc)
        return cat, msg
    if rows:
        return "success", None
    return "no_data", "empty response"


def write_result(out_path: Path, payload: dict[str, Any]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"Wrote results to {out_path}")


def print_summary(payload: dict[str, Any]) -> None:
    cats = payload["categories"]
    print()
    print("=" * 56)
    print(f"  Reliability test summary  (n={payload['n']}, seed={payload['seed']})")
    print("=" * 56)
    print(f"  Started:   {payload['started_at']}")
    print(f"  Completed: {payload['completed_at']}")
    print(f"  Duration:  {payload['duration_seconds']:.1f}s")
    print("-" * 56)
    for k in ("success", "no_data", "api_error", "timeout", "parse_error"):
        print(f"  {k:<14} {cats.get(k, 0):>6}")
    print("-" * 56)
    print(f"  success_rate_strict             = {payload['success_rate_strict']:.4f}")
    print(
        f"  success_rate_excluding_no_data  = {payload['success_rate_excluding_no_data']:.4f}"
    )
    print("=" * 56)


def make_stub(reason: str, args: argparse.Namespace, out_path: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "n": args.n,
        "seed": args.seed,
        "started_at": now,
        "completed_at": now,
        "duration_seconds": 0.0,
        "rate_limit_sec": args.rate_limit,
        "categories": {
            "success": 0,
            "no_data": 0,
            "api_error": 0,
            "timeout": 0,
            "parse_error": 0,
        },
        "success_rate_strict": 0.0,
        "success_rate_excluding_no_data": 1.0,  # vacuous pass — nothing failed
        "failures": [],
        "stub": True,
        "stub_reason": reason,
    }
    write_result(out_path, payload)
    return payload


def main() -> int:
    args = parse_args()
    if args.n <= 0:
        logger.error("--n must be > 0")
        return 2
    args.n = min(args.n, 10_000)

    logger.remove()
    logger.add(
        sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level: <7} | {message}"
    )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = (
        args.out
        or REPO_ROOT / "outputs" / "validation" / f"reliability-{timestamp}.json"
    )

    # Load catalog (with fallback).
    records, source = load_catalog(args.catalog_path)
    if not records:
        stub_path = REPO_ROOT / "outputs" / "validation" / "reliability-pilot-stub.json"
        logger.warning("No catalog data found; writing stub and exiting 0.")
        make_stub("no catalog data found at primary or fallback path", args, stub_path)
        return 0

    # Sample.
    pairs = sample_pairs(records, args.n, args.seed)
    if not pairs:
        stub_path = REPO_ROOT / "outputs" / "validation" / "reliability-pilot-stub.json"
        logger.warning("Catalog had no valid (org_id, tbl_id) pairs; writing stub.")
        make_stub("catalog had no valid (org_id, tbl_id) pairs", args, stub_path)
        return 0

    logger.info(f"Sampled {len(pairs)} pairs from {source}")

    if args.dry_run:
        print()
        print(f"Dry-run: {len(pairs)} sampled pairs (showing first 10):")
        for org_id, tbl_id in pairs[:10]:
            print(f"  org_id={org_id:>5}  tbl_id={tbl_id}")
        print()
        # Also write a dry-run artifact so callers can inspect the sample.
        now = datetime.now(timezone.utc).isoformat()
        write_result(
            out_path,
            {
                "n": len(pairs),
                "seed": args.seed,
                "dry_run": True,
                "started_at": now,
                "completed_at": now,
                "duration_seconds": 0.0,
                "rate_limit_sec": args.rate_limit,
                "catalog_source": str(source),
                "categories": {
                    "success": 0,
                    "no_data": 0,
                    "api_error": 0,
                    "timeout": 0,
                    "parse_error": 0,
                },
                "success_rate_strict": 0.0,
                "success_rate_excluding_no_data": 1.0,
                "failures": [],
                "sample": [{"org_id": o, "tbl_id": t} for o, t in pairs],
            },
        )
        return 0

    # Live mode: need API key + canonical fetcher.
    import os

    if not os.getenv("KOSIS_API_KEY"):
        stub_path = REPO_ROOT / "outputs" / "validation" / "reliability-pilot-stub.json"
        logger.warning(
            "KOSIS_API_KEY not set; writing stub (skipped pilot) and exiting 0."
        )
        payload = make_stub("KOSIS_API_KEY not set in env", args, stub_path)
        print_summary(payload)
        return 0

    try:
        from kosis_tools.data import StatisticsData  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        logger.error(f"Cannot import kosis_tools.data.StatisticsData: {exc}")
        return 2

    fetcher = StatisticsData()

    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    counts: dict[str, int] = {
        "success": 0,
        "no_data": 0,
        "api_error": 0,
        "timeout": 0,
        "parse_error": 0,
    }
    failures: list[dict[str, str]] = []

    total = len(pairs)
    for i, (org_id, tbl_id) in enumerate(pairs, 1):
        cat, msg = run_one(fetcher, org_id, tbl_id)
        counts[cat] = counts.get(cat, 0) + 1
        if cat != "success":
            failures.append(
                {
                    "org_id": org_id,
                    "tbl_id": tbl_id,
                    "category": cat,
                    "message": msg or "",
                }
            )
        if i % 25 == 0 or i == total:
            logger.info(
                f"progress {i}/{total} "
                f"success={counts['success']} no_data={counts['no_data']} "
                f"api_error={counts['api_error']} timeout={counts['timeout']} parse_error={counts['parse_error']}"
            )
        if i < total and args.rate_limit > 0:
            time.sleep(args.rate_limit)

    completed = datetime.now(timezone.utc)
    duration = time.monotonic() - t0

    n = total
    real_failures = counts["api_error"] + counts["timeout"] + counts["parse_error"]
    denom_excl = max(n - counts["no_data"], 1)
    payload: dict[str, Any] = {
        "n": n,
        "seed": args.seed,
        "started_at": started.isoformat(),
        "completed_at": completed.isoformat(),
        "duration_seconds": round(duration, 2),
        "rate_limit_sec": args.rate_limit,
        "catalog_source": str(source),
        "categories": counts,
        "success_rate_strict": counts["success"] / n,
        "success_rate_excluding_no_data": (denom_excl - real_failures) / denom_excl,
        "failures": failures,
    }
    write_result(out_path, payload)
    print_summary(payload)

    if payload["success_rate_excluding_no_data"] >= args.gate_threshold:
        return 0
    logger.error(
        f"Gate FAILED: success_rate_excluding_no_data="
        f"{payload['success_rate_excluding_no_data']:.4f} < threshold={args.gate_threshold}"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
