# KOSIS MCP Server

KOSIS(국가통계포털) 데이터를 Claude와 다른 LLM에서 직접 조회하고 분석할 수 있는 MCP(Model Context Protocol) 서버입니다.

## Features

- **DISCOVER**: 통계표 검색, 기관/주제 목록 조회, 메타데이터 확인
- **FETCH**: 통계 데이터 조회, 필터링, 집계
- **PRESENT**: 추세/비교/순위 분석, 시각화, 리포트 생성

## Installation

### Prerequisites

- Python 3.12+
- [KOSIS OpenAPI Key](https://kosis.kr/openapi/) (무료 발급)

### Option 1: uvx (권장)

설치 없이 바로 실행:

```bash
uvx kosis-mcp
```

### Option 2: pip

```bash
pip install kosis-mcp
```

### Option 3: uv

```bash
uv add kosis-mcp
```

## Configuration

### Environment Variable

```bash
export KOSIS_API_KEY="your-api-key"
```

또는 `.env` 파일 생성:

```env
KOSIS_API_KEY=your-api-key
```

## Claude Desktop Integration

### 방법 1: fastmcp install (권장)

```bash
fastmcp install claude-desktop kosis-mcp --env KOSIS_API_KEY=your-key
```

### 방법 2: 수동 설정

Claude Desktop 설정 파일 위치:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "kosis-mcp": {
      "command": "uvx",
      "args": ["kosis-mcp"],
      "env": {
        "KOSIS_API_KEY": "your-api-key"
      }
    }
  }
}
```

설정 후 Claude Desktop을 재시작하세요.

## Available Tools

| Category | Tool | Description |
|----------|------|-------------|
| DISCOVER | `search_statistics` | 키워드로 통계표 검색 |
| DISCOVER | `list_organizations` | 통계 작성 기관 목록 |
| DISCOVER | `list_themes` | 통계 주제 분류 목록 |
| DISCOVER | `get_table_metadata` | 통계표 상세 메타데이터 |
| FETCH | `get_statistics_data` | 통계 데이터 조회 |
| FETCH | `filter_data` | 데이터 필터링 |
| FETCH | `aggregate_data` | 데이터 집계 |
| FETCH | `get_available_values` | 사용 가능한 필드 값 조회 |
| PRESENT | `analyze_trend` | 시계열 추세 분석 |
| PRESENT | `analyze_comparison` | 항목 간 비교 분석 |
| PRESENT | `analyze_ranking` | 순위 분석 |
| PRESENT | `analyze_statistics` | 기술통계 분석 |
| PRESENT | `create_quick_report` | 원클릭 분석 리포트 |
| PRESENT | `create_custom_report` | 커스텀 리포트 생성 |

## Usage Examples

Claude에서 사용 예시:

```
"인구 관련 통계표를 검색해줘"
→ search_statistics("인구")

"통계청의 행정구역별 인구수 데이터를 2020-2023년으로 조회해줘"
→ get_statistics_data(org_id="101", tbl_id="DT_1B040A3",
                       start_period="2020", end_period="2023")

"서울시 인구 추세를 분석해줘"
→ analyze_trend(data, time_field="PRD_DE", value_field="DT")
```

## Development

```bash
# Clone repository
git clone https://github.com/sdh/kosis-mcp.git
cd kosis-mcp

# Install dependencies
uv sync --dev

# Run tests
uv run pytest

# Run MCP Inspector (interactive testing)
uv run fastmcp dev src/kosis_tools/mcp_server.py

# Inspect server tools
uv run fastmcp inspect src/kosis_tools/mcp_server.py
```

## Publishing to PyPI

```bash
# Build
uv build

# Publish (requires PyPI token)
uv publish
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Links

- [KOSIS 국가통계포털](https://kosis.kr/)
- [KOSIS OpenAPI 안내](https://kosis.kr/openapi/)
- [FastMCP Documentation](https://gofastmcp.com/)
- [MCP Protocol](https://modelcontextprotocol.io/)
