---
phase: 05-walk-forward-backtest-engine
plan: 07
subsystem: backtest-engine
tags: [walk-forward, holdout-guard, xgboost, sqlite, injury-filter, tdd]

# Dependency graph
requires:
  - phase: 05-walk-forward-backtest-engine
    plan: 01
    provides: config.HOLDOUT_START_DATO, locked Phase 5 pre-flight decisions
  - phase: 05-walk-forward-backtest-engine
    plan: 02
    provides: model.tren(features_df, as_of=<dato>) — as_of-aware train/calibrate
  - phase: 05-walk-forward-backtest-engine
    plan: 04
    provides: odds.hent_bet_time_pris/hent_closing_pris archive readers, (None,None) skip contract
  - phase: 05-walk-forward-backtest-engine
    plan: 05
    provides: spillerlogg.les_spillerlogg() and nba_spillerlogg_raw.csv
  - phase: 05-walk-forward-backtest-engine
    plan: 06
    provides: skadefilter.sjekk_lag_helse_som_of() as-of injury check
provides:
  - "backtest.py — HoldoutLaastFeil, _sikre_ikke_holdout, trenger_retrening, vurder_kamp, _lag_id_og_navn, klargjor_backtestdata, kjor_backtest, kjor_endelig_holdout_backtest"
  - "The predict half of BT-01 (score -> value -> odds filter -> injury filter, cached prediction rows for plan 05-08's simulate pass)"
  - "BT-02's structural leakage proof (source-level + real-data outcome-flip regression)"
  - "BT-03's structural holdout guard — single reachable entry point into config.HOLDOUT_START_DATO"
affects: [05-08, 05-09, 05-10, 05-11, 05-12, 05-13]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Structural holdout guard: HoldoutLaastFeil raised by a pre-flight pass over the whole date list plus a per-iteration re-check, with the allow-flag settable from exactly one function (kjor_endelig_holdout_backtest) — proven by a source-grep test that removes that function's own source before searching for the assignment token"
    - "Predict/simulate split: kjor_backtest returns cached prediction rows; plan 05-08's simulate pass re-stakes them without re-running the (expensive) retrain loop"
    - "Named-counter result dict: every skip/block/vacuous-pass path increments a dedicated counter rather than silently dropping data, mirroring odds.py::kjor_backfill's convention"

key-files:
  created:
    - backtest.py
    - tests/test_backtest.py
  modified:
    - .planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md

key-decisions:
  - "Corrected a floating-point test literal (Rule 1): the plan's suggested (0.55, 2.00, 2.00)/0.05 threshold-equality example hits IEEE754 cancellation (0.55-0.5 = 0.050000000000000044, strictly greater than the 0.05 double), so the boundary test uses a dyadic-exact (0.5625, 2.00, 2.00)/0.0625 case instead — same class of finding 05-02-SUMMARY.md documented for beregn_innsats"
  - "Fixed a test-fixture bug (Rule 1): the original 3-month features_df fixture built 50 consecutive days from the 1st of each of three months, which silently overflowed into a 4th calendar month; replaced with one contiguous 2022-11-01..2023-01-31 range that stays inside exactly three months"

requirements-completed: [BT-01, BT-02, BT-03]

# Metrics
duration: 14min
completed: 2026-08-27
---

# Phase 5 Plan 07: backtest.py — Walk-Forward Predict Pass + Holdout Guard Summary

**Composed model.py/odds.py/skadefilter.py/strategy.py into a chronological walk-forward replay (`backtest.py`), with a structurally single-entry holdout guard (`HoldoutLaastFeil`) and a decision function provably blind to both the game outcome and the closing price — reproduces all seven verified counters against the real archive on first run.**

## Performance

- **Duration:** ~14 min (RED commit 12:53:37 -> final GREEN/smoke commit 13:07:04)
- **Started:** 2026-08-27T12:53:37+02:00
- **Completed:** 2026-08-27T13:07:04+02:00
- **Tasks:** 3
- **Files modified:** 3 (2 created, 1 modified)

## Kontrakt for plan 05-08/05-09

