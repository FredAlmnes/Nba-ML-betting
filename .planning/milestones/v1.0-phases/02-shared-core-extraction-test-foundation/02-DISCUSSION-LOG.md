# Phase 2: Shared Core Extraction & Test Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-20
**Phase:** 2-Shared Core Extraction & Test Foundation
**Areas discussed (auto mode — recommended option selected for each, grounded in milestone research + direct codebase inspection):** package structure, team-name resolution scope, feature-engineering extraction scope, strategy/staking extraction scope, handling of pre-existing uncommitted WIP, test scope for CORE-04

---

## Package structure

| Option | Description | Selected |
|--------|-------------|----------|
| Flat modules at repo root | `features.py`/`strategy.py`/`teams.py` alongside existing numbered scripts | ✓ |
| Full `nba_betting/` package now | Matches milestone research's eventual target structure | |

**Choice:** [auto] Flat modules — matches existing convention; full package restructure only becomes load-bearing in Phase 4/5 when backtest/live paths must coexist.

---

## CORE-04 parity test scope

| Option | Description | Selected |
|--------|-------------|----------|
| True live-vs-backtest integration test | Requires the Phase 5 backtest engine to exist | |
| Determinism/referential-transparency test on shared functions | Provable now, without the backtest engine | ✓ |

**Choice:** [auto] Determinism test — the actual cross-path integration proof naturally happens once Phase 5 builds a second call site into the same shared functions. Flagged explicitly in CONTEXT.md as a scoping interpretation for the researcher/planner to validate, since this is the one place the requirement slightly outruns what's buildable yet.

---

## Pre-existing uncommitted WIP in 05_skadefilter.py / 06_bot.py

**Finding:** Confirmed via `git status` this session — both files still carry substantial pre-existing uncommitted changes (88 / 1009 lines) from before Phase 1, and both are files this phase's team-lookup/strategy extraction must edit.

**Choice:** [auto] Do not assume "include" by default (even though that was the Phase 1 decision for `04_value_detector.py`) — instruct the planner to build an equivalent pre-flight checkpoint asking the developer fresh, since the WIP has had more time to diverge.

---

## Claude's Discretion

- Exact function names/signatures in the new shared modules
- Shape of the CORE-02 config module (constants module vs. small dataclass)
- Whether `debug_kamp.py` (currently untracked) gets tracked as part of this phase

## Deferred Ideas

- Full `nba_betting/` package restructure — Phase 4/5
- `06_bot.py` subprocess-to-import refactor — Phase 4 (ODDS-02)
- Any threshold/feature-set/Kelly-fraction value changes — Phase 5, backtest-gated
