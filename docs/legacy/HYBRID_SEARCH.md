# KOSIS MCP Server - 하이브리드 검색 설계

> **상태**: 설계 검증 완료, 구현 대기
> **최종 검증일**: 2024-12-15
> **참조 문서**: pgvector GitHub, PostgreSQL 공식문서, OpenAI Embeddings Docs

---

## 1. 개요

### 1.1 목적

KOSIS 메타데이터 카탈로그(103,796개 테이블)를 대상으로 자연어 검색을 지원합니다.
키워드 검색(BM25)과 의미 검색(Vector Similarity)을 결합한 하이브리드 검색으로
사용자 쿼리에 가장 관련성 높은 통계 테이블을 추천합니다.

### 1.2 검색 방식 비교

| 방식 | 장점 | 단점 | 사용 시나리오 |
|------|------|------|--------------|
| **키워드 (BM25)** | 정확한 용어 매칭 | 동의어/유사어 놓침 | "출생아수", "GDP" |
| **벡터 (Cosine)** | 의미적 유사성 | 정확한 용어 놓침 | "경제가 좋아졌나요?" |
| **하이브리드** | 양쪽 장점 결합 | 복잡도 증가 | 범용 검색 |

### 1.3 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│  사용자 쿼리: "출산율 감소 원인"                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
          ┌───────────▼───────────┐
          │  PostgreSQL 16        │
          │  + pgvector extension │
          └───────────┬───────────┘
                      │
      ┌───────────────┼───────────────┐
      ▼               ▼               ▼
┌──────────┐   ┌──────────┐   ┌──────────────┐
│ FTS 검색  │   │ Vector   │   │ RRF 결합     │
│ (BM25)   │   │ 검색     │   │ (Reciprocal  │
│ ts_rank  │   │ Cosine   │   │  Rank Fusion)│
└────┬─────┘   └────┬─────┘   └──────┬───────┘
     │              │                │
     └──────────────┴────────────────┘
                    │
          ┌─────────▼─────────┐
          │  최종 순위 결과    │
          │  Top-K 테이블 반환 │
          └───────────────────┘
```

---

## 2. 데이터베이스 스키마

### 2.1 테이블 정의

**출처**: pgvector GitHub, PostgreSQL FTS 문서

```sql
-- pgvector 확장 활성화
CREATE EXTENSION IF NOT EXISTS vector;

