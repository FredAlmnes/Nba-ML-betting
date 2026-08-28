---
phase: 05-walk-forward-backtest-engine
plan: 11
subsystem: testing
tags: [pytest, parity-test, backtest, live-decision-parity]

requires:
  - phase: 05-04
    provides: odds.py's velg_beste_pris_per_utfall / hent_bet_time_pris best-price helpers
  - phase: 05-07
    provides: backtest.py's kjor_backtest, vurder_kamp
  - phase: 05-08
    provides: backtest.py's simuler_bets
  - phase: 05-10
    provides: 08_kjor_backtest.py CLI (present at gate time)
provides:
  - Live-vs-backtest decision-parity test proving verdi_deteksjon.finn_value_bets and
    backtest.kjor_backtest/simuler_bets agree on flag, kamp, bet, odds, modell_prob,
    value, EV and stake for the same historical date/game
  - Structural non-vacuity guard (forced threshold divergence) proving the parity
    comparison actually discriminates rather than trivially passing
  - Repo-wide best-price-rule uniqueness guard (exactly one velg_beste_pris_per_utfall)
  - Config-constant identity guard (`is`, not `==`) across both call sites
  - Real-archive cross-check of the SQL best-price path against the Python reduction
  - First all-plans-together full-suite gate for Phase 5 (344 tests green)
  - BT-02 row filled in 05-VALIDATION.md

affects: [05-12, 05-13]

tech-stack:
  added: []
  patterns:
    - "Live-vs-backtest side-by-side parity test with one fixed pre-holdout fixture (2023-01-15, BOS/MIA), sharing one price set encoded both as an Odds-API payload and as archive rows"
    - "Non-vacuity proof via forced threshold divergence — a parity test with no discriminating power would pass even if both sides were broken identically"

key-files:
  created: []
  modified:
    - tests/test_parity.py
    - .planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md

key-decisions:
  - "Backtest side of the parity comparison runs with bruk_skadefilter=False, matching where finn_value_bets sits in the live pipeline (before the injury filter, which is a separate post-detection stage in 06_bot.py) — comparing with the filter on would silently compare different pipeline lengths."
  - "Config-constant identity uses `is`, not `==`, so a future accidental copy of a threshold value (rather than importing the shared constant) fails this test even though the values would still compare equal."

requirements-completed: [BT-02]

duration: ~35min (across several dispatches interrupted by machine sleep; no work lost — each retry resumed from the last commit)
completed: 2026-08-28
---

# Phase 5 Plan 11: Live-vs-Backtest Decision Parity Summary

**Live-vs-backtest decision-parity test proving `verdi_deteksjon.finn_value_bets` and `backtest.kjor_backtest`/`simuler_bets` agree bet-for-bet on one fixed historical fixture, backed by a non-vacuity proof and a 344-test full-suite gate**

## Performance

- **Duration:** ~35 min across multiple dispatches (repeated machine-sleep interruptions between tasks; each retry resumed cleanly from the last commit with no rework)
- **Completed:** 2026-08-28
- **Tasks:** 3
- **Files modified:** 2 (`tests/test_parity.py`, `05-VALIDATION.md`)

## Accomplishments

- Closed the half of CORE-04 that Phase 2 deferred: `test_identisk_bet_beslutning_live_og_backtest` runs the live and backtest decision paths side by side on `2023-01-15` (BOS vs MIA) and asserts identical `flag`, `Kamp`, `Bet`, `KampDato`, `Odds`, `Modell_prob`, `Value`, `Forv. EV`, and stake.
- Added `test_paritetsassertionen_har_diskriminerende_kraft`, which forces a backtest-side threshold divergence and proves the parity test would actually fail if the two paths disagreed — not a test that merely happens to pass.
- Added `test_ingen_andre_besteprisregel_i_kodebasen`, confirming exactly one `velg_beste_pris_per_utfall` definition exists repo-wide (no surviving inline best-price reduction anywhere else).
- Added the config-constant identity guard and a real-archive cross-check of the SQL `MAX(odds) GROUP BY utfall_navn` path against the Python-side reduction.
- Ran the phase's first all-10-landed-plans full-suite gate: **344 passed, 45 warnings, 53.68s**, zero failures.

## Task Commits

1. **Task 1: Live-vs-backtest decision-parity test** — `8967b97` (test)
2. **Task 2: Structural non-vacuity, best-price-rule, config-identity and real-archive parity guards** — `b983c35` (test)
3. **Task 3: Full-suite gate + BT-02 validation row** — `821cb12` (docs)

