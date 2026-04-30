# KOSIS MCP Server - 아키텍처 설계서

> **버전**: 3.0 (Phase 4 - 프로덕션 배포 완료)
> **최종 수정일**: 2025-12-20
> **관련 문서**: [DEPLOYMENT.md](./DEPLOYMENT.md), [HYBRID_SEARCH.md](./HYBRID_SEARCH.md)

---

## 1. 시스템 개요

### 1.1 목적

KOSIS MCP Server는 **국가통계포털(KOSIS) OpenAPI**를 **MCP(Model Context Protocol)** 도구로 래핑하여,
AI 에이전트(Claude 등)가 한국 통계 데이터를 **탐색, 조회, 분석, 시각화**할 수 있게 합니다.

### 1.2 핵심 설계 원칙

| 원칙 | 설명 | 구현 |
|------|------|------|
| **LLM 컨텍스트 절감** | 대용량 데이터를 직접 전달하지 않음 | 서버사이드 처리, 요약 반환 |
| **점진적 공개** | summary → sample → chunk 순서 | 3-Layer Tool 구조 |
| **Stateless 설계** | 수평 확장 가능 | FastMCP stateless_http=True |
| **로컬 아티팩트 제공** | 생성 파일을 서버 로컬 디렉토리에 저장 | `/artifacts/*` 정적 서빙 |

```
❌ 안티패턴: API → 전체 데이터 → LLM 컨텍스트 (토큰 폭발)
✅ 권장 패턴: API → 서버 저장 → Code Execution → 아티팩트 URL
```

### 1.3 기술 스택

```
┌─────────────────────────────────────────────────────────────────────────┐
│  MCP Client (Claude, etc.)                                              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │ MCP Protocol (stdio / HTTP)
┌────────────────────────────────▼────────────────────────────────────────┐
│  KOSIS MCP Server                                                       │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  FastMCP (Python 3.12)                                             │ │
│  │  └── uvicorn (ASGI, stateless_http=True)                           │ │
│  ├────────────────────────────────────────────────────────────────────┤ │
│  │  kosis_tools/                                                       │ │
│  │  ├── API Clients (search, data, metadata, transform)               │ │
│  │  ├── Code Executor (sandboxed Python runtime)                      │ │
│  │  └── Visualize (Altair HTML)                                        │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└───────────────┬─────────────────────────────┬───────────────────────────┘
                │                             │
    ┌───────────▼───────────┐     ┌───────────▼───────────┐
    │  PostgreSQL 16        │     │  KOSIS OpenAPI        │
    │  + pgvector           │     │  (kosis.kr)           │
    │  ┌─────────────────┐  │     └───────────────────────┘
    │  │ kosis_tables    │  │
    │  │ (252,890 recs)  │  │
    │  │ + FTS + Vector  │  │
    │  └─────────────────┘  │
    └───────────┬───────────┘
                │
    ┌───────────▼───────────┐
    │  Local Artifacts      │
    │  ├── /charts/         │
    │  ├── /reports/        │
    │  └── /data/           │
    └───────────────────────┘
```

---

## 2. 레이어 아키텍처

### 2.1 전체 구조

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MCP Tool Layer                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   DISCOVER   │  │    FETCH     │  │   EXECUTE    │  │   PRESENT    │ │
│  │              │  │              │  │              │  │              │ │
│  │ search_      │  │ get_         │  │ execute_     │  │ analyze_     │ │
│  │ statistics   │  │ statistics_  │  │ code ⭐      │  │ trend        │ │
│  │              │  │ data         │  │              │  │              │ │
│  │ browse_      │  │              │  │ (pandas,     │  │ create_      │ │
│  │ categories   │  │ filter_      │  │  altair,     │  │ quick_       │ │
│  │              │  │ statistics   │  │  numpy)      │  │ report       │ │
│  │ get_table_   │  │              │  │              │  │              │ │
│  │ metadata     │  │ aggregate_   │  │              │  │ analyze_     │ │
│  │              │  │ statistics   │  │              │  │ comparison   │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘ │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────┘
          │                 │                 │                 │
┌─────────▼─────────────────▼─────────────────▼─────────────────▼─────────┐
│                        Service Layer (kosis_tools/)                      │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────────┐ │
│  │ API Clients     │ │ Data Processing │ │ Code Execution              │ │
│  │ ├─ search.py    │ │ ├─ transform.py │ │ └─ code_executor.py         │ │
│  │ ├─ data.py      │ │ └─ visualize.py │ │    ├─ Sandboxed Runtime     │ │
│  │ ├─ table_meta   │ └─────────────────┘ │    ├─ Data Signature        │ │
│  │ └─ list_cat...  │                     │    └─ Validation            │ │
│  └─────────────────┘                     └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
          │                                           │
