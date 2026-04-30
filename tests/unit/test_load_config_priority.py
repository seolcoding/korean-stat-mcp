"""load_config() priority: contextvar > env > ValueError."""

from __future__ import annotations

import pytest

from kosis_tools.config import load_config
from kosis_tools.request_context import current_api_key


def test_contextvar_wins_over_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KOSIS_API_KEY", "from-env")
    token = current_api_key.set("from-contextvar")
    try:
        config = load_config()
        assert config.api_key == "from-contextvar"
    finally:
        current_api_key.reset(token)


def test_env_used_when_contextvar_unset(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("KOSIS_API_KEY", "from-env")
    assert current_api_key.get() is None
    config = load_config()
    assert config.api_key == "from-env"


def test_raises_when_neither_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("KOSIS_API_KEY", raising=False)
    assert current_api_key.get() is None
    with pytest.raises(ValueError, match="KOSIS_API_KEY"):
        load_config()


def test_empty_contextvar_falls_back_to_env(monkeypatch: pytest.MonkeyPatch):
    """Empty string contextvar (treated as missing) defers to env."""
    monkeypatch.setenv("KOSIS_API_KEY", "from-env")
    token = current_api_key.set("")
    try:
        config = load_config()
        assert config.api_key == "from-env"
    finally:
        current_api_key.reset(token)
