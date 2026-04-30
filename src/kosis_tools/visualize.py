"""KOSIS data preparation helpers.

Native chart generation is intentionally not part of the base MCP package.
Agents should render visualizations in the client/tooling layer after fetching
structured KOSIS data.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)


def prepare_data(
    data: List[Dict[str, Any]],
    numeric_fields: List[str] | None = None,
) -> pd.DataFrame:
    """
    KOSIS 데이터를 DataFrame으로 변환.

    Args:
        data: KOSIS API 응답 데이터
        numeric_fields: 숫자로 변환할 필드 (기본: ["DT"])

    Returns:
        pandas DataFrame
    """
    df = pd.DataFrame(data)

    if numeric_fields is None:
        numeric_fields = ["DT"]

    for field in numeric_fields:
        if field in df.columns:
            df[field] = pd.to_numeric(
                df[field]
                .astype(str)
                .str.replace(",", "")
                .replace(["-", "", "*"], None),
                errors="coerce",
            )

    return df


def save_chart(
    chart: Any,
    filename: str,
    output_dir: str | None = None,
    scale: float = 2.0,
) -> Dict[str, Any]:
    """
    외부에서 만든 chart 객체를 로컬 아티팩트 디렉토리에 저장하고 URL을 반환.

    Args:
        chart: ``save(path)`` 메서드를 제공하는 외부 chart 객체
        filename: 파일명 (.html)
        output_dir: 저장 디렉토리 (기본: artifacts 디렉토리 사용)
        scale: PNG 해상도 배율

    Returns:
        {"url": 접근 URL, "path": 저장 경로, "format": 형식, "type": "chart"}
    """
    import os

    suffix = Path(filename).suffix.lower()
    if suffix != ".html":
        raise ValueError(
            "Only .html chart artifacts are supported in the base package."
        )
    if not hasattr(chart, "save"):
        raise TypeError("chart must provide a save(path) method")

    artifacts_dir = os.environ.get("KOSIS_ARTIFACTS_DIR", "/tmp/kosis_artifacts")
    base_url = os.environ.get("KOSIS_BASE_URL", "http://localhost:8000")

    output_path = Path(output_dir) if output_dir else Path(artifacts_dir) / "charts"
    output_path.mkdir(parents=True, exist_ok=True)

    final_path = output_path / filename
    chart.save(final_path)

    return {
        "url": f"{base_url}/artifacts/charts/{filename}",
        "path": str(final_path.absolute()),
        "local_path": str(final_path.absolute()),
        "format": suffix.lstrip("."),
        "type": "chart",
    }


def chart_to_json(chart: Any) -> str:
    """외부 chart 객체를 JSON으로 변환."""
    if not hasattr(chart, "to_json"):
        raise TypeError("chart must provide a to_json() method")
    return chart.to_json()


def chart_to_html(chart: Any, title: str = "Chart") -> str:
    """외부 chart 객체를 standalone HTML로 변환."""
    spec = chart.to_json()
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
</head>
<body>
    <div id="chart"></div>
    <script>
        vegaEmbed('#chart', {spec}, {{"renderer": "svg"}}).catch(console.error);
    </script>
</body>
</html>"""
