"""
스토리 기반 리포트 템플릿 시스템.

100개 KOSIS 리포트에서 추출한 성공 패턴을 템플릿화.
MCP 클라이언트에게 토큰 효율적으로 가이드 제공.

설계 원칙:
- 템플릿 ID로 참조 (전체 내용 전송 X)
- 필요 시에만 상세 정보 제공
- 검증 실패 시 맞춤 가이드
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class ChartType(Enum):
    """차트 유형."""
    LINE = "line"
    BAR = "bar"
    GROUPED_BAR = "grouped_bar"
    STACKED_BAR = "stacked_bar"
    PIE = "pie"
    DONUT = "donut"
    SCATTER = "scatter"
    AREA = "area"
    HEATMAP = "heatmap"


class SectionType(Enum):
    """리포트 섹션 유형."""
    HOOK = "hook"           # 충격적 숫자로 시작
    CONTEXT = "context"     # 배경/맥락 설명
    STAT_CARDS = "stats"    # 핵심 수치 카드
    CHART = "chart"         # 시각화
    INSIGHT = "insight"     # 인사이트/해석
    TABLE = "table"         # 데이터 테이블
    BREAKDOWN = "breakdown" # 세부 분석
    COMPARISON = "comparison"  # 비교
    FORECAST = "forecast"   # 전망/시사점


@dataclass
class SectionSpec:
    """섹션 명세."""
    type: SectionType
    title: str
    description: str
    chart_type: Optional[ChartType] = None
    required: bool = True


@dataclass
class StoryTemplate:
    """스토리 템플릿."""
    id: str
    name: str
    description: str
    when_to_use: str
    sections: List[SectionSpec]
    example_topics: List[str]
    golden_example: Optional[str] = None  # 골든 리포트 파일명

    def to_brief(self) -> Dict[str, Any]:
        """토큰 효율적인 요약 반환 (리스트용)."""
        return {
            "id": self.id,
            "name": self.name,
            "when": self.when_to_use,
            "sections": len(self.sections),
        }

    def to_guide(self) -> Dict[str, Any]:
        """상세 가이드 반환 (선택 후)."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "structure": [
                {
                    "step": i + 1,
                    "type": s.type.value,
                    "title": s.title,
                    "desc": s.description,
                    "chart": s.chart_type.value if s.chart_type else None,
                }
                for i, s in enumerate(self.sections)
            ],
            "examples": self.example_topics,
            "code_pattern": self._generate_code_pattern(),
        }

    def _generate_code_pattern(self) -> str:
        """코드 패턴 생성."""
        lines = ["# 데이터 준비", "df = prepare_data(data, numeric_fields=['DT'])", ""]

        chart_idx = 1
        for section in self.sections:
            if section.type == SectionType.STAT_CARDS:
                lines.append("# 통계 카드")
                lines.append("stats = [{'label': '핵심지표', 'value': f'{df[\"DT\"].sum():,.0f}', 'unit': '명'}]")
                lines.append("")
            elif section.type == SectionType.CHART and section.chart_type:
                lines.append(f"# 차트 {chart_idx}: {section.title}")
                if section.chart_type == ChartType.LINE:
                    lines.append(f"chart{chart_idx} = alt.Chart(df).mark_line(point=True).encode(")
                    lines.append("    x='PRD_DE:N', y='DT:Q', color='C1_NM:N'")
                    lines.append(f").properties(title='{section.title}')")
                elif section.chart_type == ChartType.BAR:
                    lines.append(f"chart{chart_idx} = alt.Chart(df).mark_bar().encode(")
                    lines.append("    x=alt.X('C1_NM:N', sort='-y'), y='DT:Q'")
                    lines.append(f").properties(title='{section.title}')")
                lines.append("")
                chart_idx += 1
            elif section.type == SectionType.INSIGHT:
                lines.append("# 인사이트")
                lines.append(f"insight = '{section.description}'")
                lines.append("")

        lines.append("# 리포트 조립")
        lines.append("sections = [...]  # 위에서 만든 요소들 조합")
        lines.append("return save_report(build_report('제목', sections), 'report')")

        return "\n".join(lines)


