---
phase: 05-walk-forward-backtest-engine
plan: 03
subsystem: backtest-reporting
tags: [metrics, roi, bootstrap-ci, wilson-ci, clv, numpy, pytest]

# Dependency graph
requires:
  - phase: 05-walk-forward-backtest-engine (plan 01)
    provides: HOLDOUT_START_DATO tripwire, locked D-05-01..D-05-04 decisions
  - phase: 02-shared-strategy-core
    provides: strategy.fjern_vigorish (the single vig-removal implementation this plan reuses for CLV)
provides:
  - "metrics.py — pure, zero-I/O reporting layer with 9 functions covering BT-04 (ROI/vinnrate/drawdown/CI) and BT-06 (CLV)"
  - "oppsummer_ledger() — the single JSON-serialisable manifest-ready aggregation entry point for plans 05-08/05-09"
  - "tests/test_metrics.py — 23 hand-derivable tests, including the two pinned names test_bootstrap_roi_ci_kjente_verdier and test_clv_beregning"
affects: [05-08-backtest-orchestrator, 05-09-kelly-sweep, 05-10-cli-entrypoint, 05-12-human-verify-checkpoint]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Percentile-method bootstrap CI over bets (not games/dates), seeded via np.random.default_rng, scipy-free (hardcoded z=1.96 for Wilson)"
    - "Every metrics.py return value explicitly cast to plain Python float/int so json.dumps never sees a numpy.float64"
    - "CLV reuses strategy.fjern_vigorish instead of re-deriving vig removal locally — proven by monkeypatch, not just by grep"

key-files:
  created:
    - metrics.py
    - tests/test_metrics.py
  modified: []

key-decisions:
  - "CLV sign convention locked exactly as 05-CONTEXT.md specifies: closing vig-free prob minus bet-time vig-free prob, so positive = bet beat the close"
  - "aggreger_clv reports andel_slo_closing (share of clv > 0) as an unambiguous companion field alongside clv_snitt, so plan 05-12's human-verify checkpoint cannot misread the sign"
  - "oppsummer_ledger is entirely date-unaware, letting plan 05-08 call it repeatedly over date-filtered ledger slices (full-period + ex-burn-in) at near-zero cost per D-05-02"

patterns-established:
  - "Purity-guard test pattern: read metrics.py source via pathlib, assert absence of open(/to_csv/scipy/config/pandas imports — mirrors tests/test_strategy.py's config-has-no-secrets test"

requirements-completed: [BT-04, BT-06]

# Metrics
duration: 35min
completed: 2026-08-27
---

# Phase 5 Plan 3: metrics.py — Backtest Reporting Layer Summary

**Pure, zero-I/O reporting module turning a settled bet ledger into ROI/win-rate/drawdown with bootstrap and Wilson confidence intervals plus CLV computed exclusively through `strategy.fjern_vigorish`, composed into one JSON-serialisable `oppsummer_ledger()` entry point.**

## Performance

- **Duration:** 35min (Task 1: 11:45, Task 2: 12:00, Task 3: 12:20 — Task 3 execution was interrupted mid-planning by a machine sleep event and resumed as a continuation with no partial code on disk)
- **Started:** 2026-08-27T11:45:00+02:00 (Task 1 commit)
- **Completed:** 2026-08-27T12:20:51+02:00 (Task 3 commit)
- **Tasks:** 3/3 completed
- **Files modified:** 2 (`metrics.py`, `tests/test_metrics.py`)

## Accomplishments

- `metrics.py` now exposes all nine functions BT-04/BT-06 require: `beregn_profitt`, `beregn_roi`, `beregn_vinnrate`, `beregn_maks_drawdown`, `bootstrap_roi_ci`, `wilson_ci`, `beregn_clv`, `aggreger_clv`, `oppsummer_ledger` — exactly two module-level imports (`numpy as np`, `from strategy import fjern_vigorish`), no scipy, no I/O.
- CLV is computed via two calls to the one shared `fjern_vigorish` implementation in the whole repo, with the sign convention (`closing − bet_time`, positive = beat the close) proven both by a hand-calculated test and by a monkeypatch test that would fail if a local re-derivation silently took over.
- `oppsummer_ledger()` composes every other function into a flat, `json.dumps`-safe dict carrying `bootstrap_seed`/`bootstrap_n_resamples` for manifest reproducibility (BT-05), and is date-unaware so plan 05-08 can call it repeatedly over filtered slices.
- Full test suite: 164 tests passing (155 pre-existing + 9 new from Task 3; Tasks 1+2 had already brought the suite to 155 in a prior session).

