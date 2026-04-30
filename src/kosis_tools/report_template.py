"""
HTML 리포트 템플릿.

프린트 가능한 스탠드얼론 HTML 리포트를 생성합니다.
Vega-Lite 차트를 인라인으로 포함하고, 외부 의존성 없이 동작합니다.

Example:
    >>> from kosis_tools.report_template import build_report
    >>> html = build_report(
    ...     title="인구 분석 리포트",
    ...     sections=[
    ...         {"type": "text", "content": "<h2>개요</h2><p>...</p>"},
    ...         {"type": "chart", "vega_spec": {...}},
    ...         {"type": "table", "html": "<table>...</table>"},
    ...     ]
    ... )
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional


# Vega-Lite CDN URLs (프린트용으로 인라인 가능)
VEGA_CDN = "https://cdn.jsdelivr.net/npm/vega@5"
VEGA_LITE_CDN = "https://cdn.jsdelivr.net/npm/vega-lite@5"
VEGA_EMBED_CDN = "https://cdn.jsdelivr.net/npm/vega-embed@6"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="{vega_cdn}"></script>
    <script src="{vega_lite_cdn}"></script>
    <script src="{vega_embed_cdn}"></script>
    <style>
        /* 기본 스타일 */
        * {{
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont,
                         'Segoe UI', Roboto, 'Helvetica Neue', Arial,
                         'Noto Sans KR', sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            background: #fff;
        }}

        /* 헤더 */
        .report-header {{
            text-align: center;
            border-bottom: 2px solid #2c3e50;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}

        .report-header h1 {{
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 2rem;
        }}

        .report-meta {{
            color: #7f8c8d;
            font-size: 0.9rem;
        }}

        /* 섹션 */
        .section {{
            margin-bottom: 40px;
            page-break-inside: avoid;
        }}

        .section h2 {{
            color: #34495e;
            border-left: 4px solid #3498db;
            padding-left: 15px;
            margin-bottom: 20px;
        }}

        .section h3 {{
            color: #7f8c8d;
            margin-top: 25px;
        }}

        /* 차트 컨테이너 */
        .chart-container {{
            background: #fafafa;
            border: 1px solid #eee;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            text-align: center;
        }}

        .chart-container .vega-embed {{
            display: inline-block;
        }}

        /* 테이블 스타일 */
        .table-container {{
            overflow-x: auto;
            margin: 20px 0;
        }}

        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}

        .data-table th {{
            background: #34495e;
            color: white;
            padding: 12px 15px;
            text-align: left;
            font-weight: 500;
        }}

        .data-table td {{
            padding: 10px 15px;
            border-bottom: 1px solid #eee;
        }}

        .data-table tr:hover {{
            background: #f8f9fa;
        }}

        .data-table tr:nth-child(even) {{
            background: #fafafa;
        }}

        .table-note {{
            color: #7f8c8d;
            font-size: 0.85rem;
            font-style: italic;
            margin-top: 10px;
        }}

        /* 텍스트 콘텐츠 */
        .text-content {{
            text-align: justify;
        }}

        .text-content p {{
            margin-bottom: 15px;
        }}

        /* 인사이트 박스 */
        .insight-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px 25px;
            border-radius: 10px;
            margin: 20px 0;
        }}

        .insight-box h4 {{
            margin: 0 0 10px 0;
            font-size: 1.1rem;
        }}

        /* 통계 카드 */
        .stat-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}

        .stat-card {{
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }}

        .stat-card .value {{
            font-size: 2rem;
            font-weight: bold;
            color: #2c3e50;
        }}

        .stat-card .label {{
            color: #7f8c8d;
            font-size: 0.9rem;
        }}

        /* 푸터 */
        .report-footer {{
            border-top: 1px solid #eee;
            padding-top: 20px;
            margin-top: 40px;
            text-align: center;
            color: #7f8c8d;
            font-size: 0.85rem;
        }}

        /* 프린트 스타일 */
        @media print {{
            body {{
                padding: 0;
                font-size: 11pt;
            }}

            .report-header {{
                page-break-after: avoid;
            }}

            .section {{
                page-break-inside: avoid;
            }}

            .chart-container {{
                page-break-inside: avoid;
                background: white;
                border: 1px solid #ccc;
            }}

            .no-print {{
                display: none;
            }}

            a {{
                text-decoration: none;
                color: #333;
            }}
        }}

        /* 커스텀 스타일 */
        {custom_styles}
    </style>
</head>
<body>
    <header class="report-header">
        <h1>{title}</h1>
        <div class="report-meta">
            {subtitle}
            <br>
            생성일시: {generated_at}
        </div>
    </header>

    <main>
        {content}
    </main>

    <footer class="report-footer">
        <p>KOSIS 통계 데이터 기반 자동 생성 리포트</p>
        <p class="no-print">
            <a href="javascript:window.print()">이 리포트 인쇄하기</a>
        </p>
    </footer>

    <script>
        // Vega-Lite 차트 렌더링
        document.querySelectorAll('.vega-chart').forEach(function(el) {{
            var spec = JSON.parse(el.getAttribute('data-spec'));
            vegaEmbed(el, spec, {{
                actions: false,
                renderer: 'svg'  // 프린트용 SVG
            }}).catch(console.error);
        }});
    </script>
</body>
</html>"""


