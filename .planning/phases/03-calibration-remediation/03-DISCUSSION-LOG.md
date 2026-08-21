# Phase 3: Calibration Remediation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-21
**Phase:** 3-Calibration Remediation
**Areas discussed:** Uncommitted starting point, Split strategy, Reporting format

---

## Uncommitted starting point

An off-plan, uncommitted edit to `03_tren_modell.py` was discovered during `/gsd-progress` (before this discussion started). It wires `IsotonicRegression` + `modell_utils.KalibrertModell` into the model-save path, but fits the calibrator on `X_test`/`y_test` and then evaluates calibration quality on that same slice — reproducing the exact same-slice leakage bug CALIB-01/CALIB-02 exist to fix. `git log` confirms `03_tren_modell.py` has been untouched since the initial commit, so this is manual pre-GSD experimentation, not the output of any plan.

| Option | Description | Selected |
|--------|-------------|----------|
| Discard and rewrite from scratch | Revert the uncommitted edit, design the split fresh | |
| Use as scaffold, fix the leak | Keep the `KalibrertModell` wiring and console-table format, restructure the split | ✓ |

**User's choice:** "her må du bare kjøre på å bygge bro" (just go ahead and build the bridge), followed by "do what you think is the best."
**Notes:** Interpreted as: use the existing edit as the starting point rather than discard it, since it already does most of the mechanical wiring correctly (the only defect is which data slice touches the calibrator vs. which slice reports on it).

---

## Split strategy

Current script has a 2-way chronological split (train / last-2-months holdout used as `X_test`). CALIB-01 requires a 3-way split (train/calibrate/test), all disjoint.

| Option | Description | Selected |
|--------|-------------|----------|
| Split holdout window in half | Keep existing "last 2 months" cutoff, divide it into calibrate (older half) + test (newer half) | ✓ |
| New independent cutoffs | Introduce a separate calibrate-window size unrelated to the existing 2-month holdout | |
| Cross-validation-based calibration | Use `CalibratedClassifierCV`-style CV folds on the training set instead of a held-out slice | |

**User's choice:** Not asked directly — decided by Claude per "do what you think is the best," minimizing changes to the existing, working time-series-split convention.
**Notes:** Also decided to repoint XGBoost's `early_stopping_rounds` eval_set from `X_test` to the new `X_calibrate`, since it was quietly using test data for a fitting decision (tree count) — same leakage category, small fix, keeps `test` fully virgin.

---

## Reporting format

CALIB-02 requires an out-of-sample calibration curve / reliability diagram.

| Option | Description | Selected |
|--------|-------------|----------|
| Console table (existing pattern) | Reuse the bucketed predicted-vs-actual print table already in the uncommitted diff, repointed at the `test` split | ✓ |
| Plot/image file | Add matplotlib, save a PNG reliability diagram | |
| HTML report | Build a report page similar to `dashboard.html` | |

**User's choice:** Not asked directly — decided by Claude per "do what you think is the best."
**Notes:** No plotting library exists in `requirements.txt`; HTML/plot reporting is explicitly BTV2-02, already deferred to v2 in STATE.md. Console table keeps this phase's footprint minimal and consistent with the rest of the codebase.

---

## Claude's Discretion

- Exact Norwegian variable names for the new calibrate split.
- Whether to add an automated `tests/test_calibration_split.py` overlap-assertion test, or keep the check informal/inline — left for planner to size.

## Deferred Ideas

- A fourth, "true final holdout" split for the whole betting strategy (not just calibration) — belongs to Phase 5 (BT-03), not this phase.
- HTML/plot calibration reporting — BTV2-02, already deferred to v2.
