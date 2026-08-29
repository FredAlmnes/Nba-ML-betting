---
phase: 05-walk-forward-backtest-engine
plan: 06
subsystem: injury-filter
tags: [skadefilter, as-of, backtest-engine, leakage-proof, injury-filter]

# Dependency graph
requires:
  - phase: 05-walk-forward-backtest-engine
    plan: 05
    provides: "spillerlogg.py + nba_spillerlogg_raw.csv (78,602-row player-game-log archive) and spillerlogg.les_spillerlogg()"
provides:
  - "skadefilter.sjekk_lag_helse_som_of() — the as-of-aware, network-free team-health check plan 05-07's walk-forward loop calls"
  - "skadefilter.sesong_grenser_for_dato() — date-driven season boundary, the parameterized replacement for gjeldende_sesong()'s clock read"
  - "The injury-filter half of BT-02's leakage proof, parallel to tests/test_parity.py::test_grenserad_paa_as_of_er_ekskludert on the feature side"
affects: [05-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Team-scoped recency window (last SISTE_N_KAMPER distinct GAME_DATE values), not player-scoped tail(3) — corrects 05-RESEARCH.md Pattern 7's draft, which would have made the filter structurally unable to flag an injured player"
    - "Single as-of chokepoint (hent_sesonglogg_som_of) — every other as-of helper routes through it, so the strict-< leakage boundary lives in exactly one place"
    - "Diagnostic counters (antall_toppspillere/antall_kamprader) alongside the verdict — lets the caller distinguish a genuinely healthy team from a vacuous pass on empty/uncovered data"

key-files:
  created: []
  modified:
    - skadefilter.py
    - tests/test_skadefilter.py

key-decisions:
  - "Corrected 05-RESEARCH.md Pattern 7's draft recency window from the player's own tail(3) to the team's last SISTE_N_KAMPER distinct game dates — see '## Korrigert Pattern 7' below"

requirements-completed: [BT-01, BT-02]

# Metrics
duration: 35min
completed: 2026-08-27
---

# Phase 5 Plan 6: skadefilter.py — As-Of Injury Filter Summary

**Added a date-driven season-boundary helper and an as-of-aware team-health check to `skadefilter.py` (six new pure, network-free functions), correcting a structural bug in `05-RESEARCH.md` Pattern 7's draft along the way, and proved the leakage boundary holds on both synthetic fixtures and the real 78,602-row player-game-log archive.**

## Performance

- **Duration:** ~35min (Task 1 write+verify, Task 2 write+verify+manual negative-control-on-negative-control, Task 3 real-archive smoke test)
- **Completed:** 2026-08-27
- **Tasks:** 3/3 completed
- **Files modified:** 2 (`skadefilter.py`, `tests/test_skadefilter.py`)

## Accomplishments

- `skadefilter.py` gained six new functions, purely additive — every pre-existing line is byte-identical (`git diff -U0 skadefilter.py | grep -c '^-[^-]'` → `0`):
  - `sesong_grenser_for_dato(dato)` — parameterized season-boundary derivation, never reads the clock (proven by a monkeypatch that makes `_dt.now()` raise).
  - `valider_spillerlogg(spillerlogg_df)` — raises `ValueError` on a missing required column or a datetime-typed `GAME_DATE`, naming the fix (`les_spillerlogg()`), rather than skip-and-log like the rest of the module.
  - `hent_sesonglogg_som_of(spillerlogg_df, team_id, as_of_dato)` — the single as-of chokepoint; strict `GAME_DATE < as_of_dato` inside the as-of season.
  - `hent_toppspillere_som_of(sesong_logg, antall)` — season-to-date top-N players by mean `MIN`, same record shape as the live `hent_toppspillere_for_lag`.
  - `bygg_siste3_som_of(sesong_logg, antall_kamper)` — adapter producing a `siste3`-shaped frame so `sjekk_spiller` is reused completely unmodified.
  - `sjekk_lag_helse_som_of(spillerlogg_df, team_id, lagnavn, as_of_dato, ...)` — the entry point plan 05-07 calls; same first three result-dict keys as `sjekk_lag_helse` plus `antall_toppspillere`/`antall_kamprader` diagnostics.
- `tests/test_skadefilter.py` extended from 9 to 22 tests (13 new), all deterministic and network-free — full suite green at **204 tests**.
- Real-archive smoke test (Task 3) confirms the filter finds 3 top players and produces plausible, historically-recognizable injury/availability signal on all 6 fixed team/date combinations — see below.

## Task Commits

Each task was committed atomically:

1. **Task 1:** `feat(05-06): add date-driven as-of injury filter to skadefilter.py` — `a35f387`
2. **Task 2:** `test(05-06): add as-of leakage-proof and live-parity tests for skadefilter.py` — `ea73e6c`
3. **Task 3:** No source-file commit — this task ran a read-only smoke check against the real `nba_spillerlogg_raw.csv` archive and found no defect, so no fix commit was needed. Numbers recorded below.

## Files Created/Modified

- `skadefilter.py` — Modified, purely additive (+179 lines). Six new as-of functions appended below the untouched live path.
- `tests/test_skadefilter.py` — Modified, purely additive (+290 lines). 13 new tests appended; module docstring extended with one paragraph naming the as-of coverage.

## Korrigert Pattern 7

`05-RESEARCH.md:400-431`'s Pattern 7 draft computed each top player's recent form as
`sesong_logg[sesong_logg["PLAYER_ID"] == sp["PLAYER_ID"]].tail(3)` — i.e. that player's own
last 3 appearances anywhere in the season. That is **not** what the live filter measures.
Live, `LeagueDashPlayerStats(last_n_games=3)` scopes to the *team's* last 3 games, and `GP`
counts how many of those the player actually appeared in — which is precisely how an injured
player registers as `GP` 0 or 1.

Under the draft's per-player `tail(3)`, any player with three appearances anywhere in the
season always yields `gp == 3`, so `sjekk_spiller` could never return `False` for him — the
whole filter would be structurally incapable of flagging anyone. This is Pitfall 1's
silent-always-healthy failure in a new disguise.

**Fix implemented in this plan:** `bygg_siste3_som_of` scopes the recent window to the
**team's** last `SISTE_N_KAMPER` (3) distinct `GAME_DATE` values before `as_of_dato`, then
counts each player's appearances within those dates. A player absent from all of those dates
is simply absent from the built `siste3` frame, which `sjekk_spiller` already reports as
"0 kamper siste 3".

Proven by `test_bygg_siste3_som_of_bruker_lagets_kampdatoer_ikke_spillerens` (a player who
plays the first 2 of 5 team dates and is then absent shows `GP` 0, i.e. is absent from the
frame entirely, rather than `GP == 2`) and by
`test_sjekk_lag_helse_som_of_flagger_fravaerende_toppspiller` (end-to-end: the same fixture
flags the missing top player). Plan 05-07's executor should read `05-RESEARCH.md`'s Pattern 7
draft as superseded by this correction, not as the implemented behavior.

## Røyktest mot ekte arkiv

Ran `sjekk_lag_helse_som_of` against the real, on-disk `nba_spillerlogg_raw.csv`
(78,602 rows, 2022-10-18 to 2025-04-13, 771 distinct players — see `05-05-SUMMARY.md`) for
3 fixed dates × 2 fixed teams. No `## Ufullstendig arkiv` heading exists in `05-05-SUMMARY.md`,
so the archive is treated as complete for all three seasons.

| Dato | Lag | `antall_kamprader` | `antall_toppspillere` | `tilgjengelig` | Toppspillere (sesong-til-dato min/kamp) |
|------|-----|---------------------|------------------------|----------------|-------------------------------------------|
| 2023-01-15 | Miami Heat | 403 | 3 | False | Tyler Herro (35.3), Kyle Lowry (35.0), Bam Adebayo (35.0) |
| 2023-01-15 | Toronto Raptors | 443 | 3 | True | Pascal Siakam (37.2), OG Anunoby (36.9), Fred VanVleet (36.5) |
| 2023-11-15 | Miami Heat | 107 | 3 | False | Bam Adebayo (34.6), Tyler Herro (34.0), Jimmy Butler III (33.9) |
| 2023-11-15 | Toronto Raptors | 107 | 3 | True | Scottie Barnes (36.2), Pascal Siakam (35.1), Dennis Schröder (32.3) |
| 2024-02-15 | Miami Heat | 543 | 3 | False | Bam Adebayo (34.5), Jimmy Butler III (33.9), Tyler Herro (33.7) |
| 2024-02-15 | Toronto Raptors | 581 | 3 | False | Scottie Barnes (35.2), Pascal Siakam (34.7), RJ Barrett (33.6) |

**Judged against the three expectations named in the plan:**

- `antall_toppspillere == 3` for all 6 combinations — pass. `TEAM_ID` values in the archive
  match `nba_api` team IDs and `MIN` survived as numeric.
- `antall_kamprader` grows within-season and is in the hundreds by mid-January: Heat
  403 rows by 2023-01-15; both teams' 2023-24-season counts grow from 107 (2023-11-15) to
  543/581 (2024-02-15) — pass, strictly larger as required.
- Named top players are recognizable starters for both franchises across the three seasons —
  pass, and the flagged absences line up with real, known events rather than looking like
  noise: Tyler Herro missed months of the 2023-24 season with a foot injury (flagged absent on
  2023-11-15); Pascal Siakam was traded from Toronto to Indiana in January 2024, days before
  the 2024-02-15 check (flagged absent for Toronto on that date); Kyle Lowry had a documented
  knee issue in January 2023 (flagged absent on 2023-01-15). No name looked wrong.

**Leakage spot-check on real data:** `sjekk_lag_helse_som_of` for `2023-01-15` (Miami Heat)
against the full archive produces a result dict identical to the same call against the archive
pre-truncated to `GAME_DATE < "2023-01-15"` — proving the function ignores the tens of
thousands of rows dated after the as-of date that are present in the full frame and absent
from the truncated one.

No defect was found; `skadefilter.py` and `tests/test_skadefilter.py` were not modified in
this task.

## API plan 05-07 calls

```python
skadefilter.sjekk_lag_helse_som_of(
    spillerlogg_df,      # the raw player-log DataFrame, injected by the caller
    team_id,              # nba_api TEAM_ID (int)
    lagnavn,               # display name, echoed back in the result dict
    as_of_dato,             # "YYYY-MM-DD" string or pd.Timestamp, the decision date
    antall=ANTALL_TOPPSPILLERE,  # optional, defaults to 3
    skriv_ut=False,               # optional, defaults to no console output
)
```

Returns a dict with exactly these keys, in this order: `lagnavn`, `tilgjengelig`,
`advarsler`, `antall_toppspillere`, `antall_kamprader`. The first three match
`sjekk_lag_helse`'s live-path shape exactly, so `backtest.py` can treat live and as-of
results identically.

**`backtest.py` — not `skadefilter.py` — is responsible for loading the log** via
`spillerlogg.les_spillerlogg()` and passing the resulting DataFrame into every
`sjekk_lag_helse_som_of` call. `skadefilter.py` deliberately never imports `spillerlogg`,
so the dependency direction stays `backtest.py -> {spillerlogg, skadefilter}` and the live
import graph `06_bot.py` uses is unaffected.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstring text tripped the plan's own `now()`/`today()` source-code grep**
- **Found during:** Task 1, first verification run
- **Issue:** `sesong_grenser_for_dato`'s docstring originally explained the fix by contrasting
  it with `_dt.now()`, which is a literal-string match for the acceptance check
  `assert 'now()' not in k`. The check exists to prove the as-of code path never reads the
  clock, but it (correctly, if bluntly) also matches the substring inside prose describing
  what the code does *not* do.
- **Fix:** Reworded the docstring to say "systemklokken" (system clock) instead of quoting
  `_dt.now()` literally. No behavior change — purely a docstring wording fix.
- **Files modified:** `skadefilter.py`
- **Commit:** `a35f387` (fixed before the task's own commit, not a separate commit)

**2. [Rule 1 - Bug] Same pattern recurred in the test file's section-header comment**
- **Found during:** Task 2, acceptance-criteria check `grep -c 'datetime.now\|import random'`
- **Issue:** A section-header comment above the new as-of test block said "ingen
  `datetime.now()` noe sted" (no `datetime.now()` anywhere), which is itself a literal match
  for the plan's own no-network-read grep.
- **Fix:** Reworded to "ingen lesing av systemklokken noe sted" (no reading of the system
  clock anywhere). No behavior change.
- **Files modified:** `tests/test_skadefilter.py`
- **Commit:** `ea73e6c` (fixed before the task's own commit, not a separate commit)

No other deviations — `skadefilter.py`'s logic and `tests/test_skadefilter.py`'s test bodies
were implemented exactly as the plan specified on the first pass; the real-archive smoke test
(Task 3) found no defect.

## Issues Encountered

None beyond the two docstring-wording fixes above. System `python3` still lacks
`pytest`/`nba_api`-compatible `pandas` on this machine (consistent with prior plans'
findings) — all verification ran via `./venv/bin/python3`.

## Negative-control-on-negative-control (Task 2 acceptance criterion)

Temporarily changed `hent_sesonglogg_som_of`'s `GAME_DATE < as_of_dato` filter to `<=` and
re-ran `test_hent_sesonglogg_som_of_ekskluderer_grenseraden`: it failed as expected
(`assert 3 == 2`, the boundary-dated row leaked in). Reverted immediately with `mv
skadefilter.py.bak skadefilter.py`, confirmed `git diff --stat skadefilter.py` was empty
afterward, and re-ran the test to confirm it passes again. This is the proof that the test
genuinely exercises the strict-`<` boundary rather than passing vacuously.

## User Setup Required

None — this plan added no new dependency and made no network call. All verification and the
real-archive smoke test used data already fetched by plan 05-05.

## Next Phase Readiness

- Plan 05-07's walk-forward loop can call `skadefilter.sjekk_lag_helse_som_of(spillerlogg_df,
  team_id, lagnavn, as_of_dato)` for both teams on every game date, loading `spillerlogg_df`
  once via `spillerlogg.les_spillerlogg()` and reusing it across all ~960 iterations — the
  function makes zero network calls and is provably leakage-safe.
- `05-RESEARCH.md` Pattern 7's draft recency window (per-player `tail(3)`) is superseded by
  the team-scoped `SISTE_N_KAMPER`-dates window implemented here — see "## Korrigert Pattern 7"
  above.
- `gjeldende_sesong()`'s clock-driven duplication (flagged in `04-02-SUMMARY.md` and
  `02-05-SUMMARY.md` as a Phase 5 consolidation candidate) remains unresolved by design — this
  plan adds a parallel, parameterized function rather than touching the live one, per the
  plan's explicit "leave `gjeldende_sesong()` byte-identical" instruction. Still flagged as an
  open consolidation candidate for whenever the project addresses it.
- Full pytest suite green (204 tests); no blockers for Plan 05-07.

---
*Phase: 05-walk-forward-backtest-engine*
*Completed: 2026-08-27*

## Self-Check: PASSED

- `skadefilter.py` exists and contains all 6 new function definitions: FOUND
- `tests/test_skadefilter.py` exists and contains 22 tests: FOUND
- `.planning/phases/05-walk-forward-backtest-engine/05-06-SUMMARY.md` exists: FOUND
- Commit `a35f387` exists: FOUND
- Commit `ea73e6c` exists: FOUND
- `python3 -m pytest tests/ -q` → 204 passed
