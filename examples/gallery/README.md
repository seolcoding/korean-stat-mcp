# KOSIS 데이터 분석 예제 갤러리

이 폴더는 KOSIS API를 활용한 다양한 통계 분석 예제를 포함합니다.
각 예제는 특정 지표에 대해 체계적인 분석 프로세스를 제공합니다.

## 📁 구조

```
examples/gallery/
├── README.md                        # 이 파일
├── output/                          # 생성된 차트 저장 폴더
├── 01_population_analysis.py        # 인구 통계 분석
├── 02_consumer_price_analysis.py    # 소비자물가지수 분석
└── 03_employment_analysis.py        # 고용 통계 분석 (예정)
```

## 🚀 실행 방법

```bash
# 전체 예제 실행
uv run python examples/gallery/01_population_analysis.py
uv run python examples/gallery/02_consumer_price_analysis.py

# 또는 개별 실행
cd examples/gallery
python 01_population_analysis.py
```

## 📊 예제 목록

### 1. 인구 통계 분석 (`01_population_analysis.py`)

**지표**: 행정구역별 인구수 (DT_1B040A3)

| 항목 | 내용 |
|------|------|
| 출처 | 통계청 |
| 주기 | 연간/월간 |
| 수록기간 | 1992년 ~ 현재 |

**분석 내용**:
- 전국 인구 추이
- 지역별 인구 비교
- 인구 증감률 계산
- 인구 집중도 분석

**생성되는 시각화**:
- `population_trend.html` - 전국 인구 추이
- `regional_comparison.html` - 지역별 인구 비교
- `regional_trend.html` - 주요 지역 추이
- `regional_pie.html` - 인구 구성비

---

### 2. 소비자물가지수 분석 (`02_consumer_price_analysis.py`)

**지표**: 소비자물가지수 (DT_1J22001)

| 항목 | 내용 |
|------|------|
| 출처 | 통계청 |
| 주기 | 월간 |
| 기준시점 | 2020년 = 100 |

**분석 내용**:
- 물가지수 추이
- 품목별 물가 비교
- 월별 변동률 분석
- 인플레이션 트렌드

**생성되는 시각화**:
- `cpi_trend.html` - 물가지수 추이
- `cpi_by_category.html` - 품목별 비교
- `cpi_growth_rate.html` - 월별 변동률

---

## 📋 분석 구조

각 예제는 다음과 같은 일관된 구조를 따릅니다:

```
1. 기초 설명
   - 지표 개요
   - 작성기관/주기/수록기간
   - 활용분야

2. EDA (탐색적 데이터 분석)
   - 필드 구조
   - 차원 정보
   - 샘플 데이터

3. 주요 통계
   - 요약 통계량
   - 시계열 데이터
   - 순위 분석

4. 시각화
   - 라인 차트 (추이)
   - 막대 차트 (비교)
   - 파이 차트 (구성비)

5. 인사이트
   - 주요 발견사항
   - 시사점

6. LLM 컨텍스트
   - AI 분석용 데이터 요약
```

## 🛠 사용된 도구

- **kosis_tools.StatisticsData**: API 데이터 조회
- **kosis_tools.KosisTransformer**: 데이터 변환/집계
- **kosis_tools.KosisVisualizer**: 시각화 생성

## 📝 나만의 분석 추가하기

새로운 분석 예제를 추가하려면:

1. 새 Python 파일 생성 (예: `03_employment_analysis.py`)
2. 템플릿 구조 복사
3. 지표 정보 및 분석 내용 수정
4. 실행 및 검증

```python
from kosis_tools import StatisticsData
from kosis_tools.transform import KosisTransformer
from kosis_tools.visualize import KosisVisualizer

# 데이터 조회
data_client = StatisticsData()
records = data_client.get_data(
    org_id="기관ID",
    tbl_id="테이블ID",
    start_date="시작연도",
    end_date="종료연도",
)

# 변환 및 분석
tx = KosisTransformer(records)
df = tx.to_dataframe()

# 시각화
viz = KosisVisualizer()
fig = viz.line_chart(records, title="제목")
viz.save_chart(fig, "output/my_chart.html")
```

## ⚠️ 주의사항

- KOSIS API 키가 환경변수에 설정되어 있어야 합니다
- `KOSIS_API_KEY` 또는 `.env` 파일에 설정
- API 요청은 rate limiting이 적용됩니다 (1초 간격)

## 📚 참고자료

- [KOSIS 국가통계포털](https://kosis.kr)
- [KOSIS OpenAPI 매뉴얼](https://kosis.kr/openapi/)
- [kosis_tools 패키지 문서](../../docs/)
