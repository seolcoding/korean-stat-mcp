"""
테이블 생성 코드 실행 엔진.

예쁜 HTML 테이블 생성에 특화된 실행 환경과 가이드라인을 제공합니다.

가이드라인:
    - 숫자 포맷: 천 단위 구분자 필수
    - 컬럼명: 한글로 명확하게
    - 정렬: 숫자는 우측, 텍스트는 좌측
    - 최대 행 수 제한 (기본 20행)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from .base import get_base_globals, execute_with_context

logger = logging.getLogger(__name__)

# 테이블 가이드라인 (LLM에게 전달)
TABLE_GUIDE = """
## 테이블 생성 가이드라인

### 1. 숫자 포맷팅 (필수)
- 천 단위 구분자: `12,345`
- 퍼센트: `12.3%`
- 소수점: 필요한 만큼만 (보통 1자리)

### 2. 컬럼명 규칙
- 한글로 명확하게: `PRD_DE` → `연도`
- 단위 명시: `인구` → `인구 (천 명)`

### 3. 테이블 스타일
```python
table = create_table(
    df,
    title="지역별 인구 현황",
    columns={
        "C1_NM": "지역",
        "DT": "인구 (천 명)",
    },
    number_format={
        "인구 (천 명)": ",.0f",
    },
    max_rows=20,
)
```

### 4. 정렬
- 숫자: 우측 정렬
- 텍스트: 좌측 정렬
- 자동 적용됨

### 5. 반환 형식
```python
return create_table(df, ...)
# 반환: {"html": "<table>...</table>", "type": "table"}
```
"""

# 테이블 CSS 스타일
TABLE_STYLES = """
<style>
.styled-table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    font-size: 14px;
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    border-radius: 8px;
    overflow: hidden;
}

.styled-table thead tr {
    background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
    color: #ffffff;
    text-align: left;
    font-weight: 600;
}

.styled-table th,
.styled-table td {
    padding: 12px 16px;
    border-bottom: 1px solid #e0e0e0;
}

.styled-table tbody tr {
    background-color: #ffffff;
    transition: background-color 0.2s;
}

.styled-table tbody tr:nth-of-type(even) {
    background-color: #f8f9fa;
}

.styled-table tbody tr:hover {
    background-color: #e8f4fd;
}

.styled-table tbody tr:last-of-type {
    border-bottom: 2px solid #2c3e50;
}

.styled-table .number {
    text-align: right;
    font-variant-numeric: tabular-nums;
}

.styled-table .text {
    text-align: left;
}

.styled-table .highlight {
    background-color: #fff3cd;
    font-weight: 600;
}

.styled-table .positive {
    color: #28a745;
}

.styled-table .negative {
    color: #dc3545;
}

.table-title {
    font-size: 16px;
    font-weight: 600;
    color: #2c3e50;
    margin-bottom: 12px;
}

