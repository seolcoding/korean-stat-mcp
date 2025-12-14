"""
KOSIS 리포트 디버깅 시나리오 정의 모듈.

MCP 호출 시나리오와 하드코딩 데이터 시나리오를 정의합니다.
"""

from .mcp_scenarios import MCP_SCENARIOS
from .hardcoded_scenarios import HARDCODED_SCENARIOS, SAMPLE_DATASETS

__all__ = ["MCP_SCENARIOS", "HARDCODED_SCENARIOS", "SAMPLE_DATASETS"]
