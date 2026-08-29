---
phase: 5
slug: walk-forward-backtest-engine
status: complete
nyquist_compliant: true
wave_0_complete: true
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
| 05-11-01 | 05-11 | 8 | BT-02 | T-05-11-01, T-05-11-02 | Feature/odds/injury lookups never see data dated `>= as_of` | unit (leakage regression, extends `test_parity.py`) | `pytest tests/test_parity.py -x` | ✅ utvidet | ✅ green |
| 05-07-01 | 05-07 | 5 | BT-03 | T-05-07-01 | `kjor_backtest()` raises `HoldoutLaastFeil` for any date `>= HOLDOUT_START_DATO` unless called via `kjor_endelig_holdout_backtest()` | unit | `pytest tests/test_backtest.py::test_holdout_guard_reiser_feil -x` | ✅ tests/test_backtest.py | ✅ green |
| 05-08-02 | 05-08 | 6 | BT-04 | T-05-08-06 | `bootstrap_roi_ci`/`wilson_ci` match hand-calculated values on a known synthetic bet sequence | unit | `pytest tests/test_metrics.py::test_bootstrap_roi_ci_kjente_verdier -x` | ✅ tests/test_metrics.py + tests/test_backtest.py | ✅ green |
| 05-08-02 | 05-08 | 6 | BT-05 | T-05-08-04 | `manifest.json` round-trips config + metrics correctly, `run_id` unique per config | unit | `pytest tests/test_backtest.py::test_manifest_inneholder_konfig_og_metrikker -x` | ✅ tests/test_backtest.py | ✅ green |
| 05-08-01 | 05-08 | 6 | BT-06 | T-05-08-07 | CLV computed as `fjern_vigorish(bet_time) - fjern_vigorish(closing)`, `None` when closing snapshot missing | unit | `pytest tests/test_metrics.py::test_clv_beregning -x` | ✅ tests/test_metrics.py + tests/test_backtest.py | ✅ green |
| 05-09-01 | 05-09 | 7 | BT-07 | T-05-09-01 | Kelly sweep produces 4 distinct entries (flat/quarter/half/full) from one cached predict pass, never re-running the walk-forward loop | unit | `pytest tests/test_backtest.py::test_kelly_sweep_bruker_cachet_prediksjoner -x` | tests/test_backtest.py | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Task IDs and wave assignment are TBD — the planner fills these in once PLAN.md files exist; this table's Req/Test/Command columns are locked from research and must not be re-derived.*

---

## Wave 0 Requirements

