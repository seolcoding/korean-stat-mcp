# KOSIS MCP Server 종합 보고서

**날짜**: 2025-12-20
**버전**: 0.2.0
**상태**: ✅ 프로덕션 운영 중

---

## 📋 목차

1. [개요](#개요)
2. [시스템 아키텍처](#시스템-아키텍처)
3. [주요 기능](#주요-기능)
4. [테스트 결과](#테스트-결과)
5. [배포 현황](#배포-현황)
6. [사용 가이드](#사용-가이드)
7. [성능 지표](#성능-지표)

---

## 🎯 개요

**KOSIS MCP Server**는 대한민국 국가통계포털(KOSIS) 데이터를 AI 에이전트가 쉽게 활용할 수 있도록 지원하는 Model Context Protocol (MCP) 서버입니다.

### 핵심 가치

- **252,890개 통계표 즉시 검색**: 하이브리드 검색(Vector + BM25)으로 의미 기반 검색 지원
- **실시간 데이터 조회**: KOSIS OpenAPI를 통한 최신 통계 데이터 조회
- **자동 시각화**: Altair 기반 차트 자동 생성 및 R2 호스팅
- **코드 실행 환경**: 안전한 샌드박스에서 Python 분석 코드 실행
- **AI 친화적 설계**: LLM이 이해하기 쉬운 JSON 응답 구조

### MCP(Model Context Protocol)란?

MCP는 AI 모델이 외부 데이터와 도구에 안전하게 접근할 수 있도록 설계된 표준 프로토콜입니다.

```
┌─────────────┐      MCP Protocol       ┌──────────────┐
│             │◄─────────────────────────│              │
│  AI Agent   │   JSON-RPC over HTTP    │  MCP Server  │
│ (Claude AI) │─────────────────────────►│   (KOSIS)    │
└─────────────┘                          └──────────────┘
                                                │
                                                ▼
                                         ┌──────────────┐
                                         │ KOSIS API    │
                                         │ PostgreSQL   │
                                         │ R2 Storage   │
                                         └──────────────┘
```

---

## 🏗️ 시스템 아키텍처

### 계층 구조

```
┌─────────────────────────────────────────────────────────────┐
│                        MCP Layer                             │
│  - 24개 도구 (Tools)                                         │
│  - StreamableHTTP 프로토콜                                   │
│  - JSON-RPC 2.0                                              │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                     Service Layer                            │
│  - 통계 검색 (Search)                                        │
│  - 데이터 조회 (Fetch)                                       │
│  - 코드 실행 (Execute)                                       │
│  - 분석 도구 (Analyze)                                       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                              │
│  - PostgreSQL (252,890 테이블 메타데이터)                   │
│  - pgvector (1536차원 임베딩)                                │
│  - KOSIS OpenAPI                                             │
│  - Cloudflare R2 (차트/리포트 저장)                         │
└─────────────────────────────────────────────────────────────┘
```

### 기술 스택

| 계층 | 기술 | 용도 |
|------|------|------|
| **프레임워크** | FastMCP 2.14.0 | MCP 서버 구현 |
| **웹 서버** | Starlette + Uvicorn | HTTP/SSE 서빙 |
| **데이터베이스** | PostgreSQL 16 + pgvector | 메타데이터 + 벡터 검색 |
| **임베딩** | OpenAI text-embedding-3-small | 의미 기반 검색 |
| **시각화** | Altair 6.0 | 차트 생성 |
| **코드 실행** | Python 3.12 Sandbox | 안전한 분석 환경 |
| **스토리지** | Cloudflare R2 | 정적 파일 호스팅 |
| **배포** | Docker Compose | 컨테이너 오케스트레이션 |

### 데이터 흐름

```
1. 검색 요청
   User → Claude AI → MCP Server → PostgreSQL (Hybrid Search)
                                 → KOSIS API

2. 데이터 조회
   MCP Server → KOSIS API → 파싱 → 저장 (임시) → data_id 반환

3. 시각화
   코드 실행 → Altair 차트 → HTML 파일 → R2 업로드 → 공개 URL

4. 최종 리포트
   분석 + 차트 + 테이블 → HTML 조합 → R2 → URL
```

---

## ⚡ 주요 기능

### 1. 검색 도구 (Discover)

| 도구 | 설명 | 입력 예시 | 출력 |
|------|------|----------|------|
| `search_statistics` | KOSIS API 키워드 검색 | `"인구"` | 관련 통계표 목록 |
| `search_tables_hybrid` | 하이브리드 검색 (Vector + BM25) | `"저출산 고령화 추세"` | 의미 기반 랭킹 결과 |
| `browse_categories` | 기관/주제별 탐색 | `org_id="101"` | 통계청 전체 목록 |
| `get_table_metadata` | 테이블 구조 확인 | `tbl_id="DT_1B040A3"` | 컬럼, 기간, 항목 정보 |
| `get_available_values` | 필터 값 조회 | 테이블 ID | 지역/기간/항목 선택지 |

**검색 예시 (입력 → 출력)**

```json
// 입력: search_tables_hybrid
{
  "query": "서울 인구 변화",
  "limit": 5,
  "vector_weight": 0.7
}

// 출력
{
  "total_count": 5,
  "results": [
    {
      "tbl_id": "DT_1B040A3",
      "tbl_nm": "행정구역(시군구)별 성별 인구수",
      "org_nm": "통계청",
      "score": 0.8924,
      "period": "1992 ~ 2023"
    }
  ]
}
```

### 2. 데이터 조회 (Fetch)

| 도구 | 설명 | 특징 |
|------|------|------|
| `get_statistics_data` | KOSIS 실데이터 조회 | 자동 파싱, data_id 반환 |
| `list_stored_data` | 저장된 데이터 목록 | 재사용 가능한 data_id 확인 |
| `read_stored_data` | 저장된 데이터 읽기 | 청크 단위 읽기 지원 |

**데이터 조회 예시**

```json
// 입력: get_statistics_data
{
  "org_id": "101",
  "tbl_id": "DT_1B040A3",
  "start_date": "2020",
  "end_date": "2023",
  "format": "summary"
}

// 출력
{
  "summary": {
    "total_records": 3459,
    "period_range": "2020~2023",
    "items": ["남자인구수", "여자인구수", "총인구수"]
  },
  "metadata": {
    "tbl_nm": "행정구역(시군구)별 성별 인구수",
    "unit": "명"
  },
  "data_preview": [
    {"기간": "2023", "분류1": "전국", "항목": "총인구수", "값": "51325329"}
  ]
}
```

### 3. 코드 실행 (Execute)

| 도구 | 설명 | 자동 제공 함수 |
|------|------|--------------|
| `execute_code` | 범용 Python 코드 실행 | `data`, `pd`, `np`, `json` |
| `execute_visualization` | 차트 생성 전용 | `prepare_data()`, `save_chart()`, `alt` |
| `execute_analysis` | 통계 분석 전용 | `calc_change_rate()`, `calc_cagr()`, `to_thousand()` |
| `execute_table` | HTML 테이블 생성 | `create_table()`, 스타일링 자동 |
| `execute_report` | 복합 리포트 조합 | `build_report()` |

**시각화 예시 (입력 → 출력)**

```python
# 입력: execute_visualization
code = '''
df = prepare_data(data, numeric_fields=["DT"])
df["인구_천명"] = df["DT"] / 1000

chart = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X("PRD_DE:N", title="연도"),
    y=alt.Y("인구_천명:Q", title="인구 (천 명)",
            axis=alt.Axis(format=",.0f")),
).properties(title="인구 추이", width=600, height=350)

return save_chart(chart, "population.html")
'''

# 출력
{
  "success": true,
  "result": {
    "url": "https://pub-2563a36b1b9e4e208ea0718e1056b358.r2.dev/charts/abc123_population.html",
    "type": "chart",
    "format": "html"
  }
}
```

### 4. 분석 도구 (Analyze)

| 도구 | 설명 | 사용 예시 |
|------|------|----------|
| `analyze_trend` | 추세 분석 (CAGR) | 10년간 인구 증감률 |
| `analyze_comparison` | 지역/항목 비교 | 서울 vs 부산 인구 |
| `analyze_ranking` | 순위 분석 | 증가율 상위/하위 5개 |
| `aggregate_statistics` | 집계 (sum/avg/min/max) | 연도별 전국 총인구 |
| `filter_statistics` | 필터링 | 서울 데이터만 추출 |

### 5. 데이터 액세스 (Data Access)

| 도구 | 설명 |
|------|------|
| `list_stored_data` | 저장된 파일 목록 |
| `read_stored_data` | 원본 데이터 읽기 |

---

## 🧪 테스트 결과

### 기본 테스트 (6/6 통과) ✅

| 항목 | 결과 | 상세 |
|------|------|------|
| Health Check | ✅ | DB 연결됨, 252,890개 테이블 |
| Info Endpoint | ✅ | 버전 0.2.0 확인 |
| Database Query | ✅ | 서버 시간: 2025-12-20 07:32:09 UTC |
| Static Files (R2) | ✅ | R2 버킷 접근 가능 |
| MCP tools/list | ✅ | 24개 도구 발견 |
| MCP 통계검색 | ✅ | '인구' 검색 결과 수신 |

**실행 방법**:
```bash
uv run python scripts/test_mcp_server.py ${KOSIS_MCP_URL}
```

### E2E 워크플로 테스트 (5/5 통과) ✅

| 시나리오 | 결과 | 상세 |
|----------|------|------|
| [1] 통계 검색 | ✅ | KOSIS API 키워드 검색 성공 |
| [2] 하이브리드 검색 | ✅ | PostgreSQL + Vector 검색 성공 |
| [3] 데이터 조회 | ✅ | 3,459건 (2020~2023, 3개 항목) |
| [4] 시각화 + R2 | ✅ | 차트 생성 및 R2 업로드 성공 |
| [5] 분석 실행 | ✅ | 통계 분석 및 인사이트 생성 |

**테스트 출력 샘플**:

```
[3] 데이터 조회 (get_statistics_data)
--------------------------------------------------
  ✅ 데이터 조회 성공
     - 레코드 수: 3459
     - 기간: 2020~2023
     - 항목: 남자인구수, 여자인구수, 총인구수

[4] 시각화 생성 (execute_visualization)
--------------------------------------------------
  ✅ 차트 생성 성공!
     - URL: https://pub-2563a36b1b9e4e208ea0718e1056b358.r2.dev/charts/2a70606f_population_trend.html
     - 스토리지: Cloudflare R2 ✅

[5] 분석 실행 (execute_analysis)
--------------------------------------------------
  ✅ 분석 완료!
     - 시작연도: 2020
     - 종료연도: 2023
     - 시작인구: 51,829.0천 명
     - 종료인구: 51,558.0천 명
     - 총변화율: -0.52%
```

**실행 방법**:
```bash
uv run python scripts/test_e2e_workflow.py ${KOSIS_MCP_URL}
```

### R2 스토리지 검증

생성된 차트 URL이 실제로 접근 가능한지 확인:

```bash
curl -I "https://pub-2563a36b1b9e4e208ea0718e1056b358.r2.dev/charts/2a70606f_population_trend.html"

# 응답
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
```

✅ R2 호스팅 정상 작동

---

## 🚀 배포 현황

### 원격 서버 (사용자 자체 호스팅 예시)

| 항목 | 정보 |
|------|------|
| 호스트 | 사용자 자체 호스팅 |
| 업타임 | 1주 1일 5시간+ |
| OS | Ubuntu 24.04 (Kernel 6.14.0-36) |
| 디스크 | 457GB (사용률 57%) |
| Docker | active ✅ |

### 컨테이너 상태

```bash
CONTAINER           STATUS
kosis-mcp           Up 46 hours (healthy) ✅
kosis-postgres      Up 46 hours (healthy) ✅
```

### PostgreSQL 데이터

```sql
SELECT COUNT(*) FROM kosis_tables;
-- 결과: 252,890

SELECT COUNT(*) FROM kosis_tables WHERE embedding IS NOT NULL;
-- 결과: 252,890 (100% 임베딩 완료)
```

### 접속 정보

| 엔드포인트 | URL |
|-----------|-----|
| **Cloudflare Tunnel** | `${KOSIS_MCP_URL}` |
| Health Check | `/health` |
| Info | `/info` |
| MCP Protocol | `/` (POST, StreamableHTTP) |
| R2 Storage | `https://pub-2563a36b1b9e4e208ea0718e1056b358.r2.dev` |

### 환경 변수

```bash
DATABASE_URL=postgresql://kosis:***@postgres:5432/kosis
R2_BUCKET_NAME=kosis-assets
R2_PUBLIC_URL=https://pub-2563a36b1b9e4e208ea0718e1056b358.r2.dev
ARTIFACT_STORAGE=auto
FASTMCP_STATELESS_HTTP=true
```

---

## 📖 사용 가이드

### Claude Desktop 연결 (권장)

**1. Claude Desktop 설정 파일 편집**

macOS:
```bash
code ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**2. MCP 서버 추가**

```json
{
  "mcpServers": {
    "kosis": {
      "url": "${KOSIS_MCP_URL}",
      "transport": "streamable-http"
    }
  }
}
```

**3. Claude Desktop 재시작**

**4. 사용 예시**

```
User: "서울과 부산의 최근 5년 인구 변화를 비교해주세요"

Claude: [search_tables_hybrid 호출]
       → [get_statistics_data 호출]
       → [execute_visualization 호출]
       → "분석 결과를 차트로 보여드립니다: [R2 URL]"
```

### 직접 API 호출

```bash
curl -X POST ${KOSIS_MCP_URL}/ \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "search_statistics",
      "arguments": {"keyword": "인구", "limit": 5}
    }
  }'
```

### 로컬 개발

```bash
# 1. 저장소 클론
git clone https://github.com/seolcoding/kosis-mcp.git
cd kosis-mcp

# 2. 환경 변수 설정
cp .env.example .env
# DATABASE_URL, KOSIS_API_KEY 등 설정

# 3. Docker Compose 실행
docker compose up -d

# 4. 헬스 체크
curl http://localhost:8001/health
```

---

## 📊 성능 지표

### 검색 성능

| 검색 유형 | 평균 응답 시간 | 정확도 |
|----------|---------------|--------|
| 키워드 검색 (API) | ~500ms | 정확 매칭 |
| 하이브리드 검색 (DB) | ~200ms | 의미 기반 랭킹 |

### 데이터 처리

| 작업 | 처리량 | 비고 |
|------|--------|------|
| 데이터 조회 | ~1,000 레코드/초 | KOSIS API 제한 |
| 차트 생성 | ~2초 | Altair 렌더링 포함 |
| R2 업로드 | ~500ms | 평균 파일 크기 100KB |

### 메타데이터 DB

- **테이블 수**: 252,890개
- **임베딩 차원**: 1536 (OpenAI text-embedding-3-small)
- **인덱스**: HNSW (벡터), GIN (전문검색)
- **저장 용량**: ~5.14GB (Docker volume)

---

## 🎓 활용 사례

### 1. 인구 통계 분석

```
User: "대한민국 17개 시도의 인구 증감률을 순위별로 보여주세요"

AI 워크플로:
1. search_tables_hybrid("시도별 인구")
2. get_statistics_data(전체 시도, 2019-2023)
3. execute_analysis(변화율 계산)
4. execute_visualization(순위 막대 차트)
5. execute_report(분석 + 차트 조합)
```

### 2. 경제 지표 대시보드

```
User: "GDP, 물가상승률, 실업률을 종합한 경제 대시보드를 만들어주세요"

AI 워크플로:
1. search_statistics("GDP") × 3개 지표
2. get_statistics_data × 3회
3. execute_visualization × 3회 (라인, 막대, 영역 차트)
4. execute_analysis (지표간 상관관계)
5. execute_report (최종 대시보드)
```

### 3. 지역 비교 리포트

```
User: "서울, 부산, 대구의 출산율과 고령화율을 비교해주세요"

AI 워크플로:
1. search_tables_hybrid("출산율"), search_tables_hybrid("고령화율")
2. get_statistics_data (3개 지역 필터)
3. execute_visualization (비교 라인 차트)
4. execute_table (비교 테이블)
5. execute_report (인사이트 포함)
```

---

## 🔒 보안 및 제약사항

### 보안 조치

- ✅ 코드 실행: 샌드박스 환경 (제한된 패키지만 허용)
- ✅ API 키: 환경 변수로 관리 (소스 코드에 포함 안 함)
- ✅ 데이터 저장: 임시 파일은 24시간 후 자동 삭제
- ✅ R2 스토리지: 공개 읽기 전용, 쓰기는 서버만

### 제약사항

- **KOSIS API Rate Limit**: 초당 1회 권장 (서버가 자동 조절)
- **데이터 크기**: 단일 조회 최대 10,000 레코드
- **차트 복잡도**: 권장 시리즈 수 5개 이하
- **코드 실행 시간**: 최대 30초

---

## 📈 향후 계획

### Phase 6 (예정)

- [ ] Cloudflare 영구 터널 설정
- [ ] 사용자 인증/권한 시스템
- [ ] 데이터 캐싱 최적화
- [ ] 추가 시각화 유형 (히트맵, 트리맵)
- [ ] 다국어 지원 (영문 통계표 검색)

### Phase 7 (검토 중)

- [ ] Webhook 알림 (새 통계표 업데이트 시)
- [ ] 배치 작업 스케줄러
- [ ] 데이터 내보내기 (CSV, Excel)
- [ ] Claude API 통합 (자동 인사이트 생성)

---

## 🛠️ 개발자 참고

### 프로젝트 구조

```
kosis-mcp/
├── src/
│   ├── mcp_server/
│   │   ├── server.py              # MCP 도구 정의 (24개)
│   │   └── app.py                 # FastAPI HTTP 앱
│   └── kosis_tools/
│       ├── search.py              # KOSIS API 검색
│       ├── hybrid_search.py       # 하이브리드 검색
│       ├── code_executor.py       # 코드 실행 엔진
│       ├── executors/             # 모듈형 실행기
│       │   ├── visualization.py   # 차트 생성
│       │   ├── analysis.py        # 통계 분석
│       │   ├── table.py           # 테이블 생성
│       │   └── report.py          # 리포트 조합
│       ├── database.py            # PostgreSQL 연결
│       ├── embeddings.py          # OpenAI 임베딩
│       └── r2_storage.py          # Cloudflare R2
├── scripts/
│   ├── test_mcp_server.py         # 기본 테스트
│   └── test_e2e_workflow.py       # E2E 테스트
├── docker-compose.yml             # 로컬 개발 환경
├── docker-compose.remote.yml      # 원격 배포용
└── migrations/
    └── init.sql                   # DB 스키마
```

### 주요 커맨드

```bash
# 테스트
uv run python scripts/test_mcp_server.py <URL>
uv run python scripts/test_e2e_workflow.py <URL>

# 로컬 실행
docker compose up -d

# 원격 배포
docker compose -f docker-compose.remote.yml up -d --build

# 로그 확인
docker compose logs -f kosis-mcp

# 메타데이터 로드
docker compose run updater
```

---

## 📞 연락처 및 리소스

- **GitHub**: https://github.com/seolcoding/kosis-mcp
- **KOSIS 공식 사이트**: https://kosis.kr
- **FastMCP 문서**: https://gofastmcp.com
- **MCP 프로토콜**: https://modelcontextprotocol.io

---

## 📝 변경 이력

### v0.2.0 (2025-12-20)

- ✅ 원격 서버 배포 완료
- ✅ Cloudflare Tunnel 연결
- ✅ R2 스토리지 통합
- ✅ E2E 테스트 스크립트 추가
- ✅ 데이터베이스 초기화 개선

### v0.1.0 (2025-12-15)

- ✅ 기본 MCP 서버 구현
- ✅ 24개 도구 개발
- ✅ PostgreSQL + pgvector 통합
- ✅ 하이브리드 검색 구현

---

**© 2025 KOSIS MCP Server - All Rights Reserved**
