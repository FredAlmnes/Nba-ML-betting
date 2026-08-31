---
quick: 260831-c4z
subsystem: bot
tags: [xss, dashboard, bankroll, nba-api, tdd]

key-files:
  modified:
    - 06_bot.py
    - tests/test_bot.py

key-decisions:
  - "_json_til_script() escapes every '<' as \\u003c in both embedded JSON payloads (historikk_json, bets_json) rather than switching to a templating engine — smallest possible fix, no behavior change to the underlying data"
  - "JS-side trygg() helper HTML-escapes every third-party string before innerHTML, as defense-in-depth alongside the Python-side script-tag escaping"
  - "sjekk_resultater no longer writes any bankroll history point; oppdater_dagens_historikk() is now the single, idempotent place that writes/updates today's point, called once at the end of main() after both settlement and new bets"
  - "hent_kampresultat prefers an exact GAME_DATE string match over the old 'vs.' preference; falls back to None (wait) rather than guessing df.iloc[0] when only the return-leg fixture is in the search window"
  - "er_hjemmekamp (previously dead code, IN-01) is now used to detect and warn when NBA API's home/away orientation for a matched row disagrees with Odds API's, without changing the WL-based outcome logic"

requirements-completed: [CR-01, CR-02, CR-03]

duration: ~20min
completed: 2026-08-31
---

# Quick Task 260831-c4z: Fix Three Known Bugs in 06_bot.py/dashboard.html Summary

**Closed CR-01 (stored XSS via Odds API team names), CR-02 (double bankroll-history checkpoint corrupting the ledger), and CR-03 (settlement against the wrong physical game) — all three findings from Phase 2's code review (`02-REVIEW.md`) that remained open going into v2.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-08-31
- **Tasks:** 4 (3 TDD auto tasks + 1 verification-only task)
- **Files modified:** 2 (`06_bot.py`, `tests/test_bot.py`)

## Accomplishments

- **CR-01 (stored XSS):** Third-party team names/value strings from The Odds API can no longer break out of the embedded `<script>` block or execute as markup via `innerHTML` in the generated `dashboard.html`.
- **CR-02 (double bankroll-history checkpoint):** A day with both bet settlement and new bet placement now ends with exactly one history point equal to the true end-of-day balance, instead of freezing at the pre-placement balance.
- **CR-03 (wrong physical game at settlement):** `hent_kampresultat` now prefers the row with the bet's exact game date, and returns `None` (wait) instead of guessing against the return-leg fixture when only that fixture is in the search window.
- 13 new regression tests added, all reproducing the bug against pre-fix code (RED) before the fix made them pass (GREEN). Full suite: 349 → 362 passed, no regressions.

## Task Commits

Each task was committed atomically (test-first, then implementation, per file per task — no separate RED/GREEN commits were made since each task's tests+fix were validated as failing-then-passing before a single combined commit, matching the plan's `tdd="true"` requirement to write tests first and confirm failure prior to implementing):

1. **Task 1: Tett XSS-hullet fra Odds API-lagnavn til dashboard.html (CR-01)** - `7a544c9` (fix)
2. **Task 2: Ett historikkpunkt per dag, skrevet etter oppgjør og plassering (CR-02)** - `a1ab020` (fix)
3. **Task 3: Velg riktig fysisk kamp ved oppgjør, aldri returkampen (CR-03)** - `4bb7e3d` (fix)
4. **Task 4: Full regresjonskjøring og sluttverifikasjon** - no source changes, verification only (see below)

## Files Created/Modified

- `06_bot.py` — Added `_json_til_script()` (Python-side script-tag escaping) and JS-side `trygg()` HTML-escaper used in `generer_dashboard`; removed the history-write from `sjekk_resultater`; added `oppdater_dagens_historikk()` and wired it into `main()` step 4; rewrote `hent_kampresultat`'s row-selection logic (exact-date preference, no `df.iloc[0]` fallback, `er_hjemmekamp` now used to warn on orientation mismatch).
- `tests/test_bot.py` — Added 13 regression tests: 3 for CR-01 (`_json_til_script` escaping, malicious-payload dashboard render, normal-bet render unaffected), 4 for CR-02 (`sjekk_resultater` no longer touches `historikk`, `oppdater_dagens_historikk` update/insert behavior, full same-day settlement+placement sequence), 6 for CR-03 (exact-date preference, return-leg-only rejection, normal home win/loss, wrong-opponent rejection, empty API response).

## Decisions Made

- Followed the plan's exact specified mechanisms (function names, escaping approach, line-level target locations) — see `key-decisions` in frontmatter for the substantive ones.
- No commits were split into separate RED/GREEN/REFACTOR commits per the plan-level TDD process, since each task's own `<action>` instructed "write tests first, confirm they fail, then implement" as an in-task verification gate rather than requiring three separate commits (the plan's `tdd="true"` tasks did not specify multi-commit granularity, unlike a `type: tdd` plan-level gate). Failing-state confirmation was performed and is documented per task below; only the final, passing state was committed.

## Deviations from Plan

**None — plan executed exactly as written.** All three fixes match the plan's specified function names (`_json_til_script`, `oppdater_dagens_historikk`), escaping approach (`<` substitution, chained `.replace()` in `trygg()`), and CR-03 row-selection algorithm (exact-date match → `vs.`-only fallback → `None`) precisely as instructed. Two minor comment wording fixes were needed mid-task to avoid the new code's own explanatory comments accidentally containing the literal strings the tests were asserting the absence of (e.g. an example payload snippet in a comment, and the literal substring `df.iloc[0]` in a code comment) — these are wording-only, no logic change, and are not deviations from the plan's specified behavior.

## Issues Encountered

- Two self-inflicted false-positive test failures during Task 1 and Task 3, caused by newly-added Norwegian explanatory comments that happened to contain the exact literal strings the tests/grep-based verification checks were asserting must NOT appear in the file (a copy of the malicious payload text as an illustrative comment example; the literal substring `df.iloc[0]` used descriptively in a comment about removing that fallback). Resolved by rewording the comments to convey the same explanation without the literal collision. No functional code was affected.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- All three CR-01/CR-02/CR-03 findings from `02-REVIEW.md` are now closed; `PROJECT.md`'s Key Decisions table entry noting them as "still pending" should be updated to reflect closure.
- WR-01 through WR-06 and IN-02 from the same review remain explicitly out of scope and were not touched by this task.
- `dashboard.html` was regenerated from real on-disk state (`bankroll.json`/`bets.json`) as a smoke test: 20,366 bytes, exactly 2 `</script>` occurrences, no exceptions — confirms the f-string still evaluates correctly and the escaping doesn't break normal rendering. The regenerated file is gitignored and was not committed.
- Full pytest suite: 362 passed (349 baseline + 13 new), zero regressions.

---
*Quick task: 260831-c4z*
*Completed: 2026-08-31*

## Self-Check: PASSED

- FOUND: commit 7a544c9 (Task 1 / CR-01)
- FOUND: commit a1ab020 (Task 2 / CR-02)
- FOUND: commit 4bb7e3d (Task 3 / CR-03)
- FOUND: 06_bot.py
- FOUND: tests/test_bot.py
