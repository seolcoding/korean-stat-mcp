"""
데이터 분석 코드 실행 엔진.

통계 분석, 데이터 변환에 특화된 실행 환경과 가이드라인을 제공합니다.

가이드라인:
    - KOSIS 결측치 처리: "-", "*", "" 등
    - 증감률, 구성비, 평균 등 기본 통계 계산
    - 결과는 딕셔너리로 반환 (리포트에서 사용)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from .base import get_base_globals, execute_with_context

logger = logging.getLogger(__name__)

# 분석 가이드라인 (LLM에게 전달)
ANALYSIS_GUIDE = """
## 데이터 분석 가이드라인

### 1. KOSIS 데이터 특성
- `DT` 필드는 **문자열**입니다
- 결측치 표현: `"-"`, `"*"`, `"…"`, `""`
- 숫자 변환 필수: `pd.to_numeric(..., errors="coerce")`

### 2. 결측치 처리 (필수)
```python
df = prepare_data(data, numeric_fields=["DT"])
# 자동으로 "-", "*" 등을 NaN으로 변환
```

### 3. 기본 통계 계산
```python
# 증감률
change_rate = (current - previous) / previous * 100

# 구성비
ratio = value / total * 100

# 연평균 성장률 (CAGR)
cagr = ((end_value / start_value) ** (1 / years) - 1) * 100
```

### 4. 반환 형식 (필수)
딕셔너리로 반환하여 리포트에서 사용:
```python
return {
    "summary": {
        "total": 51325,           # 천 단위
        "change": -383,           # 증감
        "change_rate": -0.74,     # %
    },
    "by_region": {
        "서울": {"value": 9386, "ratio": 18.3},
        "경기": {"value": 13617, "ratio": 26.5},
    },
    "insights": [
        "전국 인구 5년간 0.74% 감소",
        "수도권 인구 비율 50.5%",
    ]
}
```

### 5. 숫자 포맷팅
- 기본 단위: 천 (1,000)
- 퍼센트: 소수점 1자리
- 큰 숫자: 천 단위 구분자
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
                df[field].astype(str).str.replace(",", "").replace(["-", "", "*", "…"], None),
                errors="coerce"
            )

    return df


def calc_change_rate(current: float, previous: float) -> float:
    """증감률 계산 (%)."""
    if previous == 0:
        return 0.0
    return (current - previous) / previous * 100


def calc_cagr(start_value: float, end_value: float, years: int) -> float:
    """연평균 성장률 계산 (%)."""
    if start_value <= 0 or years <= 0:
        return 0.0
    return ((end_value / start_value) ** (1 / years) - 1) * 100


def calc_ratio(value: float, total: float) -> float:
    """구성비 계산 (%)."""
    if total == 0:
        return 0.0
    return value / total * 100


def to_thousand(value: float) -> float:
    """천 단위로 변환."""
    return value / 1000


def format_stat(value: float, unit: str = "", decimals: int = 1) -> str:
    """통계 값 포맷팅."""
    if decimals == 0:
        return f"{value:,.0f}{unit}"
    return f"{value:,.{decimals}f}{unit}"


def execute_analysis(
    code: str,
    data: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    분석 코드를 실행합니다.

    Args:
        code: 실행할 Python 코드 (분석/통계)
        data: KOSIS 데이터
        context: 추가 컨텍스트

    Returns:
        {
            "success": bool,
            "result": dict,  # 분석 결과 딕셔너리
            "stdout": str,
            "error": str | None,
            "guide": str,  # 분석 가이드라인
        }

    Example:
        >>> result = execute_analysis('''
        ...     df = prepare_data(data, numeric_fields=["DT"])
        ...
        ...     total_2023 = df[df["PRD_DE"] == "2023"]["DT"].sum()
        ...     total_2019 = df[df["PRD_DE"] == "2019"]["DT"].sum()
        ...
        ...     return {
        ...         "summary": {
        ...             "total_2023": to_thousand(total_2023),
        ...             "change_rate": calc_change_rate(total_2023, total_2019),
        ...         },
        ...         "insights": ["인구 감소 추세 지속"]
        ...     }
        ... ''', data=kosis_data)
    """
    # 분석 전용 글로벌 환경
    safe_globals = get_base_globals()
    safe_globals.update({
        # 데이터 분석 라이브러리
        "pd": pd,
        "np": np,
        # 분석 헬퍼
        "prepare_data": prepare_data,
        "calc_change_rate": calc_change_rate,
        "calc_cagr": calc_cagr,
        "calc_ratio": calc_ratio,
        "to_thousand": to_thousand,
        "format_stat": format_stat,
        # 데이터
        "data": data or [],
    })

    result = execute_with_context(code, safe_globals, context)
    result["guide"] = ANALYSIS_GUIDE

    # 결과 검증: 딕셔너리가 반환되었는지 확인
    if result["success"]:
        res = result.get("result")
        if not isinstance(res, dict):
            result["warning"] = "분석 결과는 딕셔너리로 반환해야 합니다."

    return result
