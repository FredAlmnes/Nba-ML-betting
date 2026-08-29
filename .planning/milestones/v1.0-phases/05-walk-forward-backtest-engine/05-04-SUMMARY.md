---
phase: 05-walk-forward-backtest-engine
plan: 04
subsystem: backtest-engine
tags: [sqlite, odds-archive, pricing-rule, parity, tdd]

# Dependency graph
requires:
  - phase: 04-odds-integration-live-refactor
    provides: odds.py's odds_arkiv SQLite schema, apne_arkiv, arkiver_odds_rader, parse_snapshot_til_rader
provides:
  - "odds.velg_beste_pris_per_utfall — the single best-price-per-outcome reduction rule, called by both live and backtest"
  - "odds.prisrader_fra_kamp — live Odds API game dict flattener feeding the shared rule"
  - "odds.hent_bet_time_pris / odds.hent_closing_pris — archive readers returning (hjemme_odds, borte_odds) or (None, None)"
affects: [05-07-walk-forward-loop, 05-08-ledger-clv-column, 05-11-live-backtest-parity-test]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Extract-then-rewire-then-build: pull inline decision logic into a pure shared function, prove it behaviour-preserving via the untouched live regression suite, only then build new callers on top of the proven rule"
    - "Missing-data contract: (None, None) return for any unresolvable price lookup, never an exception, never a partial/half-filled pair — caller skips and counts"
    - "Two separately-named functions instead of one parameterised function, to make a forbidden data path (closing price reaching a decision) structurally unreachable rather than convention-enforced"

key-files:
  created: []
  modified:
    - odds.py
    - verdi_deteksjon.py
    - tests/test_odds.py

key-decisions:
  - "velg_beste_pris_per_utfall passes pris through unchanged (no float() coercion), preserving whatever value type the live Odds API payload or archive row already carries"
  - "_hent_beste_arkivpris pre-aggregates via SQL MAX(odds) GROUP BY utfall_navn before reducing through velg_beste_pris_per_utfall in Python — provably equivalent (max of an already-maximal value per outcome is that value), keeps the actual side-mapping/winner rule in exactly one place"
  - "No public snapshot_type parameter anywhere: hent_bet_time_pris and hent_closing_pris each bind their own literal to the private _hent_beste_arkivpris, making decision code structurally unable to reach a closing price by passing an argument (BT-02)"

requirements-completed: [BT-01, BT-02, BT-06]

# Metrics
duration: 20min
completed: 2026-08-27
---

# Phase 5 Plan 04: Shared Price Selection + Archive Readers Summary

**Extracted the live bot's inline best-price-across-bookmakers loop into `odds.velg_beste_pris_per_utfall`, rewired `verdi_deteksjon.finn_value_bets` onto it, and built `odds.hent_bet_time_pris`/`odds.hent_closing_pris` archive readers on top of that same proven rule — giving the backtest historical prices without ever risking a second, silently-diverging pricing rule.**

## Performance

- **Duration:** ~20 min (RED commit 10:xx -> final GREEN commit 10:29, across 3 tasks / 5 commits)
- **Completed:** 2026-08-27
- **Tasks:** 3 (Task 1 and Task 3 each executed as RED + GREEN TDD commits; Task 2 as a single refactor commit)
- **Files modified:** 3 (`odds.py`, `verdi_deteksjon.py`, `tests/test_odds.py`)

## Kontrakt for plan 05-07/05-08

Plan 05-07 (walk-forward loop, odds join, skip counter) and plan 05-08 (ledger `clv` column) read this section as their upstream contract — no need to re-read `odds.py`.

```python
odds.velg_beste_pris_per_utfall(prisrader, hjemme_navn, borte_navn)
# prisrader: iterable of (utfall_navn, pris, bookmaker) triples
# -> (beste_hjemme_odds, beste_borte_odds, beste_hjemme_bookmaker, beste_borte_bookmaker)
#    any of the four is None if no qualifying row exists for that side.
#    Strict '>' tie rule: first bookmaker at the best price wins. Non-positive
#    prices (0, negative) are ignored. pris is passed through unchanged (no
#    float() coercion). This is the ONLY best-price-per-outcome rule in the
#    codebase — called by verdi_deteksjon.finn_value_bets (live) AND
#    hent_bet_time_pris (backtest).

odds.prisrader_fra_kamp(kamp)
# kamp: one live Odds API game dict (bookmakers -> markets -> outcomes)
# -> list of (utfall_navn, pris, bookmaker) triples, ready for
#    velg_beste_pris_per_utfall. Uses MARKED constant, never a bare "h2h"
#    literal. Tolerant traversal: .get() at every level, bookmaker title
#    falls back to key, missing outcomes -> skipped market.

odds.hent_bet_time_pris(con, kamp_dato, hjemme_lag_id, borte_lag_id)
odds.hent_closing_pris(con, kamp_dato, hjemme_lag_id, borte_lag_id)
# -> (hjemme_odds, borte_odds), or (None, None) for: no archived snapshot,
#    a wrong date/team-id combination, or a one-sided price pair (unusable
#    for strategy.fjern_vigorish's vig removal, which needs both sides).
#
# SKIP CONTRACT: (None, None) means "skip this game and count the skip" —
# it must NEVER be read as "no value found", and hent_bet_time_pris's
# (None, None) must NEVER be backfilled from hent_closing_pris. Neither
# function reads the other's snapshot_type; there is no public
# snapshot_type parameter anywhere, so decision code cannot structurally
# reach a closing price (BT-02). 7 of 3,650 archived games legitimately
# have no closing snapshot — that is the BT-06 "CLV unavailable" case, not
# an error.
```