def build_chart_section(
    vega_spec: Dict[str, Any],
    title: Optional[str] = None,
    chart_id: Optional[str] = None,
) -> str:
    """
    Vega-Lite 차트 섹션을 생성합니다.

    Args:
        vega_spec: Vega-Lite 스펙 딕셔너리
        title: 차트 제목 (선택)
        chart_id: 차트 ID (선택, 자동 생성)

    Returns:
        HTML 문자열
    """
    import uuid

    chart_id = chart_id or f"chart-{uuid.uuid4().hex[:8]}"
    spec_json = json.dumps(vega_spec, ensure_ascii=False)

    html = '<div class="chart-container">'
    if title:
        html += f"<h3>{title}</h3>"
    html += f'<div id="{chart_id}" class="vega-chart" data-spec=\'{spec_json}\'></div>'
    html += "</div>"
    return html


def build_stat_cards(stats: List[Dict[str, Any]]) -> str:
    """
    통계 카드 섹션을 생성합니다.

    Args:
        stats: [{"label": "총인구", "value": "51,000,000", "unit": "명"}, ...]

    Returns:
        HTML 문자열
    """
    html = '<div class="stat-cards">'
    for stat in stats:
        value = stat.get("value", "")
        label = stat.get("label", "")
        unit = stat.get("unit", "")
        html += f"""
        <div class="stat-card">
            <div class="value">{value}<span style="font-size: 0.5em">{unit}</span></div>
            <div class="label">{label}</div>
        </div>
        """
    html += "</div>"
    return html


def build_insight_box(content: str, title: str = "핵심 인사이트") -> str:
    """
    인사이트 박스를 생성합니다.

    Args:
        content: 인사이트 내용 (HTML 가능)
        title: 박스 제목

    Returns:
        HTML 문자열
    """
    return f"""
    <div class="insight-box">
        <h4>{title}</h4>
        <p>{content}</p>
    </div>
    """


def build_report(
    title: str,
    sections: List[Dict[str, Any]],
    subtitle: str = "",
    custom_styles: str = "",
) -> str:
    """
    완성된 HTML 리포트를 생성합니다.

    Args:
        title: 리포트 제목
        sections: 섹션 리스트
            - {"type": "text", "content": "<p>...</p>"}
            - {"type": "chart", "vega_spec": {...}, "title": "..."}
            - {"type": "table", "html": "<table>...</table>"}
            - {"type": "stats", "items": [{"label": "...", "value": "..."}]}
            - {"type": "insight", "content": "...", "title": "..."}
            - {"type": "html", "content": "..."}  # 원시 HTML
        subtitle: 부제목
        custom_styles: 추가 CSS

    Returns:
        완성된 HTML 문자열
    """
    content_parts = []

    for section in sections:
        section_type = section.get("type", "html")

        if section_type == "text":
            html = (
                f'<div class="section text-content">{section.get("content", "")}</div>'
            )

        elif section_type == "chart":
            vega_spec = section.get("vega_spec", {})
            chart_title = section.get("title")
            html = f'<div class="section">{build_chart_section(vega_spec, chart_title)}</div>'

        elif section_type == "table":
            html = f'<div class="section">{section.get("html", "")}</div>'

        elif section_type == "stats":
            items = section.get("items", [])
            html = f'<div class="section">{build_stat_cards(items)}</div>'

        elif section_type == "insight":
            content = section.get("content", "")
            insight_title = section.get("title", "핵심 인사이트")
            html = f'<div class="section">{build_insight_box(content, insight_title)}</div>'

        elif section_type == "html":
            html = section.get("content", "")

        else:
            html = f'<div class="section">{section.get("content", "")}</div>'

        content_parts.append(html)

    generated_at = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")

    return HTML_TEMPLATE.format(
        title=title,
        subtitle=subtitle,
        generated_at=generated_at,
        content="\n".join(content_parts),
        custom_styles=custom_styles,
        vega_cdn=VEGA_CDN,
        vega_lite_cdn=VEGA_LITE_CDN,
        vega_embed_cdn=VEGA_EMBED_CDN,
    )


def quick_report(
    title: str,
    chart_specs: Optional[List[Dict[str, Any]]] = None,
    tables: Optional[List[str]] = None,
    insights: Optional[List[str]] = None,
    intro: Optional[str] = None,
) -> str:
    """
    빠른 리포트 생성을 위한 편의 함수.

    Args:
        title: 리포트 제목
        chart_specs: Vega-Lite 스펙 리스트
        tables: HTML 테이블 리스트
        insights: 인사이트 문자열 리스트
        intro: 서론 HTML

    Returns:
        완성된 HTML 리포트
    """
    sections = []

    if intro:
        sections.append({"type": "text", "content": intro})

    if insights:
        for insight in insights:
            sections.append({"type": "insight", "content": insight})

    if chart_specs:
        for i, spec in enumerate(chart_specs):
            sections.append(
                {
                    "type": "chart",
                    "vega_spec": spec,
                    "title": spec.get("title", {}).get("text", f"차트 {i + 1}"),
                }
            )

    if tables:
        for table in tables:
            sections.append({"type": "table", "html": table})

    return build_report(title=title, sections=sections)