# ============================================================================
# 템플릿 정의 - 100개 리포트에서 추출한 골든 패턴
# ============================================================================

TEMPLATES: Dict[str, StoryTemplate] = {}


def _register(template: StoryTemplate) -> StoryTemplate:
    """템플릿 등록."""
    TEMPLATES[template.id] = template
    return template


# 1. 트렌드 분석 템플릿
TREND_ANALYSIS = _register(StoryTemplate(
    id="trend",
    name="트렌드 분석",
    description="시계열 데이터의 변화 추이를 분석. 과거→현재→미래 흐름 전달.",
    when_to_use="연도별/월별 데이터가 있고, 시간에 따른 변화가 핵심일 때",
    sections=[
        SectionSpec(SectionType.HOOK, "충격 수치", "가장 최근 또는 극단적인 수치로 시작"),
        SectionSpec(SectionType.STAT_CARDS, "핵심 지표", "3-4개 KPI 카드"),
        SectionSpec(SectionType.CHART, "전체 추이", "시계열 트렌드", ChartType.LINE),
        SectionSpec(SectionType.INSIGHT, "트렌드 해석", "상승/하락 원인 분석"),
        SectionSpec(SectionType.CHART, "세부 분해", "카테고리별 비교", ChartType.GROUPED_BAR),
        SectionSpec(SectionType.FORECAST, "전망", "향후 예측 및 시사점"),
    ],
    example_topics=["출산율", "GDP 성장률", "실업률", "물가지수", "수출입"],
    golden_example="report_001_20251215_fertility_rate.html",
))


# 2. 비교 분석 템플릿
COMPARISON = _register(StoryTemplate(
    id="compare",
    name="비교 분석",
    description="여러 항목/지역/그룹 간 차이를 비교. 순위와 격차 강조.",
    when_to_use="지역별, 연령별, 카테고리별 비교가 핵심일 때",
    sections=[
        SectionSpec(SectionType.STAT_CARDS, "Top 3 순위", "상위 3개 항목 강조"),
        SectionSpec(SectionType.CHART, "전체 비교", "막대 그래프로 순위", ChartType.BAR),
        SectionSpec(SectionType.INSIGHT, "격차 분석", "1위와 최하위 차이, 중간값 등"),
        SectionSpec(SectionType.CHART, "그룹 비교", "그룹별 세부 비교", ChartType.GROUPED_BAR),
        SectionSpec(SectionType.TABLE, "상세 데이터", "전체 데이터 테이블"),
    ],
    example_topics=["지역별 인구", "산업별 매출", "국가별 순위", "연령별 분포"],
    golden_example="report_005_20251215_elderly.html",
))


# 3. 구성 분석 템플릿
COMPOSITION = _register(StoryTemplate(
    id="composition",
    name="구성 분석",
    description="전체를 100%로 보고 각 부분의 비율 분석. 파이/도넛 활용.",
    when_to_use="전체 대비 비율, 점유율, 구성비가 핵심일 때",
    sections=[
        SectionSpec(SectionType.STAT_CARDS, "전체 규모", "총합 수치"),
        SectionSpec(SectionType.CHART, "구성 비율", "파이/도넛 차트", ChartType.DONUT),
        SectionSpec(SectionType.INSIGHT, "주요 구성", "상위 항목이 차지하는 비율"),
        SectionSpec(SectionType.CHART, "구성 변화", "연도별 구성비 변화", ChartType.STACKED_BAR),
    ],
    example_topics=["예산 구성", "에너지원 비율", "산업 구조", "인구 구성"],
    golden_example="report_063_20251215_budget.html",
))


