# KOSIS MCP Server - Docker Architecture

> **Status: TODO (계획 단계)**
>
> 이 문서는 향후 구현할 Docker Compose 기반 배포 아키텍처를 설명합니다.

## Overview

로컬 개발과 서버 배포 모두 Docker Compose로 통일하여 관리합니다.

```
┌─────────────────────────────────────────────────────────────────┐
│                      Docker Compose                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │             │    │             │    │                     │ │
│  │   Updater   │───▶│  PostgreSQL │◀───│    MCP Server       │ │
│  │             │    │  + pgvector │    │                     │ │
│  └─────────────┘    └─────────────┘    └─────────────────────┘ │
│        │                   ▲                     ▲              │
│        ▼                   │                     │              │
│   ┌─────────┐              │              ┌──────┴──────┐       │
│   │ KOSIS   │              │              │   Claude    │       │
│   │ 홈페이지 │              │              │   Desktop   │       │
│   └─────────┘              │              └─────────────┘       │
│                            │                                    │
│                     kosis_data (volume)                        │
└─────────────────────────────────────────────────────────────────┘
```

## 3 Services

| 서비스 | 역할 | 실행 방식 |
|--------|------|----------|
| **db** | PostgreSQL 16 + pgvector | 상시 실행 |
| **updater** | XLS 다운로드 → 파싱 → 임베딩 → DB 적재 | cron/수동 (하루 1회) |
| **mcp-server** | Claude Desktop 연동, 하이브리드 검색 제공 | 상시 실행 |

## docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: pgvector/pgvector:pg16
    container_name: kosis-db
    restart: unless-stopped
    volumes:
      - kosis_data:/var/lib/postgresql/data
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql
    environment:
      POSTGRES_DB: kosis_metadata
      POSTGRES_USER: kosis
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kosis -d kosis_metadata"]
      interval: 10s
      timeout: 5s
      retries: 5

  updater:
    build: ./services/updater
    container_name: kosis-updater
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://kosis:${POSTGRES_PASSWORD}@db:5432/kosis_metadata
      OPENAI_API_KEY: ${OPENAI_API_KEY}
    volumes:
      - ./data/metadata_files:/app/data

  mcp-server:
    build: ./services/mcp-server
    container_name: kosis-mcp
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://kosis:${POSTGRES_PASSWORD}@db:5432/kosis_metadata
      KOSIS_API_KEY: ${KOSIS_API_KEY}
    ports:
      - "8080:8080"

volumes:
  kosis_data:
