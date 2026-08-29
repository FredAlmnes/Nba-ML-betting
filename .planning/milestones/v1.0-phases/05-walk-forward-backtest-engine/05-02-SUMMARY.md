---
phase: 05-walk-forward-backtest-engine
plan: 02
subsystem: model-training
tags: [xgboost, isotonic-calibration, tdd, refactor, backtest-engine]

# Dependency graph
requires:
  - phase: 05-walk-forward-backtest-engine
    plan: 01
    provides: config.HOLDOUT_START_DATO, locked Phase 5 pre-flight decisions
  - phase: 03-calibration-fix
    provides: kalibrering.del_kronologisk_3veis (3-way chronological split), CALIB-01 leakage fix
provides:
  - "model.py — the single as_of-aware train/calibrate/persist/load module; owns every XGBoost .fit() and IsotonicRegression .fit() in the codebase"
  - "model.tren(features_df, as_of=<dato>) — the one-call contract Plan 05-07's walk-forward retrain loop will use per retrain point (BT-01)"
  - "model.del_for_trening(df, as_of=<dato>) — strict-< expanding-window split, fraction-based calibrate slice, empty test mask (BT-02)"
affects: [05-07, 05-08, 05-09, 05-10, 05-12, 05-13]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "as_of dual-mode split: one function, two calling conventions — as_of=None delegates verbatim to the already-tested kalibrering.del_kronologisk_3veis (one-shot 3-way split); as_of=<dato> builds a fraction-based 2-way expanding-window split with an empty test mask, since the walk-forward loop's own out-of-sample prediction on as_of's games IS the test"
    - "Source-guard tests moved with the code they guard: when fit logic moves module, its source-level regression guards (grep-based, comment-stripped) move with it, and the vacated location gets a single new guard proving it now delegates instead of re-inlining"

key-files:
  created:
    - model.py
    - tests/test_model.py
  modified:
    - 03_tren_modell.py
    - tests/test_calibrering_split.py

key-decisions:
  - "Kept del_for_trening's as_of branch validating kalibrer_andel before checking window size, so an invalid fraction always raises regardless of how much history precedes as_of — matches the plan's ValueError ordering intent without being explicitly specified"
  - "tren_og_kalibrer's verbose parameter defaults to 50 (matching 03_tren_modell.py's original call), while tren()'s wrapper defaults verbose=False for the backtest's ~24-models-per-run use case — 03_tren_modell.py calls tren_og_kalibrer directly (not tren()) so its own progress output is preserved byte-for-byte"

requirements-completed: [BT-01, BT-02]

# Metrics
duration: 9min
completed: 2026-08-27
---

# Phase 5 Plan 02: Extract model.py (as_of-Aware Train/Calibrate/Persist/Load) Summary

**Extracted every XGBoost/isotonic `.fit()` call out of `03_tren_modell.py` into a new `model.py` with a dual-mode `as_of` split (delegates to `kalibrering.del_kronologisk_3veis` one-shot, or a fraction-based strict-`<` expanding-window split for walk-forward), rewired the training script onto it with byte-identical stdout, and moved its calibration-discipline source guards to the module that now owns the fits.**

## Performance

- **Duration:** ~9 min (RED commit 11:33 -> final rewire commit 11:37, plus read/design time before)
- **Completed:** 2026-08-27
- **Tasks:** 2 (Task 1 executed as RED + GREEN TDD commits; Task 2 as a single refactor commit)
- **Files modified:** 4 (2 created, 2 modified)

## model.py-kontrakten

Plan 05-07's `backtest.py` walk-forward loop reads this section as its upstream contract — no need to re-read `model.py` to learn these signatures.

**Module constants:**
```python
DATO_KOLONNE = "GAME_DATE_HJEMME"
MAAL_KOLONNE = "HJEMME_VANT"
KALIBRER_ANDEL = 0.15
FEATURE_PREFIKSER = ("DIFF_", "HJEMME_RULL_", "BORTE_RULL_")
```

**`velg_feature_kolonner(df)`**
Returns the list of `df` columns starting with any of `FEATURE_PREFIKSER`, preserving `df.columns` order.

