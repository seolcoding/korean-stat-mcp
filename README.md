# KOSIS MCP Server

<p align="center">
  <strong>Korean Statistical Data at Your Fingertips</strong><br>
  AI agents can now search, analyze, and visualize KOSIS statistics through MCP
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#production-server">Production Server</a> •
  <a href="#usage">Usage</a> •
  <a href="docs/USER_GUIDE.md">User Guide</a> •
  <a href="#contributing">Contributing</a>
</p>

---

## 🚀 Production Server (Now Live!)

**The KOSIS MCP Server is currently running in production:**

```
🌐 URL: https://schedule-fell-quizzes-comments.trycloudflare.com
✅ Status: Operational
📊 Database: 252,890 statistical tables with embeddings
🔧 Server: wai-3090ti (Ubuntu 24.04)
```

**Connect to the production server:**

```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "kosis": {
      "url": "https://schedule-fell-quizzes-comments.trycloudflare.com",
      "transport": "streamable-http"
    }
  }
}
```

> **Note**: This is a temporary Cloudflare Tunnel URL. A permanent domain will be configured in Phase 5.

---

## What is KOSIS MCP Server?

**KOSIS MCP Server** is a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that enables AI agents like Claude to directly access and analyze Korean statistical data from [KOSIS (Korean Statistical Information Service)](https://kosis.kr/).

### Key Benefits

- **98% Token Savings**: Server-side data processing with chunked responses
- **Natural Language Search**: Hybrid search combining vector similarity and BM25
- **Rich Visualizations**: Generate interactive Altair charts with URL links
- **Comprehensive Data**: Access to 250,000+ statistical tables

## Features

### 🔍 DISCOVER - Smart Data Search

- **Hybrid Search**: Vector embeddings + BM25 full-text search with RRF ranking
- **Category Browsing**: Navigate by organization or theme
- **Metadata Access**: Explore table structures and classification values

### 📥 FETCH - Efficient Data Retrieval

- **Chunked Responses**: Large datasets split into manageable chunks
- **Server-Side Storage**: Raw data stays on server, summaries to LLM
- **Filtering & Aggregation**: Query data without loading it all

### 📊 PRESENT - Analysis & Visualization

- **Modular Executors**: Specialized tools for visualization, analysis, tables, reports
- **Interactive Charts**: Altair-based visualizations served via URL
- **Composite Reports**: Combine charts, analysis, and tables into HTML reports

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- KOSIS API Key ([Get one here](https://kosis.kr/openapi/))
- Docker & Docker Compose (recommended)

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/sdh/kosis-mcp.git
cd kosis-mcp

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start services
docker compose up -d

# Verify
curl http://localhost:8000/health
```

### Option 2: Local Development

```bash
# Clone and setup
git clone https://github.com/sdh/kosis-mcp.git
cd kosis-mcp

# Install dependencies
uv sync

# Set environment variables
export KOSIS_API_KEY="your-api-key"

# Run MCP server (stdio mode)
uv run python -m mcp_server
```

## Claude Desktop Integration

### Option 1: Production Server (Recommended)

Connect to the live production server:

```json
{
  "mcpServers": {
    "kosis": {
      "url": "https://schedule-fell-quizzes-comments.trycloudflare.com",
      "transport": "streamable-http"
    }
  }
}
```

### Option 2: Local Docker

Run your own local server:

```json
{
  "mcpServers": {
    "kosis": {
      "url": "http://localhost:8001",
      "transport": "streamable-http"
    }
  }
}
```

### Option 3: stdio Mode (Advanced)

For development only:

```json
{
  "mcpServers": {
    "kosis": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/kosis-mcp", "python", "-m", "mcp_server"],
      "env": {
        "KOSIS_API_KEY": "your-api-key"
      }
    }
  }
}
```

## Usage

### Example: Population Trend Analysis

```text
User: "Show me Korea's population trend over the last 5 years"

Claude uses:
1. search_statistics("인구") → finds relevant tables
2. get_statistics_data(org_id="101", tbl_id="DT_1B040A3") → retrieves data
3. execute_visualization(code="...", data_id="...") → creates chart
   → Returns: http://localhost:8000/artifacts/charts/population_trend.html
```

### Available MCP Tools

| Layer | Tool | Description |
|-------|------|-------------|
| **DISCOVER** | `search_statistics` | Keyword-based table search |
| | `search_tables_hybrid` | Semantic + keyword hybrid search |
| | `get_table_metadata` | Get table structure and classifications |
| **FETCH** | `get_statistics_data` | Retrieve statistical data |
| | `filter_statistics` | Filter stored data |
| | `aggregate_statistics` | Aggregate by groups |
| **EXECUTE** | `execute_code` | Run Python code server-side |
| | `execute_visualization` | Generate Altair charts |
| | `execute_analysis` | Perform statistical analysis |
| | `execute_report` | Create composite HTML reports |

See [User Guide](docs/USER_GUIDE.md) for detailed tool documentation and examples.

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `KOSIS_API_KEY` | Yes | KOSIS OpenAPI key |
| `DATABASE_URL` | For hybrid search | PostgreSQL connection string |
| `OPENAI_API_KEY` | For hybrid search | For generating embeddings |
| `KOSIS_ARTIFACTS_DIR` | No | Artifact storage path (default: `/tmp/kosis_artifacts`) |
| `KOSIS_BASE_URL` | No | Base URL for artifact links (default: `http://localhost:8000`) |

See [.env.example](.env.example) for all configuration options.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    MCP Client (Claude)                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ MCP Protocol
┌──────────────────────────▼──────────────────────────────────┐
│                   KOSIS MCP Server                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Layer 3: EXECUTE (Code Execution & Visualization)     │ │
│  │  • execute_code • execute_visualization • execute_report│ │
│  ├────────────────────────────────────────────────────────┤ │
│  │  Layer 2: FETCH (Data Operations)                      │ │
│  │  • get_statistics_data • filter • aggregate            │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │  Layer 1: DISCOVER (Search & Metadata)                 │ │
│  │  • search_statistics • hybrid_search • metadata        │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────┬───────────────────────┬───────────────────┘
                  │                       │
       ┌──────────▼──────────┐   ┌────────▼────────┐
       │  PostgreSQL         │   │  KOSIS OpenAPI  │
       │  + pgvector         │   │  (kosis.kr)     │
       └─────────────────────┘   └─────────────────┘
```

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests
uv run pytest tests/ -v

# Run MCP Inspector for debugging
uv run fastmcp dev src/mcp_server/server.py

# Type checking
uv run mypy src/
```

### Project Structure

```
kosis-mcp/
├── src/
│   ├── mcp_server/          # MCP server entry points
│   │   ├── server.py        # Tool definitions
│   │   └── app.py           # HTTP mode ASGI app
│   └── kosis_tools/         # Core functionality
│       ├── search.py        # KOSIS API search
│       ├── data.py          # Data retrieval
│       ├── visualize.py     # Altair visualization
│       ├── code_executor.py # Sandboxed code execution
│       └── executors/       # Modular executors
├── data/                    # Metadata cache
├── docs/                    # Documentation
├── tests/                   # Test suite
├── docker-compose.yml       # Docker setup
└── pyproject.toml           # Project config
```

## Documentation

- [User Guide](docs/USER_GUIDE.md) - Detailed usage instructions
- [Architecture Design](docs/ARCHITECTURE_DESIGN.md) - System architecture
- [KOSIS API Reference](docs/KOSIS_API_REFERENCE.md) - API documentation
- [Deployment Guide](docs/DEPLOYMENT.md) - Production deployment
- [Hybrid Search Design](docs/HYBRID_SEARCH.md) - Search implementation

## Contributing

Contributions are welcome! Please see our contributing guidelines (coming soon).

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [KOSIS (Korean Statistical Information Service)](https://kosis.kr/) for providing the OpenAPI
- [FastMCP](https://gofastmcp.com/) for the MCP server framework
- [Altair](https://altair-viz.github.io/) for declarative visualization

## Links

- [KOSIS Portal](https://kosis.kr/)
- [KOSIS OpenAPI Guide](https://kosis.kr/openapi/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastMCP Documentation](https://gofastmcp.com/)
