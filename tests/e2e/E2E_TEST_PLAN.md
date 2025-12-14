# KOSIS MCP Server E2E 테스트 계획

> 사용자 시나리오 기반 End-to-End 테스트 전략

## 1. 사용자 페르소나 정의

### 1.1 Persona A: 비전공자/일반인 (Beginner)
| 항목 | 설명 |
|------|------|
| **프로필** | 통계 비전공자, 데이터 분석 경험 없음, 대학생/일반 시민 |
| **목표** | "우리 지역 인구가 얼마나 되나요?", "최근 물가 많이 올랐나요?" |
| **특징** | 단순 질문, 기관/테이블 ID 모름, 자연어 쿼리 |
| **기대 결과** | 명확한 답변 + 시각화, 복잡한 파라미터 불필요 |

### 1.2 Persona B: 초보 분석가 (Intermediate)
| 항목 | 설명 |
|------|------|
| **프로필** | 대학원생, 주니어 연구원, 기초 데이터 분석 가능 |
| **목표** | "서울과 경기도 인구 비교해줘", "최근 5년 추이 분석" |
| **특징** | 비교/추이 분석 요청, 조건 필터링 이해 |
| **기대 결과** | 차트 + 분석 인사이트, 데이터 테이블 제공 |

### 1.3 Persona C: 전문 분석가 (Advanced)
| 항목 | 설명 |
|------|------|
| **프로필** | 정책 연구원, 데이터 분석가, 저널리스트 |
| **목표** | "인구 감소 상위 5개 지역 분석 + 리포트 생성" |
| **특징** | 복합 분석, 다중 테이블 조합, 리포트 요구 |
| **기대 결과** | 종합 리포트(HTML), 다양한 차트, 심층 인사이트 |

### 1.4 Persona D: 전문가/개발자 (Expert)
| 항목 | 설명 |
|------|------|
| **프로필** | 데이터 엔지니어, API 통합 개발자, 통계 전문가 |
| **목표** | 특정 테이블 데이터 추출, 자동화 파이프라인 구축 |
| **특징** | org_id, tbl_id 직접 지정, 대용량 데이터 처리 |
| **기대 결과** | 정확한 데이터, 토큰 효율성, 청킹/페이지네이션 |

---

## 2. 시나리오별 테스트 케이스

### 2.1 Persona A 시나리오: 단순 질문

#### Scenario A1: "서울 인구가 얼마나 되나요?"
```yaml
workflow:
  1. search_statistics("서울 인구")
  2. get_statistics_data(선택된 테이블)
  3. get_data_summary()

expected:
  - 검색 결과 반환 (< 2초)
  - 데이터 조회 성공
  - 명확한 숫자 답변: "서울 인구는 약 9,411,211명입니다 (2023년)"

artifacts:
  - 없음 (텍스트 답변만)

validation:
  - output_length: < 500자
  - response_time: < 5초
  - contains: ["서울", "인구", "명"]
```

#### Scenario A2: "최근 물가 많이 올랐나요?"
```yaml
workflow:
  1. search_statistics("소비자물가지수")
  2. get_statistics_data() - 최근 2년
  3. analyze_data_trend()

expected:
  - 물가 상승률 수치 제공
  - 간단한 해석 ("X% 상승했습니다")

validation:
  - contains: ["%", "상승" or "하락"]
  - no_technical_jargon: true
```

---

### 2.2 Persona B 시나리오: 비교 분석

#### Scenario B1: "서울과 경기도 인구 비교"
```yaml
workflow:
  1. search_statistics("인구")
  2. get_statistics_data(period: 2019-2023)
  3. filter_statistics_data(regions: [서울, 경기도])
  4. analyze_data_comparison()
  5. create_quick_report()

expected:
  - 비교 분석 결과
  - 추이 차트
  - 인사이트 ("경기도가 서울보다 X배 많음")

artifacts:
  - HTML 리포트 (선택)
  - 라인 차트
  - 막대 차트

validation:
  - chart_count: >= 2
  - findings: >= 3
  - report_size: < 100KB
```

#### Scenario B2: "최근 5년 인구 변화 추이"
```yaml
workflow:
  1. get_statistics_data(2019-2023)
  2. analyze_data_trend(group_by="C1_NM")
  3. viz_line_trend()

expected:
  - 연도별 추이 데이터
  - 증감률 계산
  - 추세선 차트

validation:
  - has_trend_chart: true
  - periods_count: 5
  - trend_direction: ["증가", "감소", "유지"] 중 하나
```

---

### 2.3 Persona C 시나리오: 전문 분석

