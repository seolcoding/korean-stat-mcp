# KOSIS MCP Server - 코드베이스 워크쓰루

> 이 문서는 프로젝트의 전체 구조와 데이터 흐름을 설명합니다.
> LLM에게 지시하거나 코드를 수정할 때 참고하세요.

---

## 1. 프로젝트 개요

### 1.1 프로젝트 목적
KOSIS(국가통계포털) OpenAPI의 데이터를 **MCP(Model Context Protocol)** 서버로 제공하여,
Claude 같은 LLM이 한국 공공통계 데이터를 조회/분석/시각화할 수 있게 합니다.

### 1.2 핵심 철학 (MCP_PATTERN.md)
```
❌ 안티패턴: API → 전체 데이터 → LLM 컨텍스트 (토큰 폭발!)
✅ 권장 패턴: API → 서버 저장 → 요약만 LLM에 → 필요시 청크 요청
```

**핵심 원칙**: 데이터는 서버에, 요약만 모델에

---

## 2. 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│                          MCP Server                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    mcp_server.py                              │   │
│  │  @mcp.tool() 데코레이터로 도구 등록                            │   │
│  └─────────────────────────┬────────────────────────────────────┘   │
│                            │                                         │
│  ┌─────────────────────────┼────────────────────────────────────┐   │
│  │         Layer 1: DISCOVER      │        Layer 2: FETCH        │   │
│  │  ┌─────────────┐ ┌────────────┐│┌───────────┐ ┌─────────────┐│   │
│  │  │   search    │ │   list_    ││ │   data    │ │  transform  ││   │
│  │  │ _statistics │ │organizations│││.get_data()│ │(filter/agg) ││   │
│  │  └──────┬──────┘ └──────┬─────┘│└─────┬─────┘ └──────┬──────┘│   │
│  │         │               │      │      │              │        │   │
│  │         └───────┬───────┘      │      └──────┬───────┘        │   │
│  │                 ↓              │             ↓                │   │
│  │  ┌─────────────────────────────┴─────────────────────────────┐│   │
│  │  │                    Layer 3: PRESENT                       ││   │
│  │  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ││   │
│  │  │  │ visualize │ │analyze_*  │ │ text_*    │ │ report_   │ ││   │
│  │  │  │ (Plotly)  │ │(trend/cmp)│ │(headline) │ │generator  │ ││   │
│  │  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘ ││   │
│  │  └──────────────────────────────────────────────────────────┘│   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                     Core Modules                                ││
│  │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐   ││
│  │  │ base   │  │ config │  │ search │  │  data  │  │table_  │   ││
│  │  │.py     │  │.py     │  │.py     │  │.py     │  │meta.py │   ││
│  │  └────────┘  └────────┘  └────────┘  └────────┘  └────────┘   ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                ↓
                    ┌───────────────────────┐
                    │    KOSIS OpenAPI      │
                    │  kosis.kr/openapi     │
                    └───────────────────────┘
```

---

## 3. 파일별 역할

### 3.1 Core Layer (기반 모듈)

| 파일 | 역할 | 주요 클래스/함수 |
|------|------|------------------|
| `base.py` | HTTP 클라이언트, rate limiting, 에러 핸들링 | `KosisBaseClient` |
| `config.py` | 환경변수, API 엔드포인트, 설정 상수 | `KosisConfig`, `Endpoints`, `PeriodType` |
| `search.py` | 통계표 키워드 검색 | `StatisticsSearch.search()` |
| `data.py` | 실제 통계 데이터 조회 | `StatisticsData.get_data()`, `get_data_auto_period()` |
| `table_meta.py` | 테이블 메타데이터 조회 | `TableMetadata.get_metadata()` |
| `list_categories.py` | 기관/테마 목록 조회 | `CategoryList`, `OrgCode`, `ThemeCode` |

### 3.2 Transform Layer (데이터 변환)

| 파일 | 역할 | 주요 클래스/함수 |
|------|------|------------------|
| `transform.py` | DataFrame 변환, 피벗, 필터링, 집계 | `KosisTransformer`, `filter_data()`, `to_dataframe()` |

**KosisTransformer 주요 메서드:**
```python
tx = KosisTransformer(data)
tx.filter_by("C1_NM", "서울특별시")     # 필터링
tx.pivot(index="C1_NM", columns="PRD_DE")  # 피벗 테이블
tx.groupby("PRD_DE", {"DT": "sum"})    # 그룹별 집계
tx.rank_by("DT", top_n=10)             # 순위
tx.calculate_growth()                   # 성장률 계산
tx.get_llm_context()                    # LLM용 요약 텍스트
```

### 3.3 Visualization Layer (시각화)

| 파일 | 역할 | 주요 클래스/함수 |
|------|------|------------------|
| `visualize.py` | Plotly 기반 인터랙티브 차트 | `KosisVisualizer`, `quick_line()`, `quick_bar()` |

**지원 차트 유형:**
- `line_chart()` - 시계열 추이
- `bar_chart()` - 항목별 비교
- `pie_chart()` - 구성비
- `heatmap()` - 2차원 매트릭스
- `scatter_chart()` - 산점도

### 3.4 Report Layer (리포트 생성)

| 파일 | 역할 | 주요 클래스/함수 |
|------|------|------------------|
| `report_generator.py` | 유저 쿼리 기반 동적 리포트 | `ReportGenerator`, `generate_html()` |
| `report_tools.py` | MCP 도구용 리포트 빌딩 블록 | `viz_*`, `analyze_*`, `text_*`, `layout_*` |

### 3.5 MCP Server (진입점)

| 파일 | 역할 |
|------|------|
| `mcp_server.py` | FastMCP 서버, `@mcp.tool()` 등록, 도구 라우팅 |

---

## 4. 데이터 흐름 시나리오

### 4.1 시나리오 A: 단순 질문 ("서울 인구가 얼마나 되나요?")

```
[사용자 질문]
     ↓
