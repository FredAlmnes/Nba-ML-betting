---
phase: 05-walk-forward-backtest-engine
plan: 13
subsystem: backtest
tags: [walk-forward, holdout, core-value, milestone-close]

requires:
  - phase: 05-12
    provides: frozen strategy configuration (F-05-01..15) and the exact holdout command line
provides:
  - The 2024-25 holdout run, spent exactly once (run_id 20260829-092351-3cc4a836)
  - 05-HOLDOUT-RESULTAT.md, the milestone's Core Value evidence dossier (run + before/after + verdict)
  - HOLDOUT BRUKT: ja durable record in STATE.md (survives backtests/ being gitignored)
  - BT-01 through BT-07 closed complete in REQUIREMENTS.md and ROADMAP.md
  - Phase 5 marked complete (13/13); milestone v1.0's one permitted out-of-sample evaluation used
affects: []

tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - .planning/phases/05-walk-forward-backtest-engine/05-HOLDOUT-RESULTAT.md
  modified:
    - .planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md
    - .planning/STATE.md
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md

key-decisions:
  - "Developer approved the irreversible holdout run directly in-session ('Yes, run the holdout now') after an explicit checkpoint stated the irreversibility, the frozen configuration, and the small-sample caveat from the tuning-slice signal."
  - "Core Value gate verdict: 'Ikke avgjort' — the frozen configuration is NOT validated by the holdout. ROI -25.0% (95% CI -64.5% to +24.6%, straddles zero), win rate 36.8% (CI straddles the 47.9% break-even rate implied by average odds), only 19 bets placed, far under the ~300-bet threshold for statistical meaning."
  - "No new threshold values proposed after seeing the holdout — re-tuning against this slice now would be the exact in-sample anti-pattern BT-03 exists to prevent. A future out-of-sample assessment requires 2025-26 data, not a rerun against 2024-25."
  - "Fixed two stale artifacts left by plan 05-12's close-out as Rule 1 blocking-issue fixes under Task 3's own precondition gate: 05-VALIDATION.md's frontmatter status still read draft despite the sign-off checklist being closed, and the Manual-Only Verifications table had no Utfall outcome column at all."

requirements-completed: [BT-03, BT-05]

duration: ~45min
completed: 2026-08-29
---

# Phase 5 Plan 13: Spend-the-Holdout Summary

**The 2024-25 holdout was spent exactly once under the frozen configuration (0.20 threshold, 2.50 max odds, flat staking); the result is honest and unflattering — 19 bets, ROI -25.0% with a confidence interval that straddles zero — so the Core Value gate verdict is "Ikke avgjort," not a validated positive edge.**

## Performance

- **Duration:** ~45 min (pre-flight gate + a ~3-second real backtest run + four planning-document edits)
- **Completed:** 2026-08-29
- **Tasks:** 3/3 (blocking checkpoint + holdout execution/write-up + close-out)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments

