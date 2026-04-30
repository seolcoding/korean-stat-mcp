"""LLM-judge harness: feed the routing manual to a fresh LLM session
and score routing accuracy on the 20 hand-designed queries.

Usage
-----
    uv run python scripts/validation/run_llm_judge.py
    uv run python scripts/validation/run_llm_judge.py --model claude-sonnet-4-6
    uv run python scripts/validation/run_llm_judge.py --dry-run   # offline harness self-check
    uv run python scripts/validation/run_llm_judge.py --gate 0.85 --out outputs/validation/judge.json

Behaviour
---------
- Loads ``docs/llm-routing-manual.md`` and the ``V1_EXPOSED`` allow-list.
- For each ``JudgeCase`` in ``scripts.validation.judge_queries.CASES`` it builds a
  prompt that contains the manual + the V1 tool names + the user query and asks
  the model for the **first** tool it would call.
- The reply is normalised (strip backticks/quotes/whitespace, lowercase, alias the
  legacy names that still appear in the manual) and compared to
  ``expected_first_tool``.
- If ``ANTHROPIC_API_KEY`` is missing and ``--dry-run`` is not set, the script
  falls back to dry-run mode and clearly marks the JSON output as a skeleton.

Requires ``pip install anthropic`` OR ``uv add anthropic`` for real runs.
Not added to project deps because it's only used by validation tooling.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

# Make ``src/`` importable so ``mcp_server.exposed_tools`` resolves whether the
# script is run from the repo root or via ``uv run``.
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# Also make the repo root importable so ``scripts.validation.judge_queries``
# resolves whether we run as a module (``python -m scripts.validation.run_llm_judge``)
# or as a plain script (``python scripts/validation/run_llm_judge.py``).
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp_server.exposed_tools import V1_EXPOSED, V1_EXPOSED_NAMES  # noqa: E402

try:
    from scripts.validation.judge_queries import CASES, JudgeCase  # noqa: E402
except ModuleNotFoundError:
    # Fall back to a sibling-file import when ``scripts`` is not a package.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from judge_queries import CASES, JudgeCase  # type: ignore[no-redef]  # noqa: E402

ROUTING_MANUAL = REPO_ROOT / "docs" / "llm-routing-manual.md"
DEFAULT_OUT_DIR = REPO_ROOT / "outputs" / "validation"

# Legacy → V1 tool name aliases. The bilingual routing manual still references a
# few pre-V1 names; map them onto the canonical V1 surface before scoring.
LEGACY_ALIASES: dict[str, str] = {
    "search_statistics_tables": "search_statistics",
    "browse_by_organization": "browse_categories",
    "browse_by_theme": "browse_categories",
}


@dataclass
class CaseResult:
    id: str
    lang: str
    query: str
    expected: str
    actual: str
    correct: bool
    raw_response: str = ""


def _normalise_tool_name(raw: str) -> str:
    """Strip code fences/quotes/whitespace, lowercase, apply legacy aliases."""
    text = raw.strip()
    # Take the first non-empty line — many models reply with the name then a
    # paragraph of justification we did not ask for.
    for line in text.splitlines():
        line = line.strip()
        if line:
            text = line
            break
    text = text.strip("`'\" .,:;\n\t")
    # Drop a leading bullet/number marker like "- " or "1. ".
    text = re.sub(r"^[-*\d.)\s]+", "", text)
    # If the model wrote "tool: foo" or "answer: foo".
    if ":" in text:
        text = text.rsplit(":", 1)[-1].strip()
    text = text.strip("`'\" ")
    text = text.lower()
    return LEGACY_ALIASES.get(text, text)


def _build_prompt(manual: str, tool_names: list[str], case: JudgeCase) -> str:
    tool_list = "\n".join(f"- {n}" for n in tool_names)
    return (
        "You are an LLM client of the `korean-stat-mcp` MCP server. Read the "
        "routing manual below and decide which tool you would call FIRST for "
        "the user's question.\n\n"
        "================ ROUTING MANUAL ================\n"
        f"{manual}\n"
        "================ END MANUAL ====================\n\n"
        "The MCP server only exposes these tool names (V1_EXPOSED):\n"
        f"{tool_list}\n\n"
        f"User asks ({case.lang}): {case.query}\n\n"
        "Respond with ONLY the tool name (one of the names above). No prose, "
        "no backticks, no explanation."
    )


def _call_anthropic(model: str, prompt: str) -> str:
    """Call the Anthropic Messages API. Raises with an instructive error if the
    SDK is not installed."""
    try:
        import anthropic  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "The `anthropic` package is required for non-dry-run mode. "
            "Install it with `uv add anthropic` or `pip install anthropic`."
        ) from exc

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=64,
        messages=[{"role": "user", "content": prompt}],
    )
    # Text content is in msg.content[0].text for plain text replies.
    parts: list[str] = []
    for block in msg.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


def run(
    *,
    model: str,
    dry_run: bool,
    gate: float,
    out_path: Path,
) -> int:
    manual = ROUTING_MANUAL.read_text(encoding="utf-8")
    tool_names = [t.name for t in V1_EXPOSED]

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    effective_dry_run = dry_run or not api_key
    skeleton_note = ""
    if not dry_run and not api_key:
        skeleton_note = (
            "ANTHROPIC_API_KEY not set — falling back to dry-run skeleton; "
            "actual scoring deferred."
        )

    started_at = datetime.now(timezone.utc).isoformat()
    results: list[CaseResult] = []

    for case in CASES:
        if case.expected_first_tool not in V1_EXPOSED_NAMES:
            # Defensive: catch query-bank drift before we score anything.
            raise ValueError(
                f"Case {case.id}: expected tool {case.expected_first_tool!r} "
                "is not in V1_EXPOSED."
            )

        if effective_dry_run:
            actual = case.expected_first_tool
            raw = "[dry-run: pretended response equals expected]"
        else:
            prompt = _build_prompt(manual, tool_names, case)
            raw = _call_anthropic(model, prompt)
            actual = _normalise_tool_name(raw)

        results.append(
            CaseResult(
                id=case.id,
                lang=case.lang,
                query=case.query,
                expected=case.expected_first_tool,
                actual=actual,
                correct=(actual == case.expected_first_tool),
                raw_response=raw,
            )
        )

    completed_at = datetime.now(timezone.utc).isoformat()
    correct = sum(1 for r in results if r.correct)
    n = len(results)
    accuracy = (correct / n) if n else 0.0
    passed = accuracy >= gate

    payload: dict[str, object] = {
        "model": model,
        "n": n,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "gate": gate,
        "passed": passed,
        "dry_run": effective_dry_run,
        "started_at": started_at,
        "completed_at": completed_at,
        "cases": [asdict(r) for r in results],
    }
    if effective_dry_run:
        payload["note"] = skeleton_note or "dry-run skeleton — actual scoring deferred"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "model": model,
                "dry_run": effective_dry_run,
                "n": n,
                "correct": correct,
                "accuracy": payload["accuracy"],
                "gate": gate,
                "passed": passed,
                "out": str(out_path),
            },
            ensure_ascii=False,
        )
    )

    return 0 if passed else 1


def _default_out() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_OUT_DIR / f"llm-judge-{ts}.json"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--api-key",
        default="ANTHROPIC_API_KEY",
        help="Name of the env var that holds the Anthropic API key (default ANTHROPIC_API_KEY).",
    )
    p.add_argument("--gate", type=float, default=0.85)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)

    # Honour --api-key even though we always read os.environ — the user can
    # point us at a differently named env var.
    if args.api_key and args.api_key != "ANTHROPIC_API_KEY":
        val = os.environ.get(args.api_key)
        if val:
            os.environ["ANTHROPIC_API_KEY"] = val

    out_path = args.out if args.out is not None else _default_out()
    return run(
        model=args.model,
        dry_run=args.dry_run,
        gate=args.gate,
        out_path=out_path,
    )


if __name__ == "__main__":
    sys.exit(main())
