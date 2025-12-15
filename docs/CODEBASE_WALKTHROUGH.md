# KOSIS MCP Server - 코드베이스 워크쓰루

> 이 문서는 프로젝트의 전체 구조와 데이터 흐름을 설명합니다.

---

## 1. 프로젝트 개요

### 1.1 프로젝트 목적
KOSIS(국가통계포털) OpenAPI의 데이터를 **MCP(Model Context Protocol)** 서버로 제공하여,
Claude 같은 LLM이 한국 공공통계 데이터를 조회/분석/시각화할 수 있게 합니다.

### 1.2 핵심 철학 (MCP_PATTERN.md)
```
❌ 안티패턴: API → 전체 데이터 → LLM 컨텍스트 (토큰 폭발!)
✅ 권장 패턴: API → 서버 저장 → 요약만 LLM에 → 필요시 청크 요청
```

**핵심 원칙**: 데이터는 서버에, 요약만 모델에

---

## 2. 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MCP Server                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                      server.py + app.py                              │ │
│  │   @mcp.tool() 데코레이터로 도구 등록 + FastAPI HTTP 서버             │ │
│  └───────────────────────────────┬─────────────────────────────────────┘ │
│                                  │                                        │
│  ┌───────────────────────────────┴─────────────────────────────────────┐ │
│  │  Layer 1: DISCOVER          │  Layer 2: FETCH                       │ │
│  │  ┌─────────────────────┐    │  ┌─────────────────────┐              │ │
│  │  │ search_tables_hybrid│    │  │ get_statistics_data │              │ │
│  │  │ (벡터 + BM25 검색)  │    │  │ filter_statistics   │              │ │
│  │  │ browse_categories   │    │  │ aggregate_statistics│              │ │
│  │  │ get_table_metadata  │    │  │ list_stored_data    │              │ │
│  │  └─────────────────────┘    │  └─────────────────────┘              │ │
│  └───────────────────────────────┬─────────────────────────────────────┘ │
│                                  │                                        │
│  ┌───────────────────────────────┴─────────────────────────────────────┐ │
│  │                      Layer 3: PRESENT (모듈형 Executors)            │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌─────────────┐│ │
│  │  │ execute_     │ │ execute_     │ │ execute_     │ │ execute_    ││ │
│  │  │ visualization│ │ analysis     │ │ table        │ │ report      ││ │
│  │  │ (Altair)     │ │ (통계분석)   │ │ (HTML테이블) │ │ (조합)      ││ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └─────────────┘│ │
│  └─────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                    Infrastructure Modules                            │ │
│  │  ┌─────────┐  ┌──────────┐  ┌────────────┐  ┌─────────────────────┐│ │
│  │  │database │  │embeddings│  │hybrid_     │  │ visualize.py        ││ │
│  │  │.py      │  │.py       │  │search.py   │  │ (Altair 차트)       ││ │
│  │  │(Postgres)│ │(OpenAI)  │  │(Vector+FTS)│  │ save_chart → URL    ││ │
│  │  └─────────┘  └──────────┘  └────────────┘  └─────────────────────┘│ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                   ↓
                     ┌───────────────────────────┐
                     │     PostgreSQL + pgvector │
                     │   (252,890 테이블 메타)    │
                     └───────────────────────────┘
                                   ↓
                     ┌───────────────────────────┐
                     │      KOSIS OpenAPI        │
                     │    kosis.kr/openapi       │
                     └───────────────────────────┘
