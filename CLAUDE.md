# KOSIS MCP Server - Claude Code Instructions

> **이 문서는 Claude Code가 이 프로젝트를 이해하고 작업하기 위한 최상위 엔트리포인트입니다.**

---

## 문서 인덱스 (Document Hierarchy)

### 핵심 문서 (반드시 읽기)

| 우선순위 | 문서 | 목적 | 언제 참조 |
|:--------:|------|------|----------|
| 1 | **[PRD.md](./PRD.md)** | 제품 요구사항, 유저 스토리, 수락 기준 | 기능 구현 전 |
| 2 | **[MCP_PATTERN.md](./MCP_PATTERN.md)** | 대용량 데이터 처리 핵심 패턴 | 모든 MCP 도구 개발 시 |
| 3 | **[docs/ARCHITECTURE_DESIGN.md](./docs/ARCHITECTURE_DESIGN.md)** | 전체 시스템 아키텍처 | 새 기능 설계 시 |
| 4 | **[docs/CODEBASE_WALKTHROUGH.md](./docs/CODEBASE_WALKTHROUGH.md)** | 코드베이스 구조, 파일 역할 | 코드 수정 시 |

### API & 데이터 문서

| 문서 | 내용 | 언제 참조 |
|------|------|----------|
| [docs/KOSIS_API_REFERENCE.md](./docs/KOSIS_API_REFERENCE.md) | KOSIS API 엔드포인트, 파라미터, 응답 필드 | API 호출/파싱 시 |
| [docs/LARGE_DATA_MCP_PATTERNS.md](./docs/LARGE_DATA_MCP_PATTERNS.md) | execute_code 패턴 상세 | 코드 실행 기능 개발 시 |

### 메타데이터 문서

| 문서 | 내용 |
|------|------|
| [docs/METADATA_COLLECTION_GUIDE.md](./docs/METADATA_COLLECTION_GUIDE.md) | 메타데이터 수집 방법 |
| [docs/METADATA_JSON_SCHEMA.md](./docs/METADATA_JSON_SCHEMA.md) | JSON 스키마 정의 |

### 사용자 문서

| 문서 | 내용 |
|------|------|
| [docs/USER_GUIDE.md](./docs/USER_GUIDE.md) | 사용자 가이드, 도구 사용법, 예제 |

### 배포 & 인프라 문서

| 문서 | 내용 | 상태 |
|------|------|------|
| [docs/ARCHITECTURE_DESIGN.md](./docs/ARCHITECTURE_DESIGN.md) | 전체 시스템 아키텍처, 레이어 구조, 데이터 흐름 | ✅ 완료 |
| [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) | FastMCP HTTP, Docker, PostgreSQL | ✅ 완료 |
| [docs/HYBRID_SEARCH.md](./docs/HYBRID_SEARCH.md) | pgvector HNSW, BM25 FTS, RRF 결합 | ✅ 완료 |

---

## 프로젝트 현황 (Current State)

### 완료된 기능 ✅

**Phase 1-2: Core MCP** ✅ 완료
- MCP 서버 기본 구조 (FastMCP 기반)
- KOSIS API 연동 (검색, 조회, 메타데이터)
- Code Execution 패턴 (`execute_code` 도구)
- 시각화 (Altair 기반 차트 생성)
- 리포트 생성 (HTML 리포트)

**Phase 3: Production Infrastructure** ✅ 완료
- PostgreSQL + pgvector (252,890 테이블 메타데이터)
- 하이브리드 검색 (벡터 + BM25 + RRF)
- OpenAI 임베딩 (`text-embedding-3-small`)
- FastAPI HTTP 서버 (`app.py`)
- 정적 파일 서빙 (차트/리포트 URL)
- Docker 컨테이너화

**Modular Executors** ✅ 완료
- `execute_visualization` - 차트 생성 (천 단위, 과학적표기법 금지)
- `execute_analysis` - 통계 분석 (변화율, CAGR)
- `execute_table` - HTML 테이블 (스타일링)
- `execute_report` - 복합 리포트 (차트+분석+테이블)

### 다음 단계 (Phase 4) 📋
- Tailscale 또는 Cloudflare Tunnel 설정
- 외부에서 MCP 서버 접근 가능하게
- 인증/권한 설정

---

## 핵심 제약사항 (Constraints)

### 1. 대용량 데이터 처리 원칙

```
❌ 안티패턴: API → 전체 데이터 → LLM 컨텍스트 (토큰 폭발)
✅ 권장 패턴: API → 서버 저장 → 요약만 LLM에 → 필요시 청크 요청
```

### 2. 숫자 포맷 규칙

| 항목 | 규칙 | 예시 |
|------|------|------|
| 인구 | 천 명 단위 | `9,386천 명` (not `9386320`) |
| Y축 | `format=",.0f"` | 천 단위 구분자 |
| 과학적 표기법 | **금지** | `5.17e+7` ❌ |

### 3. 기술 스택

