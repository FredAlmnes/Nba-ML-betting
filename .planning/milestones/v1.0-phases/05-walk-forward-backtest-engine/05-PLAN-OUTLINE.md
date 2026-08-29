---
phase: 05
slug: walk-forward-backtest-engine
type: plan-outline
created: 2026-08-24
plan_count: 13
wave_count: 10
requirements: [BT-01, BT-02, BT-03, BT-04, BT-05, BT-06, BT-07]
---

# Phase 5 — Plan Outline

Build order derived from `05-RESEARCH.md` (Patterns 1–7, Pitfalls 1–6, Wave 0 test gaps),
`05-CONTEXT.md` (locked decisions + Post-Research Resolution), and `05-PATTERNS.md`
(file classification / closest analogs). Deliberately **not** compressed into a few large
plans — research explicitly warns that the correctness plumbing (odds join, as-of injury
filter, holdout guard, CI math) is the cost driver in this phase, not compute.

## Plans

| Plan ID | Objective | Wave | Depends On | Requirements |
|---------|-----------|------|------------|--------------|
| 05-01 | Pre-flight safety gate + holdout constant: blocking `checkpoint:decision` on the exact `HOLDOUT_START_DATO` value (research A1 recommends `"2024-10-01"`), the burn-in/early-months reporting policy (Open Q3 — include all months, report headline metrics both full-period and excluding first 2-3 months), and the "flat" stake definition for the BT-07 sweep (Pitfall 6 — `backtest.py`-local branch, never a `strategy.py` change); working-tree/scratch-artifact disposition confirmed unchanged (D-08 ignore-only); then add `HOLDOUT_START_DATO` to `config.py` and `backtests/` + `nba_spillerlogg_raw.csv` to `.gitignore` | 1 | — | BT-03 |
| 05-02 | `model.py` (new): extract train/calibrate/persist/load out of `03_tren_modell.py` into one `as_of`-aware module reusing `modell_utils.KalibrertModell` and Phase 3's disjoint-slice discipline — `as_of=None` → 3-way train/calibrate/test (one-shot), `as_of=<dato>` → 2-way expanding-window train/calibrate with fraction-based `kalibrer_andel` (Pattern 3, A5); rewire `03_tren_modell.py` to call it with byte-comparable output; `tests/test_model.py` | 2 | 05-01 | BT-01, BT-02 |
| 05-03 | `metrics.py` (new): pure, zero-I/O reporting layer — ROI, win rate, max drawdown over a bet ledger, `bootstrap_roi_ci` (1,000 resamples, seeded, resamples **bets** not games/dates), `wilson_ci` (hardcoded z=1.96, no new `scipy` dependency), and the per-bet + aggregate CLV function built on `strategy.fjern_vigorish` (never a second vig implementation); `tests/test_metrics.py` against hand-calculated synthetic values | 2 | 05-01 | BT-04, BT-06 |
| 05-04 | `odds.py` (modified): add parameterized best-price-per-outcome archive helpers — `hent_bet_time_pris()` and a closing-snapshot counterpart for CLV — using `MAX(odds) GROUP BY utfall_navn` on `(kamp_dato, hjemme_lag_id, borte_lag_id)`, returning `(None, None)` on a missing snapshot so callers skip rather than error (Pitfall 2); rewire `verdi_deteksjon.py`'s inline `beste_hjemme_odds`/`beste_borte_odds` reduction onto the shared helper so live and backtest can never diverge on price selection (A3, CORE-04 parity); extend `tests/test_odds.py` | 3 | 05-02, 05-03 | BT-01, BT-02, BT-06 |
| 05-05 | `spillerlogg.py` (new) + `nba_spillerlogg_raw.csv`: closes the Pitfall 1 data gap that `05-CONTEXT.md`'s Post-Research Resolution put in scope — fetch player-game logs for 2022-23/2023-24/2024-25 via `nba_api.leaguegamelog.LeagueGameLog(player_or_team_abbreviation='P', ...)` (3 free calls, no Odds API credits), same season-loop-to-CSV shape as `01_hent_data.py`, with `time.sleep()` rate-limit spacing and skip-and-log on failure; `tests/test_spillerlogg.py` (no network — schema/parse assertions on an injected fixture) | 3 | 05-02, 05-03 | BT-01, BT-02 |
| 05-06 | `skadefilter.py` (modified): add `sesong_grenser_for_dato()` (date-driven, parameterized — the actual as-of fix replacing `datetime.now()`-driven `gjeldende_sesong()`) and `sjekk_lag_helse_som_of(spillerlogg_df, team_id, lagnavn, as_of_dato)` mirroring the live `MIN_MINUTTER`/`ANTALL_TOPPSPILLERE`/`sjekk_spiller` thresholds but reading only rows with `GAME_DATE < as_of` inside the as-of season (Pattern 7); extend `tests/test_skadefilter.py` with injected synthetic player-log fixtures, including a negative-control proving post-`as_of` rows never influence the verdict | 4 | 05-05 | BT-01, BT-02 |
| 05-07 | `backtest.py` (new) — predict pass + holdout guard: `HoldoutLaastFeil`, `_sikre_ikke_holdout()` and the `kjor_backtest(..., tillat_holdout=False)` / `kjor_endelig_holdout_backtest()` split (Pattern 4, structural not conventional); the walk-forward date loop over `odds.hent_unike_kampdatoer()` with month-change-triggered retrain (Pitfall 5 anchor: compare against the previous *processed* date's month), precompute-once/filter-many feature table (Pattern 1), per-game model score → odds join → value/EV → injury check, emitting cached prediction rows plus explicit skip counters for missing odds; `tests/test_backtest.py` (loop produces rows, guard raises, no feature recomputation in the loop) | 5 | 05-04, 05-06 | BT-01, BT-02, BT-03 |
| 05-08 | `backtest.py` (modified) — simulate pass + run persistence: apply `strategy.beregn_innsats` (and the locked flat-stake branch) to cached predictions, build the ledger row shape parallel to `06_bot.py`'s live bet dict plus a `clv` column, settle each bet only after its decision is recorded, then write `backtests/<run_id>/` with timestamp+config-hash `run_id`, `manifest.json` (config snapshot, date range, bootstrap seed, ROI/win-rate/max-drawdown/bet-count/CI, missing-odds skip count, `skadefilter_aktiv`) and `ledger.csv`; extend `tests/test_backtest.py` for manifest round-trip and `run_id` uniqueness | 6 | 05-07 | BT-04, BT-05, BT-06 |
| 05-09 | Kelly-fraction sensitivity sweep (BT-07): run the predict pass exactly once and re-simulate only staking at flat / quarter / half / full against the cached rows (Pattern 6 — never re-run the walk-forward retrain per fraction), writing `backtests/<run_id>/kelly_sweep.json` with ROI, max drawdown and bet count per fraction; sweep is structurally confined to the train/calibrate slice and must raise `HoldoutLaastFeil` if pointed past `HOLDOUT_START_DATO`; `tests/test_backtest.py::test_kelly_sweep_bruker_cachet_prediksjoner` | 7 | 05-08 | BT-07 |
| 05-10 | `08_kjor_backtest.py` (new): thin `argparse` CLI in the `07_hent_historisk_odds.py` mould — ISO-date validation on range args (V5), train/calibrate slice as the default action, Kelly sweep behind an explicit flag, and the locked holdout reachable **only** via a separately-named `--holdout` path that calls `kjor_endelig_holdout_backtest()` and never runs by default; update `KOMME_I_GANG.md` with the new step 08 and the holdout-is-spent-once warning | 8 | 05-09 | BT-01, BT-03, BT-05, BT-07 |
| 05-11 | Extend `tests/test_parity.py` per the instruction written into its own module docstring in Phase 2 (`02-06-SUMMARY.md` "Findings for Phase 5"): the live-vs-backtest side-by-side assertion that both paths produce an identical bet decision for the same historical date/game, now buildable because `backtest.py` exists — plus a full-suite gate run (`python3 -m pytest tests/ -q`, 129 existing + all new tests green) | 8 | 05-09 | BT-02 |
| 05-12 | Freeze-the-decisions run: execute the full walk-forward backtest end-to-end on the train/calibrate slice only (2022-23 + 2023-24) with the Kelly sweep, then a blocking `checkpoint:human-verify` on statistical plausibility (sane bet count vs. the ~190-360 estimate, ROI in a plausible range, CI width honest for the sample size, skip counts visible) and on explicitly freezing every threshold/Kelly decision before the holdout may be touched; record the frozen config + results in a phase artifact and fill in `05-VALIDATION.md`'s task/wave columns | 9 | 05-10, 05-11 | BT-01, BT-04, BT-05, BT-07 |
| 05-13 | Spend the locked holdout exactly once: blocking `checkpoint:human-verify` confirming no prior holdout run exists and that 05-12's freeze is final (this is irreversible for the milestone), then a single `kjor_endelig_holdout_backtest()` run over 2024-25 producing its own `backtests/<run_id>/` manifest; record the holdout `run_id` + date in `STATE.md` so future sessions know the holdout is spent, mark BT-01…BT-07 complete in `REQUIREMENTS.md`/`ROADMAP.md`, and write the before/after comparison against the current losing live configuration | 10 | 05-12 | BT-03, BT-05 |

## Requirement Coverage

| Requirement | Covered By |
|-------------|------------|
| BT-01 | 05-02, 05-04, 05-05, 05-06, 05-07, 05-10, 05-12 |
| BT-02 | 05-02, 05-04, 05-05, 05-06, 05-07, 05-11 |
| BT-03 | 05-01, 05-07, 05-10, 05-13 |
| BT-04 | 05-03, 05-08, 05-12 |
| BT-05 | 05-08, 05-10, 05-12, 05-13 |
| BT-06 | 05-03, 05-04, 05-08 |
| BT-07 | 05-09, 05-10, 05-12 |

No requirement is unplanned; no plan has an empty requirement set.

## Wave Structure & File Ownership

| Wave | Plans | Parallel? | File-ownership note |
|------|-------|-----------|---------------------|
| 1 | 05-01 | — | Checkpoints + `config.py`, `.gitignore` |
| 2 | 05-02, 05-03 | yes | `model.py`/`03_tren_modell.py`/`tests/test_model.py` vs `metrics.py`/`tests/test_metrics.py` — disjoint |
| 3 | 05-04, 05-05 | yes | `odds.py`/`verdi_deteksjon.py`/`tests/test_odds.py` vs `spillerlogg.py`/`tests/test_spillerlogg.py` — disjoint |
| 4 | 05-06 | — | `skadefilter.py`, `tests/test_skadefilter.py` |
| 5 | 05-07 | — | `backtest.py`, `tests/test_backtest.py` |
| 6 | 05-08 | — | `backtest.py`, `tests/test_backtest.py` (same files as 05-07 → forced later wave) |
| 7 | 05-09 | — | `backtest.py`, `tests/test_backtest.py` (same files → forced later wave) |
| 8 | 05-10, 05-11 | yes | `08_kjor_backtest.py`/`KOMME_I_GANG.md` vs `tests/test_parity.py` — disjoint |
| 9 | 05-12 | — | Run artifacts + `05-VALIDATION.md` |
| 10 | 05-13 | — | Run artifacts + `STATE.md`/`REQUIREMENTS.md`/`ROADMAP.md` |

Waves 5-7 are strictly sequential purely on `backtest.py` file ownership, not on
conceptual dependency alone.

## Notes for Per-Plan Planning

- **No new packages.** Every capability needed is already installed (`pandas`, `numpy`,
  `xgboost`, `scikit-learn`, `sqlite3`). `scipy` is present transitively but is NOT in
  `requirements.txt` — the Wilson z-score stays a hardcoded constant (05-03). No Package
  Legitimacy Gate applies this phase.
- **No Odds API credits are spent anywhere in this phase.** The engine reads only the
  already-archived `odds_arkiv.db`. The single network dependency is free `nba_api`
  (05-05).
- **Norwegian snake_case, no type hints, numbered `# --- N. ... ---` banners,
  `if __name__ == "__main__":` guards** apply to every new module per CLAUDE.md and
  `05-PATTERNS.md` Shared Patterns.
- **Never change live `MIN_VALUE_TERSKEL`/`MAX_ODDS`/`KELLY_FRAKSJON` values in
  `config.py`** — deferred per `05-CONTEXT.md`; this phase only adds
  `HOLDOUT_START_DATO` and produces the evidence for a later decision.
- **Known accepted data-quality boundaries to surface in the manifest, not investigate as
  bugs:** thinner eu-region bookmaker coverage in early 2022-23 (Pitfall 3) and the 2
  closing-line gap games from the 04-09 archive (Pitfall 2).

---
*Phase: 5-Walk-Forward Backtest Engine*
*Outline created: 2026-08-24*
