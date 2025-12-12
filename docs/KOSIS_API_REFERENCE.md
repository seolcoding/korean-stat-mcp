# KOSIS API Reference

프로젝트에서 사용 중인 모든 KOSIS API 엔드포인트, 파라미터, 응답 형식 정리

---

## 목차

1. [통계 검색 API (statisticsSearch.do)](#1-통계-검색-api)
2. [통계 데이터 조회 API (statisticsParameterData.do)](#2-통계-데이터-조회-api)
3. [통계 목록 API (statisticsList.do)](#3-통계-목록-api)
4. [통계표설명 API (statisticsData.do - getMeta)](#4-통계표설명-api)
5. [통계설명 API (statisticsExplData.do)](#5-통계설명-api)
6. [HTML 콘텐츠 (statHtmlContent.do)](#6-html-콘텐츠-엔드포인트)
7. [k-stat.go.kr 메타데이터](#7-k-statgokr-메타데이터)

---

## 공통 사항

### Base URL
```
https://kosis.kr/openapi/
```

### 인증
- API Key 필요 (발급: https://kosis.kr/openapi/)
- 파라미터: `apiKey`

### 응답 형식 주의
KOSIS API는 **비표준 JSON**을 반환합니다. 키에 따옴표가 없는 형식:
```javascript
// 원본 응답 (비표준)
{ORG_ID:"101", TBL_ID:"DT_1YL20631"}

// 수정 필요 (표준 JSON)
{"ORG_ID":"101", "TBL_ID":"DT_1YL20631"}
```

**수정 코드:**
```python
import re
def fix_json(text):
    return re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', text)
```

---

## 1. 통계 검색 API

키워드로 통계표를 검색합니다.

### Endpoint
```
GET https://kosis.kr/openapi/statisticsSearch.do
```

### 파라미터

| 파라미터 | 필수 | 설명 | 예시 |
|---------|------|------|------|
| `method` | O | 호출 메소드 | `getList` |
| `apiKey` | O | API 인증키 | |
| `format` | O | 응답 형식 | `json` |
| `searchNm` | O | 검색어 | `인구`, `고령` |
| `resultCount` | X | 결과 개수 (max 5000) | `100` |
| `startCount` | X | 시작 위치 (페이징) | `1` |

### 샘플 요청
```
GET https://kosis.kr/openapi/statisticsSearch.do?method=getList&apiKey={KEY}&format=json&searchNm=인구&resultCount=2
```

### 샘플 응답
```json
{
  "ORG_ID": "101",
  "ORG_NM": "국가데이터처",
  "TBL_ID": "DT_XNN0011",
  "TBL_NM": "부양인구비 및 노령화지수 - 동북·중앙아시아",
  "STAT_ID": "A10120210517153124",
  "STAT_NM": "신남방신북방통계",
  "VW_CD": "MT_RTITLE01",
  "MT_ATITLE": "아주지역 통계 > 동북·중앙아시아 통계 > 주제별 통계 > 영토/인구",
  "FULL_PATH_ID": "101_001 > 101_001_NN > ...",
  "CONTENTS": "국가별 인구(0-14세) 총부양비(노년) ...",
  "STRT_PRD_DE": "1950",
  "END_PRD_DE": "2100",
  "ITEM03": "출처: UN 자료...",
  "REC_TBL_SE": "N",
  "TBL_VIEW_URL": "https://kosis.kr/statisticsList/...",
  "LINK_URL": "http://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_XNN0011",
  "STAT_DB_CNT": "104447",
  "QUERY": "인구"
}
```

### 응답 필드 설명

| 필드 | 설명 |
|------|------|
| `ORG_ID` | 기관 ID (통계청=101) |
| `ORG_NM` | 기관명 |
| `TBL_ID` | 통계표 ID (데이터 조회 시 사용) |
| `TBL_NM` | 통계표명 |
| `STAT_ID` | 통계 ID |
| `STAT_NM` | 통계명 |
| `VW_CD` | 뷰 코드 (MT_ZTITLE, MT_GTITLE01 등) |
| `MT_ATITLE` | 분류 경로 |
| `FULL_PATH_ID` | 전체 경로 ID |
| `CONTENTS` | 데이터 내용 미리보기 |
| `STRT_PRD_DE` | 시작 기간 (YYYY) |
| `END_PRD_DE` | 종료 기간 (YYYY) |
| `ITEM03` | 통계 설명/출처 정보 |
| `REC_TBL_SE` | 추천 통계표 여부 |
| `TBL_VIEW_URL` | KOSIS 웹 뷰 URL |
| `LINK_URL` | 직접 링크 URL |
| `STAT_DB_CNT` | 검색 결과 총 건수 |
| `QUERY` | 검색어 |

---

## 2. 통계 데이터 조회 API

실제 통계 데이터를 조회합니다. **핵심 API**

### Endpoint
```
GET https://kosis.kr/openapi/Param/statisticsParameterData.do
```

### 파라미터

| 파라미터 | 필수 | 설명 | 값 |
|---------|------|------|-----|
| `method` | O | 호출 메소드 | `getList` |
| `apiKey` | O | API 인증키 | |
| `format` | O | 응답 형식 | `json` |
| `orgId` | O | 기관 ID | `101` |
| `tblId` | O | 통계표 ID | `DT_1YL20631` |
| `objL1` | O | 분류1 | `ALL` 또는 특정값 |
| `objL2` | X | 분류2 | `ALL` 또는 특정값 |
| `objL3`~`objL8` | X | 분류3~8 | 필요시 사용 |
| `itmId` | O | 항목 ID | `ALL` 또는 특정값 |
| `prdSe` | O | 수록주기 | 아래 참조 |
| `startPrdDe` | O | 시작 기간 | 주기별 형식 다름 |
| `endPrdDe` | O | 종료 기간 | 주기별 형식 다름 |

### 수록주기 (prdSe) 값

| 코드 | 설명 | 기간 형식 |
|------|------|----------|
| `M` | 월간/격월 | YYYYMM (예: 202401) |
| `Q` | 분기 | YYYYQQ (예: 202401=1분기) |
| `S` | 반기 | YYYYHH (예: 202401=상반기) |
| `Y` | 연간 | YYYY (예: 2024) |
| `F` | 다년 (2,3,4,5,10년) | YYYY |
| `IR` | 부정기 | YYYY 또는 YYYYMMDD |

### 샘플 요청
```
GET https://kosis.kr/openapi/Param/statisticsParameterData.do?method=getList&apiKey={KEY}&format=json&orgId=101&tblId=DT_1YL20631&objL1=ALL&itmId=ALL&prdSe=Y&startPrdDe=2020&endPrdDe=2024
```

### 샘플 응답
```json
{
  "TBL_ID": "DT_1YL20631",
  "ORG_ID": "101",
  "PRD_SE": "A",
  "ITM_NM": "65세이상인구<br>(A)",
  "LST_CHN_DE": "2021-01-06",
  "ITM_ID": "T001",
  "UNIT_NM": "명",
  "C1": "00",
  "DT": "8496077",
  "C1_NM": "전국",
  "PRD_DE": "2020",
  "C1_NM_ENG": "Whole country",
  "TBL_NM": "고령인구비율(시도/시/군/구)",
  "C1_OBJ_NM": "행정구역별"
}
```

### 응답 필드 설명

| 필드 | 설명 |
|------|------|
| `TBL_ID` | 통계표 ID |
| `ORG_ID` | 기관 ID |
| `PRD_SE` | 수록주기 코드 (A=연간, M=월간 등) |
| `PRD_DE` | 기준 기간 (YYYY 또는 YYYYMM) |
| `ITM_ID` | 항목 ID |
| `ITM_NM` | 항목명 |
| `UNIT_NM` | 단위 (명, %, 원 등) |
| `DT` | **실제 데이터 값** |
| `C1` | 분류1 코드 |
| `C1_NM` | 분류1 명칭 |
| `C1_NM_ENG` | 분류1 영문명 |
| `C1_OBJ_NM` | 분류1 객체명 (예: 행정구역별) |
| `C2`~`C8` | 분류2~8 코드 (테이블에 따라 존재) |
| `C2_NM`~`C8_NM` | 분류2~8 명칭 |
| `TBL_NM` | 통계표명 |
| `LST_CHN_DE` | 최종 변경일 |

### 에러 응답
```json
{
  "errMsg": "해당 조건에 맞는 데이터가 없습니다."
}
```

---

## 3. 통계 목록 API

통계표 분류 목록을 조회합니다.

### Endpoint
```
GET https://kosis.kr/openapi/statisticsList.do
```

### 파라미터

| 파라미터 | 필수 | 설명 | 예시 |
|---------|------|------|------|
| `method` | O | 호출 메소드 | `getList` |
| `apiKey` | O | API 인증키 | |
| `format` | O | 응답 형식 | `json` |
| `vwCd` | O | 뷰 코드 | `MT_ZTITLE` |
| `parentListId` | X | 상위 분류 ID | `A` |

### 뷰 코드 (vwCd) 값

| 코드 | 설명 |
|------|------|
| `MT_ZTITLE` | 국내통계 주제별 |
| `MT_GTITLE01` | e-지방지표 주제별 |
| `MT_RTITLE01` | 국제/북한통계 |

### 샘플 응답
```json
{
  "LIST_NM": "인구총조사",
  "LIST_ID": "A_4",
  "VW_NM": "국내통계 주제별",
  "VW_CD": "MT_ZTITLE"
}
```

### 응답 필드 설명

| 필드 | 설명 |
|------|------|
| `LIST_ID` | 분류 ID |
| `LIST_NM` | 분류명 |
| `VW_CD` | 뷰 코드 |
| `VW_NM` | 뷰 명칭 |

---

## 4. 통계표설명 API

통계표의 국문/영문 명칭을 조회합니다. 수록정보, 분류/항목, 주석, 단위, 출처 등 조회 가능.

### Endpoint
```
GET https://kosis.kr/openapi/statisticsData.do?method=getMeta&type=TBL
```

### 파라미터

| 파라미터 | 필수 | 설명 | 예시 |
|---------|------|------|------|
| `method` | O | 호출 메소드 | `getMeta` |
| `type` | O | 메타 타입 | `TBL` |
| `apiKey` | O | API 인증키 | |
| `format` | O | 응답 형식 | `json` |
| `orgId` | O | 기관 ID | `101` |
| `tblId` | O | 통계표 ID | `DT_1IN0001` |
| `content` | X | 헤더 유형 | `html`, `json` |

### 샘플 요청
```
GET https://kosis.kr/openapi/statisticsData.do?method=getMeta&type=TBL&apiKey={KEY}&format=json&orgId=101&tblId=DT_1IN0001
```

### 샘플 응답
```json
[
  {
    "TBL_NM": "총조사인구 총괄(읍면동/성/연령별)",
    "TBL_NM_ENG": "Summary of Census Population(By administrative district/sex/age)"
  }
]
```

### 응답 필드 설명

| 필드 | 설명 | 형식 |
|------|------|------|
| `TBL_NM` | 통계표 국문명 | VARCHAR2(300) |
| `TBL_NM_ENG` | 통계표 영문명 | VARCHAR2(300) |

---

## 5. 통계설명 API

통계조사의 상세 메타데이터(조사목적, 조사주기, 조사대상, 연락처 등)를 조회합니다. **LLM 컨텍스트 생성에 핵심**

### Endpoint
```
GET https://kosis.kr/openapi/statisticsExplData.do?method=getList
```

### 파라미터

| 파라미터 | 필수 | 설명 | 예시 |
|---------|------|------|------|
| `method` | O | 호출 메소드 | `getList` |
| `apiKey` | O | API 인증키 | |
| `format` | O | 응답 형식 | `json` |
| `statId` | O* | 통계조사 ID | `1962009` (가계동향조사) |
| `orgId` | O* | 기관 ID (statId 대체) | `101` |
| `tblId` | O* | 통계표 ID (statId 대체) | `DT_1IN0001` |
| `metaItm` | O | 요청 항목 | `All` 또는 개별 항목 |
| `content` | X | 헤더 유형 | `html`, `json` |

> **참고:** `statId` 또는 `orgId`+`tblId` 조합 중 하나 필수

### metaItm 항목 목록

| 코드 | 설명 |
|------|------|
| `All` | 전체 항목 |
| `statsNm` | 조사명 |
| `statsKind` | 작성유형 |
| `statsEnd` | 통계종류 |
| `statsContinue` | 계속여부 |
| `basisLaw` | 법적근거 |
| `writingPurps` | 조사목적 |
| `examinPd` | 조사기간 |
| `statsPeriod` | 조사주기 |
| `writingSystem` | 조사체계 |
| `writingTel` | 연락처 |
| `statsField` | 통계(활용)분야·실태 |
| `examinObjrange` | 조사 대상범위 |
| `examinObjArea` | 조사 대상지역 |
| `josaUnit` | 조사단위 및 조사대상규모 |
| `applyGroup` | 적용분류 |
| `josaItm` | 조사항목 |
| `pubPeriod` | 공표주기 |
| `pubExtent` | 공표범위 |
| `pubDate` | 공표시기 |
| `publictMth` | 공표방법 및 URL |
| `examinTrgetPd` | 조사대상기간 및 조사기준시점 |
| `dataUserNote` | 자료이용시 유의사항 |
| `mainTermExpl` | 주요 용어해설 |
| `dataCollectMth` | 자료 수집방법 |
| `examinHistory` | 조사연혁 |
| `confmNo` | 승인번호 |
| `confmDt` | 승인일자 |

### 샘플 요청
```
GET https://kosis.kr/openapi/statisticsExplData.do?method=getList&apiKey={KEY}&format=json&statId=1962009&metaItm=statsNm
```

### 샘플 응답
```json
[
  {
    "statsNm": "가계동향조사",
    "statsKind": "조사통계",
    "statsPeriod": "분기",
    "confmNo": "101006",
    "writingPurps": "□ 가구에 대한 가계수지 실태를 파악하여 국민의 소득과 소비 수준변화의 측정 및 분석 등에 필요한 자료를 제공...",
    "pubPeriod": "분기",
    "examinObjArea": "전국"
  }
]
```

### 응답 필드 설명

| 필드 | 설명 | 형식 |
|------|------|------|
| `statsNm` | 조사명 | VARCHAR2(4000) |
| `statsKind` | 작성유형 (조사통계, 가공통계 등) | VARCHAR2(4000) |
| `statsEnd` | 통계종류 (지정통계, 일반통계 등) | VARCHAR2(4000) |
| `statsContinue` | 계속여부 | VARCHAR2(4000) |
| `basisLaw` | 법적근거 | VARCHAR2(4000) |
| `writingPurps` | 조사목적 | VARCHAR2(4000) |
| `examinPd` | 조사기간 | VARCHAR2(4000) |
| `statsPeriod` | 조사주기 | VARCHAR2(4000) |
| `writingSystem` | 조사체계 | VARCHAR2(4000) |
| `writingTel` | 연락처 | VARCHAR2(8000) |
| `statsField` | 통계(활용)분야·실태 | VARCHAR2(4000) |
| `examinObjrange` | 조사 대상범위 | VARCHAR2(4000) |
| `examinObjArea` | 조사 대상지역 | VARCHAR2(4000) |
| `josaUnit` | 조사단위 및 조사대상규모 | VARCHAR2(4000) |
| `applyGroup` | 적용분류 | VARCHAR2(4000) |
| `josaItm` | 조사항목 | VARCHAR2(4000) |
| `pubPeriod` | 공표주기 | VARCHAR2(4000) |
| `pubExtent` | 공표범위 | VARCHAR2(4000) |
| `pubDate` | 공표시기 | VARCHAR2(4000) |
| `publictMth` | 공표방법 및 URL | VARCHAR2(4000) |
| `examinTrgetPd` | 조사대상기간 및 조사기준시점 | VARCHAR2(4000) |
| `dataUserNote` | 자료이용시 유의사항 | VARCHAR2(4000) |
| `mainTermExpl` | 주요 용어해설 | VARCHAR2(4000) |
| `dataCollectMth` | 자료 수집방법 | VARCHAR2(4000) |
| `examinHistory` | 조사연혁 | VARCHAR2(4000) |
| `confmNo` | 승인번호 | VARCHAR2(4000) |
| `confmDt` | 승인일자 | VARCHAR2(4000) |

### 주요 statId 예시

| statId | 통계명 |
|--------|--------|
| `1962001` | 인구총조사 |
| `1962009` | 가계동향조사 |
| `1977013` | 사회조사 |
| `2006097` | 국가유산관리현황 |

---

## 6. HTML 콘텐츠 엔드포인트

통계표 상세 정보 HTML을 반환합니다. **k-stat.go.kr URL 추출용**

### Endpoint
```
GET https://kosis.kr/statHtml/statHtmlContent.do
```

### 파라미터

| 파라미터 | 필수 | 설명 | 예시 |
|---------|------|------|------|
| `orgId` | O | 기관 ID | `101` |
| `tblId` | O | 통계표 ID | `DT_1IN1503` |

### 샘플 요청
```
GET https://kosis.kr/statHtml/statHtmlContent.do?orgId=101&tblId=DT_1IN1503
```

### 응답
- Content-Type: `text/html;charset=UTF-8`
- HTML 내에 k-stat.go.kr URL 포함 (일부 테이블만)

### k-stat URL 추출 패턴
```python
import re
pattern = r'https://www\.k-stat\.go\.kr/metasvc/msba100/statsdcdta\?statsConfmNo=([^&"\'>\s]+)'
matches = re.findall(pattern, html_text)
```

### k-stat URL이 있는 테이블 예시

| TBL_ID | statsConfmNo | 통계명 |
|--------|--------------|--------|
| DT_1IN1503 | 101001 | 주민등록인구 |
| DT_1B040A3 | 110026 | 총인구(인구총조사) |
| DT_1DA7002S | 101004 | 성별 인구수 |

> **참고:** 모든 테이블에 k-stat URL이 있는 것은 아닙니다.

---

## 7. k-stat.go.kr 메타데이터

통계 메타데이터(정의, 작성기관, 작성주기 등) 상세 정보

### Endpoint
```
GET https://www.k-stat.go.kr/metasvc/msba100/statsdcdta
```

### 파라미터

| 파라미터 | 필수 | 설명 | 예시 |
|---------|------|------|------|
| `statsConfmNo` | O | 통계승인번호 | `101001` |

### 샘플 요청
```
GET https://www.k-stat.go.kr/metasvc/msba100/statsdcdta?statsConfmNo=101001
```

### 응답
- Content-Type: `text/html`
- 통계 메타데이터 상세 페이지 (HTML)

### 포함 정보
- 통계명
- 작성기관
- 작성주기
- 작성목적
- 법적근거
- 조사대상
- 조사항목
- 공표범위
- 공표주기
- 기타 메타데이터

---

## 프로젝트 내 사용 현황

### 파일별 API 사용

| 파일 | 사용 API |
|------|----------|
| `src/scripts/scrape_kosis_metadata.py` | statisticsSearch.do |
| `src/kosis_wrapper.py` | statisticsParameterData.do |
| `src/api.py` | statisticsParameterData.do |
| `src/scripts/scrape_kstat_metadata.py` | statHtmlContent.do, k-stat.go.kr |
| (신규 구현 예정) | statisticsData.do (getMeta) |
| (신규 구현 예정) | statisticsExplData.do |

### 저장된 데이터 파일

| 파일 | 내용 |
|------|------|
| `kosis_data/kosis_metadata_final.json` | 검색된 통계표 메타데이터 |
| `kosis_data/kstat_urls.json` | k-stat.go.kr URL 매핑 |
| `kosis_data/raw/*.json` | 개별 테이블 원본 데이터 |

---

## 참고 링크

- KOSIS OpenAPI 포털: https://kosis.kr/openapi/
- k-stat 통계설명자료서비스: https://www.k-stat.go.kr/
