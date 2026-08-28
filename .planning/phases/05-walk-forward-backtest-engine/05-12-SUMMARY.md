---
phase: 05-walk-forward-backtest-engine
plan: 12
subsystem: backtest
tags: [walk-forward, calibration, isotonic-regression, freeze, kelly-sweep]

requires:
  - phase: 05-07
    provides: backtest.py predict pass, HoldoutLaastFeil guard
  - phase: 05-08
    provides: backtest.py simulate pass, manifest.json/ledger.csv persistence
  - phase: 05-09
    provides: Kelly-fraction sweep
  - phase: 05-10
    provides: 08_kjor_backtest.py CLI
  - phase: 05-11
    provides: live-vs-backtest decision parity proof (precondition for trusting this run)
provides:
  - Real, full train/calibrate walk-forward backtest evidence (multiple runs)
  - Discovery and fix of a real calibration-degeneracy bug (D-05-05)
  - --flat CLI run mode for 08_kjor_backtest.py (D-05-03 flat staking as a first-class mode)
  - A frozen strategy configuration for plan 05-13's one-shot holdout run
affects: [05-13]

tech-stack:
  added: []
  patterns:
    - "Absolute floor on top of a proportional split — MIN_KALIBRERINGSKAMPER guards against a percentage-based calibration split degenerating at small window sizes"

key-files:
  created:
    - .planning/phases/05-walk-forward-backtest-engine/05-FROSNE-BESLUTNINGER.md
  modified:
    - model.py
    - tests/test_model.py
    - 08_kjor_backtest.py
    - .planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md

key-decisions:
  - "D-05-05: floored the walk-forward calibration split at 50 games (model.py MIN_KALIBRERINGSKAMPER/MIN_TRENING_ETTER_KALIBRERING) after discovering 15%-of-window calibration sets as small as ~15 games saturated isotonic regression to modell_prob=1.0 for up to 38% of bets in some samples."
  - "Added --flat as a first-class 08_kjor_backtest.py run mode (not just a --sweep arm) so the frozen flat-staking decision can actually be reproduced by plan 05-13's holdout run."
  - "Froze on min_value_terskel=0.20, maks_odds=2.50, flat staking (20kr/bet) — a real deviation from the live bot's config (0.05, half-Kelly) — because the live config showed no statistically meaningful edge even after the calibration fix, while this tighter config showed positive ROI/CLV that survived excluding residual-saturation bets."

requirements-completed: [BT-01, BT-04, BT-05, BT-07]

duration: ~90min (multiple real backtest runs, a mid-flight bug discovery and fix, and 3 rounds of direct developer decisions)
completed: 2026-08-28
---

# Phase 5 Plan 12: Freeze-the-Decisions Run Summary

**Discovered and fixed a real isotonic-calibration degeneracy bug mid-run, then froze a tighter strategy configuration (0.20 threshold, 2.50 max odds, flat staking) that showed a genuine — though still small-sample — positive ROI/CLV signal after the fix, versus no detectable edge in the live bot's current configuration**

## Performance

- **Duration:** ~90 min across multiple real walk-forward backtest runs (each retraining XGBoost 13 times over 2,302 games)
- **Completed:** 2026-08-28
- **Tasks:** 1 (plan) + substantial unplanned-but-necessary follow-on work (calibration fix, CLI extension, re-exploration) driven by real findings during the checkpoint

## Accomplishments

- Ran the phase's first real, full train/calibrate walk-forward backtest (458 bets under the live config) — the actual Core Value deliverable this milestone exists to produce.
- Discovered a genuine data-quality bug during the human-verify checkpoint: 38% of bets in one sample had `modell_prob` saturated at exactly `1.0`, traced to isotonic regression calibrating on sets as small as ~15 games at early walk-forward retrain points.
- Fixed the root cause (`model.py` D-05-05: absolute 50-game floor on the calibration split), verified with 4 new/updated tests, full suite green at 346 tests.
- Added `--flat` as a first-class `08_kjor_backtest.py` run mode so a flat-staking freeze decision is actually reproducible by plan 05-13.
- Explored 6 real backtest configurations (see `05-FROSNE-BESLUTNINGER.md` for the full sequence) before freezing on the one that showed a genuine, calibration-fix-surviving positive signal.
- Froze the final configuration directly with the developer across 3 interactive decision points — no agent-relayed approvals.

## Task Commits

