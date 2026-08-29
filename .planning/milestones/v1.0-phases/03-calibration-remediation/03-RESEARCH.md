# Phase 3: Calibration Remediation - Research

**Researched:** 2026-08-21
**Domain:** Probability calibration (isotonic regression) on a small tabular sports-prediction dataset; chronological train/calibrate/test splitting for an XGBoost classifier
**Confidence:** HIGH (split mechanics, sklearn/xgboost API behavior — verified against official docs and this repo's actual installed versions/data) / MEDIUM (calibration-set-size adequacy judgment call, since the real number falls in a documented gray zone)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Uncommitted starting point**
- **D-01:** The working tree already has an uncommitted edit to `03_tren_modell.py` (never committed — `git log` shows the file untouched since the initial commit) that wires `IsotonicRegression` + `modell_utils.KalibrertModell` into the save path. The user explicitly asked to build on this rather than discard it ("her må du bare kjøre på å bygge bro" / "do what you think is the best"). Treat it as the scaffold: keep its console-table diagnostic format and `KalibrertModell` wiring, but restructure the split so fit and eval no longer share a slice.
- **D-02:** `modell_utils.KalibrertModell` already exists (built in Phase 2) and needs no changes — it's a thin `predict_proba` wrapper around `(xgboost_model, fitted_calibrator)`.

**Split strategy**
- **D-03:** Extend the existing chronological 2-way split (`train` vs. "last 2 months" holdout) into a 3-way chronological split by dividing the existing holdout window in half instead of introducing a new cutoff scheme:
  - `train`: everything more than 2 months before the last game date (unchanged from today's `fra_dato` cutoff)
  - `calibrate`: the older half of the holdout window (2 months ago → 1 month ago)
  - `test`: the newer half of the holdout window (1 month ago → most recent game) — never touched by fitting or by the calibrator, only by final reporting
  - Verify game counts in `calibrate` land in the low hundreds (isotonic regression needs reasonable N); if `calibrate` turns out too small, planner/executor should widen it rather than silently accept a noisy calibrator — flag this as a runtime check, not a fixed number, since roster/schedule density varies by month.
- **D-04:** XGBoost's `early_stopping_rounds` currently uses `X_test`/`y_test` as its `eval_set`, which is a second, milder instance of "fitting on the final test slice" (test performance implicitly steers how many trees get built). Since we're already introducing a `calibrate` split for the isotonic fit, point `early_stopping`'s `eval_set` at `X_calibrate`/`y_calibrate` instead of `X_test`/`y_test` — this is a small, in-scope change that keeps `test` fully virgin (only used once, for final reporting) without adding a fourth split. This directly serves CALIB-01's "disjoint from both the training data and the final evaluation/test data" wording, which covers early stopping too since it's part of model fitting.

**Reporting**
- **D-05:** Keep the reliability diagram as a console table (existing project convention — the current uncommitted diff already prints a 10-bucket predicted-vs-actual table; no plotting library is in `requirements.txt` and none is added). Compute it only from the `test` split's calibrated predictions, not `calibrate`. This satisfies CALIB-02 without introducing new dependencies or output files.
- **D-06:** Print both the calibrate-fit diagnostics (optional, informal) and the out-of-sample test-set reliability table clearly labeled as separate ("kalibrert på X, evaluert på Y") so it's visually obvious in the script's own output that the two slices differ — this is the cheapest possible guardrail against the bug silently reappearing in a future edit.

### Claude's Discretion
- Exact variable names for the new split (`X_kalibrer`/`y_kalibrer` etc., matching existing Norwegian naming convention) — planner/executor's call.
- Whether to add a lightweight assertion (e.g., date-range non-overlap check) inline in the script vs. a `tests/` unit test — Phase 2 already established a `tests/` pytest foundation (`test_parity.py`, `test_features.py`, etc.) with the explicit pattern of leakage/determinism regression tests; a `tests/test_calibration_split.py` asserting `train`/`calibrate`/`test` date ranges never overlap would fit that established pattern. Recommended but left to planner to size correctly against phase scope.

### Deferred Ideas (OUT OF SCOPE)
- **Fourth split for a true holdout beyond calibration** — not needed now; `test` in this phase's 3-way split already serves as that final holdout for calibration purposes. Phase 5's "locked, never-touched final holdout slice" (BT-03) is a separate, larger-scope concept (applies to the full betting strategy, not just calibration) and should be designed fresh in Phase 5, not inherited from this phase's split.
- **HTML/plot calibration report (equity curve, calibration plot, CLV chart)** — explicitly BTV2-02, already deferred to v2 in `.planning/STATE.md`'s Deferred Items table. Not touched here.
- None else — discussion stayed within phase scope otherwise.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CALIB-01 | The isotonic calibrator is fit and evaluated using a proper train/calibrate/test three-way split, not the same data slice for both fitting and evaluation | See Architecture Patterns (Pattern 1, Pattern 2), Code Examples, and Validation Architecture's requirements→test map. The 3-way split arithmetic was verified directly against this repo's real `nba_features.csv` (train=3,217, calibrate=172, test=249 games). `out_of_bounds="clip"` is confirmed as the correct existing choice (Pitfall 3). |
| CALIB-02 | An out-of-sample calibration curve / reliability diagram is reported on held-out data the calibrator never saw | See Pattern 1 (fit-on-calibrate / eval-on-test), D-05/D-06 reporting requirements captured verbatim above, and Validation Architecture's manual/smoke verification approach (no existing convention in this repo for unit-testing full top-level script execution). |
</phase_requirements>

## Summary

This phase is a narrow, single-file bug fix: `03_tren_modell.py` currently fits its `IsotonicRegression` calibrator on `X_test`/`y_test` and then evaluates calibration quality on that exact same slice — a same-slice leakage bug. The fix, already scoped by CONTEXT.md's locked decisions (D-01 through D-06), is to extend the existing 2-way chronological split (`train` vs. "last 2 months" holdout) into a 3-way chronological split by bisecting the holdout window into `calibrate` (older half) and `test` (newer half), fit isotonic regression only on `calibrate`, repoint XGBoost's `early_stopping_rounds` eval_set at `calibrate` instead of `test`, and print the existing 10-bucket reliability table computed only from `test`.

Running the split against this repo's actual `nba_features.csv` (3,638 games, 2022-10-24 to 2025-04-13) confirms the resulting three slices are: `train` = 3,217 games, `calibrate` = 172 games (2025-02-13 to 2025-03-12), `test` = 249 games (2025-03-13 to 2025-04-13). This matters directly for planning: scikit-learn's own official documentation states isotonic regression needs "greater than ~1000 samples" to reliably outperform sigmoid/Platt calibration and is "more prone to overfitting, especially on small datasets" — 172 samples is well inside that documented risk zone. This isn't a reason to abandon the locked split strategy (CONTEXT.md D-03 already anticipated this and explicitly asks for a runtime size check, not a redesign), but it is a finding the plan should surface as a printed warning and an honestly-labeled caveat on the reliability table, not silently absorb.

**Primary recommendation:** Implement the 3-way split and repointed `eval_set` exactly as locked in CONTEXT.md D-03/D-04, keep `IsotonicRegression(out_of_bounds="clip")` (already correct in the uncommitted diff — `clip` is required here because `calibrate`'s raw-score range will likely be narrower than `test`'s), add a runtime `print()` warning when `len(calibrate) < 1000` citing the sklearn threshold, and add a small, fast pytest regression test asserting the three date ranges are non-overlapping and chronologically ordered — extracting just the pure split-boundary logic into a small importable function (matching the Phase 2 `features.py`/`strategy.py` precedent) rather than trying to import the full top-level training script.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Chronological 3-way data split | Offline training script (`03_tren_modell.py`) | — | Split boundaries are a training-time concern only; no other script needs them |
| XGBoost model fitting + early stopping | Offline training script (`03_tren_modell.py`) | — | Unchanged responsibility, only its `eval_set` input changes (D-04) |
| Isotonic calibration fitting | Offline training script (`03_tren_modell.py`), via `modell_utils.KalibrertModell` | — | `KalibrertModell` already exists (Phase 2) as the storage/inference wrapper; fitting still happens in `03_tren_modell.py` |
| Calibrated inference (`predict_proba`) | `modell_utils.KalibrertModell` | `04_value_detector.py` (consumer) | Unchanged this phase — wrapper interface already compatible per Phase 2 |
| Reliability diagram reporting | Offline training script (`03_tren_modell.py`), console output | — | No new output artifact/file; stdout only, per D-05 (no plotting library added) |

This phase has no browser/API/CDN tiers — it is a single offline batch-training script. The map above is included for completeness per the research template but is intentionally flat.

## Standard Stack

### Core
| Library | Version (installed in this repo's `venv/`) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `scikit-learn` | 1.8.0 [VERIFIED: local venv] | `IsotonicRegression`, `accuracy_score`/`log_loss`/`brier_score_loss` | Already the project's calibration library (Phase 2's `KalibrertModell` wraps it); no new dependency |
| `xgboost` | 3.2.0 [VERIFIED: local venv] | `XGBClassifier` training + early stopping | Already the project's model library; no new dependency |
| `pandas` | 3.0.1 (per CLAUDE.md tech-stack notes) [CITED: CLAUDE.md] | Chronological split, bucketed reliability table (`pd.cut`) | Already used throughout the pipeline |

No new packages are introduced by this phase — every library needed is already installed and already imported by the existing (uncommitted) `03_tren_modell.py` diff. **Package Legitimacy Audit is not applicable this phase** (see below).

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | already present (`pytest.ini`, `tests/` dir, 37 tests collected) [VERIFIED: local run] | Optional regression test for split non-overlap (Claude's Discretion, D-06 context) | If planner chooses the `tests/` route over an inline `assert` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Isotonic regression (locked, unchanged) | `sklearn.calibration.CalibratedClassifierCV(method="sigmoid")` (Platt scaling) | Sigmoid is explicitly recommended by sklearn's own docs when the calibration set is small (< ~1000 samples), which is the actual situation here (172 games). **Not in scope to change** — CONTEXT.md does not reopen the calibration *method*, only the leakage bug in how it's split. Flagged here as an Open Question for future consideration, not a recommendation to act on now. |
| Simple date-cutoff 3-way split (locked, D-03) | `sklearn.model_selection.TimeSeriesSplit` | CLAUDE.md explicitly instructs staying consistent with the existing simple date-cutoff pattern and not introducing `TimeSeriesSplit`. Not researched further per that constraint. |

**Installation:** None required — no new packages.

**Version verification:** Confirmed directly against this repo's own `venv/` via `venv/bin/python3 -c "import xgboost; print(xgboost.__version__)"` → `3.2.0`, and `import sklearn; print(sklearn.__version__)` → `1.8.0`. These match the versions already documented in CLAUDE.md's Technology Stack section.

## Package Legitimacy Audit

**Not applicable.** This phase introduces zero new external packages — `scikit-learn`, `xgboost`, and `pandas` are already installed, already imported by the current (uncommitted) `03_tren_modell.py`, and already covered by the project's `requirements.txt`. The Package Legitimacy Gate is skipped per its own scope condition ("whenever this phase installs external packages").

## Architecture Patterns

### System Architecture Diagram

```
nba_features.csv (3,638 games, sorted by GAME_DATE_HJEMME)
        │
        ▼
  compute cutoffs: fra_dato = maks_dato - 2mnd, midt_dato = maks_dato - 1mnd
        │
        ├─────────────┬───────────────┬─────────────────┐
        ▼             ▼               ▼                 ▼
   train (< fra_dato)  calibrate (fra_dato ≤ · < midt_dato)  test (≥ midt_dato)
   3,217 games          172 games                              249 games
        │                     │                                    │
        ▼                     │                                    │
  XGBClassifier.fit(          │                                    │
    X_train, y_train,         │                                    │
    eval_set=[(X_calibrate,   │                                    │
               y_calibrate)]  │  ◄── D-04: early stopping now       │
  )  ─────────────────────────┘      watches calibrate, not test    │
        │                                                            │
        ▼                                                            │
  raw XGBoost probs on calibrate ──► IsotonicRegression.fit()        │
        │                              (fit ONLY on calibrate)       │
        ▼                                                            │
  KalibrertModell(xgb_model, fitted_calibrator)                     │
        │                                                            │
        ├──► pickle to nba_modell.pkl (unchanged format)             │
        │                                                            ▼
        └──► KalibrertModell.predict_proba(X_test) ──► reliability table
                                                          (console only,
                                                           test split only)
```

### Recommended Project Structure

No new files/folders required beyond the optional test file:

```
03_tren_modell.py          # modified: 3-way split, repointed eval_set, test-only reporting
modell_utils.py            # unchanged (KalibrertModell already correct)
tests/
├── conftest.py             # existing fixtures — reusable if a synthetic-date fixture is added
└── test_calibrering_split.py  # NEW (optional per Claude's Discretion) — non-overlap regression test
```

### Pattern 1: Isotonic calibration fit/eval on disjoint slices

**What:** Fit `IsotonicRegression` only on the raw model scores + true labels from `calibrate`; evaluate/report only on `test`'s raw scores passed through the already-fitted calibrator.
**When to use:** Always, per CALIB-01 — this is the core fix.
**Example:**
```python
# Source: sklearn.isotonic.IsotonicRegression official docs
# https://scikit-learn.org/stable/modules/generated/sklearn.isotonic.IsotonicRegression.html
kalibrerer = IsotonicRegression(out_of_bounds="clip")

y_rå_kalibrer = modell.predict_proba(X_kalibrer)[:, 1]
kalibrerer.fit(y_rå_kalibrer, y_kalibrer)          # fit ONLY on calibrate

y_rå_test    = modell.predict_proba(X_test)[:, 1]
y_sann_kal   = kalibrerer.predict(y_rå_test)        # eval ONLY on test
logloss_kal  = log_loss(y_test, y_sann_kal)
brier_kal    = brier_score_loss(y_test, y_sann_kal)
```
`out_of_bounds="clip"` (already present in the uncommitted diff) is the correct choice here specifically *because* `calibrate` is a much smaller, narrower slice than `test` — some of `test`'s raw XGBoost scores will likely fall outside the range of raw scores observed during `calibrate` fitting. `"clip"` maps those to the nearest calibrated boundary value instead of returning `NaN` (the default `out_of_bounds="nan"` would silently corrupt the reliability table and downstream metrics with `NaN`s). [CITED: scikit-learn IsotonicRegression docs]

### Pattern 2: Repointed early-stopping eval_set

**What:** XGBoost's `early_stopping_rounds` (already a constructor parameter in the installed xgboost 3.2.0, matching current code) needs its `fit(..., eval_set=[...])` argument repointed from `(X_test, y_test)` to `(X_kalibrer, y_kalibrer)`.
**When to use:** Per locked decision D-04.
**Example:**
```python
# Source: xgboost sklearn_estimator docs
# https://xgboost.readthedocs.io/en/latest/python/sklearn_estimator.html
modell = xgb.XGBClassifier(
    n_estimators=300, max_depth=4, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8,
    eval_metric="logloss", random_state=42,
    early_stopping_rounds=20,   # constructor param — confirmed current API, no change needed
)
modell.fit(
    X_tren, y_tren,
    eval_set=[(X_kalibrer, y_kalibrer)],   # was (X_test, y_test) — this is the D-04 change
    verbose=50,
)
```
Verified against the installed xgboost 3.2.0 in this repo's `venv/`: `early_stopping_rounds` as a constructor kwarg + `eval_set` in `.fit()` is the current, non-deprecated pattern (not the older fit()-kwarg form). [CITED: xgboost.readthedocs.io sklearn_estimator.html]

### Pattern 3: Testable pure split function (recommended for the optional regression test)

**What:** `03_tren_modell.py` executes top-to-bottom with heavy side effects (trains a real XGBoost model, writes `nba_modell.pkl`) and has no `if __name__ == "__main__":` guard — importing it in a test would run the entire training pipeline, which is slow and requires `nba_features.csv` to exist locally (it's gitignored, so not guaranteed on a fresh clone). This mirrors exactly the problem Phase 2 already solved for `features.py`/`strategy.py`/`teams.py`: pull the *pure, testable* piece out into a small function, leave the rest of the script's top-level-execution style untouched.
**When to use:** If the planner takes the `tests/` route (Claude's Discretion, recommended by CONTEXT.md's own text referencing the Phase 2 `tests/test_parity.py` precedent).
**Example:**
```python
# New, small function — could live in 03_tren_modell.py itself (defined before use,
# called at module level as today) or in modell_utils.py alongside KalibrertModell.
# Kept pure (no I/O, no prints) so it's fast and deterministic to unit test.
def del_kronologisk_3veis(df, dato_kolonne, trenings_cutoff_mnd=2, kalibrer_cutoff_mnd=1):
    """
    Deler en tidsserie-DataFrame i tren/kalibrer/test basert på antall
    måneder tilbake fra siste dato i datasettet. Returnerer tre boolske masker.
    """
    maks_dato = df[dato_kolonne].max()
    fra_dato  = maks_dato - pd.DateOffset(months=trenings_cutoff_mnd)
    midt_dato = maks_dato - pd.DateOffset(months=kalibrer_cutoff_mnd)
    tren_mask     = df[dato_kolonne] < fra_dato
    kalibrer_mask = (df[dato_kolonne] >= fra_dato) & (df[dato_kolonne] < midt_dato)
    test_mask     = df[dato_kolonne] >= midt_dato
    return tren_mask, kalibrer_mask, test_mask
```
A test can then import this one function with a small synthetic date DataFrame (matching the style already used in `tests/conftest.py`'s `kamper_df` fixture) and assert:
- `tren_mask & kalibrer_mask` is all-False (no overlap)
- `kalibrer_mask & test_mask` is all-False (no overlap)
- `max(dates[tren_mask]) < min(dates[kalibrer_mask]) <= max(dates[kalibrer_mask]) < min(dates[test_mask])` (chronological order)

**Fallback (lower-effort, if the planner wants zero new files given phase is "narrowly scoped"):** Add plain `assert` statements directly in `03_tren_modell.py` right after computing the three masks, e.g. `assert X_tren.index.max() < X_kalibrer.index.min() < X_test.index.min()`, wired to fail loudly (non-zero exit) if the split logic is ever edited incorrectly. This has no test-discovery benefit and won't run in a `pytest` sweep, but costs zero new files/functions and satisfies the same "guardrail against the bug silently reappearing" goal from D-06. Norwegian-comment it as `# Garanti: de tre datasettene skal aldri overlappe`.

### Anti-Patterns to Avoid
- **Reusing `calibrate` as both `eval_set` for early stopping *and* the isotonic fit data without acknowledging it:** This is explicitly locked as acceptable by D-04 (a smaller, secondary leakage than the one being fixed), but it is a real, documented residual risk — see Open Questions below. Don't let it go undocumented in code comments; a one-line comment explaining why `calibrate` is used for both is cheap insurance against a future "why is early stopping using calibrate not test?" confusion.
- **Predicting on `test` raw scores using `out_of_bounds="nan"` (the sklearn default):** would silently introduce `NaN`s into the reliability table whenever `test`'s XGBoost scores fall outside `calibrate`'s observed range — a near-certainty given `calibrate` is only 172 games. The uncommitted diff already correctly sets `out_of_bounds="clip"`; keep it.
- **Increasing the holdout window's total size (beyond just moving the midpoint) to "fix" the small calibrate-set problem:** out of scope — CONTEXT.md D-03 locks the 3-way split to bisecting the *existing* 2-month holdout, not extending it. If `calibrate` size is a real concern, the correct in-scope response is a printed warning + honest labeling (D-03's own instruction: "flag this as a runtime check, not a fixed number"), not silently widening the training/holdout boundary, which would also shrink `train`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Monotonic probability calibration | A custom binning/averaging calibration function | `sklearn.isotonic.IsotonicRegression` (already used) | Already correctly implemented; hand-rolling a bucket-average calibrator would just reimplement a worse, unverified version of what's already there |
| Reliability/calibration curve binning | A hand-written percentile-bucket loop | `pd.cut(..., bins=10)` (already used in the uncommitted diff) — equivalent in spirit to `sklearn.calibration.calibration_curve`, which project convention (D-05: console table, no new dependency) explicitly chooses not to add | Console-table output is the locked reporting format; `pd.cut` bucketing is already correct and sufficient for this |

**Key insight:** Nothing in this phase needs new machinery — the uncommitted diff already contains correct calibration and reporting *mechanics* (isotonic fit call, `out_of_bounds="clip"`, 10-bucket console table). The entire fix is about *which slice* feeds which step, not about new algorithms or libraries.

## Common Pitfalls

### Pitfall 1: Isotonic regression overfits below ~1,000 calibration samples
**What goes wrong:** With only 172 games in `calibrate`, the fitted isotonic step function can be a needlessly jagged, high-variance mapping that overfits noise in that small slice rather than the model's true miscalibration pattern — potentially making calibration *worse* on `test` than the raw XGBoost scores were.
**Why it happens:** Isotonic regression is a non-parametric, unconstrained-shape (monotonic-only) fit; scikit-learn's own docs state it needs "greater than ~1000 samples" to reliably beat simpler sigmoid (Platt) calibration, and is "more prone to overfitting, especially on small datasets." [CITED: scikit-learn.org/stable/modules/calibration.html]
**How to avoid:** This phase's locked scope does not permit switching calibration methods (that would reopen CONTEXT.md's decisions). The mitigating, in-scope action is: (1) print the sklearn-documented size threshold alongside the actual `calibrate` size so future readers see the caveat every run, (2) report both pre- and post-calibration Brier/log-loss on `test` so a regression is visible immediately if it happens, (3) leave a code comment flagging this as a known limitation of splitting an already-small 2-month holdout three ways, for future phases (e.g., if a full-season backtest dataset later becomes available via ODDS-01, revisit whether `calibrate` can be enlarged).
**Warning signs:** `test`-split Brier score or log-loss *after* calibration is worse than *before* calibration in the printed comparison table — this would indicate the isotonic fit overfit `calibrate` and is now actively hurting generalization.

### Pitfall 2: `calibrate` doing double duty (early stopping + isotonic fit) reintroduces a milder version of the same leakage
**What goes wrong:** XGBoost's early stopping picks the number of trees based on `calibrate` performance; the isotonic calibrator is then fit on that same tree count's output on that same `calibrate` slice. The chosen model is thus (mildly) tuned to `calibrate`, and then calibration is fit on the very data that influenced the model. This is a smaller-scale version of the exact pattern this phase exists to eliminate.
**Why it happens:** This is a well-recognized general ML pattern — using the same validation slice for both early-stopping/hyperparameter selection and final calibration/evaluation biases both toward overly optimistic performance on that slice. [ASSUMED: general ML practice, not tied to a single citable source, but a widely-documented pattern; see also the calibration.html docs' emphasis on calibrator "held-out" fitting]
**How to avoid:** CONTEXT.md D-04 explicitly accepts this trade-off as in-scope and preferable to adding a fourth split (deferred to Phase 5's `BT-03` locked-holdout concept, which is a different, larger-scope idea). The correct action for this phase is: document the trade-off in a code comment near the `eval_set=[(X_kalibrer, y_kalibrer)]` line, and ensure `test` truly never appears in any `.fit()` call anywhere in the script (grep-checkable: `test` should only ever appear as an argument to `.predict()`/`.predict_proba()`, never `.fit()`).
**Warning signs:** Any future edit that adds `X_test`/`y_test` to a `.fit()`, `eval_set`, or similar training-influencing call — this is exactly the class of bug this phase exists to close, and D-06's "kalibrert på X, evaluert på Y" console labeling is the intended guardrail against it recurring silently.

### Pitfall 3: `out_of_bounds` default (`"nan"`) silently corrupting metrics
**What goes wrong:** If a future edit recreates `IsotonicRegression()` without `out_of_bounds="clip"`, any `test`-split raw score outside `calibrate`'s observed range predicts `NaN`, which then silently propagates into `log_loss`/`brier_score_loss` (raising an error) or, worse, into `pd.cut` bucket means (silently dropped, not erroring) — masking the real reliability picture.
**Why it happens:** `"nan"` is scikit-learn's documented default for `out_of_bounds`, not `"clip"`. [CITED: scikit-learn.org IsotonicRegression API docs]
**How to avoid:** Keep the existing `out_of_bounds="clip"` argument (already correct in the uncommitted diff) and don't let it get dropped in refactoring.
**Warning signs:** `log_loss`/`brier_score_loss` on `test` raising a `ValueError` about NaN input, or the console reliability table showing fewer than 10 non-empty buckets unexpectedly.

## Code Examples

### Full split + fit block (composed from Patterns 1 and 2 above)
```python
# Source: composed from sklearn.isotonic.IsotonicRegression docs +
# xgboost sklearn_estimator docs + this repo's own existing chronological-split style
maks_dato  = df["GAME_DATE_HJEMME"].max()
fra_dato   = maks_dato - pd.DateOffset(months=2)   # unchanged cutoff
midt_dato  = maks_dato - pd.DateOffset(months=1)   # NEW cutoff, bisects the holdout

tren_mask     = df["GAME_DATE_HJEMME"] < fra_dato
kalibrer_mask = (df["GAME_DATE_HJEMME"] >= fra_dato) & (df["GAME_DATE_HJEMME"] < midt_dato)
test_mask     = df["GAME_DATE_HJEMME"] >= midt_dato

X_tren,     y_tren     = X[tren_mask],     y[tren_mask]
X_kalibrer, y_kalibrer = X[kalibrer_mask], y[kalibrer_mask]
X_test,     y_test     = X[test_mask],     y[test_mask]

print(f"Treningssett:  {len(X_tren)} kamper")
print(f"Kalibreringssett: {len(X_kalibrer)} kamper")
print(f"Testsett:      {len(X_test)} kamper")
if len(X_kalibrer) < 1000:
    print(f"ADVARSEL: kalibreringssettet har kun {len(X_kalibrer)} kamper. "
          f"sklearn anbefaler >~1000 for isotonic regression for å unngå overfitting.")
```
Verified against this repo's actual `nba_features.csv` (3,638 games): produces `train`=3,217, `calibrate`=172, `test`=249, matching the counts reported in the Summary above.

## State of the Art

| Old Approach (current uncommitted diff) | Current/Fixed Approach (this phase) | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `kalibrerer.fit(y_rå, y_test)` where `y_rå` comes from `X_test` — fit and eval share `X_test`/`y_test` | `kalibrerer.fit(y_rå_kalibrer, y_kalibrer)` fit on `calibrate`; evaluation uses `test`'s raw scores passed through the fitted calibrator | This phase | Closes CALIB-01's same-slice leakage; reported calibration quality becomes genuinely out-of-sample for the first time |
| `eval_set=[(X_test, y_test)]` for early stopping | `eval_set=[(X_kalibrer, y_kalibrer)]` | This phase (D-04) | `test` is no longer touched by any `.fit()`-adjacent call; only ever scored/predicted on |

**Deprecated/outdated:** None — this is a bug fix to logic added in an uncommitted diff that was never deployed/committed, not a migration away from a previously-shipped behavior.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Reusing the same slice for early stopping and calibration fitting reintroduces a milder leakage bias (general ML principle, not tied to one specific citable source for this exact combination) | Common Pitfalls, Pitfall 2 | Low — this is widely accepted ML practice and is already explicitly accepted as a locked trade-off by CONTEXT.md D-04; if the underlying claim were somehow wrong, the only consequence is an unnecessary code comment, not an incorrect implementation |
| A2 | `pandas` version in the active venv is 3.0.1 (taken from CLAUDE.md's own tech-stack documentation, not independently re-verified via `pip show` in this research session) | Standard Stack | Low — `pandas` API surface used here (`pd.DateOffset`, boolean masking, `pd.cut`) has been stable for many major versions; even if the exact version differs slightly, none of this phase's code depends on version-specific pandas behavior |

## Open Questions (RESOLVED)

1. **RESOLVED: Is isotonic regression still the right calibration method given the actual `calibrate` sample size (172) falls well below sklearn's own ~1000-sample guidance?** — Keep isotonic regression (changing method is out of scope, would reopen a locked decision); Plan 03-02 Task 1 surfaces a runtime `ADVARSEL` warning instead.
   - What we know: scikit-learn's official docs explicitly recommend sigmoid/Platt scaling over isotonic when calibration data is scarce, and 172 is scarce by that standard.
   - What's unclear: Whether the resulting calibration curve on `test` will actually show harmful overfitting in practice (it may still be net-positive vs. no calibration at all) — this is an empirical question CONTEXT.md defers to runtime observation (D-03's "flag this as a runtime check, not a fixed number").
   - Recommendation: Not in scope to change the calibration method this phase (would reopen a locked decision). Planner should ensure the printed output makes the small-sample caveat visible every run, and that pre/post-calibration Brier/log-loss on `test` are both reported so a regression is immediately visible if it occurs. If the reliability table on `test` shows the calibrator making things worse, that's a finding for a future phase (or a fast-follow), not something to silently patch around inside this narrowly-scoped bug fix.

2. **RESOLVED: Should the split-boundary logic be extracted into a small pure/testable function, or should the regression test (if added) just duplicate the date-cutoff formula inline?** — Extracted: Plan 03-01 creates `kalibrering.del_kronologisk_3veis`, matching the Phase 2 `features.py`/`strategy.py` precedent.
   - What we know: CONTEXT.md leaves this fully to planner discretion; Phase 2 already established the precedent of extracting pure logic into importable, unit-testable functions (`features.py`, `strategy.py`) specifically to avoid needing to run full pipeline scripts in tests.
   - What's unclear: Whether extracting a function for this phase is worth the (small) extra diff given the phase is explicitly framed as "narrowly-scoped bug fix... not a new feature."
   - Recommendation: See Architecture Patterns, Pattern 3 — recommend the small pure-function extraction (fits established precedent, ~10 lines, testable with a synthetic-date fixture matching `conftest.py`'s existing style) but note the zero-new-files inline-`assert` fallback as an acceptable lower-effort alternative if the planner wants to minimize diff size.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `nba_features.csv` (local file) | The entire training script — must exist before running `03_tren_modell.py` | ✓ (confirmed present, 3,638 rows) | — | If missing on a fresh clone: run `01_hent_data.py` then `02_feature_engineering.py` first (existing pipeline order per `KOMME_I_GANG.md`) |
| `xgboost` | Model training | ✓ | 3.2.0 | — |
| `scikit-learn` | Isotonic calibration + metrics | ✓ | 1.8.0 | — |
| `pytest` + `pytest.ini` (`pythonpath = .`, `testpaths = tests`) | Optional regression test (if planner chooses the `tests/` route) | ✓ (37 existing tests collected successfully) | — | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None — everything needed is already present in the repo's committed `venv/`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (version bundled in `venv/`; `pytest.ini` present, `pythonpath = .`, `testpaths = tests`) |
| Config file | `pytest.ini` (repo root) |
| Quick run command | `venv/bin/python3 -m pytest tests/test_calibrering_split.py -q` (once created) |
| Full suite command | `venv/bin/python3 -m pytest -q` (currently 37 tests, all passing per this session's collection check) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CALIB-01 | `train`/`calibrate`/`test` date ranges are non-overlapping and chronologically ordered; calibrator fit call only ever receives `calibrate` data | unit (on extracted pure split function) | `venv/bin/python3 -m pytest tests/test_calibrering_split.py -x` | ❌ Wave 0 |
| CALIB-02 | Reliability table is computed and printed using only `test`-split predictions through the already-fitted calibrator | manual/smoke — no existing convention in this repo for testing full top-level script execution (`03_tren_modell.py` has no `main()` guard, trains a real model, writes `nba_modell.pkl`); verify by running the script end-to-end and inspecting console output for the labeled "kalibrert på X, evaluert på Y" table (D-06) | `venv/bin/python3 03_tren_modell.py` (manual inspection of stdout) | N/A — script itself, not a test file |

### Sampling Rate
- **Per task commit:** `venv/bin/python3 -m pytest -q` (fast — 37 existing tests run in well under a second; adding one more small test file won't meaningfully change this)
- **Per wave merge:** same full suite, plus one manual run of `venv/bin/python3 03_tren_modell.py` to visually confirm the reliability table prints correctly and `nba_modell.pkl` is regenerated without errors
- **Phase gate:** Full pytest suite green + one clean manual run of `03_tren_modell.py` producing a labeled, non-`NaN` reliability table before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_calibrering_split.py` — covers CALIB-01 (non-overlap/chronological-order assertions on the split logic)
- [ ] If Pattern 3's pure-function extraction is chosen: the extracted function itself (e.g., `del_kronologisk_3veis`) — new, small, needs to be written before the test can import it
- [ ] No new fixtures strictly required — `tests/conftest.py`'s existing `kamper_df`/date-fixture style can be reused or a minimal inline synthetic DataFrame can be built directly in the new test file, consistent with how `test_features.py` already does date-based synthetic fixtures

*(CALIB-02 has no Wave 0 gap — it's satisfied by manual/smoke verification of existing script output, matching this repo's established convention of not unit-testing the top-level numbered pipeline scripts themselves.)*

## Security Domain

**`security_enforcement`:** not present in `.planning/config.json` — treated as enabled per default, but this phase has essentially no attack surface to assess.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No auth in this offline training script |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | Marginal | `nba_features.csv` is a locally-generated, trusted intermediate artifact (produced by this same pipeline's `02_feature_engineering.py`), not external/untrusted input — no new validation warranted this phase |
| V6 Cryptography | No | N/A — no secrets, keys, or crypto touched by this phase (the Odds API key lives in `04_value_detector.py`, untouched here) |

### Known Threat Patterns for this stack
None applicable — this is an offline, single-user, no-network, no-user-input batch training script. No STRIDE-relevant threat patterns identified for this phase's scope.

## Sources

### Primary (HIGH confidence)
- scikit-learn `IsotonicRegression` API docs (https://scikit-learn.org/stable/modules/generated/sklearn.isotonic.IsotonicRegression.html) — fit signature, `out_of_bounds` parameter default/behavior
- scikit-learn Probability Calibration guide (https://scikit-learn.org/stable/modules/calibration.html) — isotonic vs. sigmoid sample-size guidance ("~1000 samples"), reliability-diagram/calibration-curve construction methodology
- xgboost sklearn estimator interface docs (https://xgboost.readthedocs.io/en/latest/python/sklearn_estimator.html) — `early_stopping_rounds` as constructor param + `eval_set` in `.fit()`, current non-deprecated pattern
- This repo's own `venv/` (`venv/bin/python3 -c "import xgboost/sklearn; print(__version__)"`) — confirmed installed versions xgboost 3.2.0, scikit-learn 1.8.0
- This repo's own `nba_features.csv` (queried directly via pandas in this session) — confirmed actual split sizes: train=3,217, calibrate=172, test=249 games
- This repo's own `pytest.ini` + `tests/` directory (collected via `pytest --collect-only`) — confirmed 37 existing tests, `pythonpath = .` working

### Secondary (MEDIUM confidence)
- General ML literature on validation-set reuse for early stopping + calibration/evaluation (WebSearch, cross-referenced against the same underlying principle scikit-learn's own calibration docs describe for held-out calibration data) — supports Pitfall 2's framing

### Tertiary (LOW confidence)
- None used as load-bearing claims — all size-threshold and API-behavior claims above were verified against official docs or this repo's own environment.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; versions confirmed directly against this repo's own venv
- Architecture: HIGH — split logic is arithmetic on dates already verified against the real dataset; xgboost/sklearn API patterns confirmed against official docs
- Pitfalls: MEDIUM — the ~1,000-sample isotonic guidance is a HIGH-confidence documented fact, but *how much* it will actually hurt calibration quality on this specific 172-game slice is an empirical question this research cannot resolve without running the actual fit (left as an Open Question / runtime observation per CONTEXT.md D-03's own framing)

**Research date:** 2026-08-21
**Valid until:** 30 days (stable ecosystem — scikit-learn/xgboost calibration APIs are not fast-moving; the dataset-size findings are specific to this repo's current `nba_features.csv` and should be re-checked if the dataset grows materially, e.g. after ODDS-01/Phase 4/5 work)
