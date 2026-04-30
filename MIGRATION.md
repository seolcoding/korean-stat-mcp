# Migration Guide: `kosis-mcp` → `korean-stat-mcp` v0.1.0

> 🇰🇷 한국어가 먼저, English follows each section.

This document covers the breaking changes between the private `kosis-mcp` codebase and the first public release `korean-stat-mcp` v0.1.0.

---

## 1. 패키지 이름 변경 / Package rename

`kosis-mcp` → `korean-stat-mcp`. 모든 import는 그대로(`kosis_tools`, `mcp_server`)지만 PyPI/CLI 이름이 바뀌었습니다.

```bash
# 이전 / Before
pip uninstall kosis-mcp
kosis-mcp

# 신규 / Now
pip install korean-stat-mcp
korean-stat-mcp
```

`KOSIS_API_KEY` 환경변수 등 다른 이름은 변경되지 않았습니다.

---

## 2. OpenAI 임베딩 / 하이브리드 검색 제거 / Embeddings removed

`search_tables_hybrid` 도구, `embeddings.py`, `hybrid_search.py`, `pgvector` 스키마는 모두 제거되었습니다. 기본 설치는 더 이상 OpenAI API 키를 요구하지 않습니다.

```python
# 이전 / Before — 더 이상 사용 불가
result = await mcp.call_tool("search_tables_hybrid", {"query": "출산율"})

# 신규 / Now — KOSIS API 자체 검색 사용
result = await mcp.call_tool("search_statistics", {"keyword": "출산율"})
```

PostgreSQL FTS는 여전히 선택 사항으로 남아있습니다 (`pip install korean-stat-mcp[postgres]`).

---

## 3. 큐레이션된 도구 표면 / Curated tool surface

LLM에게 노출되는 도구가 25개 → 16개로 줄었습니다. 내부 도구는 `discover_tools`/`execute_tool` 메타 도구로 호출 가능합니다.

```python
# 이전 / Before — 직접 호출
mcp.call_tool("execute_code", {...})        # 이제 V1_EXPOSED 외부

# 신규 / Now — 메타 도구로 escape hatch
mcp.call_tool("discover_tools", {})         # 전체 목록 조회
mcp.call_tool("execute_tool", {"name": "execute_code", "args": {...}})
```

전체 매핑은 [docs/TOOL_MIGRATION.md](./docs/TOOL_MIGRATION.md) 참조.

---

## 4. 선택 의존성 분리 / Optional extras

`asyncpg`는 더 이상 필수 의존성이 아닙니다.

| 용도 / Use | 명령 / Install |
|---|---|
| 기본 (KOSIS API만) | `pip install korean-stat-mcp` |
| PostgreSQL FTS 추가 | `pip install korean-stat-mcp[postgres]` |
| 전부 / Everything | `pip install korean-stat-mcp[all]` |

---

## 5. 새 도구: `verify_statistics`

LLM이 만든 수치 주장을 KOSIS 원천 데이터와 자동 대조하는 도구가 추가되었습니다.

```python
result = await mcp.call_tool("verify_statistics", {
    "claim": "2023년 서울 인구는 9.4M명",
    "tolerance": 0.01,
})
# {"match": true, "expected": 9386034, "actual": 9400000,
#  "diff_pct": 0.0015, "source_url": "https://kosis.kr/...",
#  "confidence": "high"}
```

---

## 6. 사유 호스팅 레퍼런스 제거 / Private hosting refs removed

`wai-3090ti`, `seolcoding.com`, 임시 Cloudflare Tunnel URL 등은 모두 `${KOSIS_MCP_URL}` 환경변수 또는 중립적 placeholder로 대체되었습니다. 자체 호스팅 가이드는 [deploy/README.md](./deploy/README.md) 참조.

---

## 7. 새 CLI 플래그 / New CLI flags

```bash
korean-stat-mcp --version    # 0.1.0
korean-stat-mcp --help       # 사용법 출력
korean-stat-mcp --http       # HTTP/SSE 서버 모드 (FastAPI)
korean-stat-mcp              # stdio MCP 모드 (기본)
```

---

## 8. 새 검증 하니스 / New validation harnesses

```bash
# KOSIS API 신뢰도 측정 (10K 샘플 기본 99.38%)
uv run python scripts/validation/run_reliability_test.py --n 100

# LLM이 라우팅 매뉴얼대로 도구를 잘 고르는지 평가
uv run python scripts/validation/run_llm_judge.py
```

자세한 내용은 [docs/VALIDATION_REPORT.md](./docs/VALIDATION_REPORT.md) 참조.

---

## 9. 추가된 KOSIS API 파라미터 / Added KOSIS API params

`statisticsParameterData.do`, `statisticsSearch.do`, `statisticsBigData.do` 등 기존 wrapper에 KOSIS 공개 명세 전수 파라미터가 추가되었습니다 (`newEstPrdCnt`, `prdInterval`, `sort=RANK|DATE`, `format=sdmx|xml|html`, `xls`, `content=html`). 모두 `None` 기본값의 keyword-only 인자라 기존 호출 코드는 변경 없이 동작합니다.

전체 커버리지 매트릭스는 [docs/API_COVERAGE.md](./docs/API_COVERAGE.md).

---

## 신뢰도 / Reliability

KOSIS API 호출 성공률 **99.38%** (10,000 샘플 테스트, Phase 4.5에서 측정)는 그대로 유지됩니다. 모든 신규 파라미터는 기본값이 비활성이라 기존 호출 경로는 byte-identical 입니다.

---

## 0.2.0 — Hosted instance + per-request API key

A public hosted endpoint at `https://korean-stat-mcp.seolcoding.com/mcp` is now available. URL form:

```
https://korean-stat-mcp.seolcoding.com/mcp?apiKey=<your KOSIS OpenAPI key>
```

For self-hosted deployments **nothing changes** — `KOSIS_API_KEY` env var still works exactly as before. The new behavior:

- HTTP requests with `?apiKey=` use that per-request key (env is ignored for that request).
- HTTP requests with no `?apiKey=` fall back to env.
- Without either, `/mcp` returns `401 missing_api_key` instead of failing deep inside a tool.

stdio mode is unchanged.