| 영역 | 기술 | 비고 |
|------|------|------|
| 시각화 | **Altair** | Plotly/Matplotlib 대신 |
| 서버 | **FastMCP + FastAPI** | MCP + HTTP 듀얼 모드 |
| DB | **PostgreSQL + pgvector** | 하이브리드 검색 |
| 임베딩 | **OpenAI text-embedding-3-small** | 1536 차원 |

### 4. 금지 사항

- **Playwright/Selenium/Puppeteer** 사용 금지
- 모든 데이터 수집은 API 또는 `requests.get`으로
- 브라우저 자동화 없이 빠르게 파싱 가능해야 함

---

## 디렉토리 구조

```
kosis-data-processor/
├── src/
│   ├── mcp_server/
│   │   ├── server.py              # MCP 서버 (도구 정의)
│   │   └── app.py                 # FastAPI HTTP 앱
│   └── kosis_tools/
│       ├── report_tools.py        # 데이터 조회/분석
│       ├── code_executor.py       # execute_code 범용
│       ├── visualize.py           # Altair 시각화
│       ├── executors/             # 모듈형 실행기
│       │   ├── visualization.py   # 차트 (가이드라인 포함)
│       │   ├── analysis.py        # 분석 (통계 함수)
│       │   ├── table.py           # 테이블 (스타일링)
│       │   └── report.py          # 리포트 (조합)
│       ├── database.py            # PostgreSQL 연결
│       ├── embeddings.py          # OpenAI 임베딩
│       └── hybrid_search.py       # 벡터+BM25 검색
├── data/
│   └── metadata_api/
│       └── tables.json            # 메타데이터 (252,890 테이블)
├── migrations/
│   └── init.sql                   # PostgreSQL 스키마
├── scripts/
│   └── load_metadata.py           # DB 로드 스크립트
├── .claude/
│   └── commands/
│       └── test-mcp.md            # E2E 테스트 슬래시 커맨드
├── Dockerfile                     # 컨테이너 빌드
├── docker-compose.yml             # 로컬 개발 환경
└── CLAUDE.md                      # 이 문서
```

---

## KOSIS API Quick Reference

### 핵심 엔드포인트

| 엔드포인트 | 용도 |
|-----------|------|
| `statisticsParameterData.do` | 실제 데이터 조회 |
| `statisticsList.do` | 통계 목록 조회 |

### 데이터 응답 필드

| 필드 | 설명 | 예시 |
|------|------|------|
| `PRD_DE` | 기간 | `2023`, `202401` |
| `C1_NM` | 분류1 (주로 지역) | `서울특별시` |
| `DT` | **데이터 값 (문자열!)** | `"9411211"`, `"-"` |
| `ITM_NM` | 항목명 | `총인구` |
| `UNIT_NM` | 단위 | `명`, `%` |

> ⚠️ **`DT`는 문자열입니다.** `"-"`, `"*"` 등 특수값 처리 필요!

---

## 서버 실행

### 로컬 개발 (Docker Compose)

```bash
# PostgreSQL + 서버 시작
docker-compose up -d

# 또는 수동 실행
DATABASE_URL="postgresql://kosis:kosis_dev_password@localhost:5432/kosis" \
KOSIS_ARTIFACTS_DIR="/tmp/kosis_artifacts" \
KOSIS_BASE_URL="http://localhost:8000" \
uv run uvicorn mcp_server.app:app --port 8000
```

### 테스트

```bash
# 서버 상태 확인
curl http://localhost:8000/health

# E2E 테스트 슬래시 커맨드
/test-mcp
```

---

## 모듈형 Executor 사용법

### execute_visualization

```python
# 천 단위 + 과학적표기법 금지 자동 적용
code = '''
df = prepare_data(data, numeric_fields=["DT"])
df["인구_천명"] = df["DT"] / 1000

chart = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X("PRD_DE:N", title="연도"),
    y=alt.Y("인구_천명:Q", title="인구 (천 명)",
            axis=alt.Axis(format=",.0f")),  # 필수!
)
return save_chart(chart, "population.html")
'''
```

### execute_analysis

```python
# 헬퍼 함수: calc_change_rate, calc_cagr, to_thousand
code = '''
df = prepare_data(data, numeric_fields=["DT"])
pop_2023 = df[df["PRD_DE"] == "2023"]["DT"].iloc[0]
pop_2019 = df[df["PRD_DE"] == "2019"]["DT"].iloc[0]

return {
    "summary": {
        "2023년 인구": f"{to_thousand(pop_2023):,.0f}천 명",
        "변화율": f"{calc_change_rate(pop_2023, pop_2019):.1f}%",
    }
}
'''
```

### execute_report (조합)

```python
# 분석 + 차트 + 테이블 조합
code = '''
return build_report(
    title="인구 분석 리포트",
    analysis=analysis,   # execute_analysis 결과
    charts=charts,       # execute_visualization 결과 배열
    tables=tables,       # execute_table 결과 배열
    source="통계청 KOSIS",
)
'''
```

---

## 참고 링크

- **KOSIS 100대 지표**: https://kosis.kr/visual/nsportalStats/main.do
- **FastMCP 문서**: https://gofastmcp.com/
- **Altair 문서**: https://altair-viz.github.io/

---

*마지막 업데이트: 2025-12-15*
