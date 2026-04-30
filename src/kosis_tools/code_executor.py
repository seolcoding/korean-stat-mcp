"""
Code Execution 엔진.

LLM이 작성한 Python 코드를 안전하게 실행.
대용량 데이터 처리 시 토큰 98.7% 절감.

사용 가능한 모듈:
    - pandas (as pd)
    - altair (as alt)
    - numpy (as np)

사용 가능한 헬퍼 - 시각화:
    - prepare_data(data, numeric_fields): KOSIS 데이터 → DataFrame
    - save_chart(chart, name): Altair 차트 저장 → {url, ...}
    - chart_to_json(chart): Altair 차트 → Vega-Lite JSON
    - chart_to_html(chart): Altair 차트 → 독립형 HTML

사용 가능한 헬퍼 - 아티팩트:
    - save_report(html, name): HTML 리포트 저장 → {url, ...}
    - save_data(data, name, format): 데이터 저장 → {url, ...}

사용 가능한 헬퍼 - 리포트 템플릿:
    - build_report(title, sections): 완성된 HTML 리포트 생성
    - build_chart_section(vega_spec, title): 차트 섹션 HTML
    - build_stat_cards(stats): 통계 카드 HTML
    - build_insight_box(content, title): 인사이트 박스 HTML
    - quick_report(title, chart_specs, tables, insights): 빠른 리포트

사용 가능한 헬퍼 - 유틸리티:
    - to_table_html(df, max_rows=10, title=""): DataFrame → HTML 테이블
    - datetime: datetime 모듈

Example:
    >>> result = execute_code('''
    ...     df = prepare_data(data, numeric_fields=["DT"])
    ...     chart = alt.Chart(df).mark_line().encode(
    ...         x="PRD_DE:N", y="DT:Q", color="C1_NM:N"
    ...     )
    ...     html = build_report(
    ...         title="인구 분석",
    ...         sections=[
    ...             {"type": "chart", "vega_spec": chart.to_dict()},
    ...             {"type": "table", "html": to_table_html(df)}
    ...         ]
    ...     )
    ...     return save_report(html, "population_report")
    ... ''', data=kosis_data)
    >>> print(result['artifacts'][0]['url'])
    http://localhost:8000/artifacts/reports/population_report_xxx.html
"""

from __future__ import annotations

import io
import re
import sys
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def to_table_html(
    df: pd.DataFrame, max_rows: int = 10, title: str = "", format_numbers: bool = True
) -> str:
    """
    DataFrame을 HTML 테이블로 변환.

    Args:
        df: 변환할 DataFrame
        max_rows: 최대 표시 행 수
        title: 테이블 제목 (선택)
        format_numbers: 큰 숫자에 천 단위 구분자 적용 (기본: True)

    Returns:
        HTML 테이블 문자열
    """
    # 행 수 제한
    display_df = df.head(max_rows) if len(df) > max_rows else df.copy()

    # 숫자 포맷팅 (천 단위 구분자)
    if format_numbers:
        for col in display_df.columns:
            if display_df[col].dtype in ["int64", "float64"]:
                # 큰 숫자만 포맷팅 (1000 이상)
                display_df[col] = display_df[col].apply(
                    lambda x: f"{x:,.0f}" if pd.notna(x) and abs(x) >= 1000 else x
                )

    html = '<div class="table-container">'
    if title:
        html += f"<h3>{title}</h3>"

    # DataFrame to HTML
    table_html = display_df.to_html(
        index=False,
        classes="data-table",
        border=0,
        escape=False,
    )
    html += table_html

    if len(df) > max_rows:
        html += f'<p class="table-note">... 외 {len(df) - max_rows}건 더</p>'

    html += "</div>"
    return html


