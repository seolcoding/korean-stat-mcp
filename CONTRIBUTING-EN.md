# Contributing

Welcome, and thank you for your interest in `korean-stat-mcp`. Even a one-line typo fix is genuinely helpful.

> 한국어 버전: [CONTRIBUTING.md](./CONTRIBUTING.md)

---

## How to contribute

### Issues

- **Bug reports**: include reproduction steps, expected vs actual behavior, and your environment (OS, Python version, package versions).
- **Feature requests**: separate the *problem* (why) from the *proposed solution* (how).
- Please search existing issues first to avoid duplicates.

### Pull Requests

1. Open an issue first to align on direction before sending a PR. (Trivial typo fixes are exempt.)
2. Don't commit directly to `main` — branch from it with a `feat/`, `fix/`, or `docs/` prefix.
3. Prefer small, focused commits. One PR should address one logical change.
4. Reference related issues in the PR description (`Closes #123`).

---

## Development setup

```bash
# 1. Clone
git clone https://github.com/seolcoding/korean-stat-mcp.git
cd korean-stat-mcp

# 2. Install dependencies (uv)
uv sync

# 3. Configure environment
cp .env.example .env
# Open .env and fill in KOSIS_API_KEY.
# Request a KOSIS API key here: https://kosis.kr/openapi/index/index.jsp

# 4. Run tests
uv run pytest -q
```

> We standardize on [uv](https://github.com/astral-sh/uv) as the Python package manager.

---

## Code style

```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type-check
uv run mypy src/
```

- Keep lines under 100 characters and prefer functions under ~50 lines.
- Add docstrings (Korean or English) to public functions.
- Treat all incoming KOSIS API response fields as untrusted strings. The `DT` field in particular can contain placeholders like `"-"` or `"*"`.

---

## Commit message convention

We recommend [Conventional Commits](https://www.conventionalcommits.org/).

| Prefix | Use |
|---|---|
| `feat:` | A new feature |
| `fix:` | A bug fix |
| `docs:` | Docs-only changes |
| `refactor:` | Code restructure without behavior change |
| `test:` | Test additions or fixes |
| `chore:` | Build, tooling, or meta changes |

Examples:

```
feat: add verify_statistics tool for citation re-fetch
fix: handle KOSIS DT="-" placeholder as null in parser
```

---

## PR checklist

Before opening a PR, please confirm:

- [ ] `uv run pytest -q` passes
- [ ] `uv run ruff check .` passes
- [ ] `uv run mypy src/` passes
- [ ] New functionality has tests
- [ ] User-visible behavior changes are reflected in docs (`README.md`, `docs/USER_GUIDE.md`, etc.)
- [ ] A line item is added under `## [Unreleased]` in `CHANGELOG.md`

---

## Code of Conduct

All participants in this project are expected to follow the [Code of Conduct](./CODE_OF_CONDUCT.md).

---

## Korean version

한국어 안내는 [CONTRIBUTING.md](./CONTRIBUTING.md) 를 참고해주세요.