#### Scenario C1: "인구 감소 상위 5개 지역 분석"
```yaml
workflow:
  1. get_statistics_data(2019-2023)
  2. calculate_change_rate_per_region
  3. analyze_data_ranking(top_n=5)
  4. filter for declining regions
  5. analyze_data_trend(group_by)
  6. create_custom_report()

expected:
  - 순위 테이블 (1-5위)
  - 감소율 수치
  - 지역별 추이 차트
  - 정책 시사점 인사이트

artifacts:
  - 종합 HTML 리포트
  - 순위 테이블
  - 지역별 추이 차트
  - 감소율 막대 차트
  - 하이라이트 박스

validation:
  - ranking_count: 5
  - report_sections: >= 4
  - insights_depth: "deep"
  - report_file_created: true
  - report_size: 50KB ~ 500KB
```

#### Scenario C2: "산업별 고용 현황 대시보드"
```yaml
workflow:
  1. search_statistics("고용")
  2. get_statistics_data(2023)
  3. analyze_stats()
  4. analyze_ranking()
  5. create_custom_report(dashboard=true)

expected:
  - KPI 카드 그리드
  - 파이 차트 (비중)
  - 막대 차트 (산업별)
  - 히트맵 (산업x분기)

artifacts:
  - 대시보드 HTML
  - 최소 4종 차트

validation:
  - kpi_cards: >= 3
  - chart_types: ["line", "bar", "pie", "heatmap"] 중 3개 이상
  - layout: "dashboard" template 사용
```

---

### 2.4 Persona D 시나리오: 대용량/기술적

#### Scenario D1: "대용량 데이터 청킹"
```yaml
workflow:
  1. get_statistics_data(org_id="101", tbl_id="DT_1B040A3", 2010-2023)
  2. Verify chunked response

expected:
  - 청크 응답 (50건 단위)
  - 총 레코드 수 표시
  - data_id로 추가 청크 접근 가능

validation:
  - response_pattern: "summary" mode
  - token_count: < 5000
  - token_reduction: >= 90%
  - has_data_id: true (chunked인 경우)
```

#### Scenario D2: "특정 테이블 메타데이터 조회"
```yaml
workflow:
  1. get_table_metadata(org_id="101", tbl_id="DT_1B040A3")
  2. get_statistics_data with specific params

expected:
  - 분류항목(dimensions) 목록
  - 항목(items) 목록
  - 기간 정보

validation:
  - has_dimensions: true
  - has_items: true
  - has_period_info: true
```

---

## 3. MCP 출력 검증 기준

### 3.1 토큰 효율성 (MCP_PATTERN.md 준수)

| 데이터 크기 | 원본 토큰 | 목표 출력 | 절감률 |
|------------|----------|----------|--------|
| 100건 | ~5,000 | < 2,000 | ≥ 60% |
| 500건 | ~25,000 | < 3,000 | ≥ 88% |
| 1,000건 | ~50,000 | < 5,000 | ≥ 90% |
| 3,000건 | ~150,000 | < 5,000 | ≥ 97% |

### 3.2 응답 구조 검증

```python
# 필수 필드 (summary 모드)
required_fields = {
    "summary": ["total_records", "period_range", "dimensions"],
    "metadata": ["tbl_id", "tbl_nm", "org_id", "org_nm"],
    "data_availability": ["full_data_available", "sample_count", "note"],
    "pivot_summary": ["by_period", "by_c1"],
}
```

### 3.3 컨텍스트 길이 제한

| 응답 타입 | 최대 문자 | 최대 토큰 (추정) |
|----------|----------|-----------------|
| summary | 10,000자 | ~5,000 |
| sample | 5,000자 | ~2,500 |
| analysis | 2,000자 | ~1,000 |
| report_meta | 1,000자 | ~500 |

### 3.4 안티패턴 탐지

```python
antipatterns = [
    "전체 데이터를 data/records 필드에 포함",
    "각 행에 TBL_NM, ORG_NM 반복",
    "PRD_DE 등 원본 필드명 노출 (한글 라벨 미사용)",
    "sample 50행 초과",
]
```

---

## 4. 리포트 아티팩트 검증

### 4.1 HTML 리포트 품질

```yaml
structure:
  - "<!DOCTYPE html>" 포함
  - "<html lang=\"ko\">" 한글 설정
  - Plotly CDN 로드
  - "Noto Sans KR" 폰트 적용

content:
  - 제목 (title)
  - KPI 카드 (kpi-card class)
  - 차트 컨테이너 (chart-container class)
  - 인사이트 섹션
  - 데이터 출처 (KOSIS)

size:
  - quick_report: 20KB ~ 100KB
  - custom_report: 50KB ~ 500KB
  - dashboard: 100KB ~ 1MB
```

