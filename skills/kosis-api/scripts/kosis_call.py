#!/usr/bin/env python3
"""Minimal KOSIS OpenAPI smoke-test caller.

This script is intentionally small. For production work, import and use
src/kosis_tools modules instead.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def parse_response(text: str) -> Any:
    try:
        from kosis_tools.base import parse_kosis_json

        return parse_kosis_json(text)
    except Exception:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text[:2000]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Call a KOSIS OpenAPI endpoint.")
    parser.add_argument("endpoint", help="Endpoint path, e.g. statisticsList.do")
    parser.add_argument("--param", action="append", default=[], help="Query param as key=value")
    parser.add_argument("--base-url", default="https://kosis.kr/openapi")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    api_key = os.environ.get("KOSIS_API_KEY")
    if not api_key:
        print("KOSIS_API_KEY is required", file=sys.stderr)
        return 2

    params: dict[str, str] = {"apiKey": api_key}
    for item in args.param:
        if "=" not in item:
            print(f"Invalid --param {item!r}; expected key=value", file=sys.stderr)
            return 2
        key, value = item.split("=", 1)
        params[key] = value

    url = f"{args.base_url.rstrip('/')}/{args.endpoint.lstrip('/')}"
    response = requests.get(url, params=params, timeout=args.timeout)
    response.raise_for_status()
    data = parse_response(response.text)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