- Ran three independent pre-flight scans proving the 2024-25 holdout was unspent (no `backtests/*/manifest.json` with `type: "holdout"`, no `HOLDOUT BRUKT` in the git-tracked `STATE.md`, no holdout record anywhere in `.planning/`) and that the engine was byte-unchanged since the freeze's `git_head` (`33bbae1`).
- Obtained direct, in-session developer approval ("Yes, run the holdout now") to an explicit checkpoint stating the irreversibility, the exact command, and the small-sample caveat from the tuning-slice signal — not agent-relayed.
- Executed the frozen command verbatim: `./venv/bin/python3 08_kjor_backtest.py --holdout --bekreft-holdout --min-value-terskel 0.20 --maks-odds 2.50 --flat`. Produced `backtests/20260829-092351-3cc4a836/manifest.json` with `type: "holdout"`, 162 dates, 1,225 games, 7 retrains, zero warm-up skips — every counter matching the plan's pre-measured `verified_data_facts` exactly.
- Verified the run's own config (`min_value_terskel`/`min_odds`/`maks_odds`/`kelly_fraksjon`) matched all 15 frozen `F-05-NN` values exactly — no drift between what was frozen and what was evaluated.
- Wrote `05-HOLDOUT-RESULTAT.md` (this milestone's actual Core Value deliverable): the run, the config comparison, both metric sets, all fourteen data-quality counters, a before/after table against the 1,000 kr → 74,88 kr live baseline with every unrecoverable before-side cell marked `ukjent`, the statistical-weight read, and exactly one of the three named verdicts.
- Closed out the phase: `HOLDOUT BRUKT: ja` recorded in the git-tracked `STATE.md`, BT-01 through BT-07 marked complete in `REQUIREMENTS.md` (BT-03/BT-05 rows now name the holdout run and point at the before/after section), Phase 5 marked complete (13/13) in `ROADMAP.md`.

## Task Commits

1. **Task 1: BLOCKING gate — pre-flight scans, direct developer approval recorded** — `36b43bc` (docs)
2. **Task 2: Spend the holdout, write the numbers and the before/after comparison** — `cfbfda6` (docs)
3. **Task 3: Record the spend, close out BT-01..BT-07** — `0502372` (docs)

**Plan metadata:** this SUMMARY's own commit (docs)

## Files Created/Modified

- `.planning/phases/05-walk-forward-backtest-engine/05-HOLDOUT-RESULTAT.md` — the full evidence dossier: pre-flight proof, the single holdout run, its numbers, the before/after comparison, and the Core Value verdict
- `.planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md` — BT-03's Manual-Only row flipped to done naming the holdout run_id; frontmatter `status` corrected to `complete`; a Utfall column added to the Manual-Only Verifications table (see Deviations)
- `.planning/STATE.md` — `HOLDOUT BRUKT: ja` block, Decisions bullets, `completed_phases: 5`/`percent: 100` progress block counted from files actually on disk
- `.planning/REQUIREMENTS.md` — BT-03/BT-05 traceability rows annotated with the holdout run_id and a pointer to the before/after section
- `.planning/ROADMAP.md` — Phase 5 ticked complete, `05-13-PLAN.md` ticked, per-criterion Utfall mapping added, Progress table row updated to `13/13 | Complete`

## Decisions Made

See `key-decisions` in the frontmatter. The load-bearing one: **the Core Value gate verdict is "Ikke avgjort," not "Porten er åpnet."** The frozen configuration (chosen because it looked promising on the tuning slice — ROI +15.0%, CLV +2.08%, 52 bets) did not confirm that signal on the genuinely out-of-sample 2024-25 slice: ROI -25.0% on 19 bets, confidence interval [-64.5%, +24.6%] straddling zero. This is the classic in-sample-optimism signature (a result far below the tuning result), named as such in `05-HOLDOUT-RESULTAT.md` §7. No new threshold values are proposed anywhere in the artifact or this summary — the milestone's evidence is genuinely inconclusive, and reporting that honestly is what BT-03 exists to protect.

## Milepælens bevisgrunnlag

Mapping `ROADMAP.md` §Phase 5's five Success Criteria to the plan and artifact that satisfied each:

1. Walk-forward replay of the full decision pipeline → plan 05-07 (prediksjonspass/holdout guard), plan 05-12 (the full tuning-slice run with sweep)
2. As-of data filtering (no post-decision-time leakage) → plan 05-06 (as-of skadefilter), plan 05-07 (as-of prediksjonspass), plan 05-11 (live-vs-backtest decision-parity test)
3. Locked holdout checked exactly once, after all decisions frozen → **this plan (05-13)** — run_id `20260829-092351-3cc4a836`, `05-HOLDOUT-RESULTAT.md`
4. Reproducible versioned manifest enabling a before/after comparison → plan 05-08 (`manifest.json`/`ledger.csv` persistence) plus `05-HOLDOUT-RESULTAT.md` §6 (the actual comparison)
5. CLV reporting and a Kelly-fraction sensitivity sweep → plan 05-03 (CLV calculation), plan 05-09 (the sweep), the frozen tuning run's `kelly_sweep.json`

## Holdouten er brukt

`run_id`: `20260829-092351-3cc4a836`. Date: `2026-08-29`. Milestone v1.0 has now used its one permitted out-of-sample evaluation. **A new out-of-sample assessment requires new data (the 2025-26 season), not a new run against 2024-25** — the 2024-25 slice is no longer out-of-sample for this project, for this plan, this milestone, or any later session. `backtests/` is gitignored; the durable record is the `HOLDOUT BRUKT: ja` block in `.planning/STATE.md`, which is tracked in git.

No new value is proposed for `MIN_VALUE_TERSKEL`, `MAX_ODDS`, or `KELLY_FRAKSJON` here, and `config.py` is byte-identical to its pre-plan state — the live bot still runs its pre-phase configuration (`0.05`/`4.00`/half-Kelly). Whether and how the live bot's configuration should change in light of this evidence is a decision for after this milestone, explicitly deferred by `05-CONTEXT.md`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `05-VALIDATION.md`'s frontmatter `status` field was stale**
- **Found during:** Task 3's precondition gate check
- **Issue:** The gate required `status: complete` before Task 3 could proceed (plan 05-12's own SUMMARY claims "sign-off checklist closed, Approval field filled"), but the frontmatter still read `status: draft`. All substantive content (sign-off checkboxes, the Approval line with date and freeze-document reference, the Per-Task Verification Map's BT-01..BT-07 rows all green) was already correct — only the status label itself was never flipped.
- **Fix:** Set `status: complete` in the frontmatter, matching the substance that was already true.
- **Files modified:** `.planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md`
- **Verification:** `grep -c '^status: complete$'` outputs `1`; `nyquist_compliant: true` and the sign-off checklist were left untouched.
- **Committed in:** `0502372`

**2. [Rule 2 - Missing structure] Manual-Only Verifications table had no `Utfall` outcome column**
- **Found during:** Task 1's `read_first` and Task 3's action, both of which assume an existing `Utfall` cell in row 2 (`⬜ utestående — eies av plan 05-13 (holdouten er ikke brukt ennå)`) that Task 3 is meant to flip to done. The table as left by plan 05-12 had no such column at all — only `Behavior | Requirement | Why Manual | Test Instructions`.
- **Issue:** Without this column, Task 3's literal instruction ("replace row 2's Utfall cell") had nothing to act on, and the phase would have no visible record that either manual verification (BT-01/BT-04's full-history plausibility check, BT-03's holdout-once check) was actually completed and by which run.
- **Fix:** Added an `Utfall` column to the table. Row 1 (BT-01/BT-04) marked done, naming the tuning run_id `20260828-095233-3cc4a836` and its headline numbers. Row 2 (BT-03) marked done, naming this plan's holdout run_id `20260829-092351-3cc4a836`.
- **Files modified:** `.planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md`
- **Verification:** `grep -c '05-HOLDOUT-RESULTAT' 05-VALIDATION.md` outputs `1`; `grep -c 'eies av plan 05-13'` outputs `0`.
- **Committed in:** `0502372`

---

**Total deviations:** 2, both Rule 1/2 auto-fixes of stale/missing structure left by plan 05-12's close-out, discovered by this plan's own precondition gate rather than left silently unresolved. Neither touched production code; both were scoped entirely to `05-VALIDATION.md`, which Task 3 already owns.

## Issues Encountered

None blocking. The holdout run itself completed in about 3 seconds (7 retrains over 1,225 games) with zero warm-up skips and zero counter mismatches against the plan's pre-measured expectations — no STOP condition was triggered anywhere in Task 2's verification chain.

One arithmetic note carried into `05-HOLDOUT-RESULTAT.md` for transparency: the plan's own Task 2 automated-verify script parses the `F-05-NN` freeze table by parameter name and would raise `KeyError` looking up `kelly_fraksjon` (the frozen table's row for staking is named `staking-regel`, not `kelly_fraksjon`). This is a pre-existing quirk in the plan's own verification snippet, not a defect in the run or the freeze. The actual comparison was performed correctly by hand: `konfig.kelly_fraksjon` is `null` (flat stake) in the holdout run, matching F-05-04's frozen "flat (ikke Kelly)" staking rule exactly.

## Known Stubs

None. This plan writes only planning documents and runs one already-shipped CLI; no application code or UI was touched.

## Next Phase Readiness

Milestone v1.0 is complete: all five phases done, BT-01 through BT-07 satisfied, the Core Value question asked and answered honestly. The answer is not the hoped-for one — the frozen configuration's promising tuning-slice signal (ROI +15.0%, CLV +2.08%) did not survive contact with the genuinely out-of-sample 2024-25 slice (ROI -25.0%, CI straddling zero, only 19 bets). Per `.planning/PROJECT.md`'s hard gate, this means the strategy has NOT demonstrated a positive, validated ROI over a proper historical backtest, and therefore remains not trusted with anything beyond paper trading — the live bot's configuration is unchanged and no real-money decision is unlocked by this result. What happens next (accept the null result and explore a different strategy, wait for 2025-26 data for a genuinely fresh out-of-sample look, or continue paper trading under the existing configuration) is a decision for the developer outside this milestone's scope.

## Self-Check: PASSED

All claimed files found on disk and all three task commit hashes (`36b43bc`, `cfbfda6`, `0502372`) verified present in `git log --oneline --all`.