- [x] `tests/test_model.py` — covers `model.py::tren()`'s one-shot vs. walk-forward split behavior. Verified: `pytest tests/test_model.py -q` -> `13 passed` (as part of the plan 05-11 quick-run: `pytest tests/test_backtest.py tests/test_metrics.py tests/test_model.py -q` -> `140 passed in 23.61s`).
- [x] `tests/test_backtest.py` — covers the walk-forward loop, holdout guard, and Kelly-sweep caching. Verified: `104` tests collected, green in the same quick-run above.
- [x] `tests/test_metrics.py` — covers bootstrap CI, Wilson interval, CLV, drawdown arithmetic against hand-calculated synthetic values. Verified: `23` tests collected, green in the same quick-run above.
- [x] Extend `tests/test_parity.py` per its own existing docstring instruction — add the live-vs-backtest side-by-side decision-parity assertion once `backtest.py` exists. Verified: `pytest tests/test_parity.py -x -q` -> `17 passed` (plan 05-11, this row's own locked command).
- [x] `tests/test_skadefilter.py` — new as-of-aware test cases using an injected synthetic player-log fixture (no network), mirroring the existing `siste3`/`sesong_snitt` injection pattern already used for the live path (required since the injury-filter backtest is in scope per 05-CONTEXT.md's Post-Research Resolution). Verified: `pytest tests/test_skadefilter.py -q` -> `22 passed in 0.21s`, run directly by plan 05-11 rather than inferred from the full-suite total.

---

## Full-suite gate (plan 05-11)

Run from the repo root with the venv active (`source venv/bin/activate`), 2026-08-28:

**Command:** `python3 -m pytest tests/ -q`

**Verbatim final summary line:** `344 passed, 45 warnings in 53.68s`

**Collected count:** `344` tests (`python3 -m pytest tests/ -q --collect-only` -> `344 tests collected in 1.29s`), strictly above the pre-Phase-5 baseline of `129`.

**Per-file collected counts (from the same `--collect-only` run):**

| File | Collected |
|------|-----------|
| `tests/test_parity.py` | 17 |
| `tests/test_backtest.py` | 104 |
| `tests/test_metrics.py` | 23 |
| `tests/test_model.py` | 13 |
| `tests/test_spillerlogg.py` | 11 |
| `tests/test_skadefilter.py` | 22 |

**BT-02 row's own locked command, run and observed independently:** `python3 -m pytest tests/test_parity.py -x -q` -> `17 passed in 1.62s`.

**Quick-run command (05-VALIDATION.md's declared command):** `python3 -m pytest tests/test_backtest.py tests/test_metrics.py tests/test_model.py -q` -> `140 passed, 45 warnings in 23.61s`.

**Plan 05-10 landed at gate time:** yes. `08_kjor_backtest.py` exists and `python3 08_kjor_backtest.py --help` exits `0`, printing the full CLI argument list (`--fra`, `--til`, `--sweep`, `--holdout`, `--bekreft-holdout`, `--uten-skadefilter`, threshold/odds/Kelly/startkapital overrides, `--min-treningskamper`, `--features-fil`, `--arkiv`, `--katalog`, `--stille`). The gate therefore covers all ten landed plans of the outline (05-01 through 05-10) plus this plan's own extension of `tests/test_parity.py`.

**Zero failures, zero errors.** The only pytest warnings observed are xgboost's own `UserWarning: Parameters: { "use_label_encoder" } are not used.`, unrelated to this plan or to Phase 5's test additions — pre-existing noise from the pinned `xgboost` version, not a new finding.

**No production file modified by this plan:** `git diff --name-only backtest.py odds.py verdi_deteksjon.py strategy.py config.py features.py model.py metrics.py skadefilter.py spillerlogg.py teams.py` — empty.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions | Utfall |
|----------|-------------|------------|-------------------|--------|
| Full-history backtest run produces plausible, non-degenerate ROI/drawdown numbers (not just correct plumbing) | BT-01, BT-04 | Statistical plausibility of a real multi-season run isn't a unit-testable assertion — it requires human judgment on whether the numbers look sane before trusting them for a go/no-go decision | Run `08_kjor_backtest.py` end-to-end against the full train/calibrate slice (2022-23+2023-24), inspect `manifest.json` for a sane bet count, ROI within a plausible range, and a CI width that isn't absurdly wide for the sample size | ✅ utført 2026-08-28 — run_id `20260828-095233-3cc4a836` (tuning-slice, frosset konfigurasjon), 52 bets, ROI 15.0% (KI -11.9% – 42.9%), maks drawdown 7.8%; se `05-FROSNE-BESLUTNINGER.md` |
| Final locked-holdout run is checked exactly once and matches the "checked once" intent | BT-03 | Enforcing "exactly once" as a runtime invariant across the *project's lifetime* (not just one process run) isn't mechanically testable in a unit test — it's a human-process guarantee the code only makes structurally hard to violate accidentally | Before running `kjor_endelig_holdout_backtest()`, manually confirm no prior holdout run exists for this config; after running, record the run_id/date in STATE.md so future sessions know the holdout has been spent | ✅ utført 2026-08-29 — run_id `20260829-092351-3cc4a836`, holdouten er brukt nøyaktig én gang; se `05-HOLDOUT-RESULTAT.md` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 20s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-08-28 — see `.planning/phases/05-walk-forward-backtest-engine/05-FROSNE-BESLUTNINGER.md` for the full decision trail (initial run → calibration-degeneracy finding → `D-05-05` fix → re-exploration → freeze on tight threshold 0.20/2.50 + flat staking). Frozen configuration approved directly by the developer via interactive decision points, not agent-relayed.