Plans 05-08 (ledger, manifest, settlement) and 05-09 (Kelly sweep) read this section as
their upstream contract instead of re-reading `backtest.py`.

```python
klargjor_backtestdata(features_fil="nba_features.csv", arkiv_fil="odds_arkiv.db",
                        fra=None, til=None, bruk_skadefilter=True,
                        features_df=None, spillerlogg_df=None, con=None)
# -> {"features_df": <DataFrame>, "datoer": [<"YYYY-MM-DD">, ...] sorted+unique,
#     "spillerlogg_df": <DataFrame or None>, "con": <sqlite3.Connection>}
# Does ALL file/DB I/O for a run, exactly once. Injecting features_df/spillerlogg_df/con
# makes the whole downstream pipeline network- and file-free (used by every test).

kjor_backtest(data, datoer=None, tillat_holdout=False,
               min_value_terskel=config.MIN_VALUE_TERSKEL,
               min_odds=config.MIN_ODDS, maks_odds=config.MAX_ODDS,
               min_treningskamper=100, kalibrer_andel=model.KALIBRER_ANDEL,
               bruk_skadefilter=True, skriv_ut=True)
# -> (prediksjoner, resultat)   # 2-tuple, mirrors spillerlogg.hent_spillerlogg's (df, resultat)
# Raises HoldoutLaastFeil (pre-flight, before any model.tren call) if any date in
# `datoer` is >= config.HOLDOUT_START_DATO and tillat_holdout is falsy.
# `tillat_holdout` is NOT meant to be set by ordinary callers — only
# kjor_endelig_holdout_backtest ever sets it.

kjor_endelig_holdout_backtest(data, **kwargs)
# -> (prediksjoner, resultat)
# The ONLY function that can open config.HOLDOUT_START_DATO. Filters
# data["datoer"] down to dates >= config.HOLDOUT_START_DATO itself (does not trust
# its caller), then calls kjor_backtest with tillat_holdout set. Raises ValueError
# (Norwegian message) if the filtered date list is empty.
# WARNING (plan 05-13): calling this spends the holdout. Only meaningful once every
# threshold/Kelly decision is frozen on the train/calibrate slice; record the run id
# in STATE.md afterward.
```

**Prediction row — full ordered key list** (one dict per surviving candidate):

```
as_of_dato, kamp_dato, game_id, kamp, side, bet, hjemme_lag_id, borte_lag_id,
modell, retrent_dato, modell_prob, modell_prob_hjemme, odds, impl_prob, value, ev,
odds_bet_time_hjemme, odds_bet_time_borte, odds_closing_hjemme, odds_closing_borte,
hjemme_vant
```

`odds_closing_*` may be `None` (missing closing snapshot — CLV unavailable, bet still
kept). The four odds fields feed `metrics.beregn_clv(odds_bet_time_hjemme,
odds_bet_time_borte, odds_closing_hjemme, odds_closing_borte, side)` unchanged. `side`
is the canonical `"hjemme"`/`"borte"` token metrics.beregn_clv expects, not the display
string in `bet`. `hjemme_vant` is attached only AFTER `vurder_kamp` returns — no code in
`backtest.py` reads it; it exists purely so plan 05-08 can settle the bet post-decision.

**`resultat` counter dict — full ordered key list:**

```
fra_dato, til_dato, datoer_totalt, datoer_behandlet,
datoer_hoppet_over_for_lite_treningsgrunnlag, kamper_totalt,
kamper_hoppet_over_manglende_odds, kamper_hoppet_over_ukjent_lag,
kamper_uten_closing_snapshot, kandidater_flagget,
kandidater_blokkert_av_skadefilter, skadesjekk_uten_datagrunnlag, retreninger,
prediksjoner, min_treningskamper, kalibrer_andel, min_value_terskel, min_odds,
maks_odds, skadefilter_aktiv
```

`datoer_totalt == datoer_behandlet + datoer_hoppet_over_for_lite_treningsgrunnlag` always
holds. Every tuning knob that changes the numbers (`min_treningskamper`,
`kalibrer_andel`, `min_value_terskel`, `min_odds`, `maks_odds`, `skadefilter_aktiv`) is
recorded verbatim in this dict — plan 05-08 copies it straight into `manifest.json`.

