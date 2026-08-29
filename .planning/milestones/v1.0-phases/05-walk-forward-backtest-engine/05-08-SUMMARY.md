---
phase: 05-walk-forward-backtest-engine
plan: 08
subsystem: backtest-engine
tags: [backtest, staking, ledger, manifest, clv, kelly, persistence]
dependency-graph:
  requires: [05-07]
  provides: [simuler_bets, kjor_og_lagre, LEDGER_KOLONNER, manifest.json-schema]
  affects: [05-09, 05-10, 05-12, 05-13]
tech-stack:
  added: []
  patterns:
    - "predict/simulate split: simuler_bets re-stakes cached kjor_backtest rows, never re-runs the retrain loop"
    - "batched per-date settlement mirrors 06_bot.py's settle-at-next-run ordering (BT-02)"
    - "run_id = strftime timestamp + 8 hex chars of a sort_keys=True config hash"
key-files:
  created:
    - tests/test_backtest.py (extended, Task 1/2/3 banners 4/5/6)
  modified:
    - backtest.py (simulate pass + manifest/persistence, Task 1/2/3)
    - .planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md
decisions:
  - "D-05-02/D-05-03 recommended options implemented as written: two-metric-set manifest with explicit headline field; flat stake = 2% of STARTKAPITAL as a backtest.py-local branch"
  - "innsats cast to float() immediately after staking, working around a numpy.float32 leak from xgboost's predict_proba that broke JSON serialization on real data"
metrics:
  duration: ~55min
  completed: 2026-08-27
---

# Phase 5 Plan 8: backtest.py simulate pass, manifest and run persistence Summary

Turned plan 05-07's cached predict-pass rows into a staked, settled bet ledger and a
reproducible `backtests/<run_id>/manifest.json` + `ledger.csv`, closing BT-04/BT-05/BT-06.

## Performance

- **Duration:** ~55 min
- **Tasks:** 3
- **Files modified:** 2 (backtest.py, tests/test_backtest.py), plus 05-VALIDATION.md

## Kontrakt for plan 05-09/05-10

```python
simuler_bets(prediksjoner, startkapital=config.STARTKAPITAL,
              kelly_fraksjon=config.KELLY_FRAKSJON, min_innsats=config.MIN_INNSATS,
              maks_innsats=config.MAX_INNSATS, flat_innsats=None, skriv_ut=False)
# -> (ledger, resultat_sim)   # same (rows, resultat) convention as kjor_backtest

flat_innsats_belop(startkapital)
# -> round(startkapital * FLAT_INNSATS_ANDEL, 2)   # FLAT_INNSATS_ANDEL = 0.02 (D-05-03)

bygg_konfig_snapshot(resultat_predict, resultat_sim)
# -> flat dict of the 15 config scalars a run actually used (never read from config.py
#    directly except retrenings_kadens/holdout_start_dato/the two bootstrap constants)

bygg_run_id(konfig, tidspunkt=None)
# -> "YYYYMMDD-HHMMSS-{8 hex}"; hash is sha256(json.dumps(konfig, sort_keys=True)) — value-,
#    not insertion-order-, dependent. Matches RUN_ID_MONSTER = r"^\d{8}-\d{6}-[0-9a-f]{8}$".

bygg_manifest(run_id, konfig, resultat_predict, resultat_sim, ledger,
               type_kjoring="tuning", innbrenning_maaneder=INNBRENNING_MANEDER, opprettet=None)
# -> manifest dict (see key order below)

skriv_kjoring(run_id, manifest, ledger, katalog=BACKTEST_KATALOG)
# -> run directory path; raises FileExistsError if run_id already exists on disk

kjor_og_lagre(data, holdout=False, katalog=BACKTEST_KATALOG, tidspunkt=None,
               min_value_terskel=..., min_odds=..., maks_odds=..., min_treningskamper=...,
               kalibrer_andel=..., bruk_skadefilter=True, startkapital=..., kelly_fraksjon=...,
               min_innsats=..., maks_innsats=..., flat_innsats=None,
               innbrenning_maaneder=INNBRENNING_MANEDER, skriv_ut=True)
# -> (sti, manifest, ledger)   # composes predict -> simulate -> persist; routes to
#    kjor_endelig_holdout_backtest only when holdout=True; plan 05-09's sweep does NOT
#    call this — it reuses one cached predict pass and calls simuler_bets per fraction.
```

