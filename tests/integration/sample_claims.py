"""20 hand-picked verify_statistics claims for the US-005 acceptance harness.

10 claims are deliberately CORRECT (within 1% of the published KOSIS value as
of late 2024/early 2025) and 10 are deliberately WRONG (off by >>1%). Run the
acceptance harness in ``test_verify_statistics.py`` to confirm we hit
>=18/20.

Each entry:
    claim:        free-form Korean/English sentence with a number
    table_id:     'org_id:tbl_id' so verify can skip search (deterministic)
    expect_match: True if the claim should verify, False otherwise
    notes:        why this number was chosen (so the test can be audited)

Tables referenced:
    101:DT_1B040A3   행정구역별 인구수 (residence registration)
    101:DT_1YL20631  실업률 (unemployment rate, monthly)
    301:DT_2KAA101   주택유형별 (housing — illustrative; left here for shape)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SampleClaim:
    claim: str
    table_id: str
    expect_match: bool
    notes: str


SAMPLES: tuple[SampleClaim, ...] = (
    # ---- CORRECT (10) -------------------------------------------------------
    SampleClaim(
        "2023년 서울 인구는 약 9.4M명",
        "101:DT_1B040A3",
        True,
        "Seoul residents 2023 ≈ 9.41M",
    ),
    SampleClaim(
        "Seoul population in 2023 was 9.4 million",
        "101:DT_1B040A3",
        True,
        "English form of the same number",
    ),
    SampleClaim(
        "2022년 서울 인구는 약 9.43M명",
        "101:DT_1B040A3",
        True,
        "Seoul 2022 ≈ 9.43M",
    ),
    SampleClaim(
        "2021년 서울 인구는 약 9.5M명",
        "101:DT_1B040A3",
        True,
        "Seoul 2021 ≈ 9.51M",
    ),
    SampleClaim(
        "2023년 부산 인구는 약 3.3M명",
        "101:DT_1B040A3",
        True,
        "Busan 2023 ≈ 3.30M",
    ),
    SampleClaim(
        "2023년 인천 인구는 약 3.0M명",
        "101:DT_1B040A3",
        True,
        "Incheon 2023 ≈ 2.99M (within 1%)",
    ),
    SampleClaim(
        "2023년 대구 인구는 약 2.4M명",
        "101:DT_1B040A3",
        True,
        "Daegu 2023 ≈ 2.37M",
    ),
    SampleClaim(
        "2023년 경기 인구는 약 13.6M명",
        "101:DT_1B040A3",
        True,
        "Gyeonggi 2023 ≈ 13.63M",
    ),
    SampleClaim(
        "2023년 전국 인구는 약 51.3M명",
        "101:DT_1B040A3",
        True,
        "Korea total 2023 ≈ 51.32M",
    ),
    SampleClaim(
        "2024년 1월 실업률은 약 3.7%",
        "101:DT_1YL20631",
        True,
        "Unemployment Jan 2024 ≈ 3.7% (illustrative — confirm tbl_id)",
    ),
    # ---- WRONG (10) ---------------------------------------------------------
    SampleClaim(
        "2023년 서울 인구는 12M명",
        "101:DT_1B040A3",
        False,
        "Off by ~28% — should fail",
    ),
    SampleClaim(
        "Seoul population in 2023 was 5 million",
        "101:DT_1B040A3",
        False,
        "Off by ~47%",
    ),
    SampleClaim(
        "2023년 부산 인구는 5M명",
        "101:DT_1B040A3",
        False,
        "Busan ≈ 3.3M, claim 5M",
    ),
    SampleClaim(
        "2023년 전국 인구는 60M명",
        "101:DT_1B040A3",
        False,
        "Off by ~17%",
    ),
    SampleClaim(
        "2023년 인천 인구는 1M명",
        "101:DT_1B040A3",
        False,
        "Off by ~67%",
    ),
    SampleClaim(
        "2023년 경기 인구는 5M명",
        "101:DT_1B040A3",
        False,
        "Off by ~63%",
    ),
    SampleClaim(
        "2022년 서울 인구는 7M명",
        "101:DT_1B040A3",
        False,
        "Off by ~26%",
    ),
    SampleClaim(
        "2021년 서울 인구는 11M명",
        "101:DT_1B040A3",
        False,
        "Off by ~16%",
    ),
    SampleClaim(
        "2023년 대구 인구는 5M명",
        "101:DT_1B040A3",
        False,
        "Off by >100%",
    ),
    SampleClaim(
        "2024년 1월 실업률은 15%",
        "101:DT_1YL20631",
        False,
        "Way off (>4x)",
    ),
)


assert sum(1 for s in SAMPLES if s.expect_match) == 10
assert sum(1 for s in SAMPLES if not s.expect_match) == 10
