# KOSIS MCP Server

KOSIS(국가통계포털) 데이터를 Claude와 다른 LLM에서 직접 조회하고 분석할 수 있는 MCP(Model Context Protocol) 서버입니다.

## Features

- **DISCOVER**: 하이브리드 검색 (벡터 + BM25), 252,890개 테이블 메타데이터
- **FETCH**: 통계 데이터 조회, 필터링, 집계, 청크 처리
- **PRESENT**: 모듈형 Executor (시각화, 분석, 테이블, 리포트)

## Quick Start

### Docker (권장)

```bash
# 1. Clone
git clone https://github.com/sdh/kosis-mcp.git
cd kosis-mcp

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일에 KOSIS_API_KEY 입력

# 3. 실행
docker-compose up -d

# 4. 확인
curl http://localhost:8000/health
```

### 수동 설치

```bash
# 의존성 설치
uv sync

# PostgreSQL 실행 (별도 필요)
# 메타데이터 로드
uv run python scripts/load_metadata.py

# 서버 실행
DATABASE_URL="postgresql://..." uv run uvicorn mcp_server.app:app --port 8000
```

## Configuration

### 환경 변수

```bash
# 필수
KOSIS_API_KEY=your-api-key              # KOSIS OpenAPI 키
DATABASE_URL=postgresql://user:pass@host/db  # PostgreSQL

# 선택
OPENAI_API_KEY=sk-...                   # 벡터 검색용 임베딩
KOSIS_ARTIFACTS_DIR=/tmp/kosis_artifacts  # 아티팩트 저장
KOSIS_BASE_URL=http://localhost:8000    # 아티팩트 URL
```

## Claude Desktop Integration

### 방법 1: HTTP 모드 (Docker)

```json
{
  "mcpServers": {
    "kosis-mcp": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### 방법 2: stdio 모드

```json
{
  "mcpServers": {
    "kosis-mcp": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "src/mcp_server/server.py"],
      "env": {
        "KOSIS_API_KEY": "your-api-key"
      }
    }
  }
}
```

## Available Tools

### Layer 1: DISCOVER

| Tool | Description |
|------|-------------|
| `search_tables_hybrid` | 하이브리드 검색 (벡터 + BM25 + RRF) |
| `browse_categories` | 카테고리/주제 브라우징 |
| `get_table_metadata` | 테이블 구조 및 분류 조회 |
| `get_available_values` | 분류항목 값 목록 |

### Layer 2: FETCH

| Tool | Description |
|------|-------------|
| `get_statistics_data` | KOSIS API 데이터 조회 |
| `filter_statistics` | 데이터 필터링 |
| `aggregate_statistics` | 그룹별 집계 |
| `list_stored_data` | 저장된 데이터 목록 |
| `read_stored_data` | 청크 단위 데이터 읽기 |

### Layer 3: PRESENT (Modular Executors)

| Tool | Description |
|------|-------------|
| `execute_visualization` | Altair 차트 생성 (URL 반환) |
| `execute_analysis` | 통계 분석 (변화율, CAGR 등) |
| `execute_table` | HTML 테이블 생성 |
| `execute_report` | 복합 리포트 (차트+분석+테이블) |

## Usage Examples

### 하이브리드 검색

```
"인구 관련 통계표를 찾아줘"
→ search_tables_hybrid("인구")
→ 벡터 유사도 + BM25 키워드 검색 결합
```

### 데이터 조회 및 시각화

```
"서울 인구 추이를 차트로 보여줘"
→ get_statistics_data(org_id="101", tbl_id="DT_1B040A3", ...)
→ execute_visualization(code="...", data=...)
→ http://localhost:8000/artifacts/charts/xxx.html
```

### 복합 리포트 생성

```
"서울, 부산, 대구 인구 비교 리포트를 만들어줘"
→ execute_analysis(...) - 비교 분석
→ execute_visualization(...) - 비교 차트
→ execute_table(...) - 비교 테이블
→ execute_report(...) - 조합
→ http://localhost:8000/artifacts/reports/xxx.html
```

## Development

```bash
# 테스트
uv run pytest tests/ -v

# MCP Inspector
uv run fastmcp dev src/mcp_server/server.py

# 타입 체크
uv run mypy src/

# E2E 시나리오 테스트 (Claude Code)
/test-mcp
```

## Architecture

```
┌─────────────────────────────────────────┐
│          FastAPI + FastMCP              │
│  ┌─────────────────────────────────────┐│
│  │ Layer 3: Modular Executors          ││
│  │  visualization | analysis | report  ││
│  └─────────────────────────────────────┘│
│  ┌─────────────────────────────────────┐│
│  │ Layer 2: Data Operations            ││
│  │  fetch | filter | aggregate         ││
│  └─────────────────────────────────────┘│
│  ┌─────────────────────────────────────┐│
│  │ Layer 1: Discovery                  ││
│  │  hybrid_search | metadata           ││
│  └─────────────────────────────────────┘│
└─────────────────────────────────────────┘
         │              │
         ▼              ▼
┌─────────────┐  ┌─────────────┐
│ PostgreSQL  │  │ KOSIS API   │
│ + pgvector  │  │             │
└─────────────┘  └─────────────┘
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Links

- [KOSIS 국가통계포털](https://kosis.kr/)
- [KOSIS OpenAPI 안내](https://kosis.kr/openapi/)
- [FastMCP Documentation](https://gofastmcp.com/)
- [MCP Protocol](https://modelcontextprotocol.io/)