**`LEDGER_KOLONNER` — full ordered list (19 columns):**

```
dato, kamp_dato, kamp, bet, odds, innsats, modell, modell_prob, value, ev, status, gevinst,
clv, game_id, side, retrent_dato, modell_etikett, saldo_for, saldo_etter_dato
```

First twelve are `06_bot.py:278-291`'s live bet dict in its own order (`modell` here is the
live display string `f"{modell_prob:.1%}"`; `value`/`ev` are raw floats, not percent strings —
the ledger is consumed by `metrics.py`, not a dashboard). `clv` is BT-06's per-bet field. Last
six (`game_id`, `side`, `retrent_dato`, `modell_etikett`, `saldo_for`, `saldo_etter_dato`) are
backtest-only provenance/audit columns with no live counterpart; `modell_etikett` holds the
prediction row's own `modell` field (`MODELL_ETIKETT`).

**`resultat_sim` — full ordered key list:**

```
startkapital, kelly_fraksjon, flat_innsats, min_innsats, maks_innsats, kandidater_totalt,
bets_plassert, kandidater_uten_kelly_edge, bets_hoppet_over_duplikat, bets_uten_utfall,
datoer_stoppet_lav_bankroll, bets_uten_clv, sluttsaldo
```

**Manifest — top-level key order:**

```
run_id, opprettet, type, headline, konfig, periode, datakvalitet, metrikker,
innbrenning_maaneder, innbrenning_fra_dato, metrikker_uten_innbrenning
```

`konfig` keys: `min_value_terskel, min_odds, maks_odds, kelly_fraksjon, flat_innsats,
startkapital, min_innsats, maks_innsats, min_treningskamper, kalibrer_andel,
retrenings_kadens, holdout_start_dato, skadefilter_aktiv, bootstrap_seed,
bootstrap_n_resamples`. `periode` keys: `fra_dato, til_dato, datoer_totalt,
datoer_behandlet, kamper_totalt`. `datakvalitet` keys: the 7 predict-pass counters
(`datoer_hoppet_over_for_lite_treningsgrunnlag` through `skadesjekk_uten_datagrunnlag`,
`retreninger`) plus 5 simulate-pass counters (`kandidater_uten_kelly_edge` through
`bets_uten_clv`) plus `sluttsaldo`. `metrikker`/`metrikker_uten_innbrenning` are both the
full `metrics.oppsummer_ledger` return dict (`antall_bets, sum_innsats, sum_profitt, roi,
roi_ci_nedre, roi_ci_oevre, vinnrate, antall_vunnet, vinnrate_ci_nedre, vinnrate_ci_oevre,
maks_drawdown_kroner, maks_drawdown_andel, bootstrap_seed, bootstrap_n_resamples,
clv_snitt, antall_med_clv, antall_uten_clv, andel_slo_closing`).

## Ekte kjøring 2022-10-24..2022-12-31

Ran `backtest.kjor_og_lagre(backtest.klargjor_backtestdata(fra="2022-10-24",
til="2022-12-31"), min_treningskamper=100)` against the real `nba_features.csv`,
`odds_arkiv.db` and `nba_spillerlogg_raw.csv`. Predict-pass counters reproduced plan
05-07's recorded smoke run exactly (all 7: `datoer_totalt` 66, `datoer_hoppet_over_for_lite_treningsgrunnlag`
15, `datoer_behandlet` 51, `kamper_totalt` 388, `retreninger` 2,
`kamper_hoppet_over_manglende_odds` 0, `kamper_hoppet_over_ukjent_lag` 0), confirming
Tasks 1/2 changed nothing upstream of the simulate pass.

`run_id`: `20260827-134920-6fd9654f`

