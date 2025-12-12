# KOSIS API Pre-Development Testing Report

> 테스트 일시: 2025-12-12
> 테스트 환경: Python 3.12, pytest 9.0.2

## 1. API 기본 테스트 결과

### 1.1 테스트 구성 (tests/test_api.py)

총 **27개 테스트 전체 통과** (10.61s)

| 테스트 영역 | 테스트 수 | 결과 |
|------------|----------|------|
| 환경변수 설정 | 5개 | ✅ Pass |
| URL 연결성 | 3개 | ✅ Pass |
| API 인증 | 2개 | ✅ Pass |
| KosisAPIWrapper | 5개 | ✅ Pass |
| 데이터 변환 | 6개 | ✅ Pass |
| 에러 핸들링 | 3개 | ✅ Pass |
| 메타데이터 기반 | 3개 | ✅ Pass |

### 1.2 주요 검증 항목

- `.env` 파일 존재 및 API 키 유효성
- KOSIS 메인 사이트 및 API 엔드포인트 접근성
- 유효/무효 API 키 인증 처리
- 비표준 JSON 파싱 (KOSIS는 키에 따옴표 없는 JSON 반환)
- 연간/월간/분기 날짜 포맷 변환
- 타임아웃 및 잘못된 파라미터 에러 처리

---

## 2. Native API 접근 (캐시 없이)

### 2.1 서비스뷰 코드 (tests/test_api_native.py)

KOSIS는 여러 서비스뷰를 통해 통계를 분류합니다:

| 코드 | 명칭 | 접근 가능 |
|------|------|----------|
| `MT_ZTITLE` | 국내통계 주제별 | ✅ |
| `MT_OTITLE` | 국내통계 기관별 | ✅ |
| `MT_GTITLE01` | e-지방지표(주제별) | ✅ |
| `MT_GTITLE02` | e-지방지표(지역별) | ✅ |
| `MT_CHOSUN_TITLE` | 광복이전통계 | ✅ |
| `MT_HANKUK_TITLE` | 대한민국통계연감 | ✅ |
| `MT_STOP_TITLE` | 작성중지통계 | ✅ |
| `MT_RTITLE` | 국제통계 | ✅ |
| `MT_BUKHAN` | 북한통계 | ✅ |
| `MT_TM1_TITLE` | 대상별통계 | ✅ |
| `MT_TM2_TITLE` | 이슈별통계 | ✅ |
| `MT_ETITLE` | 영문 KOSIS | ✅ |

### 2.2 API 엔드포인트

```python
ENDPOINTS = {
    "list": "https://kosis.kr/openapi/statisticsList.do",
    "data": "https://kosis.kr/openapi/Param/statisticsParameterData.do",
    "search": "https://kosis.kr/openapi/search/search.do",  # HTML 반환 주의
}
```

### 2.3 카테고리 트리 탐색

- `parentListId` 파라미터로 하위 카테고리 재귀 탐색 가능
- `LIST_ID`: 폴더(카테고리)
- `TBL_ID`: 통계표(데이터)
- depth=3 탐색 시 약 50개 테이블 발견 (전체 탐색 시 수천 개)

---

## 3. 병렬 처리 테스트 결과

### 3.1 성능 비교 (tests/test_parallel_and_metadata.py)

5개 테이블 동시 조회 테스트:

| 방식 | 소요시간 | 성공률 |
|------|---------|--------|
| 순차 처리 | 2.83s | 5/5 |
| 병렬 (2 workers) | 1.47s | 5/5 |
| 병렬 (5 workers) | 0.62s | 5/5 |

**결과: 병렬 처리로 4.6배 속도 향상**

### 3.2 권장 사항

- API Rate Limit 고려하여 최대 5~10 workers 권장
- 대량 요청 시 0.3~0.5초 딜레이 추가 고려
- `ThreadPoolExecutor` 사용 (`concurrent.futures`)

---

## 4. 데이터 컬럼 정의

### 4.1 응답 필드 설명

| 필드명 | 설명 | 예시 |
|--------|------|------|
| `TBL_ID` | 통계표 ID | DT_1YL20631 |
| `TBL_NM` | 통계표명 | 고령인구비율 |
| `ORG_ID` | 기관 ID | 101 (통계청) |
| `STAT_ID` | 통계조사 ID | - |
| `C1` | 분류1 코드 | - |
| `C1_NM` | 분류1 명칭 | 서울특별시 |
| `C1_NM_ENG` | 분류1 영문명 | Seoul |
| `C2` ~ `C8` | 분류2~8 (동일 패턴) | - |
| `ITM_ID` | 항목 ID | - |
| `ITM_NM` | 항목명 | 고령인구비율, 총인구 등 |
| `PRD_DE` | 수록시점 | 2024, 202401 |
| `PRD_SE` | 수록주기 | Y(연간), M(월간), Q(분기) |
| `DT` | 데이터 값 | 19.2 |
| `UNIT_NM` | 단위명 | %, 명, 원 |
| `LST_CHN_DE` | 최종변경일자 | - |

