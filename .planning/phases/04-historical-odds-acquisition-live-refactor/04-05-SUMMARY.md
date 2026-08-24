---
phase: 04-historical-odds-acquisition-live-refactor
plan: 05
subsystem: api
tags: [odds-api, sqlite, backfill, resumability, credit-ceiling, dry-run, cli, tdd]

# Dependency graph
requires:
  - phase: 04-historical-odds-acquisition-live-refactor (04-01)
    provides: odds.py's SQLite archive layer (apne_arkiv/er_allerede_arkivert/arkiver_odds_rader/logg_kreditt)
  - phase: 04-historical-odds-acquisition-live-refactor (04-03)
    provides: DST-aware timestamp logic (morgen_tidspunkt/lukketidspunkt/grupper_commence_tider) and parse_snapshot_til_rader
  - phase: 04-historical-odds-acquisition-live-refactor (04-04)
    provides: hent_historisk_odds_snapshot/hent_historiske_events HTTP client, credit-cost headers via (body, headers) returns
provides:
  - "hent_unike_kampdatoer() — reads nba_features.csv, returns the 480 sorted unique game dates (optionally range-filtered)"
  - "kjor_backfill() — resumable, budget-capped orchestration loop: existence-check-before-fetch, credit ceiling enforced before every call, per-cluster closing-line archival, broad per-date try/except that still lets SystemExit abort the whole run"
  - "07_hent_historisk_odds.py — CLI entry point, dry-run by default, --maks-kreditt mandatory with no default"
  - "parse_snapshot_til_rader gains kun_event_ider= to scope a closing-line call to only its own tipoff cluster"