```

## Directory Structure

```
kosis-data-processor/
├── docker-compose.yml
├── .env                          # API 키, DB 비밀번호
│
├── db/
│   └── init.sql                  # 스키마, pgvector, FTS 설정
│
├── services/
│   ├── updater/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── download.py           # KOSIS에서 XLS 다운로드
│   │   ├── parse.py              # XLS → 정규화
│   │   ├── embed.py              # OpenAI 임베딩 생성
│   │   ├── load.py               # DB 적재 (upsert)
│   │   └── main.py               # 파이프라인 오케스트레이션
│   │
│   └── mcp-server/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── server.py             # MCP 서버
│
├── data/
│   └── metadata_files/           # 다운로드된 XLS 파일
│
└── src/kosis_tools/              # 공유 라이브러리
```

## Database Schema

```sql
-- pgvector 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- 메타데이터 테이블
CREATE TABLE statistics_tables (
    id SERIAL PRIMARY KEY,
    tbl_id VARCHAR(50) NOT NULL UNIQUE,
    org_id VARCHAR(10) NOT NULL,
    tbl_nm TEXT NOT NULL,                    -- 통계표명
    stat_nm TEXT,                            -- 통계명
    prd_de TEXT,                             -- 수록기간
    full_path TEXT,                          -- 전체 경로
    source_file VARCHAR(50),                 -- 원본 파일 (주제별/기관별 등)

    -- 벡터 임베딩 (OpenAI text-embedding-3-small)
    embedding vector(1536),

    -- 메타
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 인덱스
CREATE INDEX idx_tbl_id ON statistics_tables(tbl_id);
CREATE INDEX idx_org_id ON statistics_tables(org_id);

-- FTS 인덱스 (한글 검색)
CREATE INDEX idx_fts ON statistics_tables
    USING GIN (to_tsvector('simple', tbl_nm || ' ' || COALESCE(stat_nm, '')));

-- 벡터 인덱스 (HNSW)
CREATE INDEX idx_embedding ON statistics_tables
    USING hnsw (embedding vector_cosine_ops);
```

## Updater Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│                      Updater 실행 흐름                        │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Download     KOSIS 홈페이지에서 최신 XLS 파일 다운로드    │
│       │          (주제별, 기관별, 지역통계 등)                │
│       ▼                                                      │
│  2. Parse        XLS → pandas → 정규화                       │
│       │          (중복 제거, 컬럼 통일)                       │
│       ▼                                                      │
│  3. Diff         기존 DB와 비교                              │
│       │          (신규/수정/삭제 식별)                        │
│       ▼                                                      │
│  4. Embed        변경된 레코드만 OpenAI 임베딩               │
│       │          (비용 절감)                                  │
│       ▼                                                      │
│  5. Load         PostgreSQL UPSERT                           │
│                  (트랜잭션으로 원자성 보장)                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Hybrid Search

MCP Server의 검색은 키워드(FTS)와 벡터(pgvector)를 결합합니다:

```sql
-- 하이브리드 검색 쿼리 예시
WITH keyword_results AS (
    SELECT id, tbl_id, tbl_nm,
           ts_rank(to_tsvector('simple', tbl_nm), plainto_tsquery('simple', $1)) as keyword_score
    FROM statistics_tables
    WHERE to_tsvector('simple', tbl_nm) @@ plainto_tsquery('simple', $1)
),
vector_results AS (
    SELECT id, tbl_id, tbl_nm,
           1 - (embedding <=> $2::vector) as vector_score
    FROM statistics_tables
    ORDER BY embedding <=> $2::vector
    LIMIT 100
)
SELECT DISTINCT ON (id)
    id, tbl_id, tbl_nm,
    COALESCE(keyword_score, 0) * 0.3 + COALESCE(vector_score, 0) * 0.7 as combined_score
FROM (
    SELECT * FROM keyword_results
    UNION ALL
    SELECT * FROM vector_results
) combined
ORDER BY combined_score DESC
LIMIT 20;
```

## Usage

### 개발 환경

```bash
# DB만 실행 (MCP 서버는 로컬에서 직접)
docker-compose up db

# 업데이터 수동 실행
docker-compose run --rm updater python main.py
```

### 배포 환경

```bash
# 전체 스택 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f mcp-server

# 업데이터 스케줄링 (cron)
# 0 3 * * * cd /path/to/project && docker-compose run --rm updater python main.py
```

## Environment Variables

`.env` 파일:

```env
# Database
POSTGRES_PASSWORD=your_secure_password

# APIs
KOSIS_API_KEY=your_kosis_api_key
OPENAI_API_KEY=your_openai_api_key

# Optional
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

## TODO

- [ ] `db/init.sql` 스키마 작성
- [ ] `services/updater/` 구현
  - [ ] download.py - XLS 다운로드 로직
  - [ ] parse.py - XLS 파싱 및 정규화
  - [ ] embed.py - OpenAI 임베딩 생성
  - [ ] load.py - DB upsert
  - [ ] main.py - 파이프라인 오케스트레이션
- [ ] `services/mcp-server/` 구현
  - [ ] 기존 kosis_tools 통합
  - [ ] 하이브리드 검색 구현
- [ ] Claude Desktop MCP 설정 가이드 작성
- [ ] 배포 문서 작성
