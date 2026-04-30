"""
KOSIS 시각화 유틸리티.

Code Execution 패턴용 헬퍼 함수들.
LLM이 작성한 코드에서 import하여 사용.

Example (LLM이 작성하는 코드):
    ```python
    import altair as alt
    from kosis_tools.visualize import prepare_data, save_chart

    df = prepare_data(data, numeric_fields=["DT"])

    chart = alt.Chart(df).mark_line(point=True).encode(
        x='PRD_DE:N',
        y='DT:Q',
        color='C1_NM:N'
    ).properties(title="인구 추이")

    result = save_chart(chart, "population_trend.html")
    ```
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import altair as alt
import pandas as pd

logger = logging.getLogger(__name__)

# Altair 설정
alt.data_transformers.disable_max_rows()


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
    chart: alt.Chart,
    filename: str,
    output_dir: str | None = None,
    scale: float = 2.0,
) -> Dict[str, Any]:
    """
    차트를 파일로 저장하고 URL을 반환.

    R2가 설정되어 있으면 R2에 업로드, 아니면 로컬에 저장.

    Args:
        chart: Altair Chart 객체
        filename: 파일명 (확장자로 형식 결정: .html, .png, .svg)
        output_dir: 저장 디렉토리 (기본: artifacts 디렉토리 사용)
        scale: PNG 해상도 배율

    Returns:
        {"url": 접근 URL, "path": 저장 경로, "format": 형식, "type": "chart"}
    """
    import os
    import tempfile

    suffix = Path(filename).suffix.lower()

    # 임시 파일에 먼저 저장
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name

    if suffix == ".png":
        chart.save(tmp_path, scale_factor=scale)
    else:
        chart.save(tmp_path)

    # R2 또는 로컬 스토리지에 업로드
    try:
        from kosis_tools.r2_storage import get_storage, generate_artifact_key

        storage = get_storage()
        key = generate_artifact_key("charts", filename)
        url = storage.upload_file(tmp_path, key)

        return {
            "url": url,
            "path": key,
            "local_path": tmp_path,
            "format": suffix.lstrip("."),
            "type": "chart",
        }
    except Exception as e:
        # R2 실패 시 로컬 폴백
        logger.warning(f"R2 upload failed, using local: {e}")
        artifacts_dir = os.environ.get("KOSIS_ARTIFACTS_DIR", "/tmp/kosis_artifacts")
        base_url = os.environ.get("KOSIS_BASE_URL", "http://localhost:8000")

        output_path = Path(artifacts_dir) / "charts"
        output_path.mkdir(parents=True, exist_ok=True)

        import shutil

        final_path = output_path / filename
        shutil.move(tmp_path, final_path)

        return {
            "url": f"{base_url}/artifacts/charts/{filename}",
            "path": str(final_path.absolute()),
            "local_path": str(final_path.absolute()),
            "format": suffix.lstrip("."),
            "type": "chart",
        }


def chart_to_json(chart: alt.Chart) -> str:
    """차트를 Vega-Lite JSON으로 변환."""
    return chart.to_json()


def chart_to_html(chart: alt.Chart, title: str = "Chart") -> str:
    """차트를 standalone HTML로 변환."""
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
