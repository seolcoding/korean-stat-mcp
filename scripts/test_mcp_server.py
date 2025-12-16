#!/usr/bin/env python3
"""
KOSIS MCP Server E2E Test Script.

MCP 서버의 핵심 기능을 테스트합니다:
1. Health Check
2. MCP Protocol (tools/list, tools/call)
3. 통계 검색
4. 데이터 조회
5. 분석 기능

Usage:
    # 로컬 테스트
    uv run python scripts/test_mcp_server.py http://localhost:8001

    # 원격 테스트
    uv run python scripts/test_mcp_server.py https://your-tunnel.trycloudflare.com
"""

import sys
import json
import httpx
import asyncio
from typing import Any


class MCPServerTester:
    """MCP 서버 테스트 클래스."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        self.results: list[dict] = []

    async def close(self):
        await self.client.aclose()

    def log(self, test_name: str, success: bool, message: str, data: Any = None):
        """테스트 결과 로깅."""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} | {test_name}: {message}")
        self.results.append({
            "test": test_name,
            "success": success,
            "message": message,
            "data": data
        })

    async def test_health(self) -> bool:
        """1. Health Check 테스트."""
        try:
            resp = await self.client.get(f"{self.base_url}/health")
            data = resp.json()

            if resp.status_code == 200 and data.get("status") == "healthy":
                db_info = data.get("database", {})
                table_count = db_info.get("table_count", 0)
                self.log("Health Check", True, f"DB 연결됨, {table_count:,}개 테이블", data)
                return True
            else:
                self.log("Health Check", False, f"상태 이상: {data}")
                return False
        except Exception as e:
            self.log("Health Check", False, f"요청 실패: {e}")
            return False

    async def test_root(self) -> bool:
        """2. Root Endpoint 테스트."""
        try:
            resp = await self.client.get(f"{self.base_url}/")
            data = resp.json()

            if data.get("service") == "KOSIS MCP Server":
                self.log("Root Endpoint", True, f"버전 {data.get('version')}", data)
                return True
            else:
                self.log("Root Endpoint", False, f"예상치 못한 응답: {data}")
                return False
        except Exception as e:
            self.log("Root Endpoint", False, f"요청 실패: {e}")
            return False

    async def mcp_call(self, method: str, params: dict = None) -> dict | None:
        """MCP JSON-RPC 호출."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
        }
        if params:
            payload["params"] = params

        # FastMCP HTTP 모드는 SSE 스트리밍 사용
        headers = {"Content-Type": "application/json"}

        try:
            # /mcp/sse 엔드포인트 시도 (FastMCP stateless HTTP)
            resp = await self.client.post(
                f"{self.base_url}/mcp/sse",
                json=payload,
                headers=headers
            )
            if resp.status_code == 200:
                # SSE 응답 파싱
                content = resp.text
                for line in content.split("\n"):
                    if line.startswith("data: "):
                        return json.loads(line[6:])

            # 일반 JSON-RPC 엔드포인트 시도
            resp = await self.client.post(
                f"{self.base_url}/mcp",
                json=payload,
                headers=headers
            )
            if resp.status_code == 200 and resp.text:
                return resp.json()

        except Exception as e:
            print(f"  [DEBUG] MCP call error: {e}")

        return None

    async def test_mcp_tools_list(self) -> bool:
        """3. MCP tools/list 테스트."""
        try:
            result = await self.mcp_call("tools/list")

            if result and "result" in result:
                tools = result["result"].get("tools", [])
                tool_names = [t.get("name") for t in tools[:5]]
                self.log("MCP tools/list", True, f"{len(tools)}개 도구 발견: {tool_names}...", {"count": len(tools)})
                return True
            else:
                self.log("MCP tools/list", False, f"응답 없음 또는 오류: {result}")
                return False
        except Exception as e:
            self.log("MCP tools/list", False, f"요청 실패: {e}")
            return False

    async def test_mcp_search(self) -> bool:
        """4. MCP 통계 검색 테스트."""
        try:
            result = await self.mcp_call("tools/call", {
                "name": "search_statistics",
                "arguments": {"keyword": "인구", "limit": 3}
            })

            if result and "result" in result:
                content = result["result"].get("content", [])
                if content and len(content) > 0:
                    # 텍스트 결과 파싱
                    text = content[0].get("text", "")
                    self.log("MCP 통계검색", True, f"'인구' 검색 결과 수신", {"preview": text[:100]})
                    return True

            self.log("MCP 통계검색", False, f"검색 결과 없음: {result}")
            return False
        except Exception as e:
            self.log("MCP 통계검색", False, f"요청 실패: {e}")
            return False

    async def test_static_files(self) -> bool:
        """5. 정적 파일 서빙 테스트."""
        try:
            # artifacts 디렉토리 접근 테스트
            resp = await self.client.get(f"{self.base_url}/artifacts/")

            # 디렉토리 존재 확인 (404가 아니면 성공)
            if resp.status_code != 404:
                self.log("Static Files", True, f"artifacts 경로 접근 가능 (status: {resp.status_code})")
                return True
            else:
                self.log("Static Files", False, "artifacts 경로 없음")
                return False
        except Exception as e:
            self.log("Static Files", False, f"요청 실패: {e}")
            return False

    async def test_database_query(self) -> bool:
        """6. 데이터베이스 쿼리 테스트 (Health에서 확인)."""
        try:
            resp = await self.client.get(f"{self.base_url}/health")
            data = resp.json()

            db = data.get("database", {})
            if db.get("status") == "healthy" and db.get("table_count", 0) > 0:
                self.log("Database Query", True, f"서버 시간: {db.get('server_time')}")
                return True
            else:
                self.log("Database Query", False, f"DB 상태 이상: {db}")
                return False
        except Exception as e:
            self.log("Database Query", False, f"요청 실패: {e}")
            return False

    async def run_all_tests(self) -> dict:
        """모든 테스트 실행."""
        print(f"\n{'='*60}")
        print(f"KOSIS MCP Server Test")
        print(f"Target: {self.base_url}")
        print(f"{'='*60}\n")

        tests = [
            ("Health Check", self.test_health),
            ("Root Endpoint", self.test_root),
            ("Database Query", self.test_database_query),
            ("Static Files", self.test_static_files),
            ("MCP tools/list", self.test_mcp_tools_list),
            ("MCP Search", self.test_mcp_search),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                result = await test_func()
                if result:
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                self.log(name, False, f"예외 발생: {e}")
                failed += 1

        print(f"\n{'='*60}")
        print(f"Results: {passed} passed, {failed} failed")
        print(f"{'='*60}\n")

        return {
            "url": self.base_url,
            "passed": passed,
            "failed": failed,
            "total": passed + failed,
            "results": self.results
        }


async def main():
    # 기본 URL 또는 인자로 받은 URL 사용
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8001"

    tester = MCPServerTester(base_url)

    try:
        summary = await tester.run_all_tests()

        # 종료 코드: 실패가 있으면 1
        sys.exit(0 if summary["failed"] == 0 else 1)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