**`del_for_trening(df, as_of=None, kalibrer_andel=KALIBRER_ANDEL, dato_kolonne=DATO_KOLONNE)`**
Returns `(tren_mask, kalibrer_mask, test_mask)` — three boolean `pd.Series`, index-aligned to `df`.
- `as_of=None`: delegates verbatim to `kalibrering.del_kronologisk_3veis(df, dato_kolonne=dato_kolonne)`. `kalibrer_andel` is ignored in this branch.
- `as_of=<dato>`: builds the expanding window `df[dato_kolonne] < as_of` (strict `<`), sorts chronologically, cuts at `int(len(vindu) * (1 - kalibrer_andel))` clamped to `[1, len(vindu) - 1]` so the newest `kalibrer_andel` share becomes the calibrate slice. `test_mask` is always all-`False` in this branch.
- Raises `ValueError` if `kalibrer_andel` is outside the open interval `(0, 1)`, or if fewer than 2 rows precede `as_of`.

**`tren_og_kalibrer(X_tren, y_tren, X_kalibrer, y_kalibrer, verbose=50)`**
Fits the `xgb.XGBClassifier` (verbatim hyperparameters from the original `03_tren_modell.py`) with `eval_set=[(X_kalibrer, y_kalibrer)]`, then fits `IsotonicRegression(out_of_bounds="clip")` on `X_kalibrer`'s raw predictions. Returns a dict:
```python
{
  "raa_modell": <fitted xgb.XGBClassifier>,
  "kalibrerer": <fitted IsotonicRegression>,
  "y_raa_kalibrer": <np.ndarray, raw probs on X_kalibrer>,
  "modell": <KalibrertModell wrapping raa_modell + kalibrerer>,
}
```

**`tren(features_df, as_of=None, kalibrer_andel=KALIBRER_ANDEL, verbose=False)`**
One-call convenience wrapper: selects feature columns, splits via `del_for_trening`, fits via `tren_og_kalibrer`. Returns `tren_og_kalibrer`'s dict extended with:
```python
{
  ...,  # raa_modell, kalibrerer, y_raa_kalibrer, modell
  "feature_kolonner": [...],
  "tren_mask": <pd.Series>,
  "kalibrer_mask": <pd.Series>,
  "test_mask": <pd.Series>,
  "as_of": <same value passed in, or None>,
}
```
This is the function Plan 05-07's retrain loop calls once per retrain point with `as_of=<dato>`.

**`lagre(kalibrert_modell, feature_kolonner, sti="nba_modell.pkl")`** / **`last(sti="nba_modell.pkl")`**
Pickle/unpickle a dict with exactly the keys `modell` and `feature_kolonner` — the identical contract `verdi_deteksjon.last_modell` already reads. `last` returns `(modell, feature_kolonner)`.

## Byte-Diff Verification

`03_tren_modell.py`'s stdout measured at **3,440 bytes** before any edit (`2>/dev/null` capture, stderr discarded to avoid the xgboost timestamped `UserWarning`). After the full rewire, re-running and diffing against the baseline:

```
diff /tmp/03_tren_baseline.txt /tmp/03_tren_etter.txt   # empty, exit 0
wc -c < /tmp/03_tren_etter.txt                          # 3440
```

**Confirmed byte-identical.**

## Accomplishments

- `model.py` created: a flat, print-free, type-hint-free Norwegian module exposing `velg_feature_kolonner`, `del_for_trening`, `tren_og_kalibrer`, `tren`, `lagre`, `last` — now the single owner of every XGBoost `.fit()` and `IsotonicRegression.fit()` in the codebase
- `del_for_trening`'s one-shot branch (`as_of=None`) delegates verbatim to `kalibrering.del_kronologisk_3veis`, preserving Phase 3's disjoint tren/kalibrer/test discipline (CALIB-01) unchanged
- `del_for_trening`'s `as_of` branch is strictly `<`-bounded and fraction-based (not a fixed month count), so the calibrate slice scales with the expanding window instead of collapsing to ~50 games in early backtest months (A5/Pitfall 4)
- `03_tren_modell.py` rewired onto `model.py`: no `XGBClassifier(`, `IsotonicRegression(`, `.fit(`, or `pickle.dump(` remains in the script; stdout is byte-identical to the pre-rewire baseline
- `nba_modell.pkl` keeps its `{modell, feature_kolonner}` dict shape; `verdi_deteksjon.last_modell()` still loads it unchanged (`len(feature_kolonner) == 25`)
- Calibration-discipline source guards (`test_kalibrator_fittes_kun_pa_kalibreringssettet`, `test_early_stopping_bruker_aldri_testsettet`) moved from `tests/test_calibrering_split.py` into `tests/test_model.py`, retargeted at `model.py`; `tests/test_calibrering_split.py` gained one new guard, `test_treningsskript_delegerer_til_model`, proving `03_tren_modell.py` can never silently re-inline the fit logic
- Full suite green: **141 tests** (130 baseline + 13 new in `test_model.py` − 3 guards moved out of `test_calibrering_split.py` + 1 new delegation guard)

