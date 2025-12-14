"""
KOSIS 데이터 시각화 모듈.

이 모듈은 KOSIS API에서 조회한 통계 데이터를 시각화하는 기능을 제공합니다.
Plotly 기반으로 인터랙티브 차트를 생성하며, 한글이 깨지지 않도록 처리합니다.

주요 기능:
    - 시계열 라인 차트: 기간별 데이터 추이
    - 막대 차트: 분류별 비교
    - 파이 차트: 구성비 시각화
    - 지역별 히트맵: 지역 데이터 비교

Example:
    기본 사용:
    >>> from kosis_tools import StatisticsData
    >>> from kosis_tools.visualize import KosisVisualizer
    >>>
    >>> data_client = StatisticsData()
    >>> records = data_client.get_data("101", "DT_1B040A3", "2020", "2023", prd_se="Y")
    >>>
    >>> viz = KosisVisualizer()
    >>> fig = viz.line_chart(records, x="PRD_DE", y="DT", color="C1_NM", title="인구 추이")
    >>> fig.show()

Note:
    - 모든 차트는 한글 폰트가 기본 적용됩니다.
    - HTML, PNG, PDF 등 다양한 형식으로 저장 가능합니다.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

logger = logging.getLogger(__name__)

# 한글 폰트 설정 (시스템 폰트 우선순위)
KOREAN_FONTS = [
    "Malgun Gothic",      # Windows
    "맑은 고딕",          # Windows (한글명)
    "Apple SD Gothic Neo", # macOS
    "AppleGothic",        # macOS 대체
    "NanumGothic",        # 나눔고딕
    "나눔고딕",           # 나눔고딕 (한글명)
    "Noto Sans KR",       # Google Noto
    "sans-serif",         # 기본 대체
]

FONT_FAMILY = ", ".join(KOREAN_FONTS)


class KosisVisualizer:
    """
    KOSIS 데이터 시각화 클래스.

    KOSIS API에서 조회한 데이터를 Plotly를 사용하여 시각화합니다.
    한글 폰트가 기본 적용되어 한글이 깨지지 않습니다.

    Attributes:
        font_family: 사용할 폰트 패밀리 (기본: 한글 폰트 목록)
        template: Plotly 테마 (기본: "plotly_white")
        default_height: 기본 차트 높이 (기본: 500)
        default_width: 기본 차트 너비 (기본: 900)

    Example:
        >>> viz = KosisVisualizer()
        >>> fig = viz.line_chart(data, x="PRD_DE", y="DT", title="데이터 추이")
        >>> fig.show()
    """

    def __init__(
        self,
        font_family: str = FONT_FAMILY,
        template: str = "plotly_white",
        default_height: int = 500,
        default_width: int = 900,
    ):
        """
        시각화 클래스를 초기화합니다.

        Args:
            font_family: 폰트 패밀리 문자열. 콤마로 구분된 폰트 목록.
                        기본값은 한글 폰트 우선순위 목록.
            template: Plotly 테마. "plotly", "plotly_white", "plotly_dark",
                     "ggplot2", "seaborn", "simple_white" 등.
            default_height: 기본 차트 높이 (픽셀)
            default_width: 기본 차트 너비 (픽셀)
        """
        self.font_family = font_family
        self.template = template
        self.default_height = default_height
        self.default_width = default_width

    def _apply_korean_layout(
        self,
        fig: go.Figure,
        title: Optional[str] = None,
        xaxis_title: Optional[str] = None,
        yaxis_title: Optional[str] = None,
        height: Optional[int] = None,
        width: Optional[int] = None,
    ) -> go.Figure:
        """
        한글 폰트 및 공통 레이아웃을 적용합니다.

        Args:
            fig: Plotly Figure 객체
            title: 차트 제목
            xaxis_title: X축 제목
            yaxis_title: Y축 제목
            height: 차트 높이
            width: 차트 너비

        Returns:
            레이아웃이 적용된 Figure 객체
        """
        fig.update_layout(
            font=dict(family=self.font_family),
            title=dict(
                text=title,
                font=dict(size=18, family=self.font_family),
            ) if title else None,
            xaxis_title=xaxis_title,
            yaxis_title=yaxis_title,
            height=height or self.default_height,
            width=width or self.default_width,
            template=self.template,
            legend=dict(
                font=dict(family=self.font_family),
            ),
            hoverlabel=dict(
                font=dict(family=self.font_family),
            ),
        )
        # Binary encoding 방지를 위해 native Python 타입으로 변환
        return self._ensure_native_types(fig)

    def _ensure_native_types(self, fig: go.Figure) -> go.Figure:
        """
        Figure의 trace 데이터를 native Python 타입으로 변환.

        Plotly 6.x의 binary encoding(bdata)이 CDN plotly.js와 호환되지 않는
        문제를 해결합니다. numpy array를 plain Python list로 변환한
        새로운 Figure를 반환합니다.

        Args:
            fig: 변환할 Plotly Figure 객체

        Returns:
            데이터가 native Python 타입으로 변환된 새 Figure 객체
        """
        # 각 trace의 데이터를 추출하고 list로 변환
        new_data = []
        for trace in fig.data:
            trace_dict = {}

            # trace 유형
            trace_dict['type'] = trace.type

            # 기본 속성들 복사
            for prop in ['name', 'orientation', 'showlegend', 'legendgroup',
                         'marker', 'line', 'textposition', 'mode', 'fill',
                         'hoverinfo', 'hovertemplate', 'texttemplate',
                         'customdata', 'meta', 'hoverlabel']:
                if hasattr(trace, prop):
                    val = getattr(trace, prop)
                    if val is not None:
                        if hasattr(val, 'to_plotly_json'):
                            trace_dict[prop] = val.to_plotly_json()
                        else:
                            trace_dict[prop] = val

            # 데이터 속성들을 list로 변환
            for attr in ['x', 'y', 'z', 'values', 'text', 'labels', 'ids', 'parents']:
                if hasattr(trace, attr):
                    val = getattr(trace, attr)
                    if val is not None:
                        if hasattr(val, 'tolist'):
                            trace_dict[attr] = val.tolist()
                        else:
                            trace_dict[attr] = val

            new_data.append(trace_dict)

        # 레이아웃 복사 후 새 Figure 생성
        layout_dict = fig.layout.to_plotly_json()
        return go.Figure(data=new_data, layout=layout_dict)

    def line_chart(
        self,
        data: List[Dict[str, Any]],
        x: str = "PRD_DE",
        y: str = "DT",
        color: Optional[str] = None,
        title: Optional[str] = None,
        xaxis_title: Optional[str] = None,
        yaxis_title: Optional[str] = None,
        height: Optional[int] = None,
        width: Optional[int] = None,
        markers: bool = True,
        line_shape: str = "linear",
        labels: Optional[Dict[str, str]] = None,
    ) -> go.Figure:
        """
        시계열 라인 차트를 생성합니다.

        기간별 데이터 추이를 시각화하는 데 적합합니다.
        여러 그룹(지역, 항목 등)을 색상으로 구분할 수 있습니다.

        Args:
            data: KOSIS API 응답 데이터 (레코드 리스트)
            x: X축 필드명 (기본: "PRD_DE" - 기간)
            y: Y축 필드명 (기본: "DT" - 데이터 값)
            color: 색상 구분 필드명 (선택, 예: "C1_NM" - 분류명)
            title: 차트 제목
            xaxis_title: X축 제목 (labels로 지정 권장)
            yaxis_title: Y축 제목 (labels로 지정 권장)
            height: 차트 높이 (픽셀)
            width: 차트 너비 (픽셀)
            markers: 데이터 포인트 마커 표시 여부
            line_shape: 라인 형태 ("linear", "spline", "hv", "vh", "hvh", "vhv")
            labels: 필드명→표시라벨 매핑 (MCP에서 LLM이 지정)
                   예: {"PRD_DE": "연도", "DT": "인구수", "C1_NM": "지역"}
                   hovertemplate, 축 제목, 범례 제목에 모두 적용됩니다.

        Returns:
            Plotly Figure 객체. fig.show()로 표시하거나
            fig.write_html("file.html")로 저장할 수 있습니다.

        Example:
            MCP에서 LLM이 호출할 때:
            >>> viz = KosisVisualizer()
            >>> fig = viz.line_chart(
            ...     data=records,
            ...     x="PRD_DE",
            ...     y="DT",
            ...     color="C1_NM",
            ...     title="지역별 인구 추이",
            ...     labels={"PRD_DE": "연도", "DT": "인구수", "C1_NM": "지역"}
            ... )
            >>> fig.show()
        """
        # 숫자 변환 (DT 필드가 문자열인 경우)
        processed_data = self._convert_numeric(data, y)

        fig = px.line(
            processed_data,
            x=x,
            y=y,
            color=color,
            markers=markers,
            line_shape=line_shape,
            labels=labels,  # Plotly가 hovertemplate까지 자동 변환
        )

        # labels에서 축 제목 추출 (xaxis_title/yaxis_title 미지정 시)
        if labels:
            if xaxis_title is None and x in labels:
                xaxis_title = labels[x]
            if yaxis_title is None and y in labels:
                yaxis_title = labels[y]

        return self._apply_korean_layout(
            fig, title, xaxis_title, yaxis_title, height, width
        )

    def bar_chart(
        self,
        data: List[Dict[str, Any]],
        x: str,
        y: str = "DT",
        color: Optional[str] = None,
        title: Optional[str] = None,
        xaxis_title: Optional[str] = None,
        yaxis_title: Optional[str] = None,
        height: Optional[int] = None,
        width: Optional[int] = None,
        orientation: str = "v",
        barmode: str = "group",
        text_auto: bool = False,
        labels: Optional[Dict[str, str]] = None,
    ) -> go.Figure:
        """
        막대 차트를 생성합니다.

        분류별 데이터 비교에 적합합니다.
        수평/수직, 그룹/스택 등 다양한 형태를 지원합니다.

        Args:
            data: KOSIS API 응답 데이터 (레코드 리스트)
            x: X축 필드명 (예: "C1_NM" - 분류명)
            y: Y축 필드명 (기본: "DT" - 데이터 값)
            color: 색상 구분 필드명 (선택)
            title: 차트 제목
            xaxis_title: X축 제목 (labels로 지정 권장)
            yaxis_title: Y축 제목 (labels로 지정 권장)
            height: 차트 높이 (픽셀)
            width: 차트 너비 (픽셀)
            orientation: 막대 방향 ("v": 수직, "h": 수평)
            barmode: 막대 배치 ("group": 그룹, "stack": 스택,
                               "overlay": 중첩, "relative": 상대)
            text_auto: 막대 위에 값 자동 표시 여부
            labels: 필드명→표시라벨 매핑 (MCP에서 LLM이 지정)
                   예: {"C1_NM": "지역", "DT": "인구수", "PRD_DE": "연도"}
                   hovertemplate, 축 제목, 범례 제목에 모두 적용됩니다.

        Returns:
            Plotly Figure 객체

        Example:
            MCP에서 LLM이 호출할 때:
            >>> viz = KosisVisualizer()
            >>> fig = viz.bar_chart(
            ...     data=records,
            ...     x="C1_NM",
            ...     y="DT",
            ...     color="PRD_DE",
            ...     title="지역별 인구수",
            ...     barmode="group",
            ...     labels={"C1_NM": "지역", "DT": "인구수", "PRD_DE": "연도"}
            ... )
            >>> fig.show()
        """
        processed_data = self._convert_numeric(data, y)

        fig = px.bar(
            processed_data,
            x=x,
            y=y,
            color=color,
            orientation=orientation,
            barmode=barmode,
            text_auto=text_auto,
            labels=labels,  # Plotly가 hovertemplate까지 자동 변환
        )

        # labels에서 축 제목 추출 (xaxis_title/yaxis_title 미지정 시)
        if labels:
            if xaxis_title is None and x in labels:
                xaxis_title = labels[x]
            if yaxis_title is None and y in labels:
                yaxis_title = labels[y]

        return self._apply_korean_layout(
            fig, title, xaxis_title, yaxis_title, height, width
        )

    def pie_chart(
        self,
        data: List[Dict[str, Any]],
        values: str = "DT",
        names: str = "C1_NM",
        title: Optional[str] = None,
        height: Optional[int] = None,
        width: Optional[int] = None,
        hole: float = 0,
    ) -> go.Figure:
        """
        파이 차트를 생성합니다.

        구성비를 시각화하는 데 적합합니다.
        도넛 차트로 변형할 수도 있습니다.

        Args:
            data: KOSIS API 응답 데이터 (레코드 리스트)
            values: 값 필드명 (기본: "DT" - 데이터 값)
            names: 라벨 필드명 (기본: "C1_NM" - 분류명)
            title: 차트 제목
            height: 차트 높이 (픽셀)
            width: 차트 너비 (픽셀)
            hole: 도넛 차트 중앙 구멍 크기 (0~1, 0이면 파이 차트)

        Returns:
            Plotly Figure 객체

        Example:
            >>> viz = KosisVisualizer()
            >>> fig = viz.pie_chart(
            ...     data=records,
            ...     values="DT",
            ...     names="C1_NM",
            ...     title="지역별 인구 구성비",
            ...     hole=0.4  # 도넛 차트
            ... )
            >>> fig.show()
        """
        processed_data = self._convert_numeric(data, values)

        fig = px.pie(
            processed_data,
            values=values,
            names=names,
            hole=hole,
        )

        return self._apply_korean_layout(fig, title, height=height, width=width)

    def heatmap(
        self,
        data: List[Dict[str, Any]],
        x: str = "PRD_DE",
        y: str = "C1_NM",
        z: str = "DT",
        title: Optional[str] = None,
        xaxis_title: Optional[str] = None,
        yaxis_title: Optional[str] = None,
        height: Optional[int] = None,
        width: Optional[int] = None,
        color_scale: str = "Viridis",
    ) -> go.Figure:
        """
        히트맵을 생성합니다.

        2차원 데이터를 색상 강도로 시각화합니다.
        시간-지역, 분류1-분류2 등의 교차 데이터에 적합합니다.

        Args:
            data: KOSIS API 응답 데이터 (레코드 리스트)
            x: X축 필드명 (기본: "PRD_DE" - 기간)
            y: Y축 필드명 (기본: "C1_NM" - 분류명)
            z: 색상 값 필드명 (기본: "DT" - 데이터 값)
            title: 차트 제목
            xaxis_title: X축 제목
            yaxis_title: Y축 제목
            height: 차트 높이 (픽셀)
            width: 차트 너비 (픽셀)
            color_scale: 색상 스케일 ("Viridis", "Blues", "Reds",
                        "YlOrRd", "Plasma", "Inferno" 등)

        Returns:
            Plotly Figure 객체

        Example:
            >>> viz = KosisVisualizer()
            >>> fig = viz.heatmap(
            ...     data=records,
            ...     x="PRD_DE",
            ...     y="C1_NM",
            ...     z="DT",
            ...     title="연도별 지역별 인구 히트맵"
            ... )
            >>> fig.show()
        """
        processed_data = self._convert_numeric(data, z)

        # 피벗 테이블 형태로 변환
        pivot_data = self._pivot_for_heatmap(processed_data, x, y, z)

        fig = go.Figure(data=go.Heatmap(
            z=pivot_data["values"],
            x=pivot_data["x_labels"],
            y=pivot_data["y_labels"],
            colorscale=color_scale,
            hoverongaps=False,
        ))

        return self._apply_korean_layout(
            fig, title, xaxis_title, yaxis_title, height, width
        )

    def scatter_chart(
        self,
        data: List[Dict[str, Any]],
        x: str,
        y: str,
        color: Optional[str] = None,
        size: Optional[str] = None,
        title: Optional[str] = None,
        xaxis_title: Optional[str] = None,
        yaxis_title: Optional[str] = None,
        height: Optional[int] = None,
        width: Optional[int] = None,
        trendline: Optional[str] = None,
    ) -> go.Figure:
        """
        산점도 차트를 생성합니다.

        두 변수 간의 관계를 시각화합니다.
        추세선을 추가할 수도 있습니다.

        Args:
            data: KOSIS API 응답 데이터 (레코드 리스트)
            x: X축 필드명
            y: Y축 필드명
            color: 색상 구분 필드명 (선택)
            size: 점 크기 필드명 (선택)
            title: 차트 제목
            xaxis_title: X축 제목
            yaxis_title: Y축 제목
            height: 차트 높이 (픽셀)
            width: 차트 너비 (픽셀)
            trendline: 추세선 유형 ("ols": 선형, "lowess": 비선형, None: 없음)

        Returns:
            Plotly Figure 객체
        """
        processed_data = self._convert_numeric(data, x)
        processed_data = self._convert_numeric(processed_data, y)
        if size:
            processed_data = self._convert_numeric(processed_data, size)

        fig = px.scatter(
            processed_data,
            x=x,
            y=y,
            color=color,
            size=size,
            trendline=trendline,
        )

        return self._apply_korean_layout(
            fig, title, xaxis_title, yaxis_title, height, width
        )

    def multi_line_chart(
        self,
        data: List[Dict[str, Any]],
        x: str = "PRD_DE",
        y: str = "DT",
        facet_col: str = "C1_NM",
        title: Optional[str] = None,
        height: Optional[int] = None,
        width: Optional[int] = None,
        facet_col_wrap: int = 3,
    ) -> go.Figure:
        """
        패싯(소형 다중) 라인 차트를 생성합니다.

        여러 분류를 개별 서브 차트로 나누어 표시합니다.
        많은 분류를 비교할 때 유용합니다.

        Args:
            data: KOSIS API 응답 데이터 (레코드 리스트)
            x: X축 필드명 (기본: "PRD_DE")
            y: Y축 필드명 (기본: "DT")
            facet_col: 패싯 분할 필드명 (기본: "C1_NM")
            title: 차트 제목
            height: 차트 높이 (픽셀)
            width: 차트 너비 (픽셀)
            facet_col_wrap: 한 행당 서브 차트 개수

        Returns:
            Plotly Figure 객체
        """
        processed_data = self._convert_numeric(data, y)

        fig = px.line(
            processed_data,
            x=x,
            y=y,
            facet_col=facet_col,
            facet_col_wrap=facet_col_wrap,
            markers=True,
        )

        # 패싯 레이아웃에서도 한글 적용
        fig.update_annotations(font=dict(family=self.font_family))

        return self._apply_korean_layout(
            fig, title, height=height or 600, width=width or 1000
        )

    def save_chart(
        self,
        fig: go.Figure,
        filepath: Union[str, Path],
        format: Optional[str] = None,
        scale: float = 2.0,
    ) -> str:
        """
        차트를 파일로 저장합니다.

        HTML, PNG, PDF, SVG 등 다양한 형식을 지원합니다.
        PNG/PDF 저장에는 kaleido 패키지가 필요합니다.

        Args:
            fig: 저장할 Plotly Figure 객체
            filepath: 저장 경로 (확장자로 형식 결정)
            format: 저장 형식 (지정 시 확장자 무시)
                   "html", "png", "pdf", "svg", "jpeg", "webp"
            scale: 이미지 해상도 배율 (PNG/JPEG/WebP만, 기본: 2.0)

        Returns:
            저장된 파일의 절대 경로

        Example:
            >>> viz = KosisVisualizer()
            >>> fig = viz.line_chart(data, x="PRD_DE", y="DT")
            >>> viz.save_chart(fig, "output/population_trend.html")
            '/path/to/output/population_trend.html'
            >>> viz.save_chart(fig, "output/population_trend.png", scale=3)
            '/path/to/output/population_trend.png'
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # 형식 결정
        if format is None:
            format = filepath.suffix.lstrip(".").lower()

        if format == "html":
            fig.write_html(str(filepath))
        else:
            # PNG, PDF, SVG 등은 kaleido 사용
            fig.write_image(str(filepath), scale=scale)

        logger.info(f"차트 저장 완료: {filepath}")
        return str(filepath.absolute())

    def _convert_numeric(
        self,
        data: List[Dict[str, Any]],
        field: str,
    ) -> List[Dict[str, Any]]:
        """
        지정된 필드의 값을 숫자로 변환합니다.

        KOSIS API 응답에서 DT 필드는 문자열로 반환되므로
        시각화 전에 숫자 변환이 필요합니다.

        Args:
            data: 데이터 리스트
            field: 변환할 필드명

        Returns:
            숫자 변환된 데이터 리스트 (원본 수정하지 않음)
        """
        result = []
        for row in data:
            new_row = dict(row)
            if field in new_row:
                try:
                    val = new_row[field]
                    if isinstance(val, str):
                        # 쉼표 제거 후 변환
                        val = val.replace(",", "").strip()
                        if val == "" or val == "-":
                            new_row[field] = None
                        else:
                            new_row[field] = float(val)
                except (ValueError, TypeError):
                    new_row[field] = None
            result.append(new_row)
        return result

    def _pivot_for_heatmap(
        self,
        data: List[Dict[str, Any]],
        x: str,
        y: str,
        z: str,
    ) -> Dict[str, Any]:
        """
        히트맵용 피벗 데이터를 생성합니다.

        Args:
            data: 원본 데이터 리스트
            x: X축 필드명
            y: Y축 필드명
            z: 값 필드명

        Returns:
            {
                "x_labels": [...],  # X축 라벨 목록
                "y_labels": [...],  # Y축 라벨 목록
                "values": [[...]]   # 2D 값 배열
            }
        """
        # 고유값 추출 및 정렬
        x_labels = sorted(set(str(row.get(x, "")) for row in data))
        y_labels = sorted(set(str(row.get(y, "")) for row in data))

        # 값 매핑
        value_map = {}
        for row in data:
            key = (str(row.get(x, "")), str(row.get(y, "")))
            value_map[key] = row.get(z)

        # 2D 배열 생성
        values = []
        for y_label in y_labels:
            row_values = []
            for x_label in x_labels:
                val = value_map.get((x_label, y_label))
                row_values.append(val)
            values.append(row_values)

        return {
            "x_labels": x_labels,
            "y_labels": y_labels,
            "values": values,
        }


