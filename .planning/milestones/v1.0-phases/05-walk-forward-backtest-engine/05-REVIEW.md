---
phase: 05-walk-forward-backtest-engine
reviewed: 2026-08-29T07:43:55Z
depth: standard
files_reviewed: 21
files_reviewed_list:
  - 03_tren_modell.py
  - 08_kjor_backtest.py
  - backtest.py
  - config.py
  - metrics.py
  - model.py
  - odds.py
  - skadefilter.py
  - spillerlogg.py
  - verdi_deteksjon.py
  - tests/test_backtest.py
  - tests/test_calibrering_split.py
  - tests/test_kjor_backtest.py
  - tests/test_metrics.py
  - tests/test_model.py
  - tests/test_odds.py
  - tests/test_oppsett.py
  - tests/test_parity.py
  - tests/test_skadefilter.py
  - tests/test_spillerlogg.py
  - tests/test_strategy.py
findings:
  critical: 1
  warning: 3
  info: 1
  total: 5
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-08-29T07:43:55Z
**Depth:** standard
**Files Reviewed:** 21 (10 production, 11 test)
**Status:** issues_found

## Fixes Applied (2026-08-29, same session)

- **CR-01: FIXED.** `08_kjor_backtest.py` now validates `--min-treningskamper >= model.MIN_KALIBRERINGSKAMPER + model.MIN_TRENING_ETTER_KALIBRERING` (100) in `main()`, rejecting with `parser.error` (exit 2) before any run starts. Regression tests added: `test_cli_avviser_min_treningskamper_under_kalibreringsgulvet`, `test_min_treningskamper_gulv_matcher_model_konstantene`.
- **WR-01: FIXED.** `--min-value-terskel` now rejects negative values with `parser.error`. Regression test added: `test_cli_avviser_negativ_min_value_terskel`.
- **WR-02, WR-03: DEFERRED.** Both are lower-severity (reporting-window semantics and redundant I/O, not correctness-breaking), don't affect the already-completed holdout run (which used the defaults these findings don't touch), and need more design judgment than a mechanical fix. Left as documented follow-up items for a future session.
- Full suite green at 349 tests (346 + 3 new regression tests) after the fixes.

## Summary

This is a carefully engineered walk-forward backtest engine with genuinely structural (not just conventional) safeguards: the `HoldoutLaastFeil` gate is enforced at both a pre-flight pass and per-iteration inside `kjor_backtest`, `run_id` path construction is defended against traversal in two independent ways, all SQL in `odds.py` is fully parameterized, and the decision-boundary discipline (never reading an outcome or a closing price before a stake is computed) is consistently honored across `backtest.py`. The 05-11/05-13 test suite (`test_parity.py`, `test_backtest.py`, `test_kjor_backtest.py`) is unusually thorough, including source-level assertions that forbid bare `except:` and that only one function may ever pass `holdout=True`.

The one BLOCKER found is real and reproducible: `model.py`'s D-05-05 calibration-floor fix (`MIN_KALIBRERINGSKAMPER`/`MIN_TRENING_ETTER_KALIBRERING`), which exists specifically to prevent the isotonic-regression saturation bug that once made ~38% of bets show `modell_prob==1.0`, is silently defeatable through the `08_kjor_backtest.py` `--min-treningskamper` CLI flag (or any direct `min_treningskamper=` override below 100) with no validation tying the two together — reproduced below. The remaining findings are lower-severity validation/reporting gaps.

## Critical Issues

### CR-01: `--min-treningskamper` can silently collapse the calibration set below its own safety floor

**File:** `08_kjor_backtest.py:227-235`, `model.py:117-139`
**Issue:**
`model.py`'s `del_for_trening` was fixed under D-05-05 specifically because a plain `kalibrer_andel` split could produce a calibration bucket small enough (~15 rows) to saturate isotonic regression — observed in practice as ~38% of bets with `modell_prob==1.0` (see `model.py:39-50`). The fix adds two absolute floors, `MIN_KALIBRERINGSKAMPER=50` and `MIN_TRENING_ETTER_KALIBRERING=50`, and the code comment at `model.py:131-137` explicitly states the two floors can never collide "in practice" only *because* `backtest.MIN_TRENINGSKAMPER=100` happens to equal `50+50`.

That assumption is not enforced anywhere. `08_kjor_backtest.py:227-235` exposes `--min-treningskamper` as a bare `type=int` argument with no lower bound (no validator analogous to `positiv_flyt`, and no check against `model.MIN_KALIBRERINGSKAMPER + model.MIN_TRENING_ETTER_KALIBRERING`). Any window smaller than 100 rows (`--min-treningskamper` below 100, or any other caller of `backtest.kjor_backtest(..., min_treningskamper=<N<100>)`) silently produces a calibration bucket below the intended 50-row floor with no exception, no warning, and no manifest flag — i.e. it can silently reproduce the exact degeneracy this fix was built to prevent.

Reproduced directly against `model.del_for_trening` with a 60-row pre-`as_of` window (reachable via e.g. `--min-treningskamper 60`):

```
tren rows: 50  kalibrer rows: 10
MIN_KALIBRERINGSKAMPER: 50   MIN_TRENING_ETTER_KALIBRERING: 50
```

The training floor "wins" the collision (as the comment predicts), but the calibration bucket collapses to 10 rows — well under its own 50-row floor — with no error surfaced anywhere in the CLI, `kjor_backtest`'s counters, or `manifest.json`.