┌────────────────────────────────────────────────────────┐
│ Step 1: search_statistics("인구")                      │
│   → search.py::StatisticsSearch.search()               │
│   → 결과: [{tbl_id: "DT_1B040A3", tbl_nm: "행정구역별 인구"}] │
└────────────────────────────────────────────────────────┘
     ↓
┌────────────────────────────────────────────────────────┐
│ Step 2: get_statistics_data("101", "DT_1B040A3", ...)  │
│   → data.py::StatisticsData.get_data()                 │
│   → 결과: [{C1_NM: "서울특별시", DT: "9411211", ...}]   │
└────────────────────────────────────────────────────────┘
     ↓
┌────────────────────────────────────────────────────────┐
│ Step 3: filter_statistics_data(regions=["서울특별시"]) │
│   → report_tools.py::filter_data()                     │
│   → 결과: 서울 데이터만 필터링                          │
└────────────────────────────────────────────────────────┘
     ↓
[LLM 답변: "서울 인구는 약 9,411,211명입니다 (2023년)"]
```

### 4.2 시나리오 B: 비교 분석 ("서울과 경기도 인구 비교해줘")

```
[사용자 질문]
     ↓
┌─────────────────────────────────────────────────────────┐
│ Step 1-2: 데이터 조회 (위와 동일)                        │
└─────────────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────────────┐
│ Step 3: filter_statistics_data(regions=["서울", "경기"])│
│   → 두 지역 데이터만 추출                                │
└─────────────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────────────┐
│ Step 4: analyze_data_comparison(targets=["서울", "경기"])│
│   → report_tools.py::analyze_comparison()               │
│   → 결과: {findings: ["경기도가 서울보다 1.4배 많음"]}   │
└─────────────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────────────┐
│ Step 5: create_quick_report()                           │
│   → report_tools.py::quick_report()                     │
│   → HTML 리포트 생성 (KPI 카드 + 차트 + 인사이트)        │
└─────────────────────────────────────────────────────────┘
     ↓
[LLM 답변 + HTML 리포트 아티팩트]
```

### 4.3 시나리오 C: 전문 분석 ("인구 감소 상위 5개 지역 분석")

```
[사용자 질문]
     ↓
┌─────────────────────────────────────────────────────────┐
│ Step 1-2: 데이터 조회 (2019-2023 연간 데이터)            │
└─────────────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────────────┐
│ Step 3: aggregate_statistics_data(group_by="C1_NM")     │
│   → 지역별 합계 계산                                     │
└─────────────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────────────┐
│ Step 4: 변화율 계산 (transform.py::calculate_growth)    │
│   → 각 지역의 연간 성장률 계산                           │
└─────────────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────────────┐
│ Step 5: analyze_data_ranking(top_n=5)                   │
│   → 감소율 상위 5개 지역 추출                            │
└─────────────────────────────────────────────────────────┘
     ↓
┌─────────────────────────────────────────────────────────┐
│ Step 6: create_custom_report()                          │
│   → 종합 리포트 (순위 테이블 + 추이 차트 + 인사이트)     │
└─────────────────────────────────────────────────────────┘
     ↓
