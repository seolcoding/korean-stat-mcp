# KOSIS 로컬 메타데이터 활용 전략

> API 호출 최소화를 위한 로컬 메타데이터 활용 아키텍처

---

## 최종 결정 사항 (2025-12-14 업데이트)

### 데이터 소스: XLS 파일 기반

**선택 이유:**
- API 재귀 탐색(`statisticsList.do`)은 수십만 건의 개별 호출 필요
- XLS 파일은 KOSIS 공식 스냅샷으로 안정적
- 중복 제거 후 93.8% 데이터 커버리지 달성

### 현재 메타데이터 현황

| 파일 | 개수 | 공식 수치 | 파일 크기 | 일치율 |
|------|------|----------|----------|--------|
| **tables.json** | 256,966 | 273,818 | 243MB | 93.8% |
| **indicators.json** | 1,476 | 1,476 | 469KB | **100%** |
| **surveys.json** | 1,385 | 1,487 | 358KB | 93.1% |
| **categories.json** | 51,469 | - | 39MB | - |

**차이 분석:**
- 통계표 16,852개 차이: `지역통계_기관별.xls`에 TBL_ID 없음 (API 보강 가능)

### 파일 구조

```
data/metadata/
├── tables.json      # 실제 통계표만 (TBL_ID 필수)
├── categories.json  # 카테고리 계층 구조 (별도 분리)
├── indicators.json  # 주요지표 (100% 일치)
└── surveys.json     # 통계설명자료
```

---

## 1. 메타데이터 파일 현황

### 1.1 보유 데이터 요약

| 파일 | 크기 | 통계표 수 | 주요 필드 |
|-----|------|---------|----------|
| **주제별통계.xls** | 262MB | 60,181개 | TBL_ID, 통계명, 출처, 수록기간, 계층경로 |
| **기관별통계.xls** | 266MB | 60,581개 | TBL_ID, 통계명, 기관명, 수록기간, 계층경로 |
| **지역통계_기관별.xls** | 139MB | ~30,000개 | 통계명, 기관명, 지역구분, 수록기간 |
| **국제통계.xls** | 2.5MB | 2,148개 | TBL_ID, 통계명, 국가별, 수록기간 |
| **북한통계.xls** | 1MB | 1,013개 | TBL_ID, 통계명, 수록기간 |
| **e-지방지표.xls** | 237KB | 257개 | TBL_ID, 통계명, 수록기간 |
| **OpenAPICodeList.xls** | 346KB | 1,476개 | 지표ID, 지표명, 부문, 수록주기 |
| **통계설명자료(조사).xls** | 154KB | 1,386개 | 기관명, 조사명 |

**총 메타데이터: ~60,000개 통계표 + 1,476개 핵심지표**

### 1.2 각 파일에서 얻을 수 있는 정보

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 주제별/기관별 통계 (60,000+ tables)                                       │
├─────────────────────────────────────────────────────────────────────────┤
│ • TBL_ID (통계표 고유ID) - 데이터 API 호출에 필수                          │
│ • 통계명 (자연어 검색용)                                                  │
│ • 출처 (기관명, 조사명)                                                   │
│ • 수록기간 - "년 (2015 ~ 2024)", "월 (201801 ~ 202511)"                   │
│ • 경로 - 계층 분류 "주제별통계 > 인구 > 인구총조사 > ..."                   │
│ • Level - 계층 깊이 (1=대분류, 2=중분류, 3=소분류...)                      │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ OpenAPI 지표코드표 (1,476 indicators)                                    │
├─────────────────────────────────────────────────────────────────────────┤
│ • 지표ID - 지표 API 호출에 필수                                          │
│ • 세부지표명 (실업률, GDP, 소비자물가지수 등)                              │
│ • 부문 / 세부부문 - 분류 체계                                             │
│ • 지역구분 - 전국/시도/국가/북한                                          │
│ • 수록시작/종료 - 데이터 커버리지                                         │
│ • 수록주기 - Y(연)/M(월)/Q(분기)                                         │
│ • 설명자료유무 - T/F                                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 현재 vs 최적화 워크플로우

### 2.1 현재 워크플로우 (API 중심)

