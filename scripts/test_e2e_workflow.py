#!/usr/bin/env python3
"""
KOSIS MCP Server E2E Workflow Test.

전체 워크플로 테스트:
1. 통계 검색 (search_statistics)
2. 하이브리드 검색 (search_tables_hybrid)
3. 데이터 조회 (get_statistics_data)
4. 시각화 생성 (execute_visualization) → R2 업로드
5. 분석 실행 (execute_analysis)

Usage:
    uv run python scripts/test_e2e_workflow.py https://your-tunnel.trycloudflare.com
"""

import sys
import json
import httpx
import asyncio
from typing import Any


class MCPWorkflowTester:
    """MCP 전체 워크플로 테스트."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0, follow_redirects=True)
        self.data_id = None  # 저장된 데이터 ID

    async def close(self):
        await self.client.aclose()

    async def mcp_call(self, method: str, tool_name: str = None, arguments: dict = None) -> dict | None:
        """MCP JSON-RPC 호출."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
        }
        if tool_name:
            payload["params"] = {"name": tool_name, "arguments": arguments or {}}

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        try:
            resp = await self.client.post(f"{self.base_url}/", json=payload, headers=headers)
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "")
                if "text/event-stream" in content_type:
                    for line in resp.text.split("\n"):
                        if line.startswith("data: "):
                            return json.loads(line[6:])
                if resp.text:
                    return resp.json()
        except Exception as e:
            print(f"  [ERROR] {e}")
        return None

    async def test_1_search_statistics(self) -> bool:
        """1. 키워드 검색 (KOSIS API)."""
        print("\n[1] 통계 검색 (search_statistics)")
        print("-" * 50)

        result = await self.mcp_call("tools/call", "search_statistics", {
            "keyword": "인구",
            "limit": 5
        })

        if result and "result" in result:
            content = result["result"].get("content", [])
            if content:
                text = content[0].get("text", "")
                data = json.loads(text)
                if "results" in data:
                    print(f"  ✅ 검색 결과: {data.get('total_count', 0)}건")
                    for r in data["results"][:3]:
                        print(f"     - {r.get('tbl_nm', 'N/A')} ({r.get('org_nm', '')})")
                    return True
        print("  ❌ 검색 실패")
        return False

    async def test_2_hybrid_search(self) -> bool:
        """2. 하이브리드 검색 (PostgreSQL + Vector)."""
        print("\n[2] 하이브리드 검색 (search_tables_hybrid)")
        print("-" * 50)

        result = await self.mcp_call("tools/call", "search_tables_hybrid", {
            "query": "저출산 고령화 인구 변화",
            "limit": 5,
            "vector_weight": 0.7
        })

        if result and "result" in result:
            content = result["result"].get("content", [])
            if content:
                text = content[0].get("text", "")
                data = json.loads(text)

                if "error" in data:
                    print(f"  ⚠️ {data.get('message', data.get('error'))}")
                    return False

                if "results" in data:
                    print(f"  ✅ 하이브리드 검색 결과: {len(data['results'])}건")
                    for r in data["results"][:3]:
                        print(f"     - [{r.get('score', 0):.3f}] {r.get('tbl_nm', 'N/A')}")
                    return True
        print("  ❌ 하이브리드 검색 실패")
        return False

    async def test_3_get_data(self) -> bool:
        """3. 데이터 조회."""
        print("\n[3] 데이터 조회 (get_statistics_data)")
        print("-" * 50)

        # 행정구역별 인구수 (통계청)
        result = await self.mcp_call("tools/call", "get_statistics_data", {
            "org_id": "101",
            "tbl_id": "DT_1B040A3",
            "start_date": "2020",
            "end_date": "2023",
            "format": "summary"
        })

        if result and "result" in result:
            content = result["result"].get("content", [])
            if content:
                text = content[0].get("text", "")
                data = json.loads(text)

                # summary 형식 응답 처리
                if "summary" in data:
                    summary = data["summary"]
                    print(f"  ✅ 데이터 조회 성공")
                    print(f"     - 레코드 수: {summary.get('total_records', 'N/A')}")
                    print(f"     - 기간: {summary.get('period_range', 'N/A')}")
                    print(f"     - 항목: {', '.join(summary.get('items', [])[:3])}")
                    if "data_id" in data:
                        self.data_id = data["data_id"]
                    return True
                elif "data_id" in data:
                    self.data_id = data["data_id"]
                    print(f"  ✅ 데이터 조회 성공 (data_id: {self.data_id})")
                    return True
                elif "error" in data:
                    print(f"  ⚠️ API 오류: {data.get('error')}")
                    return False

        print("  ❌ 데이터 조회 실패")
        return False

    async def test_4_visualization(self) -> bool:
        """4. 시각화 생성 (R2 업로드)."""
        print("\n[4] 시각화 생성 (execute_visualization)")
        print("-" * 50)

        if not self.data_id:
            print("  ⚠️ data_id 없음, 샘플 데이터로 테스트")
            # 샘플 데이터로 차트 생성
            code = '''
import altair as alt
import pandas as pd

# 샘플 데이터
df = pd.DataFrame({
    "year": ["2020", "2021", "2022", "2023"],
    "population": [51829, 51744, 51628, 51558]
})

chart = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X("year:N", title="연도"),
    y=alt.Y("population:Q", title="인구 (천 명)",
            scale=alt.Scale(zero=False),
            axis=alt.Axis(format=",.0f")),
).properties(
    title="대한민국 총인구 추이",
    width=500,
    height=300
)

return save_chart(chart, "population_trend.html")
'''
        else:
            code = f'''
df = prepare_data(data, numeric_fields=["DT"])
df["인구_천명"] = df["DT"] / 1000

# 연도별 총인구 집계
yearly = df.groupby("PRD_DE")["인구_천명"].sum().reset_index()

chart = alt.Chart(yearly).mark_line(point=True).encode(
    x=alt.X("PRD_DE:N", title="연도"),
    y=alt.Y("인구_천명:Q", title="인구 (천 명)",
            axis=alt.Axis(format=",.0f")),
).properties(title="연도별 인구 추이", width=500, height=300)

return save_chart(chart, "population_trend.html")
'''

        result = await self.mcp_call("tools/call", "execute_visualization", {
            "code": code,
            "data_id": self.data_id
        })

        if result and "result" in result:
            content = result["result"].get("content", [])
            if content:
                text = content[0].get("text", "")
                data = json.loads(text)

                # 중첩된 result 구조 처리
                inner_result = data.get("result", data)
                url = inner_result.get("url") if isinstance(inner_result, dict) else None

                if url:
                    print(f"  ✅ 차트 생성 성공!")
                    print(f"     - URL: {url}")

                    # R2 URL인지 확인
                    if "r2.dev" in url:
                        print(f"     - 스토리지: Cloudflare R2 ✅")
                    else:
                        print(f"     - 스토리지: 로컬")
                    return True
                elif data.get("error"):
                    print(f"  ⚠️ 시각화 오류: {data.get('error')}")

        print("  ❌ 시각화 실패")
        return False

    async def test_5_analysis(self) -> bool:
        """5. 분석 실행."""
        print("\n[5] 분석 실행 (execute_analysis)")
        print("-" * 50)

        code = '''
# 샘플 분석
import pandas as pd

df = pd.DataFrame({
    "year": [2020, 2021, 2022, 2023],
    "population": [51829, 51744, 51628, 51558]
})

# 변화율 계산
df["change"] = df["population"].pct_change() * 100

return {
    "summary": {
        "시작연도": 2020,
        "종료연도": 2023,
        "시작인구": f"{df.iloc[0]['population']:,}천 명",
        "종료인구": f"{df.iloc[-1]['population']:,}천 명",
        "총변화율": f"{(df.iloc[-1]['population'] / df.iloc[0]['population'] - 1) * 100:.2f}%",
    },
    "insight": "2020년 대비 2023년 인구가 약 0.52% 감소했습니다."
}
'''

        result = await self.mcp_call("tools/call", "execute_analysis", {
            "code": code,
            "data_id": self.data_id
        })

        if result and "result" in result:
            content = result["result"].get("content", [])
            if content:
                text = content[0].get("text", "")
                data = json.loads(text)

                if "result" in data or "summary" in data:
                    print(f"  ✅ 분석 완료!")
                    result_data = data.get("result", data)
                    if isinstance(result_data, dict):
                        summary = result_data.get("summary", {})
                        for k, v in list(summary.items())[:5]:
                            print(f"     - {k}: {v}")
                        if "insight" in result_data:
                            print(f"     - 인사이트: {result_data['insight'][:50]}...")
                    return True
                elif "error" in data:
                    print(f"  ⚠️ 분석 오류: {data.get('error')}")

        print("  ❌ 분석 실패")
        return False

    async def run_all_tests(self) -> dict:
        """전체 워크플로 테스트."""
        print("=" * 60)
        print("KOSIS MCP Server E2E Workflow Test")
        print(f"Target: {self.base_url}")
        print("=" * 60)

        tests = [
            ("통계 검색", self.test_1_search_statistics),
            ("하이브리드 검색", self.test_2_hybrid_search),
            ("데이터 조회", self.test_3_get_data),
            ("시각화 (R2)", self.test_4_visualization),
            ("분석 실행", self.test_5_analysis),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                if await test_func():
                    passed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"  ❌ 예외 발생: {e}")
                failed += 1

        print("\n" + "=" * 60)
        print(f"E2E Workflow Results: {passed} passed, {failed} failed")
        print("=" * 60)

        return {"passed": passed, "failed": failed}


async def main():
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = "http://localhost:8001"

    tester = MCPWorkflowTester(base_url)

    try:
        summary = await tester.run_all_tests()
        sys.exit(0 if summary["failed"] == 0 else 1)
    finally:
        await tester.close()


if __name__ == "__main__":
    asyncio.run(main())
