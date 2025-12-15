# KOSIS MCP Server - Product Requirements Document

> **Version**: 1.0
> **Last Updated**: 2025-12-15
> **Status**: Phase 3 Complete, Phase 4 Planning
> **Related Docs**: [CLAUDE.md](./CLAUDE.md), [docs/ARCHITECTURE_DESIGN.md](./docs/ARCHITECTURE_DESIGN.md)

---

## 1. Introduction

KOSIS MCP Server는 **국가통계포털(KOSIS) OpenAPI**를 **MCP(Model Context Protocol)** 도구로 래핑하여, AI 에이전트(Claude 등)가 한국 통계 데이터를 탐색, 조회, 분석, 시각화할 수 있게 하는 서버입니다.

**핵심 가치**: LLM 컨텍스트 효율성 98%+ 달성 (대용량 데이터를 서버에서 처리하고 URL만 반환)

---

## 2. Problem Statement

### 현재 문제점

1. **토큰 폭발 문제**: KOSIS API 응답은 수천~수만 행의 데이터를 반환하며, 이를 LLM 컨텍스트에 직접 전달하면 토큰이 급격히 소모됨
2. **검색 한계**: 키워드 기반 검색만으로는 사용자의 의도를 정확히 파악하기 어려움 (예: "경제가 좋아졌나요?" → 어떤 테이블?)
3. **메타데이터 접근성**: 252,890개 테이블의 메타데이터가 JSON 파일로만 존재, 효율적 검색 불가
4. **시각화 생성**: 데이터를 받아도 차트/리포트 생성까지 여러 단계 필요

### 해결해야 할 핵심 과제

- 대용량 데이터를 LLM 컨텍스트 없이 처리
- 자연어로 관련 통계 테이블 검색
- 코드 실행을 통한 자유로운 분석/시각화
- 프로덕션 환경 배포

---

## 3. Solution Overview

### 3.1 아키텍처 요약

```
MCP Client (Claude)
        │
        ▼
┌──────────────────────────────────┐
│  FastMCP Server (stateless)      │
│  ├── DISCOVER (검색/탐색)         │
│  ├── FETCH (데이터 조회)          │
│  ├── EXECUTE (코드 실행) ⭐       │
│  └── PRESENT (분석/리포트)        │
└──────────┬───────────────────────┘
           │
    ┌──────┴──────┐
    ▼             ▼
PostgreSQL    Cloudflare R2
+ pgvector    (CDN)
```

### 3.2 핵심 기능

| 기능 | 설명 | 상태 |
|------|------|------|
| **키워드 검색** | KOSIS API 기반 통계표 검색 | ✅ 완료 |
| **데이터 조회** | 요약만 LLM에 전달, 원본은 서버 저장 | ✅ 완료 |
| **코드 실행** | pandas/altair 코드를 서버에서 실행 | ✅ 완료 |
| **시각화** | Altair 차트 생성 및 URL 반환 | ✅ 완료 |
| **하이브리드 검색** | 벡터 + BM25 결합 검색 (252,890 테이블) | ✅ 완료 |
| **프로덕션 배포** | Docker + PostgreSQL + pgvector | ✅ 완료 |
| **모듈형 Executor** | visualization, analysis, table, report | ✅ 완료 |

---

## 4. User Stories

### 4.1 데이터 탐색 (DISCOVER)

```
US-D1: 키워드 검색
As a 데이터 분석가,
I want to 키워드로 관련 통계표를 검색,
So that 원하는 데이터를 빠르게 찾을 수 있다.
```

```
US-D2: 자연어 검색 (Phase 3)
As a 비전문가 사용자,
I want to "경제가 좋아졌나요?" 같은 자연어로 검색,
So that 전문 용어를 몰라도 관련 데이터를 찾을 수 있다.
```

```
US-D3: 메타데이터 조회
As a 개발자,
I want to 테이블의 컬럼 정보와 분류값을 조회,
So that 올바른 파라미터로 데이터를 요청할 수 있다.
```

### 4.2 데이터 조회 (FETCH)

```
US-F1: 데이터 요약 조회
As a LLM 클라이언트,
I want to 데이터 요약만 받고 원본은 서버에 저장,
So that 컨텍스트 토큰을 절약할 수 있다.
```

```
US-F2: 데이터 필터링
As a 데이터 분석가,
I want to 저장된 데이터를 조건으로 필터링,
So that 필요한 부분만 추출할 수 있다.
```

### 4.3 코드 실행 (EXECUTE)

```
US-E1: 분석 코드 실행
As a LLM 클라이언트,
I want to pandas/altair 코드를 서버에서 실행,
So that 대용량 데이터를 직접 처리하지 않아도 된다.
```

