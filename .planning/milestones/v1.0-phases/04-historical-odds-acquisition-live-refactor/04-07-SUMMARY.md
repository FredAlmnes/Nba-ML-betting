---
phase: 04-historical-odds-acquisition-live-refactor
plan: 07
subsystem: api
tags: [odds-api, smoke-test, credit-ceiling, human-checkpoint, backfill]

# Dependency graph
requires:
  - phase: 04-historical-odds-acquisition-live-refactor (04-05)
    provides: kjor_backfill()/07_hent_historisk_odds.py CLI, tested against mocked HTTP but never run for real before this plan
provides:
  - "04-SMOKETEST.md — measured cost-per-call, measured tipoff-cluster count, measured early-vs-late bookmaker coverage, projected full-run cost, all replacing 04-RESEARCH.md's assumptions (A2/A4)"
  - "Human-approved credit ceilings for plan 04-09: bet_time maks-kreditt=5500, closing maks-kreditt=13500"
  - "Human decision on early-range eu-only coverage gap: accepted as a documented data-quality caveat, no us-region fallback added"
affects: [04-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Cost-model re-verification against live docs (0 credits) performed immediately before any real spend, per 04-RESEARCH.md's own 'valid until' warning that pricing pages can drift"
    - "Real x-requests-last/x-requests-remaining headers used as the only source of truth for spend and projection — never the pre-call estimate"

key-files:
  created: [.planning/phases/04-historical-odds-acquisition-live-refactor/04-SMOKETEST.md]
  modified: [odds_arkiv.db]

key-decisions:
  - "Credit ceilings for the full 480-date backfill (plan 04-09): bet_time maks-kreditt=5500, closing maks-kreditt=13500 — both approved by the developer after reviewing 04-SMOKETEST.md's measured numbers (realistic projection 4,800/10,080; worst case 4,800/14,880), giving bet_time comfortable headroom (~700 credits) and closing a ceiling below the A2-worst-case estimate (13,500 vs 14,880), i.e. the developer accepted the realistic-case risk rather than fully budgeting for the untested worst case"
  - "Early-range (2022-10) eu-region bookmaker-coverage gap (10-11 bookmakers/game vs 17-19 late-range) accepted as-is — documented as a date-dependent data-quality caveat for Phase 5's backtest to account for; no us-region fallback fetch added for early dates, keeping scope and cost unchanged from what 04-RESEARCH.md/04-05 already built"

requirements-completed: []  # ODDS-01 not yet complete — smoke test measured the real cost model and proved free-resume against the live API, but the full 480-date archive still does not exist; that is plan 04-09's job, now unblocked with explicit ceilings

# Metrics
duration: ~20min (Task 1 execution + real API calls), plus a pause awaiting the blocking human checkpoint before Task 2 could be recorded
completed: 2026-08-24
---

# Phase 4 Plan 7: Real-API Smoke Test & Backfill Go/No-Go Summary

**Spent 51 of a 130-credit cap on six real API calls to replace every remaining estimate in this phase (cost/call, cluster count, early-vs-late bookmaker coverage, free-resume) with a measurement, then the developer reviewed the numbers and approved explicit credit ceilings for the full backfill: bet_time 5,500 / closing 13,500.**

## Performance

- **Duration:** ~20 min of active execution (Task 1's six real API calls plus cost-model re-verification), separated from Task 2 by a blocking checkpoint pause for the developer's decision
- **Tasks:** 2 (Task 1 `type="auto"`, Task 2 `type="checkpoint:human-verify" gate="blocking"`)
- **Files modified:** 2 (`04-SMOKETEST.md` new, `odds_arkiv.db` gitignored/not committed)

## Accomplishments

- Re-verified the historical-odds cost model directly against `the-odds-api.com/liveapi/guides/v4/`'s raw HTML with zero credits spent, immediately before any real call — confirmed unchanged from 04-RESEARCH.md: sport-wide historical odds = 10 credits/call regardless of games returned, discovery = 1 credit (0 if empty). No discrepancy found; Task 1 proceeded to spend.
- Ran six real, capped API calls (never exceeding a per-command `--maks-kreditt` of 60, total spend 51 of the 130-credit plan cap):
  - Bet-time smoke at both ends of the date range (2022-10-24/25, 2025-04-13) — confirmed 10 credits/call exactly, matching the assumption with zero deviation
  - A verbatim re-run of the early-range command, proving ODDS-01's central claim against the live API: `hoppet_over=2, kall=0, kreditt_brukt=0`, remaining balance unchanged
  - A closing-line run for 2025-04-13 — measured **2** tipoff clusters (not the assumed 3 from A2), 21 credits total (1 discovery + 2×10), and confirmed zero closing rows archived after their game's tipoff
- Measured a real, material coverage gap: 2022-10 dates return 10-11 distinct bookmakers/game under the `eu` region vs. 17-19 for 2025-04-13 — roughly a 40% reduction for early-range dates, confirming Pitfall 3's warning as a genuine (not hypothetical) finding
- Projected the full 480-date run from measured numbers: bet_time is exact at 4,800 credits; closing ranges from 10,080 (realistic, using the measured 2-cluster figure) to 14,880 (worst case, using A2's original conservative 3-cluster estimate) — both fit within the 19,949-credit remaining balance, though the worst case leaves only ~1.5% margin
- Presented all five of the plan's required checks to the developer with real numbers quoted inline (cost/call, projection-vs-balance, free-resume proof, coverage comparison, closing-timing safety) via a blocking checkpoint, per T-04-32's mitigation — no ceiling was inferred by the executor
- Developer responded with `godkjent: bet_time maks-kreditt=5500, closing maks-kreditt=13500` and an explicit decision to accept the eu-only early-range coverage gap as a documented caveat rather than adding a `us`-region fallback fetch

## Task Commits

1. **Task 1: Real-API smoke test evidence** — `445817d` (docs, 292 insertions, `04-SMOKETEST.md`)
2. **Task 2: Record human go/no-go decision** — recorded in this summary and the final metadata commit (checkpoint task spends no credits itself, per its own acceptance criteria)

## Files Created/Modified

- `.planning/phases/04-historical-odds-acquisition-live-refactor/04-SMOKETEST.md` (new, 292 lines) — full measured-evidence record: cost-model re-verification, per-step credit/header tables, coverage comparison, full-run projection
- `odds_arkiv.db` (gitignored, not committed) — now holds 1,360 real archived rows across 4 (kamp_dato, snapshot_type) combinations from the smoke test; plan 04-09's full backfill will skip these for free via `er_allerede_arkivert`

## Decisions Made

- **Credit ceilings for plan 04-09** (verbatim from the developer): `godkjent: bet_time maks-kreditt=5500, closing maks-kreditt=13500`
  - bet_time ceiling (5,500) sits ~700 credits above the exact, zero-uncertainty realistic cost (4,800), giving headroom for the smoke test's already-archived dates plus a small retry buffer
  - closing ceiling (13,500) sits between the realistic projection (10,080, using the measured 2-cluster figure) and the worst-case projection (14,880, using A2's original 3-cluster estimate) — the developer accepted the realistic-case risk rather than fully funding the untested worst case; if real cluster counts run consistently at 3+/date across the full range, `kjor_backfill`'s per-cluster ceiling check will stop cleanly (not overspend) and the remaining dates resume for free on a follow-up run with a raised ceiling
- **Early-range coverage decision** (verbatim, region): "accept the eu-only coverage gap for early-range dates as a documented, date-dependent data-quality caveat — do NOT also fetch the us region for early dates. No extra scope/cost added." — Phase 5's backtest must treat 2022-10-range dates as having systematically fewer available bookmaker lines (10-11/game) than 2025-04-range dates (17-19/game) when interpreting any date-correlated pattern in backtest results; this is not a code defect, it reflects The Odds API's own historical-coverage growth over time

## Deviations from Plan

None. All acceptance criteria for both tasks verified directly:
- `04-SMOKETEST.md` exists, contains `x-requests-last`, and is committed (`445817d`)
- `SELECT COALESCE(SUM(kreditt_brukt),0) FROM kreditt_logg` = 51 (>0, ≤130)
- Step 4 re-run recorded as `kall=0, kreditt_brukt=0`, remaining balance unchanged (19970 → 19970), quoted from actual script output
- `SELECT COUNT(*) FROM odds_arkiv WHERE snapshot_type='closing' AND snapshot_timestamp > commence_time` = 0
- `04-SMOKETEST.md` states the measured cluster count for 2025-04-13 (2) and uses it, not the assumed 3, in the realistic projection (the worst-case projection deliberately still uses A2's 3-cluster figure, labeled as such, since N=1 measured date is not enough to discard it)
- `04-SMOKETEST.md` states distinct-bookmaker counts for both an early (2022-10) and late (2025-04) date with an explicit "yes, thinner" verdict
- `04-SMOKETEST.md` contains the full-run projection arithmetic and a yes/(marginal) verdict on whether it fits the remaining balance
- `git status --short` shows no `odds_arkiv.db` tracked
- The developer replied with two explicit integer ceilings (not inferred by the executor) and an explicit region-coverage decision, both recorded verbatim above
- `venv/bin/python -m pytest -q` — 117 passed (no source files changed by this plan; test count unchanged from 04-06's baseline)

## Issues Encountered

None. Task 1 ran cleanly through all 8 steps with no cost-model discrepancy, no ceiling breach, and no unexpected API behavior. Task 2's blocking checkpoint worked exactly as designed: the executor presented measured numbers and waited, without inferring or guessing a ceiling, until the developer supplied both explicit integers.

## User Setup Required

None. The already-configured `.env`/`ODDS_API_NOKKEL` (paid, 20K-credit tier) was used as-is; no new environment variables or dependencies introduced by this plan.

## Next Phase Readiness

- Plan 04-09 (the full 480-date backfill) is now unblocked and has its exact `--maks-kreditt` values: `--snapshot-type bet_time --maks-kreditt 5500` and `--snapshot-type closing --maks-kreditt 13500`
- The four (kamp_dato, snapshot_type) combinations touched by this smoke test are already archived and will be skipped for free by 04-09's run, per the proven free-resume property
- Phase 5's backtest planning should carry forward the eu-only early-range coverage caveat as a known, accepted data-quality boundary condition — not a bug to fix
- Remaining balance entering plan 04-09: 19,949 credits (measured after this smoke test), comfortably above the sum of both approved ceilings (5,500 + 13,500 = 19,000)
- No blockers.

---
*Phase: 04-historical-odds-acquisition-live-refactor*
*Completed: 2026-08-24*

## Self-Check: PASSED

- FOUND: .planning/phases/04-historical-odds-acquisition-live-refactor/04-SMOKETEST.md
- FOUND: 445817d (docs, Task 1)