**Plan metadata:** this commit (docs: complete plan)

## Files Created/Modified

- `tests/test_parity.py` — extended with 5 new tests (17 total in the file): the pinned parity fixture, the non-vacuity proof, the best-price-rule uniqueness guard, the config-identity guard, and the real-archive cross-check
- `.planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md` — BT-02 row filled (Task 05-11-01, Wave 8, Threat Ref T-05-11-01/T-05-11-02, `tests/test_parity.py`, status green); Wave 0 checklist items ticked with their own observed commands; new "Full-suite gate (plan 05-11)" section recording the verbatim gate results

## Full-Suite Gate Results (verbatim)

- **Command:** `python3 -m pytest tests/ -q`
- **Final summary line:** `344 passed, 45 warnings in 53.68s`
- **Collected count:** 344 (`--collect-only` confirms), strictly above the pre-Phase-5 baseline of 129
- **Per-file collected counts:** `test_parity.py` 17 · `test_backtest.py` 104 · `test_metrics.py` 23 · `test_model.py` 13 · `test_spillerlogg.py` 11 · `test_skadefilter.py` 22
- **Plan 05-10 landed at gate time:** yes — `08_kjor_backtest.py` exists, `--help` exits 0 with the full flag list
- **Warnings:** only xgboost's pre-existing `use_label_encoder` `UserWarning`, unrelated to this plan
- **No production file modified by this plan:** confirmed via `git diff --name-only` over every shared-core module — empty

## Pinned Parity Fixture (for future readers)

- **Date/game:** `2023-01-15`, BOS (home) vs MIA (away)
- **Best prices used by both paths:** home `2.00`, away `1.95` (best home price from Bookmaker A, best away price from a different quote)
- **Live-side decision:** `innsats_live == 100.0`, `ledger_rad["value"] == 0.106329` (± 1e-6)
- **Bet-time price set:** `[(2.00, 1.80), (1.90, 1.95), (1.85, 1.85)]` — best home 2.00, best away 1.95
- **Closing price set:** `[(2.05, 1.90), (1.95, 2.00), (1.90, 1.85)]`

If these numbers ever stop matching a fresh run, the fixture's meaning has drifted and must be re-derived, not patched around.

## Decisions Made

- Backtest side runs with `bruk_skadefilter=False` to match where `finn_value_bets` sits in the live pipeline (before the injury filter stage), so the comparison is apples-to-apples rather than comparing different pipeline lengths.
- Config-constant identity checked with `is`, not `==`, so a future accidental copy-instead-of-import of a threshold value fails this test even though the values would still be numerically equal.

## Deviations from Plan

None — plan executed exactly as written across all 3 tasks.

## Issues Encountered

- Several executor dispatches for Tasks 2 and 3 were interrupted mid-task by the developer's machine going to sleep. No work was lost in any case — each retry found the prior commit(s) intact and resumed from there. This is an environmental/hardware issue (machine sleep timing), not a plan or code defect; worth the developer disabling sleep during long unattended execution sessions.

## Next Phase Readiness

- Decision parity between the live bot and the backtest engine is now proven for a real historical date/game, and the full 10-plan suite (05-01 through 05-10 plus this plan) is green together for the first time in the phase.
- Plan 05-12 (the freeze-the-decisions run) and plan 05-13 (the one-shot holdout spend) may both rely on this parity proof as a precondition — the backtest is now known to replicate the live bot's actual decision logic, not an independent approximation of it.

## Kontrakt for plan 05-12/05-13

Decision parity between the live bot (`verdi_deteksjon.finn_value_bets`) and the backtest engine (`backtest.kjor_backtest` + `simuler_bets`) is proven on a real historical fixture and is a precondition both the freeze run (05-12) and the holdout run (05-13) may rely on without re-verifying it themselves. If a future change to `strategy.py`, `odds.py`, or `verdi_deteksjon.py` breaks this parity, `tests/test_parity.py::test_identisk_bet_beslutning_live_og_backtest` will fail before either of those runs happens.

## Fortsatt åpent

The `gjeldende_sesong()` duplication between `verdi_deteksjon.py` and `skadefilter.py` — flagged "for Phase 5 consolidation" in both `04-02-SUMMARY.md` and `04-06-SUMMARY.md` — remains unowned by any plan in the Phase 5 outline. This plan writes no production code and does not fix it. It should be tracked as a post-Phase-5 tech-debt item so it does not silently disappear at phase close.

---
*Phase: 05-walk-forward-backtest-engine*
*Completed: 2026-08-28*
