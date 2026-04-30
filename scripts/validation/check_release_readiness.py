"""Release-readiness checks for publish-facing metadata and docs.

This is intentionally narrower than a full documentation linter. It catches
stale public strings that would make the v0.1.0 package misleading:

- unresolved GitHub owner placeholders
- nonexistent marketplace repo names
- removed or legacy public tool names in routing docs
- removed embedding/pgvector runtime requirements in current deploy docs
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PUBLIC_FILES = (
    ".env.example",
    ".github/ISSUE_TEMPLATE/config.yml",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "CONTRIBUTING-EN.md",
    "README.md",
    "README-EN.md",
    "deploy/README.md",
    "docker-compose.yml",
    "docker-compose.remote.yml",
    "docs/DEPLOYMENT.md",
    "docs/TOOL_MIGRATION.md",
    "docs/USER_GUIDE.md",
    "docs/llm-routing-manual.md",
    "pyproject.toml",
    "src/mcp_server/app.py",
    "src/mcp_server/server.py",
    "src/mcp_server/system_prompt.py",
    "src/kosis_tools/mcp_server.py",
)

CURRENT_DEPLOY_FILES = {
    "README.md",
    "README-EN.md",
    "deploy/README.md",
    "docker-compose.yml",
    "docker-compose.remote.yml",
    "docs/DEPLOYMENT.md",
}

ROUTING_FILES = {
    "README.md",
    "README-EN.md",
    "docs/TOOL_MIGRATION.md",
    "docs/USER_GUIDE.md",
    "docs/llm-routing-manual.md",
    "src/mcp_server/system_prompt.py",
}


@dataclass(frozen=True)
class Issue:
    path: str
    line: int
    pattern: str
    text: str


@dataclass(frozen=True)
class Rule:
    pattern: str
    regex: re.Pattern[str]
    files: frozenset[str] | None = None

    def applies_to(self, path: str) -> bool:
        return self.files is None or path in self.files


RULES: tuple[Rule, ...] = (
    Rule("<github-user>", re.compile(r"<github-user>")),
    Rule("seolcoding-OS/korean-stat-mcp", re.compile(r"seolcoding-OS/korean-stat-mcp")),
    Rule("github.com/sdh/kosis-mcp", re.compile(r"github\.com/sdh/kosis-mcp")),
    Rule("uvx kosis-mcp", re.compile(r"\buvx\s+kosis-mcp\b")),
    Rule("hard-coded 0.2.0 runtime version", re.compile(r'"version"\s*:\s*"0\.2\.0"')),
    Rule("kosis-mcp runtime service id", re.compile(r'"service"\s*:\s*"kosis-mcp"')),
    Rule(
        "search_statistics_tables",
        re.compile(r"\bsearch_statistics_tables\b"),
        frozenset(ROUTING_FILES),
    ),
    Rule(
        "browse_by_organization",
        re.compile(r"\bbrowse_by_organization\b"),
        frozenset(ROUTING_FILES),
    ),
    Rule(
        "browse_by_theme", re.compile(r"\bbrowse_by_theme\b"), frozenset(ROUTING_FILES)
    ),
    Rule("query_table", re.compile(r"\bquery_table\b"), frozenset(ROUTING_FILES)),
    Rule(
        "list_categories", re.compile(r"\blist_categories\b"), frozenset(ROUTING_FILES)
    ),
    Rule(
        "get_indicator_series",
        re.compile(r"\bget_indicator_series\b"),
        frozenset(ROUTING_FILES),
    ),
    Rule(
        "list_dimensions", re.compile(r"\blist_dimensions\b"), frozenset(ROUTING_FILES)
    ),
    Rule(
        "search_tables_hybrid in user docs",
        re.compile(r"\bsearch_tables_hybrid\b"),
        frozenset({"README.md", "README-EN.md", "docs/USER_GUIDE.md"}),
    ),
    Rule(
        "OPENAI_API_KEY in current deploy docs",
        re.compile(r"\bOPENAI_API_KEY\b"),
        frozenset(CURRENT_DEPLOY_FILES),
    ),
    Rule(
        "pgvector in current deploy docs",
        re.compile(r"\bpgvector\b"),
        frozenset(CURRENT_DEPLOY_FILES),
    ),
)


def iter_files(paths: tuple[str, ...] = PUBLIC_FILES) -> list[tuple[str, Path]]:
    missing: list[str] = []
    existing: list[tuple[str, Path]] = []
    for rel in paths:
        path = REPO_ROOT / rel
        if path.exists():
            existing.append((rel, path))
        else:
            missing.append(rel)
    if missing:
        joined = ", ".join(missing)
        raise FileNotFoundError(f"Release-readiness required files missing: {joined}")
    return existing


def run_checks(paths: tuple[str, ...] = PUBLIC_FILES) -> list[Issue]:
    issues: list[Issue] = []
    for rel, path in iter_files(paths):
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for rule in RULES:
                if rule.applies_to(rel) and rule.regex.search(line):
                    issues.append(
                        Issue(
                            path=rel,
                            line=line_no,
                            pattern=rule.pattern,
                            text=line.strip(),
                        )
                    )
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="Print only failures")
    args = parser.parse_args(argv)

    try:
        issues = run_checks()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if issues:
        print("Release-readiness check failed:", file=sys.stderr)
        for issue in issues:
            print(
                f"{issue.path}:{issue.line}: {issue.pattern}: {issue.text}",
                file=sys.stderr,
            )
        return 1

    if not args.quiet:
        print(f"Release-readiness check passed ({len(PUBLIC_FILES)} files scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