.table-footer {
    font-size: 12px;
    color: #6c757d;
    margin-top: 8px;
    text-align: right;
}
</style>
"""


def prepare_data(
    data: List[Dict[str, Any]],
    numeric_fields: List[str] | None = None,
) -> pd.DataFrame:
    """KOSIS 데이터를 DataFrame으로 변환."""
    df = pd.DataFrame(data)

    if numeric_fields is None:
        numeric_fields = ["DT"]

    for field in numeric_fields:
        if field in df.columns:
            df[field] = pd.to_numeric(
                df[field].astype(str).str.replace(",", "").replace(["-", "", "*", "…"], None),
                errors="coerce"
            )

    return df


def format_number(value: Any, fmt: str = ",.0f") -> str:
    """숫자 포맷팅."""
    if pd.isna(value):
        return "-"
    try:
        return f"{float(value):{fmt}}"
    except (ValueError, TypeError):
        return str(value)


def create_table(
    df: pd.DataFrame,
    title: str = "",
    columns: Optional[Dict[str, str]] = None,
    number_format: Optional[Dict[str, str]] = None,
    max_rows: int = 20,
    highlight_column: Optional[str] = None,
    show_index: bool = False,
) -> Dict[str, Any]:
    """
    스타일링된 HTML 테이블을 생성합니다.

    Args:
        df: 데이터프레임
        title: 테이블 제목
        columns: 컬럼명 매핑 (원본 → 표시명)
        number_format: 숫자 포맷 (컬럼명 → 포맷 문자열)
        max_rows: 최대 표시 행 수
        highlight_column: 강조할 컬럼명
        show_index: 인덱스 표시 여부

    Returns:
        {"html": str, "type": "table", "rows": int}
    """
    # 컬럼명 변경
    display_df = df.copy()
    if columns:
        display_df = display_df.rename(columns=columns)

    # 행 수 제한
    total_rows = len(display_df)
    if total_rows > max_rows:
        display_df = display_df.head(max_rows)

    # 숫자 포맷팅
    if number_format:
        for col, fmt in number_format.items():
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(lambda x: format_number(x, fmt))

    # HTML 생성
    html_parts = [TABLE_STYLES]

    if title:
        html_parts.append(f'<div class="table-title">{title}</div>')

    html_parts.append('<table class="styled-table">')

    # 헤더
    html_parts.append('<thead><tr>')
    if show_index:
        html_parts.append('<th>#</th>')
    for col in display_df.columns:
        html_parts.append(f'<th>{col}</th>')
    html_parts.append('</tr></thead>')

    # 바디
    html_parts.append('<tbody>')
    for idx, row in display_df.iterrows():
        html_parts.append('<tr>')
        if show_index:
            html_parts.append(f'<td class="number">{idx + 1}</td>')
        for col in display_df.columns:
            value = row[col]
            # 숫자 여부 판단 (포맷팅된 숫자도 포함)
            is_number = False
            try:
                # 콤마 제거 후 숫자 변환 시도
                clean_val = str(value).replace(",", "").replace("%", "")
                float(clean_val)
                is_number = True
            except (ValueError, TypeError):
                pass

            cell_class = "number" if is_number else "text"

            # 하이라이트
            if highlight_column and col == highlight_column:
                cell_class += " highlight"

            # 양수/음수 색상
            if is_number and str(value).startswith("-"):
                cell_class += " negative"
            elif is_number and str(value).startswith("+"):
                cell_class += " positive"

            html_parts.append(f'<td class="{cell_class}">{value}</td>')
        html_parts.append('</tr>')
    html_parts.append('</tbody>')

    html_parts.append('</table>')

    # 푸터 (더 많은 행이 있는 경우)
    if total_rows > max_rows:
        html_parts.append(f'<div class="table-footer">전체 {total_rows:,}건 중 {max_rows}건 표시</div>')

    return {
        "html": "\n".join(html_parts),
        "type": "table",
        "rows": total_rows,
        "displayed_rows": min(total_rows, max_rows),
    }


def create_summary_table(
    data: Dict[str, Any],
    title: str = "요약",
) -> Dict[str, Any]:
    """
    키-값 형태의 요약 테이블을 생성합니다.

    Args:
        data: {"항목명": "값", ...} 형태의 딕셔너리
        title: 테이블 제목

    Returns:
        {"html": str, "type": "table"}
    """
    html_parts = [TABLE_STYLES]

    if title:
        html_parts.append(f'<div class="table-title">{title}</div>')

    html_parts.append('<table class="styled-table">')
    html_parts.append('<thead><tr><th>항목</th><th>값</th></tr></thead>')
    html_parts.append('<tbody>')

    for key, value in data.items():
        html_parts.append(f'<tr><td class="text">{key}</td><td class="number">{value}</td></tr>')

    html_parts.append('</tbody></table>')

    return {
        "html": "\n".join(html_parts),
        "type": "table",
        "rows": len(data),
    }


def execute_table(
    code: str,
    data: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    테이블 생성 코드를 실행합니다.

    Args:
        code: 실행할 Python 코드 (테이블 생성)
        data: KOSIS 데이터
        context: 추가 컨텍스트

    Returns:
        {
            "success": bool,
            "result": {"html": str, "type": "table"},
            "stdout": str,
            "error": str | None,
            "guide": str,
        }

    Example:
        >>> result = execute_table('''
        ...     df = prepare_data(data, numeric_fields=["DT"])
        ...     df["인구_천명"] = df["DT"] / 1000
        ...
        ...     return create_table(
        ...         df[["PRD_DE", "C1_NM", "인구_천명"]],
        ...         title="연도별 지역별 인구",
        ...         columns={"PRD_DE": "연도", "C1_NM": "지역", "인구_천명": "인구 (천 명)"},
        ...         number_format={"인구 (천 명)": ",.0f"},
        ...         max_rows=20,
        ...     )
        ... ''', data=kosis_data)
    """
    # 테이블 전용 글로벌 환경
    safe_globals = get_base_globals()
    safe_globals.update({
        # 데이터 분석 라이브러리
        "pd": pd,
        "np": np,
        # 테이블 헬퍼
        "prepare_data": prepare_data,
        "create_table": create_table,
        "create_summary_table": create_summary_table,
        "format_number": format_number,
        # 데이터
        "data": data or [],
    })

    result = execute_with_context(code, safe_globals, context)
    result["guide"] = TABLE_GUIDE

    # 결과 검증
    if result["success"]:
        res = result.get("result")
        if not isinstance(res, dict) or "html" not in res:
            result["warning"] = "create_table() 또는 create_summary_table()을 호출해야 합니다."

    return result
