---
phase: 04-historical-odds-acquisition-live-refactor
plan: 02
subsystem: injury-filter
tags: [refactor, tdd, skadefilter, importable-module]

# Dependency graph
requires:
  - phase: 02 (Shared Core extraction)
    provides: "teams.py's finn_lag_id() contract, reused here instead of rebuilding a lookup dict"
provides:
  - "skadefilter.py — importable injury-filter core (filtrer_bets_for_skader, sjekk_lag_helse, hent_spillerstatistikk) with zero import-time nba_api calls"
  - "05_skadefilter.py reduced to a thin CLI wrapper (main() + __main__ guard) that calls into skadefilter.py"
affects: [04-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "skadefilter.py follows the Phase 2 shared-module precedent (features.py/teams.py): flat module at repo root, Norwegian docstrings/identifiers, snake_case, no type hints"
    - "Keyword-injection point (siste3=None, sesong_snitt=None) is the testability seam — filtrer_bets_for_skader hits the network only when both are None"

key-files:
  created: [skadefilter.py, tests/test_skadefilter.py]
  modified: [05_skadefilter.py]

key-decisions:
  - "gjeldende_sesong() duplication between skadefilter.py and verdi_deteksjon.py (plan 04-06) documented, not fixed — never scoped as one of Phase 2 D-03's four listed duplicates; consolidation flagged as a Phase 5 item, same treatment 02-05-SUMMARY.md gave the DIFF_-column divergence"

patterns-established:
  - "No-network-on-import proof pattern: monkeypatch the nba_api endpoint class to raise AssertionError, then import/reload the module — if it succeeds, no module-level network call exists"

requirements-completed: [ODDS-02]

# Metrics
duration: ~12min
completed: 2026-08-23
---

# Phase 4 Plan 2: Skadefilter Extraction Summary

**Extracted 05_skadefilter.py's entire injury-filter decision logic (four nba_api calls, top-3-minutes-player availability check) into an importable skadefilter.py module via TDD, leaving 05_skadefilter.py as a 76-line CLI wrapper — 06_bot.py (plan 04-08) can now call the filter in-process instead of shelling out to it.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-08-23T11:17:xxZ (immediately after 04-01)
- **Completed:** 2026-08-23T11:29:53Z
- **Tasks:** 2 completed
- **Files modified:** 3 (skadefilter.py + tests/test_skadefilter.py created, 05_skadefilter.py rewritten)

## Accomplishments

- `skadefilter.py` created: every decision rule, threshold, print string and emoji from the old `05_skadefilter.py` carried over verbatim, now as importable functions (`gjeldende_sesong`, `hent_spillerdata`, `hent_spillerstatistikk`, `hent_toppspillere_for_lag`, `sjekk_spiller`, `sjekk_lag_helse`, `filtrer_bets_for_skader`, `skriv_skadefilter_csv`)
- Zero `nba_api` calls at import time — proven by `test_import_skadefilter_gjor_ingen_nettverkskall`, which reloads the module with `leaguedashplayerstats.LeagueDashPlayerStats` monkeypatched to raise `AssertionError`
- `filtrer_bets_for_skader(value_df, siste3=None, sesong_snitt=None)` is testable with zero network access via keyword-injected DataFrames; both `None` (the default) means "fetch fresh via `hent_spillerstatistikk()`"
- `05_skadefilter.py` reduced from 245 to 76 lines: docstring + `main()` + `if __name__ == "__main__":` guard only — no `nba_api` import, no thresholds remain in the file
- Bare `exit()` on the missing-input-CSV path replaced with `sys.exit(1)`, matching the `04_value_detector.py` convention documented in CLAUDE.md's Error Handling section (a bare `exit()` returns exit code 0 and hides the failure from `06_bot.py`'s subprocess return-code check)
- Full TDD gate followed: RED commit (9 failing tests, `skadefilter` module didn't exist) → GREEN commit (implementation, all 9 tests pass, full 61-test suite green)
- End-to-end smoke test: ran `venv/bin/python 05_skadefilter.py` standalone against the real (gitignored) `value_bets_idag.csv` — reproduced identical console output, status strings (`✅ OK` / `⚠️  USIKKER`), and CSV columns as the pre-extraction script, with real `nba_api` calls succeeding

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for skadefilter.py** - `3a36c62` (test)
2. **Task 1 (GREEN): skadefilter.py implementation** - `ff1c4b3` (feat)
3. **Task 2: Reduce 05_skadefilter.py to thin CLI wrapper** - `bf82120` (refactor)

## Files Created/Modified

- `skadefilter.py` (new, 245 lines) - importable injury-filter core: `ANTALL_TOPPSPILLERE`/`MIN_MINUTTER` constants, `gjeldende_sesong`, `hent_spillerdata(season_type, sesong, last_n=0)`, `hent_spillerstatistikk(sesong=None)` (the four-call fetch-and-merge, returns `(siste3, sesong_snitt)`), `hent_toppspillere_for_lag(sesong_snitt, team_id, antall=ANTALL_TOPPSPILLERE)`, `sjekk_spiller(siste3, spiller_id, spiller_navn, sesong_min)`, `sjekk_lag_helse(siste3, sesong_snitt, team_id, lagnavn)`, `filtrer_bets_for_skader(value_df, siste3=None, sesong_snitt=None)`, `skriv_skadefilter_csv(resultat_df, sti=...)`
- `tests/test_skadefilter.py` (new, 188 lines) - 9 tests: no-network-on-import proof, `sjekk_spiller` decision-rule branches (absent player, low GP, low minutes, OK), `hent_toppspillere_for_lag` limit/sort/threshold, `filtrer_bets_for_skader` with injected frames (no network + row-count preservation + OK/USIKKER status strings), unresolvable-team-name skip behaviour
- `05_skadefilter.py` (rewritten, 245 → 76 lines) - docstring (updated to point at `skadefilter.py`) + `main()` (season print, header, CSV read with `sys.exit(1)` on missing file, empty-input short circuit, `skadefilter.filtrer_bets_for_skader(value_df)` call, summary block, `skadefilter.skriv_skadefilter_csv(resultat_df)`) + `if __name__ == "__main__": main()`

## Decisions Made

- Documented (did not fix) the `gjeldende_sesong()` duplication between `skadefilter.py` (this plan) and `verdi_deteksjon.py` (plan 04-06, formerly `04_value_detector.py`) — both derive the same NBA-season string independently. Not one of Phase 2 D-03's four originally-scoped duplicates and not in this plan's `04-CONTEXT.md` scope; flagged as a Phase 5 consolidation candidate in `skadefilter.py`'s own docstring comment above `gjeldende_sesong()`, mirroring how `02-05-SUMMARY.md` handled the `DIFF_`-column divergence
- Used `monkeypatch.setattr(skadefilter, "finn_lag_id", lambda navn: None)` (rather than crafting an unresolvable team-name string) to deterministically test the unresolvable-team skip path — more robust than relying on `teams.finn_lag()`'s substring fallback never accidentally matching an arbitrary test string

## Deviations from Plan

None — plan executed exactly as written. Every interface function signature, threshold, status string and emoji specified in the plan's `<interfaces>` block was implemented verbatim; all acceptance-criteria grep checks passed (after one self-correction: the file docstring's prose initially contained the literal substring "nba_api", tripping the `grep -c "nba_api" 05_skadefilter.py` check — reworded to "nettverkskall mot NBA sin statistikk-API" before committing, so this was corrected pre-commit and never landed as a failing state).

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. The end-to-end smoke test used the developer's pre-existing, gitignored `value_bets_idag.csv` and made real (free, no-API-key) `nba_api` calls as part of manual verification; no new credentials or setup needed.

