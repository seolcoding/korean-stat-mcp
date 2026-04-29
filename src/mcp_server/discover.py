"""Tool discovery and execution escape hatch.

`discover_tools()` lists every tool registered on the FastMCP server,
flagging which subset is part of the curated V1_EXPOSED public surface.

`execute_tool(name, args)` invokes any registered tool by name — including
internal ones that are hidden from the default LLM tool list. This gives
power users (and other agents) a single entry point to the full surface
without the harness having to advertise 24+ tools.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

from .exposed_tools import V1_EXPOSED, V1_EXPOSED_NAMES

# Snapshot of every registered tool taken BEFORE the public surface is pruned.
# Populated by mcp_server.server._snapshot_tool_registry() at import time.
_FULL_REGISTRY: dict[str, Any] = {}


def _register_full_registry(registry: dict[str, Any]) -> None:
    """Record the pre-prune tool registry. Called once from server.py."""
    _FULL_REGISTRY.clear()
    _FULL_REGISTRY.update(registry)


def _get_mcp():
    """Lazy import of the FastMCP server to avoid circular imports."""
    from . import server as _server  # noqa: PLC0415

    return _server.mcp


def _all_tools() -> dict[str, Any]:
    """Return {name: FunctionTool} for every tool that was ever registered.

    Uses the pre-prune snapshot so internal (hidden) tools remain reachable.
    Falls back to a live mcp.get_tools() if the snapshot is empty (e.g. tests
    that import discover.py before server.py).
    """
    if _FULL_REGISTRY:
        return dict(_FULL_REGISTRY)
    mcp = _get_mcp()
    coro = mcp.get_tools()
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    return {}  # pragma: no cover - inside running loop, no snapshot


def _short_desc(tool: Any) -> str:
    """Pull a one-line description from a FunctionTool object."""
    desc = getattr(tool, "description", None) or ""
    if not desc:
        fn = getattr(tool, "fn", None)
        if fn and fn.__doc__:
            desc = fn.__doc__
    first = (desc or "").strip().splitlines()
    return first[0].strip() if first else ""


def discover_tools() -> dict:
    """List all internal tool names with one-line descriptions and exposure status.

    Returns:
        dict with keys:
            exposed:        list of curated V1 tools (name, layer, purpose_ko, purpose_en)
            internal:       list of registered tools NOT in V1 (name, exposed=False, description)
            total:          total number of registered tools
            exposed_count:  len(V1_EXPOSED)
    """
    exposed = [
        {
            "name": t.name,
            "layer": t.layer,
            "purpose_ko": t.purpose_ko,
            "purpose_en": t.purpose_en,
        }
        for t in V1_EXPOSED
    ]

    try:
        registered = _all_tools()
    except Exception:  # pragma: no cover - defensive
        registered = {}

    internal = [
        {
            "name": name,
            "exposed": False,
            "description": _short_desc(tool),
        }
        for name, tool in sorted(registered.items())
        if name not in V1_EXPOSED_NAMES
    ]

    return {
        "exposed": exposed,
        "internal": internal,
        "total": len(registered) + sum(1 for t in V1_EXPOSED if t.name not in registered),
        "exposed_count": len(V1_EXPOSED),
    }


def execute_tool(name: str, args: dict | None = None) -> dict:
    """Invoke any registered tool by name (escape hatch for power users).

    Args:
        name: Registered MCP tool name (exposed or internal).
        args: Keyword arguments to pass to the tool. Validated against the
              underlying function signature; unknown keys raise TypeError.

    Returns:
        {"tool": name, "result": <tool return value>} on success.
        {"tool": name, "error": "<message>"} on lookup / invocation failure.
    """
    args = args or {}

    try:
        registered = _all_tools()
    except Exception as exc:  # pragma: no cover - defensive
        return {"tool": name, "error": f"failed to list tools: {exc}"}

    tool = registered.get(name)
    if tool is None:
        available = sorted(registered.keys())
        return {
            "tool": name,
            "error": f"unknown tool: {name!r}",
            "available": available,
        }

    fn = getattr(tool, "fn", None)
    if fn is None:
        return {"tool": name, "error": f"tool {name!r} has no callable .fn"}

    # Validate arg names against the signature for an early, clear error.
    try:
        sig = inspect.signature(fn)
        sig.bind_partial(**args)
    except TypeError as exc:
        return {"tool": name, "error": f"invalid arguments: {exc}"}

    try:
        result = fn(**args)
        if inspect.iscoroutine(result):
            result = asyncio.run(result)
    except Exception as exc:
        return {"tool": name, "error": f"{type(exc).__name__}: {exc}"}

    return {"tool": name, "result": result}