Golden cases verified directly against the real 67MB `odds_arkiv.db` (not just the in-memory test fixture):

| Game | bet_time (hjemme, borte) | closing (hjemme, borte) |
|------|--------------------------|--------------------------|
| `"2023-01-15"`, Lakers (1610612747) vs 76ers (1610612755) | `(2.45, 1.68)` | `(2.97, 1.55)` |
| `"2023-03-11"`, Suns (1610612756) vs Kings (1610612758) | `(1.72, 2.3)` | `(None, None)` — real gap game |

## Accomplishments

- `odds.velg_beste_pris_per_utfall` is now the single definition of "which price do we bet at" in the whole codebase — extracted verbatim from the inline triple loop that used to live in `verdi_deteksjon.finn_value_bets`, preserving strict-`>` first-bookmaker-wins tie behaviour and the "no qualifying price" semantics (now `None` instead of the old `0` sentinel).
- `odds.prisrader_fra_kamp` flattens a live Odds API game dict through the exact same tolerant idiom `parse_snapshot_til_rader` already uses for archived snapshots — live and archive payloads now converge on one flattening logic.
- `verdi_deteksjon.finn_value_bets` was rewired onto both shared functions; the inline bookmaker/market/outcome loop, the `"h2h"` literal, and the `0`-sentinel guard are gone from that file entirely. `grep -v '^\s*#' verdi_deteksjon.py | grep -c 'bookmakers'` is `0`.
- `odds.hent_bet_time_pris`/`odds.hent_closing_pris` give the backtest historical prices, built as thin wrappers around a private `_hent_beste_arkivpris` that pre-aggregates via parameterized SQL (`MAX(odds) ... GROUP BY utfall_navn`) then reduces through the same `velg_beste_pris_per_utfall` rule — proven equivalent to the raw-row-through-Python path by a dedicated parity test.
- All archive SQL uses `?` placeholders exclusively; a source-level test (`test_odds_py_har_ingen_string_formatert_sql`) asserts `execute(f"`/`execute(f'` never appears in `odds.py`.
- Full suite: **180 tests passing** (164 pre-existing + 16 new: 9 in Task 1, 7 in Task 3 — `test_odds.py` alone grew from 59 to 75 tests; `test_verdi_deteksjon.py`'s pre-existing 9 tests stayed untouched and green throughout).

## Task Commits

Each task was committed atomically, Tasks 1 and 3 following the RED -> GREEN TDD cycle:

1. **Task 1 (RED):** `test(05-04): add failing test for velg_beste_pris_per_utfall/prisrader_fra_kamp` — `b898a6d`
2. **Task 1 (GREEN):** `feat(05-04): extract shared best-price-per-outcome rule into odds.py` — `a0bee5e`
3. **Task 2:** `refactor(05-04): rewire finn_value_bets onto odds.velg_beste_pris_per_utfall` — `0b57a56`
4. **Task 3 (RED):** `test(05-04): add failing test for hent_bet_time_pris/hent_closing_pris archive readers` — `3c31a59`
5. **Task 3 (GREEN):** `feat(05-04): add hent_bet_time_pris and hent_closing_pris archive readers` — `2e3684d`

No REFACTOR-phase commits were needed on either TDD task — the GREEN implementations required no cleanup pass.

## Files Created/Modified

- `odds.py` — Added `velg_beste_pris_per_utfall`, `prisrader_fra_kamp`, `_hent_beste_arkivpris`, `hent_bet_time_pris`, `hent_closing_pris` under a new "Delt pris-seleksjonsregel" banner section, positioned after `parse_snapshot_til_rader` and before the "Backfill-driveren" banner
- `verdi_deteksjon.py` — `finn_value_bets`'s inline bookmaker/market/outcome loop (lines 141-159 pre-edit) replaced by a single call chain through `odds.prisrader_fra_kamp` + `odds.velg_beste_pris_per_utfall`; guard changed from `beste_hjemme_odds == 0 or beste_borte_odds == 0` to an `is None` check
- `tests/test_odds.py` — 18 new tests across two `# ---` banner sections (Task 1's reducer/flattener behaviour cases, Task 3's archive-reader behaviour cases); `_rad()` extended with an optional `odds=1.85` keyword (default preserves every existing call site)

## Decisions Made

- `velg_beste_pris_per_utfall` never coerces `pris` with `float()` — passes the caller's value through unchanged, so live's emitted value-bet dict keeps exactly the value types it emitted before this extraction (verified by the untouched `test_finn_value_bets_uendret_output` still passing byte-for-byte).
- `_hent_beste_arkivpris`'s SQL pre-aggregation (`MAX(odds) ... GROUP BY utfall_navn`) is deliberately redundant with what `velg_beste_pris_per_utfall` would compute in Python — kept anyway as an index-friendly narrowing, with a dedicated test (`test_arkivleser_reduserer_som_velg_beste_pris_per_utfall`) proving the two paths agree rather than just asserting by inspection.
- A one-sided archived price pair (only home or only away side present) returns `(None, None)`, not a half-filled tuple — `strategy.fjern_vigorish` needs both sides to remove the vig, so a partial pair is unusable and gets the same "skip" treatment as a fully missing snapshot.

## Deviations from Plan

**1. [Rule 1 - Bug] Docstring literal `"h2h"` string tripped the plan's own acceptance grep**

- **Found during:** Task 1, running the acceptance criteria checks after implementation
- **Issue:** `prisrader_fra_kamp`'s docstring originally said `aldri en bar "h2h"-streng` — the quoted literal made `grep -v '^\s*#' odds.py | grep -c '"h2h"'` return `2` instead of the plan's required `1` (only `MARKED = "h2h"`'s own definition should survive the comment filter)
- **Fix:** Reworded the docstring to `aldri en bar h2h-streng-literal` (no quotes around h2h), preserving the same meaning without the literal grep-matchable string
- **Files modified:** `odds.py`
- **Verification:** `grep -v '^\s*#' odds.py | grep -c '"h2h"'` now outputs `1`; full `tests/test_odds.py` suite still green
- **Committed in:** `a0bee5e` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 bug in a docstring, not runtime code)
**Impact on plan:** Cosmetic docstring wording only; no behavioural change. No scope creep.