```
사용자 질문: "2023년 서울 청년 실업률"

┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 1: 검색 API 호출                                                    │
│   → statisticsSearch.do?searchNm=청년실업률                              │
│   ← 10~50개 결과 반환 (네트워크 지연 + Rate Limit)                        │
├──────────────────────────────────────────────────────────────────────────┤
│ STEP 2: 각 결과별 메타데이터 API 호출 (N회)                               │
│   → statisticsData.do?method=getMeta&type=TBL (테이블 정보)              │
│   → statisticsData.do?method=getMeta&type=ITM (항목 정보)                │
│   → statisticsData.do?method=getMeta&type=PRD (기간 정보)                │
│   ← 분류/항목/기간 정보 (N * 3 API 호출!)                                │
├──────────────────────────────────────────────────────────────────────────┤
│ STEP 3: 데이터 API 호출                                                  │
│   → statisticsParameterData.do (실제 데이터)                             │
│   ← 통계 데이터 반환                                                     │
└──────────────────────────────────────────────────────────────────────────┘

문제점:
• 단순 질문에 10+ API 호출 필요
• Rate Limit (1초 딜레이) → 10+ 초 소요
• 네트워크 지연 누적
• API 서버 부하
```

### 2.2 최적화 워크플로우 (로컬 메타데이터 활용)

```
사용자 질문: "2023년 서울 청년 실업률"

┌──────────────────────────────────────────────────────────────────────────┐
│ STEP 1: 로컬 메타데이터 검색 (0ms)                                        │
│   → 벡터 DB 또는 SQLite에서 "청년 실업률" 검색                            │
│   ← TBL_ID, 수록기간, 분류체계 즉시 반환                                  │
│                                                                          │
│   이미 알고 있는 정보:                                                    │
│   • TBL_ID = "DT_1DA7012S"                                               │
│   • 수록기간 = "월 (200601 ~ 202311)"                                    │
│   • 경로 = "주제별통계 > 노동 > 경제활동인구조사 > 실업률"                  │
│   • 출처 = "국가데이터처,「경제활동인구조사」"                              │
├──────────────────────────────────────────────────────────────────────────┤
│ STEP 2: (선택적) 상세 메타 API 호출 - 필요시에만                          │
│   → 분류값(objL1=서울), 항목(itmId=청년) 확인 필요시                      │
│   ← 1회 API 호출                                                         │
├──────────────────────────────────────────────────────────────────────────┤
│ STEP 3: 데이터 API 호출 (1회)                                            │
│   → statisticsParameterData.do?tblId=DT_1DA7012S&objL1=11&...            │
│   ← 통계 데이터 반환                                                     │
└──────────────────────────────────────────────────────────────────────────┘

개선 효과:
• API 호출: 10+ → 1~2회 (90% 감소)
• 응답 시간: 10초+ → 1~2초 (80%+ 감소)
• 서버 부하 대폭 감소
• 오프라인 검색 가능
```

---

## 3. MCP 서버 아키텍처 제안

### 3.1 3-Layer 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MCP KOSIS Server                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Layer 1: DISCOVER (로컬 100%)                                    │    │
│  │ • search_tables() → 로컬 SQLite/벡터DB 검색                      │    │
│  │ • browse_categories() → 로컬 계층 구조 탐색                       │    │
│  │ • get_table_info() → 로컬 메타데이터 반환                         │    │
│  │ • suggest_related() → 로컬 연관 통계 추천                         │    │
│  │                                                                   │    │
│  │ 데이터소스: metadata.db (SQLite + FTS5)                          │    │
│  │            embeddings.db (벡터 인덱스)                            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                               │                                          │
│                               ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Layer 2: PLAN (로컬 80% + API 20%)                               │    │
│  │ • get_available_values() → 로컬 캐시 우선, 없으면 API            │    │
│  │ • validate_params() → 로컬 메타데이터로 파라미터 검증             │    │
│  │ • estimate_data_size() → 로컬 정보로 데이터 크기 예측             │    │
│  │                                                                   │    │
│  │ 캐시: Redis 또는 로컬 캐시 (분류값, 항목 목록)                    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                               │                                          │
│                               ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ Layer 3: FETCH (API 100% - 실제 데이터만)                        │    │
│  │ • fetch_data() → KOSIS API로 실제 통계 데이터 조회               │    │
│  │ • fetch_big_data() → 대용량 데이터 조회                          │    │
│  │                                                                   │    │
│  │ 최적화: 필요한 데이터만 정확히 요청                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 데이터베이스 스키마 제안

