# KOSIS MCP Server - User Guide

> **버전**: 1.0
> **최종 업데이트**: 2024-12-15
> **대상 독자**: KOSIS MCP Server 사용자, Claude Desktop 사용자

---

## 목차

1. [시작하기](#1-시작하기)
2. [기본 사용법](#2-기본-사용법)
3. [MCP 도구 상세 가이드](#3-mcp-도구-상세-가이드)
4. [실전 예제](#4-실전-예제)
5. [시각화 가이드](#5-시각화-가이드)
6. [트러블슈팅](#6-트러블슈팅)
7. [FAQ](#7-faq)

---

## 1. 시작하기

### 1.1 KOSIS란?

[KOSIS (국가통계포털)](https://kosis.kr/)는 통계청에서 운영하는 한국의 공식 통계 데이터 포털입니다. 인구, 경제, 사회, 환경 등 다양한 분야의 250,000개 이상의 통계 테이블을 제공합니다.

### 1.2 KOSIS MCP Server의 역할

KOSIS MCP Server는 AI 에이전트(Claude 등)가 KOSIS 데이터를 직접 검색하고 분석할 수 있게 해주는 다리 역할을 합니다.

```
┌─────────────────┐      MCP Protocol      ┌─────────────────┐      API      ┌─────────────────┐
│   Claude        │  ◄─────────────────►   │  KOSIS MCP      │  ◄─────────►  │   KOSIS         │
│   (AI Agent)    │                        │  Server         │               │   OpenAPI       │
└─────────────────┘                        └─────────────────┘               └─────────────────┘
```

### 1.3 설치 및 설정

#### KOSIS API 키 발급

1. [KOSIS OpenAPI 페이지](https://kosis.kr/openapi/) 방문
2. 회원가입 후 로그인
3. "인증키 발급" 메뉴에서 API 키 발급 신청
4. 발급받은 키를 `.env` 파일에 설정

#### Claude Desktop 설정

**macOS:**
```bash
# 설정 파일 위치
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```bash
# 설정 파일 위치
%APPDATA%\Claude\claude_desktop_config.json
```

**설정 예시 (HTTP 모드):**
```json
{
  "mcpServers": {
    "kosis": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**설정 예시 (stdio 모드):**
```json
{
  "mcpServers": {
    "kosis": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/kosis-mcp", "python", "-m", "mcp_server"],
      "env": {
        "KOSIS_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

---

## 2. 기본 사용법

### 2.1 권장 워크플로우

KOSIS MCP Server는 3단계 워크플로우를 권장합니다:

```
1. DISCOVER (검색)  →  2. FETCH (조회)  →  3. EXECUTE (분석/시각화)
```

**예시 대화:**

```
사용자: "최근 5년 출생아수 추이를 그래프로 보여줘"

Claude의 작업:
1. search_statistics("출생") → 관련 테이블 검색
2. get_statistics_data(...) → 데이터 조회 (data_id 획득)
3. execute_visualization(...) → 차트 생성
   → 결과: http://localhost:8000/artifacts/charts/birth_trend.html
```

### 2.2 자연어 요청 예시

| 요청 유형 | 예시 |
|----------|------|
| 데이터 검색 | "인구 관련 통계표 찾아줘" |
| 추세 분석 | "서울 인구 변화 추이 보여줘" |
| 비교 분석 | "시도별 고용률 비교해줘" |
| 시각화 | "GDP 성장률 그래프 만들어줘" |
| 리포트 | "출산율 분석 리포트 작성해줘" |

---

## 3. MCP 도구 상세 가이드

### 3.1 Layer 1: DISCOVER (데이터 탐색)

#### search_statistics

키워드로 KOSIS 통계표를 검색합니다.

```
파라미터:
- keyword (필수): 검색 키워드 (예: "인구", "고용", "GDP")
- org_id (선택): 기관 ID로 필터링
  - "101" = 통계청
  - "154" = 고용노동부
  - "301" = 한국은행
- limit (선택): 최대 결과 수 (기본: 10)

응답:
- results: 검색된 테이블 목록
- org_distribution: 기관별 결과 분포
- next_step: 다음 단계 안내
```

**예시:**
```
search_statistics("출생", limit=5)

결과:
{
  "query": "출생",
  "result_count": 5,
  "results": [
    {"tbl_id": "DT_1B8000F", "tbl_nm": "시도/성/연령별 출생아수", "org_nm": "통계청"},
    ...
  ],
  "next_step": "get_table_metadata(org_id, tbl_id)로 테이블 구조 확인"
}
```

#### 하이브리드 검색 제거 안내

이전 하이브리드 검색 도구는 v0.1.0 공개 릴리스에서 제거되었습니다. 현재 기본 검색은 KOSIS 공식 `statisticsSearch.do`를 감싼 `search_statistics`입니다.

```python
search_statistics("경제", limit=10)
```

PostgreSQL은 선택적 FTS 메타데이터 검색용으로만 남아 있으며, 기본 설치와 기본 MCP 도구 사용에는 필요하지 않습니다.

#### get_table_metadata

테이블의 상세 구조와 분류 정보를 조회합니다.

```
파라미터:
- org_id (필수): 기관 ID
- tbl_id (필수): 테이블 ID

응답:
- 테이블명, 기간, 주기
- 분류 항목 (C1, C2, C3...)
- 항목 목록 (ITM_ID, ITM_NM)
```

### 3.2 Layer 2: FETCH (데이터 조회)

#### get_statistics_data

KOSIS API에서 실제 통계 데이터를 조회합니다.

> **핵심**: 원본 데이터는 서버에 저장되고, LLM에게는 요약만 전달됩니다.

```
파라미터:
- org_id (필수): 기관 ID
- tbl_id (필수): 테이블 ID
- prd_de (선택): 기간 (예: "2020", "202001")
- prd_se (선택): 주기 ("Y"=연, "Q"=분기, "M"=월)
- c1, c2, c3... (선택): 분류 항목 필터

응답:
- data_id: 저장된 데이터 참조 ID (중요!)
- summary: 데이터 요약 (건수, 기간, 샘플)
- next_step: execute_code 사용 안내
```

**예시:**
```
get_statistics_data(
  org_id="101",
  tbl_id="DT_1B040A3",
  prd_de="2019:2023"
)

결과:
{
  "data_id": "abc123",
  "total_records": 1500,
  "date_range": "2019 ~ 2023",
  "sample": [...처음 5개 레코드...],
  "next_step": "execute_code(data_id='abc123', code='...')로 분석"
}
```

#### filter_statistics

저장된 데이터를 조건으로 필터링합니다.

```
파라미터:
- data_id (필수): 데이터 참조 ID
- conditions (필수): 필터 조건
  예: {"C1_NM": "서울특별시", "PRD_DE": "2023"}
```

#### aggregate_statistics

데이터를 그룹별로 집계합니다.

```
파라미터:
- data_id (필수): 데이터 참조 ID
- group_by (필수): 그룹화 기준 필드
- agg_function (선택): 집계 함수 ("sum", "mean", "count", "min", "max")
```

### 3.3 Layer 3: EXECUTE (코드 실행)

#### execute_code

Python 코드를 서버에서 실행합니다. **가장 강력하고 유연한 도구입니다.**

```
파라미터:
- code (필수): 실행할 Python 코드
- data_id (선택): 사용할 데이터 참조 ID

사용 가능한 라이브러리:
- pandas (as pd)
- numpy (as np)
- altair (as alt)
- json, math, datetime

사전 정의된 헬퍼 함수:
- prepare_data(data, numeric_fields=["DT"]): 데이터 전처리
- save_chart(chart, filename): 차트 저장 및 URL 반환
- to_thousand(value): 천 단위 변환
- calc_change_rate(new, old): 변화율 계산
- calc_cagr(start, end, years): 연평균성장률 계산
```

**예시:**
```python
execute_code(
  data_id="abc123",
  code='''
df = prepare_data(data, numeric_fields=["DT"])
df["인구_천명"] = df["DT"] / 1000

chart = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X("PRD_DE:N", title="연도"),
    y=alt.Y("인구_천명:Q", title="인구 (천 명)")
).properties(width=600, height=400, title="인구 추이")

return save_chart(chart, "population.html")
'''
)
```

#### execute_visualization

시각화에 특화된 실행기입니다. 차트 가이드라인이 자동 적용됩니다.

```
자동 적용되는 가이드라인:
- Y축 format=",.0f" (천 단위 구분자)
- 과학적 표기법 금지
- 적절한 차트 크기
```

#### execute_analysis

통계 분석에 특화된 실행기입니다.

```
사전 정의된 분석 함수:
- calc_change_rate(new, old): 변화율 (%)
- calc_cagr(start, end, years): 연평균성장률
- to_thousand(value): 천 단위 변환
- format_number(value): 한국식 숫자 포맷
```

#### execute_report

차트, 분석, 테이블을 조합한 HTML 리포트를 생성합니다.

```python
execute_report(
  code='''
return build_report(
    title="인구 분석 리포트",
    analysis=analysis_result,
    charts=["chart1.html", "chart2.html"],
    tables=[table_html],
    source="통계청 KOSIS"
)
'''
)
```

---

## 4. 실전 예제

### 4.1 인구 추이 분석

```
사용자: "서울 인구가 어떻게 변화했는지 최근 10년 추이를 보여줘"
```

Claude의 작업 과정:

**Step 1: 데이터 검색**
```
search_statistics("서울 인구")
→ 결과: DT_1B040A3 (주민등록인구현황)
```

**Step 2: 데이터 조회**
```
get_statistics_data(
  org_id="101",
  tbl_id="DT_1B040A3",
  prd_de="2014:2023",
  c1="11"  # 서울특별시 코드
)
→ data_id: "seoul_pop_123"
```

**Step 3: 시각화**
```python
execute_visualization(
  data_id="seoul_pop_123",
  code='''
df = prepare_data(data, numeric_fields=["DT"])

chart = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X("PRD_DE:N", title="연도"),
    y=alt.Y("DT:Q", title="인구 (명)", axis=alt.Axis(format=",.0f"))
).properties(title="서울특별시 인구 추이 (2014-2023)")

return save_chart(chart, "seoul_population.html")
'''
)
```

### 4.2 시도별 비교 분석

```
사용자: "시도별 고용률을 비교해줘"
```

**Step 1: 검색**
```
search_statistics("고용률")
→ 결과: DT_1ES1002 (지역별 고용률)
```

**Step 2: 조회**
```
get_statistics_data(org_id="101", tbl_id="DT_1ES1002", prd_de="2023")
→ data_id: "emp_rate_2023"
```

**Step 3: 비교 차트**
```python
execute_visualization(
  data_id="emp_rate_2023",
  code='''
df = prepare_data(data, numeric_fields=["DT"])
df = df[df["C1_NM"] != "전국"]  # 전국 제외

chart = alt.Chart(df).mark_bar().encode(
    x=alt.X("DT:Q", title="고용률 (%)"),
    y=alt.Y("C1_NM:N", title="시도", sort="-x"),
    color=alt.condition(
        alt.datum.DT >= 60,
        alt.value("steelblue"),
        alt.value("lightgray")
    )
).properties(title="2023년 시도별 고용률 비교")

return save_chart(chart, "employment_comparison.html")
'''
)
```

### 4.3 종합 리포트 생성

```
사용자: "출산율 분석 리포트를 만들어줘"
```

**Step 1: 데이터 조회**
```
get_statistics_data(org_id="101", tbl_id="DT_1B8000F", prd_de="2013:2023")
→ data_id: "birth_data"
```

**Step 2: 분석 수행**
```python
execute_analysis(
  data_id="birth_data",
  code='''
df = prepare_data(data, numeric_fields=["DT"])

total_2023 = df[df["PRD_DE"] == "2023"]["DT"].sum()
total_2013 = df[df["PRD_DE"] == "2013"]["DT"].sum()

return {
    "summary": {
        "2023년 출생아수": f"{to_thousand(total_2023):,.0f}천 명",
        "2013년 출생아수": f"{to_thousand(total_2013):,.0f}천 명",
        "10년간 변화율": f"{calc_change_rate(total_2023, total_2013):.1f}%",
        "연평균 감소율": f"{calc_cagr(total_2013, total_2023, 10):.1f}%"
    }
}
'''
)
```

**Step 3: 차트 생성**
```python
execute_visualization(data_id="birth_data", code="...")
→ birth_trend.html
```

**Step 4: 리포트 조합**
```python
execute_report(
  code='''
return build_report(
    title="대한민국 출산율 분석 리포트",
    analysis=analysis_result,
    charts=["birth_trend.html"],
    source="통계청 KOSIS, 2013-2023"
)
'''
)
→ http://localhost:8000/artifacts/reports/birth_report.html
```

---

## 5. 시각화 가이드

### 5.1 숫자 포맷 규칙

| 데이터 유형 | 권장 포맷 | 예시 |
|------------|----------|------|
| 인구 | 천 명 단위 | `9,386천 명` |
| 금액 | 억/조 원 단위 | `1,234조 원` |
| 비율 | 소수점 1자리 | `62.5%` |
| Y축 | format=",.0f" | 천 단위 구분자 |

### 5.2 차트 유형 선택

| 분석 목적 | 권장 차트 | Altair 마크 |
|----------|----------|------------|
| 시간 추세 | 선 그래프 | `mark_line()` |
| 비교 | 막대 그래프 | `mark_bar()` |
| 분포 | 히스토그램 | `mark_bar()` |
| 관계 | 산점도 | `mark_circle()` |
| 구성비 | 파이/도넛 | `mark_arc()` |

### 5.3 차트 코드 템플릿

**선 그래프 (추세 분석)**
```python
chart = alt.Chart(df).mark_line(point=True).encode(
    x=alt.X("PRD_DE:N", title="연도"),
    y=alt.Y("value:Q", title="값", axis=alt.Axis(format=",.0f")),
    color="category:N"
).properties(width=600, height=400, title="제목")
```

**막대 그래프 (비교)**
```python
chart = alt.Chart(df).mark_bar().encode(
    x=alt.X("value:Q", title="값"),
    y=alt.Y("category:N", sort="-x", title="항목"),
    color=alt.value("steelblue")
).properties(width=600, height=400, title="제목")
```

---

## 6. 트러블슈팅

### 6.1 일반적인 오류

#### "DATABASE_NOT_AVAILABLE" 오류

**원인**: PostgreSQL이 연결되지 않음 (하이브리드 검색 기능)

**해결**:
1. Docker Compose로 실행 중인지 확인
2. `DATABASE_URL` 환경변수 확인
3. 키워드 검색 (`search_statistics`)으로 대체

#### "DT 필드 형변환 오류"

**원인**: KOSIS API의 DT 필드는 문자열입니다.

**해결**:
```python
# prepare_data 함수 사용 (자동 변환)
df = prepare_data(data, numeric_fields=["DT"])

# 또는 수동 변환
df["DT"] = pd.to_numeric(df["DT"], errors="coerce")
```

#### "빈 차트가 생성됨"

**원인**: 데이터 필터링 결과가 비어있거나, 필드명 불일치

**해결**:
```python
# 1. 데이터 확인
print(df.head())
print(df.columns.tolist())

# 2. 필드명 확인
# PRD_DE, C1_NM, C2_NM, DT, ITM_NM 등
```

### 6.2 성능 최적화

#### 대용량 데이터 처리

```python
# 나쁜 예: 전체 데이터를 LLM에 전달
get_statistics_data(..., view="full")  # 토큰 폭발!

# 좋은 예: 요약만 받고 서버에서 처리
data_id = get_statistics_data(..., view="summary")
execute_code(data_id=data_id, code="...")  # 서버에서 처리
```

#### 청크 단위 조회

```python
# 데이터가 너무 클 때
filter_statistics(data_id="...", conditions={"PRD_DE": "2023"})
# 또는
read_stored_data(data_id="...", chunk_index=0)
```

---

## 7. FAQ

### Q: KOSIS API 키는 어디서 발급받나요?

[KOSIS OpenAPI 페이지](https://kosis.kr/openapi/)에서 회원가입 후 발급받을 수 있습니다. 무료입니다.

### Q: 하이브리드 검색과 키워드 검색의 차이는?

- **키워드 검색** (`search_statistics`): KOSIS API 직접 호출, 정확한 키워드 필요
- **하이브리드 검색**: v0.1.0에서 제거됨. 의미 검색이 필요하면 별도 애플리케이션 레이어에서 구현하세요.

### Q: 차트가 열리지 않아요

1. 서버가 실행 중인지 확인: `curl http://localhost:8000/health`
2. 아티팩트 URL 확인: `http://localhost:8000/artifacts/charts/...`
3. CORS 설정 확인 (다른 도메인에서 접근 시)

### Q: execute_code에서 어떤 라이브러리를 쓸 수 있나요?

- pandas, numpy, altair (기본 제공)
- json, math, datetime (기본 제공)
- matplotlib, plotly 등은 지원하지 않습니다 (Altair 사용)

### Q: 데이터는 얼마나 오래 저장되나요?

서버 재시작 전까지 메모리/임시 파일에 저장됩니다. 영구 저장이 필요하면 리포트로 내보내세요.

---

## 추가 리소스

- [KOSIS 100대 지표](https://kosis.kr/visual/nsportalStats/main.do)
- [KOSIS API 매뉴얼](https://kosis.kr/openapi/)
- [Altair 문서](https://altair-viz.github.io/)
- [FastMCP 문서](https://gofastmcp.com/)

---

*문서 피드백이나 질문은 [GitHub Issues](https://github.com/seolcoding/korean-stat-mcp/issues)에 남겨주세요.*
