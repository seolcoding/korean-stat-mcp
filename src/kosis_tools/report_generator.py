"""
KOSIS 데이터 분석 리포트 생성 모듈.

이 모듈은 유저 인풋을 기반으로 동적으로 데이터 분석 리포트를 생성합니다.
LLM이 유저의 질문이나 요청에 맞춰 맞춤형 분석을 수행할 수 있도록 지원합니다.

주요 기능:
    - 동적 리포트 생성: 유저 인풋 기반 분석
    - 섹션별 모듈화: 선택적 섹션 포함
    - 다양한 출력 형식: Markdown, HTML, JSON
    - LLM 친화적 구조: 프롬프트 생성 지원

시각화:
    - 기본 패키지는 네이티브 차트 생성을 포함하지 않음

Example:
    기본 사용:
    >>> from kosis_tools.report_generator import ReportGenerator
    >>>
    >>> generator = ReportGenerator(data)
    >>> report = generator.generate(
    ...     user_query="서울과 부산의 인구 변화를 비교해주세요",
    ...     sections=["summary", "comparison", "visualization"]
    ... )

    LLM 통합:
    >>> context = generator.create_llm_context(
    ...     user_query="최근 물가 상승 원인을 분석해주세요"
    ... )
    >>> # LLM에 context 전달하여 분석 요청

Note:
    - 모든 메서드는 유저 인풋에 따라 동적으로 결과가 달라집니다.
    - 시각화는 유저 요청에 맞는 차트 유형을 자동 선택합니다.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from .transform import KosisTransformer, Fields, FieldLabels

logger = logging.getLogger(__name__)
alt: Any = None  # Native Altair support was removed from the base package.


@dataclass
class UserQuery:
    """
    유저 쿼리를 구조화한 클래스.

    Attributes:
        raw_query: 원본 쿼리 문자열
        target_regions: 분석 대상 지역 목록
        target_periods: 분석 대상 기간 목록
        target_items: 분석 대상 항목 목록
        comparison_type: 비교 유형 (temporal, regional, categorical)
        analysis_depth: 분석 깊이 (quick, standard, deep)
        output_format: 출력 형식 (markdown, html, json)
        include_visualization: 시각화 포함 여부
        custom_params: 추가 파라미터
    """

    raw_query: str
    target_regions: List[str] = field(default_factory=list)
    target_periods: List[str] = field(default_factory=list)
    target_items: List[str] = field(default_factory=list)
    comparison_type: str = "temporal"  # temporal, regional, categorical
    analysis_depth: str = "standard"  # quick, standard, deep
    output_format: str = "markdown"  # markdown, html, json
    include_visualization: bool = True
    custom_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportSection:
    """
    리포트 섹션 데이터 클래스.

    Attributes:
        name: 섹션 이름
        title: 섹션 제목 (표시용)
        content: 섹션 내용
        charts: 관련 시각화 리스트
        data: 관련 데이터 (DataFrame 또는 dict)
    """

    name: str
    title: str
    content: str
    charts: List[Any] = field(default_factory=list)
    data: Optional[Union[pd.DataFrame, Dict]] = None


class ReportGenerator:
    """
    유저 인풋 기반 동적 리포트 생성 클래스.

    유저의 질문이나 요청에 맞춰 데이터 분석 리포트를 동적으로 생성합니다.
    LLM이 활용할 수 있는 구조화된 컨텍스트도 제공합니다.

    Attributes:
        data: 원본 KOSIS API 응답 데이터
        tx: KosisTransformer 인스턴스

    Example:
        >>> generator = ReportGenerator(records)
        >>> report = generator.generate(
        ...     user_query="지역별 인구 순위를 알려주세요",
        ...     include_chart=True
        ... )
        >>> print(report)
    """

    def __init__(
        self,
        data: List[Dict[str, Any]],
    ):
        """
        리포트 생성기를 초기화합니다.

        Args:
            data: KOSIS API 응답 데이터 (레코드 리스트)
        """
        self.data = data
        self.tx = KosisTransformer(data)
        self._sections: List[ReportSection] = []

    def parse_user_query(self, query: str) -> UserQuery:
        """
        유저 쿼리를 분석하여 구조화합니다.

        자연어 쿼리에서 지역, 기간, 비교 유형 등을 추출합니다.
        LLM이 호출하여 쿼리를 파싱할 때 사용합니다.

        Args:
            query: 유저의 자연어 쿼리

        Returns:
            구조화된 UserQuery 객체

        Example:
            >>> generator.parse_user_query("서울과 부산의 2020-2023 인구 비교")
            UserQuery(
                raw_query="서울과 부산의 2020-2023 인구 비교",
                target_regions=["서울", "부산"],
                target_periods=["2020", "2021", "2022", "2023"],
                comparison_type="regional"
            )
        """
        user_query = UserQuery(raw_query=query)

        # 지역 키워드 추출
        available_regions = self.tx.get_unique_values(Fields.C1_NM)
        for region in available_regions:
            if (
                region in query
                or region.replace("특별시", "").replace("광역시", "") in query
            ):
                user_query.target_regions.append(region)

        # 기간 키워드 추출 (연도)
        available_periods = self.tx.get_unique_values(Fields.PERIOD)
        import re

        year_pattern = r"20\d{2}"
        years_in_query = re.findall(year_pattern, query)
        for year in years_in_query:
            if year in available_periods:
                user_query.target_periods.append(year)

        # 기간 범위 추출 (예: 2020-2023)
        range_pattern = r"(20\d{2})[-~](20\d{2})"
        range_match = re.search(range_pattern, query)
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            user_query.target_periods = [
                str(y) for y in range(start, end + 1) if str(y) in available_periods
            ]

        # 비교 유형 결정
        if any(word in query for word in ["비교", "차이", "vs", "versus"]):
            if len(user_query.target_regions) >= 2:
                user_query.comparison_type = "regional"
            elif len(user_query.target_periods) >= 2:
                user_query.comparison_type = "temporal"
            else:
                user_query.comparison_type = "categorical"
        elif any(word in query for word in ["추이", "변화", "트렌드", "trend"]):
            user_query.comparison_type = "temporal"
        elif any(word in query for word in ["순위", "랭킹", "top", "상위"]):
            user_query.comparison_type = "ranking"

        # 분석 깊이 결정
        if any(word in query for word in ["자세히", "상세", "깊이", "심층"]):
            user_query.analysis_depth = "deep"
        elif any(word in query for word in ["간단히", "요약", "빠르게"]):
            user_query.analysis_depth = "quick"

        # 시각화 여부
        user_query.include_visualization = (
            any(
                word in query
                for word in ["차트", "그래프", "시각화", "chart", "graph", "plot"]
            )
            or "시각" not in query
        )  # 기본적으로 시각화 포함

        return user_query

    def generate(
        self,
        user_query: Optional[str] = None,
        parsed_query: Optional[UserQuery] = None,
        sections: Optional[List[str]] = None,
        output_dir: Optional[Path] = None,
    ) -> str:
        """
        유저 인풋 기반 분석 리포트를 생성합니다.

        Args:
            user_query: 유저의 자연어 쿼리 (parsed_query와 둘 중 하나 필수)
            parsed_query: 이미 파싱된 UserQuery 객체
            sections: 포함할 섹션 목록. None이면 자동 결정.
                     가능한 값: summary, eda, stats, comparison,
                               ranking, trend, visualization, insight
            output_dir: 시각화 파일 저장 경로

        Returns:
            생성된 리포트 (Markdown 형식)

        Example:
            >>> report = generator.generate(
            ...     user_query="최근 5년간 서울의 인구 변화를 분석해주세요"
            ... )
            >>> print(report)
        """
        # 쿼리 파싱
        if parsed_query is None:
            if user_query is None:
                user_query = "전체 데이터 분석"
            parsed_query = self.parse_user_query(user_query)

        # 섹션 자동 결정
        if sections is None:
            sections = self._determine_sections(parsed_query)

        # 데이터 필터링
        filtered_tx = self._apply_query_filters(parsed_query)

        # 리포트 빌드
        self._sections = []
        report_lines = []

        # 헤더
        report_lines.append("# 📊 KOSIS 데이터 분석 리포트")
        report_lines.append("")
        report_lines.append(f"> **분석 요청**: {parsed_query.raw_query}")
        report_lines.append("")

        # 각 섹션 생성
        for section_name in sections:
            section = self._generate_section(
                section_name, filtered_tx, parsed_query, output_dir
            )
            if section:
                self._sections.append(section)
                report_lines.append(f"## {section.title}")
                report_lines.append("")
                report_lines.append(section.content)
                report_lines.append("")

        return "\n".join(report_lines)

    def generate_html(
        self,
        user_query: Optional[str] = None,
        parsed_query: Optional[UserQuery] = None,
        sections: Optional[List[str]] = None,
        output_path: Optional[Union[str, Path]] = None,
        title: Optional[str] = None,
        save_debug_info: bool = False,
    ) -> str:
        """
        인터랙티브 HTML 보고서를 생성합니다.

        Plotly 차트가 임베드된 단일 HTML 아티팩트를 생성합니다.
        브라우저에서 바로 열어 인터랙티브하게 탐색할 수 있습니다.

        Args:
            user_query: 유저의 자연어 쿼리 (parsed_query와 둘 중 하나 필수)
            parsed_query: 이미 파싱된 UserQuery 객체
            sections: 포함할 섹션 목록. None이면 자동 결정.
            output_path: HTML 파일 저장 경로. None이면 HTML 문자열만 반환.
            title: 보고서 제목
            save_debug_info: True이면 .debug.json 파일에 메타데이터 저장

        Returns:
            output_path가 None이면 HTML 문자열,
            output_path가 있으면 저장된 파일 경로

        Example:
            >>> generator = ReportGenerator(records)
            >>> html = generator.generate_html(
            ...     user_query="서울 인구 변화",
            ...     output_path="report.html",
            ...     save_debug_info=True
            ... )
        """
        # 디버그 정보 수집
        debug_steps = []
        start_time = time.perf_counter()
        records_before = len(self.data)

        # 1. 쿼리 파싱
        step_start = time.perf_counter()
        if parsed_query is None:
            if user_query is None:
                user_query = "전체 데이터 분석"
            parsed_query = self.parse_user_query(user_query)
        debug_steps.append(
            {
                "step": "parse_query",
                "detail": f"쿼리 파싱: '{parsed_query.raw_query}'",
                "duration_ms": (time.perf_counter() - step_start) * 1000,
            }
        )

        # 2. 섹션 자동 결정
        step_start = time.perf_counter()
        if sections is None:
            sections = self._determine_sections(parsed_query)
        debug_steps.append(
            {
                "step": "determine_sections",
                "detail": f"섹션 결정: {', '.join(sections)}",
                "sections": sections,
                "duration_ms": (time.perf_counter() - step_start) * 1000,
            }
        )

        # 3. 데이터 필터링
        step_start = time.perf_counter()
        filtered_tx = self._apply_query_filters(parsed_query)
        records_after = len(filtered_tx.df)
        debug_steps.append(
            {
                "step": "filter_data",
                "detail": f"데이터 필터링: {records_before}건 → {records_after}건",
                "records_before": records_before,
                "records_after": records_after,
                "duration_ms": (time.perf_counter() - step_start) * 1000,
            }
        )

        # 제목 설정
        report_title = title or f"KOSIS 데이터 분석: {parsed_query.raw_query}"

        # 4. HTML 헤더 생성
        step_start = time.perf_counter()
        html_parts = [self._html_header(report_title)]
        debug_steps.append(
            {
                "step": "generate_header",
                "detail": "HTML 헤더 생성",
                "duration_ms": (time.perf_counter() - step_start) * 1000,
            }
        )

        # 5. 요약 정보 카드 생성
        step_start = time.perf_counter()
        html_parts.append(self._html_summary_card(filtered_tx, parsed_query))
        debug_steps.append(
            {
                "step": "generate_summary_card",
                "detail": "요약 카드 생성",
                "duration_ms": (time.perf_counter() - step_start) * 1000,
            }
        )

        # 6. 각 섹션 생성
        for section_name in sections:
            step_start = time.perf_counter()
            section_html = self._generate_html_section(
                section_name, filtered_tx, parsed_query
            )
            if section_html:
                html_parts.append(section_html)
            debug_steps.append(
                {
                    "step": f"generate_section_{section_name}",
                    "detail": f"섹션 생성: {section_name}",
                    "success": section_html is not None,
                    "duration_ms": (time.perf_counter() - step_start) * 1000,
                }
            )

        # 7. 푸터 생성
        step_start = time.perf_counter()
        html_parts.append(self._html_footer())
        debug_steps.append(
            {
                "step": "generate_footer",
                "detail": "HTML 푸터 생성",
                "duration_ms": (time.perf_counter() - step_start) * 1000,
            }
        )

        html_content = "\n".join(html_parts)

        # 총 소요 시간
        total_duration = (time.perf_counter() - start_time) * 1000

        # 저장 또는 반환
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(html_content, encoding="utf-8")
            logger.info(f"HTML 보고서 저장: {output_path}")

            # 디버그 정보 저장
            if save_debug_info:
                debug_info = {
                    "report_id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat(),
                    "user_query": parsed_query.raw_query,
                    "parsed_query": {
                        "raw_query": parsed_query.raw_query,
                        "target_regions": parsed_query.target_regions,
                        "target_periods": parsed_query.target_periods,
                        "target_items": parsed_query.target_items,
                        "comparison_type": parsed_query.comparison_type,
                        "analysis_depth": parsed_query.analysis_depth,
                        "include_visualization": parsed_query.include_visualization,
                    },
                    "sections_determined": sections,
                    "processing_steps": debug_steps,
                    "data_info": {
                        "total_records": records_before,
                        "filtered_records": records_after,
                        "columns": list(self.tx.df.columns),
                        "unique_regions": len(self.tx.get_unique_values(Fields.C1_NM)),
                        "unique_periods": len(self.tx.get_unique_values(Fields.PERIOD)),
                    },
                    "output_path": output_path.name,
                    "total_duration_ms": total_duration,
                }

                debug_path = output_path.with_suffix(".debug.json")
                debug_path.write_text(
                    json.dumps(debug_info, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logger.info(f"디버그 정보 저장: {debug_path}")

            return str(output_path)

        return html_content

    def _html_header(self, title: str) -> str:
        """HTML 헤더 생성"""
        return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
    <script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Noto Sans KR', 'Malgun Gothic', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .header {{
            background: white;
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}

        .header h1 {{
            font-size: 2rem;
            color: #333;
            margin-bottom: 10px;
        }}

        .header .subtitle {{
            color: #666;
            font-size: 1.1rem;
        }}

        .query-badge {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            margin-top: 15px;
            font-size: 0.9rem;
        }}

        .card {{
            background: white;
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}

        .card h2 {{
            font-size: 1.4rem;
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #f0f0f0;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}

        .stat-item {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 12px;
            text-align: center;
        }}

        .stat-value {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #667eea;
        }}

        .stat-label {{
            font-size: 0.9rem;
            color: #666;
            margin-top: 5px;
        }}

        .chart-container {{
            margin: 20px 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}

        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }}

        th {{
            background: #f8f9fa;
            font-weight: 600;
            color: #333;
        }}

        tr:hover {{
            background: #f8f9fa;
        }}

        .insight-box {{
            background: linear-gradient(135deg, #fff9c4 0%, #fff59d 100%);
            padding: 20px;
            border-radius: 12px;
            margin: 15px 0;
        }}

        .insight-box h3 {{
            color: #f57f17;
            margin-bottom: 10px;
        }}

        .footer {{
            text-align: center;
            color: white;
            padding: 20px;
            font-size: 0.9rem;
        }}

        .footer a {{
            color: white;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 {title}</h1>
            <p class="subtitle">KOSIS 데이터 기반 자동 생성 분석 보고서</p>
        </div>
"""

    def _html_footer(self) -> str:
        """HTML 푸터 생성"""
        from datetime import datetime

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"""
        <div class="footer">
            <p>Generated by KOSIS Data Processor | {now}</p>
            <p>Data Source: <a href="https://kosis.kr" target="_blank">KOSIS (국가통계포털)</a></p>
        </div>
    </div>
</body>
</html>
"""

    def _html_summary_card(self, tx: KosisTransformer, query: UserQuery) -> str:
        """요약 카드 HTML 생성"""
        df = tx.df

        # 통계 계산
        record_count = len(df)
        periods = tx.get_unique_values(Fields.PERIOD)
        regions = tx.get_unique_values(Fields.C1_NM)

        period_range = f"{periods[0]} ~ {periods[-1]}" if periods else "N/A"
        region_count = len(regions)

        return f"""
        <div class="card">
            <h2>📋 데이터 요약</h2>
            <div class="query-badge">분석 요청: {query.raw_query}</div>
            <div class="stats-grid" style="margin-top: 20px;">
                <div class="stat-item">
                    <div class="stat-value">{record_count:,}</div>
                    <div class="stat-label">총 데이터 건수</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{len(periods)}</div>
                    <div class="stat-label">기간 ({period_range})</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{region_count}</div>
                    <div class="stat-label">분류 항목</div>
                </div>
            </div>
        </div>
"""

    def _generate_html_section(
        self,
        section_name: str,
        tx: KosisTransformer,
        query: UserQuery,
    ) -> Optional[str]:
        """개별 HTML 섹션 생성"""
        generators = {
            "eda": self._html_eda,
            "stats": self._html_stats,
            "comparison": self._html_comparison,
            "ranking": self._html_ranking,
            "trend": self._html_trend,
            "visualization": self._html_visualization,
            "insight": self._html_insight,
        }

        generator = generators.get(section_name)
        if generator:
            return generator(tx, query)
        return None

    def _html_eda(self, tx: KosisTransformer, query: UserQuery) -> str:
        """EDA 섹션 HTML"""
        field_info = tx.get_field_info()

        # 컨텍스트 감지하여 적절한 라벨 사용
        context = FieldLabels.detect_context(tx.to_records(), query.raw_query)

        rows = ""
        for fname, info in list(field_info.items())[:8]:
            korean_label = FieldLabels.get_label(fname, context)
            rows += f"<tr><td>{korean_label}</td><td>{info['dtype']}</td><td>{info['nunique']}</td></tr>"

        return f"""
        <div class="card">
            <h2>🔍 데이터 구조 탐색</h2>
            <table>
                <thead>
                    <tr><th>필드</th><th>데이터 타입</th><th>고유값 수</th></tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
"""

    def _html_stats(self, tx: KosisTransformer, query: UserQuery) -> str:
        """통계 섹션 HTML"""
        if Fields.VALUE not in tx.df.columns:
            return ""

        stats = tx.get_summary_stats()

        return f"""
        <div class="card">
            <h2>📈 주요 통계</h2>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-value">{stats["mean"].iloc[0]:,.0f}</div>
                    <div class="stat-label">평균</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{stats["min"].iloc[0]:,.0f}</div>
                    <div class="stat-label">최소값</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{stats["max"].iloc[0]:,.0f}</div>
                    <div class="stat-label">최대값</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{stats["std"].iloc[0]:,.0f}</div>
                    <div class="stat-label">표준편차</div>
                </div>
            </div>
        </div>
"""

    def _html_comparison(self, tx: KosisTransformer, query: UserQuery) -> str:
        """비교 섹션 HTML"""
        if not query.target_regions or len(query.target_regions) < 2:
            regions = tx.get_unique_values(Fields.C1_NM)[:5]
        else:
            regions = query.target_regions

        grouped = tx.filter_by(Fields.C1_NM, regions).groupby(Fields.C1_NM)

        rows = ""
        for _, row in grouped.iterrows():
            rows += f"<tr><td>{row[Fields.C1_NM]}</td><td>{row[Fields.VALUE]:,.0f}</td></tr>"

        return f"""
        <div class="card">
            <h2>⚖️ 지역별 비교</h2>
            <table>
                <thead>
                    <tr><th>지역</th><th>합계</th></tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
"""

    def _html_ranking(self, tx: KosisTransformer, query: UserQuery) -> str:
        """순위 섹션 HTML"""
        periods = tx.get_unique_values(Fields.PERIOD)
        if not periods:
            return ""

        latest = periods[-1]
        latest_tx = tx.filter_by(Fields.PERIOD, latest)
        ranked = latest_tx.rank_by(Fields.VALUE, top_n=10)

        rows = ""
        for idx, row in enumerate(ranked.to_dict("records"), 1):
            region = row.get(Fields.C1_NM, "N/A")
            value = row.get(Fields.VALUE, 0)
            rows += f"<tr><td>{idx}</td><td>{region}</td><td>{value:,.0f}</td></tr>"

        return f"""
        <div class="card">
            <h2>🏆 순위 분석 ({latest} 기준)</h2>
            <table>
                <thead>
                    <tr><th>순위</th><th>분류</th><th>값</th></tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
"""

    def _html_trend(self, tx: KosisTransformer, query: UserQuery) -> str:
        """추이 섹션 HTML"""
        if query.target_regions:
            target = query.target_regions[0]
        else:
            regions = tx.get_unique_values(Fields.C1_NM)
            target = regions[0] if regions else None

        if not target or Fields.C1_NM not in tx.df.columns:
            return ""

        trend_tx = tx.filter_by(Fields.C1_NM, target)
        growth = trend_tx.calculate_growth()

        rows = ""
        for row in growth.to_dict("records"):
            period = row.get(Fields.PERIOD, "N/A")
            value = row.get(Fields.VALUE, 0)
            growth_pct = row.get("growth_pct", None)
            growth_str = f"{growth_pct:+.2f}%" if growth_pct is not None else "-"
            color = (
                "green"
                if growth_pct and growth_pct > 0
                else "red"
                if growth_pct and growth_pct < 0
                else "gray"
            )
            rows += f"<tr><td>{period}</td><td>{value:,.0f}</td><td style='color:{color}'>{growth_str}</td></tr>"

        return f"""
        <div class="card">
            <h2>📊 {target} 추이 분석</h2>
            <table>
                <thead>
                    <tr><th>기간</th><th>값</th><th>변동률</th></tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        </div>
"""

    def _html_visualization(self, tx: KosisTransformer, query: UserQuery) -> str:
        """시각화 섹션 HTML."""
        return """
        <div class="card">
            <h2>시각화</h2>
            <p>네이티브 차트 생성은 기본 패키지에 포함되지 않습니다.</p>
        </div>
"""

        import uuid

        charts_html = []
        df = tx.df.copy()

        # 컨텍스트 기반 라벨 생성
        context = FieldLabels.detect_context(tx.to_records(), query.raw_query)
        labels = self._build_labels(context)

        def chart_to_html(chart, chart_id: str) -> str:
            """Altair 차트를 Vega-Embed HTML로 변환"""
            spec = chart.to_json()
            return f'''
            <div id="{chart_id}" class="chart-container"></div>
            <script>
                vegaEmbed('#{chart_id}', {spec}, {{"renderer": "svg"}}).catch(console.error);
            </script>
            '''

        # 비교 유형에 따른 차트 선택
        if query.comparison_type == "temporal":
            chart = (
                alt.Chart(df)
                .mark_line(point=True)
                .encode(
                    x=alt.X(
                        f"{Fields.PERIOD}:N", title=labels.get(Fields.PERIOD, "기간")
                    ),
                    y=alt.Y(f"{Fields.VALUE}:Q", title=labels.get(Fields.VALUE, "값")),
                    color=alt.Color(
                        f"{Fields.C1_NM}:N", title=labels.get(Fields.C1_NM, "분류")
                    )
                    if Fields.C1_NM in df.columns
                    else alt.value("steelblue"),
                )
                .properties(title="시계열 추이", width=600, height=400)
            )
            charts_html.append(chart_to_html(chart, f"chart_{uuid.uuid4().hex[:8]}"))

        elif query.comparison_type == "regional":
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    x=alt.X(
                        f"{Fields.C1_NM}:N", title=labels.get(Fields.C1_NM, "지역")
                    ),
                    y=alt.Y(f"{Fields.VALUE}:Q", title=labels.get(Fields.VALUE, "값")),
                    color=alt.Color(
                        f"{Fields.PERIOD}:N", title=labels.get(Fields.PERIOD, "기간")
                    )
                    if Fields.PERIOD in df.columns
                    else alt.value("steelblue"),
                )
                .properties(title="지역별 비교", width=600, height=400)
            )
            charts_html.append(chart_to_html(chart, f"chart_{uuid.uuid4().hex[:8]}"))

        elif query.comparison_type == "ranking":
            ranked = tx.rank_by(Fields.VALUE, top_n=10)
            chart = (
                alt.Chart(ranked)
                .mark_bar()
                .encode(
                    x=alt.X(f"{Fields.VALUE}:Q", title=labels.get(Fields.VALUE, "값")),
                    y=alt.Y(
                        f"{Fields.C1_NM}:N",
                        title=labels.get(Fields.C1_NM, "분류"),
                        sort="-x",
                    ),
                )
                .properties(title="상위 순위", width=600, height=400)
            )
            charts_html.append(chart_to_html(chart, f"chart_{uuid.uuid4().hex[:8]}"))

        else:
            # 기본: 라인 차트 + 막대 차트
            chart1 = (
                alt.Chart(df)
                .mark_line(point=True)
                .encode(
                    x=alt.X(
                        f"{Fields.PERIOD}:N", title=labels.get(Fields.PERIOD, "기간")
                    ),
                    y=alt.Y(f"{Fields.VALUE}:Q", title=labels.get(Fields.VALUE, "값")),
                    color=alt.Color(
                        f"{Fields.C1_NM}:N", title=labels.get(Fields.C1_NM, "분류")
                    )
                    if Fields.C1_NM in df.columns
                    else alt.value("steelblue"),
                )
                .properties(title="시계열 추이", width=600, height=400)
            )
            charts_html.append(chart_to_html(chart1, f"chart_{uuid.uuid4().hex[:8]}"))

            x_field = Fields.C1_NM if Fields.C1_NM in df.columns else Fields.PERIOD
            chart2 = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    x=alt.X(f"{x_field}:N", title=labels.get(x_field, "분류")),
                    y=alt.Y(f"{Fields.VALUE}:Q", title=labels.get(Fields.VALUE, "값")),
                )
                .properties(title="분류별 비교", width=600, height=400)
            )
            charts_html.append(chart_to_html(chart2, f"chart_{uuid.uuid4().hex[:8]}"))

        all_charts = "\n".join(charts_html)

        return f"""
        <div class="card">
            <h2>📊 인터랙티브 시각화</h2>
            {all_charts}
        </div>
"""

    def _build_labels(self, context: Optional[str] = None) -> Dict[str, str]:
        """컨텍스트 기반 필드 라벨 딕셔너리 생성"""
        # 모든 주요 필드에 대한 라벨 생성
        fields = [
            Fields.PERIOD,
            Fields.C1_NM,
            Fields.C2_NM,
            Fields.C3_NM,
            Fields.VALUE,
            Fields.UNIT,
            Fields.ITM_NM,
        ]
        return {field: FieldLabels.get_label(field, context) for field in fields}

    def _html_insight(self, tx: KosisTransformer, query: UserQuery) -> str:
        """인사이트 섹션 HTML"""
        insights = []

        if Fields.VALUE in tx.df.columns:
            df = tx.df
            max_idx = df[Fields.VALUE].idxmax()
            min_idx = df[Fields.VALUE].idxmin()

            if pd.notna(max_idx):
                max_row = df.loc[max_idx]
                max_region = max_row.get(Fields.C1_NM, "N/A")
                max_period = max_row.get(Fields.PERIOD, "N/A")
                max_val = max_row[Fields.VALUE]
                insights.append(
                    f"<li><strong>최대값</strong>: {max_region} ({max_period}) - {max_val:,.0f}</li>"
                )

            if pd.notna(min_idx):
                min_row = df.loc[min_idx]
                min_region = min_row.get(Fields.C1_NM, "N/A")
                min_period = min_row.get(Fields.PERIOD, "N/A")
                min_val = min_row[Fields.VALUE]
                insights.append(
                    f"<li><strong>최소값</strong>: {min_region} ({min_period}) - {min_val:,.0f}</li>"
                )

        insights_html = (
            "\n".join(insights) if insights else "<li>추가 분석이 필요합니다.</li>"
        )

        return f"""
        <div class="card">
            <h2>💡 주요 인사이트</h2>
            <div class="insight-box">
                <h3>📍 주요 발견사항</h3>
                <ul>
                    {insights_html}
                </ul>
            </div>
        </div>
"""

    def _determine_sections(self, query: UserQuery) -> List[str]:
        """쿼리에 따른 섹션 자동 결정"""
        sections = ["summary"]

        if query.analysis_depth in ["standard", "deep"]:
            sections.append("eda")

        if query.comparison_type == "temporal":
            sections.extend(["trend", "stats"])
        elif query.comparison_type == "regional":
            sections.extend(["comparison", "stats"])
        elif query.comparison_type == "ranking":
            sections.extend(["ranking", "stats"])
        else:
            sections.extend(["stats"])

        if query.include_visualization:
            sections.append("visualization")

        if query.analysis_depth == "deep":
            sections.append("insight")

        return sections

    def _apply_query_filters(self, query: UserQuery) -> KosisTransformer:
        """쿼리 조건에 따른 데이터 필터링"""
        filtered_tx = self.tx

        if query.target_regions:
            filtered_tx = filtered_tx.filter_by(Fields.C1_NM, query.target_regions)

        if query.target_periods:
            filtered_tx = filtered_tx.filter_by(Fields.PERIOD, query.target_periods)

        if query.target_items and Fields.ITM_NM in filtered_tx.df.columns:
            filtered_tx = filtered_tx.filter_by(Fields.ITM_NM, query.target_items)

        return filtered_tx

    def _generate_section(
        self,
        section_name: str,
        tx: KosisTransformer,
        query: UserQuery,
        output_dir: Optional[Path],
    ) -> Optional[ReportSection]:
        """개별 섹션 생성"""

        generators = {
            "summary": self._gen_summary,
            "eda": self._gen_eda,
            "stats": self._gen_stats,
            "comparison": self._gen_comparison,
            "ranking": self._gen_ranking,
            "trend": self._gen_trend,
            "visualization": self._gen_visualization,
            "insight": self._gen_insight,
        }

        generator = generators.get(section_name)
        if generator:
            return generator(tx, query, output_dir)
        return None

    def _gen_summary(
        self, tx: KosisTransformer, query: UserQuery, output_dir: Optional[Path]
    ) -> ReportSection:
        """요약 섹션 생성"""
        df = tx.df
        lines = []

        # 기본 정보
        lines.append(f"- **데이터 건수**: {len(df):,}건")

        if Fields.PERIOD in df.columns:
            periods = tx.get_unique_values(Fields.PERIOD)
            lines.append(
                f"- **기간**: {periods[0]} ~ {periods[-1]} ({len(periods)}개 시점)"
            )

        if Fields.C1_NM in df.columns:
            regions = tx.get_unique_values(Fields.C1_NM)
            lines.append(f"- **분류**: {len(regions)}개 ({', '.join(regions[:5])}...)")

        # 분석 대상 요약
        if query.target_regions:
            lines.append(f"- **분석 대상 지역**: {', '.join(query.target_regions)}")
        if query.target_periods:
            lines.append(f"- **분석 대상 기간**: {', '.join(query.target_periods)}")

        return ReportSection(
            name="summary",
            title="📋 데이터 요약",
            content="\n".join(lines),
        )

    def _gen_eda(
        self, tx: KosisTransformer, query: UserQuery, output_dir: Optional[Path]
    ) -> ReportSection:
        """EDA 섹션 생성"""
        lines = []

        # 컨텍스트 감지
        context = FieldLabels.detect_context(tx.to_records(), query.raw_query)

        # 필드 정보
        lines.append("### 필드 구조")
        lines.append("```")
        field_info = tx.get_field_info()
        for fname, info in list(field_info.items())[:10]:
            korean_label = FieldLabels.get_label(fname, context)
            lines.append(f"{korean_label}: {info['dtype']}, {info['nunique']}개 고유값")
        lines.append("```")

        # 샘플 데이터
        lines.append("")
        lines.append("### 샘플 데이터")
        lines.append("```")
        sample_cols = [
            c for c in [Fields.PERIOD, Fields.C1_NM, Fields.VALUE] if c in tx.df.columns
        ]
        lines.append(tx.df[sample_cols].head(5).to_string(index=False))
        lines.append("```")

        return ReportSection(
            name="eda",
            title="🔍 탐색적 데이터 분석 (EDA)",
            content="\n".join(lines),
        )

    def _gen_stats(
        self, tx: KosisTransformer, query: UserQuery, output_dir: Optional[Path]
    ) -> ReportSection:
        """통계 섹션 생성"""
        lines = []

        if Fields.VALUE not in tx.df.columns:
            return ReportSection(
                name="stats",
                title="📈 주요 통계",
                content="값(DT) 필드가 없습니다.",
            )

        stats = tx.get_summary_stats()
        lines.append("| 통계량 | 값 |")
        lines.append("|--------|-----|")
        lines.append(f"| 개수 | {int(stats['count'].iloc[0]):,} |")
        lines.append(f"| 평균 | {stats['mean'].iloc[0]:,.2f} |")
        lines.append(f"| 표준편차 | {stats['std'].iloc[0]:,.2f} |")
        lines.append(f"| 최소값 | {stats['min'].iloc[0]:,.2f} |")
        lines.append(f"| 중앙값 | {stats['50%'].iloc[0]:,.2f} |")
        lines.append(f"| 최대값 | {stats['max'].iloc[0]:,.2f} |")

        return ReportSection(
            name="stats",
            title="📈 주요 통계",
            content="\n".join(lines),
            data=stats,
        )

    def _gen_comparison(
        self, tx: KosisTransformer, query: UserQuery, output_dir: Optional[Path]
    ) -> ReportSection:
        """비교 섹션 생성"""
        lines = []

        if not query.target_regions or len(query.target_regions) < 2:
            regions = tx.get_unique_values(Fields.C1_NM)[:5]
        else:
            regions = query.target_regions

        # 지역별 그룹 통계
        grouped = tx.filter_by(Fields.C1_NM, regions).groupby(Fields.C1_NM)

        lines.append("| 지역 | 합계 |")
        lines.append("|------|------|")
        for _, row in grouped.iterrows():
            lines.append(f"| {row[Fields.C1_NM]} | {row[Fields.VALUE]:,.0f} |")

        return ReportSection(
            name="comparison",
            title="⚖️ 지역별 비교",
            content="\n".join(lines),
            data=grouped,
        )

    def _gen_ranking(
        self, tx: KosisTransformer, query: UserQuery, output_dir: Optional[Path]
    ) -> ReportSection:
        """순위 섹션 생성"""
        lines = []

        # 최근 기간의 순위
        periods = tx.get_unique_values(Fields.PERIOD)
        if periods:
            latest = periods[-1]
            latest_tx = tx.filter_by(Fields.PERIOD, latest)
            ranked = latest_tx.rank_by(Fields.VALUE, top_n=10)

            lines.append(f"### {latest} 기준 상위 10개")
            lines.append("")
            lines.append("| 순위 | 분류 | 값 |")
            lines.append("|------|------|-----|")

            for idx, row in enumerate(ranked.to_dict("records"), 1):
                region = row.get(Fields.C1_NM, "N/A")
                value = row.get(Fields.VALUE, 0)
                lines.append(f"| {idx} | {region} | {value:,.0f} |")

        return ReportSection(
            name="ranking",
            title="🏆 순위 분석",
            content="\n".join(lines),
        )

    def _gen_trend(
        self, tx: KosisTransformer, query: UserQuery, output_dir: Optional[Path]
    ) -> ReportSection:
        """추이 섹션 생성"""
        lines = []

        # 대표 분류 선택
        if query.target_regions:
            target = query.target_regions[0]
        else:
            regions = tx.get_unique_values(Fields.C1_NM)
            target = regions[0] if regions else None

        if target and Fields.C1_NM in tx.df.columns:
            trend_tx = tx.filter_by(Fields.C1_NM, target)
            growth = trend_tx.calculate_growth()

            lines.append(f"### {target} 추이")
            lines.append("")
            lines.append("| 기간 | 값 | 변동률 |")
            lines.append("|------|-----|--------|")

            for row in growth.to_dict("records"):
                period = row.get(Fields.PERIOD, "N/A")
                value = row.get(Fields.VALUE, 0)
                growth_pct = row.get("growth_pct", None)
                growth_str = f"{growth_pct:+.2f}%" if growth_pct is not None else "-"
                lines.append(f"| {period} | {value:,.0f} | {growth_str} |")

        return ReportSection(
            name="trend",
            title="📊 추이 분석",
            content="\n".join(lines),
        )

    def _gen_visualization(
        self, tx: KosisTransformer, query: UserQuery, output_dir: Optional[Path]
    ) -> ReportSection:
        """시각화 섹션 생성"""
        return ReportSection(
            name="visualization",
            title="시각화",
            content="네이티브 차트 생성은 기본 패키지에 포함되지 않습니다.",
            charts=[],
        )

        from .visualize import save_chart

        lines = []
        charts = []
        df = tx.df.copy()

        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        # 비교 유형에 따른 차트 선택
        if query.comparison_type == "temporal":
            # 라인 차트
            chart = (
                alt.Chart(df)
                .mark_line(point=True)
                .encode(
                    x=alt.X(f"{Fields.PERIOD}:N", title="기간"),
                    y=alt.Y(f"{Fields.VALUE}:Q", title="값"),
                    color=alt.Color(f"{Fields.C1_NM}:N")
                    if Fields.C1_NM in df.columns
                    else alt.value("steelblue"),
                )
                .properties(title="시계열 추이", width=600, height=400)
            )
            charts.append(chart)
            lines.append("📈 **시계열 추이 차트** 생성됨")

            if output_dir:
                result = save_chart(chart, "trend_chart.html", str(output_dir))
                lines.append(f"   → 저장: `{result['path']}`")

        elif query.comparison_type == "regional":
            # 막대 차트
            chart = (
                alt.Chart(df)
                .mark_bar()
                .encode(
                    x=alt.X(f"{Fields.C1_NM}:N", title="지역"),
                    y=alt.Y(f"{Fields.VALUE}:Q", title="값"),
                    color=alt.Color(f"{Fields.PERIOD}:N")
                    if Fields.PERIOD in df.columns
                    else alt.value("steelblue"),
                )
                .properties(title="지역별 비교", width=600, height=400)
            )
            charts.append(chart)
            lines.append("📊 **지역별 비교 차트** 생성됨")

            if output_dir:
                result = save_chart(chart, "comparison_chart.html", str(output_dir))
                lines.append(f"   → 저장: `{result['path']}`")

        elif query.comparison_type == "ranking":
            # 순위 막대 차트 (수평)
            ranked = tx.rank_by(Fields.VALUE, top_n=10)
            chart = (
                alt.Chart(ranked)
                .mark_bar()
                .encode(
                    x=alt.X(f"{Fields.VALUE}:Q", title="값"),
                    y=alt.Y(f"{Fields.C1_NM}:N", title="분류", sort="-x"),
                )
                .properties(title="상위 순위", width=600, height=400)
            )
            charts.append(chart)
            lines.append("🏆 **순위 차트** 생성됨")

            if output_dir:
                result = save_chart(chart, "ranking_chart.html", str(output_dir))
                lines.append(f"   → 저장: `{result['path']}`")

        return ReportSection(
            name="visualization",
            title="📊 시각화",
            content="\n".join(lines),
            charts=charts,
        )

    def _gen_insight(
        self, tx: KosisTransformer, query: UserQuery, output_dir: Optional[Path]
    ) -> ReportSection:
        """인사이트 섹션 생성"""
        lines = []

        # 자동 인사이트 생성
        lines.append("### 📍 주요 발견사항")
        lines.append("")

        if Fields.VALUE in tx.df.columns:
            # 최대/최소
            df = tx.df
            max_idx = df[Fields.VALUE].idxmax()
            min_idx = df[Fields.VALUE].idxmin()

            if pd.notna(max_idx):
                max_row = df.loc[max_idx]
                max_region = max_row.get(Fields.C1_NM, "N/A")
                max_period = max_row.get(Fields.PERIOD, "N/A")
                max_val = max_row[Fields.VALUE]
                lines.append(
                    f"1. **최대값**: {max_region} ({max_period}) - {max_val:,.0f}"
                )

            if pd.notna(min_idx):
                min_row = df.loc[min_idx]
                min_region = min_row.get(Fields.C1_NM, "N/A")
                min_period = min_row.get(Fields.PERIOD, "N/A")
                min_val = min_row[Fields.VALUE]
                lines.append(
                    f"2. **최소값**: {min_region} ({min_period}) - {min_val:,.0f}"
                )

        lines.append("")
        lines.append("### 💡 시사점")
        lines.append("")
        lines.append("- 데이터 기반의 추가 분석이 필요합니다.")
        lines.append("- 시계열 패턴 및 이상치 검토를 권장합니다.")

        return ReportSection(
            name="insight",
            title="💡 인사이트",
            content="\n".join(lines),
        )

    def create_llm_context(
        self,
        user_query: str,
        include_data_sample: bool = True,
        max_sample_rows: int = 20,
    ) -> Dict[str, Any]:
        """
        LLM에 제공할 구조화된 컨텍스트를 생성합니다.

        LLM이 데이터를 이해하고 유저 쿼리에 맞는 분석을 수행할 수 있도록
        필요한 모든 정보를 구조화하여 제공합니다.

        Args:
            user_query: 유저의 분석 요청
            include_data_sample: 샘플 데이터 포함 여부
            max_sample_rows: 샘플 데이터 최대 행 수

        Returns:
            LLM 컨텍스트 딕셔너리:
            {
                "user_query": "유저 쿼리",
                "parsed_query": {...},
                "data_info": {...},
                "available_dimensions": {...},
                "sample_data": [...],
                "suggested_analysis": [...]
            }
        """
        parsed = self.parse_user_query(user_query)

        context = {
            "user_query": user_query,
            "parsed_query": {
                "target_regions": parsed.target_regions,
                "target_periods": parsed.target_periods,
                "comparison_type": parsed.comparison_type,
                "analysis_depth": parsed.analysis_depth,
            },
            "data_info": {
                "total_records": len(self.data),
                "columns": list(self.tx.df.columns),
                "numeric_columns": list(
                    self.tx.df.select_dtypes(include=["number"]).columns
                ),
            },
            "available_dimensions": {
                "periods": self.tx.get_unique_values(Fields.PERIOD),
                "regions": self.tx.get_unique_values(Fields.C1_NM),
            },
        }

        if include_data_sample:
            sample = self.tx.df.head(max_sample_rows).to_dict("records")
            context["sample_data"] = sample

        # 분석 제안
        context["suggested_analysis"] = self._suggest_analysis(parsed)

        return context

    def _suggest_analysis(self, query: UserQuery) -> List[str]:
        """쿼리에 따른 분석 제안"""
        suggestions = []

        if query.comparison_type == "temporal":
            suggestions.append("시계열 추이 분석 (라인 차트)")
            suggestions.append("기간별 증감률 계산")
        elif query.comparison_type == "regional":
            suggestions.append("지역별 비교 분석 (막대 차트)")
            suggestions.append("지역 간 격차 분석")
        elif query.comparison_type == "ranking":
            suggestions.append("순위 분석 (상위/하위 N개)")
            suggestions.append("순위 변동 추적")

        if query.analysis_depth == "deep":
            suggestions.append("통계적 검정 수행")
            suggestions.append("이상치 탐지")

        return suggestions


