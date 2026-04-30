"""Regression guard for publish-facing release metadata."""

from __future__ import annotations

from scripts.validation.check_release_readiness import run_checks


def test_release_readiness_public_surface_has_no_known_blockers() -> None:
    assert run_checks() == []
