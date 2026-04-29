"""verify_statistics — cross-check LLM numeric claims against KOSIS source data.

US-005: This is the differentiator tool inspired by korean-law-mcp's
``verify_citations``. It accepts a free-form numeric claim (Korean or English),
parses out the numeric value plus contextual hints (year, region, metric),
fetches the matching KOSIS table, and returns a structured pass/fail report
with a relative-tolerance comparison.

Example:
    >>> result = await verify_statistics("2023년 서울 인구는 9.4M명")
    >>> result.match
    True
    >>> result.diff_pct
    0.0012  # claimed 9.4M vs actual 9.41M

The tool deliberately stays conservative: when the claim cannot be parsed
cleanly or no matching cell is found, it returns ``confidence='unverifiable'``
and explains what the caller should provide (typically ``table_id``).
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Literal

from .data import StatisticsData
from .search import StatisticsSearch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


Confidence = Literal["high", "medium", "low", "unverifiable"]


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of a verify_statistics call.

    Attributes:
        match: True iff |actual - expected| / expected <= tolerance.
        expected: KOSIS-sourced value (None when unverifiable).
        actual: User/LLM-claimed value (None when claim couldn't be parsed).
        diff_pct: Signed relative diff ``(actual - expected) / expected``.
        tolerance: Tolerance used for the match (relative).
        table_id: KOSIS table id used as the source.
        source_url: Direct KOSIS HTML link to the table.
        confidence: One of high/medium/low/unverifiable. See ``_rank_confidence``.
        explanation: Bilingual KO+EN human-readable summary.
    """

    match: bool
    expected: float | None
    actual: float | None
    diff_pct: float | None
    tolerance: float
    table_id: str | None
    source_url: str | None
    confidence: Confidence
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Claim parsing
# ---------------------------------------------------------------------------


# Korean magnitude suffixes -> multiplier (in raw units).
_KOREAN_MAGNITUDES: dict[str, float] = {
    "조": 1_000_000_000_000,
    "억": 100_000_000,
    "만": 10_000,
    "천": 1_000,
    "백": 100,
}

# English/SI magnitude suffixes (case-insensitive).
_EN_MAGNITUDES: dict[str, float] = {
    "trillion": 1_000_000_000_000,
    "t": 1_000_000_000_000,
    "billion": 1_000_000_000,
    "b": 1_000_000_000,
    "million": 1_000_000,
    "m": 1_000_000,
    "thousand": 1_000,
    "k": 1_000,
}

# Recognized region tokens. KOSIS often returns "서울특별시"; we also accept
# the colloquial "서울" / "Seoul" forms.
_REGION_ALIASES: dict[str, str] = {
    "서울": "서울특별시",
    "부산": "부산광역시",
    "대구": "대구광역시",
    "인천": "인천광역시",
    "광주": "광주광역시",
    "대전": "대전광역시",
    "울산": "울산광역시",
    "세종": "세종특별자치시",
    "경기": "경기도",
    "강원": "강원특별자치도",
    "충북": "충청북도",
    "충남": "충청남도",
    "전북": "전북특별자치도",
    "전남": "전라남도",
    "경북": "경상북도",
    "경남": "경상남도",
    "제주": "제주특별자치도",
    "전국": "전국",
    "seoul": "서울특별시",
    "busan": "부산광역시",
    "korea": "전국",
}

# Lightweight metric vocabulary. Used both as a routing hint for ``search``
# and as a confidence signal — claims that mention nothing in this list are
# downgraded one rung.
_METRIC_KEYWORDS: tuple[str, ...] = (
    "인구",
    "population",
    "gdp",
    "실업률",
    "unemployment",
    "물가",
    "cpi",
    "출생",
    "birth",
    "사망",
    "death",
    "고용",
    "employment",
    "소득",
    "income",
)


