---
phase: 04-historical-odds-acquisition-live-refactor
plan: 01
subsystem: database
tags: [sqlite, odds-api, archive, tdd]

# Dependency graph
requires:
  - phase: 04-historical-odds-acquisition-live-refactor (D-03 amendment)
    provides: the sport-wide historical endpoint decision this plan's doc corrections encode
provides:
  - Corrected planning docs (REQUIREMENTS.md, ROADMAP.md, research/STACK.md) naming the sport-wide historical odds endpoint instead of the superseded per-event endpoint
  - odds.py — the permanent, idempotent SQLite archive layer (schema + apne_arkiv/er_allerede_arkivert/arkiver_odds_rader/logg_kreditt) that later Phase 4 plans build the HTTP client and backfill driver on top of
affects: [04-03, 04-04, 04-05, 04-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "odds.py follows the Phase 2 shared-module precedent (teams.py/config.py): flat module at repo root, Norwegian docstrings/identifiers, snake_case, no type hints"
    - "SELECT-before-fetch existence check (er_allerede_arkivert) is the actual credit-saving mechanism; INSERT OR IGNORE is only a duplicate-insert safety net"

key-files:
  created: [odds.py, tests/test_odds.py]
  modified: [.planning/REQUIREMENTS.md, .planning/ROADMAP.md, .planning/research/STACK.md, .gitignore]

key-decisions:
  - "Doc correction (Task 1) applied D-03's 2026-08-23 amendment to all three stale per-event-endpoint references without deleting STACK.md's original text — marked SUPERSEDED with a pointer to 04-RESEARCH.md instead, preserving the audit trail of what was originally believed and why it changed"
  - "odds.py's row tuple is 15 fields (id is AUTOINCREMENT), matching the plan interface exactly; UNIQUE(event_id, snapshot_type, bookmaker, marked, utfall_navn) is the idempotency key"

patterns-established:
  - "kreditt_logg audit table pattern: every API call's cost gets logged via x-requests-last/x-requests-remaining response headers, tolerating missing headers as NULL rather than failing"

requirements-completed: [ODDS-01]

# Metrics
duration: ~5min
completed: 2026-08-23
---

# Phase 4 Plan 1: Endpoint Correction & SQLite Archive Layer Summary

**Corrected three stale per-event-endpoint doc references to the sport-wide endpoint, then built odds.py's idempotent SQLite archive layer (odds_arkiv + kreditt_logg) via TDD — zero network code, zero API credits spent.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-08-23T11:17:33Z
- **Completed:** 2026-08-23T11:21:02Z
- **Tasks:** 2 completed
- **Files modified:** 6 (3 doc corrections + odds.py + tests/test_odds.py + .gitignore)

## Accomplishments
- REQUIREMENTS.md, ROADMAP.md, and research/STACK.md now all name the sport-wide historical odds endpoint (`/v4/historical/sports/{sport}/odds`), matching D-03's 2026-08-23 amendment — no downstream Phase 4 plan can accidentally build against the budget-breaking per-event premise
- Both budget-decision notes (REQUIREMENTS.md's "Open budget decision", ROADMAP.md's "Decision point (phase entry)") marked RESOLVED 2026-08-23
- `odds.py` created: a tested, idempotent, permanent SQLite archive (`odds_arkiv` + `kreditt_logg` tables) with the four interface functions (`apne_arkiv`, `er_allerede_arkivert`, `arkiver_odds_rader`, `logg_kreditt`) that later Phase 4 plans (HTTP client, backfill driver) will build on top of
- Full TDD gate followed: RED commit (8 failing tests, `odds` module didn't exist) → GREEN commit (implementation, all 8 tests pass, full 52-test suite green, no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Correct stale per-event endpoint references** - `1019593` (docs)
2. **Task 2 (RED): Failing tests for odds.py archive layer** - `73bb704` (test)
2. **Task 2 (GREEN): odds.py implementation** - `f883045` (feat)

## Files Created/Modified
- `.planning/REQUIREMENTS.md` - ODDS-01 and the open budget decision note now name the sport-wide endpoint and are marked resolved
- `.planning/ROADMAP.md` - Phase 4 success criteria #1 and decision-point note updated to match
- `.planning/research/STACK.md` - stale per-event cost claim marked SUPERSEDED, original text preserved (struck through) with a pointer to 04-RESEARCH.md
- `odds.py` - new module: `ARKIV_FIL`/`SPORT`/`MARKED`/`REGION` constants, `SKJEMA` (odds_arkiv + kreditt_logg DDL), `apne_arkiv`, `er_allerede_arkivert`, `arkiver_odds_rader`, `logg_kreditt`
- `tests/test_odds.py` - 8 tests: schema creation, existence-check semantics (including independent snapshot-type tracking), idempotent double-insert (`test_dobbel_insert_er_idempotent`), CHECK constraint enforcement, credit-log header parsing and missing-header tolerance
- `.gitignore` - added `odds_arkiv.db` under the existing "Data og modell" block

## Decisions Made
- Kept STACK.md's original (now-superseded) per-event claim visible via strikethrough rather than deleting it, per the plan's explicit instruction — preserves the record of what was believed before D-03's verified correction, useful context for anyone reading STACK.md's history later
- `arkiver_odds_rader`'s idempotency count is computed via `con.total_changes` delta (before/after `executemany`), which correctly reports 0 on a repeat call because `INSERT OR IGNORE` performs no-op inserts for rows already present under the UNIQUE constraint

## Deviations from Plan

None - plan executed exactly as written. Task 1's document edits and Task 2's TDD cycle (RED test commit, GREEN implementation commit) followed the plan's interface spec and acceptance criteria exactly; all automated verification commands in the plan passed on first attempt.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. No network calls were made, no API credits were spent (confirmed via `grep -c "import requests" odds.py` returning 0).

## TDD Gate Compliance

RED gate: `73bb704` (`test(04-01): add failing tests for odds.py SQLite archive layer`) — confirmed failing before the implementation existed (`ModuleNotFoundError: No module named 'odds'`).
GREEN gate: `f883045` (`feat(04-01): implement odds.py SQLite archive layer`) — all 8 tests pass, full 52-test suite green.
No REFACTOR commit needed — implementation matched the plan's interface spec on the first pass.

## Next Phase Readiness
- `odds.py`'s archive layer is ready for 04-03 (timestamp/date logic + `parse_snapshot_til_rader`) and 04-04 (HTTP client) to build on directly — the row-tuple shape and existence-check contract are now locked
- No blockers. Zero API credits spent, as required by this plan's scope boundary.

---
*Phase: 04-historical-odds-acquisition-live-refactor*
*Completed: 2026-08-23*

## Self-Check: PASSED

- FOUND: odds.py
- FOUND: tests/test_odds.py
- FOUND: 1019593 (docs commit)
- FOUND: 73bb704 (test RED commit)
- FOUND: f883045 (feat GREEN commit)