# 금지된 패턴 (보안)
BLOCKED_PATTERNS = [
    r"\bimport\s+os\b",
    r"\bimport\s+subprocess\b",
    r"\bimport\s+shutil\b",
    r"\bfrom\s+os\b",
    r"\bfrom\s+subprocess\b",
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bcompile\s*\(",
    r"\bglobals\s*\(",
    r"\blocals\s*\(",
    r"\bgetattr\s*\(",
    r"\bsetattr\s*\(",
    r"\bdelattr\s*\(",
    r"\bopen\s*\(",
    r"\bbreakpoint\s*\(",
]


class CodeExecutionError(Exception):
    """코드 실행 오류."""

    pass


class CodeSecurityError(Exception):
    """보안 위반 오류."""

    pass


class VisualizationValidationError(Exception):
    """시각화 검증 오류 - 빈 데이터 또는 잘못된 차트 구조."""

    pass


# 품질 검사 기준
QUALITY_THRESHOLDS = {
    "max_series_for_line": 5,  # 라인 차트 최대 시리즈 수
    "max_categories_for_bar": 15,  # 막대 차트 최대 카테고리 수
    "max_slices_for_pie": 5,  # 파이/도넛 차트 최대 조각 수
    "min_data_points": 2,  # 최소 데이터 포인트 수
    "large_number_threshold": 1000,  # 천 단위 포맷 필요 기준
}


class CodeExecutor:
    """
    LLM 코드 실행 엔진.

    안전한 샌드박스 환경에서 Python 코드를 실행합니다.
    대용량 데이터를 서버에서 처리하고 결과만 반환합니다.

    Attributes:
        timeout: 실행 제한 시간 (초)
        max_output_size: 최대 출력 크기 (바이트)
    """

    def __init__(
        self,
        timeout: int = 30,
        max_output_size: int = 1_000_000,  # 1MB
    ):
        self.timeout = timeout
        self.max_output_size = max_output_size

    def validate_code(self, code: str) -> None:
        """
        코드 보안 검증.

        Args:
            code: 검증할 Python 코드

        Raises:
            CodeSecurityError: 금지된 패턴 발견 시
        """
        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                raise CodeSecurityError(f"금지된 패턴 감지: {pattern}")

    def execute(
        self,
        code: str,
        data: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Python 코드를 실행합니다.

        Args:
            code: 실행할 Python 코드
            data: KOSIS 데이터 (코드 내에서 `data` 변수로 접근)
            context: 추가 컨텍스트 변수들

        Returns:
            {
                "success": bool,
                "result": Any,  # return 값 또는 마지막 표현식 값
                "stdout": str,  # print 출력
                "error": str | None,
            }
        """
        # 1. 보안 검증
        try:
            self.validate_code(code)
        except CodeSecurityError as e:
            return {
                "success": False,
                "result": None,
                "stdout": "",
                "error": str(e),
            }

        # 2. 안전한 글로벌 환경 구성
        import pandas as pd
        import altair as alt
        import numpy as np
        from kosis_tools.visualize import (
            prepare_data,
            save_chart,
            chart_to_json,
            chart_to_html,
        )
        from kosis_tools.artifact_host import (
            save_report,
            save_data,
        )
        from kosis_tools.report_template import (
            build_report,
            build_chart_section,
            build_stat_cards,
            build_insight_box,
            quick_report,
        )

        safe_globals = {
            # 기본 타입
            "True": True,
            "False": False,
            "None": None,
            # 빌트인 함수 (안전한 것만)
            "len": len,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "sorted": sorted,
            "reversed": reversed,
            "enumerate": enumerate,
            "zip": zip,
            "map": map,
            "filter": filter,
            "range": range,
            "list": list,
            "dict": dict,
            "set": set,
            "tuple": tuple,
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "print": print,
            "isinstance": isinstance,
            "type": type,
            # 데이터 분석 라이브러리
            "pd": pd,
            "alt": alt,
            "np": np,
            # KOSIS 헬퍼 - 시각화
            "prepare_data": prepare_data,
            "save_chart": save_chart,
            "chart_to_json": chart_to_json,
            "chart_to_html": chart_to_html,
            # KOSIS 헬퍼 - 아티팩트 저장
            "save_report": save_report,
            "save_data": save_data,
            # KOSIS 헬퍼 - HTML 테이블
            "to_table_html": to_table_html,
            # KOSIS 헬퍼 - 리포트 템플릿
            "build_report": build_report,
            "build_chart_section": build_chart_section,
            "build_stat_cards": build_stat_cards,
            "build_insight_box": build_insight_box,
            "quick_report": quick_report,
            # 유틸리티
            "datetime": datetime,
            # 데이터
            "data": data or [],
        }

        # 추가 컨텍스트 병합
        if context:
            safe_globals.update(context)

        # 3. 코드 래핑 (return 지원)
        wrapped_code = self._wrap_code(code)

        # 4. stdout 캡처
        captured_output = io.StringIO()
        old_stdout = sys.stdout

        result = {
            "success": False,
            "result": None,
            "stdout": "",
            "error": None,
            "artifacts": [],  # 생성된 아티팩트 목록
        }

        try:
            sys.stdout = captured_output

            # 5. 실행
            local_vars: Dict[str, Any] = {}
            exec(wrapped_code, safe_globals, local_vars)

            # 6. 결과 추출
            raw_result = local_vars.get("__result__")
            result["success"] = True
            result["stdout"] = captured_output.getvalue()

            # 7. 아티팩트 감지 및 추출
            artifacts = self._extract_artifacts(raw_result)

            # 8. 시각화 검증 (빈 차트 데이터 감지)
            html_content = None
            if artifacts:
                for artifact in artifacts:
                    if artifact.get("type") == "report" and "path" in artifact:
                        # 리포트 파일 읽기
                        try:
                            report_path = Path(artifact["path"])
                            if report_path.exists():
                                html_content = report_path.read_text(encoding="utf-8")
                        except Exception as e:
                            logger.warning(f"리포트 파일 읽기 실패: {e}")

            # Vega-Lite 스펙 직접 반환 시에도 검증
            direct_vega_spec = None
            if isinstance(raw_result, dict) and self._is_vega_spec(raw_result):
                direct_vega_spec = raw_result
            elif isinstance(raw_result, str):
                # JSON 문자열인 경우 파싱 시도
                try:
                    import json

                    parsed = json.loads(raw_result)
                    if isinstance(parsed, dict) and self._is_vega_spec(parsed):
                        direct_vega_spec = parsed
                except (json.JSONDecodeError, TypeError):
                    pass

            validation_error = self._validate_visualization(
                artifacts, html_content, data, direct_vega_spec
            )

            if validation_error:
                # 검증 실패: 에러 정보와 데이터 시그니처 반환
                result["success"] = False
                result["error"] = validation_error["message"]
                result["validation_details"] = validation_error
                result["artifacts"] = []  # 잘못된 아티팩트는 반환하지 않음
                logger.warning(f"시각화 검증 실패: {validation_error['empty_charts']}")
            elif artifacts:
                result["artifacts"] = artifacts
                # 단일 아티팩트면 URL만 반환, 복수면 목록 반환
                if len(artifacts) == 1:
                    result["result"] = artifacts[0]
                else:
                    result["result"] = artifacts

                # 9. 품질 검사 (성공해도 개선 제안)
                quality_warnings = self._check_visualization_quality(
                    html_content, direct_vega_spec, data
                )
                if quality_warnings:
                    result["quality_warnings"] = quality_warnings
                    result["quality_summary"] = self._summarize_quality(
                        quality_warnings
                    )
            else:
                result["result"] = raw_result
                # 출력 크기 제한
                if len(str(result["result"])) > self.max_output_size:
                    result["result"] = (
                        str(result["result"])[: self.max_output_size]
                        + "... (truncated)"
                    )

                # 직접 반환된 Vega-Lite 스펙에도 품질 검사 적용
                if direct_vega_spec:
                    quality_warnings = self._check_visualization_quality(
                        html_content, direct_vega_spec, data
                    )
                    if quality_warnings:
                        result["quality_warnings"] = quality_warnings
                        result["quality_summary"] = self._summarize_quality(
                            quality_warnings
                        )

        except Exception as e:
            result["error"] = f"{type(e).__name__}: {str(e)}"
            result["stdout"] = captured_output.getvalue()

        finally:
            sys.stdout = old_stdout

        return result

    def _extract_artifacts(self, result: Any) -> List[Dict[str, Any]]:
        """
        결과에서 아티팩트를 추출합니다.

        save_chart, save_report, save_data 반환값을 감지하여
        아티팩트 목록으로 변환합니다.

        Args:
            result: 코드 실행 결과

        Returns:
            아티팩트 딕셔너리 목록 (URL, type 등 포함)
        """
        artifacts = []

        def is_artifact(obj: Any) -> bool:
            """아티팩트 딕셔너리인지 확인."""
            if not isinstance(obj, dict):
                return False
            # artifact_host 반환 형식: url, type 필드 존재
            return "url" in obj and "type" in obj

        if is_artifact(result):
            artifacts.append(result)
        elif isinstance(result, list):
            for item in result:
                if is_artifact(item):
                    artifacts.append(item)

        return artifacts

    def _is_vega_spec(self, obj: Any) -> bool:
        """
        객체가 Vega-Lite 스펙인지 확인합니다.

        Args:
            obj: 확인할 객체

        Returns:
            Vega-Lite 스펙이면 True
        """
        if not isinstance(obj, dict):
            return False

        # Vega-Lite 스펙의 필수/일반적인 필드 확인
        vega_indicators = [
            "$schema",
            "data",
            "mark",
            "encoding",
            "layer",
            "concat",
            "hconcat",
            "vconcat",
        ]
        return any(key in obj for key in vega_indicators)

    def _validate_visualization(
        self,
        artifacts: List[Dict[str, Any]],
        html_content: Optional[str],
        data: Optional[List[Dict[str, Any]]],
        direct_vega_spec: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        시각화 결과물을 검증합니다.

        Vega-Lite spec에서 빈 데이터 배열을 감지하고,
        문제 발견 시 데이터 시그니처와 함께 에러 정보를 반환합니다.

        Args:
            artifacts: 생성된 아티팩트 목록
            html_content: 생성된 HTML 콘텐츠 (리포트인 경우)
            data: 원본 KOSIS 데이터

        Returns:
            None: 검증 통과
            Dict: 검증 실패 시 에러 정보와 데이터 시그니처
        """
        import json
        import re

        empty_charts = []

        # 1. HTML 콘텐츠에서 Vega-Lite spec 추출 및 검증
        if html_content:
            # vegaEmbed 호출에서 spec 추출
            vega_pattern = (
                r'vegaEmbed\s*\(\s*[\'"]#[^"\']+[\'"]\s*,\s*(\{[\s\S]*?\})\s*[,\)]'
            )
            matches = re.findall(vega_pattern, html_content)

            for i, spec_str in enumerate(matches):
                try:
                    # JSON 파싱 시도
                    spec = json.loads(spec_str)
                    validation = self._check_vega_spec(spec, f"chart_{i + 1}")
                    if validation:
                        empty_charts.append(validation)
                except json.JSONDecodeError:
                    # JSON 파싱 실패 시 정규식으로 빈 values 체크
                    if '"values": []' in spec_str or '"values":[]' in spec_str:
                        empty_charts.append(
                            {
                                "chart_id": f"chart_{i + 1}",
                                "issue": "빈 데이터 배열 (values: [])",
                            }
                        )

        # 2. 아티팩트에서 직접 검증
        for artifact in artifacts:
            if artifact.get("type") == "chart" and "vega_spec" in artifact:
                validation = self._check_vega_spec(
                    artifact["vega_spec"], artifact.get("name", "unknown")
                )
                if validation:
                    empty_charts.append(validation)

        # 3. 직접 반환된 Vega-Lite 스펙 검증
        if direct_vega_spec:
            validation = self._check_vega_spec(direct_vega_spec, "returned_chart")
            if validation:
                empty_charts.append(validation)

        # 4. 문제 발견 시 에러 정보 구성
        if empty_charts:
            return {
                "validation_error": True,
                "issue_type": "EMPTY_CHART_DATA",
                "message": "시각화 코드가 빈 데이터를 생성했습니다. 데이터 시그니처를 확인하고 코드를 수정하세요.",
                "empty_charts": empty_charts,
                "data_signature": self._generate_data_signature(data),
                "fix_hints": [
                    "prepare_data() 호출 시 올바른 numeric_fields 지정 확인",
                    "DataFrame 필터링 조건이 모든 데이터를 제외하지 않는지 확인",
                    "Altair 차트의 x, y, color 인코딩이 실제 컬럼명과 일치하는지 확인",
                    "DT 필드는 문자열입니다. 숫자 연산 전 형변환 필요",
                ],
            }

        return None

    def _check_vega_spec(
        self, spec: Dict[str, Any], chart_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Vega-Lite spec에서 빈 데이터를 체크합니다.

        Args:
            spec: Vega-Lite 스펙 딕셔너리
            chart_id: 차트 식별자

        Returns:
            None: 데이터 정상
            Dict: 문제 발견 시 상세 정보
        """

        def check_data_values(data_obj: Any, path: str = "") -> Optional[Dict]:
            """재귀적으로 data.values 체크."""
            if isinstance(data_obj, dict):
                if "values" in data_obj:
                    values = data_obj["values"]
                    if isinstance(values, list) and len(values) == 0:
                        return {
                            "chart_id": chart_id,
                            "path": path + ".values",
                            "issue": "빈 데이터 배열 (values: [])",
                        }
                # datasets 체크 (Vega-Lite 다중 데이터셋)
                if "datasets" in data_obj:
                    for name, dataset in data_obj["datasets"].items():
                        if isinstance(dataset, list) and len(dataset) == 0:
                            return {
                                "chart_id": chart_id,
                                "path": f"datasets.{name}",
                                "issue": f"빈 데이터셋: {name}",
                            }
            return None

        # 최상위 data 체크
        if "data" in spec:
            result = check_data_values(spec["data"], "data")
            if result:
                return result

        # 최상위 datasets 체크 (Altair가 사용하는 형식)
        if "datasets" in spec:
            for name, dataset in spec["datasets"].items():
                if isinstance(dataset, list) and len(dataset) == 0:
                    return {
                        "chart_id": chart_id,
                        "path": f"datasets.{name}",
                        "issue": f"빈 데이터셋: {name}",
                    }

        # layer, concat, hconcat, vconcat 내부 체크
        for key in ["layer", "concat", "hconcat", "vconcat"]:
            if key in spec:
                for i, sub_spec in enumerate(spec[key]):
                    if "data" in sub_spec:
                        result = check_data_values(sub_spec["data"], f"{key}[{i}].data")
                        if result:
                            return result

        return None

    def _generate_data_signature(
        self, data: Optional[List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        데이터 시그니처를 생성합니다.

        클라이언트가 올바른 시각화 코드를 작성할 수 있도록
        데이터 구조, 필드 목록, 샘플 데이터를 제공합니다.

        Args:
            data: KOSIS 데이터

        Returns:
            데이터 시그니처 딕셔너리
        """
        if not data:
            return {
                "error": "원본 데이터가 없습니다",
                "hint": "data_id 또는 data_json 파라미터를 확인하세요",
            }

        signature = {
            "total_records": len(data),
            "fields": {},
            "sample_records": data[:3] if len(data) >= 3 else data,
        }

        # 필드별 정보 수집
        if data:
            first_record = data[0]
            for field, value in first_record.items():
                unique_values = set()
                for record in data[:100]:  # 처음 100개에서 샘플링
                    if field in record:
                        unique_values.add(str(record[field]))

                signature["fields"][field] = {
                    "type": type(value).__name__,
                    "sample_values": list(unique_values)[:5],
                    "unique_count": len(unique_values),
                }

        # KOSIS 특화 힌트
        signature["kosis_hints"] = {
            "PRD_DE": "기간 (예: 2023, 202401)",
            "C1_NM": "분류1 명칭 (주로 지역명)",
            "C2_NM": "분류2 명칭",
            "C3_NM": "분류3 명칭",
            "DT": "데이터 값 (문자열! '-', '*' 등 특수값 주의)",
            "ITM_NM": "항목명",
            "UNIT_NM": "단위",
        }

        return signature

    def _check_visualization_quality(
        self,
        html_content: Optional[str],
        direct_vega_spec: Optional[Dict[str, Any]],
        data: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """
        시각화 품질을 검사하고 개선 제안을 반환합니다.

        검사 항목:
        - 차트 제목 누락
        - 축 라벨 누락
        - 큰 숫자 포맷 누락
        - 너무 많은 시리즈/카테고리
        - 부적절한 차트 유형

        Args:
            html_content: 생성된 HTML 콘텐츠
            direct_vega_spec: 직접 반환된 Vega-Lite 스펙
            data: 원본 KOSIS 데이터

        Returns:
            품질 경고 목록 (성공은 유지, 개선 제안만 포함)
        """
        import json
        import re

        warnings = []
        specs_to_check = []

        # 1. HTML에서 Vega-Lite spec 추출
        if html_content:
            vega_pattern = (
                r'vegaEmbed\s*\(\s*[\'"]#[^"\']+[\'"]\s*,\s*(\{[\s\S]*?\})\s*[,\)]'
            )
            matches = re.findall(vega_pattern, html_content)
            for i, spec_str in enumerate(matches):
                try:
                    spec = json.loads(spec_str)
                    specs_to_check.append((f"chart_{i + 1}", spec))
                except json.JSONDecodeError:
                    pass

        # 2. 직접 반환된 스펙
        if direct_vega_spec:
            specs_to_check.append(("returned_chart", direct_vega_spec))

        # 3. 각 스펙 품질 검사
        for chart_id, spec in specs_to_check:
            warnings.extend(self._analyze_vega_quality(chart_id, spec))

        # 4. 리포트 구조 검사 (HTML)
        if html_content:
            warnings.extend(self._analyze_report_quality(html_content, data))

        return warnings

    def _analyze_vega_quality(
        self,
        chart_id: str,
        spec: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Vega-Lite 스펙의 품질을 분석합니다.

        Args:
            chart_id: 차트 식별자
            spec: Vega-Lite 스펙

        Returns:
            품질 경고 목록
        """
        warnings = []

        # 1. 제목 검사
        title = spec.get("title")
        if not title:
            warnings.append(
                {
                    "chart_id": chart_id,
                    "issue": "missing_title",
                    "severity": "medium",
                    "message": "차트 제목이 없습니다",
                    "fix": ".properties(title='명확한 차트 제목')",
                }
            )
        elif isinstance(title, str) and len(title) < 3:
            warnings.append(
                {
                    "chart_id": chart_id,
                    "issue": "short_title",
                    "severity": "low",
                    "message": f"차트 제목이 너무 짧습니다: '{title}'",
                    "fix": "제목을 더 구체적으로 작성하세요 (예: '연도별 인구 변화 추이')",
                }
            )

        # 2. 인코딩 검사
        encoding = spec.get("encoding", {})

        # X축 제목 검사
        x_encoding = encoding.get("x", {})
        if x_encoding and not x_encoding.get("title"):
            # 필드명만 있고 제목이 없는 경우
            field = x_encoding.get("field", "")
            if field and field in ["PRD_DE", "C1_NM", "DT"]:
                warnings.append(
                    {
                        "chart_id": chart_id,
                        "issue": "missing_x_axis_title",
                        "severity": "low",
                        "message": f"X축 제목이 KOSIS 필드명 그대로입니다: '{field}'",
                        "fix": f"alt.X('{field}:N', title='연도' or '지역' 등 의미있는 제목)",
                    }
                )

        # Y축 제목 및 포맷 검사
        y_encoding = encoding.get("y", {})
        if y_encoding:
            y_axis = y_encoding.get("axis", {})
            y_format = y_axis.get("format")

            # 포맷 없이 큰 숫자 표시 가능성
            if not y_format:
                warnings.append(
                    {
                        "chart_id": chart_id,
                        "issue": "missing_number_format",
                        "severity": "medium",
                        "message": "Y축 숫자 포맷이 없습니다 (큰 숫자가 읽기 어려울 수 있음)",
                        "fix": "axis=alt.Axis(format=',') 추가로 천 단위 구분자 표시",
                    }
                )

        # 3. 차트 유형별 검사
        mark = spec.get("mark", "")
        if isinstance(mark, dict):
            mark_type = mark.get("type", "")
        else:
            mark_type = mark

        # 데이터 크기 추정
        data_size = self._estimate_data_size(spec)

        # 라인 차트 시리즈 수 검사
        if mark_type == "line":
            color_encoding = encoding.get("color", {})
            if color_encoding:
                # 색상으로 구분되는 시리즈가 있으면
                if (
                    data_size.get("series_count", 0)
                    > QUALITY_THRESHOLDS["max_series_for_line"]
                ):
                    warnings.append(
                        {
                            "chart_id": chart_id,
                            "issue": "too_many_line_series",
                            "severity": "medium",
                            "message": f"라인 차트에 시리즈가 너무 많습니다 ({data_size.get('series_count')}개)",
                            "fix": "상위 5개만 표시하거나, 작은 값들을 '기타'로 그룹화하세요",
                        }
                    )

        # 막대 차트 카테고리 수 검사
        elif mark_type == "bar":
            if (
                data_size.get("category_count", 0)
                > QUALITY_THRESHOLDS["max_categories_for_bar"]
            ):
                warnings.append(
                    {
                        "chart_id": chart_id,
                        "issue": "too_many_bar_categories",
                        "severity": "low",
                        "message": f"막대 차트에 카테고리가 많습니다 ({data_size.get('category_count')}개)",
                        "fix": "수평 막대 차트로 변경하거나 상위 항목만 표시하세요",
                    }
                )

        # 파이/도넛 차트 조각 수 검사
        elif mark_type == "arc":
            if (
                data_size.get("slice_count", 0)
                > QUALITY_THRESHOLDS["max_slices_for_pie"]
            ):
                warnings.append(
                    {
                        "chart_id": chart_id,
                        "issue": "too_many_pie_slices",
                        "severity": "high",
                        "message": f"파이/도넛 차트에 조각이 너무 많습니다 ({data_size.get('slice_count')}개)",
                        "fix": "5개 이하로 줄이고 나머지는 '기타'로 그룹화하세요",
                    }
                )

        # 4. 범례 검사 (다중 시리즈)
        if encoding.get("color") and not encoding.get("color", {}).get("legend"):
            # legend가 명시적으로 비활성화되었는지 확인
            legend_config = encoding.get("color", {}).get("legend")
            if legend_config is None:
                # 기본값이므로 OK
                pass
            elif legend_config is False:
                warnings.append(
                    {
                        "chart_id": chart_id,
                        "issue": "disabled_legend",
                        "severity": "medium",
                        "message": "색상으로 구분되는 시리즈가 있지만 범례가 비활성화되었습니다",
                        "fix": "legend=alt.Legend(title='분류명') 추가",
                    }
                )

        return warnings

    def _estimate_data_size(self, spec: Dict[str, Any]) -> Dict[str, int]:
        """
        Vega-Lite 스펙에서 데이터 크기를 추정합니다.

        Args:
            spec: Vega-Lite 스펙

        Returns:
            데이터 크기 정보 (series_count, category_count, slice_count 등)
        """
        result = {
            "series_count": 0,
            "category_count": 0,
            "slice_count": 0,
            "total_points": 0,
        }

        # datasets에서 데이터 추출
        datasets = spec.get("datasets", {})
        data_values = []
        for name, values in datasets.items():
            if isinstance(values, list):
                data_values = values
                break

        # data.values에서 추출
        if not data_values:
            data = spec.get("data", {})
            if isinstance(data, dict) and "values" in data:
                data_values = data["values"]

        if data_values:
            result["total_points"] = len(data_values)

            # 고유값 계산
            unique_colors = set()
            unique_x = set()
            for record in data_values:
                if isinstance(record, dict):
                    # color 필드 (시리즈)
                    for color_field in ["C1_NM", "C2_NM", "category", "series"]:
                        if color_field in record:
                            unique_colors.add(record[color_field])
                    # x 필드 (카테고리)
                    for x_field in ["PRD_DE", "C1_NM", "x", "name"]:
                        if x_field in record:
                            unique_x.add(record[x_field])

            result["series_count"] = len(unique_colors)
            result["category_count"] = len(unique_x)
            result["slice_count"] = len(unique_colors) or len(unique_x)

        return result

    def _analyze_report_quality(
        self,
        html_content: str,
        data: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """
        리포트 전체 구조의 품질을 분석합니다.

        Args:
            html_content: HTML 콘텐츠
            data: 원본 데이터

        Returns:
            품질 경고 목록
        """
        warnings = []

        # 1. 인사이트 섹션 검사
        has_insight = any(
            keyword in html_content
            for keyword in [
                "insight",
                "인사이트",
                "핵심",
                "발견",
                "분석 결과",
                '<div class="insight',
                '<section class="insight',
            ]
        )
        if not has_insight:
            # 차트만 있고 인사이트가 없는 경우
            if "vegaEmbed" in html_content:
                warnings.append(
                    {
                        "chart_id": "report",
                        "issue": "missing_insights",
                        "severity": "medium",
                        "message": "차트는 있지만 인사이트/해석이 없습니다",
                        "fix": "build_insight_box()로 핵심 발견점을 추가하세요",
                    }
                )

        # 2. 통계 카드 검사
        has_stats = any(
            keyword in html_content
            for keyword in [
                "stat-card",
                "kpi",
                "metric",
                '<div class="stat',
                '<div class="card',
            ]
        )
        if not has_stats and "vegaEmbed" in html_content:
            warnings.append(
                {
                    "chart_id": "report",
                    "issue": "missing_stat_cards",
                    "severity": "low",
                    "message": "핵심 수치 카드가 없습니다",
                    "fix": "build_stat_cards()로 3-4개 핵심 KPI를 표시하세요",
                }
            )

        # 3. 데이터 출처 검사
        has_source = any(
            keyword in html_content.lower()
            for keyword in ["출처:", "source:", "kosis", "통계청", "데이터:"]
        )
        if not has_source:
            warnings.append(
                {
                    "chart_id": "report",
                    "issue": "missing_data_source",
                    "severity": "low",
                    "message": "데이터 출처가 명시되지 않았습니다",
                    "fix": "리포트 하단에 '출처: KOSIS 통계청' 추가",
                }
            )

        # 4. 포맷되지 않은 큰 숫자 검사 (HTML 텍스트)
        import re

        # 큰 숫자 패턴 (콤마 없는 5자리 이상 숫자)
        large_numbers = re.findall(r">\s*(\d{5,})\s*<", html_content)
        if large_numbers:
            # 처음 3개만 표시
            examples = large_numbers[:3]
            warnings.append(
                {
                    "chart_id": "report",
                    "issue": "unformatted_large_numbers",
                    "severity": "medium",
                    "message": f"포맷되지 않은 큰 숫자가 있습니다: {', '.join(examples)}",
                    "fix": "f'{value:,.0f}' 또는 f'{value:,}' 형식으로 천 단위 구분자 추가",
                }
            )

        return warnings

    def _summarize_quality(self, warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        품질 경고를 요약합니다.

        Args:
            warnings: 품질 경고 목록

        Returns:
            요약 정보 (severity별 카운트, 주요 이슈, 개선 권장)
        """
        by_severity = {"high": 0, "medium": 0, "low": 0}
        top_issues = []

        for w in warnings:
            severity = w.get("severity", "low")
            by_severity[severity] = by_severity.get(severity, 0) + 1

            # high/medium 이슈만 상위에 포함
            if severity in ("high", "medium") and len(top_issues) < 3:
                top_issues.append(f"[{severity.upper()}] {w['message']}")

        # 권장 사항 생성
        recommendations = []
        if by_severity["high"] > 0:
            recommendations.append(
                "심각한 품질 이슈가 있습니다. 즉시 수정을 권장합니다."
            )
        if by_severity["medium"] > 0:
            recommendations.append(
                "중간 수준의 개선 사항이 있습니다. 가독성 향상을 위해 수정하세요."
            )
        if not recommendations:
            recommendations.append(
                "경미한 개선 사항만 있습니다. 선택적으로 적용하세요."
            )

        return {
            "total_warnings": len(warnings),
            "by_severity": by_severity,
            "top_issues": top_issues,
            "recommendations": recommendations,
            "template_hint": "get_element_guide('line_chart') 등으로 모범 사례 확인",
        }

    def _wrap_code(self, code: str) -> str:
        """
        코드를 래핑하여 return 문 지원.

        마지막 표현식 또는 return 값을 __result__에 저장.
        """
        lines = code.strip().split("\n")

        # return 문이 있으면 함수로 래핑
        if any(line.strip().startswith("return ") for line in lines):
            indented = "\n".join("    " + line for line in lines)
            return f"""
def __execute__():
{indented}

__result__ = __execute__()
"""
        else:
            # 마지막 줄이 표현식이면 __result__에 할당
            if lines:
                last_line = lines[-1].strip()
                # 할당문이 아닌 표현식인지 확인
                if last_line and not any(
                    [
                        "=" in last_line and "==" not in last_line,
                        last_line.startswith(
                            (
                                "if ",
                                "for ",
                                "while ",
                                "def ",
                                "class ",
                                "import ",
                                "from ",
                            )
                        ),
                    ]
                ):
                    lines[-1] = f"__result__ = {last_line}"
                else:
                    lines.append("__result__ = None")

            return "\n".join(lines)


# 싱글톤 인스턴스
_executor: Optional[CodeExecutor] = None


def get_executor() -> CodeExecutor:
    """CodeExecutor 싱글톤 인스턴스 반환."""
    global _executor
    if _executor is None:
        _executor = CodeExecutor()
    return _executor


def execute_code(
    code: str,
    data: Optional[List[Dict[str, Any]]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    코드 실행 편의 함수.

    Args:
        code: 실행할 Python 코드
        data: KOSIS 데이터
        context: 추가 컨텍스트

    Returns:
        실행 결과 딕셔너리
    """
    return get_executor().execute(code, data, context)