## Live-vs-extracted-rule faithfulness (for plan 05-11)

No test in `tests/test_verdi_deteksjon.py` needed a source change to stay green — the file's `git diff` is empty (`REGRESJONSNETT_URORT`). All 9 of its tests, including the hand-calculated `test_finn_value_bets_uendret_output` and the multi-bookmaker `test_finn_value_bets_velger_beste_odds_pa_tvers_av_bookmakers`, pass unmodified against the rewired `finn_value_bets`. This is direct, mechanical evidence that `velg_beste_pris_per_utfall` reproduces the old inline loop's behaviour exactly (including its strict-`>` tie rule and its "either side missing -> skip" guard), not a reinterpretation of it — the exact proof plan 05-11's live-vs-backtest parity test needs to build on.

## Issues Encountered

None. System `python3` still lacks `pytest`/`xgboost` on this machine (consistent with every prior Phase 5 plan) — all verification ran via `./venv/bin/python3`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Plan 05-07's walk-forward loop can call `odds.hent_bet_time_pris(con, kamp_dato, hjemme_lag_id, borte_lag_id)` per game and get either a real `(hjemme_odds, borte_odds)` pair or an unambiguous `(None, None)` skip signal (BT-01 satisfied)
- Plan 05-08's ledger `clv` column can call `odds.hent_closing_pris(...)` independently, with the archive-verified guarantee that it never overlaps with the bet_time price used for the decision (BT-02/BT-06 satisfied)
- Exactly one best-price-per-outcome rule exists in the codebase (`grep -v '^\s*#' verdi_deteksjon.py | grep -c 'bookmakers'` is `0`); a future pricing-rule change only needs to touch `odds.velg_beste_pris_per_utfall`
- Full pytest suite green (180 tests); no blockers for plan 05-05

---
*Phase: 05-walk-forward-backtest-engine*
*Completed: 2026-08-27*

## Self-Check: PASSED

All claimed files found on disk (`odds.py`, `verdi_deteksjon.py`, `tests/test_odds.py`, `05-04-SUMMARY.md`) and all five task commit hashes (`b898a6d`, `a0bee5e`, `0b57a56`, `3c31a59`, `2e3684d`) verified present in `git log --oneline --all`.
