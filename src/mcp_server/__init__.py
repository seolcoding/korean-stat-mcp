"""
KOSIS MCP Server.

한국 통계청 KOSIS OpenAPI를 MCP(Model Context Protocol)로 래핑하여
AI 에이전트가 한국 통계 데이터에 접근할 수 있도록 합니다.

Usage:
    # 로컬 테스트 (stdio)
    korean-stat-mcp

    # HTTP 서버로 실행 (Streamable HTTP /mcp)
    korean-stat-mcp --http

    # 버전 확인
    korean-stat-mcp --version
"""

from .server import mcp

__all__ = ["mcp"]
