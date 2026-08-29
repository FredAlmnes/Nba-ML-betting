# Phase 4: Historical Odds Acquisition & Live Refactor - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-23
**Phase:** 4-Historical Odds Acquisition & Live Refactor
**Areas discussed:** Odds snapshot timing, Fetch scope (credits), 06_bot.py refactor shape, Package restructure timing

---

## Odds snapshot timing

| Option | Description | Selected |
|--------|-------------|----------|
| Morning of game day | Run once in the morning; snapshot odds at closest-to-morning-of reading | ✓ |
| Just before first tip-off | Snapshot a few hours pre-tipoff instead | |
| No fixed time — you decide | Let planner pick a default | |

**User's choice:** "Morning of game day"
**Notes:** Locks the offset the historical fetch must reproduce so the backtest never bets against odds the live bot could never have actually seen (closing-line-as-bet-price is a known lookahead-bias pitfall per ARCHITECTURE.md).

---

## Fetch scope (credits)

| Option | Description | Selected |
|--------|-------------|----------|
| Fetch both bet-time + closing-line now | ~10,900 credits total for ~3,638 games, avoids a second paid month for Phase 5's CLV need | ✓ (Claude's recommendation, applied per user's later "run what's recommended" instruction) |
| Bet-time only for now | ~7,300 credits, smaller footprint, risks needing a second paid month later | |

**User's choice:** Initially dismissed the question mid-discussion ("[User dismissed — do not proceed, wait for next instruction]"). Discussion paused. User then said "fortsett autonoumus og kjør det som er recomended" (continue autonomous and run what's recommended) — applied as acceptance of the recommended option.
**Notes:** Marginal cost for closing-line data is small since the event is already being paid for via the per-event endpoint.

---

## Endpoint correction (post-research, 2026-08-23)

The phase researcher (`gsd-phase-researcher`) found that D-03's stated rationale ("per-event is 10x cheaper than sport-wide") does not match the current official Odds API docs — both endpoints share the same `10 × markets × regions` formula, but per-event charges it per game while sport-wide charges it per snapshot call. For this project's 3,638 games this reverses the comparison: per-event ≈ 72,760 credits (3.6x over the paid 20K budget, would fail), sport-wide ≈ 10-20K credits (fits). Independently re-verified against the raw official docs before surfacing to the user.

| Option | Description | Selected |
|--------|-------------|----------|
| Switch to sport-wide endpoint | Amends D-03; fits budget; matches official docs' own recommendation for featured markets (h2h/moneyline) | ✓ |
| Keep per-event, shrink scope | Stay with per-event but cut date range or closing-line fetch to fit ~20K credits | |
| Pause to verify independently | Wait for user to check pricing/docs themselves | |

**User's choice:** "Switch to sport-wide endpoint (Recommended)"
**Notes:** D-02 and D-03 in CONTEXT.md amended in place (dated) rather than rewritten silently, so the correction and its reasoning stay visible. `.planning/research/STACK.md`'s original per-event claim is now flagged as stale/superseded, not deleted.

---

## 06_bot.py refactor shape

Not asked directly — resolved by Claude per "run what's recommended," using the established Phase 2 extraction pattern (features.py/strategy.py/teams.py) as precedent: extract 04_value_detector.py/05_skadefilter.py logic into importable functions with a `__main__` guard for standalone use, imported directly by 06_bot.py, replacing the subprocess.run calls and their hardcoded python3.10 PYTHONPATH hack.

## Package restructure timing

Not asked directly — resolved by Claude per "run what's recommended": stay flat this phase (odds.py joins the existing flat modules), defer the full nba_betting/ package restructure to Phase 5 where backtest/live separation actually becomes real, consistent with Phase 2's original D-01 reasoning.

## Claude's Discretion

- SQLite filename/location and table/column names beyond the composite key already specified in research.
- Whether the historical bulk-fetch is a new numbered script or an invoked function.
- Exact extracted function names.

## Deferred Ideas

- Full nba_betting/ package restructure — Phase 5.
- Threshold/Kelly-fraction value changes — Phase 5, backtest-gated.
- Grid search (BTV2-01) and HTML backtest report (BTV2-02) — already deferred to v2.
