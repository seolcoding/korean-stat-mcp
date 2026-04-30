"""KOSIS error classification tests.

The KOSIS OpenAPI returns a small set of standard error codes (10/11/20/21/
30/31/40/41/42/50). Our `errors.classify` maps each code to a category and
a human-readable next-step action so tools can surface meaningful guidance
instead of raw KOSIS error strings.
"""

from __future__ import annotations

import pytest

from kosis_tools.errors import KosisError, classify


def test_classify_returns_none_when_no_error_field():
    assert classify({"jsonStat": [], "id": 1}) is None
    assert classify([{"TBL_ID": "DT_X"}]) is None
    assert classify(None) is None
    assert classify("plain string") is None


def test_classify_known_codes_via_err_field():
    e = classify({"err": "11", "errMsg": "인증키 기간만료"})
    assert isinstance(e, KosisError)
    assert e.code == "11"
    assert e.category == "auth"
    assert e.message == "인증키 기간만료"
    assert "갱신" in e.action


def test_classify_known_codes_via_errCode_field():
    """KOSIS sometimes returns errCode instead of err."""
    e = classify({"errCode": "31", "errMsg": "조회결과 초과"})
    assert e is not None
    assert e.code == "31"
    assert e.category == "query"


@pytest.mark.parametrize(
    "code,expected_category",
    [
        ("10", "auth"),
        ("11", "auth"),
        ("20", "input"),
        ("21", "input"),
        ("30", "query"),
        ("31", "query"),
        ("40", "rate_limit"),
        ("41", "rate_limit"),
        ("42", "rate_limit"),
        ("50", "server"),
    ],
)
def test_each_documented_code_classified(code: str, expected_category: str):
    e = classify({"err": code, "errMsg": "msg"})
    assert e is not None
    assert e.code == code
    assert e.category == expected_category
    assert e.action  # non-empty next-step text


def test_classify_unknown_code_falls_back_to_unknown_category():
    e = classify({"err": "99", "errMsg": "정의되지 않은 코드"})
    assert e is not None
    assert e.code == "99"
    assert e.category == "unknown"


def test_classify_when_only_errMsg_present():
    """KOSIS occasionally returns errMsg without an explicit code field."""
    e = classify({"errMsg": "해당 데이터가 없습니다."})
    assert e is not None
    assert e.code == "?"
    assert e.category == "unknown"
    assert e.message == "해당 데이터가 없습니다."


def test_kosis_error_is_immutable():
    e = classify({"err": "50", "errMsg": "서버오류"})
    assert e is not None
    with pytest.raises((AttributeError, Exception)):
        e.code = "X"  # type: ignore[misc]


def test_error_to_dict_returns_none_for_none():
    from kosis_tools.errors import error_to_dict

    assert error_to_dict(None) is None


def test_error_to_dict_envelope_shape():
    from kosis_tools.errors import error_to_dict

    err = classify({"err": "11", "errMsg": "인증키 기간만료"})
    env = error_to_dict(err)
    assert env is not None
    assert set(env.keys()) == {"code", "category", "message", "action"}
    assert env["code"] == "11"
    assert env["category"] == "auth"
    assert "갱신" in env["action"]
