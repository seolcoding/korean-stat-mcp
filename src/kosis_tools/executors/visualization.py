"""Visualization executor placeholder.

Native chart generation is intentionally excluded from the base MCP package.
The server returns structured data; agents should render charts in the client
or a dedicated visualization tool.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

# 시각화 가이드라인 (LLM에게 전달)
VISUALIZATION_GUIDE = """
## 시각화 안내

이 패키지는 기본 MCP 서버에 네이티브 차트 생성을 포함하지 않습니다.
`get_statistics_data`, `read_stored_data`, `execute_table`, `execute_analysis`로
구조화 데이터를 받은 뒤 클라이언트/노트북/문서 도구에서 시각화하세요.
"""

# 단위 변환 헬퍼
UNIT_HELPERS = """
# 단위 변환 헬퍼 함수들
def to_thousand(value):
    '''천 단위로 변환'''
    return value / 1000

def to_man(value):
    '''만 단위로 변환'''
    return value / 10000

def to_billion(value):
    '''억 단위로 변환'''
    return value / 100000000

def format_korean(value, unit=""):
    '''한국어 숫자 포맷 (천 단위 구분자)'''
    return f"{value:,.0f}{unit}"
"""


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


def save_chart(chart: Any, filename: str) -> Dict[str, Any]:
    """
    차트를 로컬 아티팩트 디렉토리에 저장하고 URL을 반환.

    Args:
        chart: ``save(path)`` 메서드를 제공하는 외부 chart 객체
        filename: 파일명 (확장자 포함)

    Returns:
        {"url": ..., "path": ..., "type": "chart"}
    """
    import os
    from pathlib import Path

    suffix = Path(filename).suffix.lower()
    if suffix != ".html":
        raise ValueError(
            "Only .html chart artifacts are supported in the base package."
        )
    if not hasattr(chart, "save"):
        raise TypeError("chart must provide a save(path) method")

    artifacts_dir = os.environ.get("KOSIS_ARTIFACTS_DIR", "/tmp/kosis_artifacts")
    base_url = os.environ.get("KOSIS_BASE_URL", "http://localhost:8000")

    output_path = Path(artifacts_dir) / "charts"
    output_path.mkdir(parents=True, exist_ok=True)

    final_path = output_path / filename
    chart.save(final_path)

    return {
        "url": f"{base_url}/artifacts/charts/{filename}",
        "path": str(final_path.absolute()),
        "type": "chart",
        "format": suffix.lstrip("."),
    }


def execute_visualization(
    code: str,
    data: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    시각화 코드를 실행합니다.

    Args:
        code: 실행할 Python 코드 (차트 생성)
        data: KOSIS 데이터
        context: 추가 컨텍스트

    Returns:
        {
            "success": bool,
            "result": {"url": ..., "path": ..., "type": "chart"},
            "stdout": str,
            "error": str | None,
            "guide": str,  # 시각화 가이드라인
        }

    Example:
        >>> result = execute_visualization('''
        ...     df = prepare_data(data, numeric_fields=["DT"])
        ...     df["인구_천명"] = df["DT"] / 1000
        ...
        ...     chart = alt.Chart(df).mark_line(point=True).encode(
        ...         x=alt.X("PRD_DE:N", title="연도"),
        ...         y=alt.Y("인구_천명:Q", title="인구 (천 명)", axis=alt.Axis(format=",.0f")),
        ...         color="C1_NM:N"
        ...     ).properties(title="인구 추이", width=600, height=350)
        ...
        ...     return save_chart(chart, "population.html")
        ... ''', data=kosis_data)
    """
    return {
        "success": False,
        "result": None,
        "stdout": "",
        "error": "Native visualization is not included in korean-stat-mcp.",
        "guide": VISUALIZATION_GUIDE,
        "suggestion": (
            "Fetch structured data with get_statistics_data/read_stored_data and "
            "render charts in the client or a dedicated visualization tool."
        ),
    }