### 4.2 분류 체계 이해

```
C1 ~ C8: 분류 차원 (지역, 성별, 연령대 등)
ITM: 측정 항목 (고령인구비율, 인구수 등)
PRD_DE: 시점 (연도, 월 등)
DT: 실제 측정값
```

---

## 5. 메타데이터 API 한계

### 5.1 통계설명 API

**엔드포인트:** `https://kosis.kr/openapi/statisticsExplData.do`

```python
params = {
    "method": "getList",
    "apiKey": API_KEY,
    "format": "json",
    "jsonVD": "Y",
    "statId": "1962009",  # 필수: 통계조사 ID
    "metaItm": "ALL",
}
```

**결과:**
- `statId`를 정확히 알아야 조회 가능
- `orgId` + `tblId`로 조회 시 대부분 N/A 반환
- 반환 필드: `statsNm`, `statsKind`, `statsPeriod`, `writingPurps`, `examinObjrange`, `mainTermExpl`, `confmNo`

### 5.2 통계표설명 API

**엔드포인트:** `https://kosis.kr/openapi/statisTable/statisTableExplData.do`

**결과:** HTML 페이지 반환 (JSON API 아님)

### 5.3 통합검색 API

**엔드포인트:** `https://kosis.kr/openapi/search/search.do`

**결과:** HTML 페이지 반환 (JSON API 아님)

---

## 6. 통계설명자료서비스 (핵심 발견!)

### 6.1 통계설명자료서비스 개요

**URL:** https://www.k-stat.go.kr/metasvc

통계청에서 운영하는 별도 서비스로, 모든 승인통계에 대한 **상세한 한국어 메타데이터**를 제공합니다.

### 6.2 제공 정보 (매우 상세함)

| 항목 | 설명 |
|------|------|
| **작성기관 및 부서** | 담당기관, 전화번호 |
| **조사목적** | 통계의 목적과 활용 방안 |
| **작성유형** | 조사통계/보고통계/가공통계 |
| **조사대상 범위** | 조사 대상 정의 |
| **조사대상 지역** | 지역 범위 |
| **조사단위 및 규모** | 조사 단위, 표본 규모 |
| **적용분류** | 표준산업분류, 표준직업분류 등 |
| **조사항목** | 수집하는 데이터 항목 목록 |
| **공표주기** | 연간/월간/분기 등 |
| **공표범위** | 지역적 범위 (시도, 시군구 등) |
| **조사기간** | 조사 실시 기간 |
| **자료이용시 유의사항** | 데이터 해석 시 주의점 |
| **주요 용어해설** | 핵심 용어 정의 (매우 유용!) |
| **자료수집방법** | 면접조사, 인터넷조사 등 |
| **법적근거** | 통계법 근거 |
| **승인번호** | 통계 승인번호 (예: 013002) |

### 6.3 접근 방법

1. **웹 인터페이스:** https://www.k-stat.go.kr/metasvc
2. **직접 URL 패턴:**
   ```
   https://www.k-stat.go.kr/metasvc/msba100/statsdcdta?statsConfmNo={승인번호}
   ```
   예시: `statsConfmNo=013002` (세종시 특별센서스)

3. **통계 선택 방법:**
   - 주제구분 선택 (인구, 사회일반, 노동 등)
   - 기관선택 (중앙행정기관, 지방자치단체 등)
   - 통계선택 (수백 개 통계 목록)

### 6.4 승인번호 매핑 필요

KOSIS의 `TBL_ID`와 통계설명자료서비스의 `승인번호`는 다른 체계입니다:
- KOSIS: `DT_1YL20631` (테이블 ID)
- 통계설명자료: `013002` (승인번호)

**매핑 방법:**
1. KOSIS 통계표에서 "주석정보" 확인
2. 통계설명자료서비스에서 통계명으로 검색
3. 승인번호-테이블ID 매핑 테이블 구축

### 6.5 스크래핑 구현 방향

