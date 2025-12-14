# KOSIS 메타데이터 JSON 스키마 설계

## 개요

KOSIS 메타데이터 XLS 파일들을 MCP 검색에 최적화된 JSON 구조로 변환합니다.

## 파일 구조

```
data/metadata/
├── tables.json          # 통합 통계표 목록 (검색 메인)
├── categories.json      # 계층형 카테고리 트리
├── indicators.json      # OpenAPI 지표 목록
└── surveys.json         # 통계설명자료 (기관-조사 매핑)
```

## 1. tables.json - 통합 통계표 목록

MCP 검색의 메인 데이터. 모든 통계표를 플랫하게 저장.

### 스키마

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal
from enum import Enum

class DataSource(str, Enum):
    """데이터 출처"""
    SUBJECT = "subject"           # 주제별통계
    ORGANIZATION = "organization" # 기관별통계
    INTERNATIONAL = "international"  # 국제통계
    NORTH_KOREA = "north_korea"   # 북한통계
    REGIONAL = "regional"         # 지역통계_기관별
    LOCAL_INDICATOR = "local_indicator"  # e-지방지표

class PeriodType(str, Enum):
    """수록 주기"""
    YEAR = "Y"      # 연
    QUARTER = "Q"   # 분기
    MONTH = "M"     # 월
    HALF = "H"      # 반기

class StatisticsTable(BaseModel):
    """통계표 메타데이터"""

    # 식별자 (필수)
    tbl_id: str = Field(..., description="통계표 고유 ID (예: DT_1YL20631)")

    # 기본 정보
    name: str = Field(..., description="통계표명")
    source: Optional[str] = Field(None, description="출처 (기관명, 조사명)")

    # 분류
    data_source: DataSource = Field(..., description="데이터 출처 구분")
    level: int = Field(..., ge=1, le=7, description="계층 레벨 (1=대분류, 7=최하위)")

    # 경로 정보
    path: str = Field(..., description="전체 경로 (예: 주제별통계 > 인구 > ...)")
    path_ids: list[str] = Field(default_factory=list, description="경로 ID 목록")
    list_id: Optional[str] = Field(None, description="목록 ID (API 호출용)")

    # 수록 기간
    period_start: Optional[str] = Field(None, description="수록 시작 (예: 2000, 200801)")
    period_end: Optional[str] = Field(None, description="수록 종료 (예: 2024, 202411)")
    period_type: Optional[PeriodType] = Field(None, description="수록 주기")

    # 검색용 필드
    keywords: list[str] = Field(default_factory=list, description="검색 키워드")

    class Config:
        use_enum_values = True
```

### JSON 예시

```json
{
  "tables": [
    {
      "tbl_id": "DT_1YL20631",
      "name": "고령인구비율(시도/시/군/구)",
      "source": "행정안전부(주민과)",
      "data_source": "local_indicator",
      "level": 2,
      "path": "e-지방지표(주제별) > 인구 > 고령인구비율(시도/시/군/구)",
      "path_ids": ["101"],
      "list_id": "101",
      "period_start": "2000",
      "period_end": "2024",
      "period_type": "Y",
      "keywords": ["고령", "인구", "비율", "시도", "시군구", "노인"]
    }
  ],
  "metadata": {
    "version": "2025-12-14",
    "total_count": 350000,
    "sources": {
      "subject": 65000,
      "organization": 280000,
      "international": 2400,
      "north_korea": 1200,
      "regional": 0,
      "local_indicator": 270
    }
  }
}
```

## 2. categories.json - 계층형 카테고리

브라우징/탐색을 위한 트리 구조.

### 스키마

```python
class Category(BaseModel):
    """카테고리 노드"""

    id: str = Field(..., description="카테고리 ID")
    name: str = Field(..., description="카테고리명")
    level: int = Field(..., description="계층 레벨")
    parent_id: Optional[str] = Field(None, description="부모 카테고리 ID")

    # 하위 정보
    children_count: int = Field(0, description="하위 카테고리 수")
    tables_count: int = Field(0, description="포함된 통계표 수")

    # 경로
    path: str = Field(..., description="전체 경로")
    path_ids: list[str] = Field(default_factory=list, description="경로 ID 목록")

