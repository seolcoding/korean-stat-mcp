"""KOSIS OpenAPI error classification.

KOSIS returns a small set of documented error codes (per the official
developer guide §1.4). The codes share an `errMsg` field and one of `err`
or `errCode` carrying the numeric code. Categories below let tools surface
a meaningful next-step action instead of leaking raw Korean error strings
to the LLM.

Reference: KOSIS 공유서비스(OpenAPI) 개발가이드 v1.0, §1.4 에러메시지.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ErrorCategory = Literal["auth", "input", "query", "rate_limit", "server", "unknown"]


@dataclass(frozen=True)
class KosisError:
    """A classified KOSIS API error response.

    `code` is the original KOSIS errCode (string form, '?' if absent).
    `category` groups codes by recommended retry/recovery semantics.
    `message` preserves the upstream errMsg.
    `action` is a one-line next-step the LLM can show to the end user.
    """

    code: str
    category: ErrorCategory
    message: str
    action: str


# code -> (category, recommended action). Source: KOSIS dev guide §1.4.
_CODE_TABLE: dict[str, tuple[ErrorCategory, str]] = {
    "10": (
        "auth",
        "URL의 ?apiKey= 파라미터를 확인하세요. 호스팅 인스턴스는 키 누락 시 401을 먼저 반환합니다.",
    ),
    "11": (
        "auth",
        "https://kosis.kr/openapi/ 에서 인증키를 갱신하세요. 갱신 후에도 동일하면 신청 상태 확인 필요.",
    ),
    "20": (
        "input",
        "도구 호출 인자에서 필수 파라미터가 빠졌습니다. 도구 docstring의 required 항목을 확인하세요.",
    ),
    "21": (
        "input",
        "잘못된 파라미터 값입니다. org_id/tbl_id, 기간 형식(YYYY/YYYYMM), 분류 코드를 다시 확인하세요.",
    ),
    "30": (
        "query",
        "조건에 맞는 결과가 없습니다. 키워드를 넓히거나 기간/분류 필터를 완화한 뒤 다시 시도하세요.",
    ),
    "31": (
        "query",
        "결과가 너무 많습니다. 1회 호출 한도(40,000셀)를 넘기지 않도록 기간/지역/항목을 분할 호출하세요.",
    ),
    "40": (
        "rate_limit",
        "분당 호출 한도(2026-03-05 이후 키당 1,000건) 초과. 잠시 대기 후 재시도하세요.",
    ),
    "41": (
        "rate_limit",
        "1회 호출 ROW 한도(40,000셀) 초과. 기간/지역/항목을 잘게 나눠 분할 호출 후 병합하세요.",
    ),
    "42": (
        "rate_limit",
        "사용자별 이용 한도 초과. KOSIS 운영팀(국가데이터처)에 문의하세요.",
    ),
    "50": (
        "server",
        "KOSIS 서버 일시 오류. 1~2초 대기 후 재시도하면 대부분 해결됩니다.",
    ),
}


def classify(body: object) -> KosisError | None:
    """Inspect a KOSIS response body and return a KosisError if it is one.

    Returns None for any payload that does not look like an error envelope.
    Recognises both `err` and `errCode` field names used by different KOSIS
    endpoints. If `errMsg` is present without a code, the result is still
    classified (under category 'unknown') so callers can surface the message.
    """
    if not isinstance(body, dict):
        return None
    if "errMsg" not in body:
        return None

    raw_code = body.get("err", body.get("errCode", ""))
    code = str(raw_code).strip() if raw_code is not None else ""
    message = str(body.get("errMsg", ""))

    if code in _CODE_TABLE:
        category, action = _CODE_TABLE[code]
    else:
        category = "unknown"
        action = (
            "에러 메시지를 확인하고, 동일 증상이 반복되면 KOSIS 운영팀에 문의하세요."
        )

    return KosisError(
        code=code or "?",
        category=category,
        message=message,
        action=action,
    )


def error_to_dict(err: KosisError | None) -> dict[str, str] | None:
    """Convert a KosisError into the canonical 'error' envelope used in
    every MCP tool response so the LLM always sees the same shape:

    {"code": "11", "category": "auth", "message": "...", "action": "..."}

    Returns None if err is None, so callers can do:

        response = {...}
        if (env := error_to_dict(client._last_error)):
            response["error"] = env
    """
    if err is None:
        return None
    return {
        "code": err.code,
        "category": err.category,
        "message": err.message,
        "action": err.action,
    }


__all__ = ["KosisError", "ErrorCategory", "classify", "error_to_dict"]
