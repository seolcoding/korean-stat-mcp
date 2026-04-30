"""Live-KOSIS integration acceptance test for verify_statistics (US-005).

Acceptance criterion: at least 18 of 20 hand-picked claims match expectations.

This test hits the live KOSIS API and is therefore marked ``integration``. It
is skipped by default. To run::

    uv run pytest tests/integration/test_verify_statistics.py --integration

(Or set ``KOSIS_RUN_INTEGRATION=1``.)

Sample claims live in ``sample_claims.py`` so they can be inspected and
audited without running the test.
"""

from __future__ import annotations

import os

import pytest

from kosis_tools.verify import verify_statistics

from .sample_claims import SAMPLES


def _integration_enabled() -> bool:
    return os.environ.get("KOSIS_RUN_INTEGRATION") == "1"


pytestmark = pytest.mark.skipif(
    not _integration_enabled(),
    reason="Live KOSIS integration test. Set KOSIS_RUN_INTEGRATION=1 to enable.",
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sample_claims_accuracy() -> None:
    """At least 18/20 sample claims should yield the expected match outcome."""
    correct = 0
    failures: list[str] = []
    for sample in SAMPLES:
        result = await verify_statistics(
            sample.claim,
            table_id=sample.table_id,
            tolerance=0.01,
        )
        if result.match == sample.expect_match:
            correct += 1
        else:
            failures.append(
                f"{sample.claim!r}: expect_match={sample.expect_match} "
                f"got match={result.match} expected={result.expected} "
                f"actual={result.actual} confidence={result.confidence}"
            )

    msg = f"verify_statistics passed {correct}/20. Failures: {failures}"
    assert correct >= 18, msg