class CategoryTree(BaseModel):
    """카테고리 트리 루트"""

    subject: list[Category] = Field(default_factory=list, description="주제별통계")
    organization: list[Category] = Field(default_factory=list, description="기관별통계")
    international: list[Category] = Field(default_factory=list, description="국제통계")
    north_korea: list[Category] = Field(default_factory=list, description="북한통계")
    local_indicator: list[Category] = Field(default_factory=list, description="e-지방지표")
```

## 3. indicators.json - OpenAPI 지표

100대 지표 등 주요 지표 목록.

### 스키마

```python
class Indicator(BaseModel):
    """OpenAPI 지표"""

    indicator_id: str = Field(..., description="지표 ID")
    name: str = Field(..., description="지표명")

    # 분류
    sector: str = Field(..., description="부문 (예: 100대 지표)")
    sub_sector: str = Field(..., description="세부부문")

    # 지역/기간
    region_type: str = Field(..., description="지역구분 (전국, 시도 등)")
    period_start: str = Field(..., description="수록 시작")
    period_end: str = Field(..., description="수록 종료")
    period_type: PeriodType = Field(..., description="수록 주기")

    # 메타
    has_explanation: bool = Field(False, description="설명자료 유무")

class IndicatorList(BaseModel):
    """지표 목록 ID"""

    list_id: str = Field(..., description="목록 ID")
    major_category: str = Field(..., description="대분류")
    minor_category: Optional[str] = Field(None, description="중분류")
```

## 4. surveys.json - 통계설명자료

기관별 조사명 매핑.

### 스키마

```python
class Survey(BaseModel):
    """통계조사"""

    organization: str = Field(..., description="기관명")
    survey_name: str = Field(..., description="조사명")

    # 정규화된 검색 키
    org_normalized: str = Field(..., description="정규화된 기관명")
    survey_normalized: str = Field(..., description="정규화된 조사명")
```

## MCP 검색 활용 방안

### 1. 키워드 검색
```python
def search_tables(query: str) -> list[StatisticsTable]:
    """통계표 키워드 검색"""
    # tables.json의 name, keywords, path 필드에서 검색
    pass
```

### 2. 카테고리 브라우징
```python
def browse_category(path_ids: list[str]) -> list[Category]:
    """카테고리 하위 항목 조회"""
    # categories.json에서 계층 탐색
    pass
```

### 3. 지표 조회
```python
def get_indicators(sector: str) -> list[Indicator]:
    """부문별 지표 목록"""
    # indicators.json에서 필터링
    pass
```

## 결측치 처리 규칙

| 필드 | NaN 처리 | Pydantic 타입 |
|------|----------|--------------|
| tbl_id | 필수 (없으면 제외) | str |
| name | 필수 | str |
| source | null 유지 | Optional[str] |
| period_start | null 유지 | Optional[str] |
| period_end | null 유지 | Optional[str] |
| period_type | null 유지 | Optional[PeriodType] |

## 지역통계_기관별.xls 처리

TBL_ID가 없는 지역통계 데이터는 별도 처리:

1. LIST_ID를 이용해 `statisticsList.do` API 호출
2. 응답에서 TBL_ID 추출하여 보강
3. API 실패 시 해당 레코드 제외 또는 별도 저장

## 키워드 생성 규칙

검색 최적화를 위한 키워드 자동 생성:

```python
def generate_keywords(table: StatisticsTable) -> list[str]:
    """키워드 자동 생성"""
    keywords = []

    # 1. 통계명에서 추출 (형태소 분석 또는 규칙 기반)
    keywords.extend(extract_from_name(table.name))

    # 2. 경로에서 추출
    keywords.extend(extract_from_path(table.path))

    # 3. 출처에서 추출
    if table.source:
        keywords.extend(extract_from_source(table.source))

    # 중복 제거 및 정규화
    return list(set(normalize(k) for k in keywords))
```
