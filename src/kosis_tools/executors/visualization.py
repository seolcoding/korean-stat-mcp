"""
시각화 코드 실행 엔진.

차트/그래프 생성에 특화된 실행 환경과 가이드라인을 제공합니다.

가이드라인:
    - 숫자 단위: 천 명/천 원/천 개 (1,000 기준)
    - Y축 포맷: format=",.0f" 사용, 과학적 표기법 금지
    - 축 제목: 반드시 단위 명시 (예: "인구 (천 명)")
    - 시리즈: 5개 이하 권장
    - 색상: 색맹 친화적 팔레트 사용
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import altair as alt
import numpy as np

from .base import get_base_globals, execute_with_context

logger = logging.getLogger(__name__)

# 시각화 가이드라인 (LLM에게 전달)
VISUALIZATION_GUIDE = """
## 시각화 가이드라인

### 1. 숫자 단위 규칙 (필수)
- 기본 단위: **천 (1,000)** 기준
  - 인구: 천 명 (예: 51,325천 명 = 5,132만 명)
  - 금액: 천 원, 백만 원, 억 원
  - 수량: 천 개, 만 개
- **과학적 표기법(1e+7) 절대 금지**
- 데이터 변환: `df["값_천단위"] = df["DT"] / 1000`

### 2. 축 포맷팅 (필수)
```python
# Y축 설정 예시
y=alt.Y("값_천단위:Q",
    title="인구 (천 명)",           # 단위 반드시 명시
    axis=alt.Axis(format=",.0f"))  # 천 단위 구분자
```

### 3. 차트 유형별 권장사항
| 유형 | 최대 시리즈 | 용도 |
|------|------------|------|
| 라인 | 5개 | 시계열 추이 |
| 막대 | 10개 | 비교 |
| 파이/도넛 | 5개 | 구성비 (비권장) |

### 4. 필수 속성
```python
chart.properties(
    title="명확한 차트 제목",
    width=600,
    height=350
)
```

### 5. 색상
- 기본: Altair 기본 팔레트 사용
- 강조: `color=alt.value("#2563eb")` (단일 시리즈)

### 6. 반환 형식
반드시 `save_chart(chart, "파일명.html")` 호출하여 URL 반환
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


def save_chart(
    chart: alt.Chart,
    filename: str,
) -> Dict[str, Any]:
    """
    차트를 로컬 아티팩트 디렉토리에 저장하고 URL을 반환.

    Args:
        chart: Altair Chart 객체
        filename: 파일명 (확장자 포함)

    Returns:
        {"url": ..., "path": ..., "type": "chart"}
    """
    import os
    from pathlib import Path

    suffix = Path(filename).suffix.lower()
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
    # 시각화 전용 글로벌 환경
    safe_globals = get_base_globals()
    safe_globals.update(
        {
            # 데이터 분석 라이브러리
            "pd": pd,
            "alt": alt,
            "np": np,
            # 시각화 헬퍼
            "prepare_data": prepare_data,
            "save_chart": save_chart,
            # 단위 변환 헬퍼
            "to_thousand": lambda v: v / 1000,
            "to_man": lambda v: v / 10000,
            "to_billion": lambda v: v / 100000000,
            # 데이터
            "data": data or [],
        }
    )

    result = execute_with_context(code, safe_globals, context)
    result["guide"] = VISUALIZATION_GUIDE

    # 결과 검증: URL이 반환되었는지 확인
    if result["success"]:
        res = result.get("result")
        if not isinstance(res, dict) or "url" not in res:
            result["warning"] = "save_chart()를 호출하여 URL을 반환해야 합니다."

    return result
