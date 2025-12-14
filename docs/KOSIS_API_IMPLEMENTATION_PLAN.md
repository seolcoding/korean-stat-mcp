# KOSIS API 구현 계획서

> PDF 공식 매뉴얼 기반 Gap 분석 및 구현 계획

## 1. KOSIS 공식 API 목록 (PDF 기준)

### 1.1 통계목록 (statisticsList.do)
| 엔드포인트 | 설명 | 현재 구현 |
|-----------|------|----------|
| `statisticsList.do?method=getList` | 목록 조회 (JSON/SDMX) | ✅ `list_categories.py` |

**파라미터:**
- `apiKey` (필수): 인증키
- `vwCd` (필수): 서비스뷰 코드 (MT_ZTITLE, MT_OTITLE 등 9가지)
- `parentListId` (필수): 시작목록 ID
- `format` (필수): 결과 유형 (json, sdmx)

### 1.2 통계자료 (statisticsData.do)
| 엔드포인트 | 설명 | 현재 구현 |
|-----------|------|----------|
| `statisticsData.do?method=getList` | 데이터 조회 | ✅ `data.py` |
| `statisticsData.do?method=getMeta&type=TBL` | 통계표 명칭 | ✅ `table_meta.py` |
| `statisticsData.do?method=getMeta&type=ORG` | 기관 명칭 | ✅ `get_org_info()` |
| `statisticsData.do?method=getMeta&type=PRD` | 수록정보 | ✅ `get_prd_info()` |
| `statisticsData.do?method=getMeta&type=ITM` | 분류/항목 | ✅ `get_itm_vars()` |
| `statisticsData.do?method=getMeta&type=CMMT` | 주석 | ✅ `get_comments()` |
| `statisticsData.do?method=getMeta&type=UNIT` | 단위 | ✅ `get_unit()` |
| `statisticsData.do?method=getMeta&type=SOURCE` | 출처 | ✅ `get_source()` |
| `statisticsData.do?method=getMeta&type=WGT` | 가중치 | ✅ `get_weight()` |
| `statisticsData.do?method=getMeta&type=NCD` | 자료갱신일 | ✅ `get_update_date()` |

**데이터 조회 파라미터:**
- `orgId` (필수): 기관 ID
- `tblId` (필수): 통계표 ID
- `objL1`~`objL8`: 분류1~8
- `itmId` (필수): 항목
- `prdSe` (필수): 수록주기 (Y/H/Q/M)
- `startPrdDe`/`endPrdDe` 또는 `newEstPrdCnt`: 기간 설정
- `format` (필수): json/sdmx/xml

### 1.3 대용량 통계자료 (statisticsBigData.do)
| 엔드포인트 | 설명 | 현재 구현 |
|-----------|------|----------|
| `statisticsBigData.do` | 대용량 데이터 조회 (SDMX/CSV) | ✅ `big_data.py` |

**특징:**
- 다중계열, 여러시점 데이터
- 출력 형식: SDMX(DSD/Generic/StructureSpecific), CSV/XLS
- 사전 등록 필요 (`userStatsId`)

### 1.4 통계설명 (statisticsExplData.do)
| 엔드포인트 | 설명 | 현재 구현 |
|-----------|------|----------|
| `statisticsExplData.do?method=getList` | 통계조사 설명 | ✅ `stats_explanation.py` |

**파라미터:**
- `statId` (필수): 통계조사 ID (또는 orgId+tblId)
- `metaItm` (필수): 요청 항목
  - `All` (전체)
  - `statsNm` (조사명), `statsKind` (작성유형), `basisLaw` (법적근거)
  - `writingPurps` (조사목적), `statsPeriod` (조사주기)
  - `confmNo` (승인번호) 등 27개 항목

### 1.5 메타자료 (statisticsMetaData.do)
| 엔드포인트 | 설명 | 현재 구현 |
|-----------|------|----------|
| `statisticsMetaData.do` | 메타데이터 조회 | ✅ `table_meta.py` |

### 1.6 KOSIS 통합검색 (statisticsSearch.do)
| 엔드포인트 | 설명 | 현재 구현 |
|-----------|------|----------|
| `statisticsSearch.do?method=getList` | 통계표 검색 | ✅ `search.py` |

**파라미터:**
- `searchNm` (필수): 검색어
- `sort` (선택): 정렬 (RANK/DATE)
- `startCount` (선택): 페이지 번호
- `resultCount` (선택): 결과 개수