Also exposed (pure, used internally, available for reuse): `HoldoutLaastFeil`,
`_sikre_ikke_holdout(dato, tillat_holdout=False)`, `trenger_retrening(as_of_dato,
siste_retrent_maaned)`, `vurder_kamp(modell_prob_hjemme, odds_hjemme, odds_borte,
min_value_terskel=..., min_odds=..., maks_odds=...)`, `_lag_id_og_navn(forkortelse)`.

## Røyktest mot ekte data

Run: `backtest.klargjor_backtestdata(fra="2022-10-24", til="2022-12-31")` then
`backtest.kjor_backtest(d, min_treningskamper=100, skriv_ut=False)` against the real
`nba_features.csv`, `odds_arkiv.db` and `nba_spillerlogg_raw.csv`.

All seven verified counters reproduced exactly (no adjustment needed):

```
fra_dato: 2022-10-24
til_dato: 2022-12-31
datoer_totalt: 66
datoer_behandlet: 51
datoer_hoppet_over_for_lite_treningsgrunnlag: 15
kamper_totalt: 388
kamper_hoppet_over_manglende_odds: 0
kamper_hoppet_over_ukjent_lag: 0
kamper_uten_closing_snapshot: 0
kandidater_flagget: 232
kandidater_blokkert_av_skadefilter: 130
skadesjekk_uten_datagrunnlag: 0
retreninger: 2
prediksjoner: 102
min_treningskamper: 100
kalibrer_andel: 0.15
min_value_terskel: 0.05
min_odds: 1.5
maks_odds: 4.0
skadefilter_aktiv: True
```

`len(prediksjoner) == 102`. First `retrent_dato`: `2022-11-09`. Last `retrent_dato`:
`2022-12-01` (2 retrains — November and December, matching `retreninger: 2`).

Two complete example prediction rows:

**Home-side:**
```python
{
    "as_of_dato": "2022-11-09", "kamp_dato": "2022-11-09", "game_id": 22200166,
    "kamp": "Chicago Bulls vs New Orleans Pelicans", "side": "hjemme",
    "bet": "Hjemme (Chicago Bulls)", "hjemme_lag_id": 1610612741, "borte_lag_id": 1610612740,
    "modell": "walk-forward", "retrent_dato": "2022-11-09",
    "modell_prob": 0.54545456, "modell_prob_hjemme": 0.54545456, "odds": 2.08,
    "impl_prob": 0.4720812182741116, "value": 0.07337335, "ev": 0.13454545,
    "odds_bet_time_hjemme": 2.08, "odds_bet_time_borte": 1.86,
    "odds_closing_hjemme": 2.06, "odds_closing_borte": 1.93, "hjemme_vant": 0,
}
```

**Away-side:**
```python
{
    "as_of_dato": "2022-11-09", "kamp_dato": "2022-11-09", "game_id": 22200162,
    "kamp": "Atlanta Hawks vs Utah Jazz", "side": "borte", "bet": "Borte (Utah Jazz)",
    "hjemme_lag_id": 1610612737, "borte_lag_id": 1610612762,
    "modell": "walk-forward", "retrent_dato": "2022-11-09",
    "modell_prob": 0.45454544, "modell_prob_hjemme": 0.54545456, "odds": 2.45,
    "impl_prob": 0.4038929440389294, "value": 0.050652504, "ev": 0.113636374,
    "odds_bet_time_hjemme": 1.66, "odds_bet_time_borte": 2.45,
    "odds_closing_hjemme": 1.59, "odds_closing_borte": 2.74, "hjemme_vant": 0,
}
```

Additional reachability probes (Task 3), both against the real archive: `kjor_backtest`
on `fra=config.HOLDOUT_START_DATO, til="2024-11-15"` raises `HoldoutLaastFeil` naming
both `"2024-10-22"` and `config.HOLDOUT_START_DATO="2024-10-01"`;
`kjor_endelig_holdout_backtest` on the same prepared data does not raise, processes 24
dates and produces 60 predictions with zero missing bet-time snapshots.