### 4.2 차트 유형별 검증

| 차트 | 필수 요소 | 검증 방법 |
|-----|----------|----------|
| Line | Plotly.newPlot, x축, y축 | `"mode": "lines"` in JS |
| Bar | x축 라벨, y축 값 | `"type": "bar"` in JS |
| Pie | labels, values | `"type": "pie"` in JS |
| Heatmap | x, y, z 데이터 | `"type": "heatmap"` in JS |

### 4.3 분석 인사이트 품질

```yaml
findings:
  - 최소 3개 이상
  - 구체적 수치 포함
  - 비교 표현 ("X보다 Y가 Z% 높음")

interpretation:
  - 1-3문장
  - 정책/비즈니스 시사점 포함
  - 전문 용어 최소화
```

---

## 5. 파이프라인 오류 시나리오

### 5.1 API 오류 처리

| 오류 유형 | 트리거 | 예상 행동 |
|----------|-------|----------|
| API 키 누락 | KOSIS_API_KEY 미설정 | 명확한 에러 메시지 |
| 테이블 없음 | 잘못된 tbl_id | "통계표를 찾을 수 없습니다" |
| 기간 오류 | 미래 날짜 요청 | 사용 가능한 기간 안내 |
| 빈 결과 | 조건에 맞는 데이터 없음 | "조건에 맞는 데이터가 없습니다" |

### 5.2 데이터 품질 오류

| 오류 유형 | 예상 행동 |
|----------|----------|
| DT 값이 "-" | 숫자 변환 시 0 또는 null 처리 |
| 비표준 기간 형식 | 파싱 실패 시 원본 반환 |
| 결측 필드 | 기본값 사용, 에러 아닌 경고 |

---

## 6. 테스트 실행 계획

### 6.1 테스트 레벨

```
tests/
├── unit/           # 개별 함수 테스트
├── integration/    # API + 함수 통합
└── e2e/            # 전체 워크플로우
    ├── test_persona_a.py     # 비전공자 시나리오
    ├── test_persona_b.py     # 초보 분석가 시나리오
    ├── test_persona_c.py     # 전문 분석가 시나리오
    ├── test_persona_d.py     # 전문가/개발자 시나리오
    ├── test_mcp_output.py    # MCP 출력 검증
    ├── test_report_quality.py # 리포트 품질 검증
    └── test_error_handling.py # 오류 처리 검증
```

### 6.2 실행 명령

```bash
# 전체 E2E 테스트
uv run pytest tests/e2e/ -v -s

# 특정 페르소나만
uv run pytest tests/e2e/test_persona_a.py -v

# MCP 출력 검증만
uv run pytest tests/e2e/test_mcp_output.py -v

# 마커별 실행
uv run pytest -m "slow" tests/e2e/  # 대용량 데이터 테스트
uv run pytest -m "api" tests/e2e/   # 실제 API 호출 테스트
```

### 6.3 환경 설정

```bash
# 필수 환경 변수
export KOSIS_API_KEY="your_api_key"

# 선택적
export TEST_OUTPUT_DIR="./test_outputs"
export TEST_SLOW_ENABLED=1  # 대용량 테스트 활성화
```

---

## 7. 성공 기준

### 7.1 기능 테스트
- [ ] 모든 페르소나 시나리오 통과
- [ ] 워크플로우 단계별 정상 동작
- [ ] 예상 아티팩트 생성

### 7.2 MCP 모범사례
- [ ] 토큰 절감률 90% 이상 (1,000건 기준)
- [ ] 응답 구조 검증 통과
- [ ] 안티패턴 미탐지

### 7.3 품질 지표
- [ ] HTML 리포트 정상 렌더링
- [ ] 차트 4종 이상 지원
- [ ] 인사이트 품질 검증 통과

### 7.4 안정성
- [ ] 오류 시나리오 정상 처리
- [ ] 대용량 데이터 청킹 동작
- [ ] 응답 시간 5초 이내 (summary 모드)

---

## 8. 참고 자료

- [MCP_PATTERN.md](../../MCP_PATTERN.md) - 대용량 데이터 처리 패턴
- [기존 E2E 테스트](./test_llm_workflow.py) - LLM 워크플로우 시나리오
- [MCP 가이드라인 테스트](../unit/test_mcp_guidelines.py) - 출력 검증 테스트
- [출력 크기 검증](../check_output_sizes.py) - 토큰 효율성 측정
