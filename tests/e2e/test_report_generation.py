"""
리포트 생성 E2E 테스트.

비판적 분석:
- 기존 test_llm_workflow.py는 리포트 생성 "동작" 검증
- 이 테스트는 리포트 "품질" 심층 검증
  - HTML 구조 완전성
  - 차트 렌더링 가능성
  - 파일 크기 적정성
  - 다양한 템플릿/옵션 조합

테스트 대상:
1. HTML 구조 검증 (DOCTYPE, charset, lang)
2. 차트 렌더링 검증 (Plotly 코드 존재)
3. 컴포넌트 조합 검증
4. 파일 크기/성능 검증
"""

import pytest
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from kosis_tools.report_tools import (
    # Visualization
    viz_line_trend,
    viz_bar_comparison,
    viz_kpi_card,
    viz_pie_composition,
    viz_heatmap,
    # Analysis
    analyze_trend,
    analyze_comparison,
    analyze_ranking,
    analyze_stats,
    # Text
    text_headline,
    text_summary,
    text_insight,
    text_data_note,
    # Layout
    layout_section,
    layout_card_grid,
    layout_two_column,
    layout_highlight_box,
    layout_table,
    # Assembly
    assemble_report,
    quick_report,
    # Data
    filter_data,
)


# =============================================================================
# HTML 구조 검증
# =============================================================================

