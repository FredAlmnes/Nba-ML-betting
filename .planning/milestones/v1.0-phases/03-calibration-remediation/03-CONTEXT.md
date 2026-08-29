# Phase 3: Calibration Remediation - Context

**Gathered:** 2026-08-21
**Status:** Ready for planning

<domain>
## Phase Boundary

`03_tren_modell.py` fits an isotonic-regression calibrator on top of the XGBoost classifier and evaluates its calibration quality. Today both the fit and the evaluation reuse the same held-out slice (`X_test`/`y_test`), which is the confirmed same-slice leakage bug (CALIB-01/CALIB-02). This phase changes the split so the calibrator is fit on data disjoint from the data used to report calibration quality, and reports an out-of-sample reliability diagram. Scope is the training script's split/calibration/reporting logic only — no changes to `04_value_detector.py`'s live scoring path, no backtest engine (Phase 5), no HTML/plot reporting (BTV2-02, deferred to v2).

</domain>

<decisions>
## Implementation Decisions

### Uncommitted starting point
- **D-01:** The working tree already has an uncommitted edit to `03_tren_modell.py` (never committed — `git log` shows the file untouched since the initial commit) that wires `IsotonicRegression` + `modell_utils.KalibrertModell` into the save path. The user explicitly asked to build on this rather than discard it ("her må du bare kjøre på å bygge bro" / "do what you think is the best"). Treat it as the scaffold: keep its console-table diagnostic format and `KalibrertModell` wiring, but restructure the split so fit and eval no longer share a slice.
- **D-02:** `modell_utils.KalibrertModell` already exists (built in Phase 2) and needs no changes — it's a thin `predict_proba` wrapper around `(xgboost_model, fitted_calibrator)`.