def create_report(
    data: List[Dict[str, Any]],
    user_query: str,
    output_dir: Optional[str] = None,
) -> str:
    """
    리포트 생성 편의 함수.

    Args:
        data: KOSIS API 응답 데이터
        user_query: 유저의 분석 요청
        output_dir: 시각화 파일 저장 경로

    Returns:
        생성된 리포트 (Markdown 형식)

    Example:
        >>> from kosis_tools.report_generator import create_report
        >>> report = create_report(records, "서울 인구 분석")
        >>> print(report)
    """
    generator = ReportGenerator(data)
    return generator.generate(
        user_query=user_query,
        output_dir=Path(output_dir) if output_dir else None,
    )


def generate_html_report(
    data: List[Dict[str, Any]],
    user_query: str,
    output_path: Optional[str] = None,
    title: Optional[str] = None,
    save_debug_info: bool = False,
) -> str:
    """
    인터랙티브 HTML 보고서 생성 편의 함수.

    차트가 임베드된 단일 HTML 아티팩트를 생성합니다.

    Args:
        data: KOSIS API 응답 데이터
        user_query: 유저의 분석 요청
        output_path: HTML 파일 저장 경로 (None이면 HTML 문자열 반환)
        title: 보고서 제목
        save_debug_info: True이면 .debug.json 파일에 메타데이터 저장

    Returns:
        생성된 HTML 문자열 (output_path가 None일 때) 또는 저장 경로

    Example:
        >>> from kosis_tools.report_generator import generate_html_report
        >>> html = generate_html_report(
        ...     records, "서울 인구 분석", "report.html", save_debug_info=True
        ... )
    """
    generator = ReportGenerator(data)
    return generator.generate_html(
        user_query=user_query,
        output_path=output_path,
        title=title,
        save_debug_info=save_debug_info,
    )


