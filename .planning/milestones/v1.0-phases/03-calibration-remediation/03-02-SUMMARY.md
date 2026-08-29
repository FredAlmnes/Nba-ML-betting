---
phase: 03-calibration-remediation
plan: 02
subsystem: calibration
tags: [xgboost, isotonic-regression, scikit-learn, chronological-split, calibration-leak-fix]

requires:
  - phase: 03-calibration-remediation
    provides: "kalibrering.del_kronologisk_3veis — pure 3-way chronological split-boundary function (Plan 03-01)"
provides:
  - "3_tren_modell.py rewired onto a 3-way tren/kalibrer/test chronological split"
  - "XGBoost early stopping evaluated on kalibreringssettet, never on testsettet (D-04)"
  - "Isotonic calibrator fit exclusively on kalibreringssettet, evaluated exclusively on testsettet (CALIB-01 fix)"
  - "Console reliability table (10 buckets) computed only from out-of-sample test-slice predictions, no NaN cells"
  - "3 new source-level guard tests (7 total in tests/test_calibrering_split.py) preventing the leak from silently returning"
affects: [phase-4-odds-refactor, phase-5-backtest-engine]

tech-stack:
  added: []
  patterns:
    - "Source-text guard tests for scripts that cannot be imported (digit-leading module name, top-level training run at import time) — regex-match against comment-stripped source"
    - "Explicit FITTET/EVALUERT console labeling for any fit/eval slice split, so leakage is visually obvious in stdout, not just in code"

key-files:
  created: []
  modified:
    - 03_tren_modell.py
    - tests/test_calibrering_split.py

key-decisions:
  - "Reused the developer's pre-existing uncommitted 03_tren_modell.py WIP as the starting scaffold (KalibrertModell wiring, console-table diagnostic format) but replaced its split/fit/eval logic entirely, per 03-CONTEXT.md D-01"
  - "Calibrated log-loss (0.7356) came out worse than uncalibrated (0.6170) on the real nba_features.csv test slice — left visible in console output with the plan's own explanatory note (small kalibreringssett likely overfit) rather than hidden or 'fixed', since this is a genuine finding for Phase 5 to investigate, not a bug in this plan's logic"

patterns-established:
  - "Pattern 1: When wiring a shared split/calibration helper into a pedagogical top-to-bottom script, keep exact variable names the plan's guard tests expect (X_kalibrer, y_kalibrer, y_rå_kalibrer, y_kal_test) so downstream regression tests can regex-match reliably"

requirements-completed: [CALIB-01, CALIB-02]

duration: 8min
completed: 2026-08-23
---

# Phase 3 Plan 2: Fix the Same-Slice Calibration Leak Summary

**`03_tren_modell.py` now fits its isotonic calibrator only on a disjoint kalibreringssett and reports the 10-bucket reliability table exclusively from an out-of-sample testsett, closing the CALIB-01 same-slice leakage bug with 3 new regression-guard tests verified by a negative control.**

## Performance

- **Duration:** 8 min
- **Completed:** 2026-08-23T09:49:13Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- Replaced the 2-way tren/test split with `del_kronologisk_3veis`'s tren/kalibrer/test split (3217/172/249 kamper against the current `nba_features.csv`), with an `ADVARSEL` runtime warning when the kalibreringssett falls under sklearn's ~1000-sample isotonic guidance
- Repointed XGBoost's `early_stopping_rounds` `eval_set` from the test slice to the kalibreringssett (D-04), so the final test slice no longer influences how many trees get built
- Rewrote the calibration section so the isotonic calibrator fits exclusively on `(y_rå_kalibrer, y_kalibrer)` and is evaluated exclusively on `(y_rå_test, y_test)` — the calibrator never sees the test slice during any `.fit()` call
- Console output now explicitly labels which slice was `FITTET` on and which was `EVALUERT` on, with row counts, plus a separate in-sample-only diagnostic block on the kalibreringssett clearly marked "IKKE et mål på generalisering"
- Rebuilt the 10-bucket reliability table to source from the test slice only (bucket counts sum to 249, matching the test-slice size, zero NaN cells)
- Added 3 new source-level pytest guard tests (`tests/test_calibrering_split.py`, now 7 tests total) that regex-match the comment-stripped script source to assert early stopping and the calibrator fit never reference `X_test`/`y_test`, and that `out_of_bounds="clip"` is retained — verified with a negative control (temporarily reverting the eval_set line makes the guard test fail, then reverting back to green)

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace the 2-way split with the 3-way chronological split and repoint early stopping** - `0d317ab` (feat)
2. **Task 2: Fit the calibrator on kalibrer and report the reliability table on test only** - `c630de9` (fix)
3. **Task 3: Add source-level guard tests so test-slice leakage cannot silently return** - `c26c355` (test)

## Files Created/Modified
- `03_tren_modell.py` - Sections 3, 4, and 7 rewritten: 3-way chronological split via `del_kronologisk_3veis`, early stopping repointed to kalibreringssett, isotonic calibrator fit-on-kalibrer/eval-on-test with explicit FITTET/EVALUERT console labeling and an out-of-sample-only reliability table
- `tests/test_calibrering_split.py` - 3 new source-level guard tests appended (`test_early_stopping_bruker_aldri_testsettet`, `test_kalibrator_fittes_kun_pa_kalibreringssettet`, `test_isotonic_klipper_utenfor_omraade`) plus a shared `_treningsskript_kode()` helper that reads `03_tren_modell.py` as comment-stripped text

## Decisions Made
- Used the developer's pre-existing uncommitted WIP as the starting scaffold per D-01, replacing only the split/fit/eval logic that carried the leakage bug — `KalibrertModell` wiring and console-table format were kept
- Left the "calibrated is worse than uncalibrated on this run" result visible in console output rather than suppressing it — the plan explicitly anticipated this as a possible small-sample overfitting signal (RESEARCH.md Pitfall 1) and asked for it to be surfaced, not hidden

## Deviations from Plan

None - plan executed exactly as written. `modell_utils.py` was not touched (D-02 respected); only `03_tren_modell.py` and `tests/test_calibrering_split.py` changed across all three commits.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CALIB-01 and CALIB-02 are both closed: the isotonic calibrator now fits only on the kalibreringssett and is evaluated only on the testsett, with source-level guard tests preventing regression
- `nba_modell.pkl` regenerates in the unchanged `{"modell": KalibrertModell, "feature_kolonner": [...]}` format, so `04_value_detector.py`'s consumption contract is unbroken
- Flag for Phase 5: on the current `nba_features.csv`, calibrated log-loss (0.7356) is worse than uncalibrated (0.6170) on the test slice, and the 172-row kalibreringssett is well under sklearn's ~1000-sample isotonic guidance — this is exactly the small-sample overfitting risk RESEARCH.md called out, and is now honestly visible in console output rather than hidden by same-slice leakage. Worth investigating further once the Phase 5 backtest engine can measure whether this calibration actually helps or hurts strategy ROI.

---
*Phase: 03-calibration-remediation*
*Completed: 2026-08-23*

## Self-Check

- `03_tren_modell.py` exists: FOUND
- `tests/test_calibrering_split.py` exists: FOUND
- `.planning/phases/03-calibration-remediation/03-02-SUMMARY.md` exists: FOUND
- Commit `0d317ab` (feat: 3-way split + eval_set repoint): FOUND
- Commit `c630de9` (fix: kalibrer-fit calibrator, test-only reliability table): FOUND
- Commit `c26c355` (test: source-level guard tests): FOUND

## Self-Check: PASSED