```sql
-- metadata.db (SQLite + FTS5 전문검색)

-- 1. 통계표 마스터 테이블
CREATE TABLE statistics_tables (
    id INTEGER PRIMARY KEY,
    tbl_id TEXT UNIQUE NOT NULL,      -- DT_1IN1502
    tbl_name TEXT NOT NULL,           -- 인구, 가구 및 주택
    source TEXT,                      -- 국가데이터처,「인구총조사」
    period_type TEXT,                 -- Y/M/Q
    period_start TEXT,                -- 2015, 201501
    period_end TEXT,                  -- 2024, 202411
    path TEXT,                        -- 주제별통계 > 인구 > ...
    path_id TEXT,                     -- > A > A_4 > A11 > ...
    category_type TEXT,               -- subject/org/region/international/north
    level INTEGER,                    -- 계층 깊이 1-5
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 전문 검색 인덱스 (FTS5)
CREATE VIRTUAL TABLE tables_fts USING fts5(
    tbl_name, source, path,
    content='statistics_tables',
    content_rowid='id',
    tokenize='unicode61'  -- 한글 지원
);

-- 3. 핵심 지표 테이블
CREATE TABLE key_indicators (
    id INTEGER PRIMARY KEY,
    indicator_id TEXT UNIQUE NOT NULL,  -- 1275, 381, ...
    indicator_name TEXT NOT NULL,       -- 실업률, GDP 등
    category TEXT,                      -- 100대 지표, 노동
    subcategory TEXT,                   -- 경기·기업·임금·물가
    area_type TEXT,                     -- 전국/시도/국가/북한
    period_type TEXT,                   -- Y/M/Q
    period_start TEXT,
    period_end TEXT,
    has_explanation BOOLEAN
);

-- 4. 통계조사 테이블
CREATE TABLE surveys (
    id INTEGER PRIMARY KEY,
    org_name TEXT NOT NULL,             -- 기관명
    survey_name TEXT NOT NULL           -- 조사명
);

-- 5. 캐시 테이블 (분류값, 항목 등)
CREATE TABLE metadata_cache (
    cache_key TEXT PRIMARY KEY,         -- tbl_id:ITM or tbl_id:OBJ_VAR
    data JSON NOT NULL,
    expires_at TIMESTAMP
);

-- 인덱스
CREATE INDEX idx_tables_tbl_id ON statistics_tables(tbl_id);
CREATE INDEX idx_tables_category ON statistics_tables(category_type);
CREATE INDEX idx_tables_period ON statistics_tables(period_start, period_end);
CREATE INDEX idx_indicators_name ON key_indicators(indicator_name);
```

### 3.3 벡터 인덱스 구조

```python
# embeddings.db (ChromaDB 또는 LanceDB)

# 1. 통계표 임베딩
collections:
  - statistics_tables:
      documents: [
        "인구 가구 주택 읍면동 시군구 인구총조사",  # 통계명 + 키워드
        "행정구역별 인구현황 주민등록인구통계",
        ...
      ]
      embeddings: [[0.1, 0.2, ...], [...], ...]
      metadata: [
        {tbl_id: "DT_1IN1502", period: "2015-2024", source: "국가데이터처"},
        ...
      ]

  - key_indicators:
      documents: [
        "실업률 경제활동인구 노동 고용",
        "소비자물가지수 CPI 인플레이션 물가",
        ...
      ]
      embeddings: [[...], [...], ...]
      metadata: [
        {indicator_id: "1275", area: "전국", period_type: "Y"},
        ...
      ]

# 하이브리드 검색 전략
# 1. 키워드 매칭 (FTS5) → 정확한 용어 검색
# 2. 벡터 검색 → 의미적 유사성
# 3. 결과 융합 (RRF - Reciprocal Rank Fusion)
```

---

## 4. MCP 도구별 활용 전략

### 4.1 DISCOVER 레이어 도구

| 도구 | 현재 | 최적화 후 | 효과 |
|-----|-----|---------|-----|
| `search_tables` | API 호출 | 로컬 FTS5 + 벡터 검색 | API 0회 |
| `browse_categories` | API 호출 | 로컬 계층 구조 | API 0회 |
| `get_table_info` | API 호출 | 로컬 메타데이터 | API 0회 |
| `recommend_tables` | 없음 | 벡터 유사도 검색 | 새 기능 |

```python
# 예시: search_tables 최적화
def search_tables(query: str, limit: int = 20):
    """로컬 메타데이터에서 통계표 검색"""

    # 1. FTS5 키워드 검색
    fts_results = db.execute("""
        SELECT tbl_id, tbl_name, source, period_start, period_end, path
        FROM tables_fts
        WHERE tables_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """, (query, limit * 2))

    # 2. 벡터 유사도 검색
    query_embedding = embed(query)
    vector_results = chroma.query(
        query_embeddings=[query_embedding],
        n_results=limit * 2
    )

    # 3. 결과 융합 (RRF)
    combined = reciprocal_rank_fusion(fts_results, vector_results)

    return combined[:limit]
```

### 4.2 PLAN 레이어 도구

