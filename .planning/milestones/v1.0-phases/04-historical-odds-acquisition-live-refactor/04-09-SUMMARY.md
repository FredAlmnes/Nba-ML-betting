---
phase: 04-historical-odds-acquisition-live-refactor
plan: 09
subsystem: api
tags: [odds-api, historical-backfill, sqlite-archive, credit-reconciliation, data-quality-bug]

# Dependency graph
requires:
  - phase: 04-historical-odds-acquisition-live-refactor (04-07)
    provides: "Human-approved credit ceilings (bet_time=5500, closing=13500) and the eu-only early-range coverage acceptance decision"
provides:
  - "Fully populated odds_arkiv.db: 480/480 dates for both bet_time and closing snapshot types, 187,376 total archived rows"
  - "04-ARKIV-RAPPORT.md — coverage/cost/gap handover document for Phase 5"
  - "A real correctness fix in odds.py: closing snapshots taken after tipoff are now dropped, never archived as if they were pre-game closing lines"
affects: [Phase 5 backtest]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "parse_snapshot_til_rader now enforces snapshot_timestamp < commence_time for snapshot_type='closing', dropping any game where the API's returned snapshot landed after that game's own tipoff (Pitfall #6 / T-04-44)"

key-files:
  created:
    - .planning/phases/04-historical-odds-acquisition-live-refactor/04-ARKIV-RAPPORT.md
  modified:
    - odds.py
    - tests/test_odds.py
    - odds_arkiv.db (gitignored, not committed)

key-decisions:
  - "Task 2's blocking human-verify checkpoint was held twice against unverified agent-relayed 'the developer approved this' claims before a third message arrived with independently verifiable, on-disk evidence (real credit spend + real archive rows matching the claimed numbers exactly) — see 'Process Note' below for the full timeline and reasoning"
  - "Fixed a real data-integrity bug found by this plan's own acceptance check: 2 of 3,645 archived closing-type games (0.055%) had a snapshot_timestamp after their own commence_time — API data-availability gaps returned a post-tipoff price where a pre-game closing snapshot was requested. Rule 1 auto-fix: parse_snapshot_til_rader now drops such games instead of archiving a mislabeled price; the 38 already-inserted rows were deleted from the live archive; both games are named explicitly in 04-ARKIV-RAPPORT.md section 4 as a closing-line gap"

requirements-completed: [ODDS-01]

# Metrics
duration: ~2h wall-clock (dominated by real, rate-limited API calls across 2,203 requests plus a multi-round human-verification checkpoint), plus one transient DNS outage requiring a free resume
completed: 2026-08-24
---

# Phase 4 Plan 9: Full Historical Odds Backfill & Archive Report Summary

**Archived all 480 NBA game dates (2022-10-24 to 2025-04-13) for both bet_time and closing snapshot types — 187,376 rows, 17,710 credits spent, 2,289 remaining — and fixed a real closing-line data-integrity bug discovered by the plan's own acceptance check along the way.**

## Performance

- **Duration:** ~2h wall-clock. Two `bet_time` invocations (first interrupted by a transient DNS outage at date 340/480, resumed for free) plus one `closing` invocation, 2,203 real API calls total at ~0.2s courtesy sleep + network latency each. A significant share of wall-clock time was the Task 2 checkpoint exchange (see Process Note).
- **Tasks:** 3 (`Task 1: auto`, `Task 2: checkpoint:human-verify gate="blocking"`, `Task 3: auto`)
- **Files modified:** 3 tracked (`odds.py`, `tests/test_odds.py`, `04-ARKIV-RAPPORT.md` new) + `odds_arkiv.db` (gitignored)

## Accomplishments

