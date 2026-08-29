---
phase: 05-walk-forward-backtest-engine
plan: 01
subsystem: infra
tags: [pytest, config, gitignore, backtest-engine, decision-gate]

# Dependency graph
requires:
  - phase: 04-odds-integration-and-live-refactor
    provides: config.py single source-of-truth for the 7 live strategy constants, tests/test_strategy.py tripwire pattern
provides:
  - "05-BESLUTNINGER.md — the four-row locked-decision table plans 05-07/05-08/05-09/05-10/05-12/05-13 read as their upstream contract"
  - "config.HOLDOUT_START_DATO = \"2024-10-01\" — the single code-resident holdout boundary constant"
  - "backtests/ and nba_spillerlogg_raw.csv gitignored ahead of any artifact existing"
affects: [05-02, 05-05, 05-07, 05-08, 05-09, 05-10, 05-12, 05-13]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Decision-gate artifact pattern: a blocking checkpoint:decision task writes a fixed-format, greppable markdown table (05-BESLUTNINGER.md) that later plans read as their single source of truth, instead of re-deriving from research/context prose"
    - "Tripwire-test pattern extended: new config constants get an equality assertion in the same test function as the existing 7 live values, so any drift requires a deliberate, reviewable test edit"

key-files:
  created:
    - .planning/phases/05-walk-forward-backtest-engine/05-BESLUTNINGER.md
  modified:
    - config.py
    - tests/test_strategy.py
    - .gitignore
    - tests/test_oppsett.py

key-decisions:
  - "D-05-01: HOLDOUT_START_DATO = \"2024-10-01\" — clean calendar-month boundary, behaviourally identical to the actual 2024-10-22 season start since no games exist in nba_features.csv before that date"
  - "D-05-02: burn-in policy — include all months in the ledger; report headline ROI/CI twice, full-period (headline) AND excluding the first 2-3 months (sensitivity check)"
  - "D-05-03: 'flat' stake in the BT-07 Kelly sweep = a backtest.py-local branch, fixed 2% of config.STARTKAPITAL (20.0 kr) per bet; strategy.py stays untouched"
  - "D-05-04: scratch artifacts (_linux_pkgs/, _pip_tmp/, _pip_home/, _wheels/, _test.bin, test_write.tmp) remain ignore-only, unchanged from Phase 1's D-08 — no deletion in this plan"

patterns-established:
  - "Decision-gate artifact: blocking checkpoint outcomes get recorded as a fixed-format markdown table in a phase-level *-BESLUTNINGER.md file, not just narrated in a SUMMARY — makes them grep-able by every downstream plan in the phase"

requirements-completed: [BT-03]

# Metrics
duration: 6min
completed: 2026-08-26
---

# Phase 5 Plan 01: Lock Pre-Flight Decisions Summary

**Locked the holdout boundary (2024-10-01), burn-in reporting policy, and BT-07 flat-stake definition via a blocking decision gate, then wired `config.HOLDOUT_START_DATO` and two new `.gitignore` rules with tripwire tests protecting both.**

## Performance

- **Duration:** 6 min (continuation after developer answered the blocking checkpoint)
- **Started:** 2026-08-26T12:28:14Z
- **Completed:** 2026-08-26T12:34:25Z
- **Tasks:** 3
- **Files modified:** 5 (1 created, 4 modified)

## Låste beslutninger

- **D-05-01 — `HOLDOUT_START_DATO`:** `"2024-10-01"`
- **D-05-02 — Burn-in/tidlige-måneder rapporteringspolicy:** Inkluder alle måneder i ledgeren; rapporter hovedtall to ganger — full periode (hovedtall) OG ekskludert de første 2-3 månedene (sensitivitetssjekk)
- **D-05-03 — "Flat" i BT-07 Kelly-sweepen:** En `backtest.py`-lokal gren, fast 2% av `config.STARTKAPITAL` (20.0 kr) per bet når sweepens fraksjons-label er "flat"; `strategy.py` er urørt
- **D-05-04 — Scratch-artefakter:** Uendret, kun ignore-only (matcher Phase 1s D-08); ingen sletting utført

Full begrunnelse per beslutning: `.planning/phases/05-walk-forward-backtest-engine/05-BESLUTNINGER.md`.

## Accomplishments
- Blocking pre-flight decision gate resolved — all four Phase 5 open questions (holdout date, burn-in policy, flat-stake definition, scratch-artifact disposition) locked before any backtest code exists
- `config.HOLDOUT_START_DATO` added as the single code-resident holdout boundary, with `test_config_values` now asserting all 8 config constants (7 live + 1 new) as one tripwire block
- `backtests/` and `nba_spillerlogg_raw.csv` gitignored strictly before Plan 05-05/05-08 create those artifacts, verified via `git check-ignore` against not-yet-existing paths and a new exact-line test