# 4. 상관관계 분석 템플릿
CORRELATION = _register(StoryTemplate(
    id="correlation",
    name="상관관계 분석",
    description="두 변수 간의 관계 분석. 산점도와 추세선 활용.",
    when_to_use="변수 간 관계, 원인-결과, 상관성 분석이 핵심일 때",
    sections=[
        SectionSpec(SectionType.CONTEXT, "가설", "분석하고자 하는 관계 설명"),
        SectionSpec(SectionType.CHART, "상관관계", "산점도", ChartType.SCATTER),
        SectionSpec(SectionType.INSIGHT, "관계 해석", "상관계수, 패턴 설명"),
        SectionSpec(SectionType.CHART, "보조 분석", "각 변수의 분포", ChartType.BAR),
    ],
    example_topics=["소득-소비", "교육-취업", "인구-주택가격"],
))


# 5. 대시보드 템플릿 (종합)
DASHBOARD = _register(StoryTemplate(
    id="dashboard",
    name="종합 대시보드",
    description="여러 지표를 한눈에 보여주는 종합 현황판.",
    when_to_use="여러 관점의 데이터를 종합적으로 보여줄 때",
    sections=[
        SectionSpec(SectionType.STAT_CARDS, "KPI 카드", "4-6개 핵심 지표"),
        SectionSpec(SectionType.CHART, "주요 트렌드", "가장 중요한 시계열", ChartType.LINE),
        SectionSpec(SectionType.CHART, "비교 현황", "카테고리별 비교", ChartType.BAR),
        SectionSpec(SectionType.CHART, "구성 비율", "비율 시각화", ChartType.DONUT),
        SectionSpec(SectionType.TABLE, "상세 데이터", "전체 데이터"),
        SectionSpec(SectionType.INSIGHT, "종합 인사이트", "핵심 발견점 요약"),
    ],
    example_topics=["월간 현황", "분기 리포트", "연간 종합"],
    golden_example="report_017_20251215_healthcare.html",
))


# 6. 순위/랭킹 템플릿
RANKING = _register(StoryTemplate(
    id="ranking",
    name="순위/랭킹",
    description="Top N 형식의 순위 분석. 1위 강조.",
    when_to_use="순위, 베스트/워스트, Top 10 등이 핵심일 때",
    sections=[
        SectionSpec(SectionType.HOOK, "1위 강조", "1위 항목 대형 표시"),
        SectionSpec(SectionType.CHART, "전체 순위", "수평 막대 그래프", ChartType.BAR),
        SectionSpec(SectionType.INSIGHT, "순위 변동", "전년 대비 순위 변화"),
        SectionSpec(SectionType.TABLE, "상세 순위", "전체 순위표"),
    ],
    example_topics=["기업 순위", "지역별 순위", "인기 순위"],
))


# ============================================================================
# 토큰 효율적 API
# ============================================================================

def get_template_list() -> List[Dict[str, Any]]:
    """
    템플릿 목록 반환 (토큰 효율적).

    Returns:
        [{"id": "trend", "name": "트렌드 분석", "when": "...", "sections": 6}, ...]
    """
    return [t.to_brief() for t in TEMPLATES.values()]


def get_template_guide(template_id: str) -> Optional[Dict[str, Any]]:
    """
    특정 템플릿의 상세 가이드 반환.

    Args:
        template_id: 템플릿 ID (예: "trend", "compare")

    Returns:
        상세 가이드 딕셔너리 또는 None
    """
    template = TEMPLATES.get(template_id)
    return template.to_guide() if template else None