┌─────────▼───────────────────────────────────────────▼───────────────────┐
│                        Infrastructure Layer                              │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────────────┐ │
│  │ PostgreSQL      │ │ KOSIS API       │ │ Local Artifacts             │ │
│  │ + pgvector      │ │ (External)      │ │ (/artifacts/*)              │ │
│  └─────────────────┘ └─────────────────┘ └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 MCP Tool Layer 상세

#### Layer 1: DISCOVER (데이터 탐색)

| 도구 | 목적 | 입력 | 출력 |
|------|------|------|------|
| `search_statistics` | 키워드 검색 | keyword, org_id, limit | 테이블 목록 + 기관 분포 |
| `browse_categories` | 카테고리 탐색 | by (org/theme), code | 계층 구조 목록 |
| `get_table_metadata` | 메타데이터 조회 | org_id, tbl_id | 컬럼 정보, 분류값 |
| `get_available_values` | 필터 옵션 조회 | org_id, tbl_id, item_id | 선택 가능한 값 |

#### Layer 2: FETCH (데이터 조회)

| 도구 | 목적 | 입력 | 출력 |
|------|------|------|------|
| `get_statistics_data` | 데이터 조회 | org_id, tbl_id, 기간 등 | **요약** + data_id |
| `filter_statistics` | 필터링 | data_id, conditions | 필터된 요약 |
| `aggregate_statistics` | 집계 | data_id, group_by, agg_fn | 집계 결과 |

> **핵심**: 원본 데이터는 서버에 저장, LLM에게는 요약만 반환

#### Layer 3: EXECUTE (코드 실행) ⭐ 권장

| 도구 | 목적 | 입력 | 출력 |
|------|------|------|------|
| `execute_code` | Python 코드 실행 | code, data_id | 실행 결과 + 아티팩트 URL |

**장점**:
- 토큰 98.7% 절감 (58K → 3K)
- 자유로운 분석 코드 작성
- pandas, altair, numpy 사용 가능

#### Layer 4: PRESENT (미리 정의된 분석)

| 도구 | 목적 | 입력 | 출력 |
|------|------|------|------|
| `analyze_trend` | 추세 분석 | data_id, time_col | 트렌드 인사이트 |
| `analyze_comparison` | 비교 분석 | data_id, group_col | 비교 결과 |
| `analyze_ranking` | 순위 분석 | data_id, value_col | Top-N 순위 |
| `create_quick_report` | HTML 리포트 | data_id, title | 리포트 URL |

---

## 3. 컴포넌트 상세 설계

### 3.1 MCP Server (src/mcp_server/)

```
src/mcp_server/
├── __init__.py
├── __main__.py          # 엔트리포인트 (stdio 모드)
├── server.py            # FastMCP 도구 정의 (~1600 lines)
└── app.py               # HTTP 모드용 ASGI 앱 (신규)
```

**server.py 구조**:
```python
from fastmcp import FastMCP

mcp = FastMCP(
    name="kosis-stats",
    instructions="...",  # 도구 사용 가이드
)

# Layer 1: DISCOVER
@mcp.tool
def search_statistics(keyword: str, ...) -> str: ...

# Layer 2: FETCH
@mcp.tool
def get_statistics_data(org_id: str, tbl_id: str, ...) -> str: ...

# Layer 3: EXECUTE
@mcp.tool
def execute_code(code: str, data_id: str = None) -> str: ...

# Layer 4: PRESENT
@mcp.tool
def analyze_trend(data_id: str, ...) -> str: ...
```

### 3.2 KOSIS Tools (src/kosis_tools/)

```
src/kosis_tools/
├── __init__.py          # 공개 API 정의
├── config.py            # 설정 (rate limit, timeout, API keys)
├── base.py              # HTTP 클라이언트 베이스 클래스
│
├── # API Clients
├── search.py            # statisticsList.do (키워드 검색)
├── data.py              # statisticsParameterData.do (데이터 조회)
├── table_meta.py        # statisticsMetaData.do (메타데이터)
├── list_categories.py   # statisticsList.do (카테고리)
├── stats_explanation.py # 통계설명
├── kstat_metadata.py    # k-stat 메타데이터
├── big_data.py          # 대용량 데이터 API
├── key_indicators.py    # 100대 지표 API
│
├── # Data Processing
├── transform.py         # pandas 변환/집계
├── visualize.py         # Altair 시각화
├── code_executor.py     # 코드 샌드박스 실행 ⭐
│
├── # Report Generation
├── report_tools.py      # 리포트 도구 모음
├── report_generator.py  # HTML 리포트 생성
├── report_template.py   # 템플릿
├── story_templates.py   # 스토리 템플릿
│
├── # Metadata Management
├── cache_builder.py     # 메타데이터 캐시 빌드
├── metadata_fetcher.py  # 비동기 수집
├── metadata_enricher.py # 보강
└── metadata_models.py   # 데이터 모델
```

### 3.3 Code Executor 상세

**목적**: LLM이 작성한 Python 코드를 안전하게 실행

```
┌─────────────────────────────────────────────────────────────────┐
│  execute_code(code, data_id)                                    │
└────────────────────────────────┬────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  1. 데이터 로드          │
                    │  data = load(data_id)   │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  2. 샌드박스 실행        │
                    │  ┌────────────────────┐ │
                    │  │ Allowed:           │ │
                    │  │ - pandas           │ │
                    │  │ - altair           │ │
                    │  │ - numpy            │ │
                    │  │ - prepare_data()   │ │
                    │  │ - save_chart()     │ │
                    │  └────────────────────┘ │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  3. 결과 검증           │
                    │  - 빈 차트 감지         │
                    │  - 에러 수집            │
                    └────────────┬────────────┘
                                 │
             ┌───────────────────┼───────────────────┐
             ▼                   ▼                   ▼
      ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
      │ Success     │    │ Validation  │    │ Error       │
      │ + URL       │    │ Error +     │    │ + Traceback │
      │             │    │ Fix Hints   │    │             │
      └─────────────┘    └─────────────┘    └─────────────┘
```

**검증 실패 응답**:
```json
{
  "success": false,
  "error": "VISUALIZATION_VALIDATION_ERROR",
  "data_signature": {
    "fields": {"PRD_DE": {"type": "str", "sample": ["2021"]}},
    "sample_records": [...]
  },
  "fix_hints": ["DT 필드는 문자열입니다. 숫자 연산 전 형변환 필요"]
}
```

---

## 4. 데이터 흐름

### 4.1 기본 워크플로우

```
┌─────────────────────────────────────────────────────────────────────────┐
│  User: "최근 5년 출생아수 추이 그래프 만들어줘"                           │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│  Step 1: DISCOVER - search_statistics("출생")                           │
│  → 검색 결과: [{tbl_id: "DT_1B8000F", tbl_nm: "출생아수", ...}]         │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│  Step 2: FETCH - get_statistics_data(org_id="101", tbl_id="DT_1B8000F") │
│  → 요약: {total: 1500, date_range: "2019-2023", data_id: "abc123"}      │
│  → 원본 저장: /tmp/kosis_artifacts/data/abc123.json                     │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│  Step 3: EXECUTE - execute_code(data_id="abc123", code='''              │
│      df = prepare_data(data, numeric_fields=["DT"])                     │
│      chart = alt.Chart(df).mark_line().encode(x="PRD_DE", y="DT")       │
│      return save_chart(chart, "birth_trend.html")                       │
│  ''')                                                                   │
│  → 결과: {url: "https://r2.example.com/charts/birth_trend.html"}        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│  Response to User: "차트를 생성했습니다: [링크]"                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 하이브리드 검색 흐름 (Phase 3)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  User: "경제가 좋아졌는지 알 수 있는 데이터"                              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│  search_tables_hybrid(query="경제가 좋아졌는지")                          │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       │
┌─────────────────┐    ┌─────────────────┐              │
│  Query Embedding│    │  PostgreSQL     │              │
│  (OpenAI API)   │    │  FTS Search     │              │
│  → [0.1, 0.2..] │    │  (BM25)         │              │
└────────┬────────┘    └────────┬────────┘              │
         │                      │                       │
         └───────────┬──────────┘                       │
                     ▼                                  │
         ┌──────────────────────┐                       │
         │  pgvector Cosine     │                       │
         │  Similarity Search   │                       │
         └──────────┬───────────┘                       │
                    │                                   │
                    └───────────────────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  RRF (Reciprocal Rank   │
                    │  Fusion) 결합            │
                    └────────────┬────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│  결과: GDP성장률, 경제활동인구, 고용률, 소비자물가지수 등                  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 5. 인프라 구성

### 5.1 배포 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│  연구실 리눅스 서버 (On-Premise)                                         │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Docker Network: kosis-net                                         │ │
│  │                                                                    │ │
│  │  ┌──────────────────────┐  ┌──────────────────────────────────────┐│ │
│  │  │  kosis-mcp           │  │  postgres                            ││ │
│  │  │  ├─ FastMCP          │  │  ├─ PostgreSQL 16                    ││ │
│  │  │  ├─ uvicorn          │  │  └─ pgvector extension               ││ │
│  │  │  └─ workers: 2       │  │                                      ││ │
│  │  │  Port: 8000          │  │  Port: 5432                          ││ │
│  │  └──────────────────────┘  │  Volume: postgres_data               ││ │
│  │                            └──────────────────────────────────────┘│ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                         │                                │
│                         ┌───────────────┼───────────────┐               │
│                         ▼               ▼               ▼               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  External Services                                                │   │
│  │  ┌─────────────┐  ┌─────────────┐                              │   │
│  │  │ KOSIS API   │  │ OpenAI API  │                              │   │
│  │  │ (kosis.kr)  │  │ (Embedding) │                              │   │
│  │  └─────────────┘  └─────────────┘                              │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  External Access (Phase 4)                                        │   │
│  │  Option A: Tailscale (P2P VPN) - 권장                             │   │
│  │  Option B: Cloudflare Tunnel                                       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Docker Compose 요약

```yaml
services:
  kosis-mcp:
    build: .
    ports: ["8000:8000"]
    environment:
      - FASTMCP_STATELESS_HTTP=true
      - DATABASE_URL=postgresql+asyncpg://...
      - OPENAI_API_KEY
    depends_on: [postgres]

  postgres:
    image: pgvector/pgvector:pg16
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations/init.sql:/docker-entrypoint-initdb.d/init.sql
```

> 상세 설정: [DEPLOYMENT.md](./DEPLOYMENT.md) 참조

---

## 6. 데이터 모델

### 6.1 PostgreSQL 스키마

```sql
CREATE TABLE kosis_tables (
    id              SERIAL PRIMARY KEY,
    tbl_id          VARCHAR(50) UNIQUE NOT NULL,   -- KOSIS 테이블 ID
    org_id          VARCHAR(10) NOT NULL,          -- 기관 ID
    tbl_nm          TEXT NOT NULL,                 -- 테이블명
    org_nm          VARCHAR(100),                  -- 기관명
    contents        TEXT,                          -- 내용 설명
    -- ...
    search_vector   TSVECTOR,                      -- FTS 벡터 (GIN index)
    embedding       VECTOR(1536),                  -- OpenAI 임베딩 (HNSW)
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_kosis_search_vector ON kosis_tables USING GIN (search_vector);
CREATE INDEX idx_kosis_embedding ON kosis_tables USING hnsw (embedding vector_cosine_ops);
```

> 상세 스키마: [HYBRID_SEARCH.md](./HYBRID_SEARCH.md) 참조

### 6.2 파일 저장 구조

```
Local: /app/artifacts/
├── data/
│   └── {data_id}.json
├── charts/
│   └── {chart_id}.html
└── reports/
    └── {report_id}.html
```

---

## 7. 보안

### 7.1 Code Executor 제한

```python
ALLOWED_MODULES = {"pandas", "numpy", "altair", "json", "math", "datetime"}
FORBIDDEN_BUILTINS = {"exec", "eval", "compile", "__import__", "open"}
```

### 7.2 API Key 관리

- 환경변수로 주입 (`KOSIS_API_KEY`, `OPENAI_API_KEY`)
- `.env` 파일은 `.gitignore`에 포함
- Docker secrets 또는 Vault 연동 가능

---

## 8. 확장 로드맵

| Phase | 상태 | 내용 |
|-------|------|------|
| **1** | ✅ 완료 | 기본 API 도구 (search, data, metadata) |
| **2** | ✅ 완료 | execute_code, 시각화, 리포트 |
| **3** | ✅ 완료 | PostgreSQL + 하이브리드 검색 (252,890 테이블) |
| **4** | ✅ 완료 | 외부 접근 (Cloudflare Tunnel, API 성공률 99.8%) |
| **5** | 📋 계획 | 캐싱 레이어, 성능 최적화, 인증/권한 |

---

## 9. 관련 문서

| 문서 | 내용 |
|------|------|
| [DEPLOYMENT.md](./DEPLOYMENT.md) | 배포 상세 가이드 |
| [HYBRID_SEARCH.md](./HYBRID_SEARCH.md) | 하이브리드 검색 설계 |
| [CODEBASE_WALKTHROUGH.md](./CODEBASE_WALKTHROUGH.md) | 코드베이스 안내 |
| [KOSIS_API_REFERENCE.md](./KOSIS_API_REFERENCE.md) | KOSIS API 참조 |
| [../MCP_PATTERN.md](../MCP_PATTERN.md) | 대용량 데이터 처리 패턴 |
