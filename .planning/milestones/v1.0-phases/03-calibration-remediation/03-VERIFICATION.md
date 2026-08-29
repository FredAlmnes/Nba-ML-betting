---
phase: 03-calibration-remediation
verified: 2026-08-23T12:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 3: Calibration Remediation Verification Report

**Phase Goal:** The model's probability calibration is fit and validated on data it never touched during fitting, closing a confirmed same-slice leakage bug that has been producing optimistically biased "value" signals.
**Verified:** 2026-08-23T12:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Merged from ROADMAP.md Success Criteria (Phase 3) and both plans' `must_haves.truths`.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Isotonic calibrator is fit on a calibration split disjoint from both training and final evaluation data — a proper three-way train/calibrate/test split is visible in training code (ROADMAP SC1 / CALIB-01) | ✓ VERIFIED | `03_tren_modell.py:71-75` calls `del_kronologisk_3veis(df)` producing `tren_mask, kalibrer_mask, test_mask`; fresh run confirms 3217/172/249 disjoint, chronologically ordered rows (2022-10-24→2025-02-12 / 2025-02-13→2025-03-12 / 2025-03-13→2025-04-13). `kalibrerer.fit(y_rå_kalibrer, y_kalibrer)` at line 177 — only `X_kalibrer`/`y_kalibrer` ever appear inside a `.fit(` call. |
| 2 | Out-of-sample calibration curve / reliability diagram generated and reported using only the held-out test slice the calibrator never saw during fitting (ROADMAP SC2 / CALIB-02) | ✓ VERIFIED | `03_tren_modell.py:211-218` builds the 10-bucket reliability table from `pd.DataFrame({"pred": y_kal_test, "faktisk": y_test.values})`, where `y_kal_test = kalibrerer.predict(y_rå_test)` (predict-only, never fit). Independent run: bucket counts sum to 249 (== test-slice size), zero NaN cells. |
| 3 | A pure, importable function computes the three chronological split masks without touching disk or printing | ✓ VERIFIED | `kalibrering.py` — single function `del_kronologisk_3veis`, imports only `pandas`; `grep -c 'print('` and `grep -c 'read_csv\|open('` both return 0. |
| 4 | The pytest suite fails if the three splits ever overlap or fall out of chronological order | ✓ VERIFIED | `tests/test_calibrering_split.py::test_maskene_overlapper_aldri` and `::test_kronologisk_rekkefolge` run and pass (44 passed total, 0.10s). |
| 5 | An invalid cutoff configuration raises loudly instead of producing silent empty splits | ✓ VERIFIED | `kalibrering.py:27-33` raises `ValueError`; `test_ugyldig_kalibrer_cutoff_gir_verdifeil` passes. |
| 6 | XGBoost early stopping evaluates on the kalibrer slice, never on the test slice | ✓ VERIFIED | `03_tren_modell.py:120` — `eval_set=[(X_kalibrer, y_kalibrer)]`. `grep -c 'eval_set=\[(X_test'` returns 0. |
| 7 | Console output states explicitly which slice was fitted on and which was evaluated on, with row counts and date ranges for both | ✓ VERIFIED | Independent run log shows `Kalibrator FITTET på: kalibreringssett (172 kamper)` / `Kalibrator EVALUERT på: testsett (249 kamper) — aldri sett under fitting`, plus per-slice date ranges printed at lines 77-85. |
| 8 | A runtime warning prints when the kalibrer slice is smaller than sklearn's ~1000-sample isotonic guidance | ✓ VERIFIED | Independent run log: `ADVARSEL: Kalibreringssettet har kun 172 kamper (under sklearns anbefalte ~1000 for isotonic regression)...`. Condition is `len(X_kalibrer) < 1000`, a runtime check not a hardcoded number. |
| 9 | The pytest suite fails if a future edit ever feeds X_test/y_test back into a fitting call | ✓ VERIFIED | Negative control performed live during this verification: temporarily reverted `eval_set=[(X_kalibrer, y_kalibrer)]` → `eval_set=[(X_test, y_test)]` in `03_tren_modell.py`; `test_early_stopping_bruker_aldri_testsettet` failed as expected (1 failed, 6 passed). Reverted; suite green again (7 passed) and `git diff --stat 03_tren_modell.py` confirmed clean after restore. |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `kalibrering.py` | Pure `del_kronologisk_3veis` 3-way split function | ✓ VERIFIED | Exists, 46 lines, imports only pandas, no I/O/prints, raises `ValueError` on invalid cutoff. |
| `tests/test_calibrering_split.py` | Non-overlap/order/coverage tests + source-level guard tests | ✓ VERIFIED | 7 tests total (4 from Plan 01 + 3 from Plan 02), all pass; deterministic fixture, no `random`/`datetime.now()`. |
| `03_tren_modell.py` | 3-way split, kalibrer-based early stopping, kalibrer-fit calibrator, test-only reliability table | ✓ VERIFIED | All five properties confirmed via source read + independent execution. |
| `nba_modell.pkl` | Regenerated `KalibrertModell` artifact | ✓ VERIFIED | mtime fresh (regenerated during this verification's independent run); `pickle.load` returns `type=KalibrertModell`, `feature_kolonner` len=25 — unbroken consumption contract with `04_value_detector.py` (`from modell_utils import KalibrertModell` present at `04_value_detector.py:25`). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `tests/test_calibrering_split.py` | `kalibrering.del_kronologisk_3veis` | module import | ✓ WIRED | `from kalibrering import del_kronologisk_3veis` present; tests import and exercise it. |
| `03_tren_modell.py` | `kalibrering.del_kronologisk_3veis` | module import | ✓ WIRED | `from kalibrering import del_kronologisk_3veis` at line 21, called at line 71. |
| `03_tren_modell.py` | xgboost early stopping | `eval_set` pointed at kalibrer slice | ✓ WIRED | Confirmed by source + negative-control test (item 9 above). |
| `03_tren_modell.py` | sklearn `IsotonicRegression` | fit on kalibrer, predict on test | ✓ WIRED | `kalibrerer.fit(y_rå_kalibrer, y_kalibrer)` then `kalibrerer.predict(y_rå_test)` — confirmed by source and by guard test `test_kalibrator_fittes_kun_pa_kalibreringssettet`. |
| `03_tren_modell.py` | `modell_utils.KalibrertModell` | pickle payload to `nba_modell.pkl` | ✓ WIRED | `KalibrertModell(modell, kalibrerer)` at line 223, unchanged payload dict shape; `04_value_detector.py` unpickles it successfully (verified via direct `pickle.load`). |

### Data-Flow Trace (Level 4)

Not applicable in the standard UI-data-flow sense (this phase produces console/CLI output, not a rendered component). Instead, the equivalent trace was performed directly: independently re-ran `03_tren_modell.py` end-to-end (not just reading SUMMARY claims) and confirmed the printed split sizes, FITTET/EVALUERT labels, warning text, and reliability-table bucket sums against `nba_features.csv` (3,638 real rows) match the numbers claimed in 03-02-SUMMARY.md exactly (3217/172/249 split; calibrated log-loss 0.7356 vs uncalibrated 0.6170; reliability buckets summing to 249 with zero NaN cells).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full pytest suite green | `venv/bin/python3 -m pytest -q` | `44 passed in 0.10s` | ✓ PASS |
| Training script runs end-to-end and produces model artifact | `venv/bin/python3 03_tren_modell.py` | exit 0; produced FITTET/EVALUERT labeled output, ADVARSEL warning, 10-bucket table summing to 249, no NaN | ✓ PASS |
| Negative control: leakage reintroduction fails the guard test | manually reverted `eval_set` to `X_test`, ran `pytest tests/test_calibrering_split.py -q`, then reverted | `1 failed, 6 passed` on the reverted (buggy) version; `7 passed` after restore | ✓ PASS |
| `nba_modell.pkl` unpickles as `KalibrertModell` consumable by `04_value_detector.py` | `pickle.load(open('nba_modell.pkl','rb'))` | `KalibrertModell 25` (type name, feature count) | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` files exist in this repo, and no PLAN/SUMMARY declared any probe-based verification. Step 7c: SKIPPED (no probes declared or found).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CALIB-01 | 03-01-PLAN.md, 03-02-PLAN.md | Isotonic calibrator fit and evaluated using a proper train/calibrate/test three-way split, not the same data slice for both fitting and evaluation | ✓ SATISFIED | `kalibrering.del_kronologisk_3veis` produces the 3-way split; `03_tren_modell.py` fits `kalibrerer` only on `(y_rå_kalibrer, y_kalibrer)`; source-level guard test + negative control confirm `X_test`/`y_test` never enter a `.fit(` call. |
| CALIB-02 | 03-02-PLAN.md | Out-of-sample calibration curve / reliability diagram reported on held-out data the calibrator never saw | ✓ SATISFIED | 10-bucket reliability table sourced exclusively from `y_kal_test`/`y_test` (test slice), confirmed via independent execution with correct bucket-count sum (249) and no NaN cells. |

No orphaned requirements: REQUIREMENTS.md maps only CALIB-01 and CALIB-02 to Phase 3, and both are declared in plan frontmatter and satisfied above.

### Anti-Patterns Found

None. Scanned `kalibrering.py`, `03_tren_modell.py`, `tests/test_calibrering_split.py` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` and placeholder-language patterns — zero matches. No empty-implementation patterns (`return null`, `=> {}`, etc. — not applicable to this Python codebase, and no analogous `pass`-only stub bodies were introduced). `modell_utils.py` and `04_value_detector.py` are untouched (`git diff --stat` shows no changes to either), respecting the D-02 lock.

### Honest Finding: Calibrated Metric Regression (Explicitly Requested Double-Check)

The executor's flagged finding was independently verified, not just re-read from SUMMARY.md:

- Independently re-running `03_tren_modell.py` (not reusing any cached log) reproduces calibrated log-loss **0.7356** vs. uncalibrated **0.6170** on the 249-row test slice — worse after calibration, on this specific dataset/run.
- This is **genuinely surfaced in console output**, not hidden: the script prints an explicit before/after comparison table plus an unconditional note ("Merk: hvis Kalibrert er DÅRLIGERE enn Ukalibrert, har isotonic-fitten sannsynligvis overfittet det lille kalibreringssettet — et funn å ta videre, ikke noe å skjule.") immediately below the metrics table, plus a separate `ADVARSEL` line at split time naming the exact under-1000-sample condition. There is no code path that suppresses, rounds away, or silently `try/except`s around this outcome.
- This does **not** represent a deviation from CALIB-01/CALIB-02. Both requirements (and both ROADMAP success criteria) are about the *mechanics* of the split/fit/eval process being leakage-free and out-of-sample — they say nothing about calibration being required to improve the headline metric on every run. The 172-row calibration set falling short of sklearn's ~1000-sample isotonic guidance is a data-volume limitation, explicitly anticipated in 03-RESEARCH.md (Pitfall 1) and explicitly surfaced by design (D-03's "flag this as a runtime check, not a fixed number", D-06's "kalibrert på X, evaluert på Y" labeling). The phase goal was to make calibration *honestly measurable*, and this finding is exactly that honesty working as intended — it is future work for Phase 5 (more data / different calibration approach), not evidence CALIB-01/CALIB-02 failed.

### Human Verification Required

None. This phase's truths are all mechanically verifiable via source inspection, independent script execution, and a negative-control test — no UI, no real-time behavior, no external service integration, and no subjective quality judgment is involved.

### Gaps Summary

No gaps. All 9 derived truths (2 from ROADMAP Success Criteria + 7 supplementary truths from the two plans' `must_haves.truths`) are verified with direct, independently-reproduced evidence — not SUMMARY.md claims taken at face value. Both requirement IDs (CALIB-01, CALIB-02) are satisfied. The one flagged risk (calibrated metric worse than uncalibrated on this run) is honestly surfaced in code/console output and is explicitly out of scope for what CALIB-01/CALIB-02 require — it is correctly deferred to Phase 5 rather than blocking this phase.

---

*Verified: 2026-08-23T12:00:00Z*
*Verifier: Claude (gsd-verifier)*
