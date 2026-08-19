# Phase 1: Repo Hygiene & Config Remediation - Context

**Gathered:** 2026-08-19
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase makes the repo trustworthy as a foundation: a fresh clone must load and run without exposing secrets or breaking on a missing file, and there must be exactly one source of truth for what strategy config is actually running (not a documented fix that silently never shipped). It does NOT build the shared config module (that's Phase 2/CORE-02), does NOT touch calibration (Phase 3), and does NOT pick new validated thresholds (Phase 5 — backtest-gated).

</domain>

<decisions>
## Implementation Decisions

### API key handling (HYG-01)
- **D-01:** Move `API_NØKKEL` in `04_value_detector.py` to an environment variable, loaded via `python-dotenv` from a git-ignored `.env` file (matches STACK.md research recommendation). Fail fast with a clear error message if the env var is missing — don't silently continue.
- **D-02:** Key rotation on the-odds-api.com is a manual account action only the user can perform — Claude cannot do this. CONTEXT flags it as a required manual step the user must complete (rotate old key, put new key in `.env`), not something the executor agent can do itself.
- **D-03:** Git history scrubbing (BFG/`git filter-repo` to remove the key from all past commits) is explicitly OUT OF SCOPE for this phase. It's a destructive, force-push-requiring operation on a public repo that may have been cloned/forked by others — requires explicit separate user approval outside of an autonomous phase execution. Rotating the key neutralizes the practical risk (old key becomes worthless) without needing history rewrite. Noted in Deferred Ideas.

### modell_utils.py tracking (HYG-02)
- **D-04:** Simply `git add modell_utils.py` and commit it — no code changes needed, it's already correct per ARCHITECTURE.md, just untracked. Verify `.gitignore` doesn't have a pattern accidentally excluding it.

### Reconciling the documented fix vs. running code (HYG-03)
- **D-05:** Do NOT apply the old proposed threshold values from `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` (`MIN_VALUE_TERSKEL=0.20`, `MAX_ODDS=2.50`) into the running code now. Per PROJECT.md's core value and Phase 5's whole purpose, threshold values must come from backtest validation, not another guess — applying the old report's numbers now would repeat exactly the pattern this project is trying to fix.
- **D-06:** Instead, mark both documents as historical/superseded: add a clear header note to `KALIBRERING_RAPPORT.md` and `ENDRINGER_SUMMARY.txt` stating they describe a fix that was drafted but never deployed, and that validated threshold values will come from the Phase 5 backtest instead. Leave the currently-running thresholds (`MIN_VALUE_TERSKEL=0.05`, `MAX_ODDS=4.00`) as-is — don't change strategy behavior in this phase, only fix the doc/code mismatch so it's no longer silently misleading.
- **D-07:** Do not build the shared config module here — that's explicitly Phase 2 (CORE-02). This phase's job is just to stop the docs from lying about what's running.

### Scratch/build artifacts
- **D-08:** `_linux_pkgs/`, `_pip_tmp/`, `_wheels/`, `_test.bin`, `test_write.tmp` look like accidental local environment-setup artifacts (pip cache/build scratch), not intentional project files. Recommend adding matching patterns to `.gitignore`. **Do not delete these files without explicit user confirmation during execution** — they're untracked but may still be something the user wants to keep locally; flag them for the user to confirm deletion rather than having the executor remove them silently.
- **D-09:** `debug_kamp.py` is an existing, intentional manual debug utility (per ARCHITECTURE.md) — out of scope for this phase, leave as-is.

### Claude's Discretion
- Exact wording of the "superseded" header note on the two markdown reports — executor can phrase this naturally as long as it's unambiguous that the proposed values were never deployed and validated values will come from Phase 5.
- Whether to keep `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` at repo root or move them into a `docs/` or `.planning/` archive folder — either is fine as long as the supersession note is added; don't delete them, they're useful history.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope
- `.planning/REQUIREMENTS.md` — HYG-01, HYG-02, HYG-03 (exact requirement text)
- `.planning/ROADMAP.md` — Phase 1 section (goal, success criteria)
- `.planning/PROJECT.md` — Core Value and Context sections (why remediation-first matters)

### Known issues driving this phase
- `.planning/codebase/CONCERNS.md` — documents the leaked key, untracked file, and doc/code drift as already-confirmed issues
- `.planning/codebase/INTEGRATIONS.md` — The Odds API integration details
- `04_value_detector.py:30` — the hardcoded `API_NØKKEL` line to fix
- `KALIBRERING_RAPPORT.md`, `ENDRINGER_SUMMARY.txt` (repo root) — the documented-but-undeployed fix to mark as superseded
- `.gitignore` (repo root) — already excludes `.env`; verify `modell_utils.py` isn't accidentally excluded, add scratch-artifact patterns

### Research
- `.planning/research/STACK.md` — recommends `python-dotenv` for env-var config, independent of the backtesting work
- `.planning/research/PITFALLS.md` — Pitfall 5/6 (config drift, untracked file) — confirms these as already-materialized risks, not hypothetical

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.gitignore` already has a pattern for `.env` — the env-var approach for the API key slots into an existing convention, not a new one.

### Established Patterns
- Norwegian identifiers throughout (`API_NØKKEL`, not `API_KEY`) — keep the env var name consistent with this, e.g. `ODDS_API_NØKKEL` or similar, matching the Norwegian-identifier convention documented in `.planning/codebase/CONVENTIONS.md`.
- `04_value_detector.py:63-67` already has an explicit `sys.exit(1)` pattern (not bare `exit()`) for fatal errors with a comment explaining why — follow the same pattern for a missing-env-var fatal error.

### Integration Points
- Only `04_value_detector.py` reads `API_NØKKEL` directly (`04_value_detector.py:30,54`) — the env-var change is localized to this one file for HYG-01.
- `modell_utils.py` is imported by both `03_tren_modell.py` and `04_value_detector.py` — HYG-02 unblocks both, not just one.

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the decisions above — open to standard approaches for the env-var loading mechanics and doc archival location.

</specifics>

<deferred>
## Deferred Ideas

- **Git history scrubbing** (removing the leaked key from all past commits via BFG/`git filter-repo`) — belongs outside this phase's autonomous execution. It's destructive (rewrites history, needs force-push) on a repo that's been public since the initial commit. Surface to the user as a separate explicit decision once the key is rotated, not bundled into Phase 1's automated work.
- **Deleting scratch/build artifacts** (`_linux_pkgs/`, `_pip_tmp/`, `_wheels/`, `_test.bin`, `test_write.tmp`) — gitignore them now; actual deletion needs explicit user confirmation, not autonomous execution.

### Reviewed Todos (not folded)

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Repo Hygiene & Config Remediation*
*Context gathered: 2026-08-19*
