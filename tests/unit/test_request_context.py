"""Per-request API key contextvar isolation tests."""

from __future__ import annotations

import asyncio

import pytest

from kosis_tools.request_context import current_api_key


def test_default_is_none():
    assert current_api_key.get() is None


def test_set_and_get():
    token = current_api_key.set("abc")
    try:
        assert current_api_key.get() == "abc"
    finally:
        current_api_key.reset(token)
    assert current_api_key.get() is None


@pytest.mark.asyncio
async def test_isolation_across_concurrent_tasks():
    """Two concurrent tasks each see only their own key — never bleed."""
    seen: dict[str, str | None] = {}

    async def worker(name: str, key: str) -> None:
        token = current_api_key.set(key)
        try:
            await asyncio.sleep(0)  # yield to the other task
            seen[name] = current_api_key.get()
        finally:
            current_api_key.reset(token)

    await asyncio.gather(worker("a", "key-a"), worker("b", "key-b"))
    assert seen == {"a": "key-a", "b": "key-b"}
    assert current_api_key.get() is None