-- 메타데이터 카탈로그 테이블
CREATE TABLE kosis_tables (
    id SERIAL PRIMARY KEY,

    -- 기본 식별자
    tbl_id VARCHAR(50) UNIQUE NOT NULL,
    org_id VARCHAR(10) NOT NULL,
    stat_id VARCHAR(20),

    -- 텍스트 필드 (검색 대상)
    tbl_nm TEXT NOT NULL,           -- 테이블명
    org_nm VARCHAR(100),            -- 기관명
    stat_nm TEXT,                   -- 통계명
    mt_atitle TEXT,                 -- 분류 경로
    contents TEXT,                  -- 내용 설명
    item03 TEXT,                    -- 추가 설명

    -- 메타데이터
    strt_prd_de VARCHAR(10),        -- 시작 기간
    end_prd_de VARCHAR(10),         -- 종료 기간
    link_url TEXT,                  -- KOSIS 링크

    -- 검색용 컬럼
    search_text TEXT,               -- 검색용 결합 텍스트
    search_vector tsvector,         -- FTS 벡터
    embedding vector(1536),         -- OpenAI 임베딩

    -- 관리 필드
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- search_text: 검색 대상 텍스트 결합
-- tbl_nm + org_nm + contents + item03 + mt_atitle
COMMENT ON COLUMN kosis_tables.search_text IS
    '검색용 결합 텍스트. 임베딩 및 FTS 생성에 사용';
```

### 2.2 인덱스 생성

**출처**:
- pgvector GitHub: HNSW vs IVFFlat 비교
- PostgreSQL 공식문서: GIN 인덱스, tsvector

```sql
-- 1. Full-Text Search용 GIN 인덱스
-- 출처: PostgreSQL 공식문서 - textsearch-indexes
CREATE INDEX idx_kosis_search_vector
    ON kosis_tables USING GIN (search_vector);

-- 2. 벡터 검색용 HNSW 인덱스
-- 출처: pgvector GitHub - HNSW indexes
-- 주의: 데이터 로드 후 생성 권장 (빌드 시간 단축)
CREATE INDEX idx_kosis_embedding
    ON kosis_tables USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 3. 기본 인덱스
CREATE INDEX idx_kosis_org_id ON kosis_tables(org_id);
CREATE INDEX idx_kosis_tbl_id ON kosis_tables(tbl_id);
```

### 2.3 HNSW vs IVFFlat 선택

**출처**: pgvector GitHub README

| 항목 | HNSW | IVFFlat |
|------|------|---------|
| **빌드 시간** | 느림 | 빠름 |
| **쿼리 속도** | 빠름 | 보통 |
| **메모리 사용** | 많음 | 적음 |
| **정확도** | 높음 | 보통 |
| **권장 사례** | 프로덕션 검색 | 대용량/빈번한 업데이트 |

> **결정**: HNSW 사용
> - 103K 테이블은 중간 규모
> - 주간 업데이트 (빈번하지 않음)
> - 검색 속도와 정확도 우선

---

## 3. 임베딩 생성

### 3.1 OpenAI API 설정

**출처**: [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)

```python
# src/kosis_tools/embeddings.py
import openai
from typing import List

class EmbeddingGenerator:
    """OpenAI 임베딩 생성기."""

    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
        # 출처: OpenAI Docs - text-embedding-3-small
        # 기본 1536차원, dimensions 파라미터로 조정 가능 (256, 512, 1024, 1536)
        self.model = "text-embedding-3-small"
        self.dimensions = 1536

    def create_embedding(self, text: str) -> List[float]:
        """단일 텍스트의 임베딩 생성."""
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
            dimensions=self.dimensions,  # 선택적: 차원 축소 가능
        )
        return response.data[0].embedding

    def create_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """배치 임베딩 생성.

        출처: OpenAI Docs - 최대 2048개 입력 지원
        비용 효율을 위해 배치 처리 권장
        """
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.client.embeddings.create(
                model=self.model,
                input=batch,
                dimensions=self.dimensions,
            )
            embeddings.extend([d.embedding for d in response.data])
        return embeddings
```

### 3.2 검색 텍스트 생성

```python
def create_search_text(record: dict) -> str:
    """메타데이터 레코드에서 검색용 텍스트 생성.

    결합 순서: 테이블명 > 기관명 > 내용 > 추가설명 > 분류경로
    중복 제거 및 길이 제한 적용
    """
    parts = [
        record.get("TBL_NM", ""),
        record.get("ORG_NM", ""),
        record.get("CONTENTS", ""),
        record.get("ITEM03", ""),
        record.get("MT_ATITLE", ""),
    ]

    # 빈 값 제거 및 결합
    text = " ".join(p.strip() for p in parts if p and p.strip())

    # OpenAI 임베딩 최대 입력: 8191 토큰
    # 한국어는 토큰당 약 2-3자, 안전하게 15000자로 제한
    return text[:15000]
```

### 3.3 비용 추정

**출처**: OpenAI Pricing (2024-12)

| 항목 | 값 |
|------|-----|
| 모델 | text-embedding-3-small |
| 가격 | $0.020 / 1M 토큰 |
| 테이블 수 | 103,796개 |
| 평균 토큰 (추정) | ~500 토큰/테이블 |
| **총 비용 (추정)** | **~$1.04** (1회 전체 임베딩) |

---

## 4. Full-Text Search (BM25)

### 4.1 한국어 설정

**출처**: PostgreSQL 공식문서 - Text Search Configuration

```sql
-- 한국어 전용 설정 생성
-- PostgreSQL 기본 제공 'simple' 사전 사용 (형태소 분석 없음)
CREATE TEXT SEARCH CONFIGURATION korean (COPY = simple);