**출력 필드:**
- `ORG_ID`, `ORG_NM`: 기관코드/명
- `TBL_ID`, `TBL_NM`: 통계표ID/명
- `STAT_ID`, `STAT_NM`: 조사코드/명
- `STRT_PRD_DE`, `END_PRD_DE`: 수록기간
- `TBL_VIEW_URL`, `LINK_URL`: 이동 URL

### 1.7 통계주요지표 (pkNumberService.do 등)
| 엔드포인트 | 설명 | 현재 구현 |
|-----------|------|----------|
| `pkNumberService.do` | 지표 고유번호별 설명조회 | ✅ `key_indicators.py` |
| `indExpService.do` | 지표명별 설명조회 | ✅ `key_indicators.py` |
| `indiListService.do` | 목록별 지표조회 | ✅ `key_indicators.py` |
| `indListSearchRequest.do` | 지표명/고유번호별 목록조회 | ✅ `key_indicators.py` |
| `indIdDetailSearchRequest.do` | 고유번호별 지표 상세조회 | ✅ `key_indicators.py` |
| `prListSearchRequest.do` | 수록주기별 목록조회 | ✅ `key_indicators.py` |

---

## 2. Gap 분석 요약

### 2.1 구현 완료 (8개) ✅ 전체 완료
- ✅ 통계목록 (`list_categories.py`)
- ✅ 통계자료 기본 조회 (`data.py`)
- ✅ 통계설명 (`stats_explanation.py`)
- ✅ **메타자료 전체** (`table_meta.py`) - Phase A 완료 (2024-12-14)
  - TBL, ORG, PRD, ITM_VAR, OBJ_VAR, CMMT, UNIT, SOURCE, WGT, NCD 모든 타입 지원
  - `get_all_metadata(include_extended=True)`로 확장 메타데이터 일괄 조회
- ✅ 통합검색 (`search.py`)
- ✅ k-stat 메타데이터 (`kstat_metadata.py`)
- ✅ **대용량 통계자료** (`big_data.py`) - Phase B 완료 (2024-12-14)
  - SDMX (DSD/Generic/StructureSpecific), CSV/XLS 형식 지원
  - `fetch_sdmx()`, `fetch_csv()`, `fetch_dsd()` 메서드
  - 주의: `userStatsId` 사전 등록 필요 (KOSIS 웹사이트)
- ✅ **통계주요지표** (`key_indicators.py`) - Phase C 완료 (2024-12-14)
  - 6개 API 엔드포인트 지원 (pkNumber, indExp, indiList, indListSearch, indIdDetail, prListSearch)
  - `get_explanation_by_id()`, `get_explanation_by_name()`, `get_by_list()` 등
  - 4개 데이터 클래스: IndicatorExplanation, IndicatorListItem, IndicatorSearchResult, IndicatorDetailData

### 2.2 미구현 (0개)
- 🎉 **모든 KOSIS OpenAPI 구현 완료!**

---

## 3. 추가 구현 계획

### Phase A: 메타자료 완성 ✅ 완료 (2024-12-14)

| Task | 담당 함수 | 상태 |
|------|----------|------|
| A1. 주석(CMMT) 조회 | `get_comments()` | ✅ 완료 |
| A2. 출처(SOURCE) 조회 | `get_source()` | ✅ 완료 |
| A3. 가중치(WGT) 조회 | `get_weight()` | ✅ 완료 |
| A4. 자료갱신일(NCD) 조회 | `get_update_date()` | ✅ 완료 |
| A5. 단위(UNIT) 조회 | `get_unit()` | ✅ 완료 |
| A6. 기관정보(ORG) 조회 | `get_org_info()` | ✅ 완료 |
| A7. 확장 메타데이터 통합 | `get_all_metadata(include_extended=True)` | ✅ 완료 |

**테스트:** 33개 유닛 테스트 통과 (`tests/unit/test_table_meta.py`)

### Phase B: 대용량 데이터 지원 ✅ 완료 (2024-12-14)

| Task | 담당 함수 | 상태 |
|------|----------|------|
| B1. 대용량 SDMX 조회 | `StatisticsBigData.fetch_sdmx()` | ✅ 완료 |
| B2. 대용량 CSV 조회 | `StatisticsBigData.fetch_csv()` | ✅ 완료 |
| B3. DSD 메타데이터 조회 | `StatisticsBigData.fetch_dsd()` | ✅ 완료 |
| B4. SDMX XML 파싱 | `parse_sdmx_xml()` | ✅ 완료 |
| B5. CSV 파싱 | `_parse_csv()` | ✅ 완료 |