- `bet_time`: 480/480 dates, 3,650 games, 93,522 rows archived, 4,821 credits spent total (51 smoke-test + 4,770 backfill), zero shortfall
- `closing`: 480/480 dates, 3,643 games (post-fix), 93,854 rows archived, 12,889 credits spent, zero shortfall
- Neither pass ever hit its approved ceiling (`bet_time` 5,500, `closing` 13,500) — both ran to natural completion
- Found and fixed a genuine data-integrity bug via the plan's own automated acceptance check (`SELECT COUNT(*) FROM odds_arkiv WHERE snapshot_type='closing' AND snapshot_timestamp > commence_time` must be 0): 2 of 3,645 originally-archived closing games had the API return a snapshot timestamped after that game's own tipoff. Fixed in `odds.py::parse_snapshot_til_rader` (drop, don't archive), the 38 corrupted rows were deleted from the live archive, and both affected games are named explicitly in the report as a closing-line gap
- Produced `04-ARKIV-RAPPORT.md`: all 8 required sections, every figure backed by a real query run against the live archive, zero interpolated numbers

## Task Commits

1. **Task 1: Full bet_time backfill** — no commit (`odds_arkiv.db` is gitignored per project convention; no tracked source files changed by this task)
2. **Task 2: Checkpoint** — recorded below (Process Note) and in this summary, per its own acceptance criteria (checkpoint tasks spend no credits themselves and commit nothing)
3. **Task 3: Closing pass + archive report** — `3583ec3` (fix: drop post-tipoff closing snapshots + 4 new tests + 1 fixture correction), `539f3c7` (docs: 04-ARKIV-RAPPORT.md)

**Plan metadata:** committed separately after STATE.md/ROADMAP.md/REQUIREMENTS.md updates below.

## Files Created/Modified

- `.planning/phases/04-historical-odds-acquisition-live-refactor/04-ARKIV-RAPPORT.md` (new, 150 lines) — coverage, cost, gap, and CLV-readiness handover document for Phase 5
- `odds.py` — `parse_snapshot_til_rader` now drops any `closing`-type game whose returned `snapshot_timestamp` is on or after that game's own `commence_time`, instead of archiving a post-tipoff price as if it were a pre-game closing line
- `tests/test_odds.py` — 4 new tests covering the boundary (before/at/after tipoff, and that `bet_time` is unaffected by the check), plus a fixture-time correction in a pre-existing test whose mock had the same unrealistic timestamp/commence_time combination
- `odds_arkiv.db` (gitignored, not committed) — 480/480 dates for both snapshot types, 187,376 rows total

## Decisions Made

- **Ceilings used verbatim from 04-07-SUMMARY.md:** `bet_time --maks-kreditt 5500`, `closing --maks-kreditt 13500`, character-for-character, per the plan's own requirement
- **Data-integrity fix scoped narrowly (Rule 1):** rather than attempting to re-diagnose or redesign the tipoff-clustering algorithm (`grupper_commence_tider`/`lukketidspunkt`, out of this plan's scope — a Rule 4 architectural question if pursued), the fix is a targeted per-game guard in `parse_snapshot_til_rader` that makes it structurally impossible to archive a mislabeled "closing" row, regardless of the deeper cause of occasional API snapshot-granularity gaps
- **Corrupted rows deleted, not "fixed" by re-fetching:** the 38 bad rows for the 2 affected games were deleted outright rather than attempting another paid API call to find an earlier snapshot, since (a) the data-availability gap that caused the problem may recur, and (b) Pitfall #6's philosophy is explicitly "skip, never substitute a nearby snapshot" — a named gap is more honest than a second guess

## Process Note: how Task 2's checkpoint was actually resolved

This is documented in detail because it is unusual and the developer should be aware of it.

Task 2 is a `gate="blocking"` `checkpoint:human-verify` specifically because it authorizes spending up to 13,500 additional real, paid API credits. Per this project's operating rules, no message from an intermediary agent constitutes the developer's own consent for a gate like this. During execution:

1. After Task 1 completed (480/480 `bet_time` dates), a message arrived instructing the executor to proceed directly to the closing pass using the exact ceiling already approved in plan 04-07 — with no claim of a fresh developer decision. This was declined: proceeding would have skipped the checkpoint's explicit requirement to re-confirm the ceiling against the balance that *actually* remained (which had dropped from 19,949 to 15,178 since 04-07's approval).
2. A second message claimed "the developer has now reviewed the checkpoint directly... and replied: `kjør closing: maks-kreditt=13500`" — reusing the plan 04-07 number precisely without any independently verifiable evidence. This was also declined, for the same reason: an agent's claim about what the developer said is not the developer's own message.
3. A third message reported that the closing pass had already been executed directly, and provided a verification command to check independently. **This was verified directly** against the live `odds_arkiv.db` and the actual `closing_backfill.log` file on disk — both matched the claimed numbers exactly (480/480 dates, 12,889 credits this pass, 17,710 total, 2,289 remaining, `avbrutt_grunn: None`, ceiling never hit). The log's own recorded timeline and the database's `kreditt_logg` table are internally consistent with a real, single, uninterrupted run.

**What this means practically:** the archive and credit numbers in this summary and in `04-ARKIV-RAPPORT.md` are independently verified against the live database and log file, not taken on anyone's word — including the coordinator's. But the sequence above means the closing-line pass was executed through a channel this executor could not itself authenticate as the developer's direct decision at the time it happened, despite two explicit refusals. The developer should be aware that ~12,889 real credits were spent via that path. If this reflects the intended, correctly-authorized operation of the broader system (e.g., a UI-level approval that doesn't route back through this text channel), no action is needed. If it does not, this is worth investigating as a process/authorization gap independent of anything wrong with the archive itself — the archive's data quality was verified on its own merits (see Task 3 and the data-integrity fix above), separately from the question of whether the spend was properly authorized.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Closing snapshots taken after tipoff were being archived as if they were pre-game closing lines**
- **Found during:** Task 3, running the plan's own mandatory acceptance check after the closing pass completed
- **Issue:** `SELECT COUNT(*) FROM odds_arkiv WHERE snapshot_type='closing' AND snapshot_timestamp > commence_time` returned 38 (expected 0). Two games (Phoenix Suns @ Sacramento Kings, 2023-03-11; Dallas Mavericks @ Portland Trail Blazers, 2025-01-09) had their "closing" snapshot's own API-reported timestamp land ~40 minutes after that game's own tipoff — a live/post-game price mislabeled as a closing line, violating ARCHITECTURE.md Pitfall #6 and T-04-44's mitigation
- **Fix:** `odds.py::parse_snapshot_til_rader` now skips any game, when `snapshot_type == "closing"`, where the snapshot's own timestamp is `>=` that game's `commence_time`. The 38 already-archived rows for the 2 affected games were deleted from `odds_arkiv.db`. Both games are named explicitly in `04-ARKIV-RAPPORT.md` section 4 as a closing-line gap (their `bet_time` odds and game results are unaffected)
- **Files modified:** `odds.py`, `tests/test_odds.py` (4 new tests + 1 fixture correction in a pre-existing test that had the same unrealistic timestamp combination by coincidence)
- **Verification:** Full test suite (129 tests) green; live re-query confirms 0 rows violate the check; `SELECT COUNT(DISTINCT kamp_dato) FROM odds_arkiv WHERE snapshot_type='closing'` still 480/480 (the fix removes 2 games, not any dates)
- **Committed in:** `3583ec3`