def recommend_template(data_signature: Dict[str, Any]) -> Dict[str, Any]:
    """
    데이터 시그니처 기반 템플릿 추천.

    Args:
        data_signature: 데이터 시그니처 (fields, total_records 등)

    Returns:
        {"recommended": "trend", "reason": "...", "alternatives": [...]}
    """
    fields = data_signature.get("fields", {})
    record_count = data_signature.get("total_records", 0)

    # 시계열 감지 (PRD_DE 필드 존재)
    has_time = "PRD_DE" in fields

    # 지역 데이터 감지
    has_region = "C1_NM" in fields
    region_samples = fields.get("C1_NM", {}).get("sample_values", [])
    is_regional = any("시" in v or "도" in v for v in region_samples)

    # 다중 카테고리 감지
    category_count = fields.get("C1_NM", {}).get("unique_count", 1)

    # 추천 로직
    if has_time and category_count > 1:
        return {
            "recommended": "trend",
            "reason": "시계열 데이터 + 다중 카테고리 → 트렌드 비교 적합",
            "alternatives": ["compare", "dashboard"],
        }
    elif has_time:
        return {
            "recommended": "trend",
            "reason": "시계열 데이터 → 트렌드 분석 적합",
            "alternatives": ["dashboard"],
        }
    elif is_regional or category_count > 5:
        return {
            "recommended": "compare",
            "reason": "지역/카테고리 데이터 → 비교 분석 적합",
            "alternatives": ["ranking", "dashboard"],
        }
    elif category_count <= 5 and record_count < 20:
        return {
            "recommended": "ranking",
            "reason": "소수 항목 → 순위/랭킹 적합",
            "alternatives": ["compare"],
        }
    else:
        return {
            "recommended": "dashboard",
            "reason": "종합 데이터 → 대시보드 적합",
            "alternatives": ["trend", "compare"],
        }


# ============================================================================
# 계층적 단계별 가이드 시스템
# ============================================================================

def get_template_step(template_id: str, step: int) -> Optional[Dict[str, Any]]:
    """
    템플릿의 특정 단계 가이드만 반환 (토큰 최적화).

    Args:
        template_id: 템플릿 ID
        step: 단계 번호 (1부터 시작)

    Returns:
        {
            "current_step": {...},      # 현재 단계 상세
            "next_preview": "...",      # 다음 단계 예고 (짧게)
            "progress": "2/6",          # 진행률
            "code_hint": "..."          # 이 단계 코드 힌트
        }
    """
    template = TEMPLATES.get(template_id)
    if not template:
        return None

    sections = template.sections
    if step < 1 or step > len(sections):
        return None

    current = sections[step - 1]
    has_next = step < len(sections)

    result = {
        "template": template_id,
        "progress": f"{step}/{len(sections)}",
        "current_step": {
            "step": step,
            "type": current.type.value,
            "title": current.title,
            "description": current.description,
            "chart_type": current.chart_type.value if current.chart_type else None,
            "required": current.required,
        },
        "code_hint": _get_step_code_hint(current),
    }

    if has_next:
        next_section = sections[step]
        result["next_preview"] = f"다음: {next_section.title} ({next_section.type.value})"
    else:
        result["next_preview"] = "마지막 단계입니다. 리포트를 완성하세요."
        result["finalize_hint"] = "return save_report(build_report(title, sections), 'report_name')"

    return result


def _get_step_code_hint(section: SectionSpec) -> str:
    """단계별 코드 힌트 생성."""
    hints = {
        SectionType.HOOK: '''# HOOK: 충격적인 숫자
latest = df[df["PRD_DE"] == df["PRD_DE"].max()]["DT"].values[0]
hook = {"type": "insight", "content": f"<h2>{latest:,.0f}</h2><p>최신 수치</p>"}''',

        SectionType.STAT_CARDS: '''# 통계 카드 (3-4개)
stats = [
    {"label": "최신값", "value": f"{latest:,.0f}", "unit": "명"},
    {"label": "증감률", "value": f"{change:+.1f}%", "trend": "up" if change > 0 else "down"},
]
section = {"type": "stats", "items": stats}''',

        SectionType.CHART: '''# 차트 생성
chart = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X("PRD_DE:N", title="연도"),
    y=alt.Y("DT:Q", title="값", axis=alt.Axis(format=",")),
    color=alt.Color("C1_NM:N", title="분류")
).properties(title="차트 제목", width=600, height=400)
section = {"type": "chart", "vega_spec": chart.to_dict(), "title": "...", "description": "..."}''',

        SectionType.INSIGHT: '''# 인사이트 박스
insight_text = """
- 핵심 발견 1
- 핵심 발견 2
- 시사점
"""
section = {"type": "insight", "content": insight_text, "title": "주요 인사이트"}''',

        SectionType.TABLE: '''# 데이터 테이블
section = {"type": "table", "html": to_table_html(df.head(10), title="상세 데이터")}''',

        SectionType.BREAKDOWN: '''# 세부 분해 (그룹별 비교)
chart = alt.Chart(df).mark_bar().encode(
    x=alt.X("C1_NM:N", sort="-y"),
    y="sum(DT):Q",
    color="C1_NM:N"
).properties(title="카테고리별 비교")
section = {"type": "chart", "vega_spec": chart.to_dict()}''',

        SectionType.FORECAST: '''# 전망/시사점
forecast = {"type": "insight", "content": "향후 전망: ...", "title": "시사점"}''',

        SectionType.COMPARISON: '''# 비교 차트
chart = alt.Chart(df).mark_bar().encode(
    y=alt.Y("C1_NM:N", sort="-x"),
    x="DT:Q"
).properties(title="비교")''',

        SectionType.CONTEXT: '''# 배경 설명
context = {"type": "text", "content": "<p>분석 배경과 목적...</p>"}''',
    }
    return hints.get(section.type, "# 해당 섹션 구현")


