# KOSIS 메타데이터 수집 가이드

메타데이터 수집 및 캐싱 프로세스 문서. 주기적 업데이트 시 참조.

---

## 목차

1. [개요](#개요)
2. [수집 파이프라인](#수집-파이프라인)
3. [스크립트 실행 순서](#스크립트-실행-순서)
4. [필드별 수집 현황](#필드별-수집-현황)
5. [파일 구조](#파일-구조)
6. [업데이트 주기](#업데이트-주기)
7. [트러블슈팅](#트러블슈팅)

---

## 개요

### 수집 대상
- **총 통계표**: 252,890개 (2024-12 기준)
- **데이터 소스**: 주제별, 기관별, 국제, 북한, e-지방지표

### 사용 API
| API | 용도 | 필드 수 |
|-----|------|---------|
| `statisticsList.do` | 기본 목록 | 9개 |
| `statisticsExplData.do` | 통계설명 | 26개 |
| `statisticsSearch.do` | 검색 정보 | 5개 |
| `statisticsData.do?method=getMeta` | 메타자료 | 5개 |

### 총 필드
- **~45개 필드** per 통계표

---

## 수집 파이프라인

```
┌─────────────────────────────────────────────────────────────────┐
│ 1단계: 기본 목록 수집 (statisticsList.do)                        │
│    - 6개 데이터소스 순회                                         │
│    - 계층형 카테고리 탐색                                        │
│    → scripts/build_tables_cache.py                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2단계: 통계설명 보강 (statisticsExplData.do)                     │
│    - stat_id별 그룹핑 (중복 API 호출 방지)                        │
│    - 26개 필드 수집                                              │
│    → scripts/enrich_metadata.py                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3단계: 검색 정보 보강 (statisticsSearch.do)                      │
│    - MT_ATITLE, CONTENTS, ITEM03 등                             │
│    → scripts/enrich_extended.py                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4단계: ORG/SOURCE 보강 (getMeta type=ORG,SOURCE)                 │
│    - 기관 영문명, 출처/담당부서 정보                              │
│    → scripts/enrich_org_source.py                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 최종 출력: data/metadata_api/tables.json                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 스크립트 실행 순서

### 전체 재수집 (Full Rebuild)

```bash
# 1단계: 기본 목록 수집 (~30분)
uv run python scripts/build_tables_cache.py

# 2단계: 통계설명 보강 (~2시간)
uv run python scripts/enrich_metadata.py

# 3단계: 검색 정보 + 확장 필드 (~2시간)
uv run python scripts/enrich_extended.py

# 4단계: ORG/SOURCE 보강 (~1시간)
uv run python scripts/enrich_org_source.py
```

### 증분 업데이트 (Incremental)

각 스크립트는 **캐시 파일**을 사용하여 이미 수집된 데이터를 스킵합니다.
캐시가 있으면 자동으로 증분 업데이트됩니다.

```bash
# 캐시 파일 위치
data/metadata_api/
├── tables.json              # 최종 결과
├── stats_cache.json         # 통계설명 캐시 (stat_id별)
├── search_cache.json        # 검색 정보 캐시
└── org_source_cache.json    # ORG/SOURCE 캐시
```

### 강제 재수집

캐시를 삭제하고 다시 실행:

```bash
rm data/metadata_api/*_cache.json
uv run python scripts/enrich_metadata.py
```

---

## 필드별 수집 현황

### 기본 필드 (statisticsList.do) - 100%

| 필드 | 설명 | 보강률 |
|------|------|--------|
| `tbl_id` | 통계표 ID | 100% |
| `tbl_nm` | 통계표명 | 100% |
| `org_id` | 기관 ID | 100% |
| `stat_id` | 통계 ID | 100% |
| `vw_cd` | 뷰 코드 | 100% |

### 가공 필드 - 100%

| 필드 | 설명 |
|------|------|
| `data_source` | 출처 구분 (subject, organization, ...) |
| `level` | 계층 레벨 |
| `path` | 전체 경로 (예: 인구 > 인구동향조사 > ...) |
| `path_ids` | 경로 ID 목록 |
| `keywords` | 검색 키워드 |

### 통계설명 API (statisticsExplData.do) - 95%+

| 필드 | 설명 | 보강률 |
|------|------|--------|
| `stats_nm` | 조사명 | 96% |
| `writing_purps` | 조사목적 | 96% |
| `stats_period` | 조사주기 | 96% |
| `stats_kind` | 작성유형 | 96% |
| `stats_end` | 통계종류 | 96% |
| `basis_law` | 법적근거 | 48% |
| `examin_pd` | 조사기간 | 96% |
| `writing_system` | 조사체계 | 96% |
| `examin_obj_range` | 조사 대상범위 | 82% |
| `examin_obj_area` | 조사 대상지역 | 96% |
| `josa_unit` | 조사단위/규모 | 96% |
| `josa_itm` | 조사항목 | 96% |
| `apply_group` | 적용분류 | 96% |
| `pub_period` | 공표주기 | 96% |
| `pub_extent` | 공표범위 | 96% |
| `publict_mth` | 공표방법/URL | 96% |
| `main_term_expl` | 용어해설 | 88% |
| `data_user_note` | 유의사항 | 96% |
| `data_collect_mth` | 자료수집방법 | 87% |
| `examin_history` | 조사연혁 | 96% |
| `confm_no` | 승인번호 | 96% |
| `confm_dt` | 승인일자 | 96% |
| `writing_tel` | 연락처 | 99% |
| `stats_field` | 통계분야 | 89% |
| `tbl_nm_eng` | 영문명 | 25% |

### 검색 API (statisticsSearch.do) - 33%

| 필드 | 설명 | 보강률 |
|------|------|--------|
| `mt_atitle` | 분류 경로 | 33% |
| `contents` | 데이터 미리보기 | 33% |
| `item03` | 설명/출처 | 17% |
| `tbl_view_url` | KOSIS URL | 33% |
| `stat_db_cnt` | 데이터 건수 | 33% |

> 검색 API는 검색 결과에 나오는 테이블만 보강됨

### 메타자료 API (getMeta) - 64~99%

| 필드 | 설명 | 보강률 |
|------|------|--------|
| `org_nm_eng` | 기관 영문명 | 64% |
| `source_josa_nm` | 조사기관 | 99.5% |
| `source_dept_nm` | 담당부서 | 98% |
| `source_dept_phone` | 연락처 | 99% |

---

## 파일 구조

```
data/metadata_api/
├── tables.json              # 최종 메타데이터 (252,890 테이블)
│   ├── tables: [...]        # 통계표 배열
│   └── metadata:            # 메타 정보
│       ├── version          # 생성 일자
│       ├── total_count      # 총 개수
│       └── sources          # 출처별 개수
│
├── stats_cache.json         # stat_id → 통계설명 캐시
├── search_cache.json        # tbl_id → 검색 정보 캐시
└── org_source_cache.json    # (org_id, tbl_id) → ORG/SOURCE 캐시
```

### tables.json 크기

- **비압축**: ~350MB
- **gzip 압축**: ~35MB (10배 압축)

---

## 업데이트 주기

### 권장 주기

| 항목 | 주기 | 이유 |
|------|------|------|
| 전체 재수집 | 분기 1회 | 신규 통계표 추가, 폐지 반영 |
| 증분 업데이트 | 월 1회 | 메타데이터 변경 반영 |

### 자동화 (예시)

```bash
# crontab 예시: 매월 1일 새벽 3시
0 3 1 * * cd /path/to/kosis-data-processor && ./scripts/update_metadata.sh
```

### update_metadata.sh

```bash
#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "=== KOSIS 메타데이터 업데이트 시작 ==="
date

# 증분 업데이트 (캐시 활용)
uv run python scripts/enrich_metadata.py
uv run python scripts/enrich_extended.py
uv run python scripts/enrich_org_source.py

# 압축 버전 생성
gzip -k -f data/metadata_api/tables.json

echo "=== 완료 ==="
date
```

---

## 트러블슈팅

### 1. API 호출 실패

```
에러: aiohttp.ClientResponseError: 429 Too Many Requests
```

**해결**: `rate_limit` 값 증가 (기본 0.03초 → 0.1초)

```python
enricher = MetadataEnricher(concurrency=10, rate_limit=0.1)
```

### 2. 메모리 부족

```
에러: MemoryError
```

**해결**: 배치 크기 축소

```python
# metadata_enricher.py
BATCH_SIZE = 500  # 기본 1000 → 500
```

### 3. 캐시 손상

```
에러: json.JSONDecodeError
```

**해결**: 해당 캐시 파일 삭제 후 재실행

```bash
rm data/metadata_api/stats_cache.json
uv run python scripts/enrich_metadata.py
```

### 4. 중단 후 재개

스크립트는 캐시 기반이므로 중단 후 재실행하면 자동으로 이어서 진행됩니다.

```bash
# Ctrl+C로 중단 후
uv run python scripts/enrich_org_source.py  # 자동 재개
```

---

## 참고

### 미사용 API (향후 검토)

| API | 용도 | 상태 |
|-----|------|------|
| `getMeta type=PRD` | 수록기간 정보 | 미테스트 |
| `getMeta type=UNIT` | 단위 정보 | 미테스트 |
| `getMeta type=NOTE` | 주석 정보 | 미테스트 |
| `getMeta type=ITM_CLSS` | 분류/항목 구조 | 대부분 빈값 |
| `statHtmlContent.do` | k-stat URL | 중복 정보 |

### 관련 문서

- [KOSIS_API_REFERENCE.md](./KOSIS_API_REFERENCE.md) - API 상세 명세
- [CODEBASE_WALKTHROUGH.md](./CODEBASE_WALKTHROUGH.md) - 코드베이스 구조
- [MCP_PATTERN.md](../MCP_PATTERN.md) - 대용량 데이터 처리 패턴
