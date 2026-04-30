"""Unit tests for verify_statistics (US-005).

These tests mock both ``StatisticsSearch`` and ``StatisticsData`` so they
never hit the live KOSIS API. End-to-end verification against real KOSIS
data lives in ``tests/integration/test_verify_statistics.py``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from kosis_tools.verify import (
    VerifyResult,
    _build_source_url,
    _parse_number,
    _parse_period,
    _parse_region,
    _to_float,
    parse_claim,
    verify_statistics,
)

# ---------------------------------------------------------------------------
# Pure parsing helpers
# ---------------------------------------------------------------------------


class TestParseNumber:
    def test_plain_integer(self) -> None:
        v, _ = _parse_number("9400000")
        assert v == 9_400_000

    def test_korean_magnitude_eok(self) -> None:
        v, _ = _parse_number("1750조원")
        assert v == 1_750 * 1_000_000_000_000

    def test_english_million(self) -> None:
        v, _ = _parse_number("9.4 million people")
        assert v == 9_400_000

    def test_english_M_suffix(self) -> None:
        v, _ = _parse_number("9.4M명")
        assert v == 9_400_000

    def test_comma_separated(self) -> None:
        v, _ = _parse_number("population was 9,411,453")
        assert v == 9_411_453

    def test_no_number(self) -> None:
        v, suffix = _parse_number("hello world")
        assert v is None
        assert suffix is None


class TestParsePeriod:
    def test_bare_year(self) -> None:
        assert _parse_period("2023년 인구는") == "2023"

    def test_year_and_month(self) -> None:
        assert _parse_period("2024년 3월") == "202403"

    def test_korean_quarter(self) -> None:
        assert _parse_period("2024년 1분기 GDP") == "2024Q1"

    def test_english_quarter(self) -> None:
        assert _parse_period("2024Q1") == "2024Q1"

    def test_no_period(self) -> None:
        assert _parse_period("the population is huge") is None


class TestParseRegion:
    def test_korean_short(self) -> None:
        assert _parse_region("서울 인구") == "서울특별시"

    def test_english_alias(self) -> None:
        assert _parse_region("Seoul population") == "서울특별시"

    def test_no_region(self) -> None:
        assert _parse_region("just a number") is None


class TestParseClaim:
    def test_korean_full_claim(self) -> None:
        out = parse_claim("2023년 서울 인구는 9.4M명")
        assert out["value"] == 9_400_000
        assert out["region"] == "서울특별시"
        assert out["period"] == "2023"
        assert out["metric"] == "인구"
        assert out["unit"] == "명"

    def test_english_full_claim(self) -> None:
        out = parse_claim("Seoul population in 2023 was 9.4 million")
        assert out["value"] == 9_400_000
        assert out["region"] == "서울특별시"
        assert out["period"] == "2023"
        assert out["metric"] == "population"

    def test_quarterly_gdp(self) -> None:
        out = parse_claim("2024년 1분기 GDP 1750조원")
        assert out["value"] == 1_750_000_000_000_000
        assert out["period"] == "2024Q1"
        assert out["metric"] == "gdp"

    def test_empty_claim(self) -> None:
        out = parse_claim("")
        assert out["value"] is None

    def test_unparseable_claim(self) -> None:
        out = parse_claim("just some words")
        assert out["value"] is None


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------


class TestToFloat:
    def test_normal(self) -> None:
        assert _to_float("9411453") == 9_411_453.0

    def test_with_commas(self) -> None:
        assert _to_float("9,411,453") == 9_411_453.0

    def test_dash_sentinel(self) -> None:
        assert _to_float("-") is None

    def test_star_sentinel(self) -> None:
        assert _to_float("*") is None

    def test_empty(self) -> None:
        assert _to_float("") is None

    def test_none(self) -> None:
        assert _to_float(None) is None


class TestBuildSourceUrl:
    def test_full(self) -> None:
        url = _build_source_url("101", "DT_1B040A3")
        assert "orgId=101" in url
        assert "tblId=DT_1B040A3" in url
        assert url.startswith("https://kosis.kr/statHtml/statHtml.do")

    def test_no_table(self) -> None:
        assert _build_source_url("101", None) is None

    def test_no_org(self) -> None:
        url = _build_source_url(None, "DT_X")
        assert url is not None and "tblId=DT_X" in url


# ---------------------------------------------------------------------------
# verify_statistics — full flow with mocked clients
# ---------------------------------------------------------------------------


def _mock_clients(
    records: list[dict[str, Any]], *, tbl_id: str = "DT_1B040A3", org_id: str = "101"
):
    search = MagicMock()
    search.search.return_value = [
        {
            "TBL_ID": tbl_id,
            "TBL_NM": "행정구역별 인구수",
            "ORG_ID": org_id,
            "ORG_NM": "통계청",
        }
    ]
    search.search_by_table_id.return_value = {
        "TBL_ID": tbl_id,
        "TBL_NM": "행정구역별 인구수",
        "ORG_ID": org_id,
    }
    data = MagicMock()
    data.get_data.return_value = records
    return search, data


@pytest.mark.asyncio
class TestVerifyStatistics:
    async def test_match_within_tolerance(self) -> None:
        """Claim within 1% of source -> match=True, confidence='high'."""
        records = [
            {
                "PRD_DE": "2023",
                "C1_NM": "서울특별시",
                "DT": "9411453",
                "ITM_NM": "총인구",
                "UNIT_NM": "명",
            },
        ]
        search, data = _mock_clients(records)
        result = await verify_statistics(
            "2023년 서울 인구는 9.4M명",
            tolerance=0.01,
            _search=search,
            _data=data,
        )
        assert isinstance(result, VerifyResult)
        assert result.match is True
        assert result.expected == 9_411_453.0
        assert result.actual == 9_400_000.0
        assert result.confidence == "high"
        assert result.source_url and "DT_1B040A3" in result.source_url

    async def test_mismatch_outside_tolerance(self) -> None:
        records = [
            {"PRD_DE": "2023", "C1_NM": "서울특별시", "DT": "9411453"},
        ]
        search, data = _mock_clients(records)
        result = await verify_statistics(
            "2023년 서울 인구는 8M명",
            tolerance=0.01,
            _search=search,
            _data=data,
        )
        assert result.match is False
        assert result.diff_pct is not None and result.diff_pct < 0

    async def test_unparseable_claim(self) -> None:
        search, data = _mock_clients([])
        result = await verify_statistics(
            "no number here",
            _search=search,
            _data=data,
        )
        assert result.confidence == "unverifiable"
        assert result.actual is None
        assert result.expected is None

    async def test_no_metric_no_table_id(self) -> None:
        """Number without metric and without table_id -> unverifiable."""
        search, data = _mock_clients([])
        result = await verify_statistics(
            "2023년에 9400000였다",
            _search=search,
            _data=data,
        )
        assert result.confidence == "unverifiable"
        assert (
            "table_id" in result.explanation.lower()
            or "metric" in result.explanation.lower()
        )

    async def test_table_id_explicit_skips_search(self) -> None:
        records = [
            {"PRD_DE": "2023", "C1_NM": "전국", "DT": "51823154"},
        ]
        search, data = _mock_clients(records)
        result = await verify_statistics(
            "2023년 인구는 51823154명",
            table_id="DT_1B040A3",
            tolerance=0.01,
            _search=search,
            _data=data,
        )
        # We don't need search.search to fire when table_id is given.
        search.search.assert_not_called()
        assert result.match is True

    async def test_org_prefixed_table_id(self) -> None:
        records = [{"PRD_DE": "2023", "C1_NM": "전국", "DT": "100"}]
        search, data = _mock_clients(records)
        result = await verify_statistics(
            "2023년 값은 100",
            table_id="101:DT_FOO",
            tolerance=0.01,
            _search=search,
            _data=data,
        )
        # search_by_table_id shouldn't be called when org is prefixed.
        search.search_by_table_id.assert_not_called()
        assert result.table_id == "DT_FOO"
        assert "orgId=101" in (result.source_url or "")

    async def test_dash_sentinel_in_dt(self) -> None:
        records = [{"PRD_DE": "2023", "C1_NM": "서울특별시", "DT": "-"}]
        search, data = _mock_clients(records)
        result = await verify_statistics(
            "2023년 서울 인구는 9.4M명",
            _search=search,
            _data=data,
        )
        assert result.confidence == "unverifiable"
        assert result.expected is None

    async def test_no_records_returned(self) -> None:
        search, data = _mock_clients([])
        result = await verify_statistics(
            "2023년 서울 인구는 9.4M명",
            _search=search,
            _data=data,
        )
        assert result.confidence == "unverifiable"
        assert result.expected is None