[LLM 답변 + 종합 HTML 리포트]
```

---

## 5. MCP 도구 레이어 설계

### 5.1 Layer 1: DISCOVER (데이터 탐색)

| 도구 | 설명 | 반환 |
|------|------|------|
| `search_statistics(keyword)` | 키워드로 통계표 검색 | `[{tbl_id, tbl_nm, org_id, ...}]` |
| `list_organizations()` | 통계 작성 기관 목록 | `[{code, name}]` |
| `list_themes()` | 통계 주제 분류 | `[{code, name}]` |
| `get_table_metadata(org_id, tbl_id)` | 테이블 구조 정보 | `{dimensions, items, period}` |

### 5.2 Layer 2: FETCH (데이터 조회)

| 도구 | 설명 | 반환 |
|------|------|------|
| `get_statistics_data(...)` | 통계 데이터 조회 | `[{PRD_DE, C1_NM, DT, ...}]` |
| `filter_statistics_data(...)` | 조건 필터링 | 필터링된 레코드 |
| `aggregate_statistics_data(...)` | 그룹 집계 | 집계된 레코드 |
| `get_data_summary(data)` | LLM용 요약 | `{record_count, periods, regions}` |

### 5.3 Layer 3: PRESENT (결과 생성)

| 도구 | 설명 | 반환 |
|------|------|------|
| `analyze_data_trend(...)` | 추세 분석 | `{type, findings, metrics}` |
| `analyze_data_comparison(...)` | 비교 분석 | `{type, findings, metrics}` |
| `analyze_data_ranking(...)` | 순위 분석 | `{type, findings, data}` |
| `create_quick_report(...)` | 자동 리포트 | HTML 문자열 |
| `create_custom_report(...)` | 커스텀 리포트 | HTML 문자열 |

---

## 6. 주요 데이터 구조

### 6.1 KOSIS API 응답 레코드

```python
{
    "TBL_ID": "DT_1B040A3",       # 테이블 ID
    "TBL_NM": "행정구역별 인구수",  # 테이블명
    "ORG_ID": "101",              # 기관 ID (101=통계청)
    "ORG_NM": "통계청",            # 기관명
    "PRD_DE": "2023",             # 기간 (연도/월/분기)
    "PRD_SE": "Y",                # 주기 (Y=연간, M=월간, Q=분기)
    "C1": "11",                   # 분류1 코드
    "C1_NM": "서울특별시",         # 분류1 이름 (보통 지역)
    "C2": None,                   # 분류2 코드 (있는 경우)
    "C2_NM": None,                # 분류2 이름
    "ITM_ID": "T20",              # 항목 ID
    "ITM_NM": "인구수",            # 항목명
    "DT": "9411211",              # 데이터 값 (문자열!)
    "UNIT_NM": "명"               # 단위
}
```

### 6.2 분석 결과 구조 (AnalysisResult)

```python
@dataclass
class AnalysisResult:
    type: str               # "trend", "comparison", "ranking", "stats"
    findings: List[str]     # ["서울: -5.2% 감소", "경기: +3.1% 증가"]
    metrics: Dict[str, Any] # {"cagr": -1.3, "direction": "감소"}
    data: List[Dict] = []   # 순위 테이블 등 상세 데이터
    interpretation: str = "" # "지속적인 감소 추세를 보이고 있습니다"
```

### 6.3 리포트 컴포넌트 구조 (ReportComponent)

```python
@dataclass
class ReportComponent:
    type: str      # "chart", "text", "table", "kpi", "layout"
    content: str   # HTML 또는 텍스트 내용
    title: str = ""
    metadata: Dict = {}
```

---

## 7. 주요 필드 상수 (Fields 클래스)

```python
from kosis_tools.transform import Fields

Fields.PERIOD    # "PRD_DE" - 기간
Fields.REGION    # "C1_NM"  - 지역/분류1 (가장 많이 사용)
Fields.VALUE     # "DT"     - 데이터 값
Fields.UNIT      # "UNIT_NM" - 단위
Fields.ITM_NM    # "ITM_NM" - 항목명
Fields.C1_NM     # "C1_NM"  - 분류1 이름
Fields.C2_NM     # "C2_NM"  - 분류2 이름
```

---

## 8. LLM 지시 가이드

### 8.1 데이터 조회 지시

```
"인구 데이터를 조회해줘"
→ search_statistics("인구") → get_statistics_data(org_id, tbl_id, ...)