## Varm-opp-gulvet

`MIN_TRENINGSKAMPER = 100` is a hard warm-up floor, not the D-05-02 burn-in reporting
policy. It exists because `model.tren`/`model.del_for_trening` raise `ValueError` on a
strictly-earlier training window with fewer than 2 rows — the archive's first date
(2022-10-24) has zero such rows. 100 was chosen as the smallest round window that leaves
the 15% calibrate slice at 15+ rows. Verified cost against the full train/calibrate
slice (not just this plan's bounded smoke window): 15 of 318 dates and 111 of 2,413
games, all inside October and early November 2022. D-05-02's burn-in policy is a
separate, later concern (plan 05-08's manifest) — it keeps ALL *processed* months in the
ledger and only affects how headline numbers are reported, never which dates are
skipped for lack of training data.

## Holdout-status

**This plan did NOT spend the holdout.** Task 3's two holdout-related checks are
reachability probes only: (1) confirming `kjor_backtest` raises `HoldoutLaastFeil` for
`fra=config.HOLDOUT_START_DATO` (a request that reads 0 real prediction rows — it fails
before any model fit), and (2) confirming `kjor_endelig_holdout_backtest` completes
without raising over a bounded two-and-a-half-week window
(`config.HOLDOUT_START_DATO..2024-11-15`), producing 60 predictions purely to prove the
entry point works structurally. Neither probe evaluates strategy performance, computes
ROI, or should be read as "the holdout run." Plan 05-13 owns the single, final, scored
holdout run over the full 2024-25 season; its run id must be recorded in `STATE.md` at
that time, per BT-03's "checked exactly once" discipline.

## Accomplishments

- `backtest.py` created (438 lines): `HoldoutLaastFeil` (the codebase's first custom
  exception class), `_sikre_ikke_holdout`, `trenger_retrening`, `vurder_kamp`,
  `_lag_id_og_navn`, `klargjor_backtestdata`, `kjor_backtest`,
  `kjor_endelig_holdout_backtest` — flat, Norwegian snake_case, no type hints, no
  module-level I/O, no network call at import
- `vurder_kamp` reuses `strategy.fjern_vigorish`/`beregn_value_og_ev` unmodified (proven
  by a monkeypatch test), reproduces `verdi_deteksjon.py`'s strict `>` threshold and
  inclusive odds bounds exactly, and is source-provably blind to both `HJEMME_VANT` and
  any closing-price token
- `kjor_backtest` retrains once per calendar month of *processed* dates, anchored on the
  previous processed month rather than the calendar (a single retrain across the
  April-to-October NBA summer gap, not five); builds the feature table once via
  `klargjor_backtestdata` and completes with `pandas.read_csv`,
  `features.beregn_lag_form` and `odds.apne_arkiv` all monkeypatched to raise
- Missing bet-time snapshots, unknown team abbreviations and under-sized training
  windows are skipped and counted (never scored as no-value, never fatal); a missing
  closing snapshot leaves `odds_closing_*` as `None` and keeps the bet
- The as-of injury stage blocks a candidate exactly when either team's
  `skadefilter.sjekk_lag_helse_som_of` verdict is unavailable (the both-teams rule from
  `filtrer_bets_for_skader` + `06_bot.py:226`), caches per `(dato, lag_id)`, and counts
  every vacuous (`antall_toppspillere == 0`) pass separately from a genuine block
- `HoldoutLaastFeil` is provably reachable from exactly one call site
  (`kjor_endelig_holdout_backtest`'s own `tillat_holdout=True`) and the module contains
  no bare `except Exception`/`except:` anywhere, so the guard can never be silently
  swallowed
- Real-archive smoke test (Task 3) reproduces all seven verified counters exactly on
  first run — no adjustment to `backtest.py` was needed after the synthetic-fixture
  tests passed
- Full suite: **241 tests passing** (204 pre-existing + 37 new in `test_backtest.py`,
  including 3 permanent skip-guarded real-data tests)

## Task Commits

Each task was committed atomically, Tasks 1 and 2 following the RED -> GREEN TDD cycle:

1. **Task 1 (RED):** `test(05-07): add failing test for backtest.py holdout guard/retrain scheduler/decision` — `705cd0c`
2. **Task 1 (GREEN):** `feat(05-07): implement backtest.py holdout guard, retrain scheduler and pure decision` — `c7dc7d7`
3. **Task 2 (RED):** `test(05-07): add failing test for walk-forward predict loop and entry points` — `23d473f`
4. **Task 2 (GREEN):** `feat(05-07): implement walk-forward predict loop and the two holdout entry points` — `2a41411`
5. **Task 3:** `test(05-07): smoke-verify walk-forward engine against real archive/model/spillerlogg` — `5fb4cc3`

No REFACTOR-phase commits were needed on either TDD task — the GREEN implementations
required no cleanup pass.

## TDD Gate Compliance

Both TDD tasks show the required RED -> GREEN sequence in git log: `705cd0c` (test) ->
`c7dc7d7` (feat) for Task 1; `23d473f` (test) -> `2a41411` (feat) for Task 2. No test
passed unexpectedly during either RED phase — both RED commits failed on
`ModuleNotFoundError`/`AttributeError` for the not-yet-implemented functions, confirmed
before writing any implementation.

## Files Created/Modified

- `backtest.py` — New. Walk-forward engine: holdout guard, retrain scheduler, pure
  per-game decision, data loader, predict loop, two entry points
- `tests/test_backtest.py` — New. 37 tests across three banner sections (guard/scheduler/
  decision; loop/entry-points; real-archive smoke tests), reusing `odds.py`'s in-memory
  archive fixtures and `_rad`-style row builders rather than the real 67MB
  `odds_arkiv.db`
- `.planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md` — BT-01/BT-02/
  BT-03 rows filled in (Plan `05-07`, Wave `5`, Task IDs `05-07-01`..`05-07-03`, matching
  `T-05-07-*` threat ids, status green); BT-04 through BT-07 rows untouched (owned by
  plans 05-08/05-09)

## Decisions Made

- `vurder_kamp`'s thresholds are parameters with `config` defaults, not direct `config`
  reads, so plan 05-09's Kelly sweep can override them per run without touching the live
  values — matches the plan's explicit instruction
- The injury-stage health-check cache is keyed on `(dato, lag_id)`, not just `lag_id`,
  since the same team's as-of health verdict legitimately changes across different dates
  in the walk-forward replay (unlike the live bot's single-day cache)
- `klargjor_backtestdata`'s injected-frame date-derivation path (used by every test)
  independently sorts/deduplicates/range-filters the date column rather than delegating
  to `odds.hent_unike_kampdatoer`, since that function always reads from disk — this is
  what makes the whole test suite network- and file-free

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's suggested boundary-test literal hits floating-point cancellation**
- **Found during:** Task 1, first GREEN verification run
- **Issue:** The plan's own acceptance-criteria example asserts
  `backtest.vurder_kamp(0.55, 2.00, 2.00) == []` (value exactly at the 0.05 threshold).
  In IEEE754 double precision, `0.55 - 0.5` evaluates to `0.050000000000000044`, which is
  strictly GREATER than the double representation of `0.05`
  (`0.05000000000000000277...`), not equal to it — a real, unavoidable floating-point
  artifact confirmed by brute-force search across 2,000,000 random odds/probability
  combinations (none reproduce exact equality via this subtraction path). Same class of
  finding `05-02-SUMMARY.md` documented for `beregn_innsats`'s edge case.
- **Fix:** Replaced the test's numeric example with a dyadic-exact case —
  `vurder_kamp(0.5625, 2.00, 2.00, min_value_terskel=0.0625)` — where `0.5`, `0.5625` and
  `0.0625` are all exact binary fractions, so the subtraction is exact by Sterbenz's
  lemma and the boundary invariant (`value == threshold` produces no candidate) is
  actually exercised rather than accidentally passing/failing on rounding noise.
- **Files modified:** `tests/test_backtest.py`
- **Verification:** `backtest.vurder_kamp(0.5625, 2.00, 2.00, min_value_terskel=0.0625) == []`
  passes deterministically; `backtest.vurder_kamp(0.55, 2.00, 2.00)` is documented
  (not asserted empty) as producing one candidate with `value=0.050000000000000044`
- **Committed in:** `c7dc7d7` (Task 1 GREEN commit)

**2. [Rule 1 - Bug] Synthetic 3-month fixture silently spanned a 4th calendar month**
- **Found during:** Task 2, first GREEN verification run
  (`test_retrening_skjer_en_gang_per_maned` expected 3 retrains, got 4)
- **Issue:** `features_df`'s original fixture built 50 consecutive calendar days
  starting from the 1st of each of three target months (Nov/Dec/Jan). Since months have
  28-31 days, `"2023-01-01" + 49 days` lands on `2023-02-19` — silently pulling a 4th
  calendar month into the fixture and breaking the "exactly 3 retrains" assumption both
  the implementation and a second test (`test_modellen_trenes_bare_paa_data_for_datoen`)
  depended on.
- **Fix:** Replaced the three-separate-50-day-runs construction with one contiguous
  `pd.date_range("2022-11-01", "2023-01-31")` (92 rows), which stays inside exactly
  three calendar months by construction. Also hardened
  `test_retrening_skjer_en_gang_per_maned` itself to assert per-month
  `retrent_dato`-uniformity and month-membership rather than comparing against the
  calendar's 1st-of-month date (which the warm-up floor's date-skipping also
  invalidated as an assumption).
- **Files modified:** `tests/test_backtest.py`
- **Verification:** `python3 -m pytest tests/test_backtest.py -q` → `34 passed` (Task 2),
  later `37 passed` after Task 3's additions
- **Committed in:** `2a41411` (Task 2 GREEN commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs in test literals/fixtures
discovered during verification, not in `backtest.py`'s implementation logic)
**Impact on plan:** Both fixes are test-correctness corrections with zero behavioral
change to `backtest.py` itself and zero scope creep. Neither altered any plan
requirement, decision, or the counters the real-archive smoke test reproduces.

## Issues Encountered

None beyond the two auto-fixes documented above. System `python3` still lacks
`pytest`/`xgboost`/`pandas` on this machine (consistent with every prior Phase 5 plan) —
all verification ran via `./venv/bin/python3`.

## User Setup Required

None — no external service configuration required. This plan reads only local files
(`nba_features.csv`, `odds_arkiv.db`, `nba_spillerlogg_raw.csv`) already produced by
earlier plans; it makes no network call and spends no Odds API credits.

## Next Phase Readiness

- Plan 05-08 can call `backtest.klargjor_backtestdata(...)` +
  `backtest.kjor_backtest(...)` to get cached prediction rows, then build the ledger,
  CLV column (via `metrics.beregn_clv` fed directly from each row's four odds fields)
  and `manifest.json` (by copying `resultat` verbatim) without touching the retrain loop
  again
- Plan 05-09's Kelly sweep can call `kjor_backtest` once, cache `prediksjoner`, and
  re-stake them under multiple fraction labels without re-running any model fit
- Plan 05-10 (`08_kjor_backtest.py`) has a stable, tested library surface to import —
  `backtest.py` has no `if __name__` block by design
- Plan 05-11's live-vs-backtest parity test can call `backtest.vurder_kamp` directly and
  compare it row-for-row against `verdi_deteksjon.finn_value_bets`'s decisions
- Plan 05-13's final holdout run has a proven, structurally single entry point
  (`kjor_endelig_holdout_backtest`) ready to call — but the holdout itself remains
  unspent; see "Holdout-status" above
- Full pytest suite green (241 tests); no blockers for Plan 05-08

---
*Phase: 05-walk-forward-backtest-engine*
*Completed: 2026-08-27*

## Self-Check: PASSED

All claimed files found on disk (`backtest.py`, `tests/test_backtest.py`,
`05-VALIDATION.md`, `05-07-SUMMARY.md`) and all five task commit hashes (`705cd0c`,
`c7dc7d7`, `23d473f`, `2a41411`, `5fb4cc3`) verified present in `git log --oneline --all`.