def quick_line(
    data: List[Dict[str, Any]],
    x: str = "PRD_DE",
    y: str = "DT",
    color: Optional[str] = None,
    title: Optional[str] = None,
) -> go.Figure:
    """
    빠른 라인 차트 생성 (편의 함수).

    KosisVisualizer 인스턴스 없이 바로 라인 차트를 생성합니다.

    Args:
        data: KOSIS API 응답 데이터
        x: X축 필드명
        y: Y축 필드명
        color: 색상 구분 필드명
        title: 차트 제목

    Returns:
        Plotly Figure 객체

    Example:
        >>> from kosis_tools.visualize import quick_line
        >>> fig = quick_line(records, title="인구 추이")
        >>> fig.show()
    """
    viz = KosisVisualizer()
    return viz.line_chart(data, x=x, y=y, color=color, title=title)


def quick_bar(
    data: List[Dict[str, Any]],
    x: str = "C1_NM",
    y: str = "DT",
    color: Optional[str] = None,
    title: Optional[str] = None,
) -> go.Figure:
    """
    빠른 막대 차트 생성 (편의 함수).

    Args:
        data: KOSIS API 응답 데이터
        x: X축 필드명
        y: Y축 필드명
        color: 색상 구분 필드명
        title: 차트 제목

    Returns:
        Plotly Figure 객체
    """
    viz = KosisVisualizer()
    return viz.bar_chart(data, x=x, y=y, color=color, title=title)


def quick_pie(
    data: List[Dict[str, Any]],
    values: str = "DT",
    names: str = "C1_NM",
    title: Optional[str] = None,
) -> go.Figure:
    """
    빠른 파이 차트 생성 (편의 함수).

    Args:
        data: KOSIS API 응답 데이터
        values: 값 필드명
        names: 라벨 필드명
        title: 차트 제목

    Returns:
        Plotly Figure 객체
    """
    viz = KosisVisualizer()
    return viz.pie_chart(data, values=values, names=names, title=title)
