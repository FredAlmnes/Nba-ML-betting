# Phase 2: Shared Core Extraction & Test Foundation - Context

**Gathered:** 2026-08-20
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase extracts the currently-duplicated feature engineering, team-name resolution, and value/stake strategy logic into shared, importable, pure-function modules so the live path and the future backtest path (Phase 5) can never silently drift apart again — this codebase has already drifted twice (feature logic between `02_feature_engineering.py`/`04_value_detector.py`; team lookup independently reimplemented in `04_value_detector.py`, `05_skadefilter.py`, `06_bot.py`, `debug_kamp.py`). It also adds this repo's first automated tests (pytest), covering the stake-sizing function and bet-dedup logic, plus a parity/determinism test proving the shared logic is safe to call identically from both the live path and a future backtest.

It does NOT touch model calibration (Phase 3), does NOT fetch historical odds or refactor `06_bot.py`'s subprocess orchestration into direct imports (Phase 4/ODDS-02), and does NOT build the backtest engine itself (Phase 5).

</domain>

<decisions>
## Implementation Decisions

### Package structure
- **D-01:** Create `features.py`, `strategy.py`, `teams.py` as **flat modules at the repo root**, matching the existing flat-script convention (no new `nba_betting/` package directory yet). Milestone-level research (`.planning/research/ARCHITECTURE.md`) recommends a full `nba_betting/` package eventually, but that restructure is only actually load-bearing once `backtest/` and `live/` need to coexist as separate execution paths — that's Phase 4/5. Introducing a full package now would be premature scope for what CORE-01 through CORE-04 actually require.
- **D-02:** `modell_utils.py` (the `KalibrertModell` calibration wrapper) is NOT touched or renamed in this phase — it already serves as the "model" concern and calibration fixes are explicitly Phase 3's job (CALIB-01/02).

### Team-name resolution (`teams.py`)
- **D-03:** Confirmed via direct grep this session: team lookup is independently reimplemented in exactly 4 places — `04_value_detector.py:129-135` (lowercase full_name/abbreviation/nickname keys, substring fallback), `05_skadefilter.py:168-172` (full_name/nickname keys only, no abbreviation), `06_bot.py:76-89` (full_name/nickname/abbreviation, `finn_lag()` closure with substring fallback), `debug_kamp.py:13-19` (same three keys, dict comprehension style). `teams.py` should provide a single canonical resolver function that supersedes all four.
- **D-04:** `debug_kamp.py` is currently **untracked** (never committed to git at all, confirmed via `git status`). Whether it gets tracked as part of this phase's `teams.py` migration, or left untracked/untouched (its own separate, lower-priority hygiene item), is a planner/research judgement call — it's an intentional manual debug utility per `.planning/codebase/ARCHITECTURE.md`, not part of the production pipeline.

### Feature engineering (`features.py`)
- **D-05:** Confirmed duplication is between `02_feature_engineering.py` (historical/batch, rolling 10-game averages with `shift(1)`) and the inline feature-building block in `04_value_detector.py` (live/online) — per `.planning/codebase/ARCHITECTURE.md`. `features.py` should be the single implementation both import, ideally parameterized by an `as_of`-style cutoff so the same function is safe for a future walk-forward backtest (Phase 5) without modification — per `.planning/research/ARCHITECTURE.md`'s recommended pattern. Do not change the actual feature set/columns in this phase — this is an extraction, not a feature redesign.

### Value/stake strategy (`strategy.py`)
- **D-06:** Extract the value/EV calculation and vig-removal logic currently in `04_value_detector.py`, plus the half-Kelly stake-sizing function `beregn_innsats` currently in `06_bot.py`, into `strategy.py` as pure functions (inputs in, decision out — no I/O, no global state). This is what CORE-03's unit tests will exercise directly.
- **D-07:** Per Phase 1's D-05/D-07 (still binding): do NOT change `MIN_VALUE_TERSKEL`, `MAX_ODDS`, or the Kelly fraction values themselves while extracting them — CORE-02's single source-of-truth config module is in scope for this phase (it's explicitly a Phase 2 requirement), but the *values* stay exactly what they are today (0.05 / 4.00 / half-Kelly) until Phase 5's backtest validates different ones.

### Pre-existing uncommitted work in files this phase touches
- **D-08:** Confirmed via `git status` this session: `05_skadefilter.py` and `06_bot.py` still carry the user's own pre-existing uncommitted changes (88 and 1009 lines respectively, per Phase 1's pre-flight inspection) — these are the exact files `teams.py`/`strategy.py` extraction must edit. Following the precedent set in Phase 1 (Plan 01-01), the planner should build an equivalent pre-flight checkpoint plan that inspects current `git diff` on these files and asks the developer whether to include the pre-existing WIP in this phase's commits, before any extraction work stages them. Do not assume "include" by default this time — ask fresh, since the WIP has had more time to diverge since Phase 1's decision.
- **D-09:** `03_tren_modell.py` also has pre-existing uncommitted changes but is NOT touched by this phase (no team lookup, no duplicated feature/strategy logic identified in it) — leave it untouched, same as Phase 1.