## Task Commits

Each task was committed atomically:

1. **Task 1: metrics.py ledger core — profit, ROI, win rate, max drawdown** - `7dd07ef` (feat) — completed in a prior session
2. **Task 2: bootstrap ROI CI and Wilson win-rate CI, scipy-free** - `33d95b3` (feat) — completed in a prior session
3. **Task 3: CLV via strategy.fjern_vigorish, oppsummer_ledger, purity guards** - `6d891b1` (feat) — completed this session

_No TDD RED/GREEN split commits were used — each task's tests and implementation landed together in one commit, consistent with how Tasks 1 and 2 were already committed before this continuation began._

## Files Created/Modified

- `metrics.py` — pure reporting module (2 module-level imports, 9 functions, no I/O)
- `tests/test_metrics.py` — 23 tests, every expected value hand-derivable from an in-file comment

## Decisions Made

- CLV sign convention implemented exactly as locked in `05-CONTEXT.md` (closing minus bet-time; positive = bet beat the close) — no re-derivation, no flip.
- `aggreger_clv` treats a missing closing snapshot as counted-not-dropped data (`antall_uten_clv`), never silently discarded, per 05-RESEARCH.md's Pitfall 2 skip-and-log discipline applied to the reporting layer.
- `oppsummer_ledger`'s `clv_verdier=None` default path returns the same four CLV keys with `None`/`0` placeholders rather than omitting them, so the dict's key set — and therefore plan 05-08's `manifest.json` schema — is stable whether or not CLV data is supplied.

## Deviations from Plan

None — plan executed exactly as written across all three tasks. Task 3's execution was interrupted mid-session by a machine sleep event before any code was written; per the checkpoint resolution note, it was treated as a clean restart with no salvage needed.

## Kontrakt for 05-08 / 05-09

Final public signatures in `metrics.py`:

```python
beregn_profitt(innsats, odds, vant) -> float
beregn_roi(profitter, innsatser) -> float
beregn_vinnrate(vant_flagg) -> tuple[float, int, int]              # (vinnrate, antall_vunnet, antall_totalt)
beregn_maks_drawdown(profitter, startkapital) -> tuple[float, float]  # (kroner, andel)
bootstrap_roi_ci(profitter, innsatser, n_resamples=1000, seed=42, konfidensnivaa=0.95) -> tuple[float, float, float]  # (punktestimat, nedre, oevre)
wilson_ci(antall_vunnet, antall_totalt, z=1.96) -> tuple[float, float, float]  # (p, nedre, oevre)
beregn_clv(odds_bet_time_hjemme, odds_bet_time_borte, odds_closing_hjemme, odds_closing_borte, side) -> float | None
aggreger_clv(clv_verdier) -> dict  # clv_snitt, antall_med_clv, antall_uten_clv, andel_slo_closing
oppsummer_ledger(profitter, innsatser, vant_flagg, startkapital, clv_verdier=None, n_resamples=1000, seed=42) -> dict
```

`oppsummer_ledger()`'s exact returned key list (all plain Python `float`/`int`/`None`, `json.dumps`-safe):

```
antall_bets, sum_innsats, sum_profitt,
roi, roi_ci_nedre, roi_ci_oevre,
vinnrate, antall_vunnet, vinnrate_ci_nedre, vinnrate_ci_oevre,
maks_drawdown_kroner, maks_drawdown_andel,
bootstrap_seed, bootstrap_n_resamples,
clv_snitt, antall_med_clv, antall_uten_clv, andel_slo_closing
```

`side` in `beregn_clv` is the canonical token `"hjemme"` or `"borte"` — not the ledger's display string. Plan 05-08's caller is responsible for translating before calling.

## CLV-fortegn

A **positive** `clv` (and a positive `clv_snitt` in `aggreger_clv`'s output) means the bet beat the closing line — the bet-time price was better than the price the market settled on. This is `closing_vig_free_prob − bet_time_vig_free_prob`, computed via two calls to `strategy.fjern_vigorish`, never a local re-derivation. `andel_slo_closing` (share of `clv > 0`) is the unambiguous companion field: plans 05-08, 05-09 and 05-12 should read both fields but never need to re-derive the sign from source.

## Self-Check: PASSED

- `metrics.py` exists: FOUND
- `tests/test_metrics.py` exists: FOUND
- Commit `7dd07ef` exists: FOUND
- Commit `33d95b3` exists: FOUND
- Commit `6d891b1` exists: FOUND
- `python3 -m pytest tests/test_metrics.py -q` → 23 passed
- `python3 -m pytest tests/ -q` → 164 passed