def create_llm_prompt(
    data: List[Dict[str, Any]],
    user_query: str,
) -> str:
    """
    LLM 프롬프트 생성 편의 함수.

    Args:
        data: KOSIS API 응답 데이터
        user_query: 유저의 분석 요청

    Returns:
        LLM에 전달할 프롬프트 문자열
    """
    generator = ReportGenerator(data)
    context = generator.create_llm_context(user_query)

    prompt = f"""
다음 KOSIS 통계 데이터를 분석해주세요.

## 유저 요청
{user_query}

## 데이터 정보
- 총 레코드 수: {context["data_info"]["total_records"]}
- 기간: {context["available_dimensions"]["periods"][0]} ~ {context["available_dimensions"]["periods"][-1]}
- 지역 수: {len(context["available_dimensions"]["regions"])}개

## 파싱된 요청
- 대상 지역: {context["parsed_query"]["target_regions"] or "전체"}
- 대상 기간: {context["parsed_query"]["target_periods"] or "전체"}
- 비교 유형: {context["parsed_query"]["comparison_type"]}

## 샘플 데이터
{json.dumps(context.get("sample_data", [])[:5], ensure_ascii=False, indent=2)}

## 제안 분석
{chr(10).join("- " + s for s in context["suggested_analysis"])}

위 정보를 바탕으로 유저의 요청에 맞는 분석을 수행해주세요.
"""
    return prompt