def get_element_guide(element_type: str) -> Dict[str, Any]:
    """
    특정 요소(차트, 인사이트 등)의 상세 가이드.

    Args:
        element_type: "line_chart", "bar_chart", "stat_cards", "insight_box", etc.

    Returns:
        해당 요소의 상세 가이드
    """
    guides = {
        "line_chart": {
            "when": "시계열 데이터, 트렌드 분석",
            "must_have": ["제목", "축 라벨", "숫자 포맷(,)", "범례"],
            "code": '''alt.Chart(df).mark_line(point=True).encode(
    x=alt.X("PRD_DE:N", title="연도"),
    y=alt.Y("DT:Q", title="값 (단위)", axis=alt.Axis(format=",")),
    color=alt.Color("C1_NM:N", legend=alt.Legend(title="분류")),
    tooltip=["PRD_DE", "C1_NM", alt.Tooltip("DT:Q", format=",")]
).properties(title="명확한 제목", width=600, height=400)''',
            "avoid": ["너무 많은 시리즈 (5개 이하)", "축 라벨 누락", "포맷 없는 큰 숫자"],
        },
        "bar_chart": {
            "when": "비교, 순위, 카테고리별 분석",
            "must_have": ["정렬(sort)", "축 라벨", "숫자 포맷"],
            "code": '''alt.Chart(df).mark_bar().encode(
    x=alt.X("C1_NM:N", sort="-y", title="분류"),
    y=alt.Y("DT:Q", title="값", axis=alt.Axis(format=",")),
    color=alt.value("#667eea")  # 단색 또는 조건부
).properties(title="비교 차트", width=600, height=400)''',
            "avoid": ["정렬 안 함", "너무 많은 막대 (15개 이하)", "3D 효과"],
        },
        "stat_cards": {
            "when": "핵심 KPI, 요약 수치",
            "must_have": ["3-4개", "단위", "변화율/트렌드"],
            "code": '''stats = [
    {"label": "총합", "value": f"{total:,.0f}", "unit": "명"},
    {"label": "평균", "value": f"{avg:,.1f}", "unit": "명"},
    {"label": "증감", "value": f"{change:+.1f}%", "trend": "up"},
]
{"type": "stats", "items": stats}''',
            "avoid": ["너무 많은 카드 (6개 이하)", "단위 누락", "복잡한 계산식 표시"],
        },
        "insight_box": {
            "when": "핵심 발견, 해석, 결론",
            "must_have": ["구체적 수치 포함", "원인/결과 설명", "간결함"],
            "code": '''{"type": "insight", "content": """
• 2023년 출생아 수 23만 명으로 역대 최저
• 전년 대비 8.3% 감소 (약 2만 명↓)
• 수도권 출산율이 비수도권의 70% 수준
""", "title": "핵심 인사이트"}''',
            "avoid": ["모호한 표현", "숫자 없는 설명", "너무 긴 문장"],
        },
        "donut_chart": {
            "when": "비율, 점유율, 구성비",
            "must_have": ["5개 이하 항목", "퍼센트 표시", "합계=100%"],
            "code": '''alt.Chart(df).mark_arc(innerRadius=50).encode(
    theta="DT:Q",
    color=alt.Color("C1_NM:N", legend=alt.Legend(title="구성")),
    tooltip=["C1_NM", alt.Tooltip("DT:Q", format=".1%")]
).properties(title="구성 비율", width=400, height=400)''',
            "avoid": ["5개 초과 (기타로 묶기)", "3D 파이", "작은 조각들"],
        },
    }
    return guides.get(element_type, {"error": f"Unknown element: {element_type}"})