```python
from playwright.sync_api import sync_playwright
import json

def get_statistics_metadata(stats_confm_no: str) -> dict:
    """통계설명자료서비스에서 메타데이터 수집"""
    url = f"https://www.k-stat.go.kr/metasvc/msba100/statsdcdta?statsConfmNo={stats_confm_no}"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        page.wait_for_load_state("networkidle")

        metadata = {}

        # 테이블에서 메타데이터 추출
        rows = page.query_selector_all("table tr")
        for row in rows:
            header = row.query_selector("th, .rowheader")
            cell = row.query_selector("td, .cell")
            if header and cell:
                key = header.inner_text().strip()
                value = cell.inner_text().strip()
                metadata[key] = value

        browser.close()

    return metadata

# 사용 예시
metadata = get_statistics_metadata("013002")
print(json.dumps(metadata, ensure_ascii=False, indent=2))
```

### 6.6 활용 방안

1. **모델 컨텍스트 제공:**
   - 조사목적, 주요 용어해설, 자료이용시 유의사항을 모델에 제공
   - 데이터 해석의 정확도 향상

2. **데이터 품질 검증:**
   - 조사대상 범위와 실제 데이터 비교
   - 공표범위에 따른 집계 검증

3. **자동화 파이프라인:**
   - 승인번호 기반 메타데이터 자동 수집
   - JSON 형태로 캐싱하여 반복 요청 방지

---

## 7. KOSIS 웹페이지 스크래핑 (보조)

### 7.1 KOSIS 웹페이지 구조

통계표 페이지 URL 패턴:
```
https://kosis.kr/statHtml/statHtml.do?orgId={ORG_ID}&tblId={TBL_ID}
```

### 7.2 페이지 구성 요소

| 요소 | 내용 |
|------|------|
| 페이지 제목 | 통계표명 (예: 고령인구비율) |
| 자료출처 | 기관명 (예: 행정안전부) |
| 수록기간 | 기간 정보 (예: 2000 ~ 2025.11) |
| 자료갱신일 | 최종 업데이트일 |
| **주석정보 버튼** | 간단한 주석 정보 |

### 7.3 주석정보 vs 통계설명자료

| 항목 | KOSIS 주석정보 | 통계설명자료서비스 |
|------|---------------|------------------|
| 상세도 | 간략 | **매우 상세** |
| 용어해설 | 제한적 | **풍부** |
| 조사방법 | 없음 | **있음** |
| 법적근거 | 없음 | **있음** |
| 접근성 | 팝업 | 독립 페이지 |

**결론:** 통계설명자료서비스가 모델 컨텍스트용으로 훨씬 적합

---

## 7. 테스트용 테이블 목록

| ORG_ID | TBL_ID | 테이블명 |
|--------|--------|---------|
| 101 | DT_1YL20631 | 고령인구비율 |
| 101 | DT_1YL20701 | 인구천명당 자동차등록대수 |
| 101 | DT_1YL20621 | 도로포장률 |
| 101 | DT_1YL20951 | 재정자립도 |
| 101 | DT_1IN1503 | 주민등록인구 |

---

## 8. 비표준 JSON 파싱

KOSIS API는 키에 따옴표가 없는 비표준 JSON을 반환합니다:

```javascript
// KOSIS 반환값
{key1: "value1", key2: "value2"}

// 표준 JSON
{"key1": "value1", "key2": "value2"}
```

**해결책:**
```python
import re
import json

def fix_json(text: str):
    corrected = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
    return json.loads(corrected)
```

---

## 9. 다음 단계 권장사항

1. **통계 설명 스크래퍼 구현**
   - Playwright 기반 웹 스크래핑
   - "주석정보" 팝업에서 상세 설명 추출
   - 캐싱하여 반복 요청 방지

2. **전체 테이블 목록 수집**
   - `KosisNativeClient.get_all_tables()` 사용
   - 서비스뷰별로 분류하여 저장

3. **병렬 처리 최적화**
   - 5~10 workers로 설정
   - Rate limit 대응 로직 추가

4. **데이터 파이프라인 구축**
   - 메타데이터 + 실제 데이터 통합
   - Parquet/JSON 형식으로 저장

---

## 10. 테스트 실행 방법

```bash
# 전체 테스트 실행
uv run pytest tests/ -v -s

# 특정 테스트만 실행
uv run pytest tests/test_api.py -v
uv run pytest tests/test_api_native.py -v
uv run pytest tests/test_parallel_and_metadata.py -v

# 특정 클래스만 실행
uv run pytest tests/test_parallel_and_metadata.py::TestParallelRequests -v -s
```