**테스트:** 23개 유닛 테스트 통과 (`tests/unit/test_big_data.py`)

**제약사항:**
- `userStatsId`는 KOSIS 웹사이트에서 미리 등록 필요
- 개발가이드 > 대용량 통계자료 > URL생성 > 자료등록

### Phase C: 통계주요지표 API ✅ 완료 (2024-12-14)

| Task | 담당 함수 | 상태 |
|------|----------|------|
| C1. 지표 고유번호별 설명조회 | `KeyIndicators.get_explanation_by_id()` | ✅ 완료 |
| C2. 지표명별 설명조회 | `KeyIndicators.get_explanation_by_name()` | ✅ 완료 |
| C3. 목록별 지표조회 | `KeyIndicators.get_by_list()` | ✅ 완료 |
| C4. 지표명별 목록조회 | `KeyIndicators.search_by_name()` | ✅ 완료 |
| C5. 고유번호별 목록조회 | `KeyIndicators.search_by_id()` | ✅ 완료 |
| C6. 고유번호별 상세조회 | `KeyIndicators.get_detail()` | ✅ 완료 |
| C7. 수록주기별 목록조회 | `KeyIndicators.search_by_period_type()` | ✅ 완료 |

**테스트:** 31개 유닛 테스트 통과 (`tests/unit/test_key_indicators.py`)

**데이터 클래스:**
- `IndicatorExplanation`: 지표 설명 정보
- `IndicatorListItem`: 목록별 지표 정보
- `IndicatorSearchResult`: 지표 검색 결과
- `IndicatorDetailData`: 지표 상세 데이터

---

## 4. 테스트 케이스 설계

### 4.1 기본 파라미터 검증
```python
# 필수 파라미터 누락 테스트
def test_missing_required_param():
    with pytest.raises(ValueError):
        client.fetch_data(org_id="101")  # tbl_id 누락

# 잘못된 파라미터 값 테스트
def test_invalid_period_type():
    with pytest.raises(ValueError):
        client.fetch_data(org_id="101", tbl_id="DT_1B01001", prd_se="X")
```

### 4.2 응답 파싱 검증
```python
# DT 필드 특수값 처리
def test_dt_special_values():
    data = [{"DT": "-"}, {"DT": "*"}, {"DT": "1234"}]
    result = parse_data_values(data)
    assert result[0] is None
    assert result[1] is None
    assert result[2] == 1234

# 빈 응답 처리
def test_empty_response():
    result = client.search("존재하지않는통계")
    assert result == []
```

### 4.3 API별 통합 테스트
```python
# 통계목록 -> 통계자료 -> 메타자료 연계
def test_full_workflow():
    # 1. 검색
    tables = client.search("인구")
    assert len(tables) > 0

    # 2. 첫 번째 결과로 데이터 조회
    table = tables[0]
    data = client.fetch_data(
        org_id=table["ORG_ID"],
        tbl_id=table["TBL_ID"]
    )
    assert "PRD_DE" in data[0]

    # 3. 메타데이터 조회
    meta = client.get_table_meta(
        org_id=table["ORG_ID"],
        tbl_id=table["TBL_ID"]
    )
    assert meta.tbl_nm is not None
```

---

## 5. 가능한 시나리오

### 시나리오 1: 기본 통계 조회
```
사용자: "2023년 서울 인구 통계 보여줘"
1. search_tables("서울 인구") → 통계표 목록
2. get_table_meta(org_id, tbl_id) → 분류/항목 확인
3. fetch_data(objL1="11", prdSe="Y", startPrdDe="2023") → 데이터
4. viz_bar_comparison() → 시각화
```

### 시나리오 2: 시계열 분석
```
사용자: "최근 10년 GDP 추이 분석해줘"
1. search_tables("GDP") → 통계표 찾기
2. fetch_data(newEstPrdCnt=10) → 최근 10개 시점
3. analyze_trend() → 추세 분석
4. viz_line_trend() → 라인 차트
```