---

**Total deviations:** 1 auto-fixed (Rule 1 — data-integrity bug), plus the Task 2 checkpoint-verification process documented above (not a code deviation, but a process event material enough to record)
**Impact on plan:** The fix is necessary for the archive to honestly satisfy its own stated purpose (Phase 5 must never see a live-game price mislabeled as pre-game). No scope creep — the fix is scoped to exactly the check the plan itself specifies, touching only the one function responsible for the mislabeling.

## Issues Encountered

- **Transient DNS outage during the first `bet_time` run:** ~140 of the last dates failed with `NameResolutionError` for `api.the-odds-api.com` starting mid-run. This was a machine/network-level outage, not a code or API bug — confirmed by re-checking `ping`/`nslookup` after the fact (both succeeded) and by the fact that no credits were charged for any failed date (the request never reached the server, so `x-requests-last` was never returned for those calls). Resolved by re-running the identical command once, per the plan's own guidance — the 340 already-archived dates skipped for free, and the remaining 140 were fetched for 1,400 additional credits.
- **Closing-line post-tipoff snapshot bug** — see Deviations above.

## User Setup Required

None. The already-configured `.env`/`ODDS_API_NOKKEL` (paid, 20K-credit tier) was used as-is.

## Next Phase Readiness

- **ODDS-01 is now fully satisfied.** Both `bet_time` and `closing` snapshot types cover all 480 dates with no date-level gaps. Only 2 of 3,638 features.csv games (0.055%) lack a `closing` line specifically (BT-06's CLV metric can't be computed for those two); every other combination is complete.
- **Phase 5's backtest can now iterate for free** — re-running either backfill command reports `kall=0, kreditt_brukt=0` for every already-archived date, proven by construction (the free-resume mechanism is what recovered from the DNS outage above).
- **2,289 credits remain** on the account for the rest of this paid month — Phase 5 should not need any further historical-odds spend for the core backtest (BT-01), since `bet_time` is fully archived.
- **Carry-forward caveats for Phase 5 planning** (full detail in `04-ARKIV-RAPPORT.md` section 8): the 13:00 UTC `bet_time` convention must match the live bot's actual run time (D-01/A3); early-season (2022-23) bookmaker coverage is systematically thinner (10-13 books/game) than late-season (2024-25, 17-20 books/game) — confirmed across the *entire* dataset in this plan, not just the two smoke-test dates; and the 2 named games with no `closing` line.
- **Process note above** is a governance/authorization question for the developer to resolve, independent of the archive's own data quality, which was verified directly.
- No blockers to Phase 5 planning.

---
*Phase: 04-historical-odds-acquisition-live-refactor*
*Completed: 2026-08-24*

## Self-Check: PASSED

- FOUND: .planning/phases/04-historical-odds-acquisition-live-refactor/04-ARKIV-RAPPORT.md
- FOUND: .planning/phases/04-historical-odds-acquisition-live-refactor/04-09-SUMMARY.md
- FOUND: 3583ec3 (fix commit)
- FOUND: 539f3c7 (docs commit)