### Testing (CORE-03, CORE-04)
- **D-10:** `pytest` is the test framework (per `.planning/research/SUMMARY.md` and Phase 2's own `.planning/research/SUMMARY.md` phase table) — this is the first automated test suite in the repo. Tests live in a `tests/` directory at repo root.
- **D-11:** CORE-03 unit tests must cover `beregn_innsats` (stake sizing) and the bet-dedup logic (`(kamp, bet, kamp_dato)` key matching in `06_bot.py::plasser_bets`) directly, now that they're extracted into testable pure functions.
- **D-12:** CORE-04's "parity/leakage regression test" cannot yet be a true live-vs-backtest integration test — the backtest engine doesn't exist until Phase 5. Per `.planning/research/ARCHITECTURE.md`'s guidance ("add a parity/regression test that asserts both paths produce identical decisions for a fixed historical date"), scope this down to: a determinism/referential-transparency test proving `features.py`/`strategy.py` functions given the same inputs (including a fixed `as_of` date) always produce the same output — i.e., proving the shared functions are safe to call identically from two different call sites, without needing the actual second call site (the backtest) to exist yet. Flag this scoping interpretation explicitly to the phase researcher/planner rather than silently deciding it — it's the one place this phase's requirement slightly outruns what's buildable yet.

### Claude's Discretion
- Exact function signatures/names within `features.py`/`strategy.py`/`teams.py` (e.g., `hent_lag_oppslag()` vs `finn_lag()` — `.planning/codebase/ARCHITECTURE.md` suggested `hent_lag_oppslag()`/`finn_lag()` as an example naming, not a locked requirement)
- Exact shape of the CORE-02 single source-of-truth config module (a `config.py` with module-level constants vs. a small dataclass) — either is fine as long as both live and (future) backtest import the same values from one place
- Whether `debug_kamp.py` gets tracked in git as part of this phase (D-04)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & scope
- `.planning/REQUIREMENTS.md` — CORE-01, CORE-02, CORE-03, CORE-04 (exact requirement text)
- `.planning/ROADMAP.md` — Phase 2 section (goal, success criteria, depends on Phase 1)
- `.planning/PROJECT.md` — Core Value and Context sections (updated after Phase 1 completion)

### Architecture guidance (already answers most "how" questions for this phase)
- `.planning/research/ARCHITECTURE.md` — the milestone-level research that specifically designed this extraction: shared-core pattern (NautilusTrader/QuantConnect/Freqtrade precedent), `as_of`-aware `features.py`, pure-function `strategy.py`, single `teams.py` resolver, and the parity-test recommendation
- `.planning/research/PITFALLS.md` — Pitfall on train/serve feature skew and zero test coverage on money-math functions, both directly addressed by this phase
- `.planning/codebase/ARCHITECTURE.md` — documents the exact current duplication (file:line references) this phase must resolve

### Known duplication to resolve (verified this session)
- `04_value_detector.py:129-135` — team lookup implementation 1
- `05_skadefilter.py:168-172` — team lookup implementation 2
- `06_bot.py:76-89` — team lookup implementation 3 (`finn_lag()`)
- `debug_kamp.py:13-19` — team lookup implementation 4 (untracked file)
- `02_feature_engineering.py` vs. inline block in `04_value_detector.py` — feature engineering duplication
- `06_bot.py::beregn_innsats` — stake-sizing function to extract and test

### Phase 1 precedent (safety pattern to reuse)
- `.planning/phases/01-repo-hygiene-config-remediation/01-01-PLAN.md` — the pre-flight-checkpoint pattern for handling pre-existing uncommitted WIP before staging; `.planning/phases/01-repo-hygiene-config-remediation/01-01-SUMMARY.md` — the decisions recorded last time (context only, do not assume they still apply — D-08 requires asking fresh)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `modell_utils.py` — already the working example of a shared module imported by multiple scripts (`03_tren_modell.py`, `04_value_detector.py`) — follow its import pattern for the new `features.py`/`strategy.py`/`teams.py`.
- Norwegian identifier convention is well-established (`lag_oppslag`, `finn_lag`, `beregn_innsats`) — new shared modules should keep this convention per `.planning/codebase/CONVENTIONS.md`.

### Established Patterns
- `sys.exit(1)` with explanatory comment for fatal errors (used in `04_value_detector.py:63-67`, now also in the Phase 1 env-var fail-fast) — follow for any new fatal-error paths in extracted modules.
- `shift(1)` is already correctly used in `02_feature_engineering.py`'s rolling-window calculation — leakage-safety is already right there; the bug is duplication, not the leakage-safety logic itself.

### Integration Points
- `04_value_detector.py` imports `KalibrertModell` from `modell_utils` — the same import pattern extends naturally to `from features import ...`, `from strategy import ...`, `from teams import ...`.
- `06_bot.py` currently subprocesses `04_value_detector.py`/`05_skadefilter.py` rather than importing them — that subprocess boundary is explicitly Phase 4's job (ODDS-02) to remove, NOT this phase's. This phase's new shared modules should be written so they're *ready* to be imported directly later, but this phase does not need to change `06_bot.py`'s subprocess orchestration itself.

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the decisions above — open to standard approaches for exact function signatures and test organization.

</specifics>

<deferred>
## Deferred Ideas

- Full `nba_betting/` package restructure (data/, backtest/, live/ subdirectories) — deferred to Phase 4/5 when backtest/live separation actually requires it (D-01)
- Refactoring `06_bot.py` to import the shared core directly instead of subprocessing — explicitly Phase 4 (ODDS-02)
- Any change to feature set, thresholds, or Kelly fraction values — explicitly Phase 5, backtest-gated

### Reviewed Todos (not folded)

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 2-Shared Core Extraction & Test Foundation*
*Context gathered: 2026-08-20*