```
US-E2: 시각화 생성
As a 데이터 분석가,
I want to 코드로 차트를 생성하고 URL을 받기,
So that 결과를 바로 공유할 수 있다.
```

```
US-E3: 에러 피드백
As a LLM 클라이언트,
I want to 빈 차트 생성 시 데이터 시그니처와 힌트를 받기,
So that 코드를 수정하여 재시도할 수 있다.
```

### 4.4 하이브리드 검색 (Phase 3)

```
US-H1: 시맨틱 검색
As a 사용자,
I want to 의미 기반으로 관련 테이블을 추천받기,
So that 정확한 키워드를 몰라도 데이터를 찾을 수 있다.
```

```
US-H2: 검색 결과 순위
As a 데이터 분석가,
I want to 키워드와 의미 검색 결과를 결합한 순위를 받기,
So that 가장 관련성 높은 테이블을 선택할 수 있다.
```

---

## 5. Technical Requirements

### 5.1 기술 스택

| 영역 | 기술 | 버전 | 비고 |
|------|------|------|------|
| **런타임** | Python | 3.12+ | uv 패키지 매니저 |
| **MCP 프레임워크** | FastMCP | 2.14+ | stateless_http 모드 |
| **시각화** | Altair | 5.5+ | vl-convert로 렌더링 |
| **데이터베이스** | PostgreSQL | 16 | pgvector 확장 |
| **임베딩** | OpenAI | text-embedding-3-small | 1536차원 |
| **스토리지** | Cloudflare R2 | - | S3 호환 API |
| **컨테이너** | Docker | - | docker-compose |

### 5.2 API 엔드포인트

#### MCP Tools (stdio/HTTP)

| Tool | 입력 | 출력 |
|------|------|------|
| `search_statistics` | keyword, org_id?, limit? | 테이블 목록 JSON |
| `get_statistics_data` | org_id, tbl_id, period? | 요약 + data_id |
| `execute_code` | code, data_id? | 실행 결과 + artifact URL |
| `search_tables_hybrid` | query, limit? | RRF 순위 결과 (Phase 3) |

#### KOSIS API (외부)

| 엔드포인트 | 용도 |
|-----------|------|
| `statisticsList.do` | 통계표 검색 |
| `statisticsParameterData.do` | 데이터 조회 |
| `statisticsMetaData.do` | 메타데이터 조회 |

### 5.3 데이터 모델

#### PostgreSQL Schema (Phase 3)

