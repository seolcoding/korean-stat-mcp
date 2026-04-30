# Ralph Mission: korean-stat-mcp Open-Source Transformation

## Mission

Transform this repo (currently `kosis-mcp`, private/internal) into `korean-stat-mcp`,
a public open-source MCP server modeled after https://github.com/chrisryugj/korean-law-mcp.

Stack stays Python/FastMCP/FastAPI. Stack rewrite is OUT OF SCOPE.

The full plan file is at `.claude/plans/https-github-com-chrisryugj-korean-law-async-hellman.md` —
**read it first**. It contains full context, file paths, and acceptance criteria for every story (US-001 through US-008).

## Execution rules

- Process stories US-001 → US-008 **in order**. Do NOT skip.
- For each story, dispatch parallel agents for independent sub-tasks
  (e.g. US-002: one agent per missing endpoint).
- Verify each story against its **exact** acceptance criteria from the plan file —
  not generic "is it done?". Run the verification commands listed in the plan.
- A story is `passes: true` only when every checkbox is verified with **fresh evidence**
  (test output, grep result, file existence, etc.) captured in `progress.txt`.
- If a verification fails, fix and re-run. Do not mark passes prematurely.
- Preserve the 99.38% KOSIS API reliability — if reliability test drops below 99.0%,
  block the iteration until restored.
- Touch existing working code minimally. Add new files in preference to refactoring stable ones
  (e.g. add `src/mcp_server/exposed_tools.py` rather than rewriting `server.py`).
- Korean is primary language for README/CLAUDE.md; create matching `-EN.md` mirrors.
- Strip every reference to `wai-3090ti`, `seolcoding.com`, and the temporary
  Cloudflare Tunnel URL. Replace with neutral placeholders or remove.

## Story-specific guidance

### US-002 (API coverage)
Use `docs/KOSIS_API_IMPLEMENTATION_PLAN.md` as starting gap list, then verify against
KOSIS OpenAPI portal (https://kosis.kr/openapi/index/index.jsp). Reach out to live KOSIS
API only with the existing rate limit (1.0s/req).

For each new endpoint, follow the pattern of `src/kosis_tools/data.py`:
Pydantic request → httpx call → Pydantic response → integration test.

### US-003 (allow-list)
Mirror korean-law-mcp's `V3_EXPOSED` pattern. Keep the 24 existing tools but only
register the V1_EXPOSED set with the MCP server; expose `discover_tools` + `execute_tool`
for power users.

### US-004 (LLM manual)
The standout pattern from korean-law-mcp is `CLAUDE.md` as a **query-pattern → tool-chain
decision table**. Build the KOSIS analog with at least 15 query patterns covering
trend / compare / rank / aggregate / verify scenarios.

### US-005 (verify_statistics)
The killer differentiator. Full spec is in the plan file.

### US-007 (validation harness)
This story is the gate before US-008 release. Both reliability and LLM-judge thresholds
must pass.

## Parallel dispatch hints

| Story | Parallel agents |
|---|---|
| US-001 | 3 — (a) hygiene file scrubbing, (b) bilingual CONTRIBUTING/CHANGELOG, (c) GitHub Actions CI |
| US-002 | N — one per missing endpoint module |
| US-004 | 2 — KO and EN versions written from same outline |
| US-006 | 4 — PyPI / plugin marketplace / Docker / hosted-endpoint |

## Definition of done

All 8 stories `passes: true`. Final iteration runs:

1. `pytest -q` (all green)
2. `python scripts/validation/run_reliability_test.py --n 10000` (≥99.0%)
3. `python scripts/validation/run_llm_judge.py` (≥85%)
4. `grep -rE "wai-3090ti|seolcoding\.com" . --exclude-dir=.git --exclude-dir=outputs --exclude-dir=.worktrees` returns 0 hits
5. ai-slop-cleaner pass on all changed files
6. Tag `v0.1.0`

When all gates pass, stop the loop and summarize the diff in `progress.txt`.
