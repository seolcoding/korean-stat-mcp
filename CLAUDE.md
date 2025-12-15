# KOSIS MCP Server - Claude Code Instructions

> **이 문서는 Claude Code가 이 프로젝트를 이해하고 작업하기 위한 최상위 엔트리포인트입니다.**

---

## 문서 인덱스 (Document Hierarchy)

### 핵심 문서 (반드시 읽기)

| 우선순위 | 문서 | 목적 | 언제 참조 |
|:--------:|------|------|----------|
| 1 | **[MCP_PATTERN.md](./MCP_PATTERN.md)** | 대용량 데이터 처리 핵심 패턴 | 모든 MCP 도구 개발 시 |
| 2 | **[docs/ARCHITECTURE_DESIGN.md](./docs/ARCHITECTURE_DESIGN.md)** | 전체 시스템 아키텍처 | 새 기능 설계 시 |
| 3 | **[docs/CODEBASE_WALKTHROUGH.md](./docs/CODEBASE_WALKTHROUGH.md)** | 코드베이스 구조, 파일 역할 | 코드 수정 시 |

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
| [docs/METADATA_OPTIMIZATION_STRATEGY.md](./docs/METADATA_OPTIMIZATION_STRATEGY.md) | 최적화 전략 |

### 배포 & 인프라 문서 (작성 예정)

| 문서 | 내용 | 상태 |
|------|------|------|
| [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) | 배포 전략, Docker, R2, Tailscale | 🚧 작성 예정 |
| [docs/HYBRID_SEARCH.md](./docs/HYBRID_SEARCH.md) | PostgreSQL + pgvector + 임베딩 | 🚧 작성 예정 |
| [ROADMAP.md](./ROADMAP.md) | 구현 로드맵, 마일스톤 | 🚧 작성 예정 |

---

## 프로젝트 현황 (Current State)

### 완료된 기능 ✅

- **MCP 서버 기본 구조** (FastMCP 기반)
- **KOSIS API 연동** (검색, 조회, 메타데이터)
- **Code Execution 패턴** (`execute_code` 도구)
- **시각화** (Altair 기반 차트 생성)
- **리포트 생성** (HTML 리포트)
- **메타데이터 카탈로그** (103,796개 테이블, 159MB JSON)

### 진행 중인 작업 🚧

- **배포 아키텍처 설계**
  - Docker 컨테이너화
  - Cloudflare R2 (스태틱 파일 CDN)
  - 연구실 서버 + Tailscale (외부 접근)

- **하이브리드 검색 시스템**
  - PostgreSQL + pgvector
  - OpenAI 임베딩 (text-embedding-3-small)
  - 벡터 + BM25 하이브리드 검색
  - 시맨틱 테이블 추천

---

## 핵심 제약사항 (Constraints)

### 1. 대용량 데이터 처리 원칙

```
❌ 안티패턴: API → 전체 데이터 → LLM 컨텍스트 (토큰 폭발)
✅ 권장 패턴: API → 서버 저장 → 요약만 LLM에 → 필요시 청크 요청
```

### 2. 기술 스택

| 영역 | 기술 | 비고 |
|------|------|------|
| 시각화 | **Altair** | Plotly 대신 사용 (가볍고 간결) |
| 서버 | **FastMCP** | MCP 서버 프레임워크 |
| DB (예정) | **PostgreSQL + pgvector** | 하이브리드 검색용 |
| 임베딩 (예정) | **OpenAI text-embedding-3-small** | 한국어 성능 우수 |

### 3. 금지 사항

- **Playwright/Selenium/Puppeteer** 사용 금지
- 모든 데이터 수집은 API 또는 `requests.get`으로
- 브라우저 자동화 없이 빠르게 파싱 가능해야 함

---

## KOSIS API Quick Reference

### 핵심 엔드포인트

| 엔드포인트 | 용도 |
|-----------|------|
| `statisticsParameterData.do` | 실제 데이터 조회 |
| `statisticsList.do` | 통계 목록 조회 |
| `statHtmlContent.do` | 테이블 상세 HTML |

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

## 시각화 검증 시스템

`execute_code` 도구는 빈 차트 데이터를 자동 감지합니다.

### 검증 실패 시 응답

```json
{
  "success": false,
  "error": "VISUALIZATION_VALIDATION_ERROR",
  "data_signature": {
    "fields": {"PRD_DE": {...}, "C1_NM": {...}, "DT": {...}},
    "sample_records": [...]
  },
  "fix_hints": [
    "prepare_data() 호출 시 올바른 numeric_fields 지정",
    "DT 필드는 문자열 - 숫자 연산 전 형변환 필요"
  ]
}
```

### 클라이언트 대응

1. `data_signature` 참조
2. 올바른 필드명/타입으로 코드 재작성
3. 다시 `execute_code` 호출

---

## 디렉토리 구조

```
kosis-data-processor/
├── src/
│   ├── mcp_server/
│   │   └── server.py          # MCP 서버 메인 (도구 정의)
│   └── kosis_tools/
│       ├── report_tools.py    # 데이터 조회/분석 함수
│       ├── code_executor.py   # execute_code 구현
│       ├── visualize.py       # Altair 시각화
│       └── ...
├── kosis_data/
│   └── kosis_metadata_final.json  # 메타데이터 카탈로그 (103K 테이블)
├── docs/                      # 상세 문서
├── tests/                     # 테스트
└── CLAUDE.md                  # 이 문서 (엔트리포인트)
```

---

## 참고 링크

- **KOSIS 100대 지표**: https://kosis.kr/visual/nsportalStats/main.do
- **k-stat 메타데이터**: https://www.k-stat.go.kr/metasvc/msba100/statsdcdta
