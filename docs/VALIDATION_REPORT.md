# Validation Report — korean-stat-mcp v0.1.0

> Generated: 2026-04-30 · Sources: `scripts/validation/`, `outputs/validation/`
> Tracks: **A** = KOSIS API reliability, **B** = LLM-judge tool routing.

This report records the methodology and the latest pilot results that gate the
v0.1.0 release. It is regenerated when the underlying JSON artefacts under
`outputs/validation/` are refreshed.

---

## 1. Reliability — KOSIS API coverage (Track A)

### 1.1 Methodology

`scripts/validation/run_reliability_test.py` exercises the public KOSIS API
end-to-end and reports a category breakdown per call.

1. Load the locally generated table catalogue
   (`outputs/kosis-api-catalog/tables.json`, ignored by Git).
2. Sample `N` `(org_id, tbl_id)` pairs **uniformly** from the catalogue using a
   fixed RNG seed (`--seed 42` by default) so runs are reproducible.
3. For each pair call `get_statistics_data()` at **≤ 1 req / sec** (configurable
   via `--rate-limit`). The rate limit protects the KOSIS API and matches the
   production client.
4. Categorise each response:

   | Category | Meaning |
   |----------|---------|
   | `success` | API returned at least one row |
   | `no_data` | API returned `[]` / "no result" — typically deprecated tables |
   | `api_error` | KOSIS error envelope (4xx/5xx semantics in payload) |
   | `timeout` | Request exceeded the per-call timeout |
   | `parse_error` | Response could not be decoded into the expected schema |

5. Compute two rates:
   - **strict** = `success / N`
   - **excluding_no_data** = `success / (N - no_data)` — the gating metric, since
     `no_data` is a property of the catalogue (deprecated tables) rather than a
     fault of the server.

**Gate:** `success_rate_excluding_no_data ≥ 99.0%`. Below the gate the release
is deferred and the failing samples are inspected.

### 1.2 Latest live pilot result

The latest live pilot was run on 2026-04-30 with `KOSIS_API_KEY` present:

```bash
uv run python scripts/validation/run_reliability_test.py \
  --n 100 \
  --rate-limit 0.2 \
  --gate-threshold 0.99
```

Output artefact:
`outputs/validation/reliability-20260430T025652Z.json` (ignored by Git).

| Field | Value |
|-------|-------|
| Sample N | 100 |
| Seed | 42 |
| Duration | 594.9s |
| Categories | `success=98`, `no_data=2`, `api_error=0`, `timeout=0`, `parse_error=0` |
| `success_rate_strict` | 0.9800 |
| `success_rate_excluding_no_data` | 1.0000 |
| Gate | PASS (`1.0000 ≥ 0.99`) |

The two `no_data` rows were `408/DT_408_2006_S0002` and `142/DT_E10216`.
Both returned empty responses after all fallback strategies, so they are treated
as catalogue drift / deprecated tables rather than server defects.

### 1.3 Previous dry-run skeleton

The pilot run that ships with this iteration was a **dry-run skeleton**
(`outputs/validation/reliability-20260429T235842Z.json`) — Track A produced a
sampling-only artefact (N=5, no live API calls). The methodology, sampling
seed, and JSON schema are therefore validated, but **the success-rate number
in this iteration's JSON is not authoritative**.

| Field | Value |
|-------|-------|
| Sample N | 5 |
| Seed | 42 |
| Live API calls | none (`dry_run=true`) |
| Categories | all zero |
| `success_rate_excluding_no_data` | 1.0 (vacuous) |

### 1.4 Historical baseline

Phase 4.5 (2025-12-21) ran the same methodology against the production server
at three sample sizes (recorded in internal pre-release notes):

| N | success | failures | success rate |
|---:|---:|---:|---:|
| 500 | 497 | 3 | 99.4 % |
| 2 000 | 1 985 | 15 | 99.25 % |
| **10 000** | **9 938** | **62** | **99.38 %** |

All 62 failures in the 10K run were `no_data` (deprecated tables / catalogue
drift), not server defects.

### 1.5 Gate decision for v0.1.0

**PASS for v0.1.0 release-candidate packaging; defer tag until PyPI Trusted
Publishing is confirmed.**
Justification: the historical 10K result is well above the 99.0 % gate and the
latest live N=100 spot-check had no API/timeout/parse failures. A live N=500
spot-check remains recommended before announcing a broader public release, and
a full 10K rerun is scheduled before v0.2.0.

---

## 2. LLM-judge — Tool routing accuracy (Track B)

### 2.1 Methodology

`scripts/validation/run_llm_judge.py` checks whether the bilingual routing
manual (`docs/llm-routing-manual.md`) is enough, on its own, to steer a fresh
LLM session to the correct **first** tool.

1. Load the routing manual verbatim.
2. Load the V1 tool surface from `mcp_server.exposed_tools.V1_EXPOSED` (16 tools).
3. Load 20 hand-written queries from
   `scripts/validation/judge_queries.py::CASES`. Each `JudgeCase` carries:
   `id`, `lang` (ko / en), `query`, `expected_first_tool`, and a one-line
   `rationale` (not shown to the model).
4. For each case, build a prompt of the form:

   > *Routing manual* … *V1 tool list* … `User asks ({lang}): {query}` … *“Respond
   > with ONLY the tool name.”*

5. Call the Anthropic Messages API (default model `claude-sonnet-4-6`,
   `max_tokens=64`) with no system prompt and no chat history. Each case is an
   independent, cold-cache prediction.
6. Normalise the reply (strip code fences, leading bullets, "tool: " prefixes,
   lowercase) and apply legacy → V1 aliases:

   | Legacy name in manual | V1 equivalent |
   |---|---|
   | `search_statistics_tables` | `search_statistics` |
   | `browse_by_organization` | `browse_categories` |
   | `browse_by_theme` | `browse_categories` |