```python
# 예시: validate_and_plan 도구
def validate_and_plan(tbl_id: str, user_query: str):
    """
    로컬 메타데이터로 쿼리 계획 수립
    API 호출 최소화
    """

    # 1. 로컬에서 기본 정보 확인
    table_info = db.get_table_info(tbl_id)  # 로컬

    # 2. 수록기간 검증 (로컬)
    if not is_period_valid(user_query, table_info['period_start'], table_info['period_end']):
        return {"error": "요청 기간이 수록기간을 벗어남"}

    # 3. 분류값 필요시에만 API 호출 (캐시 우선)
    obj_values = cache.get(f"{tbl_id}:OBJ_VAR")
    if not obj_values:
        obj_values = api.get_meta(tbl_id, "OBJ_VAR")  # API 1회
        cache.set(f"{tbl_id}:OBJ_VAR", obj_values, ttl=86400)

    # 4. 실행 계획 반환
    return {
        "tbl_id": tbl_id,
        "tbl_name": table_info['tbl_name'],
        "source": table_info['source'],
        "available_period": f"{table_info['period_start']} ~ {table_info['period_end']}",
        "classification_options": obj_values,
        "suggested_params": suggest_params(user_query, obj_values)
    }
```

### 4.3 FETCH 레이어 도구

```python
# 최적화된 데이터 조회
def fetch_data(tbl_id: str, **params):
    """
    실제 데이터 API 호출
    앞선 레이어에서 검증된 파라미터로 정확한 1회 호출
    """

    # 이미 로컬에서 검증 완료된 파라미터
    # API는 오직 실제 데이터 조회에만 사용
    return api.get_statistics_data(
        tbl_id=tbl_id,
        **params
    )
```

---

## 5. 사용 시나리오별 API 호출 비교

### 시나리오 1: 통계표 검색

```
질문: "청년 실업률 통계 찾아줘"

현재: API 1회 (검색)
최적화: API 0회 (로컬 검색)
```

### 시나리오 2: 통계표 상세 정보 확인

```
질문: "인구총조사 통계표 정보 알려줘"

현재: API 3~5회 (TBL + ITM + PRD + OBJ...)
최적화: API 0회 (로컬) 또는 1회 (분류값 캐시 미스시)
```

### 시나리오 3: 실제 데이터 조회

```
질문: "2023년 서울 인구수"

현재: API 5~10회 (검색 + 메타 + 데이터)
최적화: API 1회 (데이터만)
```

### 시나리오 4: 리포트 생성

```
질문: "고령화 관련 5개 지표 비교 리포트"

현재: API 25~50회
최적화: API 5회 (데이터만)
```

---

## 6. 구현 로드맵

### Phase 1: 메타데이터 DB 구축 (1주)

```
1. XLS → SQLite 변환 스크립트
2. FTS5 전문검색 인덱스 구축
3. 데이터 정규화 및 중복 제거
```

### Phase 2: 검색 최적화 (1주)

```
1. 하이브리드 검색 (FTS5 + 벡터)
2. 벡터 임베딩 생성 (OpenAI/Ollama)
3. 검색 결과 융합 알고리즘
```

### Phase 3: MCP 도구 리팩토링 (1주)

```
1. DISCOVER 레이어 → 로컬 우선
2. PLAN 레이어 → 캐시 우선
3. FETCH 레이어 → 데이터만
```

### Phase 4: 자동 업데이트 (선택)

```
1. KOSIS 메타데이터 정기 다운로드
2. 변경분 감지 및 동기화
3. 벡터 인덱스 증분 업데이트
```

---

## 7. 기대 효과

| 지표 | 현재 | 최적화 후 | 개선율 |
|-----|-----|---------|-------|
| 검색 API 호출 | 100% | 0% | -100% |
| 메타데이터 API 호출 | 100% | 5~10% | -90% |
| 총 API 호출 | 10회/질문 | 1~2회/질문 | -80~90% |
| 응답 시간 | 10초+ | 1~2초 | -80% |
| 오프라인 검색 | 불가 | 가능 | 신규 |
| 자동 추천 | 없음 | 벡터 유사도 | 신규 |

---

## 8. 결론

로컬 메타데이터 파일을 활용하면:

1. **API 호출 90% 감소**: 실제 데이터 조회만 API 사용
2. **응답 속도 5~10배 향상**: 로컬 검색은 밀리초 단위
3. **새로운 기능 가능**: 벡터 기반 의미 검색, 연관 통계 추천
4. **서버 부하 감소**: KOSIS 서버에 부담 최소화
5. **오프라인 검색**: 인터넷 없이도 통계표 검색 가능

**핵심 원칙**:
> "API는 오직 실제 데이터를 가져올 때만 사용한다.
> 찾기, 계획, 검증은 모두 로컬에서 처리한다."

---

*Generated: 2024-12-14*
