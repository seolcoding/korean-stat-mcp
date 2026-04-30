"""
리포트 생성 코드 실행 엔진.

시각화, 분석, 테이블을 조합하여 완성된 리포트를 생성합니다.

가이드라인:
    - 구조: 요약 → 차트 → 인사이트 → 상세 데이터
    - 숫자: 천 단위 구분자, 한글 단위
    - 출처: KOSIS 명시
"""

from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np
import altair as alt

from .base import get_base_globals, execute_with_context

logger = logging.getLogger(__name__)

# 리포트 가이드라인 (LLM에게 전달)
REPORT_GUIDE = """
## 리포트 생성 가이드라인

### 1. 리포트 구조 (권장 순서)
1. **제목 + 요약 통계** (stat_cards)
2. **주요 차트** (1-3개)
3. **핵심 인사이트** (3-5개 포인트)
4. **상세 데이터 테이블**
5. **출처 및 주석**

### 2. 입력 데이터 형식
```python
# 분석 결과 (execute_analysis에서)
analysis = {
    "summary": {"total": 51325, "change_rate": -0.74},
    "insights": ["인구 감소 추세", "수도권 집중 심화"]
}

# 차트 URL 목록 (execute_visualization에서)
charts = [
    {"url": "http://.../chart1.html", "title": "인구 추이"},
    {"url": "http://.../chart2.html", "title": "지역별 비교"},
]

# 테이블 HTML (execute_table에서)
tables = [
    {"html": "<table>...</table>", "title": "상세 데이터"},
]
```

### 3. 리포트 생성
```python
return build_report(
    title="대한민국 인구 분석 리포트",
    analysis=analysis,
    charts=charts,
    tables=tables,
    source="통계청 KOSIS",
)
```

### 4. 숫자 표기 규칙
- 기본 단위: 천 (1,000)
- 천 단위 구분자 필수: `51,325천 명`
- 퍼센트: 소수점 1자리: `18.3%`
- 증감: 부호 표시: `+2.5%`, `-0.7%`

### 5. 반환 형식
```python
{"url": "http://.../report.html", "type": "report"}
```
"""