-- 검색 벡터 생성/업데이트 함수
CREATE OR REPLACE FUNCTION update_search_vector()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector := to_tsvector('korean', COALESCE(NEW.search_text, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 트리거: search_text 변경 시 자동 업데이트
CREATE TRIGGER trg_update_search_vector
    BEFORE INSERT OR UPDATE OF search_text
    ON kosis_tables
    FOR EACH ROW
    EXECUTE FUNCTION update_search_vector();
```

### 4.2 검색 쿼리

**출처**: PostgreSQL 공식문서 - ts_rank, to_tsquery

```sql
-- BM25 유사 검색 (ts_rank 사용)
SELECT
    tbl_id,
    tbl_nm,
    org_nm,
    ts_rank(search_vector, query) AS rank
FROM
    kosis_tables,
    plainto_tsquery('korean', '출산율 감소') AS query
WHERE
    search_vector @@ query
ORDER BY
    rank DESC
LIMIT 20;
```

### 4.3 한국어 검색 한계 및 대안

PostgreSQL 기본 FTS는 한국어 형태소 분석을 지원하지 않습니다.

| 옵션 | 설명 | 복잡도 |
|------|------|--------|
| **simple 사전** | 공백 기준 분리, 형태소 분석 없음 | 낮음 |
| **mecab 사전** | 형태소 분석, 별도 설치 필요 | 중간 |
| **trigram (pg_trgm)** | n-gram 기반, 부분 매칭 | 낮음 |

> **결정**: 초기에는 `simple` + 벡터 검색 조합으로 시작
> 벡터 검색이 의미적 유사성을 보완하므로 형태소 분석 없이도 충분

---

## 5. 하이브리드 검색 구현

### 5.1 RRF (Reciprocal Rank Fusion)

**출처**: [RRF 논문](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)

```python
def reciprocal_rank_fusion(
    fts_results: List[str],
    vector_results: List[str],
    k: int = 60
) -> List[tuple]:
    """
    두 검색 결과를 RRF로 결합.

    Args:
        fts_results: FTS 검색 결과 (tbl_id 순서 리스트)
        vector_results: 벡터 검색 결과 (tbl_id 순서 리스트)
        k: RRF 파라미터 (기본값 60)

    Returns:
        결합된 결과 [(tbl_id, score), ...] 내림차순

    RRF 공식: score(d) = Σ 1 / (k + rank_i(d))
    """
    scores = {}

    # FTS 결과 점수 계산
    for rank, tbl_id in enumerate(fts_results, start=1):
        scores[tbl_id] = scores.get(tbl_id, 0) + 1 / (k + rank)

    # 벡터 결과 점수 계산
    for rank, tbl_id in enumerate(vector_results, start=1):
        scores[tbl_id] = scores.get(tbl_id, 0) + 1 / (k + rank)

    # 점수순 정렬
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### 5.2 통합 검색 쿼리

```sql
-- 하이브리드 검색 CTE
WITH
-- 1. FTS 검색 (BM25)
fts_search AS (
    SELECT
        tbl_id,
        ROW_NUMBER() OVER (ORDER BY ts_rank(search_vector, query) DESC) AS fts_rank
    FROM
        kosis_tables,
        plainto_tsquery('korean', $1) AS query
    WHERE
        search_vector @@ query
    LIMIT 100
),

-- 2. 벡터 검색 (Cosine Similarity)
vector_search AS (
    SELECT
        tbl_id,
        ROW_NUMBER() OVER (ORDER BY embedding <=> $2) AS vec_rank
    FROM
        kosis_tables
    ORDER BY
        embedding <=> $2
    LIMIT 100
),

-- 3. RRF 결합
combined AS (
    SELECT
        COALESCE(f.tbl_id, v.tbl_id) AS tbl_id,
        COALESCE(1.0 / (60 + f.fts_rank), 0) +
        COALESCE(1.0 / (60 + v.vec_rank), 0) AS rrf_score
    FROM
        fts_search f
    FULL OUTER JOIN
        vector_search v ON f.tbl_id = v.tbl_id
)

-- 4. 최종 결과
SELECT
    c.tbl_id,
    c.rrf_score,
    t.tbl_nm,
    t.org_nm,
    t.contents
FROM
    combined c
JOIN
    kosis_tables t ON c.tbl_id = t.tbl_id
ORDER BY
    c.rrf_score DESC
LIMIT 20;
```

### 5.3 Python 래퍼

```python
# src/kosis_tools/hybrid_search.py
from typing import List, Dict, Any
import asyncpg

class HybridSearcher:
    """하이브리드 검색 클라이언트."""

    def __init__(self, pool: asyncpg.Pool, embedder: EmbeddingGenerator):
        self.pool = pool
        self.embedder = embedder

    async def search(
        self,
        query: str,
        limit: int = 20,
        fts_weight: float = 0.5,
        vector_weight: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """
        하이브리드 검색 수행.

        Args:
            query: 검색어 (자연어)
            limit: 결과 수
            fts_weight: FTS 가중치 (0-1)
            vector_weight: 벡터 검색 가중치 (0-1)

        Returns:
            검색 결과 리스트
        """
        # 쿼리 임베딩 생성
        query_embedding = self.embedder.create_embedding(query)

        # SQL 실행
        sql = """
        WITH fts_search AS (
            SELECT tbl_id,
                   ROW_NUMBER() OVER (ORDER BY ts_rank(search_vector, query) DESC) AS fts_rank
            FROM kosis_tables, plainto_tsquery('korean', $1) AS query
            WHERE search_vector @@ query
            LIMIT 100
        ),
        vector_search AS (
            SELECT tbl_id,
                   ROW_NUMBER() OVER (ORDER BY embedding <=> $2) AS vec_rank
            FROM kosis_tables
            ORDER BY embedding <=> $2
            LIMIT 100
        ),
        combined AS (
            SELECT COALESCE(f.tbl_id, v.tbl_id) AS tbl_id,
                   COALESCE($3 / (60 + f.fts_rank), 0) +
                   COALESCE($4 / (60 + v.vec_rank), 0) AS rrf_score
            FROM fts_search f
            FULL OUTER JOIN vector_search v ON f.tbl_id = v.tbl_id
        )
        SELECT c.tbl_id, c.rrf_score, t.tbl_nm, t.org_nm, t.contents,
               t.strt_prd_de, t.end_prd_de, t.link_url
        FROM combined c
        JOIN kosis_tables t ON c.tbl_id = t.tbl_id
        ORDER BY c.rrf_score DESC
        LIMIT $5;
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                sql,
                query,
                query_embedding,
                fts_weight,
                vector_weight,
                limit
            )

        return [dict(row) for row in rows]
```

---

## 6. 데이터 로드

### 6.1 초기 로드 스크립트

```python
# scripts/load_metadata.py
import json
import asyncio
import asyncpg
from pathlib import Path

async def load_metadata(
    json_path: str,
    database_url: str,
    embedder: EmbeddingGenerator,
    batch_size: int = 500,
):
    """
    kosis_metadata_final.json을 PostgreSQL에 로드.

    Args:
        json_path: JSON 파일 경로
        database_url: PostgreSQL 연결 URL
        embedder: 임베딩 생성기
        batch_size: 배치 크기
    """
    # JSON 로드
    with open(json_path, 'r', encoding='utf-8') as f:
        records = json.load(f)

    print(f"총 {len(records):,}개 레코드 로드")

    # DB 연결
    conn = await asyncpg.connect(database_url)

    try:
        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]

            # search_text 생성
            search_texts = [create_search_text(r) for r in batch]

            # 임베딩 생성 (배치)
            embeddings = embedder.create_embeddings_batch(search_texts)

            # DB 삽입
            await conn.executemany(
                """
                INSERT INTO kosis_tables (
                    tbl_id, org_id, stat_id, tbl_nm, org_nm, stat_nm,
                    mt_atitle, contents, item03, strt_prd_de, end_prd_de,
                    link_url, search_text, embedding
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14
                )
                ON CONFLICT (tbl_id) DO UPDATE SET
                    search_text = EXCLUDED.search_text,
                    embedding = EXCLUDED.embedding,
                    updated_at = NOW()
                """,
                [
                    (
                        r["TBL_ID"], r["ORG_ID"], r.get("STAT_ID"),
                        r["TBL_NM"], r.get("ORG_NM"), r.get("STAT_NM"),
                        r.get("MT_ATITLE"), r.get("CONTENTS"), r.get("ITEM03"),
                        r.get("STRT_PRD_DE"), r.get("END_PRD_DE"),
                        r.get("LINK_URL"), search_texts[j], embeddings[j]
                    )
                    for j, r in enumerate(batch)
                ]
            )

            print(f"진행: {min(i + batch_size, len(records)):,} / {len(records):,}")

    finally:
        await conn.close()

    print("로드 완료!")

if __name__ == "__main__":
    asyncio.run(load_metadata(
        json_path="kosis_data/kosis_metadata_final.json",
        database_url="postgresql://kosis:password@localhost:5432/kosis",
        embedder=EmbeddingGenerator(api_key="sk-..."),
    ))
```

### 6.2 인덱스 생성 (로드 후)

```sql
-- 데이터 로드 완료 후 인덱스 생성
-- HNSW 인덱스는 데이터가 있는 상태에서 생성이 더 효율적

-- 1. HNSW 벡터 인덱스
CREATE INDEX CONCURRENTLY idx_kosis_embedding
    ON kosis_tables USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 2. GIN FTS 인덱스
CREATE INDEX CONCURRENTLY idx_kosis_search_vector
    ON kosis_tables USING GIN (search_vector);

-- 인덱스 생성 확인
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'kosis_tables';
```

---

## 7. 성능 최적화

### 7.1 HNSW 파라미터 튜닝

**출처**: pgvector GitHub

| 파라미터 | 설명 | 기본값 | 권장값 |
|----------|------|--------|--------|
| `m` | 연결 수 | 16 | 16-64 |
| `ef_construction` | 빌드 시 탐색 범위 | 64 | 64-200 |
| `ef_search` | 쿼리 시 탐색 범위 | 40 | 40-200 |

```sql
-- 쿼리 시 ef_search 조정 (세션별)
SET hnsw.ef_search = 100;

-- 확인
SHOW hnsw.ef_search;
```

### 7.2 벤치마크 예상

| 항목 | 값 |
|------|-----|
| 테이블 수 | 103,796 |
| 임베딩 차원 | 1536 |
| 예상 인덱스 크기 | ~800MB |
| 예상 검색 시간 | <100ms (HNSW) |

---

## 8. MCP 도구 통합

### 8.1 새로운 도구 추가

```python
# src/mcp_server/server.py에 추가

@mcp.tool()
async def search_tables_hybrid(
    query: str,
    limit: int = 10,
) -> str:
    """
    자연어로 KOSIS 통계 테이블을 검색합니다.

    하이브리드 검색(키워드 + 의미)을 사용하여
    관련성 높은 테이블을 추천합니다.

    Args:
        query: 검색어 (자연어). 예: "최근 출산율 동향", "지역별 고용률"
        limit: 결과 수 (기본 10, 최대 50)

    Returns:
        검색 결과 JSON (테이블 ID, 이름, 기관, 관련도 점수)
    """
    searcher = get_hybrid_searcher()
    results = await searcher.search(query, limit=min(limit, 50))

    return json.dumps({
        "query": query,
        "count": len(results),
        "results": [
            {
                "tbl_id": r["tbl_id"],
                "tbl_nm": r["tbl_nm"],
                "org_nm": r["org_nm"],
                "score": round(r["rrf_score"], 4),
                "period": f"{r['strt_prd_de']} ~ {r['end_prd_de']}",
                "link": r["link_url"],
            }
            for r in results
        ]
    }, ensure_ascii=False, indent=2)
```

---

## 9. 참조 문서

### 공식 문서
- [pgvector GitHub](https://github.com/pgvector/pgvector) - HNSW/IVFFlat 인덱스
- [PostgreSQL Text Search](https://www.postgresql.org/docs/current/textsearch.html) - tsvector, ts_rank
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings) - text-embedding-3-small

### 관련 프로젝트 문서
- [DEPLOYMENT.md](./DEPLOYMENT.md) - 배포 설정
- [ARCHITECTURE_DESIGN.md](./ARCHITECTURE_DESIGN.md) - 전체 아키텍처
