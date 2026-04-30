# korean-stat-mcp

KOSIS OpenAPI 데이터를 MCP 클라이언트에서 바로 쓸 수 있게 만든 Python 서버입니다.

Claude Desktop, Claude Code, Cursor, Windsurf 같은 MCP 지원 도구에서 통계표를
검색하고, 메타데이터를 확인하고, 데이터를 가져와 간단한 분석이나 시각화까지 이어갈
수 있습니다.

[English README](./README-EN.md)

[![PyPI](https://img.shields.io/pypi/v/korean-stat-mcp)](https://pypi.org/project/korean-stat-mcp/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/seolcoding/korean-stat-mcp/ci.yml?branch=main)](https://github.com/seolcoding/korean-stat-mcp/actions)

## 할 수 있는 일

- KOSIS 통계표 키워드 검색
- 기관/주제별 통계 목록 탐색
- 통계표 분류, 항목, 수록 기간 같은 메타데이터 조회
- 원천 데이터 조회, 필터링, 그룹 집계
- Altair 기반 차트와 HTML 리포트 생성
- `verify_statistics`로 특정 수치가 KOSIS 원천 행과 맞는지 확인

KOSIS API는 테이블마다 필요한 파라미터가 조금씩 다르고, 기간/분기/지자체
데이터에서 예외가 자주 나옵니다. 이 서버는 그 부분을 MCP 도구 형태로 감싸서
클라이언트 쪽 설정을 줄이는 데 초점을 둡니다.

## 설치

먼저 KOSIS OpenAPI 키가 필요합니다. 키는
[KOSIS OpenAPI 신청 페이지](https://kosis.kr/openapi/)에서 발급받을 수 있습니다.

### Claude Code 플러그인

```bash
/plugin marketplace add seolcoding/korean-stat-mcp
```

설치 후 `KOSIS_API_KEY`를 설정합니다.

### Claude Desktop / Cursor / Windsurf

```bash
pip install korean-stat-mcp
```

MCP 설정 파일에 아래 내용을 추가합니다.

```json
{
  "mcpServers": {
    "korean-stat": {
      "command": "korean-stat-mcp",
      "env": {
        "KOSIS_API_KEY": "<KOSIS_API_KEY>"
      }
    }
  }
}
```

Claude Desktop의 macOS 설정 파일 위치:

```text
~/Library/Application Support/Claude/claude_desktop_config.json
```

### uvx로 실행

```json
{
  "mcpServers": {
    "korean-stat": {
      "command": "uvx",
      "args": ["korean-stat-mcp"],
      "env": {
        "KOSIS_API_KEY": "<KOSIS_API_KEY>"
      }
    }
  }
}
```

### 직접 실행

```bash
pip install korean-stat-mcp
export KOSIS_API_KEY="<KOSIS_API_KEY>"
korean-stat-mcp
```

설치 확인:

```bash
korean-stat-mcp --version
```

## 원격 MCP로 호스팅하기

공식 호스팅 엔드포인트는 아직 없습니다. Claude.ai의 custom connector에서 쓰려면
직접 배포한 뒤 아래 형태의 URL을 등록합니다.

```text
https://<your-host>/mcp
```

배포 예시는 [deploy/README.md](./deploy/README.md)에 정리되어 있습니다. Docker,
Fly.io, Render, Railway, DigitalOcean App Platform, 일반 VPS 배포를 다룹니다.

상태 확인:

```bash
curl https://<your-host>/health
```

## 주요 도구

| 구분 | 도구 | 용도 |
|---|---|---|
| 검색 | `search_statistics` | 키워드로 통계표 찾기 |
| 탐색 | `browse_categories` | 기관/주제별 목록 탐색 |
| 메타데이터 | `get_table_metadata`, `get_available_values` | 분류, 항목, 기간 확인 |
| 데이터 | `get_statistics_data` | KOSIS 원천 데이터 조회 |
| 가공 | `filter_statistics`, `aggregate_statistics` | 필터링, 그룹 집계 |
| 저장 데이터 | `read_stored_data`, `list_stored_data` | 큰 결과를 나눠 읽기 |
| 검증 | `verify_statistics` | 특정 수치와 원천 데이터 대조 |
| 출력 | `execute_visualization`, `execute_table`, `execute_report` | 차트, 표, 리포트 생성 |

전체 도구 목록과 이전 이름과의 매핑은
[docs/TOOL_MIGRATION.md](./docs/TOOL_MIGRATION.md)를 참고하세요.

## 환경변수

| 변수 | 필수 | 설명 |
|---|---:|---|
| `KOSIS_API_KEY` | 예 | KOSIS OpenAPI 인증키 |
| `KOSIS_ARTIFACTS_DIR` | 아니오 | 로컬 차트/리포트 저장 경로 |
| `KOSIS_MCP_URL` | 아니오 | 자체 호스팅 인스턴스의 base URL |
| `R2_BUCKET_NAME` | 아니오 | Cloudflare R2 버킷 |
| `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` | 아니오 | Cloudflare R2 인증 정보 |
| `R2_PUBLIC_URL` | 아니오 | R2 공개 URL prefix |

전체 예시는 [.env.example](./.env.example)에 있습니다.

## 검증 상태

- Python 3.12 / 3.13 CI를 사용합니다.
- 2026-04-30 기준 unit test는 446개가 통과했습니다.
- KOSIS live pilot 100건에서 API 오류, timeout, parse 오류는 없었습니다.
  `no_data` 2건은 폐기되었거나 응답이 비어 있는 통계표로 분류했습니다.

자세한 내용은 [docs/VALIDATION_REPORT.md](./docs/VALIDATION_REPORT.md)에 있습니다.

## 문서

- [docs/USER_GUIDE.md](./docs/USER_GUIDE.md): 사용자 가이드
- [docs/KOSIS_API_REFERENCE.md](./docs/KOSIS_API_REFERENCE.md): KOSIS API 정리
- [docs/TOOL_MIGRATION.md](./docs/TOOL_MIGRATION.md): 도구 이름 변경/매핑
- [deploy/README.md](./deploy/README.md): 배포 가이드
- [MIGRATION.md](./MIGRATION.md): 기존 `kosis-mcp` 사용자용 변경 사항
- [CONTRIBUTING.md](./CONTRIBUTING.md): 개발 환경과 PR 절차

## 라이선스

코드는 MIT 라이선스로 배포됩니다. KOSIS 데이터 자체의 이용 조건은
[KOSIS 국가통계포털](https://kosis.kr/) 정책을 따릅니다.