# 리포트 HTML 템플릿
REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
    <style>
        * {{ box-sizing: border-box; }}

        body {{
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont,
                         'Segoe UI', Roboto, 'Helvetica Neue', Arial,
                         'Noto Sans KR', sans-serif;
            line-height: 1.7;
            color: #333;
            max-width: 1000px;
            margin: 0 auto;
            padding: 40px 20px;
            background: #fff;
        }}

        /* 헤더 */
        .report-header {{
            text-align: center;
            border-bottom: 3px solid #2c3e50;
            padding-bottom: 24px;
            margin-bottom: 40px;
        }}

        .report-header h1 {{
            color: #2c3e50;
            margin: 0 0 12px 0;
            font-size: 2.2rem;
            font-weight: 700;
        }}

        .report-meta {{
            color: #6c757d;
            font-size: 0.9rem;
        }}

        /* 통계 카드 */
        .stat-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 24px;
            border-radius: 12px;
            text-align: center;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }}

        .stat-card .label {{
            font-size: 0.85rem;
            opacity: 0.9;
            margin-bottom: 8px;
        }}

        .stat-card .value {{
            font-size: 1.8rem;
            font-weight: 700;
        }}

        /* 섹션 */
        .section {{
            margin-bottom: 48px;
        }}

        .section-title {{
            color: #2c3e50;
            font-size: 1.4rem;
            font-weight: 600;
            border-left: 4px solid #667eea;
            padding-left: 16px;
            margin-bottom: 24px;
        }}

        /* 차트 */
        .chart-container {{
            background: #fafafa;
            border: 1px solid #e9ecef;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
        }}

        .chart-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: #495057;
            margin-bottom: 16px;
            text-align: center;
        }}

        .chart-embed {{
            display: flex;
            justify-content: center;
        }}

        /* 인사이트 */
        .insight-box {{
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-left: 4px solid #28a745;
            padding: 24px;
            border-radius: 0 12px 12px 0;
            margin-bottom: 24px;
        }}

        .insight-box h3 {{
            color: #28a745;
            margin: 0 0 16px 0;
            font-size: 1.1rem;
        }}

        .insight-box ul {{
            margin: 0;
            padding-left: 20px;
        }}

        .insight-box li {{
            margin-bottom: 8px;
            color: #495057;
        }}

        /* 테이블 */
        .table-section {{
            overflow-x: auto;
        }}

        /* 푸터 */
        .report-footer {{
            margin-top: 48px;
            padding-top: 24px;
            border-top: 1px solid #dee2e6;
            text-align: center;
            color: #6c757d;
            font-size: 0.85rem;
        }}

        .report-footer .source {{
            margin-bottom: 8px;
        }}

        @media print {{
            body {{ padding: 20px; }}
            .chart-container {{ break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <header class="report-header">
        <h1>{title}</h1>
        <div class="report-meta">생성일: {date}</div>
    </header>

    {stat_cards_html}

    {charts_html}

    {insights_html}

    {tables_html}

    <footer class="report-footer">
        <div class="source">출처: {source}</div>
        <div>Generated by KOSIS MCP Server</div>
    </footer>

    {vega_scripts}
</body>
</html>
"""


def build_stat_cards(stats: List[Dict[str, str]]) -> str:
    """통계 카드 HTML 생성."""
    if not stats:
        return ""

    cards_html = '<div class="stat-cards">'
    for stat in stats:
        cards_html += f"""
        <div class="stat-card">
            <div class="label">{stat.get("label", "")}</div>
            <div class="value">{stat.get("value", "")}</div>
        </div>
        """
    cards_html += "</div>"
    return cards_html


def build_charts_section(charts: List[Dict[str, Any]]) -> tuple[str, str]:
    """
    차트 섹션 HTML과 Vega 스크립트를 생성합니다.

    Args:
        charts: [{"vega_spec": dict, "title": str}, ...]
               또는 [{"url": str, "title": str}, ...]

    Returns:
        (charts_html, vega_scripts)
    """
    if not charts:
        return "", ""

    charts_html = '<section class="section"><h2 class="section-title">분석 차트</h2>'
    vega_scripts = []

    for i, chart in enumerate(charts):
        chart_id = f"chart_{i}"
        title = chart.get("title", f"차트 {i + 1}")

        charts_html += f'''
        <div class="chart-container">
            <div class="chart-title">{title}</div>
            <div class="chart-embed" id="{chart_id}"></div>
        </div>
        '''

        # Vega spec이 있으면 직접 embed
        if "vega_spec" in chart:
            import json

            spec_json = json.dumps(chart["vega_spec"])
            vega_scripts.append(f"""
            vegaEmbed('#{chart_id}', {spec_json}, {{"renderer": "svg"}}).catch(console.error);
            """)
        # URL이 있으면 iframe으로 embed
        elif "url" in chart:
            charts_html = charts_html.replace(
                f'<div class="chart-embed" id="{chart_id}"></div>',
                f'<iframe src="{chart["url"]}" width="100%" height="400" frameborder="0"></iframe>',
            )

    charts_html += "</section>"

    scripts_html = ""
    if vega_scripts:
        scripts_html = f"<script>\n{''.join(vega_scripts)}\n</script>"

    return charts_html, scripts_html


def build_insights_section(insights: List[str], title: str = "핵심 인사이트") -> str:
    """인사이트 섹션 HTML 생성."""
    if not insights:
        return ""

    items = "\n".join(f"<li>{insight}</li>" for insight in insights)
    return f"""
    <section class="section">
        <div class="insight-box">
            <h3>{title}</h3>
            <ul>{items}</ul>
        </div>
    </section>
    """


def build_tables_section(tables: List[Dict[str, Any]]) -> str:
    """테이블 섹션 HTML 생성."""
    if not tables:
        return ""

    html = '<section class="section"><h2 class="section-title">상세 데이터</h2>'
    for table in tables:
        title = table.get("title", "")
        if title:
            html += f"<h3>{title}</h3>"
        html += f'<div class="table-section">{table.get("html", "")}</div>'
    html += "</section>"
    return html


def build_report(
    title: str,
    analysis: Optional[Dict[str, Any]] = None,
    charts: Optional[List[Dict[str, Any]]] = None,
    tables: Optional[List[Dict[str, Any]]] = None,
    source: str = "통계청 KOSIS",
) -> Dict[str, Any]:
    """
    완성된 HTML 리포트를 생성하고 저장합니다.

    Args:
        title: 리포트 제목
        analysis: 분석 결과 (execute_analysis 출력)
            - summary: {"label": value, ...} 또는 [{"label": ..., "value": ...}, ...]
            - insights: ["인사이트1", "인사이트2", ...]
        charts: 차트 목록 (execute_visualization 출력들)
            - [{"vega_spec": dict, "title": str}, ...]
        tables: 테이블 목록 (execute_table 출력들)
            - [{"html": str, "title": str}, ...]
        source: 데이터 출처

    Returns:
        {"url": str, "path": str, "type": "report"}
    """
    # 통계 카드 준비
    stats = []
    if analysis:
        summary = analysis.get("summary", {})
        if isinstance(summary, dict):
            # {"label": value} 형식을 [{"label": ..., "value": ...}] 로 변환
            stats = [{"label": k, "value": str(v)} for k, v in summary.items()]
        elif isinstance(summary, list):
            stats = summary

    # 인사이트 준비
    insights = []
    if analysis:
        insights = analysis.get("insights", [])

    # HTML 생성
    stat_cards_html = build_stat_cards(stats)
    charts_html, vega_scripts = build_charts_section(charts or [])
    insights_html = build_insights_section(insights)
    tables_html = build_tables_section(tables or [])

    html = REPORT_TEMPLATE.format(
        title=title,
        date=datetime.now().strftime("%Y년 %m월 %d일"),
        stat_cards_html=stat_cards_html,
        charts_html=charts_html,
        insights_html=insights_html,
        tables_html=tables_html,
        source=source,
        vega_scripts=vega_scripts,
    )

    # 파일 저장
    artifacts_dir = os.environ.get("KOSIS_ARTIFACTS_DIR", "/tmp/kosis_artifacts")
    base_url = os.environ.get("KOSIS_BASE_URL", "http://localhost:8000")

    output_path = Path(artifacts_dir) / "reports"
    output_path.mkdir(parents=True, exist_ok=True)

    # 파일명 생성
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_uuid = uuid.uuid4().hex[:8]
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:30]
    filename = f"{safe_title}_{timestamp}_{short_uuid}.html"

    filepath = output_path / filename
    filepath.write_text(html, encoding="utf-8")

    url = f"{base_url}/artifacts/reports/{filename}"

    logger.info(f"Report saved: {filepath} -> {url}")

    return {
        "url": url,
        "path": str(filepath.absolute()),
        "type": "report",
        "title": title,
    }


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
                df[field]
                .astype(str)
                .str.replace(",", "")
                .replace(["-", "", "*", "…"], None),
                errors="coerce",
            )

    return df


def execute_report(
    code: str,
    data: Optional[List[Dict[str, Any]]] = None,
    analysis: Optional[Dict[str, Any]] = None,
    charts: Optional[List[Dict[str, Any]]] = None,
    tables: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    리포트 생성 코드를 실행합니다.

    Args:
        code: 실행할 Python 코드 (리포트 생성)
        data: KOSIS 원본 데이터 (필요시)
        analysis: 분석 결과 (execute_analysis에서)
        charts: 차트 목록 (execute_visualization에서)
        tables: 테이블 목록 (execute_table에서)
        context: 추가 컨텍스트

    Returns:
        {
            "success": bool,
            "result": {"url": str, "type": "report"},
            "stdout": str,
            "error": str | None,
            "guide": str,
        }

    Example:
        >>> result = execute_report('''
        ...     return build_report(
        ...         title="인구 분석 리포트",
        ...         analysis=analysis,
        ...         charts=charts,
        ...         tables=tables,
        ...     )
        ... ''',
        ... analysis={"summary": {...}, "insights": [...]},
        ... charts=[{"vega_spec": {...}, "title": "인구 추이"}],
        ... tables=[{"html": "...", "title": "상세 데이터"}])
    """
    # 리포트 전용 글로벌 환경
    safe_globals = get_base_globals()
    safe_globals.update(
        {
            # 데이터 분석 라이브러리
            "pd": pd,
            "np": np,
            "alt": alt,
            # 리포트 헬퍼
            "build_report": build_report,
            "build_stat_cards": build_stat_cards,
            "build_charts_section": build_charts_section,
            "build_insights_section": build_insights_section,
            "build_tables_section": build_tables_section,
            "prepare_data": prepare_data,
            # 입력 데이터
            "data": data or [],
            "analysis": analysis or {},
            "charts": charts or [],
            "tables": tables or [],
        }
    )

    result = execute_with_context(code, safe_globals, context)
    result["guide"] = REPORT_GUIDE

    # 결과 검증
    if result["success"]:
        res = result.get("result")
        if not isinstance(res, dict) or "url" not in res:
            result["warning"] = "build_report()를 호출하여 URL을 반환해야 합니다."

    return result