def _parse_number(text: str) -> tuple[float | None, str | None]:
    """Pull the first numeric token out of ``text`` and apply any magnitude.

    Returns ``(value, magnitude_token)``. ``value`` is in raw units. Both
    Korean (``조``, ``억``, ``만``) and English (``M``, ``billion``) suffixes
    are honoured. Returns ``(None, None)`` when no number is found.
    """
    # Match: optional leading sign, digits with optional commas/decimal point,
    # then an optional magnitude token (Korean char OR English word/letter).
    pattern = re.compile(
        r"(-?\d{1,3}(?:,\d{3})+(?:\.\d+)?|-?\d+(?:\.\d+)?)"
        r"\s*"
        r"(조|억|만|천|백|trillion|billion|million|thousand|[KMBTkmbt])?",
    )
    match = pattern.search(text)
    if match is None:
        return None, None

    raw_num = match.group(1).replace(",", "")
    try:
        value = float(raw_num)
    except ValueError:
        return None, None

    suffix = match.group(2)
    if suffix:
        s_lower = suffix.lower()
        mult = _KOREAN_MAGNITUDES.get(suffix) or _EN_MAGNITUDES.get(s_lower)
        if mult is not None:
            value *= mult
    return value, suffix


def _parse_period(text: str) -> str | None:
    """Extract a period token. Recognises:

    - 4-digit year: ``2023`` / ``2023년`` -> ``"2023"``
    - Quarter: ``2024 1분기`` / ``2024Q1`` -> ``"2024Q1"``
    - Month: ``2024년 3월`` -> ``"202403"``
    """
    # Quarter — Korean
    m = re.search(r"(\d{4})\s*년?\s*([1-4])\s*분기", text)
    if m:
        return f"{m.group(1)}Q{m.group(2)}"
    # Quarter — English / compact
    m = re.search(r"(\d{4})\s*[Qq]\s*([1-4])", text)
    if m:
        return f"{m.group(1)}Q{m.group(2)}"
    # Year + month
    m = re.search(r"(\d{4})\s*년?\s*(\d{1,2})\s*월", text)
    if m:
        return f"{m.group(1)}{int(m.group(2)):02d}"
    # Bare year (must be 4 digits, plausible range)
    m = re.search(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", text)
    if m:
        return m.group(1)
    return None


def _parse_region(text: str) -> str | None:
    """Find the first region alias in the claim. Returns canonical KOSIS name."""
    lowered = text.lower()
    # Try Korean tokens first (often unambiguous).
    for alias, canonical in _REGION_ALIASES.items():
        if not alias.isascii():
            if alias in text:
                return canonical
    # Then English tokens (require word boundary to avoid false hits).
    for alias, canonical in _REGION_ALIASES.items():
        if alias.isascii():
            if re.search(rf"\b{re.escape(alias)}\b", lowered):
                return canonical
    return None


def _parse_metric(text: str) -> str | None:
    """Find the first metric keyword present in the claim."""
    lowered = text.lower()
    for kw in _METRIC_KEYWORDS:
        if kw in lowered:
            return kw
    return None


def parse_claim(claim: str) -> dict[str, Any]:
    """Extract numeric value, unit, region, period, metric from a claim.

    The parser is intentionally lenient — see module docstring. Returns a dict
    with keys ``value``, ``unit``, ``region``, ``period``, ``metric``. Any field
    that couldn't be determined is ``None`` (callers must handle this).

    Examples (informally):
        ``"2023년 서울 인구는 9.4M명"``
            -> ``{value: 9_400_000, unit: '명', region: '서울특별시',
                  period: '2023', metric: '인구'}``
        ``"Seoul population in 2023 was 9.4 million"``
            -> equivalent dict (region resolved via 'seoul' alias).
    """
    if not claim or not claim.strip():
        return {"value": None, "unit": None, "region": None, "period": None, "metric": None}

    period = _parse_period(claim)
    region = _parse_region(claim)
    metric = _parse_metric(claim)

    # Parse number AFTER stripping the period so we don't accidentally grab
    # the year (e.g. ``"2023년 ... 9.4M명"`` should yield 9_400_000, not 2023).
    number_text = claim
    if period is not None:
        # Remove the literal period token's leading-year portion. Quarterly /
        # monthly periods all start with the 4-digit year; remove just the
        # year so we still see any embedded "1분기"/"3월" tokens.
        year = period[:4]
        # \b doesn't fire next to CJK characters; use a manual boundary that
        # allows year[0] to be at-start or preceded by whitespace, and the
        # trailing digit to be followed by non-digit.
        number_text = re.sub(rf"(?<!\d){year}(?!\d)\s*년?", "", number_text)
        # Also strip "N분기" / "N월" leftovers — they contain digits that
        # would otherwise be picked up.
        number_text = re.sub(r"[1-4]\s*분기", "", number_text)
        number_text = re.sub(r"\d{1,2}\s*월", "", number_text)
    value, _suffix = _parse_number(number_text)

    # Unit: grab the trailing token after the number, if any. Best-effort.
    unit: str | None = None
    unit_match = re.search(
        r"\d[\d,\.]*\s*(?:조|억|만|천|백|trillion|billion|million|thousand|[KMBTkmbt])?\s*"
        r"(명|원|%|퍼센트|percent|건|개|kg|톤|million|billion)",
        claim,
        flags=re.IGNORECASE,
    )
    if unit_match:
        unit = unit_match.group(1)

    return {
        "value": value,
        "unit": unit,
        "region": region,
        "period": period,
        "metric": metric,
    }


# ---------------------------------------------------------------------------
# KOSIS lookup helpers
# ---------------------------------------------------------------------------


def _build_source_url(org_id: str | None, tbl_id: str | None) -> str | None:
    """Build the canonical KOSIS direct-link URL for a table.

    Format mirrors the existing convention used elsewhere in this codebase
    (see ``src/kosis_tools/config.py`` ``STAT_HTML_CONTENT``).
    """
    if not tbl_id:
        return None
    if not org_id:
        return f"https://kosis.kr/statHtml/statHtml.do?tblId={tbl_id}"
    return f"https://kosis.kr/statHtml/statHtml.do?orgId={org_id}&tblId={tbl_id}"


def _to_float(raw: Any) -> float | None:
    """Parse a KOSIS ``DT`` field into a float.

    ``DT`` is *always* a string in the KOSIS response and may carry sentinel
    placeholders like ``"-"`` (no data) or ``"*"`` (suppressed). Returns
    ``None`` for any unparseable value.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s or s in {"-", "*", "...", "x", "X"}:
        return None
    s = s.replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def _period_to_kosis_dates(period: str | None, prd_se: str = "Y") -> tuple[str, str, str]:
    """Map a parsed period token to ``(start, end, prd_se)`` for ``StatisticsData``.

    - ``"2023"`` -> ``("2023", "2023", "Y")``
    - ``"202403"`` (year+month) -> ``("202403", "202403", "M")``
    - ``"2024Q1"`` -> ``("202401", "202401", "Q")``
    - ``None`` -> last 5 years yearly window (best-effort default).
    """
    if period is None:
        # Best-effort default — caller already lacks a year, so just sweep recent.
        return "2019", "2024", "Y"
    if period.endswith(tuple(f"Q{i}" for i in range(1, 5))):
        year, q = period.split("Q")
        return f"{year}{int(q):02d}", f"{year}{int(q):02d}", "Q"
    if len(period) == 6 and period.isdigit():
        return period, period, "M"
    if len(period) == 4 and period.isdigit():
        return period, period, "Y"
    return period, period, prd_se


def _select_matching_record(
    records: list[dict[str, Any]],
    parsed: dict[str, Any],
) -> dict[str, Any] | None:
    """Pick the record best matching the parsed claim hints.

    Prefer records where ``C1_NM`` contains the region; fall back to the first
    record with a parseable ``DT``. Returns ``None`` if no usable record found.
    """
    if not records:
        return None

    region = parsed.get("region")
    period = parsed.get("period")

    def matches(rec: dict[str, Any]) -> int:
        score = 0
        if region:
            for k in ("C1_NM", "C2_NM"):
                v = rec.get(k)
                if isinstance(v, str) and (region in v or v in region):
                    score += 2
                    break
        if period:
            prd = str(rec.get("PRD_DE", ""))
            if period.startswith(prd) or prd.startswith(period[:4]):
                score += 1
        if _to_float(rec.get("DT")) is not None:
            score += 1
        return score

    scored = sorted(records, key=matches, reverse=True)
    best = scored[0]
    if matches(best) == 0:
        # Nothing matched any hint — fall back to first parseable DT only.
        for rec in records:
            if _to_float(rec.get("DT")) is not None:
                return rec
        return None
    return best


def _rank_confidence(parsed: dict[str, Any], match: bool, has_region_match: bool) -> Confidence:
    """Decide a confidence label.

    - ``high``: claim has period+region+metric AND match succeeded AND we found
      a region-specific cell.
    - ``medium``: most fields present, OR match succeeded with weaker hints.
    - ``low``: parsed value present but missing two or more hints.
    - ``unverifiable``: no parseable value, or no source data found.
    """
    hint_score = sum(1 for k in ("period", "region", "metric") if parsed.get(k))
    if match and hint_score >= 3 and has_region_match:
        return "high"
    if match or hint_score >= 2:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def verify_statistics(
    claim: str,
    table_id: str | None = None,
    tolerance: float = 0.01,
    *,
    _search: StatisticsSearch | None = None,
    _data: StatisticsData | None = None,
) -> VerifyResult:
    """Cross-check a numeric claim against KOSIS source data.

    Args:
        claim: Free-form sentence containing a number, e.g. ``"2023년 서울
            인구는 9.4M명"``. Korean and English forms are both supported.
        table_id: Optional KOSIS ``TBL_ID``. If provided, search is skipped
            and the table is fetched directly. Format ``"<org_id>:<tbl_id>"``
            is also accepted (handy when the org id is known).
        tolerance: Relative tolerance (default ``0.01`` = 1%). The match
            condition is ``abs(actual - expected) / expected <= tolerance``.
        _search / _data: Injection points for unit tests. Production callers
            should leave these as ``None``.

    Returns:
        :class:`VerifyResult`. The function never raises for ordinary failure
        modes (no parseable number, table not found, etc.) — they are reported
        via ``confidence='unverifiable'`` and a human-readable ``explanation``.
    """
    parsed = parse_claim(claim)
    actual = parsed["value"]

    if actual is None:
        return VerifyResult(
            match=False,
            expected=None,
            actual=None,
            diff_pct=None,
            tolerance=tolerance,
            table_id=table_id,
            source_url=None,
            confidence="unverifiable",
            explanation=(
                "주장에서 숫자를 추출할 수 없습니다. 명확한 숫자 표현(예: '9.4M', '9400000')을 포함하세요. / "
                "Could not extract a numeric value from the claim. Include an explicit number "
                "(e.g. '9.4M', '9400000')."
            ),
        )

    search = _search or StatisticsSearch()
    data_client = _data or StatisticsData()

    # ---- Resolve org_id / tbl_id ----
    org_id: str | None = None
    tbl_id: str | None = None
    table_name: str | None = None

    if table_id:
        if ":" in table_id:
            org_id, tbl_id = table_id.split(":", 1)
        else:
            tbl_id = table_id
            # Look up org_id via search-by-id.
            info = search.search_by_table_id(tbl_id)
            if info:
                org_id = info.get("ORG_ID")
                table_name = info.get("TBL_NM")
    else:
        # Need both metric and (region or period) to disambiguate.
        keyword = parsed.get("metric")
        if not keyword:
            return VerifyResult(
                match=False,
                expected=None,
                actual=actual,
                diff_pct=None,
                tolerance=tolerance,
                table_id=None,
                source_url=None,
                confidence="unverifiable",
                explanation=(
                    "테이블을 식별할 수 없습니다. table_id를 명시하거나 지표명(예: '인구', 'GDP')을 포함하세요. / "
                    "Could not identify a source table. Pass `table_id` explicitly or include a metric "
                    "keyword (e.g. 'population', 'GDP')."
                ),
            )
        results = search.search(keyword, result_count=10)
        if not results:
            return VerifyResult(
                match=False,
                expected=None,
                actual=actual,
                diff_pct=None,
                tolerance=tolerance,
                table_id=None,
                source_url=None,
                confidence="unverifiable",
                explanation=(
                    f"'{keyword}' 키워드로 매칭되는 KOSIS 테이블을 찾지 못했습니다. table_id를 직접 전달하세요. / "
                    f"No KOSIS table matched the keyword '{keyword}'. Please pass `table_id` directly."
                ),
            )
        chosen = results[0]
        org_id = chosen.get("ORG_ID")
        tbl_id = chosen.get("TBL_ID")
        table_name = chosen.get("TBL_NM")

    if not (org_id and tbl_id):
        return VerifyResult(
            match=False,
            expected=None,
            actual=actual,
            diff_pct=None,
            tolerance=tolerance,
            table_id=tbl_id,
            source_url=_build_source_url(org_id, tbl_id),
            confidence="unverifiable",
            explanation=(
                "유효한 org_id/tbl_id 쌍을 확보하지 못했습니다. / "
                "Could not resolve a valid (org_id, tbl_id) pair."
            ),
        )

    # ---- Fetch data ----
    start, end, prd_se = _period_to_kosis_dates(parsed.get("period"))
    try:
        records = data_client.get_data(
            org_id=org_id,
            tbl_id=tbl_id,
            start_date=start,
            end_date=end,
            prd_se=prd_se,
        )
    except Exception as exc:
        logger.warning(f"verify_statistics: get_data failed for {tbl_id}: {exc}")
        records = []

    record = _select_matching_record(records, parsed)
    if record is None:
        return VerifyResult(
            match=False,
            expected=None,
            actual=actual,
            diff_pct=None,
            tolerance=tolerance,
            table_id=tbl_id,
            source_url=_build_source_url(org_id, tbl_id),
            confidence="unverifiable",
            explanation=(
                f"테이블 {tbl_id}에서 주장과 일치하는 셀을 찾지 못했습니다. / "
                f"No matching cell found in table {tbl_id} for the claim."
            ),
        )

    expected = _to_float(record.get("DT"))
    if expected is None or expected == 0:
        return VerifyResult(
            match=False,
            expected=expected,
            actual=actual,
            diff_pct=None,
            tolerance=tolerance,
            table_id=tbl_id,
            source_url=_build_source_url(org_id, tbl_id),
            confidence="unverifiable",
            explanation=(
                "원본 데이터 값이 비어있거나 0이라 비교할 수 없습니다. / "
                "Source data value is missing or zero; cannot compute relative diff."
            ),
        )

    diff_pct = (actual - expected) / expected
    match = abs(diff_pct) <= tolerance

    has_region_match = bool(
        parsed.get("region")
        and isinstance(record.get("C1_NM"), str)
        and (parsed["region"] in record["C1_NM"] or record["C1_NM"] in parsed["region"])
    )
    confidence = _rank_confidence(parsed, match, has_region_match)
    source_url = _build_source_url(org_id, tbl_id)

    label_ko = "일치" if match else "불일치"
    label_en = "matches" if match else "does NOT match"
    explanation = (
        f"[{label_ko}] 주장 {actual:,.0f} vs KOSIS {expected:,.0f} "
        f"(차이 {diff_pct * 100:+.2f}%, 허용 ±{tolerance * 100:.2f}%). "
        f"출처: {table_name or tbl_id}. / "
        f"[{label_en}] claim {actual:,.0f} vs KOSIS {expected:,.0f} "
        f"(diff {diff_pct * 100:+.2f}%, tolerance ±{tolerance * 100:.2f}%). "
        f"Source: {table_name or tbl_id}."
    )

    return VerifyResult(
        match=match,
        expected=expected,
        actual=actual,
        diff_pct=diff_pct,
        tolerance=tolerance,
        table_id=tbl_id,
        source_url=source_url,
        confidence=confidence,
        explanation=explanation,
    )
