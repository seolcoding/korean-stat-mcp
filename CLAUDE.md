# KOSIS Data Processor - Project Constraints

## 필수 참조 문서

코드 수정 전 반드시 아래 문서를 읽으세요:

| 문서 | 내용 | 언제 참조 |
|------|------|----------|
| **[docs/KOSIS_API_REFERENCE.md](./docs/KOSIS_API_REFERENCE.md)** | KOSIS API 엔드포인트, 파라미터, 응답 필드 | API 호출/파싱 관련 작업 시 |
| **[docs/CODEBASE_WALKTHROUGH.md](./docs/CODEBASE_WALKTHROUGH.md)** | 아키텍처, 파일 역할, 데이터 흐름 | 새 기능 추가/수정 시 |
| **[MCP_PATTERN.md](./MCP_PATTERN.md)** | 대용량 데이터 처리 패턴 | MCP 도구 개발 시 |

## MCP Server Development

이 프로젝트는 KOSIS MCP Server입니다. MCP 도구 개발 시 반드시 참고:

- **[MCP_PATTERN.md](./MCP_PATTERN.md)**: 대용량 API 응답 처리 패턴
  - 전체 데이터를 LLM 컨텍스트에 넣지 말 것
  - summary → sample → chunk 순으로 점진적 공개
  - 서버사이드 처리 우선, 결과만 반환

## KOSIS API 핵심 필드 (Quick Reference)

데이터 조회 API (`statisticsParameterData.do`) 응답 필드:

| 필드 | 설명 | 예시 |
|------|------|------|
| `PRD_DE` | 기간 | `2023`, `202401` |
| `C1_NM` | 분류1 명칭 (주로 지역) | `서울특별시` |
| `DT` | **데이터 값 (문자열!)** | `"9411211"`, `"-"` |
| `ITM_NM` | 항목명 | `총인구`, `남자인구` |
| `UNIT_NM` | 단위 | `명`, `%` |

> ⚠️ `DT`는 문자열입니다. `"-"`, `"*"` 등 특수값 처리 필요!

상세 필드 설명은 [docs/KOSIS_API_REFERENCE.md](./docs/KOSIS_API_REFERENCE.md) 참조

## Technical Requirements

### NO Playwright / Browser Automation
- **Playwright, Selenium, Puppeteer 등 브라우저 자동화 도구 사용 금지**
- 모든 데이터 수집은 API 또는 `requests.get`으로 가능해야 함
- 빠른 실행 속도 필수 (순식간에 파싱 가능해야 함)

### Preferred Approach
1. KOSIS OpenAPI 활용
2. requests + BeautifulSoup for HTML parsing
3. 직접 HTTP 요청으로 데이터 추출

## KOSIS Endpoints

### API Endpoints
- `statisticsParameterData.do` - 실제 데이터 조회
- `statisticsList.do` - 통계 목록 조회
- API 응답이 비표준 JSON (키에 따옴표 없음) - 파싱 전 수정 필요

### HTML Endpoints (requests로 접근 가능)
- `statHtmlContent.do?orgId={}&tblId={}` - 테이블 상세 정보 HTML
  - k-stat.go.kr URL 포함 (statsConfmNo)
  - Playwright 없이 requests.get으로 파싱 가능

## k-stat.go.kr Integration
- 통계설명자료서비스 (메타데이터)
- URL: `https://www.k-stat.go.kr/metasvc/msba100/statsdcdta?statsConfmNo={번호}`
- KOSIS `statHtmlContent.do` HTML에서 statsConfmNo 추출
- 일부 테이블은 k-stat 링크가 없음 (정상)
