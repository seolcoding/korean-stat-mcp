"""
공통 실행 엔진 기반 코드.

모든 특화 실행기가 공유하는 기본 기능을 제공합니다.
"""

from __future__ import annotations

import io
import re
import sys
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# 금지된 패턴 (보안)
BLOCKED_PATTERNS = [
    r"\bimport\s+os\b",
    r"\bimport\s+subprocess\b",
    r"\bimport\s+shutil\b",
    r"\bfrom\s+os\b",
    r"\bfrom\s+subprocess\b",
    r"\b__import__\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bcompile\s*\(",
    r"\bglobals\s*\(",
    r"\blocals\s*\(",
    r"\bgetattr\s*\(",
    r"\bsetattr\s*\(",
    r"\bdelattr\s*\(",
    r"\bopen\s*\(",
    r"\bbreakpoint\s*\(",
]


class ExecutionError(Exception):
    """코드 실행 오류."""

    pass


class SecurityError(Exception):
    """보안 위반 오류."""

    pass


def validate_code(code: str) -> None:
    """
    코드 보안 검증.

    Args:
        code: 검증할 Python 코드

    Raises:
        SecurityError: 금지된 패턴 발견 시
    """
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code, re.IGNORECASE):
            raise SecurityError(f"금지된 패턴 감지: {pattern}")


def get_base_globals() -> Dict[str, Any]:
    """모든 실행기가 공유하는 기본 글로벌 환경."""
    return {
        # 기본 타입
        "True": True,
        "False": False,
        "None": None,
        # 빌트인 함수 (안전한 것만)
        "len": len,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "sorted": sorted,
        "reversed": reversed,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "range": range,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "print": print,
        "isinstance": isinstance,
        "type": type,
    }


def wrap_code(code: str) -> str:
    """
    코드를 래핑하여 return 문 지원.

    마지막 표현식 또는 return 값을 __result__에 저장.
    """
    lines = code.strip().split("\n")

    # return 문이 있으면 함수로 래핑
    if any(line.strip().startswith("return ") for line in lines):
        indented = "\n".join("    " + line for line in lines)
        return f"""
def __execute__():
{indented}

__result__ = __execute__()
"""
    else:
        # 마지막 줄이 표현식이면 __result__에 할당
        if lines:
            last_line = lines[-1].strip()
            if last_line and not any(
                [
                    "=" in last_line and "==" not in last_line,
                    last_line.startswith(
                        ("if ", "for ", "while ", "def ", "class ", "import ", "from ")
                    ),
                ]
            ):
                lines[-1] = f"__result__ = {last_line}"
            else:
                lines.append("__result__ = None")

        return "\n".join(lines)


def execute_with_context(
    code: str,
    safe_globals: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    주어진 컨텍스트에서 코드를 실행합니다.

    Args:
        code: 실행할 Python 코드
        safe_globals: 안전한 글로벌 환경
        context: 추가 컨텍스트 변수들

    Returns:
        {
            "success": bool,
            "result": Any,
            "stdout": str,
            "error": str | None,
        }
    """
    # 보안 검증
    try:
        validate_code(code)
    except SecurityError as e:
        return {
            "success": False,
            "result": None,
            "stdout": "",
            "error": str(e),
        }

    # 추가 컨텍스트 병합
    if context:
        safe_globals.update(context)

    # 코드 래핑
    wrapped_code = wrap_code(code)

    # stdout 캡처
    captured_output = io.StringIO()
    old_stdout = sys.stdout

    result = {
        "success": False,
        "result": None,
        "stdout": "",
        "error": None,
    }

    try:
        sys.stdout = captured_output

        local_vars: Dict[str, Any] = {}
        exec(wrapped_code, safe_globals, local_vars)

        result["success"] = True
        result["result"] = local_vars.get("__result__")
        result["stdout"] = captured_output.getvalue()

    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)}"
        result["stdout"] = captured_output.getvalue()

    finally:
        sys.stdout = old_stdout

    return result