## TDD Gate Compliance

RED gate: `3a36c62` (`test(04-02): add failing tests for skadefilter.py extraction`) — confirmed failing before `skadefilter.py` existed (`ModuleNotFoundError: No module named 'skadefilter'`).
GREEN gate: `ff1c4b3` (`feat(04-02): implement skadefilter.py injury-filter core module`) — all 9 new tests pass, full 61-test suite green.
No REFACTOR commit needed for Task 1 — implementation matched the plan's interface spec on the first pass. Task 2 (`bf82120`) was a separate, non-TDD `auto` task per the plan's own task-type declaration.

## Next Phase Readiness

- `skadefilter.filtrer_bets_for_skader` is ready for `06_bot.py` (plan 04-08) to import and call in-process, removing the `subprocess.run(["05_skadefilter.py"])` shell-out and its `python3.10`-hardcoded `PYTHONPATH` workaround
- No blockers. Zero behaviour, threshold, or output string changed from the pre-extraction script — verified both by the 9 new unit tests and by a live end-to-end run against real data.

---
*Phase: 04-historical-odds-acquisition-live-refactor*
*Completed: 2026-08-23*

## Self-Check: PASSED

- FOUND: skadefilter.py
- FOUND: tests/test_skadefilter.py
- FOUND: 3a36c62 (test RED commit)
- FOUND: ff1c4b3 (feat GREEN commit)
- FOUND: bf82120 (refactor commit)