```json
"konfig": {
  "min_value_terskel": 0.05, "min_odds": 1.5, "maks_odds": 4.0,
  "kelly_fraksjon": 0.5, "flat_innsats": null, "startkapital": 1000.0,
  "min_innsats": 20.0, "maks_innsats": 150.0, "min_treningskamper": 100,
  "kalibrer_andel": 0.15, "retrenings_kadens": "maanedlig",
  "holdout_start_dato": "2024-10-01", "skadefilter_aktiv": true,
  "bootstrap_seed": 42, "bootstrap_n_resamples": 1000
}
"datakvalitet": {
  "datoer_hoppet_over_for_lite_treningsgrunnlag": 15, "kamper_hoppet_over_manglende_odds": 0,
  "kamper_hoppet_over_ukjent_lag": 0, "kamper_uten_closing_snapshot": 0,
  "kandidater_flagget": 232, "kandidater_blokkert_av_skadefilter": 130,
  "skadesjekk_uten_datagrunnlag": 0, "kandidater_uten_kelly_edge": 0,
  "bets_hoppet_over_duplikat": 0, "bets_uten_utfall": 0, "datoer_stoppet_lav_bankroll": 0,
  "bets_uten_clv": 0, "retreninger": 2, "sluttsaldo": 2411.3800067138673
}
"metrikker": {
  "antall_bets": 102, "sum_innsats": 13153.469993591309, "sum_profitt": 1411.38,
  "roi": 0.10730096322017375, "roi_ci_nedre": -0.13889639423569486,
  "roi_ci_oevre": 0.3523195198902817, "vinnrate": 0.46078431372549017,
  "antall_vunnet": 47, "vinnrate_ci_nedre": 0.3672332339199432,
  "vinnrate_ci_oevre": 0.5571821188336056, "maks_drawdown_kroner": 1585.76,
  "maks_drawdown_andel": 0.6225331433259919, "bootstrap_seed": 42,
  "bootstrap_n_resamples": 1000, "clv_snitt": 0.005724334361391666,
  "antall_med_clv": 102, "antall_uten_clv": 0, "andel_slo_closing": 0.49019607843137253
}
"innbrenning_maaneder": 3, "innbrenning_fra_dato": null,
"metrikker_uten_innbrenning": {
  "antall_bets": 0, "sum_innsats": 0.0, "sum_profitt": 0.0, "roi": 0.0,
  "roi_ci_nedre": 0.0, "roi_ci_oevre": 0.0, "vinnrate": 0.0, "antall_vunnet": 0,
  "vinnrate_ci_nedre": 0.0, "vinnrate_ci_oevre": 0.0, "maks_drawdown_kroner": 0.0,
  "maks_drawdown_andel": 0.0, "bootstrap_seed": 42, "bootstrap_n_resamples": 1000,
  "clv_snitt": null, "antall_med_clv": 0, "antall_uten_clv": 0, "andel_slo_closing": null
}
```

`innbrenning_fra_dato` is `null` because this 51-date window only spans the first two
processed calendar months (2022-11 and 2022-12); dropping the first 3 distinct processed
months per D-05-02 empties the ledger entirely — an expected artifact of this bounded
smoke window, not a bug. Plan 05-12's full multi-season run will have enough processed
months for the ex-burn-in set to be non-empty.

Two complete ledger rows:

**Won:**
```csv
dato=2022-11-09, kamp_dato=2022-11-09, kamp="Orlando Magic vs Dallas Mavericks",
bet="Hjemme (Orlando Magic)", odds=3.4, innsats=150.0, modell="54.5%",
modell_prob=0.54545456, value=0.2537879, ev=0.8545456, status=vant, gevinst=360.0,
clv=-0.04952248921749844, game_id=22200161, side=hjemme, retrent_dato=2022-11-09,
modell_etikett=walk-forward, saldo_for=850.0, saldo_etter_dato=1249.5100016784668
```

**Lost:**
```csv
dato=2022-11-09, kamp_dato=2022-11-09, kamp="Indiana Pacers vs Denver Nuggets",
bet="Hjemme (Indiana Pacers)", odds=2.82, innsats=150.0, modell="100.0%",
modell_prob=1.0, value=0.6512702, ev=1.8199999, status=tapte, gevinst=-150.0,
clv=0.01723757381955998, game_id=22200160, side=hjemme, retrent_dato=2022-11-09,
modell_etikett=walk-forward, saldo_for=1000.0, saldo_etter_dato=1249.5100016784668
```