"서울과 부산만 비교해줘"
→ filter_statistics_data(data, regions=["서울특별시", "부산광역시"])

"연도별로 집계해줘"
→ aggregate_statistics_data(data, group_by="PRD_DE", agg_func="sum")
```

### 8.2 분석 지시

```
"추세를 분석해줘"
→ analyze_data_trend(data, group_by="C1_NM")

"지역별로 비교해줘"
→ analyze_data_comparison(data, targets=["서울", "부산"])

"상위 10개 지역을 보여줘"
→ analyze_data_ranking(data, top_n=10)
```

### 8.3 리포트 지시

```
"간단한 리포트를 만들어줘"
→ create_quick_report(data, title="인구 분석")

"KPI 카드와 차트가 포함된 리포트"
→ create_custom_report(data, include_kpi=True, include_trend_chart=True)

"리포트를 HTML 파일로 저장해줘"
→ create_quick_report(data, output_path="report.html")
```

---

## 9. 자주 하는 실수와 해결

### 9.1 DT 필드가 문자열임

```python
# ❌ 잘못된 사용
total = sum(r["DT"] for r in data)  # 문자열 연결됨!

# ✅ 올바른 사용
total = sum(int(r["DT"]) for r in data if r["DT"].isdigit())
# 또는 KosisTransformer 사용 (자동 변환)
tx = KosisTransformer(data)
df = tx.to_dataframe()  # DT가 숫자로 변환됨
```

### 9.2 빈 데이터 처리

```python
# ❌ 빈 데이터 체크 없이
result = analyze_trend(data)  # data가 []면 에러

# ✅ 항상 체크
if not data:
    return {"error": "데이터가 없습니다"}
```

### 9.3 기간 형식 주의

```python
# 연간(Y): "2023"
# 월간(M): "202301" (6자리)
# 분기(Q): "202301" (01=1분기)

# ❌ 잘못된 기간 형식
get_statistics_data(..., start_period="2023-01", period_type="M")

# ✅ 올바른 형식
get_statistics_data(..., start_period="202301", period_type="M")
```

---

## 10. 테스트 실행

```bash
# 전체 테스트
uv run pytest tests/ -v

# E2E 테스트만
uv run pytest tests/e2e/ -v

# 특정 테스트 파일
uv run pytest tests/e2e/test_mcp_server_tools.py -v

# 마커별 실행
uv run pytest -m "not slow" tests/  # 빠른 테스트만
uv run pytest -m "api" tests/       # 실제 API 호출 테스트
```

---

## 11. 환경 설정

```bash
# 필수 환경 변수
export KOSIS_API_KEY="your_api_key_here"

# MCP 서버 실행 (로컬 테스트)
uv run fastmcp run src/kosis_tools/mcp_server.py

# Claude Desktop에 설치
fastmcp install claude-desktop src/kosis_tools/mcp_server.py
```

---

## 12. 확장 가이드

### 12.1 새 MCP 도구 추가

```python
# mcp_server.py에 추가
@mcp.tool
def my_new_tool(param1: str, param2: int = 10) -> dict:
    """
    도구 설명 (LLM이 읽음).

    Args:
        param1: 파라미터1 설명
        param2: 파라미터2 설명 (기본값: 10)

    Returns:
        결과 딕셔너리
    """
    # 구현
    return {"result": "..."}
```

### 12.2 새 분석 함수 추가

```python
# report_tools.py에 추가
def analyze_new_metric(
    data: List[Dict[str, Any]],
    **kwargs
) -> AnalysisResult:
    """새로운 분석 메트릭."""
    # 분석 로직
    return AnalysisResult(
        type="new_metric",
        findings=["발견1", "발견2"],
        metrics={"value": 123},
    )
```

### 12.3 새 차트 유형 추가

```python
# visualize.py의 KosisVisualizer에 추가
def my_chart(
    self,
    data: List[Dict[str, Any]],
    **kwargs
) -> go.Figure:
    """새 차트 유형."""
    fig = go.Figure(...)
    return self._apply_korean_layout(fig, ...)
```

---

## 부록: 주요 KOSIS 테이블 ID

| 테이블 ID | 테이블명 | 기관 |
|-----------|----------|------|
| DT_1B040A3 | 행정구역별 인구수 | 통계청 (101) |
| DT_1J20001 | 소비자물가지수 | 통계청 (101) |
| DT_1DA7001 | 산업별 취업자 | 통계청 (101) |

---

*마지막 업데이트: 2024-12-13*
*문서 생성: Claude Code*