1. **Task 1: Run full train/calibrate walk-forward backtest with Kelly sweep** — `4f182f9` (feat)
2. **[Unplanned, developer-directed] Add --flat CLI run mode** — `404621b` (feat)
3. **[Unplanned, developer-directed] Fix calibration split degeneracy (D-05-05)** — `33bbae1` (fix)
4. **Task 2/3: Freeze the decisions, close out validation** — this commit (docs)

## Files Created/Modified

- `.planning/phases/05-walk-forward-backtest-engine/05-FROSNE-BESLUTNINGER.md` — the full decision trail: every run tried, the calibration bug, the fix, and the final frozen configuration with the exact command line for plan 05-13
- `model.py` — `MIN_KALIBRERINGSKAMPER`/`MIN_TRENING_ETTER_KALIBRERING` constants, symmetric floor logic in `del_for_trening`'s as_of branch
- `tests/test_model.py` — rewrote the stale 85/15-split assertion, added floor-behavior and above-floor-proportionality tests
- `08_kjor_backtest.py` — `--flat` argument, wired through `bygg_kjoreargumenter`, validation against combining with an explicit `--kelly-fraksjon`
- `.planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md` — sign-off checklist closed, Approval field filled

## Decisions Made

See `05-FROSNE-BESLUTNINGER.md`'s "Frosne beslutninger" table for the full F-05-01 through F-05-15 list. Headline: **min_value_terskel=0.20** (vs. live 0.05), **maks_odds=2.50** (vs. live 4.00), **flat staking 20kr/bet** (vs. live half-Kelly). No `config.py` value was changed — this is a frozen set of CLI arguments for plan 05-13, not a live-bot config change.

## Deviations from Plan

### Auto-fixed Issues (developer-directed, not autonomous)

**1. [Data quality] Isotonic calibration degeneracy discovered and fixed**
- **Found during:** Task 2's checkpoint, inspecting the ledger.csv of an exploratory tighter-threshold run
- **Issue:** `KALIBRER_ANDEL=0.15` applied to small walk-forward windows produced calibration sets as small as ~15 games, causing isotonic regression to saturate `modell_prob` to exactly 1.0 for up to 38% of bets in some samples — undermining every backtest result computed before the fix
- **Fix:** Added an absolute floor (`MIN_KALIBRERINGSKAMPER=50`) protected symmetrically against starving the training set (`MIN_TRENING_ETTER_KALIBRERING=50`)
- **Files modified:** `model.py`, `tests/test_model.py`
- **Verification:** Saturation dropped from ~38% to ~3.5% in the live-config re-run; full suite green at 346 tests
- **Committed in:** `33bbae1`

**2. [Missing capability] `--flat` CLI run mode added**
- **Found during:** Task 2's checkpoint, when the developer chose to freeze on a flat-staking configuration that `08_kjor_backtest.py` could not run standalone (flat previously existed only as a `--sweep` arm, by original D-05-03 design)
- **Issue:** Without this, plan 05-13 could not execute the frozen configuration verbatim
- **Fix:** Added `--flat` as a first-class run mode, reusing `backtest.py`'s existing `flat_innsats` machinery unchanged
- **Files modified:** `08_kjor_backtest.py`
- **Verification:** 26/26 existing CLI tests still pass; smoke-tested against real data reproducing the sweep's flat-arm numbers exactly
- **Committed in:** `404621b`

---

**Total deviations:** 2, both explicitly directed by the developer in response to real findings during the checkpoint, not autonomous scope expansion.
**Impact on plan:** Both were necessary — the calibration fix corrects a genuine correctness bug threatening every backtest result in the phase; the CLI addition is a precondition for plan 05-13 being executable at all under the chosen freeze.

## Issues Encountered

The calibration degeneracy bug (see above) is the significant finding of this plan. It was not anticipated by any prior plan or research document — it surfaced only once real data was run through the real walk-forward loop, which is exactly why plan 05-12's human-verify checkpoint exists rather than trusting synthetic-fixture tests alone.

## Next Phase Readiness

- A frozen configuration exists, with an exact, verbatim command line for plan 05-13.
- The frozen configuration's evidence is genuinely mixed: a real positive signal (ROI +15.0%, CLV +2.08%, drawdown 7.8%) that survives excluding residual-saturation bets, but on a small sample (52 bets, or 36 "clean") whose 95% CI does not exclude zero. Plan 05-13's checkpoint should present this honestly, not round it up to "proven."
- The calibration fix (D-05-05) is a permanent, general improvement — it affects every future walk-forward run, not just this one.

---
*Phase: 05-walk-forward-backtest-engine*
*Completed: 2026-08-28*
