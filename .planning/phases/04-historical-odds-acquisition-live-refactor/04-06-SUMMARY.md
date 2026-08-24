---
phase: 04-historical-odds-acquisition-live-refactor
plan: 06
subsystem: value-detector
tags: [refactor, tdd, verdi-deteksjon, importable-module, odds-api]

# Dependency graph
requires:
  - phase: 02 (Shared Core extraction)
    provides: "strategy.py's fjern_vigorish/beregn_value_og_ev, features.py's bygg_feature_rad/snitt_fra_kamplogg, teams.py's finn_lag_id, config.py's thresholds"
  - phase: 04-04
    provides: "odds.py's hent_live_odds() — the live-odds fetch this plan repoints at, replacing the inline HTTP block"
provides:
  - "verdi_deteksjon.py — importable value-detection core (finn_value_bets, last_modell, hent_siste_lagstats, gjeldende_sesong, skriv_value_bets_csv) with zero import-time network/pickle/CSV side effects"
  - "04_value_detector.py reduced to a thin CLI wrapper (main() + __main__ guard) that calls into odds.py and verdi_deteksjon.py"
affects: [04-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "verdi_deteksjon.py follows the same extraction shape as skadefilter.py (04-02): flat module at repo root, Norwegian docstrings/identifiers, snake_case, no type hints"
    - "Keyword-injection points (kamper=None, hent_lagstats=None) are the testability seam — finn_value_bets hits the network only when both are None, mirroring skadefilter's siste3=None/sesong_snitt=None pattern"

key-files:
  created: [verdi_deteksjon.py, tests/test_verdi_deteksjon.py]
  modified: [04_value_detector.py, .planning/REQUIREMENTS.md]

key-decisions:
  - "gjeldende_sesong() duplication between verdi_deteksjon.py and skadefilter.py documented, not fixed — same treatment 04-02-SUMMARY.md gave it and 02-05-SUMMARY.md gave the DIFF_-column divergence; flagged as a Phase 5 consolidation candidate in this module's own docstring"
  - "Docstring prose referencing the removed inline HTTP call was reworded from the literal substring 'requests.get' to avoid self-tripping the plan's own grep-based acceptance check (grep -c \"requests.get\" verdi_deteksjon.py must return 0) — same self-reference pitfall 04-04-SUMMARY.md hit with load_dotenv()"

patterns-established: []

requirements-completed: []  # ODDS-02 not fully complete — 06_bot.py's in-process wiring still lands in 04-08

# Metrics
duration: ~10min
completed: 2026-08-24
---

# Phase 4 Plan 6: Verdi-Deteksjon Extraction Summary

**Extracted 04_value_detector.py's entire value/EV decision logic (odds/model scoring loop, threshold checks, CSV writer) into an importable verdi_deteksjon.py module via TDD, and repointed its live-odds fetch at odds.hent_live_odds() (D-07) — 04_value_detector.py is now a 59-line CLI wrapper, and the last inline Odds API HTTP call in this repo is gone.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-08-24 (continuation of Phase 4 execution)
- **Completed:** 2026-08-24
- **Tasks:** 2 completed
- **Files modified:** 4 (verdi_deteksjon.py + tests/test_verdi_deteksjon.py created, 04_value_detector.py rewritten, .planning/REQUIREMENTS.md updated)

## Accomplishments

- `verdi_deteksjon.py` created: every threshold, comparison, rounding, format specifier, print string and dict key from `04_value_detector.py` carried over verbatim, now as importable functions (`gjeldende_sesong`, `hent_siste_lagstats`, `last_modell`, `finn_value_bets`, `skriv_value_bets_csv`), plus the `KOLONNER` module constant
- Zero network calls, pickle loads, or CSV writes at import time — proven by `test_import_verdi_deteksjon_gjor_ingen_nettverkskall`, which reloads the module with `teamgamelogs.TeamGameLogs` monkeypatched to raise `AssertionError`
- `finn_value_bets(modell, feature_kolonner, kamper=None, api_nokkel=None, hent_lagstats=None)` is testable with zero network access via keyword-injected `kamper`/`hent_lagstats`; `kamper is None` now resolves via `odds.hent_live_odds(api_nokkel)` — the old inline `requests.get` block against The Odds API is gone from this codebase entirely (only `odds.py` makes that call now)
- `04_value_detector.py` reduced from 254 to 59 lines: docstring + `main()` + `if __name__ == "__main__":` guard only — no `requests`, `nba_api`, `pickle` or threshold constants remain in the file
- Missing-pickle path (`nba_modell.pkl` not found) now produces a clean Norwegian instruction + `sys.exit(1)` instead of an unhandled traceback — the wrapper is the natural place to make that failure mode explicit
- Full TDD gate followed for Task 1: RED commit (9 failing tests, `verdi_deteksjon` module didn't exist) → GREEN commit (implementation, all 9 tests pass, full 117-test suite green)
- Standalone smoke-checked: `ODDS_API_NOKKEL= venv/bin/python 04_value_detector.py` exits 1 and prints the Phase 1 `.env.example` guidance, proving the fail-fast key check survived the move into `odds.py`

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for verdi_deteksjon.py** - `f572874` (test)
2. **Task 1 (GREEN): verdi_deteksjon.py implementation** - `5502cd0` (feat)
3. **Task 2: Reduce 04_value_detector.py to thin CLI wrapper** - `5c9c093` (refactor)

## Files Created/Modified

- `verdi_deteksjon.py` (new, 227 lines) - importable value-detection core: `KOLONNER` constant, `gjeldende_sesong()`, `hent_siste_lagstats(team_id, antall_kamper=10, sesong=None)`, `last_modell(sti="nba_modell.pkl")` (returns `(modell, feature_kolonner)`, imports `KalibrertModell` from `modell_utils` so the pickle can unpickle per HYG-02), `finn_value_bets(modell, feature_kolonner, kamper=None, api_nokkel=None, hent_lagstats=None)` (the full odds/model scoring loop, best-odds-across-bookmakers selection, `fjern_vigorish`/`beregn_value_og_ev` threshold checks), `skriv_value_bets_csv(value_bets, sti="value_bets_idag.csv")` (always-write behaviour with its load-bearing 2026-08-19-bug comment carried over word for word)
- `tests/test_verdi_deteksjon.py` (new, 253 lines) - 9 tests: no-network-on-import proof, exact-dict regression test (`test_finn_value_bets_uendret_output`, expected values computed by hand — impl_hjemme=6/13, impl_borte=7/13), unresolvable-team-name skip, missing-lagstats skip, no-h2h-odds skip, under-threshold non-flag, out-of-range-odds non-flag, best-odds-across-bookmakers selection, empty-list CSV header-only write
- `04_value_detector.py` (rewritten, 254 → 59 lines) - docstring (updated to point at `verdi_deteksjon.py`/`odds.py`) + `main()` (`odds.hent_api_nokkel()`, model load with `try/except FileNotFoundError`, three narration blocks in original order, `verdi_deteksjon.finn_value_bets(...)`, summary banner, `verdi_deteksjon.skriv_value_bets_csv(...)`, closing responsible-gambling warning) + `if __name__ == "__main__": main()`
- `.planning/REQUIREMENTS.md` - ODDS-02 traceability note updated: both extraction halves (skadefilter.py 04-02, verdi_deteksjon.py 04-06) now done; `06_bot.py`'s in-process wiring explicitly still pending, not marked complete, per this plan's own instruction

## Decisions Made

- Documented (did not fix) the `gjeldende_sesong()` duplication between `verdi_deteksjon.py` (this plan) and `skadefilter.py` (04-02) — both derive the same NBA-season string independently. Not one of Phase 2 D-03's four originally-scoped duplicates; flagged as a Phase 5 consolidation candidate in this module's own docstring, mirroring `04-02-SUMMARY.md`'s and `02-05-SUMMARY.md`'s treatment of equivalent findings.
- Reworded two docstring passages that originally used the literal substring `requests.get` (describing the now-removed inline HTTP call) to avoid tripping the plan's own `grep -c "requests.get" verdi_deteksjon.py` acceptance check — same self-reference pitfall `04-04-SUMMARY.md` documented for `load_dotenv()`. Caught and fixed before the GREEN commit, not a follow-up.

## Deviations from Plan

None — plan executed exactly as written. Every interface function signature, threshold, dict key, print string and the `KOLONNER` constant specified in the plan's `<interfaces>` block was implemented verbatim; all acceptance-criteria grep checks passed after the one self-correction above (caught pre-commit, not landed as a failing state).

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. This plan's tests never make a real network call (`kamper`/`hent_lagstats` are always injected in tests); `ODDS_API_NOKKEL` continues to be read the same way it has since Phase 1.

## TDD Gate Compliance

RED gate: `f572874` (`test(04-06): add failing tests for verdi_deteksjon.py extraction`) — confirmed failing before `verdi_deteksjon.py` existed (`ModuleNotFoundError: No module named 'verdi_deteksjon'`).
GREEN gate: `5502cd0` (`feat(04-06): implement verdi_deteksjon.py value-detection core module`) — all 9 new tests pass, full 117-test suite green.
No REFACTOR commit needed — the one docstring wording fix (the `requests.get` self-reference) was folded into the GREEN commit itself, caught before commit.
Task 2 (`5c9c093`) was a separate, non-TDD `auto` task per the plan's own task-type declaration.

## Next Phase Readiness

- `verdi_deteksjon.finn_value_bets`/`last_modell`/`skriv_value_bets_csv` are ready for `06_bot.py` (plan 04-08) to import and call in-process, removing the second half of the `subprocess.run(["04_value_detector.py"])` shell-out and its `python3.10`-hardcoded `PYTHONPATH` workaround
- Exactly one place in the repo now makes an HTTP call to The Odds API (`odds.py:246`), verified via `grep -rn "requests.get(" --include="*.py" . | grep -v venv/`
- No blockers. Zero behaviour, threshold, or output-string change from the pre-extraction script — verified both by the 9 new unit tests and by the standalone `ODDS_API_NOKKEL=` fail-fast smoke check.

---
*Phase: 04-historical-odds-acquisition-live-refactor*
*Completed: 2026-08-24*

## Self-Check: PASSED

- FOUND: verdi_deteksjon.py
- FOUND: tests/test_verdi_deteksjon.py
- FOUND: 04_value_detector.py
- FOUND: f572874 (test RED commit)
- FOUND: 5502cd0 (feat GREEN commit)
- FOUND: 5c9c093 (refactor commit)