def get_next_recommendation(
    template_id: str,
    completed_steps: List[int],
    current_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    현재 진행 상황 기반 다음 단계 추천.

    Args:
        template_id: 템플릿 ID
        completed_steps: 완료된 단계 번호 목록
        current_data: 현재까지 생성된 데이터 (선택)

    Returns:
        다음 단계 가이드 + 맞춤 추천
    """
    template = TEMPLATES.get(template_id)
    if not template:
        return {"error": "Template not found"}

    total_steps = len(template.sections)
    next_step = max(completed_steps) + 1 if completed_steps else 1

    if next_step > total_steps:
        return {
            "status": "complete",
            "message": "모든 단계 완료! 리포트를 저장하세요.",
            "finalize": "return save_report(build_report(title, all_sections), 'report')",
        }

    step_guide = get_template_step(template_id, next_step)

    # 맞춤 추천 추가
    if current_data:
        step_guide["personalized_tip"] = _get_personalized_tip(
            template.sections[next_step - 1],
            current_data,
        )

    return step_guide


def _get_personalized_tip(section: SectionSpec, data: Dict[str, Any]) -> str:
    """데이터 기반 맞춤 팁."""
    fields = data.get("fields", {})

    if section.type == SectionType.CHART:
        if "C1_NM" in fields:
            unique_count = fields["C1_NM"].get("unique_count", 0)
            if unique_count > 10:
                return f"카테고리가 {unique_count}개로 많습니다. 상위 10개만 표시하거나 그룹화하세요."
            elif unique_count <= 3:
                return "카테고리가 적어 색상으로 명확히 구분됩니다."
    elif section.type == SectionType.STAT_CARDS:
        return "가장 최근 값, 변화율, 최대/최소를 카드로 만드세요."

    return ""


# ============================================================================
# 차트 선택 가이드 (토큰 효율적)
# ============================================================================

CHART_GUIDE = {
    "time_series": {
        "best": "line",
        "alt": ["area"],
        "avoid": ["pie", "donut"],
        "tip": "시간축은 X, 값은 Y. 여러 시리즈는 color로 구분.",
    },
    "comparison": {
        "best": "bar",
        "alt": ["grouped_bar"],
        "avoid": ["line", "scatter"],
        "tip": "정렬 필수 (sort='-y'). 카테고리가 많으면 수평 막대.",
    },
    "proportion": {
        "best": "donut",
        "alt": ["pie", "stacked_bar"],
        "avoid": ["line", "scatter"],
        "tip": "5개 이하 카테고리. 그 이상은 '기타'로 묶기.",
    },
    "relationship": {
        "best": "scatter",
        "alt": ["heatmap"],
        "avoid": ["pie", "bar"],
        "tip": "X, Y 모두 연속형 변수. 추세선 추가 권장.",
    },
    "distribution": {
        "best": "bar",
        "alt": ["area"],
        "avoid": ["pie"],
        "tip": "히스토그램 스타일. 구간 설정 중요.",
    },
}


def get_chart_recommendation(analysis_type: str) -> Dict[str, Any]:
    """
    분석 유형에 따른 차트 추천.

    Args:
        analysis_type: "time_series", "comparison", "proportion", "relationship", "distribution"

    Returns:
        차트 추천 정보
    """
    return CHART_GUIDE.get(analysis_type, CHART_GUIDE["comparison"])
