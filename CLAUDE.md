# KOSIS Data Processor - Project Constraints

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