### Split strategy
- **D-03:** Extend the existing chronological 2-way split (`train` vs. "last 2 months" holdout) into a 3-way chronological split by dividing the existing holdout window in half instead of introducing a new cutoff scheme:
  - `train`: everything more than 2 months before the last game date (unchanged from today's `fra_dato` cutoff)
  - `calibrate`: the older half of the holdout window (2 months ago → 1 month ago)
  - `test`: the newer half of the holdout window (1 month ago → most recent game) — never touched by fitting or by the calibrator, only by final reporting
  - Verify game counts in `calibrate` land in the low hundreds (isotonic regression needs reasonable N); if `calibrate` turns out too small, planner/executor should widen it rather than silently accept a noisy calibrator — flag this as a runtime check, not a fixed number, since roster/schedule density varies by month.
- **D-04:** XGBoost's `early_stopping_rounds` currently uses `X_test`/`y_test` as its `eval_set`, which is a second, milder instance of "fitting on the final test slice" (test performance implicitly steers how many trees get built). Since we're already introducing a `calibrate` split for the isotonic fit, point `early_stopping`'s `eval_set` at `X_calibrate`/`y_calibrate` instead of `X_test`/`y_test` — this is a small, in-scope change that keeps `test` fully virgin (only used once, for final reporting) without adding a fourth split. This directly serves CALIB-01's "disjoint from both the training data and the final evaluation/test data" wording, which covers early stopping too since it's part of model fitting.

### Reporting
- **D-05:** Keep the reliability diagram as a console table (existing project convention — the current uncommitted diff already prints a 10-bucket predicted-vs-actual table; no plotting library is in `requirements.txt` and none is added). Compute it only from the `test` split's calibrated predictions, not `calibrate`. This satisfies CALIB-02 without introducing new dependencies or output files.
- **D-06:** Print both the calibrate-fit diagnostics (optional, informal) and the out-of-sample test-set reliability table clearly labeled as separate ("kalibrert på X, evaluert på Y") so it's visually obvious in the script's own output that the two slices differ — this is the cheapest possible guardrail against the bug silently reappearing in a future edit.

### Claude's Discretion
- Exact variable names for the new split (`X_kalibrer`/`y_kalibrer` etc., matching existing Norwegian naming convention) — planner/executor's call.
- Whether to add a lightweight assertion (e.g., date-range non-overlap check) inline in the script vs. a `tests/` unit test — Phase 2 already established a `tests/` pytest foundation (`test_parity.py`, `test_features.py`, etc.) with the explicit pattern of leakage/determinism regression tests; a `tests/test_calibration_split.py` asserting `train`/`calibrate`/`test` date ranges never overlap would fit that established pattern. Recommended but left to planner to size correctly against phase scope.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §"Calibration Remediation" — CALIB-01, CALIB-02 (locked acceptance criteria for this phase)

### Roadmap
- `.planning/ROADMAP.md` §"Phase 3: Calibration Remediation" — goal + success criteria

### Prior phase decisions this phase depends on
- `.planning/phases/02-shared-core-extraction-test-foundation/02-06-SUMMARY.md` — confirms `tests/test_parity.py` already documents (in its own module docstring) that Phase 5, not Phase 3, owns live-vs-backtest integration testing; Phase 3's own tests (if added) should stay scoped to the split/calibration logic only, not duplicate that.
- `KALIBRERING_RAPPORT.md` / `ENDRINGER_SUMMARY.txt` — a **different, unrelated** legacy calibration idea (a flat ×0.60 shrinkage factor) that HYG-03 (Phase 1) already explicitly superseded/disclaimed as never applied to running code. Not to be confused with this phase's isotonic-regression fix — do not resurrect the ×0.60 factor.

No other external specs — requirements fully captured above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `modell_utils.KalibrertModell` (`modell_utils.py:8-22`) — already built, already imported by the uncommitted `03_tren_modell.py` diff. No changes needed; just needs to be fit on the right slices.
- The uncommitted `03_tren_modell.py` diff's console-table diagnostic pattern (bucketed predicted-vs-actual, `pd.cut(..., bins=10)`) — reuse the format, just repoint it at the `test` split instead of `X_test` reused as both fit and eval data.

### Established Patterns
- Chronological/time-series splitting via `GAME_DATE_HJEMME` cutoffs (`pd.DateOffset(months=N)`) is the existing convention in `03_tren_modell.py` — extend it, don't replace it with a different splitting mechanism (e.g. no `sklearn.model_selection.TimeSeriesSplit` — stay consistent with the simple date-cutoff style already in the file).
- Norwegian identifiers throughout (`tren_mask`, `y_sann`, `kalibrerer`) — new split variables should follow the same convention.
- `nba_modell.pkl` save format (`{"modell": ..., "feature_kolonner": ...}`) is unchanged — only what's fit into `modell` (now `KalibrertModell`) changes, consistent with what the uncommitted diff already does.

### Integration Points
- `04_value_detector.py` unpickles `nba_modell.pkl` and calls `.predict_proba()` — already compatible with `KalibrertModell`'s interface, per Phase 2. No changes needed there for this phase.
- `tests/` directory (pytest) exists with `conftest.py` and 4 existing test files — natural home for an optional split-overlap regression test (see Claude's Discretion above).

</code_context>

<specifics>
## Specific Ideas

The user's instruction was procedural, not a specific design vision: given the discovered uncommitted, off-plan edit to `03_tren_modell.py` that already reproduces the exact leakage bug this phase exists to fix, the user said to "just go ahead and build the bridge" — i.e., use that edit as the starting scaffold for the real fix rather than discard it or ask more clarifying questions. That instruction is captured as D-01 above; no other specific requirements were raised.

</specifics>

<deferred>
## Deferred Ideas

- **Fourth split for a true holdout beyond calibration** — not needed now; `test` in this phase's 3-way split already serves as that final holdout for calibration purposes. Phase 5's "locked, never-touched final holdout slice" (BT-03) is a separate, larger-scope concept (applies to the full betting strategy, not just calibration) and should be designed fresh in Phase 5, not inherited from this phase's split.
- **HTML/plot calibration report (equity curve, calibration plot, CLV chart)** — explicitly BTV2-02, already deferred to v2 in `.planning/STATE.md`'s Deferred Items table. Not touched here.

None — discussion stayed within phase scope otherwise.

</deferred>

---

*Phase: 3-Calibration Remediation*
*Context gathered: 2026-08-21*