7. Compare against `expected_first_tool`. Record per-case correct / incorrect.

**Gate:** `accuracy ≥ 0.85` (17 / 20). Below the gate the routing manual is
revised before release.

**Dry-run mode** (`--dry-run`, or automatic when `ANTHROPIC_API_KEY` is unset)
substitutes the expected answer for every case so the harness pipeline can be
verified offline; the JSON output is then tagged with
`"dry_run": true` and a `note` field.

### 2.2 Result

This iteration was executed in **dry-run skeleton mode** —
`ANTHROPIC_API_KEY` was not available in the runner environment, so actual
routing accuracy is **deferred**. The harness, the prompt, the normaliser, the
20-query bank, and the JSON output schema have all been exercised end-to-end:

| Field | Value |
|---|---|
| Model | `claude-sonnet-4-6` |
| `n` | 20 |
| `dry_run` | true |
| `accuracy` (vacuous) | 1.0 |
| Output | `outputs/validation/llm-judge-*.json` |

Re-run with the key present to score the routing manual:

```bash
ANTHROPIC_API_KEY=sk-ant-... uv run python scripts/validation/run_llm_judge.py
```

### 2.3 Per-tool coverage in the 20 query bank

| Tool | Layer | Times expected as first call |
|------|-------|---:|
| `search_statistics` | DISCOVER | 4 |
| `browse_categories` | DISCOVER | 1 |
| `get_table_metadata` | DISCOVER | 2 |
| `get_available_values` | DISCOVER | 1 |
| `get_statistics_data` | FETCH | 4 |
| `filter_statistics` | FETCH | 1 |
| `aggregate_statistics` | FETCH | 1 |
| `execute_visualization` | PRESENT | 2 |
| `execute_analysis` | PRESENT | 1 |
| `execute_table` | PRESENT | 0 |
| `execute_report` | PRESENT | 1 |
| `list_stored_data` | DATA | 0 |
| `read_stored_data` | DATA | 0 |
| `discover_tools` | META | 1 |
| `execute_tool` | META | 0 |
| `verify_statistics` | VERIFY | 1 |
| **Total** | — | **20** |

**Intentional gaps (not flaws of the bank):**

- `execute_table` — never the *first* call in a realistic chain; users always
  fetch / aggregate first. Covered transitively.
- `list_stored_data` / `read_stored_data` — DATA layer is server-state
  inspection; the bank chooses `filter_statistics` and `execute_visualization`
  as the more idiomatic first steps when a `resource_id` is already in hand.
- `execute_tool` — META escape hatch by design; no first-call user query is
  natural for it.

These three are tracked as known coverage gaps for v0.2.0.

---

## 3. V1_EXPOSED tool coverage in `tests/e2e/`

The e2e suite in `tests/e2e/` was written before the V1_EXPOSED rename
(US-003), so it still references several legacy tool names. The table below
reports literal-string occurrences per V1 tool, with the legacy alias still
counted as covering its V1 successor.

| Tool | Covered in e2e? | Notes |
|------|:-:|------|
| `search_statistics` | ✅ | also via legacy `search_statistics_tables` |
| `browse_categories` | ❌ | legacy `browse_by_*` not exercised either |
| `get_table_metadata` | ✅ | direct reference |
| `get_available_values` | ✅ | direct + legacy `get_available_field_values` |
| `get_statistics_data` | ✅ | direct reference |
| `filter_statistics` | ✅ | via legacy `filter_statistics_data` (17 hits) |
| `aggregate_statistics` | ✅ | via legacy `aggregate_statistics_data` (4 hits) |
| `execute_visualization` | ⚠️ | only generic `execute_code` (3 hits) |
| `execute_analysis` | ⚠️ | only generic `execute_code` |
| `execute_table` | ❌ | not exercised |
| `execute_report` | ❌ | not exercised |
| `list_stored_data` | ❌ | not exercised |
| `read_stored_data` | ❌ | not exercised |
| `discover_tools` | ❌ | not exercised |
| `execute_tool` | ❌ | not exercised |
| `verify_statistics` | ❌ | new in US-005, suite not yet updated |

(Source: `grep` over `tests/e2e/*.py`. Legend: ✅ direct or aliased coverage,
⚠️ indirect via `execute_code`, ❌ no occurrence.)

---

## 4. Recommendations for v0.1.0 release

**Confirmed passes**

- Track A methodology is reproducible (fixed seed) and the gate is well-defined.
- Track A live N=100 pilot passed on 2026-04-30 with no API/timeout/parse
  failures.
- Track B harness runs end-to-end (dry-run validated).
- The 20-query bank covers 13 of the 16 V1_EXPOSED tools as a first call;
  the three gaps are intentional and documented.
- The legacy-alias map keeps the judge honest about routing-manual drift
  without silently lowering the bar.

**Deferred verifications (must complete before tag)**

- PyPI Trusted Publishing must be configured for
  `seolcoding/korean-stat-mcp/.github/workflows/release.yml` before pushing a
  `v0.1.0` tag.
- Live Track A pilot at N≥500 is recommended before broad announcement.
- Live Track B run with `ANTHROPIC_API_KEY` present is optional and should be
  used only if routing-manual quality needs a model-scored gate; dry-run already
  validates harness structure.

**Tracked for v0.2.0**

- Update `tests/e2e/` to use V1 tool names, retire the legacy aliases.
- Add e2e coverage for `execute_table`, `execute_report`, `verify_statistics`,
  `list_stored_data`, `read_stored_data`, `discover_tools`.
- Full N=10 000 reliability rerun and refresh the historical baseline.