```

---

## 3. 파일별 역할

### 3.1 MCP Server Layer

| 파일 | 역할 | 주요 내용 |
|------|------|----------|
| `src/mcp_server/server.py` | MCP 도구 정의 | 25+ 도구 등록, `@mcp.tool()` |
| `src/mcp_server/app.py` | FastAPI HTTP 앱 | 정적 파일 서빙, health check |

### 3.2 Core Modules (`src/kosis_tools/`)

| 파일 | 역할 | 주요 함수/클래스 |
|------|------|------------------|
| `report_tools.py` | 데이터 조회/분석 | `fetch_data()`, `filter_data()`, `aggregate_data()` |
| `code_executor.py` | 범용 코드 실행 | `execute_code()` |
| `visualize.py` | Altair 시각화 | `create_chart()`, `save_chart()` → URL 반환 |

### 3.3 Modular Executors (`src/kosis_tools/executors/`)

| 파일 | 역할 | 내장 가이드라인 |
|------|------|----------------|
| `visualization.py` | 차트 생성 | 천 단위, `format=",.0f"`, 과학적표기법 금지 |
| `analysis.py` | 통계 분석 | `calc_change_rate()`, `calc_cagr()`, `to_thousand()` |
| `table.py` | HTML 테이블 | 스타일링, 숫자 포맷팅 |
| `report.py` | 리포트 조합 | `build_report()` - 차트+분석+테이블 |

### 3.4 Infrastructure (`src/kosis_tools/`)

| 파일 | 역할 | 주요 내용 |
|------|------|----------|
| `database.py` | PostgreSQL 연결 | `DatabasePool`, 커넥션 풀 관리 |
| `embeddings.py` | OpenAI 임베딩 | `text-embedding-3-small`, 1536 차원 |
| `hybrid_search.py` | 하이브리드 검색 | 벡터(pgvector) + BM25(FTS) + RRF |

---

## 4. 데이터 흐름

### 4.1 시나리오: 지역별 인구 비교 분석

```
[사용자: "서울, 부산, 대구 인구를 비교해줘"]
     │
     ▼
┌─────────────────────────────────────────────────────┐
│ Step 1: search_tables_hybrid("시도별 인구")          │
│   → hybrid_search.py → PostgreSQL (벡터 + BM25)     │
│   → 결과: [{tbl_id: "DT_1B040A3", ...}]             │
└─────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────┐
│ Step 2: get_statistics_data(org_id, tbl_id, ...)    │
│   → KOSIS API 호출                                   │
│   → 서버에 데이터 저장 (data_id 반환)                │
└─────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────┐
│ Step 3: execute_analysis(code, data=...)            │
│   → executors/analysis.py                           │
│   → 지역별 변화율 계산                               │
│   → {summary: {...}, insights: [...]}               │
└─────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────┐
│ Step 4: execute_visualization(code, data=...)       │
│   → executors/visualization.py → Altair             │
│   → save_chart() → URL 반환                         │
│   → http://localhost:8000/artifacts/charts/...html  │
└─────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────┐
│ Step 5: execute_report(code, context={...})         │
│   → executors/report.py                             │
│   → 분석 + 차트 + 테이블 조합                        │
│   → http://localhost:8000/artifacts/reports/...html │
└─────────────────────────────────────────────────────┘
     │
     ▼
[LLM 응답 + 리포트 URL]
```

---

## 5. MCP 도구 레이어 설계

### 5.1 Layer 1: DISCOVER (데이터 탐색)

| 도구 | 설명 | 반환 |
|------|------|------|
| `search_tables_hybrid` | 하이브리드 검색 (벡터+BM25) | 테이블 목록 |
| `browse_categories` | 카테고리 브라우징 | 분류 트리 |
| `get_table_metadata` | 테이블 구조 정보 | 필드, 분류, 기간 |
| `get_available_values` | 분류항목 값 목록 | 지역/항목 코드 |

### 5.2 Layer 2: FETCH (데이터 조회)

| 도구 | 설명 | 반환 |
|------|------|------|
| `get_statistics_data` | 통계 데이터 조회 | data_id + 요약 |
| `filter_statistics` | 조건 필터링 | 필터링된 레코드 |
| `aggregate_statistics` | 그룹 집계 | 집계된 레코드 |
| `list_stored_data` | 저장된 데이터 목록 | data_id 리스트 |
| `read_stored_data` | 청크 단위 읽기 | 데이터 청크 |

### 5.3 Layer 3: PRESENT (모듈형 Executors)

| 도구 | 설명 | 반환 |
|------|------|------|
| `execute_visualization` | 차트 생성 (가이드라인 포함) | `{url, path, type}` |
| `execute_analysis` | 통계 분석 (헬퍼 함수 포함) | `{summary, insights}` |
| `execute_table` | HTML 테이블 (스타일링) | `{html, rows}` |
| `execute_report` | 복합 리포트 조합 | `{url, path}` |

---

## 6. 주요 데이터 구조

### 6.1 KOSIS API 응답 레코드

```python
{
    "TBL_ID": "DT_1B040A3",       # 테이블 ID
    "ORG_ID": "101",              # 기관 ID (101=통계청)
    "PRD_DE": "2023",             # 기간
    "C1_NM": "서울특별시",         # 분류1 이름
    "ITM_NM": "인구수",            # 항목명
    "DT": "9411211",              # ⚠️ 데이터 값 (문자열!)
    "UNIT_NM": "명"               # 단위
}
```

### 6.2 Executor 결과 구조

```python
# execute_visualization 반환
{
    "url": "http://localhost:8000/artifacts/charts/chart.html",
    "path": "/tmp/kosis_artifacts/charts/chart.html",
    "type": "chart"
}