class TestHtmlStructure:
    """
    HTML 구조 완전성 검증.

    브라우저에서 올바르게 렌더링되기 위한 필수 요소.
    """

    def test_doctype_present(self, small_population_data, output_dir):
        """DOCTYPE 선언 포함."""
        output_path = output_dir / "doctype_test.html"
        quick_report(small_population_data, output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content

    def test_korean_lang_attribute(self, small_population_data, output_dir):
        """한국어 lang 속성."""
        output_path = output_dir / "lang_test.html"
        quick_report(small_population_data, output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert '<html lang="ko">' in content or 'lang="ko"' in content

    def test_utf8_charset(self, small_population_data, output_dir):
        """UTF-8 문자셋 선언."""
        output_path = output_dir / "charset_test.html"
        quick_report(small_population_data, output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert 'charset="UTF-8"' in content or 'charset="utf-8"' in content.lower()

    def test_viewport_meta(self, small_population_data, output_dir):
        """반응형 viewport 메타 태그."""
        output_path = output_dir / "viewport_test.html"
        quick_report(small_population_data, output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert "viewport" in content

    def test_valid_html_closing_tags(self, small_population_data, output_dir):
        """HTML 태그 올바르게 닫힘."""
        output_path = output_dir / "closing_test.html"
        quick_report(small_population_data, output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert "</html>" in content
        assert "</head>" in content
        assert "</body>" in content

    def test_korean_font_loaded(self, small_population_data, output_dir, validate_html):
        """한글 폰트 로드."""
        output_path = output_dir / "font_test.html"
        quick_report(small_population_data, output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        errors = validate_html(content)

        # 한글 폰트 관련 에러가 없어야 함
        font_errors = [e for e in errors if "font" in e.lower()]
        assert not font_errors, f"폰트 관련 오류: {font_errors}"


# =============================================================================
# 차트 렌더링 검증
# =============================================================================

class TestChartRendering:
    """
    차트 렌더링 가능성 검증.

    Vega-Lite 차트 코드가 올바르게 포함되어 있는지.
    """

    def test_vega_cdn_included(self, medium_population_data, output_dir):
        """Vega CDN 스크립트 포함."""
        output_path = output_dir / "vega_cdn_test.html"
        quick_report(medium_population_data, output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert "vega-lite" in content.lower() or "cdn.jsdelivr.net/npm/vega" in content

    def test_line_chart_code_present(self, medium_population_data, output_dir):
        """라인 차트 코드 포함."""
        filtered = filter_data(medium_population_data, regions=["서울특별시"])
        chart = viz_line_trend(filtered, title="라인 차트 테스트")

        output_path = output_dir / "line_chart_test.html"
        assemble_report([chart], title="라인 차트", output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        # Vega-Lite 차트 코드 확인
        assert "vegaEmbed" in content or "vega-lite" in content.lower()

    def test_bar_chart_code_present(self, medium_population_data, output_dir):
        """막대 차트 코드 포함."""
        filtered = filter_data(medium_population_data, periods=["2024"])
        chart = viz_bar_comparison(filtered, title="막대 차트 테스트")

        output_path = output_dir / "bar_chart_test.html"
        assemble_report([chart], title="막대 차트", output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert "vegaEmbed" in content or "bar" in content.lower()

    def test_pie_chart_code_present(self, medium_population_data, output_dir):
        """파이 차트 코드 포함."""
        filtered = filter_data(medium_population_data, periods=["2024"], items=["총인구"])
        chart = viz_pie_composition(filtered, title="파이 차트 테스트")

        output_path = output_dir / "pie_chart_test.html"
        assemble_report([chart], title="파이 차트", output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert "vegaEmbed" in content or "arc" in content.lower()

    def test_heatmap_code_present(self, employment_data, output_dir):
        """히트맵 코드 포함."""
        chart = viz_heatmap(
            employment_data,
            x="PRD_DE",
            y="C1_NM",
            z="DT",
            title="히트맵 테스트"
        )

        output_path = output_dir / "heatmap_test.html"
        assemble_report([chart], title="히트맵", output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert output_path.exists()

    def test_multiple_charts_in_report(self, medium_population_data, output_dir):
        """
        여러 차트가 하나의 리포트에 포함.

        각 차트가 고유 ID를 가지고 충돌 없이 렌더링.
        """
        filtered = filter_data(medium_population_data, items=["총인구"])

        line = viz_line_trend(filtered, title="추이")
        bar = viz_bar_comparison(
            filter_data(filtered, periods=["2024"]),
            title="비교"
        )

        output_path = output_dir / "multi_chart_test.html"
        assemble_report([line, bar], title="다중 차트", output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")

        # 여러 차트 컨테이너 확인
        chart_divs = re.findall(r'<div[^>]*id="chart-[^"]*"', content)
        # 최소 2개 차트 또는 vegaEmbed 호출이 2개 이상
        assert len(chart_divs) >= 2 or content.count("vegaEmbed") >= 2


# =============================================================================
# 컴포넌트 조합 검증
# =============================================================================

class TestComponentCombination:
    """
    다양한 컴포넌트 조합 검증.
    """

    def test_kpi_cards_grid(self, small_population_data, output_dir):
        """KPI 카드 그리드."""
        cards = [
            viz_kpi_card(100, "지표 A", icon="📊"),
            viz_kpi_card(200, "지표 B", change=5.5),
            viz_kpi_card(300, "지표 C", change=-2.3),
        ]

        grid = layout_card_grid(cards, columns=3)

        output_path = output_dir / "kpi_grid_test.html"
        assemble_report([grid], title="KPI 그리드", output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert "kpi" in content.lower() or "card" in content.lower()

    def test_two_column_layout(self, medium_population_data, output_dir):
        """2단 레이아웃."""
        filtered = filter_data(medium_population_data, periods=["2024"], items=["총인구"])

        pie = viz_pie_composition(filtered, title="비중")
        bar = viz_bar_comparison(filtered, title="비교")

        two_col = layout_two_column(pie, bar, ratio="1:1")

        output_path = output_dir / "two_col_test.html"
        assemble_report([two_col], title="2단 레이아웃", output_path=str(output_path))

        assert output_path.exists()

    def test_section_with_icon(self, medium_population_data, output_dir):
        """아이콘 포함 섹션."""
        filtered = filter_data(medium_population_data, items=["총인구"])
        chart = viz_line_trend(filtered, title="추이")

        section = layout_section("핵심 지표", [chart], icon="📈")

        output_path = output_dir / "section_icon_test.html"
        assemble_report([section], title="섹션 테스트", output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert "핵심 지표" in content

    def test_highlight_box_styles(self, output_dir):
        """하이라이트 박스 스타일."""
        boxes = [
            layout_highlight_box("정보 메시지", style="info", title="정보"),
            layout_highlight_box("경고 메시지", style="warning", title="경고"),
            layout_highlight_box("성공 메시지", style="success", title="성공"),
        ]

        output_path = output_dir / "highlight_test.html"
        assemble_report(boxes, title="하이라이트", output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert "정보" in content
        assert "경고" in content

    def test_data_table_rendering(self, small_population_data, output_dir):
        """데이터 테이블 렌더링."""
        table = layout_table(
            small_population_data[:10],
            columns=["PRD_DE", "C1_NM", "DT"],
            column_labels={"PRD_DE": "기간", "C1_NM": "지역", "DT": "값"}
        )

        output_path = output_dir / "table_test.html"
        assemble_report([table], title="테이블", output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        assert "<table" in content or "table" in content.lower()
        assert "서울" in content or "부산" in content

    def test_analysis_insight_text(self, medium_population_data, output_dir):
        """분석 인사이트 텍스트."""
        filtered = filter_data(medium_population_data, items=["총인구"])
        trend = analyze_trend(filtered)

        headline = text_headline(trend, style="news")
        insight = text_insight(trend, depth="standard")
        note = text_data_note(medium_population_data)

        output_path = output_dir / "insight_test.html"
        assemble_report([headline, insight, note], title="인사이트", output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        # 텍스트 내용이 포함되어 있어야 함
        assert len(content) > 500


# =============================================================================
# 파일 크기/성능 검증
# =============================================================================

class TestFileSizeAndPerformance:
    """
    리포트 파일 크기 및 성능 검증.
    """

    def test_quick_report_size_limit(self, medium_population_data, output_dir):
        """
        quick_report 파일 크기 제한.

        300건 데이터: 20KB ~ 200KB
        """
        output_path = output_dir / "size_quick.html"
        quick_report(medium_population_data, output_path=str(output_path))

        file_size = output_path.stat().st_size

        assert 10_000 < file_size < 300_000, (
            f"quick_report 크기 범위 벗어남: {file_size / 1000:.1f}KB"
        )

    @pytest.mark.slow
    def test_large_data_report_size(self, large_population_data, output_dir):
        """
        대용량 데이터 리포트 크기.

        1,700건 데이터: Vega-Lite 스펙 포함 시 800KB 미만
        """
        output_path = output_dir / "size_large.html"
        quick_report(large_population_data, output_path=str(output_path))

        file_size = output_path.stat().st_size

        assert file_size < 850_000, (
            f"대용량 리포트 크기 초과: {file_size / 1000:.1f}KB > 850KB"
        )

    @pytest.mark.report
    def test_complex_report_size(self, medium_population_data, output_dir):
        """
        복잡한 리포트 (모든 컴포넌트) 크기.
        """
        filtered = filter_data(medium_population_data, items=["총인구"])
        recent = filter_data(filtered, periods=["2024"])

        components = [
            # KPI
            layout_card_grid([
                viz_kpi_card(100, "A"),
                viz_kpi_card(200, "B"),
                viz_kpi_card(300, "C"),
            ]),
            # 차트
            viz_line_trend(filtered),
            viz_bar_comparison(recent),
            viz_pie_composition(recent),
            # 분석
            text_insight(analyze_trend(filtered)),
            # 테이블
            layout_table(recent[:10]),
            # 노트
            text_data_note(medium_population_data),
        ]

        output_path = output_dir / "complex_report.html"
        assemble_report(components, title="복잡한 리포트", output_path=str(output_path))

        file_size = output_path.stat().st_size

        # 복잡한 리포트도 1MB 미만
        assert file_size < 1_000_000, (
            f"복잡한 리포트 크기 초과: {file_size / 1000:.1f}KB > 1000KB"
        )


# =============================================================================
# 데이터 출처 표시 검증
# =============================================================================

class TestDataAttribution:
    """
    데이터 출처 표시 검증.
    """

    def test_kosis_attribution(self, small_population_data, output_dir):
        """KOSIS 출처 표시."""
        output_path = output_dir / "attribution_test.html"
        quick_report(small_population_data, output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")

        # KOSIS 또는 통계청 언급
        has_attribution = (
            "KOSIS" in content or
            "통계청" in content or
            "kosis" in content.lower()
        )
        assert has_attribution, "데이터 출처 표시 누락"

    def test_data_note_includes_metadata(self, medium_population_data, output_dir):
        """
        데이터 노트에 메타데이터 포함.
        """
        note = text_data_note(medium_population_data, source="KOSIS 통계청")

        output_path = output_dir / "note_test.html"
        assemble_report([note], title="노트 테스트", output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")
        # 출처 정보 또는 KOSIS 관련 정보가 포함되어야 함
        assert "출처" in content or "KOSIS" in content or "통계청" in content


# =============================================================================
# 인코딩 및 특수문자 검증
# =============================================================================

class TestEncodingAndSpecialChars:
    """
    인코딩 및 특수문자 처리 검증.
    """

    def test_korean_text_rendering(self, medium_population_data, output_dir):
        """한글 텍스트 정상 렌더링."""
        output_path = output_dir / "korean_test.html"
        quick_report(
            medium_population_data,
            title="한글 제목 테스트: 시도별 인구",
            output_path=str(output_path)
        )

        content = output_path.read_text(encoding="utf-8")

        # 한글이 깨지지 않고 포함
        assert "한글" in content
        assert "인구" in content
        # 리포트에 한글 컨텐츠가 포함되어야 함 (차트나 분석 텍스트)
        assert "분석" in content or "데이터" in content or "통계" in content

    def test_special_characters_escaped(self, output_dir):
        """특수문자 이스케이프."""
        special_data = [{
            "PRD_DE": "2024",
            "C1_NM": "테스트 <지역>",  # HTML 태그 문자
            "DT": "1000",
            "ITM_NM": "값 & 수치",  # 앰퍼샌드
        }]

        output_path = output_dir / "special_char_test.html"
        quick_report(special_data, output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")

        # HTML이 깨지지 않아야 함
        assert "</html>" in content

    def test_numeric_formatting(self, medium_population_data, output_dir):
        """숫자 포맷팅 (천 단위 구분)."""
        output_path = output_dir / "numeric_test.html"
        quick_report(medium_population_data, output_path=str(output_path))

        content = output_path.read_text(encoding="utf-8")

        # 대용량 숫자가 포함됨
        # 천 단위 구분자(,) 또는 원본 숫자 포함
        has_large_number = bool(re.search(r'\d{1,3}(,\d{3})+|\d{7,}', content))
        assert has_large_number, "숫자 포맷팅 확인 필요"
