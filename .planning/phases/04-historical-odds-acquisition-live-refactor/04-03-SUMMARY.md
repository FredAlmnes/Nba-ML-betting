---
phase: 04-historical-odds-acquisition-live-refactor
plan: 03
subsystem: database
tags: [odds-api, timezone, zoneinfo, sqlite, tdd]

# Dependency graph
requires:
  - phase: 04-historical-odds-acquisition-live-refactor (04-01)
    provides: odds.py's SQLite archive layer (apne_arkiv/er_allerede_arkivert/arkiver_odds_rader/logg_kreditt) and its 15-field row schema
provides:
  - "kamp_dato_fra_commence / morgen_tidspunkt / snap_til_5min / grupper_commence_tider / lukketidspunkt — tested, DST-aware timestamp decisions for what to ask the historical API for"
  - "parse_snapshot_til_rader — pure offline conversion of a sport-wide historical odds snapshot into archive rows, via teams.finn_lag_id"
affects: [04-04, 04-05, 04-07, 04-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "zoneinfo.ZoneInfo('America/New_York') for NBA-calendar-date derivation from UTC commence_time, not a hardcoded UTC offset (DST-safe)"
    - "Floor-only 5-minute snapshot grid snapping (never round up) to avoid landing a closing-line request after tipoff"
    - "teams.finn_lag_id imported directly into odds.py rather than a new lookup dict, continuing the Phase 2 D-03 shared-module precedent"

key-files:
  created: []
  modified: [odds.py, tests/test_odds.py]

key-decisions:
  - "from teams import finn_lag_id added to odds.py in Task 2's commit only (not Task 1's), keeping each task's diff scoped to what it actually uses"
  - "Unresolved team names keep their archive row with a None *_lag_id column and the raw name preserved, rather than being skipped — matches T-04-14's disposition and 04-01's existing skip-and-log convention elsewhere in the pipeline"

requirements-completed: []  # ODDS-01 not fully realized yet — see REQUIREMENTS.md note; HTTP fetch/backfill still lands in 04-04 through 04-09

# Metrics
duration: ~4min
completed: 2026-08-23
---

# Phase 4 Plan 3: Timestamp Logic & Snapshot Parser Summary

**Six new offline functions in `odds.py` — DST-aware "morning of game day"/closing-line timestamp logic plus a sport-wide snapshot-to-archive-row parser — closing Pitfall 2 and Pitfall 4 from 04-RESEARCH.md in tested code, still zero network calls and zero API credits.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-08-23T12:12:23Z
- **Completed:** 2026-08-23T12:15:41Z
- **Tasks:** 2 completed
- **Files modified:** 2 (`odds.py`, `tests/test_odds.py`)

## Accomplishments
- `kamp_dato_fra_commence`/`morgen_tidspunkt`/`snap_til_5min`/`grupper_commence_tider`/`lukketidspunkt` added to `odds.py`, all DST-verified against a July fixture (EDT, UTC-4) rather than assuming a fixed UTC offset
- `parse_snapshot_til_rader` added: converts a sport-wide historical odds JSON response into 15-field archive rows offline, resolving teams via the shared `teams.finn_lag_id` (no new lookup dict — the exact drift Phase 2 D-03 eliminated)
- Out-of-window games are dropped entirely rather than relabelled with the requested date (ARCHITECTURE.md Pitfall #6 / threat T-04-10)
- `snapshot_timestamp` always comes from the API's own `snapshot["timestamp"]`, never the requested date; a missing timestamp raises `ValueError` rather than archiving silently (threat T-04-11)
- Unresolved team names keep their row with `None` in the `*_lag_id` column and the raw name preserved (threat T-04-14); all nested bookmaker/market/outcome traversal uses `.get(..., [])` defaults so a partial response can't raise `KeyError` mid-backfill (threat T-04-12)
- Full TDD gate followed for both tasks: RED commit (failing tests, function didn't exist) → GREEN commit (implementation, all tests pass, no regressions)
- Test suite grew from 61 (pre-plan baseline) to 79 tests, all green

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for timestamp/clustering logic** - `9122a9d` (test)
1. **Task 1 (GREEN): Implement timestamp/clustering logic** - `c8a0033` (feat)
2. **Task 2 (RED): Failing tests for parse_snapshot_til_rader** - `9a0c8d6` (test)
2. **Task 2 (GREEN): Implement parse_snapshot_til_rader** - `81a849d` (feat)

**Plan metadata:** _pending_ (docs: complete plan — added after this summary is committed)

## Files Created/Modified
- `odds.py` - added `NBA_TIDSSONE`/`MORGEN_UTC_TIME` module constants and six functions: `kamp_dato_fra_commence`, `morgen_tidspunkt`, `snap_til_5min`, `grupper_commence_tider`, `lukketidspunkt`, `parse_snapshot_til_rader`; imports `finn_lag_id` from `teams`
- `tests/test_odds.py` - 18 new tests: 8 timestamp/clustering tests (DST case included) and 10 `parse_snapshot_til_rader` tests (team resolution, snapshot-timestamp fidelity, date-window drop, moneyline-only filter, unresolved-team preservation, missing-timestamp `ValueError`, round-trip through `arkiver_odds_rader`)

## Decisions Made
- Kept `from teams import finn_lag_id` out of Task 1's commit and added it only in Task 2's commit, since Task 1 doesn't use it — keeps each task's diff scoped to exactly what that task needs, consistent with the atomic-commit-per-task protocol
- `grupper_commence_tider` accepts both a list of ISO strings and a list of event dicts (each with a `commence_time` key), since the discovery endpoint documented in 04-RESEARCH.md returns dicts — implemented as a single normalization step at the top of the function rather than two code paths

## Deviations from Plan

None - plan executed exactly as written. All acceptance criteria commands (literal stdout checks, grep counts, `pytest -k rader`) passed on first attempt after implementation.

**Observation (not a deviation, no fix applied):** The plan's own `<verification>` section states `grep -c "requests\|urllib\|http" odds.py` should return `0`. In practice it returns `3`, matching the pre-existing `x-requests-last`/`x-requests-remaining` header-name strings inside `logg_kreditt` (added by plan 04-01, verified via `git show f883045:odds.py`, unchanged by this plan). The plan's own Task 1 acceptance criteria uses the more precise `grep -c "import requests" odds.py` check, which does return `0` and was verified. No network code was added by this plan; this is a stale, overly broad verification pattern inherited from 04-01, not a defect introduced here.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. No network calls were made, no API credits were spent (confirmed via `grep -c "import requests" odds.py` returning 0 both before and after this plan's changes).

## TDD Gate Compliance

RED gate: `9122a9d` (Task 1), `9a0c8d6` (Task 2) — both confirmed failing (`AttributeError: module 'odds' has no attribute ...`) before implementation existed.
GREEN gate: `c8a0033` (Task 1), `81a849d` (Task 2) — all tests pass after each implementation; full 79-test suite green with no regressions.
No REFACTOR commits needed — both implementations matched the plan's interface spec on the first pass.

## Next Phase Readiness
- Every timestamp the eventual HTTP backfill driver (04-04+) will ask the API for is now produced by a tested function with a documented timezone convention (`morgen_tidspunkt`, `lukketidspunkt`), not inline string formatting at the call site
- `parse_snapshot_til_rader` is ready to receive real HTTP response bodies once 04-04 adds the network client — its output already round-trips cleanly through `arkiver_odds_rader` (04-01)
- ODDS-01 traceability note updated in `.planning/REQUIREMENTS.md` to "2/9 plans — persistence layer + offline timestamp/snapshot-parsing logic, no HTTP fetch yet" rather than marked complete, since no network call exists in the codebase yet
- No blockers. Zero API credits spent, as required by this plan's scope boundary.

---
*Phase: 04-historical-odds-acquisition-live-refactor*
*Completed: 2026-08-23*

## Self-Check: PASSED

- FOUND: odds.py
- FOUND: tests/test_odds.py
- FOUND: 9122a9d (test RED, Task 1)
- FOUND: c8a0033 (feat GREEN, Task 1)
- FOUND: 9a0c8d6 (test RED, Task 2)
- FOUND: 81a849d (feat GREEN, Task 2)