### 시나리오 3: 지역 비교
```
사용자: "시도별 출생률 비교"
1. search_tables("출생률") → 통계표
2. get_available_values(objL1) → 지역 목록
3. fetch_data(objL1="all") → 전체 지역 데이터
4. viz_heatmap() → 히트맵
```

### 시나리오 4: 대용량 데이터 (Phase B 이후)
```
사용자: "전국 읍면동별 인구 전체 다운로드"
1. register_big_data() → 대용량 등록
2. fetch_big_data(format="csv") → CSV 다운로드
3. to_dataframe() → DataFrame 변환
```

### 시나리오 5: 주요 지표 조회 ✅
```
사용자: "실업률 지표 설명 보여줘"
1. KeyIndicators.get_explanation_by_name("실업률") → 지표 설명
2. KeyIndicators.search_by_name("실업률") → 지표 목록 검색
3. KeyIndicators.get_detail(jipyoId) → 상세 시계열 데이터
```

---

## 6. 병렬 실행 계획

### Phase A (병렬 6개) ✅ 완료
```
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ A1. CMMT 조회 ✅  │ │ A2. SOURCE 조회✅│ │ A3. WGT 조회 ✅  │ │ A4. NCD 조회 ✅  │
│ (주석)           │ │ (출처)           │ │ (가중치)         │ │ (자료갱신일)     │
└──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────────┘
┌──────────────────┐ ┌──────────────────┐
│ A5. UNIT 조회 ✅  │ │ A6. ORG 조회 ✅  │
│ (단위)           │ │ (기관정보)       │
└──────────────────┘ └──────────────────┘
         │                   │                   │                   │
         └───────────────────┴───────────────────┴───────────────────┘
                                    │
                        ┌───────────▼───────────┐
                        │ table_meta.py 통합 ✅ │
                        │ get_all_metadata()    │
                        │ include_extended=True │
                        └───────────────────────┘
```

### Phase B (순차 의존) ✅ 완료
```
┌──────────────────┐
│ B1. BigData API ✅│
│ StatisticsBigData│
└────────┬─────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌───▼───┐
│B2.CSV✅│ │B3.SDMX│
│파싱    │ │파싱 ✅ │
└───────┘ └───────┘
```

### Phase C (병렬 7개) ✅ 완료
```
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ C1. ID별 설명 ✅  │ │ C2. 이름별 설명✅ │ │ C3. 목록별 지표✅ │ │ C4. 이름별 목록✅ │
└──────────────────┘ └──────────────────┘ └──────────────────┘ └──────────────────┘
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ C5. ID별 목록 ✅  │ │ C6. 상세 조회 ✅  │ │ C7. 주기별 목록✅ │
└──────────────────┘ └──────────────────┘ └──────────────────┘
         │                   │                   │
         └───────────────────┴───────────────────┘
                                    │
                        ┌───────────▼───────────┐
                        │ key_indicators.py ✅  │
                        │ KeyIndicators 클래스  │
                        │ 31개 유닛 테스트 통과 │
                        └───────────────────────┘
```

---

## 7. 구현 완료 요약

### 🎉 모든 KOSIS OpenAPI 구현 완료!

| Phase | 내용 | 테스트 | 완료일 |
|-------|------|--------|--------|
| Phase A | 메타자료 세부 타입 (CMMT, SOURCE, WGT, NCD, UNIT, ORG) | 33개 | 2024-12-14 |
| Phase B | 대용량 통계자료 API (SDMX, CSV) | 23개 | 2024-12-14 |
| Phase C | 통계주요지표 API (6개 엔드포인트) | 31개 | 2024-12-14 |

**총 신규 테스트:** 87개

### 구현 파일 구조
```
src/kosis_tools/
├── config.py          # API 설정 및 엔드포인트
├── base.py            # 베이스 클라이언트
├── search.py          # 통합검색
├── list_categories.py # 카테고리 목록
├── data.py            # 데이터 조회
├── table_meta.py      # 통계표 메타데이터 (Phase A)
├── stats_explanation.py # 통계설명
├── kstat_metadata.py  # k-stat 메타데이터
├── big_data.py        # 대용량 데이터 (Phase B)
├── key_indicators.py  # 통계주요지표 (Phase C)
├── transform.py       # 데이터 변환
├── visualize.py       # 시각화
├── report_generator.py # 리포트 생성
└── report_tools.py    # 리포트 도구
```

---

*Generated: 2024-12-14*
*Updated: 2024-12-14 - Phase A, B, C 모두 완료*