## Task Commits

Each task was committed atomically:

1. **Task 1: Blocking pre-flight decision gate — holdout date, burn-in policy, flat-stake definition, scratch disposition** - `695e910` (docs)
2. **Task 2: Add HOLDOUT_START_DATO to config.py and lock its value with the existing tripwire test** - `68c8023` (feat)
3. **Task 3: Gitignore backtests/ and nba_spillerlogg_raw.csv before either artifact exists, with a test asserting both rules** - `6e596b9` (chore)

_No plan-metadata commit yet — created below alongside this SUMMARY, STATE.md, and ROADMAP.md updates._

## Files Created/Modified
- `.planning/phases/05-walk-forward-backtest-engine/05-BESLUTNINGER.md` - Four-row locked-decision table (D-05-01..D-05-04) with Norwegian rationale, read by Plans 05-07/05-08/05-09/05-10/05-12/05-13
- `config.py` - Added `HOLDOUT_START_DATO = "2024-10-01"` after `STARTKAPITAL`; extended module docstring to describe holdout-boundary ownership; the 7 live strategy constants left byte-identical
- `tests/test_strategy.py` - `test_config_values` gained `assert config.HOLDOUT_START_DATO == "2024-10-01"` plus explanatory comment; no new test function
- `.gitignore` - New section (between "Bankroll og bet-historikk" and "Dashboard") adding `backtests/` and `nba_spillerlogg_raw.csv`; six scratch-artifact rules at the bottom untouched
- `tests/test_oppsett.py` - Added `test_backtest_artefakter_er_gitignorert`, asserting both new rules as exact `.gitignore` lines (not substring matches); added `pathlib` import

## Decisions Made
See "Låste beslutninger" above — all four decisions were answered by the developer accepting every RECOMMENDED option at the blocking checkpoint. No agent-side interpretation was required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] config.py docstring initially failed its own grep-based acceptance check**
- **Found during:** Task 2 self-verification
- **Issue:** The first docstring draft explaining the holdout boundary mentioned the literal identifier `HOLDOUT_START_DATO` twice in prose, in addition to the constant definition itself — `grep -v '^#' config.py | grep -c 'HOLDOUT_START_DATO'` returned `3` instead of the plan's required `1`
- **Fix:** Reworded the docstring to describe "holdout-grensen" (the holdout boundary) without repeating the literal constant name, leaving exactly one occurrence (the constant's own definition line)
- **Files modified:** config.py
- **Verification:** `grep -v '^#' config.py | grep -c 'HOLDOUT_START_DATO'` now outputs `1`, matching the plan's acceptance criterion exactly
- **Committed in:** 68c8023 (Task 2 commit)

**2. [Rule 3 - Blocking] System `python3` had no pytest installed; switched to the committed venv's interpreter**
- **Found during:** Task 2 verification (`python3 -m pytest ...` failed with `No module named pytest`)
- **Issue:** The plan's verification commands assume a `python3` with pytest on PATH; this machine's system `python3.14` has no pytest, while the repo's committed `venv/` does
- **Fix:** Ran all verification/test commands via `venv/bin/python3 -m pytest ...` instead of bare `python3`; no code change, no source file affected
- **Files modified:** none
- **Verification:** `venv/bin/python3 -m pytest tests/ -q` → `130 passed`
- **Committed in:** n/a (verification-only, no commit needed)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes are process/verification corrections with zero scope creep — no plan requirement, decision, or generated-code behavior changed as a result.

## Issues Encountered
None beyond the two auto-fixes documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- BT-03 now has a code-resident boundary constant (`config.HOLDOUT_START_DATO`) for Plan 05-07's structural `_sikre_ikke_holdout()` guard to enforce against
- All three downstream-blocking decisions (D-05-01, D-05-02, D-05-03) are locked and greppable in `05-BESLUTNINGER.md`; Plans 05-07 through 05-13 can proceed without re-litigating them
- `backtests/` and `nba_spillerlogg_raw.csv` are gitignored ahead of Plan 05-05 (which creates the player log) and Plan 05-08 (which creates the first run directory) — no risk of either landing in git history
- Full pytest suite green (130 tests: 129 existing + 1 new); no blockers for Plan 05-02

---
*Phase: 05-walk-forward-backtest-engine*
*Completed: 2026-08-26*

## Self-Check: PASSED

All claimed files found on disk (`05-BESLUTNINGER.md`, `config.py`, `.gitignore`, `tests/test_strategy.py`, `tests/test_oppsett.py`, `05-01-SUMMARY.md`) and all three task commit hashes (`695e910`, `68c8023`, `6e596b9`) verified present in `git log --oneline --all`.
