"""Unit tests for the V1_EXPOSED tool allow-list (US-003)."""

from __future__ import annotations

import pytest

from mcp_server.exposed_tools import V1_EXPOSED, V1_EXPOSED_NAMES, ExposedTool


# ---------------------------------------------------------------------------
# V1_EXPOSED structure
# ---------------------------------------------------------------------------


def test_v1_exposed_count() -> None:
    """V1 surface ships with 12 core tools + 4 key-indicator tools = 16."""
    assert len(V1_EXPOSED) == 16
    assert len(V1_EXPOSED_NAMES) == 16


def test_v1_exposed_entries_fully_populated() -> None:
    """Every entry must have all four fields filled in."""
    for tool in V1_EXPOSED:
        assert isinstance(tool, ExposedTool)
        assert tool.name and isinstance(tool.name, str)
        assert tool.layer in {"DISCOVER", "FETCH", "VERIFY", "DATA", "META"}
        assert tool.purpose_ko and isinstance(tool.purpose_ko, str)
        assert tool.purpose_en and isinstance(tool.purpose_en, str)


def test_v1_exposed_names_are_unique() -> None:
    names = [t.name for t in V1_EXPOSED]
    assert len(names) == len(set(names))


def test_search_tables_hybrid_not_exposed() -> None:
    """Regression guard: removed in US-001b, must stay out of V1."""
    assert "search_tables_hybrid" not in V1_EXPOSED_NAMES


def test_core_tools_present() -> None:
    """Spot-check that the curated essentials are listed."""
    expected = {
        "search_statistics",
        "get_statistics_data",
        "discover_tools",
        "execute_tool",
    }
    assert expected.issubset(V1_EXPOSED_NAMES)
    assert "execute_analysis" not in V1_EXPOSED_NAMES
    assert "execute_table" not in V1_EXPOSED_NAMES
    assert "execute_visualization" not in V1_EXPOSED_NAMES
    assert "execute_report" not in V1_EXPOSED_NAMES


# ---------------------------------------------------------------------------
# discover_tools / execute_tool behaviour
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def loaded_server():
    """Importing server.py registers tools and runs the prune step."""
    from mcp_server import server  # noqa: F401

    return server


def test_discover_tools_shape(loaded_server) -> None:
    from mcp_server.discover import discover_tools

    result = discover_tools()
    assert set(result.keys()) == {"exposed", "internal", "total", "exposed_count"}
    assert result["exposed_count"] == 16
    assert result["total"] >= 16
    # Each exposed entry carries name+layer+purpose fields
    for entry in result["exposed"]:
        assert {"name", "layer", "purpose_ko", "purpose_en"}.issubset(entry.keys())
    # Internal entries are flagged false and carry a description string
    for entry in result["internal"]:
        assert entry["exposed"] is False
        assert "description" in entry


def test_discover_tools_internal_excludes_exposed(loaded_server) -> None:
    from mcp_server.discover import discover_tools

    result = discover_tools()
    internal_names = {e["name"] for e in result["internal"]}
    assert internal_names.isdisjoint(V1_EXPOSED_NAMES)


def test_execute_tool_unknown_name(loaded_server) -> None:
    from mcp_server.discover import execute_tool

    result = execute_tool("does_not_exist", {})
    assert "error" in result
    assert "unknown tool" in result["error"]
    assert "available" in result


def test_execute_tool_signature_validation(loaded_server) -> None:
    """Unknown kwargs surface as a clean error, not a raw exception."""
    from mcp_server.discover import execute_tool

    result = execute_tool("search_statistics", {"not_a_real_param": 1})
    assert "error" in result
    assert "invalid arguments" in result["error"]


def test_execute_tool_signature_lookup(loaded_server) -> None:
    """search_statistics must be reachable via execute_tool (signature OK)."""
    import inspect

    from mcp_server.discover import _all_tools

    tools = _all_tools()
    assert "search_statistics" in tools
    fn = tools["search_statistics"].fn
    sig = inspect.signature(fn)
    assert "keyword" in sig.parameters