# execute_analysis 반환
{
    "summary": {"2023년 인구": "9,386천 명", "변화율": "-3.5%"},
    "insights": ["서울 인구 5년간 감소 추세"]
}

# execute_report 반환
{
    "url": "http://localhost:8000/artifacts/reports/report.html",
    "path": "/tmp/kosis_artifacts/reports/report.html"
}
```

---

## 7. 환경 변수

```bash
# 필수
KOSIS_API_KEY=your_api_key           # KOSIS OpenAPI 키
DATABASE_URL=postgresql://...         # PostgreSQL 연결

# 선택
OPENAI_API_KEY=sk-...                 # 임베딩용 (하이브리드 검색)
KOSIS_ARTIFACTS_DIR=/tmp/kosis_artifacts  # 아티팩트 저장 경로
KOSIS_BASE_URL=http://localhost:8000  # 아티팩트 URL 베이스
```

---

## 8. 테스트 실행

```bash
# 전체 테스트
uv run pytest tests/ -v

# E2E 테스트만
uv run pytest tests/e2e/ -v

# MCP 서버 도구 테스트
uv run pytest tests/e2e/test_mcp_server_tools.py -v

# 서버 상태 확인
curl http://localhost:8000/health

# E2E 시나리오 테스트 (Claude Code)
/test-mcp
```

---

## 9. 자주 하는 실수

### 9.1 DT 필드가 문자열임

```python
# ❌ 잘못된 사용
total = sum(r["DT"] for r in data)  # 문자열 연결됨!

# ✅ 올바른 사용 (prepare_data 사용)
df = prepare_data(data, numeric_fields=["DT"])
total = df["DT"].sum()
```

### 9.2 과학적 표기법 사용

```python
# ❌ 잘못된 사용 (5.17e+7 표시됨)
y=alt.Y("value:Q")

# ✅ 올바른 사용
y=alt.Y("value:Q", axis=alt.Axis(format=",.0f"))
```

### 9.3 URL 반환 누락

```python
# ❌ 잘못된 사용 (경로만 반환)
chart.save("chart.html")
return {"path": "chart.html"}

# ✅ 올바른 사용 (save_chart 사용)
return save_chart(chart, "chart.html")
# → {"url": "http://...", "path": "...", "type": "chart"}
```

---

## 10. 확장 가이드

### 10.1 새 MCP 도구 추가

```python
# server.py에 추가
@mcp.tool
def my_new_tool(param: str) -> str:
    """도구 설명 (LLM이 읽음)."""
    return "result"
```

### 10.2 새 Executor 추가

```python
# executors/my_executor.py
MY_GUIDE = """
# 가이드라인
- 규칙 1
- 규칙 2
"""

def execute_my_executor(code: str, **kwargs) -> dict:
    from .base import execute_with_context
    return execute_with_context(code, MY_GUIDE, **kwargs)
```

---

*마지막 업데이트: 2025-12-15*
