---
phase: 5
slug: walk-forward-backtest-engine
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-24
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (version per `requirements.txt`; 129 tests currently collected) |
| **Config file** | `pytest.ini` (`pythonpath = .`, `testpaths = tests`) |
| **Quick run command** | `python3 -m pytest tests/test_backtest.py tests/test_metrics.py tests/test_model.py -q` |
| **Full suite command** | `python3 -m pytest tests/ -q` |
| **Estimated runtime** | ~10-20 seconds (no network calls in unit tests; walk-forward loop itself is exercised only against small synthetic fixtures) |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/test_backtest.py tests/test_metrics.py tests/test_model.py -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -q` (full 129+ suite)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-07-02 | 05-07 | 5 | BT-01 | T-05-07-07 | Walk-forward loop produces a ledger for a small synthetic date range | unit/integration | `pytest tests/test_backtest.py::test_kjor_backtest_produserer_ledger -x` | ✅ tests/test_backtest.py | ✅ green |
| 05-07-03 | 05-07 | 5 | BT-02 | T-05-07-05 | Feature/odds/injury lookups never see data dated `>= as_of` | unit (leakage regression, extends `test_parity.py`) | `pytest tests/test_parity.py -x` | ✅ tests/test_backtest.py | ✅ green |
| 05-07-01 | 05-07 | 5 | BT-03 | T-05-07-01 | `kjor_backtest()` raises `HoldoutLaastFeil` for any date `>= HOLDOUT_START_DATO` unless called via `kjor_endelig_holdout_backtest()` | unit | `pytest tests/test_backtest.py::test_holdout_guard_reiser_feil -x` | ✅ tests/test_backtest.py | ✅ green |
| 05-08-02 | 05-08 | 6 | BT-04 | T-05-08-06 | `bootstrap_roi_ci`/`wilson_ci` match hand-calculated values on a known synthetic bet sequence | unit | `pytest tests/test_metrics.py::test_bootstrap_roi_ci_kjente_verdier -x` | ✅ tests/test_metrics.py + tests/test_backtest.py | ✅ green |
| 05-08-02 | 05-08 | 6 | BT-05 | T-05-08-04 | `manifest.json` round-trips config + metrics correctly, `run_id` unique per config | unit | `pytest tests/test_backtest.py::test_manifest_inneholder_konfig_og_metrikker -x` | ✅ tests/test_backtest.py | ✅ green |
| 05-08-01 | 05-08 | 6 | BT-06 | T-05-08-07 | CLV computed as `fjern_vigorish(bet_time) - fjern_vigorish(closing)`, `None` when closing snapshot missing | unit | `pytest tests/test_metrics.py::test_clv_beregning -x` | ✅ tests/test_metrics.py + tests/test_backtest.py | ✅ green |
| 05-09-01 | 05-09 | 7 | BT-07 | T-05-09-01 | Kelly sweep produces 4 distinct entries (flat/quarter/half/full) from one cached predict pass, never re-running the walk-forward loop | unit | `pytest tests/test_backtest.py::test_kelly_sweep_bruker_cachet_prediksjoner -x` | tests/test_backtest.py | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Task IDs and wave assignment are TBD — the planner fills these in once PLAN.md files exist; this table's Req/Test/Command columns are locked from research and must not be re-derived.*

---

## Wave 0 Requirements

- [ ] `tests/test_model.py` — covers `model.py::tren()`'s one-shot vs. walk-forward split behavior
- [ ] `tests/test_backtest.py` — covers the walk-forward loop, holdout guard, and Kelly-sweep caching
- [ ] `tests/test_metrics.py` — covers bootstrap CI, Wilson interval, CLV, drawdown arithmetic against hand-calculated synthetic values
- [ ] Extend `tests/test_parity.py` per its own existing docstring instruction — add the live-vs-backtest side-by-side decision-parity assertion once `backtest.py` exists
- [ ] `tests/test_skadefilter.py` — new as-of-aware test cases using an injected synthetic player-log fixture (no network), mirroring the existing `siste3`/`sesong_snitt` injection pattern already used for the live path (required since the injury-filter backtest is in scope per 05-CONTEXT.md's Post-Research Resolution)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full-history backtest run produces plausible, non-degenerate ROI/drawdown numbers (not just correct plumbing) | BT-01, BT-04 | Statistical plausibility of a real multi-season run isn't a unit-testable assertion — it requires human judgment on whether the numbers look sane before trusting them for a go/no-go decision | Run `08_kjor_backtest.py` end-to-end against the full train/calibrate slice (2022-23+2023-24), inspect `manifest.json` for a sane bet count, ROI within a plausible range, and a CI width that isn't absurdly wide for the sample size |
| Final locked-holdout run is checked exactly once and matches the "checked once" intent | BT-03 | Enforcing "exactly once" as a runtime invariant across the *project's lifetime* (not just one process run) isn't mechanically testable in a unit test — it's a human-process guarantee the code only makes structurally hard to violate accidentally | Before running `kjor_endelig_holdout_backtest()`, manually confirm no prior holdout run exists for this config; after running, record the run_id/date in STATE.md so future sessions know the holdout has been spent |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