```sql
CREATE TABLE kosis_tables (
    id              SERIAL PRIMARY KEY,
    tbl_id          VARCHAR(50) UNIQUE NOT NULL,
    org_id          VARCHAR(10) NOT NULL,
    tbl_nm          TEXT NOT NULL,
    org_nm          VARCHAR(100),
    contents        TEXT,
    search_text     TEXT,
    search_vector   TSVECTOR,           -- GIN index
    embedding       VECTOR(1536),        -- HNSW index
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### 5.4 성능 요구사항

| 메트릭 | 목표 | 측정 방법 |
|--------|------|----------|
| 검색 응답 시간 | < 500ms | 하이브리드 검색 (캐시 후) |
| 코드 실행 시간 | < 10s | 일반적인 분석 코드 |
| 토큰 절감율 | > 95% | execute_code vs 원본 전달 |
| 차트 생성 시간 | < 3s | Altair → HTML |

---

## 6. Acceptance Criteria

### Phase 2 (완료) - Core Features

- [x] `search_statistics` 도구가 키워드로 통계표를 검색
- [x] `get_statistics_data` 도구가 요약만 반환하고 원본은 서버 저장
- [x] `execute_code` 도구가 pandas/altair 코드를 샌드박스에서 실행
- [x] 빈 차트 생성 시 `VISUALIZATION_VALIDATION_ERROR`와 `data_signature` 반환
- [x] Altair 차트가 HTML로 저장되고 URL 반환
- [x] 금지된 모듈(`exec`, `eval`, `open` 등) 사용 시 에러 발생

### Phase 3 (완료) - Hybrid Search & Deployment

- [x] PostgreSQL + pgvector 컨테이너 구성
- [x] `kosis_tables` 테이블에 252,890개 메타데이터 로드
- [x] OpenAI 임베딩 생성 (text-embedding-3-small)
- [x] HNSW 인덱스 생성 (vector_cosine_ops)
- [x] GIN 인덱스 생성 (tsvector)
- [x] `search_tables_hybrid` 도구 구현 (RRF 결합)
- [x] 하이브리드 검색 응답 시간 < 500ms
- [x] Docker Compose로 전체 스택 배포
- [x] FastMCP HTTP 모드 (`stateless_http=True`)
- [x] Cloudflare R2 연동 (차트/리포트 업로드)

### Phase 4 (계획) - External Access

- [ ] Tailscale 또는 Cloudflare Tunnel 설정
- [ ] 외부에서 MCP 서버 접근 가능
- [ ] 인증/권한 설정

---

## 7. Constraints & Non-Negotiables

### 7.1 필수 제약사항

| 제약 | 이유 | 대안 |
|------|------|------|
| **Playwright/Selenium 금지** | 속도, 의존성 | requests + BeautifulSoup |
| **DT 필드 문자열 처리** | KOSIS API 응답 특성 | 숫자 연산 전 형변환 |
| **비표준 JSON 파싱** | KOSIS API 응답 형식 | `fix_malformed_json()` |
| **Rate Limit 준수** | KOSIS API 정책 | 1 req/sec |

### 7.2 보안 제약사항

| 제약 | 구현 |
|------|------|
| API 키 보호 | 환경변수, .env 파일 |
| 코드 샌드박스 | 허용 모듈 화이트리스트 |
| SQL Injection 방지 | Parameterized queries |

### 7.3 아키텍처 제약사항

| 제약 | 이유 |
|------|------|
| Stateless 설계 | 수평 확장 지원 |
| 서버사이드 처리 | LLM 토큰 절감 |
| CDN 분리 | 정적 파일 빠른 전달 |

---

## 8. Success Metrics

### 8.1 기술 메트릭

| 메트릭 | 현재 | 목표 | 측정 방법 |
|--------|------|------|----------|
| 토큰 절감율 | 98.7% | > 95% | execute_code 사용 시 |
| 검색 정확도 | N/A | > 80% | 상위 10개 결과 관련성 |
| API 응답 시간 | ~2s | < 500ms | 캐시된 검색 |
| 시스템 가용성 | N/A | > 99% | 프로덕션 배포 후 |

### 8.2 사용자 메트릭

| 메트릭 | 목표 | 측정 방법 |
|--------|------|----------|
| 검색 성공률 | > 90% | 첫 검색에서 원하는 데이터 발견 |
| 코드 실행 성공률 | > 80% | 첫 시도에서 유효한 차트 생성 |
| 재시도 횟수 | < 2회 | 평균 재시도 횟수 |

---

## 9. Implementation Phases

### Phase 1 ✅ - Core API Tools

- KOSIS API 클라이언트 구현
- 기본 MCP 도구 (search, data, metadata)
- 데이터 변환/필터링

### Phase 2 ✅ - Code Execution & Visualization

- `execute_code` 샌드박스 구현
- Altair 시각화 통합
- 빈 차트 검증 시스템
- HTML 리포트 생성

### Phase 3 ✅ - Hybrid Search & Deployment

- PostgreSQL + pgvector 설정
- 252,890개 테이블 메타데이터 임베딩 생성
- 하이브리드 검색 구현 (벡터 + BM25 + RRF)
- Docker 컨테이너화
- Modular Executors (visualization, analysis, table, report)

### Phase 4 📋 - External Access & Optimization

- Tailscale/Cloudflare Tunnel 설정
- 캐싱 레이어 추가
- 성능 최적화
- 모니터링/로깅

---

## 10. Out of Scope

다음 항목은 현재 PRD 범위에 포함되지 않음:

- 웹 UI/대시보드 (MCP 클라이언트가 담당)
- 사용자 인증/멀티테넌시
- 실시간 데이터 스트리밍
- 다른 통계 API 연동 (한국은행, MDIS 등)
- 모바일 앱

---

## 11. References

### 내부 문서

- [CLAUDE.md](./CLAUDE.md) - 프로젝트 엔트리포인트
- [docs/USER_GUIDE.md](./docs/USER_GUIDE.md) - 사용자 가이드
- [docs/ARCHITECTURE_DESIGN.md](./docs/ARCHITECTURE_DESIGN.md) - 시스템 아키텍처
- [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md) - 배포 가이드
- [docs/HYBRID_SEARCH.md](./docs/HYBRID_SEARCH.md) - 하이브리드 검색 설계
- [docs/KOSIS_API_REFERENCE.md](./docs/KOSIS_API_REFERENCE.md) - KOSIS API 참조
- [MCP_PATTERN.md](./MCP_PATTERN.md) - 대용량 데이터 처리 패턴

### 외부 문서

- [KOSIS OpenAPI](https://kosis.kr/openapi/) - 공식 API 문서
- [FastMCP Documentation](https://gofastmcp.com/) - MCP 서버 프레임워크
- [pgvector GitHub](https://github.com/pgvector/pgvector) - 벡터 검색 확장
- [Cloudflare R2 Docs](https://developers.cloudflare.com/r2/) - S3 호환 스토리지