## Task Commits

Each task was committed atomically, with Task 1 following the RED → GREEN TDD cycle:

1. **Task 1 (RED):** `test(05-02): add failing test for model.py as_of-aware train/calibrate/persist/load` — `5c7bfbb`
2. **Task 1 (GREEN):** `feat(05-02): implement model.py as_of-aware train/calibrate/persist/load` — `d7200e0`
3. **Task 2:** `refactor(05-02): rewire 03_tren_modell.py onto model.py, retarget delegation guard` — `9073f6e`

No REFACTOR-phase commit was needed — the GREEN implementation required no cleanup pass.

## Files Created/Modified

- `model.py` — New. As_of-aware train/calibrate/persist/load module (235 lines); owns all `.fit()` calls; imports `kalibrering.del_kronologisk_3veis` and `modell_utils.KalibrertModell`, never reimplements either
- `tests/test_model.py` — New. 13 tests: feature-column selection, one-shot split parity with `kalibrering.del_kronologisk_3veis`, `as_of` boundary/disjointness/fraction-sizing/error-path coverage, `tren()`'s `KalibrertModell` contract, `lagre`/`last` pickle round-trip, and the two source guards retargeted from `03_tren_modell.py`
- `03_tren_modell.py` — Rewired to `import model` and delegate feature selection, splitting, fit, and persistence; kept all `pandas`/`numpy`/`sklearn.metrics` imports and every `print(` line unchanged; stdout byte-identical to pre-rewire baseline
- `tests/test_calibrering_split.py` — 3 fit-discipline source guards removed (moved to `tests/test_model.py`); 1 new guard added (`test_treningsskript_delegerer_til_model`); module docstring updated to describe the new split of responsibilities; unused `import re` removed

## Decisions Made

- `kalibrer_andel` validation happens unconditionally at the top of `del_for_trening`'s `as_of` branch, before the window-size check — an invalid fraction raises regardless of how much history precedes `as_of`, matching the plan's implied ordering without being explicitly specified
- `tren_og_kalibrer`'s `verbose` parameter keeps the original default of `50` (so `03_tren_modell.py` calling it directly reproduces today's `[0]`/`[50]`/`[62]` progress lines byte-for-byte); the `tren()` convenience wrapper independently defaults `verbose=False`, since Plan 05-07's backtest loop fits ~24 models per run and does not want per-model XGBoost progress noise

## Deviations from Plan

None — plan executed exactly as written. All acceptance criteria (function count, no `print`/`read_csv` in `model.py`, correct imports, no type hints, byte-diff gate, pickle contract, 141-test collection) were verified to match the plan's stated expected values on first pass.

## Issues Encountered

None. System `python3` still lacks `pytest`/`xgboost` on this machine (confirmed again, consistent with Plan 05-01's finding) — all verification ran via `./venv/bin/python3`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 05-07's walk-forward retrain loop can call `model.tren(features_tabell, as_of=<dato>)` per retrain point without writing any training code of its own (BT-01 satisfied)
- `model.del_for_trening(df, as_of=<dato>)`'s strict-`<` boundary guard (proven by `test_as_of_split_ekskluderer_grenseraden`) gives Plan 05-07 the same off-by-one safety `features.py::beregn_lag_form` already has (BT-02 satisfied)
- `03_tren_modell.py`'s one-shot path is unchanged in behavior (byte-identical stdout) — no regression risk carried into Phase 5's backtest baseline
- Full pytest suite green (141 tests); no blockers for Plan 05-03

---
*Phase: 05-walk-forward-backtest-engine*
*Completed: 2026-08-27*

## Self-Check: PASSED

All claimed files found on disk (`model.py`, `tests/test_model.py`, `03_tren_modell.py`, `tests/test_calibrering_split.py`, `05-02-SUMMARY.md`) and all three task commit hashes (`5c7bfbb`, `d7200e0`, `9073f6e`) verified present in `git log --oneline --all`.