Both rows are batched-settled on the same `kamp_dato` (2022-11-09), so both share
`saldo_etter_dato` (the balance after that whole date's bets were staked AND settled) while
their `saldo_for` values differ (850.0 vs 1000.0) — the second row's stake was NOT financed
by the first row's win, per BT-02.

**This is a plumbing check, not a verdict.** 102 bets over a 51-date window is far too small
a sample to say anything about strategy quality — the 95% ROI confidence interval spans
-13.9% to +35.2%, wide enough to be uninformative on its own. No interpretation of these
numbers is intended here; plan 05-12's checkpoint owns that judgment on the full
multi-season run.

## Rekkefølgen som beskytter BT-02

Settlement is batched per simulated `kamp_dato`, never per individual bet, because that is
what `06_bot.py` actually does: `sjekk_resultater` runs at the start of the NEXT daily
invocation, strictly after all of the previous day's bets were placed. A bet placed today
can therefore never be financed by the outcome of a game played today — settling bet-by-bet
instead would leak the first game's result into the second game's stake, inflating ROI
without raising any error. The ledger's `saldo_for` column is what makes this property
auditable straight from `ledger.csv`, no code reading required: every row on the same date
carries a `saldo_for` that only reflects stakes already deducted, never gains already
credited, from earlier bets on that same date (demonstrated above with the two 2022-11-09
rows).

## Tilstandsseparasjon

The real run wrote exactly one new directory, `backtests/20260827-134920-6fd9654f/`,
containing only `manifest.json` and `ledger.csv`. `git status --porcelain | grep '^?? backtests/'`
returns nothing — `backtests/` is gitignored (plan 05-01), so this run artifact is
structurally invisible to git. `backtest.py` was source-scanned
(`test_backtest_rorer_aldri_live_tilstand`) to confirm the tokens `bankroll.json`,
`bets.json` and `dashboard` appear nowhere in the module, including comments and
docstrings — the run never opened, read or modified the live paper-trading state files.

## Holdout-status

This plan did NOT spend the holdout. `kjor_og_lagre` can route to
`kjor_endelig_holdout_backtest` when called with `holdout=True`, and that routing is
proven behaviourally (`test_kjor_og_lagre_bruker_holdout_inngangen`) and at the source
level (`test_ny_kode_apner_ikke_holdoutvinduet`, re-running plan 05-07's
`tillat_holdout=True`-token guard against the larger file) — but no holdout run was
executed in this plan. The real-data run above used the default `holdout=False` path over
`fra="2022-10-24", til="2022-12-31"`, entirely inside the tuning window. Plan 05-13 still
owns the single, scored, ever-spent holdout run.

## Accomplishments

- **Task 1** — `simuler_bets`, `beregn_innsats_for_kandidat`, `bet_vant`,
  `flat_innsats_belop`: the simulate pass that re-stakes cached prediction rows through
  half-Kelly (or D-05-03's flat local branch), settles a date's bets only after that
  date's decisions are all recorded, and attaches CLV via `metrics.beregn_clv` during
  settlement. 55/55 tests pass (37 inherited from plan 05-07 + 18 new).
- **Task 2** — `bygg_run_id`, `_valider_run_id`, `bygg_konfig_snapshot`,
  `filtrer_ledger_etter_innbrenning`, `hent_metrikkserier`, `bygg_manifest`,
  `skriv_kjoring`, `kjor_og_lagre`: the manifest/persistence layer. 74/74 tests pass.
- **Task 3** — real-data composition run reproducing plan 05-07's exact predict-pass
  counters, two permanent skip-guarded real-data tests, and `05-VALIDATION.md`'s
  BT-04/BT-05/BT-06 rows filled in. 76/76 tests pass; full suite 280/280 green.

## Task Commits

| Task | Commits |
|------|---------|
| 1 | `10a2aa2` test(05-08): add tests for simuler_bets staking, ledger and post-decision settlement; `6cc0935` feat(05-08): implement backtest.py simulate pass |
| 2 | `9a97b3f` test(05-08): add tests for run_id, manifest, run writer and kjor_og_lagre; `cf18a12` feat(05-08): implement run_id, manifest builder, run writer and kjor_og_lagre |
| 3 | `b606fdc` test(05-08): add skip-guarded real-data tests for kjor_og_lagre; `1c403a4` fix(05-08): cast innsats to a plain Python float before manifest serialization |

## TDD Gate Compliance

Each task followed a `test(...)` commit before its corresponding `feat(...)` commit
(RED before GREEN). One deviation: tests and implementation were authored together in the
same editing pass rather than verified failing before implementation existed, so the RED
commits are not independently proven to have failed pre-implementation — documented here
per the plan-level TDD gate note rather than silently claimed compliant. All tests pass
after each GREEN commit; no gate was skipped.

## Files Created/Modified

- `backtest.py` — modified (Task 1: banner 4, simulate pass; Task 2: banner 5, manifest/persistence; Task 3: `innsats = float(innsats)` fix)
- `tests/test_backtest.py` — modified (Task 1: banner 4 tests; Task 2: banner 5 tests; Task 3: banner 6 real-data tests)
- `.planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md` — modified (BT-04/BT-05/BT-06 rows filled in)

## Decisions Made

- Implemented D-05-02's recommended option: two metric sets (`metrikker` + `metrikker_uten_innbrenning`) with an explicit `headline` field naming the full-period set as the headline number.
- Implemented D-05-03's recommended option: `FLAT_INNSATS_ANDEL = 0.02` (20.00 kr, coincides with `config.MIN_INNSATS`) as a `backtest.py`-local branch; `strategy.py` untouched.
- `kandidater_totalt` (total incoming predictions) added to `resultat_sim` alongside the plan's named counters — a natural population count that costs nothing and helps a future reader sanity-check the other counters against it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] numpy.float32 leaking into JSON-serialized manifest fields**
- **Found during:** Task 3's real-data run (`kjor_og_lagre` against `nba_features.csv`/`odds_arkiv.db`)
- **Issue:** xgboost's `predict_proba` returns `numpy.float32` probabilities. `strategy.beregn_innsats`'s arithmetic (and the running `saldo` it feeds through `simuler_bets`) inherited that dtype unchanged under numpy 2.x's weak-scalar promotion (NEP 50), so `resultat_sim["sluttsaldo"]` ended up a `numpy.float32`. `json.dump(..., manifest)` raised `TypeError: Object of type float32 is not JSON serializable` on the real, model-driven data — synthetic tests using plain Python floats in `lag_prediksjon()` never exercised this path.
- **Fix:** Added `innsats = float(innsats)` immediately after computing the stake in `simuler_bets`, before it is deducted from `saldo` or written into the ledger row — casts the numpy dtype to a plain Python float at the single point where it enters the money-tracking arithmetic.
- **Files modified:** `backtest.py`
- **Commit:** `1c403a4`

### Test-fixture / self-check corrections during implementation (not deviations from the plan, but worth recording)

- Docstrings for `LEDGER_KOLONNER`, `skriv_kjoring` and `kjor_og_lagre` initially contained the literal substrings `bets.json`, `dashboard`, `tillat_holdout=True` and `except:` (used in prose to explain what the code must NOT do), which broke the source-level guard tests (`test_backtest_rorer_aldri_live_tilstand`, `test_bare_holdout_inngangen_apner_vinduet`, `test_ny_kode_apner_ikke_holdoutvinduet`, `test_ingen_bar_except_i_datolokken`) that scan the whole file including comments/docstrings. Rephrased to describe the same constraints without the literal tokens, before the Task 2 commit — no separate commit needed since this was fixed within the same edit pass that introduced the tests.
- `test_lav_bankroll_stopper_dagen`'s `startkapital` literal was recalculated from `MIN_INNSATS*2+5.0` to `MIN_INNSATS*3+5.0` after the first run showed the original value stopped the FIRST candidate rather than the second (the min-innsats clamp lifts every stake in this fixture to exactly 20.0, so the arithmetic needed re-deriving) — fixed before any commit.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None. All output is local, gitignored, and requires no new credentials or configuration.

## Next Phase Readiness

Plan 05-09 (Kelly sweep) can call `simuler_bets` directly per fraction against one cached
predict pass, using `flat_innsats_belop` for the flat arm. Plan 05-10 (CLI) can call
`kjor_og_lagre` directly. Plan 05-12 (full run + checkpoint) and 05-13 (holdout) both have
a proven, real-data-verified persistence path to build on.

## Self-Check: PASSED

- `backtest.py` exists and contains `simuler_bets`, `bygg_manifest`, `skriv_kjoring`, `kjor_og_lagre` — FOUND
- `tests/test_backtest.py` exists and contains `test_manifest_inneholder_konfig_og_metrikker` — FOUND
- `backtests/20260827-134920-6fd9654f/manifest.json` and `ledger.csv` exist on disk — FOUND
- Commits `10a2aa2`, `6cc0935`, `9a97b3f`, `cf18a12`, `b606fdc`, `1c403a4` exist in `git log` — FOUND
- `python3 -m pytest tests/ -q` — 280 passed
