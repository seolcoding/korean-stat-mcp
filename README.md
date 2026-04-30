# korean-stat-mcp

> 한국 국가통계포털(KOSIS) 통합 MCP 도구 — Korean Statistics (KOSIS) MCP Server for LLM agents

[![PyPI](https://img.shields.io/pypi/v/korean-stat-mcp)](https://pypi.org/project/korean-stat-mcp/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![CI](https://img.shields.io/badge/CI-pending-lightgrey)](#)

🌐 English version: [README-EN.md](./README-EN.md)

---

## 왜 이 도구인가

- **검증된 안정성**: KOSIS OpenAPI 호출 성공률 **99.38%** (10,000건 샘플 테스트). 분기/반기/지자체 fallback 자동화로 LLM이 단일 API 호출만 신경 쓰면 됩니다.
- **큐레이션된 도구 표면**: 26개 내부 도구 중 LLM에게 정말 필요한 16개만 노출하여 토큰 낭비 없이 빠른 의사결정 흐름을 만듭니다.
- **`verify_statistics`**: LLM이 만든 수치 주장을 KOSIS 원천 데이터와 자동 대조하는 검증 도구. 환각(hallucination) 방어가 기본 내장입니다.
- **한국 통계 LLM 표준을 지향**: 천 단위 한글 포맷, 과학적표기법 금지, 한국어/영어 라우팅 매뉴얼 등 한국어 LLM 워크플로에 최적화.

---

## 🚀 Quick Start — 4가지 설치 채널

### 1. Claude Code 플러그인 마켓 (가장 쉬움)

```bash
/plugin marketplace add seolcoding/korean-stat-mcp
```

설치 후 `KOSIS_API_KEY` 환경변수만 설정하면 즉시 사용할 수 있습니다.
설치 검증: `korean-stat-mcp --version` (예상 출력: `korean-stat-mcp 0.1.0`).

### 2. Claude.ai 커스텀 커넥터 (호스팅 인스턴스 사용)

Claude.ai의 **Settings → Connectors → Add custom connector** 에서 다음 URL을 등록합니다.

```
https://korean-stat-mcp.example.com/mcp
```

> ⚠️ 공식 호스팅 엔드포인트는 운영팀 결정 전입니다. 직접 호스팅하려면 [deploy/README.md](./deploy/README.md) 의 Fly.io / Render / Railway / DigitalOcean / VPS 가이드를 참고하세요.
> 검증: `curl https://<your-host>/health` 가 `200 OK` 를 반환해야 합니다.

### 3. Claude Desktop / Cursor / Windsurf (JSON 설정)

```bash
pip install korean-stat-mcp
```

설정 파일에 다음 블록을 추가합니다.

```json
{
  "mcpServers": {
    "korean-stat": {
      "command": "korean-stat-mcp",
      "env": {
        "KOSIS_API_KEY": "<여기에-KOSIS-API-키>"
      }
    }
  }
}
```

- macOS Claude Desktop: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Cursor / Windsurf: 각 IDE의 MCP 설정 화면에서 위 JSON을 그대로 사용

설치 검증: `korean-stat-mcp --version` (예상 출력: `korean-stat-mcp 0.1.0`).

### 4. PyPI 직접 설치 (스크립트/CLI)

```bash
pip install korean-stat-mcp
export KOSIS_API_KEY="<여기에-KOSIS-API-키>"

# stdio 모드로 직접 실행
korean-stat-mcp
```

설치 검증: `korean-stat-mcp --version` (예상 출력: `korean-stat-mcp 0.1.0`).
KOSIS API 키는 [KOSIS OpenAPI 신청 페이지](https://kosis.kr/openapi/)에서 무료로 발급받을 수 있습니다.

---

## 도구 일람

LLM 에 노출되는 큐레이션 도구 (12-16개 수준). 자세한 시그니처와 마이그레이션 매핑은 [docs/TOOL_MIGRATION.md](./docs/TOOL_MIGRATION.md) 참조.

| 레이어 | 도구 | 설명 |
|--------|------|------|
| **DISCOVER** | `search_statistics` | KOSIS 검색 API 기반 통계표 검색 |
| | `get_table_metadata` | 테이블 분류·항목 메타데이터 |
| | `browse_categories` | 기관·주제별 카테고리 탐색 |
| **FETCH** | `get_statistics_data` | KOSIS 원천 데이터 조회 (chunked) |
| | `filter_statistics` | 서버 측 필터링 |
| | `aggregate_statistics` | 그룹 집계 |
| | `read_stored_data` | 큰 데이터셋의 청크 단위 접근 |
| **VERIFY** | `verify_statistics` | LLM 수치 주장 ↔ KOSIS 원천 자동 대조 |
| **PRESENT** | `execute_visualization` | Altair 차트 생성 (천 단위, 과학적표기법 금지) |
| | `execute_analysis` | 변화율·CAGR·통계 분석 |
| | `execute_table` | 스타일 적용된 HTML 테이블 |
| | `execute_report` | 차트+분석+테이블 복합 리포트 |

---

## 환경변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `KOSIS_API_KEY` | ✅ | KOSIS OpenAPI 키 ([발급](https://kosis.kr/openapi/)) |
| `R2_BUCKET_NAME` | 선택 | Cloudflare R2 차트/리포트 호스팅 버킷 |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | 선택 | R2 자격증명 |
| `R2_PUBLIC_URL` | 선택 | R2 퍼블릭 URL prefix |
| `KOSIS_ARTIFACTS_DIR` | 선택 | 로컬 아티팩트 저장 경로 (기본 `/tmp/kosis_artifacts`) |
| `KOSIS_MCP_URL` | 선택 | 자체 호스팅 인스턴스 베이스 URL |

전체 설정 항목은 [.env.example](./.env.example) 참조.

---

## 문서

- 프로젝트 진입점: [CLAUDE.md](./CLAUDE.md)
- 마이그레이션 가이드 (이전 `kosis-mcp` 사용자): [MIGRATION.md](./MIGRATION.md)
- 사용 가이드: [docs/USER_GUIDE.md](./docs/USER_GUIDE.md)
- 아키텍처: [docs/ARCHITECTURE_DESIGN.md](./docs/ARCHITECTURE_DESIGN.md)
- KOSIS API 레퍼런스: [docs/KOSIS_API_REFERENCE.md](./docs/KOSIS_API_REFERENCE.md)
- 배포 가이드: [deploy/README.md](./deploy/README.md)
- 대용량 데이터 패턴: [docs/LARGE_DATA_MCP_PATTERNS.md](./docs/LARGE_DATA_MCP_PATTERNS.md)

---

## 기여

이슈와 PR을 환영합니다. 개발 환경 셋업·코드 스타일·테스트 절차는 [CONTRIBUTING.md](./CONTRIBUTING.md) 를 참고해주세요. 행동 강령은 [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md) 를 따릅니다.

---

## 라이선스

본 프로젝트는 MIT 라이선스를 따릅니다. 전체 조항은 [LICENSE](./LICENSE) 파일을 확인해주세요.

데이터 출처는 [KOSIS 국가통계포털](https://kosis.kr/) 이며, 데이터 자체의 이용 조건은 KOSIS의 정책을 따릅니다.
