"""
모듈형 코드 실행 엔진.

각 도메인별로 특화된 실행 환경과 가이드라인을 제공합니다.

도구 구조:
    - execute_visualization: 차트/그래프 생성
    - execute_analysis: 데이터 분석/통계 계산
    - execute_table: 테이블 생성
    - execute_report: 위 결과물들을 조합해서 리포트 생성
"""

from .visualization import execute_visualization, VISUALIZATION_GUIDE
from .analysis import execute_analysis, ANALYSIS_GUIDE
from .table import execute_table, TABLE_GUIDE
from .report import execute_report, REPORT_GUIDE

__all__ = [
    "execute_visualization",
    "execute_analysis",
    "execute_table",
    "execute_report",
    "VISUALIZATION_GUIDE",
    "ANALYSIS_GUIDE",
    "TABLE_GUIDE",
    "REPORT_GUIDE",
]
