---
phase: 03-calibration-remediation
plan: 01
subsystem: calibration
tags: [pytest, chronological-split, calibration-leak-prevention]
dependency-graph:
  requires: []
  provides:
    - "kalibrering.del_kronologisk_3veis — pure 3-way chronological split-boundary function"
  affects:
    - "03_tren_modell.py (Plan 02 will wire this in, not yet done in this plan)"
tech-stack:
  added: []
  patterns:
    - "Plain-named shared module at repo root, pure/no-I/O, mirroring features.py/modell_utils.py precedent"
key-files:
  created:
    - kalibrering.py
    - tests/test_calibrering_split.py
  modified: []
decisions: []
metrics:
  duration: 5min
  completed: 2026-08-23
---

# Phase 3 Plan 1: Chronological 3-Way Split Scaffold Summary

Extracted a pure, importable `del_kronologisk_3veis` split-boundary function that bisects the existing 2-month holdout window into disjoint tren/kalibrer/test masks, covered by 4 new pytest regression tests guarding CALIB-01's non-overlap property.

## What Was Built

- **`kalibrering.py`** (new, 45 lines): a single pure function `del_kronologisk_3veis(df, dato_kolonne="GAME_DATE_HJEMME", tren_cutoff_mnd=2, kalibrer_cutoff_mnd=1)` that returns three boolean pandas Series (`tren_mask`, `kalibrer_mask`, `test_mask`). It reuses the exact `pd.DateOffset(months=N)` cutoff mechanism already used in `03_tren_modell.py`'s 2-way split, bisecting the same 2-month holdout window rather than widening it (per D-03). Raises `ValueError` with a Norwegian message if `kalibrer_cutoff_mnd >= tren_cutoff_mnd`, which would otherwise silently produce an empty or inverted calibration window. No prints, no file I/O — pure and unit-testable without running the full training script.
- **`tests/test_calibrering_split.py`** (new, 52 lines): 4 Norwegian pytest tests using a deterministic local fixture (150 consecutive daily dates from 2024-10-01, no `random`/`datetime.now()`):
  - `test_maskene_overlapper_aldri` — pairwise non-overlap of all three masks
  - `test_maskene_dekker_alle_rader` — masks jointly cover every row
  - `test_kronologisk_rekkefolge` — strict chronological ordering across all three slices, and all three are non-empty (guards against a future off-by-one silently emptying `kalibrer`)
  - `test_ugyldig_kalibrer_cutoff_gir_verdifeil` — invalid cutoff pair raises `ValueError`

## Why

`03_tren_modell.py` cannot be imported by a test (numeric-leading module name, executes a full XGBoost training run and writes `nba_modell.pkl` at import time). This plan pulls the pure split-boundary logic that Plan 02 will wire into `03_tren_modell.py` into its own plain-named, testable module — the same pattern Phase 2 already established for `features.py`/`strategy.py`/`teams.py`. This is the Wave 0 scaffold; the actual integration into the training script (replacing the 2-way split with a 3-way tren/kalibrer/test split, fitting the isotonic calibrator only on `kalibrer`, evaluating only on `test`) is Plan 02's job.

## Verification

- `venv/bin/python3 -m pytest -q` — 41 passed (37 pre-existing + 4 new), 0.08s wall time (well under 5s budget)
- `venv/bin/python3 -c "from kalibrering import del_kronologisk_3veis"` — imports cleanly from repo root
- `git diff --stat` across both commits shows only `kalibrering.py` and `tests/test_calibrering_split.py` touched — `modell_utils.py` untouched (D-02 lock respected) and `03_tren_modell.py` untouched by this plan
- Manual disjoint/exhaustive check on a 150-row synthetic frame: three masks sum to 150 rows with zero pairwise overlap
- Invalid cutoff pair (`kalibrer_cutoff_mnd=2, tren_cutoff_mnd=2`) confirmed to raise `ValueError` (exit code 1) via CLI probe

## Deviations from Plan

None - plan executed exactly as written.

## Notes

- A pre-existing, unrelated uncommitted diff to `03_tren_modell.py` (adding isotonic-calibration code inline, apparently developer WIP predating this plan) was present in the working tree throughout this plan's execution. It was left untouched and is not part of either commit in this plan — Plan 02 is the correct place to reconcile/replace that inline calibration logic with `kalibrering.del_kronologisk_3veis`.
- `.planning/config.json` also had a pre-existing uncommitted diff (unrelated GSD workflow config fields); left untouched, not committed by this plan.

## Self-Check

- `kalibrering.py` exists: FOUND
- `tests/test_calibrering_split.py` exists: FOUND
- Commit `8c49294` (feat: kalibrering.py): FOUND
- Commit `87ed7b9` (test: test_calibrering_split.py): FOUND

## Self-Check: PASSED
