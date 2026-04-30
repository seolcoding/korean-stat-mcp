"""Per-request API key context for the HTTP server.

The hosted MCP server lets users supply their KOSIS OpenAPI key via a
URL query parameter on each call. The ApiKeyMiddleware in mcp_server stores
the per-request key here so that load_config() can read it without changing
every tool's signature.

stdio mode never sets this contextvar; load_config() falls back to env.
"""

from __future__ import annotations

from contextvars import ContextVar

current_api_key: ContextVar[str | None] = ContextVar("current_api_key", default=None)
