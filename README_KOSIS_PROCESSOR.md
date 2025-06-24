# KOSIS Data Processor

KOSIS (Korean Statistical Information Service) 데이터를 자동으로 수집하고 처리하는 시스템입니다.

## 주요 기능

1. **자동 데이터 수집**: regional_index_data_list.csv의 모든 통계표 ID에 대해 데이터 수집
2. **메타데이터 통합**: kosis_metadata_final.json의 메타데이터를 활용한 증강된 데이터 생성
3. **다양한 출력 형식**: JSON (long format), CSV (wide format), Parquet 지원
4. **동적 연도 처리**: 각 테이블의 실제 데이터 기간에 맞춘 자동 처리
5. **오류 처리 및 재시도**: 실패한 테이블 자동 기록 및 재시도 기능

## 설치 및 설정

### 1. 필요한 패키지 설치
```bash
pip install requests pandas pyarrow pyyaml tqdm
```

### 2. API 키 설정
다음 두 가지 방법 중 하나로 API 키 설정:

#### 방법 1: .env 파일 사용 (권장)
`.env` 파일 생성 후 다음 내용 추가:
```
KOSIS_API_KEY=your_actual_api_key_here
```

#### 방법 2: config.yaml 사용
config.yaml 파일에서 직접 설정:
```yaml
api:
  api_key: "your_actual_api_key_here"
```

API 키는 [KOSIS OpenAPI](https://kosis.kr/openapi/)에서 발급받을 수 있습니다.

## 사용 방법

### 전체 테이블 처리
```bash
python src/kosis_processor.py
```

### 특정 테이블만 처리
```bash
python src/kosis_processor.py --table-id DT_1YL20631
```

### 테스트 모드 (처음 5개 테이블만)
```bash
python src/kosis_processor.py --test
```

### 실패한 테이블 재시도
```bash
python src/kosis_processor.py --retry-failed
```

### 단일 테이블 테스트
```bash
# test_single_table.py에서 API 키 설정 후
python test_single_table.py
```

## 출력 구조

```
kosis_data/
├── raw/              # 원본 API 응답
│   └── {TBL_ID}_raw.json
├── processed/        # 처리된 데이터
│   ├── json/        # Long format (전체 메타데이터 포함)
│   ├── csv/         # Wide format (연도별 컬럼)
│   └── parquet/     # 효율적 저장 형식
├── reports/         # 처리 결과 보고서
│   └── processing_report_YYYYMMDD_HHMMSS.json
└── failed/          # 실패한 테이블 목록
    └── failed_tables_YYYYMMDD_HHMMSS.json
```

## 데이터 형식

### Long Format (JSON)
```json
{
  "metadata": {
    "org_id": "101",
    "org_name": "통계청",
    "table_id": "DT_1YL20631",
    "table_name": "고령인구비율(시도/시/군/구)",
    "date_range": "2000 ~ 2025",
    ...
  },
  "data": [
    {
      "item": "서울특별시 - 종로구 - 고령인구비율",
      "timestamp": "2024",
      "value": 23.5
    },
    ...
  ]
}
```

### Wide Format (CSV)
```
item,category,2000,2001,2002,...,2024
서울특별시 - 종로구 - 고령인구비율,Statistics,15.2,15.8,16.3,...,23.5
...
```

## 주요 클래스

### KosisAPIWrapper
- KOSIS API 호출 및 응답 처리
- 비표준 JSON 수정
- 최적 수록주기 자동 탐색 (월→분기→반기→년)

### DataProcessor
- 원시 데이터를 item 기반 형식으로 변환
- Long format을 Wide format으로 피벗
- 다양한 출력 형식 저장

### BatchProcessor
- 여러 테이블 일괄 처리
- 진행 상황 추적
- 오류 처리 및 보고서 생성

## 설정 옵션 (config.yaml)

- `api.rate_limit`: API 호출 간격 (초)
- `processing.max_workers`: 동시 처리 워커 수 (1 권장)
- `output.formats`: 출력 형식 선택
- `logging.level`: 로깅 레벨 (DEBUG, INFO, WARNING, ERROR)

## 문제 해결

### API 키 오류
- config.yaml의 api_key가 올바르게 설정되었는지 확인
- API 키가 활성화되어 있는지 KOSIS 사이트에서 확인

### 메타데이터 불일치
- 일부 테이블 ID가 메타데이터에 없을 수 있음
- reports/processing_report_*.json에서 실패 원인 확인

### 메모리 부족
- 대용량 데이터의 경우 처리를 나누어 실행
- `--table-id` 옵션으로 개별 처리

## 로그 파일

처리 과정은 `kosis_processor.log`에 기록됩니다.