affects: [04-07, 04-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Existence-check-before-fetch as the actual credit-saving mechanism (not INSERT OR IGNORE after the fact) — er_allerede_arkivert runs at odds.py:629, before the first hent_historisk_odds_snapshot call at odds.py:654"
    - "Credit ceiling re-checked before every single HTTP call (not once per date) — a closing date's per-cluster calls each re-verify budget headroom before firing"
    - "break (not continue) on ceiling breach — the loop stops cleanly so the next invocation resumes for free from exactly that point"
    - "Dry-run-by-default CLI: the API key is not even read unless --utfor is passed, so a machine with no .env can still safely preview a run"
    - "Broad try/except Exception per date, but SystemExit deliberately uncaught — one bad date doesn't kill a 480-date run, but a fatal auth/param error still stops it instead of repeating the same failure 480 times"

key-files:
  created: [07_hent_historisk_odds.py]
  modified: [odds.py, tests/test_odds.py]

key-decisions:
  - "kun_event_ider added as a trailing keyword-only parameter to parse_snapshot_til_rader (existing positional params untouched, so plan 04-03's tests kept passing without modification)"
  - "CLI takes zero fetch logic itself (grep -c \"requests\" 07_hent_historisk_odds.py == 0) — every credit-spending line lives in odds.py, already covered by mocked-HTTP tests; the CLI only parses args and calls kjor_backfill"
  - "--maks-kreditt has no default value, by design — forcing the operator to name a ceiling every single run rather than trusting (and eventually forgetting) a preset default"

requirements-completed: []  # ODDS-01 not fully realized yet — the backfill mechanism is now complete and tested against mocks, but no real credits have been spent; the actual paid fetch still lands in 04-07 (smoke test) and 04-09 (full backfill)

# Metrics
duration: ~15min (coding across 2 TDD/build cycles, interrupted three times by local-machine sleep during the SUMMARY.md write step — verification and this summary were completed by the orchestrator directly from the already-committed, already-green work)
completed: 2026-08-23
---

# Phase 4 Plan 5: Backfill Driver & Dry-Run CLI Summary

**`odds.py` gains a resumable, credit-ceiling-enforced backfill loop (`kjor_backfill`) and `07_hent_historisk_odds.py` gives it a CLI that defaults to a dry run — every credit-spending code path is written and tested against mocked HTTP, but this plan makes zero real API calls.**

## Performance

- **Duration:** ~15 min of coding (RED/GREEN commits at 20:47–21:02, 2026-08-23)
- **Started:** 2026-08-23T20:47:39+02:00 (first RED commit, `3f922c1`)
- **Completed:** 2026-08-23T21:02:05+02:00 (last commit, `b91cbc4`)
- **Tasks:** 2 (both `type="auto"`, no checkpoints)
- **Files modified:** 3 (`odds.py`, `tests/test_odds.py`, plus new `07_hent_historisk_odds.py`)

## Accomplishments

- `hent_unike_kampdatoer(features_fil="nba_features.csv", fra=None, til=None)` added: reads `nba_features.csv`, coerces `GAME_DATE_HJEMME` to the first 10 characters (robust to a future timestamp-bearing regeneration), drops duplicates, applies inclusive string-range filtering, returns 480 sorted dates for the full unfiltered range — verified live: `python -c "import odds; print(len(odds.hent_unike_kampdatoer()))"` prints `480`
- `parse_snapshot_til_rader` extended with trailing keyword `kun_event_ider=None` so a closing-line call for one tipoff cluster never archives a later cluster's not-yet-closed games; existing positional signature untouched, plan 04-03's tests pass unmodified
- `kjor_backfill(con, api_nokkel, datoer, snapshot_type, maks_kreditt, utfor=False)` added — the safety-critical loop, in the exact required order: (1) print progress, (2) **existence check first** (`er_allerede_arkivert` at `odds.py:629`, strictly before the first fetch call `hent_historisk_odds_snapshot` at `odds.py:654`) — this ordering is what makes re-running free, not `INSERT OR IGNORE`, (3) dry-run short-circuit when `utfor=False`, (4) credit-ceiling check re-evaluated before every call (not just once per date), breaking (not continuing) the loop on breach so the next run resumes for free, (5) `bet_time` path fetches one sport-wide snapshot at the morning-of timestamp, (6) `closing` path discovers tipoff clusters and fires one snapshot call per cluster, chronologically, each scoped via `kun_event_ider`, (7) real cost accumulated from `x-requests-last` response headers, never estimated, (8) per-date `try/except Exception` continues past a bad date, but `except SystemExit` is absent by design (`grep -c "except SystemExit" odds.py` = 0) so a fatal auth/param failure still aborts the whole run instead of repeating across all 480 dates
- `07_hent_historisk_odds.py` created — the CLI entry point joining the existing `0N_verb_ting.py` numbered-pipeline convention: 8 ASCII-named arguments (`--snapshot-type`, `--maks-kreditt` [required, no default], `--utfor`, `--fra`, `--til`, `--datoer`, `--features-fil`, `--arkiv`), dry-run banner (`TØRRKJØRING – ingen API-kall utføres...`) unless `--utfor` is passed, and `hent_api_nokkel()` called only inside the `--utfor` branch so a dry run works with no `.env` present at all
- Full TDD gate followed for Task 1 (RED `3f922c1` → GREEN `e9245fe`); Task 2 built the CLI directly with 2 new subprocess-based tests appended in the same commit (`b91cbc4`), both guarded by `pytest.mark.skipif` on `nba_features.csv`'s absence since it's gitignored
- Test suite grew from 95 (pre-plan baseline) to 108 tests, all green

## Task Commits

1. **Task 1 (RED): Failing tests for `hent_unike_kampdatoer`/`kjor_backfill`/`kun_event_ider`** — `3f922c1` (test, 216 insertions)
2. **Task 1 (GREEN): Implement `hent_unike_kampdatoer`/`kjor_backfill`/`kun_event_ider` filtering** — `e9245fe` (feat, 229 insertions, 1 deletion)
3. **Task 2: `07_hent_historisk_odds.py` CLI + subprocess tests** — `b91cbc4` (feat, 198 insertions across 2 files)

## Files Created/Modified

- `odds.py` — added `hent_unike_kampdatoer`, `kjor_backfill`, and `kun_event_ider=None` on `parse_snapshot_til_rader`'s signature; file now 728 lines total
- `tests/test_odds.py` — 18 new tests: `test_torrkjor_gjor_null_http_kall`, `test_er_allerede_arkivert_hindrer_dobbelt_kall`, `test_kredittgrense_stopper_lopet`, cluster-scoping and chronological-ordering tests for the `closing` path, resumability-after-crash test (reopen connection, count rows), plus the two CLI subprocess tests
- `07_hent_historisk_odds.py` (new, 153 lines) — CLI entry point, zero fetch logic of its own (`grep -c "requests" 07_hent_historisk_odds.py` = 0)

## Decisions Made

- `kun_event_ider` implemented as a trailing keyword-only parameter rather than changing `parse_snapshot_til_rader`'s existing positional contract — keeps plan 04-03's tests stable
- Credit-ceiling check placed before every individual HTTP call (including each closing-line cluster call within one date), not once per date — a date with 3 clusters can partially complete (e.g. 2 of 3 clusters archived) if the ceiling is hit mid-date, and the third cluster becomes free to pick up on the next run since its data was never fetched
- `except SystemExit` deliberately absent — verified via `grep -c "except SystemExit" odds.py` returning `0`, so `_utfor_kall`'s fail-loud path (bad key, bad params) still terminates the whole backfill rather than looping through 480 identical failures

## Deviations from Plan

None. All acceptance criteria verified directly against the committed code:
- `venv/bin/python -m pytest -q` — 108 passed
- `test_er_allerede_arkivert_hindrer_dobbelt_kall`, `test_torrkjor_gjor_null_http_kall`, `test_kredittgrense_stopper_lopet` all exist and pass
- `er_allerede_arkivert(con, dato, snapshot_type)` at `odds.py:629`, first `hent_historisk_odds_snapshot(api_nokkel, tidspunkt)` call at `odds.py:654` — existence check precedes the fetch, as required
- `grep -c "kun_event_ider" odds.py` → 5 (≥3 required)
- `grep -c "avbrutt_grunn" odds.py` → 8 (≥3 required)
- `grep -c "except SystemExit" odds.py` → 0 (required)
- `python -c "import odds; print(len(odds.hent_unike_kampdatoer()))"` → 480
- `07_hent_historisk_odds.py --snapshot-type bet_time --maks-kreditt 0 --datoer 3` → exits 0, prints `TØRRKJØRING`
- `07_hent_historisk_odds.py --snapshot-type bet_time` (no `--maks-kreditt`) → exits 2, argparse "required" error
- `07_hent_historisk_odds.py --help` → lists all 8 arguments
- `grep -c "requests" 07_hent_historisk_odds.py` → 0
- `grep -c "hent_api_nokkel" 07_hent_historisk_odds.py` → 1, inside the `--utfor` branch
- `git status --short` → no `odds_arkiv.db` tracked

## Issues Encountered

**Process note, not a code issue:** the executor agent was interrupted three times mid-response by the local machine sleeping (an environment/connectivity issue, not an agent error) — the first two interruptions happened before any Task-2 work was committed and were resumed cleanly; the third interruption happened after all code and tests were already committed and green, with only this SUMMARY.md's write remaining. Rather than re-spawn a fourth executor attempt for a purely administrative step, the orchestrating session independently re-verified every acceptance criterion above directly against the committed code and wrote this SUMMARY.md itself. No code was written or modified as part of that verification — only reads, greps, and test runs.

## User Setup Required

None. No new environment variables or dependencies. `07_hent_historisk_odds.py` is safe to run with no `.env` present as long as `--utfor` is omitted.

## TDD Gate Compliance

RED gate: `3f922c1` (Task 1) — confirmed failing before implementation existed (new functions not yet defined).
GREEN gate: `e9245fe` (Task 1) — all tests pass after implementation, no regressions.
Task 2 was built directly (`type="auto"`, no explicit RED/GREEN split required by the plan) with its 2 tests landing in the same commit as the CLI implementation (`b91cbc4`); both pass.

## Next Phase Readiness

- The entire credit-spending mechanism now exists, is fully tested against mocked HTTP, and has never made a real network call — `odds.py`'s `kjor_backfill` and `07_hent_historisk_odds.py`'s CLI are ready for plan 04-07's smoke test (a small, `--maks-kreditt`-capped real run) and plan 04-09's full 480-date backfill
- Both downstream plans can rely on: resumability (re-running costs nothing for already-archived dates), a hard credit ceiling enforced per-call, and dry-run safety as the default posture
- No blockers.

---
*Phase: 04-historical-odds-acquisition-live-refactor*
*Completed: 2026-08-23*

## Self-Check: PASSED

- FOUND: odds.py
- FOUND: 07_hent_historisk_odds.py
- FOUND: tests/test_odds.py
- FOUND: 3f922c1 (test RED, Task 1)
- FOUND: e9245fe (feat GREEN, Task 1)
- FOUND: b91cbc4 (feat, Task 2)