**Fix:** Enforce the invariant the comment already assumes, either by validating in `08_kjor_backtest.py::main()` (alongside the existing `--kelly-fraksjon`/`--min-odds` checks) or defensively inside `model.del_for_trening`:
```python
# 08_kjor_backtest.py, alongside the other parser.error() checks in main()
_MIN_VINDU = model.MIN_KALIBRERINGSKAMPER + model.MIN_TRENING_ETTER_KALIBRERING
if args.min_treningskamper < _MIN_VINDU:
    parser.error(
        f"--min-treningskamper {args.min_treningskamper} er under "
        f"model.MIN_KALIBRERINGSKAMPER + model.MIN_TRENING_ETTER_KALIBRERING "
        f"({_MIN_VINDU}) — et mindre vindu kan kollidere med kalibreringsgulvet "
        "og stille gjeninnføre isotonic-metningsbuggen D-05-05 fikset."
    )
```

## Warnings

### WR-01: `--min-value-terskel` has no bounds validation, unlike its sibling threshold flags

**File:** `08_kjor_backtest.py:185-190`, `08_kjor_backtest.py:499-518`
**Issue:** `main()` validates `--kelly-fraksjon` (must be in `(0, 1]`, `08_kjor_backtest.py:503`) and `--min-odds < --maks-odds` (`08_kjor_backtest.py:514`), but `--min-value-terskel` (`type=float`, default `config.MIN_VALUE_TERSKEL`) has no validator at all. A negative or zero value passed here flows straight into `vurder_kamp`'s `value_hjemme > min_value_terskel` comparison (`backtest.py:130`) and would flag nearly every game with any modeled edge — including negative-edge games — as a "value bet," producing a backtest that looks like it is finding value everywhere without any error, warning, or manifest annotation distinguishing it from a legitimate run.
**Fix:** Either document that `0` is an intentionally allowed research value and reject negatives explicitly, or add a bound consistent with the other threshold flags:
```python
if args.min_value_terskel < 0:
    parser.error(
        f"--min-value-terskel {args.min_value_terskel} er negativ — dette "
        "ville flagget nesten hver kamp med noe modell-edge som en value bet"
    )
```

### WR-02: Burn-in window is derived from months present in the ledger, not months actually processed — can silently misalign with thin-coverage early data

**File:** `backtest.py:806-825`, `backtest.py:862-863`
**Issue:** `filtrer_ledger_etter_innbrenning` drops the first `innbrenning_maaneder` *distinct calendar months present in `ledger`* (`backtest.py:823-824`), not the first N calendar months of the backtest's processed date range. `bygg_manifest`'s own `datakvalitet` docstring (`backtest.py:858-861`) independently flags "tynn EU-region-bookmaker-dekning tidlig i 2022-23" as an accepted data-quality gap. If an early month has zero flagged/placed bets (plausible given that documented thin coverage), it contributes no row to `ledger` and is therefore invisible to the burn-in filter — the filter then excises whichever *later* bet-bearing month happens to be third in the sorted set instead, which is not the model's actual early/noisy retraining period the burn-in sensitivity check is meant to isolate. This doesn't crash anything, but it can make `metrikker_uten_innbrenning` (the sensitivity number BT-05's before/after comparison leans on) quietly answer a different question than intended in exactly the months where coverage is worst.
**Fix:** Either compute the burn-in cutoff from `resultat_predict["fra_dato"]` plus N calendar months (independent of which months happen to have bets) and filter the ledger against that date, or explicitly document in the manifest which real calendar months were skipped versus dropped so a reader can tell the two apart.

### WR-03: `klargjor_backtestdata` reads `features_fil` from disk twice on every real (non-injected) run

**File:** `backtest.py:199-212`
**Issue:** When `features_df` is not injected (the normal CLI path), `klargjor_backtestdata` calls `odds.hent_unike_kampdatoer(features_fil, ...)` (which itself does `pd.read_csv(features_fil)` internally, `odds.py:747`) and then separately does `features_df = pd.read_csv(features_fil)` (`backtest.py:200`) to build the DataFrame it actually uses. Both reads parse the same `GAME_DATE_HJEMME` column independently. This is harmless today (single-threaded, file not mutated mid-run) but is redundant I/O and a latent inconsistency risk if `nba_features.csv` is ever regenerated concurrently with a running backtest, or if a future change causes the two read paths to apply different dtype/parsing rules to the same column.
**Fix:** Read once and derive `datoer` from the already-loaded `features_df` (as already done in the `features_df is not None` branch just below), or pass the already-read DataFrame into `odds.hent_unike_kampdatoer` instead of re-reading from disk.

## Info

### IN-01: Test suite is thorough; no test-quality blockers found

**File:** `tests/test_backtest.py`, `tests/test_kjor_backtest.py`, `tests/test_parity.py`, `tests/test_model.py`
**Issue:** Not a defect — noted for completeness. The 5,200+ lines of tests across these files include source-level guard tests (e.g. `tests/test_backtest.py:502` and `tests/test_kjor_backtest.py:170` assert `"except:"` never appears in the reviewed source, and `tests/test_kjor_backtest.py:313` asserts only `kjor_holdout` may contain the token `holdout=True`), explicit BT-02/BT-03 parity and non-leakage tests, and edge-case coverage for the calibration-floor collision boundary (`tests/test_model.py:132-178`) — though that coverage stops at exactly `n=100` and `n=500` and does not exercise the sub-100-row collision documented in CR-01.
**Fix:** N/A — recommend adding a regression test for CR-01's fix once implemented (a `--min-treningskamper` value below `MIN_KALIBRERINGSKAMPER + MIN_TRENING_ETTER_KALIBRERING` should be rejected, or `del_for_trening` should raise rather than silently under-floor).

---

_Reviewed: 2026-08-29T07:43:55Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
