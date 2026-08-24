# Phase 5: Walk-Forward Backtest Engine - Research

**Researched:** 2026-08-24
**Domain:** Walk-forward backtest engine for an NBA moneyline value-betting pipeline (Python/pandas/XGBoost, SQLite historical-odds archive)
**Confidence:** HIGH (almost every claim below is verified directly against this repo's actual code and data — `features.py`, `strategy.py`, `odds.py`, `odds_arkiv.db`, `nba_features.csv`, `03_tren_modell.py`, `skadefilter.py` — and against a live timing benchmark and a live `nba_api` call run during this research session, not just training-data recall)

## Summary

The engine this phase builds is simpler than it first looks, because of one fact confirmed by reading `features.py` directly: `beregn_lag_form`'s rolling-window features are computed per-team via `groupby("TEAM_ID")...shift(1).rolling(window=10, min_periods=3)`, sorted by that team's own game date. A row's feature value therefore depends only on **that team's own prior games**, never on rows appended later in the DataFrame — appending future games never changes a past game's `RULL_*`/`DIFF_*` values. This means the entire feature table only needs to be built **once** (either reuse the existing `nba_features.csv`, or rebuild it via `beregn_lag_form(df_raw)` with `as_of=None`), and the walk-forward loop's ~30 monthly retrain points then just **filter that one precomputed table by date** (`GAME_DATE_HJEMME < cutoff` for training, `== as_of_date` for scoring) — no per-retrain-point feature recomputation, no quadratic blow-up, and no new caching layer to build. A live timing test in this session confirmed a full XGBoost + isotonic-calibration fit on ~2,500 rows takes **~0.4 seconds**; 30 monthly retrains cost well under a minute total. The real cost driver in this phase is not compute, it's correctness plumbing: joining `odds_arkiv.db` snapshots to games, and making the injury filter as-of-aware.

The odds join is straightforward and has a precedent to copy exactly: `verdi_deteksjon.py`'s live path already resolves "one price per outcome" from a bookmaker-multiplicity odds payload by taking the **highest (best) price across all bookmakers per outcome** (`beste_hjemme_odds`/`beste_borte_odds`, lines 141–156). `odds_arkiv.db`'s `bet_time`/`closing` rows have the identical shape (one row per bookmaker × outcome), so the backtest should apply the exact same "best price across bookmakers" reduction — this is both the simplest correct choice and the one that keeps CORE-04 parity between live and backtest intact. Missing snapshots (2 known closing-line gap games from the 04-09 archive, plus any date with zero rows) should be skipped, not errored, matching the project's existing "skip-and-log" convention (`04_value_detector.py`/`06_bot.py`'s pattern for unresolvable team names).

**The single biggest risk in this phase is the injury filter, and CONTEXT.md's premise about it needs correction.** `05_skadefilter.py`/`skadefilter.py` derives "is a key player missing" from `nba_api`'s `leaguedashplayerstats` endpoint — a **player-level, live-only** query. Neither `nba_kamper_raw.csv` nor `nba_features.csv` contains any player-level columns (verified directly: both are team-level box scores only — `PLAYER_ID`, `PLAYER_NAME`, per-player `MIN` do not exist in either file). CONTEXT.md's Integration Points section assumes the as-of adaptation can be done "using historical box-score data already in `nba_kamper_raw.csv`/`nba_features.csv`" — that data does not exist there. This research verified a concrete, cheap fix: `nba_api`'s `leaguegamelog.LeagueGameLog(player_or_team_abbreviation='P', season=<season>)` returns one row per player per game for an entire season in a single call (verified live in this session: 25,895 rows for the 2022-23 season alone, with numeric `MIN`, `PLAYER_ID`, `TEAM_ID`, `GAME_DATE`) — exactly the same call pattern `01_hent_data.py` already uses for team-level data, just with `player_or_team_abbreviation='P'` instead of the team-level `LeagueGameFinder`. Building a new `nba_spillerlogg_raw.csv` (3 season-level calls, free, no Odds API credits, no rate-limit risk) is the recommended path to make the injury filter genuinely backtestable. The documented fallback — if this new data-acquisition step is descoped — is to run the walk-forward loop with the injury filter disabled (treat every bet as injury-filter-OK) and explicitly flag in the run manifest that reported ROI excludes injury-filter dampening, since that is a real, known optimistic bias versus what the live bot would have done.

**Primary recommendation:** Build `backtest.py` as a two-pass engine (predict pass: walk-forward retrain + score + odds-join + injury-check, cached; simulate pass: apply `strategy.beregn_innsats` at each Kelly fraction against the cached predictions) operating on a features table built exactly once via `features.beregn_lag_form`, retrain `model.py`'s `KalibrertModell` monthly via simple boolean date-mask filtering (no recomputation), reuse `strategy.py`/`teams.py`/`odds.py` unmodified, and treat the injury-filter as-of adaptation as requiring a new (small, free, one-time) player-game-log data acquisition step rather than an in-place code change against data that doesn't exist yet.

## Architectural Responsibility Map

This is a single-process, offline CLI tool (no web/service tiers apply). Mapping capabilities to conceptual layers instead:

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Feature computation (rolling team form) | Data/Feature layer (`features.py`) | — | Already exists, already leakage-safe, already as-of-aware; backtest only needs to call it once and filter, not extend it |
| Model train/calibrate | Model layer (new `model.py`) | Data/Feature layer | Consumes the precomputed features table; owns the `KalibrertModell` fit/calibrate lifecycle for both one-shot and walk-forward callers |
| Odds snapshot join & price selection | Data layer (`odds.py` + new backtest-side join helper) | Strategy layer (`strategy.fjern_vigorish`) | `odds.py` already owns the SQLite archive; the "select best price per outcome" reduction currently lives inline in `verdi_deteksjon.py` and should be extracted so both live and backtest call one function (closes a duplication risk before it starts) |
| Injury-availability decision | Data layer (new as-of player-log module/function) | Strategy/filter layer (`skadefilter.py`) | Needs a new historical data source (player game log); the pass/fail decision logic itself is a light adaptation of `skadefilter.py`'s existing `sjekk_spiller`/`hent_toppspillere_for_lag` |
| Value/EV/Kelly decision | Strategy layer (`strategy.py`) | — | Already shared, pure, zero I/O — reuse unmodified, no changes needed |
| Walk-forward orchestration (retrain cadence, date loop, holdout guard) | Backtest orchestration layer (new `backtest.py`) | Model/Data layers (calls into them) | New code this phase writes; owns date iteration, calls `model.py`/`odds.py`/`strategy.py`/injury module in sequence per date |
| Metrics (ROI/drawdown/CLV/CI) | Reporting layer (new `metrics.py`) | — | Pure functions over a completed ledger — no I/O, unit-testable in isolation |
| Run manifest / ledger persistence | Storage layer (`backtests/<run_id>/`) | — | Flat files (JSON/CSV), gitignored, structurally separate from `bankroll.json`/`bets.json` per the locked decision |

## Project Constraints (from CLAUDE.md)

- Norwegian identifiers/comments throughout — all new code (`backtest.py`, `metrics.py`, `model.py`, `08_kjor_backtest.py`) must follow this; no type hints anywhere in the codebase, none should be introduced.
- No linter/formatter config exists — match existing hand-maintained style, numbered `# --- N. ... ---` section-comment banners, docstrings explaining *why* not *what*.
- No test framework existed until Phase 2 introduced `pytest` — it is now the established framework (`pytest.ini` present, 129 tests collected as of this research). New backtest code should get `pytest` coverage following the same fixture-based, no-network pattern as `tests/conftest.py`.
- No `.env`/secrets handling changes needed this phase — the backtest reads the already-archived `odds_arkiv.db` and does not need `ODDS_API_NOKKEL` at all for its core loop (only the optional new player-log fetch needs `nba_api`, which requires no key).
- Flat, numbered scripts at repo root (`0N_verb_ting.py`) remain the entry-point convention; `08_kjor_backtest.py` follows this.
- Moneyline-only scope (v1) — nothing in this phase should introduce spread/totals handling.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Package & Module Structure**
- Backtest code lives as flat modules at repo root — `backtest.py` (walk-forward loop) and `metrics.py` (ROI/drawdown/CLV/CI), matching the existing `features.py`/`strategy.py`/`teams.py`/`odds.py`/`config.py` pattern established in Phases 2 and 4. The full `nba_betting/` package sketched in early research is explicitly NOT adopted this phase — D-08 (Phase 4) left this undecided and nothing in BT-01–07 requires the restructure.
- A new numbered entry script, `08_kjor_backtest.py`, matches the existing `0N_verb_ting.py` convention (01–07 already exist) and calls `backtest.py`'s functions — mirrors the importable-function-plus-`if __name__` pattern established in Phase 4's D-05.
- Model training/retraining logic is extracted into a new shared `model.py` module (train/calibrate/persist/load, `as_of`-aware), reusing the existing `modell_utils.KalibrertModell` wrapper, so both `03_tren_modell.py` (one-shot) and the backtest's walk-forward retrain loop call the same function — closes the last duplicated-logic gap the research flagged (Anti-Pattern 2).
- Backtest run outputs (manifests, ledgers) go in a new gitignored `backtests/` directory at repo root, one subfolder per run — kept structurally separate from `bankroll.json`/`bets.json` so simulated backtest state can never mix with or be mistaken for real paper-trading history.

**Walk-Forward Retraining & Holdout Definition**
- Retraining cadence is monthly: the model is refit at the start of each simulated calendar month using only data strictly before that date. Avoids ~30x the model fits of daily retraining for negligible accuracy gain at this data volume (3,638 games).
- Training window is expanding (all data from 2022-10-24 up to the retrain cutoff), not rolling — the total data volume (~2.5 seasons) is modest enough that discarding older games via a rolling window would needlessly throw away signal.
- The locked final holdout is the full 2024-25 season (2024-10 through 2025-04-13, the most recent complete season in the archived data). All threshold/parameter/Kelly-fraction decisions are tuned only on 2022-23 + 2023-24 data; the 2024-25 slice is checked exactly once, after those decisions are frozen — satisfies BT-03.
- The holdout lock is enforced in code, not just convention: a `HOLDOUT_START_DATO` constant in `config.py`, plus a structural guard so the tuning/sweep code path raises if asked to evaluate dates on or after that constant. Only a separate, explicit "final holdout run" entry point may read past it. BT-03 explicitly requires enforcement "by the code, not just convention."

**Run Manifest & Reporting Output**
- Each run writes `backtests/<run_id>/manifest.json` containing: the config snapshot (thresholds, odds range, Kelly fraction, retrain cadence), date range, and headline metrics (ROI, win rate, max drawdown, bet count, confidence interval).
- Each run also writes `backtests/<run_id>/ledger.csv`, one row per simulated bet — CSV rather than JSON since backtest ledgers are write-once/read-many per run.
- Confidence intervals: bootstrap resampling (1,000 resamples) of the bet ledger for the ROI CI; Wilson score interval for the win-rate CI.
- `run_id` is timestamp-based (`YYYYMMDD-HHMMSS`) with a short config-hash suffix, so runs sort chronologically and identical-config reruns remain distinguishable.

**CLV & Kelly Sweep Mechanics**
- CLV per bet is computed as the vig-free implied probability at the bet-time snapshot minus the vig-free implied probability at the closing snapshot, reusing `strategy.fjern_vigorish()` on both.
- The Kelly-fraction sweep (flat/quarter/half/full, BT-07) is split into a predict pass (walk-forward model scoring + odds/injury filtering, run once and cached) and a simulate pass (re-running `strategy.beregn_innsats` at each Kelly fraction against the cached predictions).
- The sweep runs only on the train/calibrate slice (2022-23 + 2023-24) — never on the locked holdout.
- Sweep output is `backtests/<run_id>/kelly_sweep.json` (one entry per Kelly fraction: ROI, max drawdown, bet count), written alongside the main manifest.

### Claude's Discretion
- Exact internal function names and module-level organization within `backtest.py`, `metrics.py`, and `model.py` (Norwegian, snake_case, per established convention).
- Exact bootstrap implementation details (resample count beyond the 1,000 default, RNG seeding for reproducibility — should be seeded so re-running the same manifest config reproduces the same CI).
- Whether `08_kjor_backtest.py` takes CLI flags for date range / Kelly fraction overrides, or is edited-and-rerun like the other numbered scripts — planner's call, but must remain resumable/cheap to iterate on the train/calibrate slice per the "predict once, simulate many" cost-management guidance.
- Exact injury-filter as-of adaptation: `skadefilter.py`'s "last 3 games" logic must become as-of-aware (relative to the simulated date, not real "today") — planner determines the specific function signature change. **This research found the specific data gap that makes this non-trivial — see Common Pitfalls and Open Questions below.**

### Deferred Ideas (OUT OF SCOPE)
- Full `nba_betting/` package restructure (`data/`, `backtest/`, `live/` subdirectories) — stays deferred; flat modules chosen instead for this phase.
- Threshold/odds-range grid search (BTV2-01), static HTML backtest report (BTV2-02), error-slice breakdown (BTV2-03), retrain-cadence experiments (BTV2-04), automated paper-trading-vs-backtest reconciliation (BTV2-05) — all already tracked as v2 requirements.
- Any change to the *live* `MIN_VALUE_TERSKEL`/`MAX_ODDS`/`KELLY_FRAKSJON` values in `config.py` — this phase builds the engine that will produce the evidence for such a change, but does not itself change the live-running values.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BT-01 | Walk-forward, chronological replay of the full decision pipeline against historical odds | Confirmed feasible with existing data (`nba_features.csv`, `odds_arkiv.db`, 3,638 games/480 dates verified). Feature-reuse pattern (Architecture Pattern 1) makes the loop itself cheap; odds join pattern (Pattern 2) makes bet-time pricing well-defined. Injury filter is the one pipeline stage that needs new data — see Open Questions. |
| BT-02 | All data as-of-date-D-safe (no post-decision info) | `features.beregn_lag_form(as_of=...)` already verified leakage-safe (per-team shift(1)/rolling, doesn't depend on future rows). Odds join must select `bet_time` snapshots only for the decision (never `closing`). Injury-availability check must use only games strictly before `as_of` — see Code Examples. |
| BT-03 | Locked, never-touched final holdout, checked exactly once | Concrete structural-guard code pattern provided (Architecture Pattern 4) — a `HoldoutLåstFeil` exception raised by an internal guard function, bypassable only from one explicitly-named "final holdout run" entry point. `HOLDOUT_START_DATO` value needs planner/user confirmation (Assumption A1). |
| BT-04 | ROI/win-rate/max-drawdown on flagged-bet subset, with CI | Bootstrap ROI CI and Wilson win-rate CI implementations provided (Code Examples), using only `numpy` (already a dependency, no new install). Bet-count-vs-CI-width risk flagged explicitly (Common Pitfalls) — likely 200-300 flagged bets on the train/calibrate slice, near the "statistically inconclusive" threshold already documented in prior milestone research. |
| BT-05 | Reproducible, versioned run manifest | `run_id` naming and manifest/ledger separation already locked in CONTEXT.md; this research adds the concrete bootstrap-seed-in-manifest detail needed for reproducibility (Assumption/discretion note). |
| BT-06 | CLV tracked per bet and in aggregate | Confirmed `odds_arkiv.db` has both `bet_time` and `closing` snapshot types keyed identically (`kamp_dato`, `event_id`); CLV = `fjern_vigorish(bet_time odds) - fjern_vigorish(closing odds)`, reusing the existing function — no new vig-removal logic needed. |
| BT-07 | Kelly-fraction sensitivity sweep (flat/quarter/half/full) | Predict/simulate split already locked in CONTEXT.md; this research confirms the "predict pass" is cheap (~12s total model-fit cost for the whole 2.5-year walk-forward loop, verified via live timing test), so caching predictions once and sweeping Kelly fractions against them is not a performance-driven necessity so much as a correctness one (never re-run walk-forward retraining per fraction, since retraining is stochastic-adjacent via `random_state` but re-running risks accidental divergence). |

</phase_requirements>

## Standard Stack

### Core

No new packages are required for this phase — every capability needed (bootstrap resampling, Wilson interval, ROI/drawdown math, model retraining) is achievable with libraries already installed and used elsewhere in this project.

| Library | Version (installed) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pandas` | 3.0.1 (per CLAUDE.md/venv) | Date-mask filtering of the precomputed features table, ledger DataFrame construction, CSV I/O | Already the project's dataframe layer throughout |
| `numpy` | 2.4.3 [VERIFIED: `python3 -c "import numpy"` in this session] | Bootstrap resampling (`np.random.default_rng`), percentile CI, ROI/drawdown arithmetic | Already a dependency; sufficient for both the bootstrap and Wilson-interval math without any new package |
| `xgboost` | 3.2.0 (per CLAUDE.md/venv) | Walk-forward model retraining via `model.py`'s extracted `train()` | Existing model family, `KalibrertModell` wrapper already built around it |
| `scikit-learn` (`IsotonicRegression`) | 1.8.0 (per CLAUDE.md/venv) | Calibration refit at each retrain point | Existing calibration approach (Phase 3), reused unmodified |
| `sqlite3` (stdlib) | bundled | Read `odds_arkiv.db` for bet-time/closing snapshots | Already how `odds.py` accesses the archive; no ORM needed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `scipy` | 1.17.1 [VERIFIED: `python3 -c "import scipy"` succeeds in the project venv — present transitively, likely via `quantstats`'s dependency chain from prior-phase exploration, NOT currently in `requirements.txt`] | Optional: `scipy.stats.norm.ppf` for a precise z-score in the Wilson interval | Only if the planner wants sub-percent precision on the z-score; hand-rolling with a hardcoded `z=1.96` (95% CI) avoids adding `scipy` to `requirements.txt` as an explicit new dependency and is standard practice for Wilson intervals — **recommended default is the hardcoded z-score, not a new scipy import**, to avoid dependency creep for a value that's constant across the whole phase |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled bootstrap CI (numpy) | `scipy.stats.bootstrap` | `scipy.stats.bootstrap` (available since scipy 1.7) does the same percentile-method resampling with less code, and scipy is already present in the venv transitively — but it is NOT in `requirements.txt`, so using it would be a new explicit dependency. Given the whole implementation is ~10 lines of numpy, prefer the hand-rolled version and skip the new dependency. |
| Hand-rolled Wilson interval | `statsmodels.stats.proportion.proportion_confint(method="wilson")` | `statsmodels` is not installed anywhere in this project and is a heavy dependency (pulls in `patsy`, adds real install weight) for a five-line formula. Not recommended. |

## Package Legitimacy Audit

**Not applicable this phase.** No new external packages are introduced — every library used (`pandas`, `numpy`, `xgboost`, `scikit-learn`, `sqlite3`) is already an installed, in-use project dependency per `requirements.txt`/the committed `venv/`. `scipy` is present but not used (see Alternatives Considered — recommendation is to avoid using it to avoid an undeclared new dependency). If the planner chooses to use `scipy.stats.norm.ppf`, run the Package Legitimacy Gate on `scipy` specifically before adding it to `requirements.txt`.

## Architecture Patterns

### System Architecture Diagram

```text
                    ┌─────────────────────────────────────────────┐
                    │  nba_kamper_raw.csv (3,638 team-game rows)   │
                    │  odds_arkiv.db (187,376 odds rows, 480 dates)│
                    └───────────────┬───────────────────────────────┘
                                    │  (built ONCE, not per retrain point)
                                    ▼
                    ┌─────────────────────────────────────────────┐
                    │ features.beregn_lag_form(df_raw, as_of=None) │
                    │ → full leakage-safe feature table            │
                    │   (or reuse nba_features.csv directly)       │
                    └───────────────┬───────────────────────────────┘
                                    │
                                    ▼
        ┌───────────────────────────────────────────────────────────────┐
        │                  backtest.py — walk-forward loop                │
        │                                                                  │
        │  for as_of_dato in unike_kampdatoer (480 dates, 30 months):     │
        │    ┌─ holdout guard: raise if as_of_dato >= HOLDOUT_START_DATO ─┐│
        │    │  (unless caller = kjor_endelig_holdout_backtest)          ││
        │    └─────────────────────────────────────────────────────────┘│
        │    if ny_maaned(as_of_dato):                                    │
        │        model = model.train(features_tabell, as_of=as_of_dato)   │
        │            └─ boolean date-mask filter, NOT recomputation       │
        │    dagens_kamper = features_tabell[dato == as_of_dato]          │
        │    for kamp in dagens_kamper:                                   │
        │        prob = model.predict_proba(kamp)                        │
        │        odds = odds.hent_bet_time_pris(as_of_dato, kamp)  ──┐    │
        │            └─ best price across bookmakers (mirrors live)  │    │
        │        if odds is None: skip (missing snapshot, don't error)│   │
        │        impl = strategy.fjern_vigorish(odds)                 │   │
        │        value, ev = strategy.beregn_value_og_ev(...)         │   │
        │        if value > terskel and odds i range:                 │   │
        │            skade_ok = skadefilter.sjekk_lag_helse_som_of(    │   │
        │                spillerlogg, kamp, as_of=as_of_dato)   ◄──── NEW │
        │            if skade_ok:                                      │  │
        │                innsats = strategy.beregn_innsats(...)        │  │
        │                ledger.append(bet_record)                     │  │
        │    ledger.settle(as_of_dato, faktiske_resultater)  # revealed│  │
        │        # only AFTER the decision is recorded                 │  │
        └───────────────────────────────┬─────────────────────────────┘  │
                                         │                                │
                                         ▼                                │
                    ┌─────────────────────────────────────────────┐      │
                    │ metrics.py: ROI/drawdown/CLV/bootstrap-CI/    │◄─────┘
                    │             Wilson-interval over ledger        │
                    └───────────────┬───────────────────────────────┘
                                    │
                                    ▼
        backtests/<run_id>/manifest.json + ledger.csv + kelly_sweep.json
```

### Recommended Project Structure

```
nba_betting/  (repo root — flat, per locked decision)
├── config.py            # + HOLDOUT_START_DATO constant (new)
├── features.py          # unchanged — beregn_lag_form already as-of-aware
├── strategy.py          # unchanged — pure functions reused as-is
├── teams.py             # unchanged
├── odds.py              # + a "select best bet_time price per outcome for a game"
│                         #   helper, extracted so live path + backtest share it
├── model.py             # NEW — train()/predict()/save()/load(), as_of-aware
├── skadefilter.py        # + a new as-of-aware check function; may need a small
│                         #   new module (e.g. spillerlogg.py) for the historical
│                         #   player-game-log data source (see Open Questions)
├── backtest.py           # NEW — walk-forward loop, holdout guard, predict/simulate split
├── metrics.py             # NEW — ROI, drawdown, CLV, bootstrap CI, Wilson interval
├── 08_kjor_backtest.py   # NEW — thin CLI entry point
├── backtests/             # NEW, gitignored — <run_id>/manifest.json, ledger.csv, kelly_sweep.json
└── nba_spillerlogg_raw.csv  # NEW (recommended), gitignored like other CSVs —
                              # player-game-log archive for as-of injury checks
```

### Pattern 1: Precompute-once, filter-many feature strategy

**What:** Build the full-history feature table exactly once (`features.beregn_lag_form(df_raw)` with `as_of=None`, or simply load the existing `nba_features.csv`), then at every walk-forward retrain point and every prediction date, filter that single in-memory DataFrame by `GAME_DATE_HJEMME` boolean masks rather than recomputing rolling stats.

**Why this is safe (not just fast):** `beregn_lag_form` groups by `TEAM_ID`, sorts by date, then does `shift(1).rolling(window=10, min_periods=3)` — the feature value for team T's game on date D depends only on team T's own games before D. Appending or including rows dated after D anywhere in the input DataFrame cannot change T's feature value on D. This is exactly the property `ARCHITECTURE.md`'s Pattern 2 leakage-regression test asserts (`test_feature_leakage_safety`), and it is what makes "compute the whole table once, then slice" both correct and fast.

**When to use:** Every retrain point in `backtest.py`'s loop, and every "today's games" lookup.

**Example:**
```python
# model.py (new)
def tren(features_df, as_of=None, kalibrer_andel=0.15, tidligste_dato=None):
    """
    Trener + kalibrerer en KalibrertModell på features_df, filtrert til
    rader strengt før 'as_of' (expanding window). as_of=None betyr
    "bruk hele datasettet" (engangs-treningen i 03_tren_modell.py).

    kalibrer_andel: hvor stor ANDEL av (tren+kalibrer)-vinduet som går
    til kalibrering, kronologisk nyest først — IKKE et fast antall
    måneder, fordi et fast vindu blir latterlig lite tidlig i en
    walk-forward-løkke (se Pitfalls: "varm-opp-periode").
    """
    if as_of is not None:
        vindu = features_df[features_df["GAME_DATE_HJEMME"] < as_of]
    else:
        vindu = features_df

    vindu = vindu.sort_values("GAME_DATE_HJEMME").reset_index(drop=True)
    kutt = int(len(vindu) * (1 - kalibrer_andel))
    tren_df, kalibrer_df = vindu.iloc[:kutt], vindu.iloc[kutt:]
    # ... fit XGBClassifier on tren_df, fit IsotonicRegression on kalibrer_df,
    # wrap in KalibrertModell — identical logic to 03_tren_modell.py's steps
    # 4 and 7, just parameterized by the as_of-filtered window instead of a
    # module-level df.
```

### Pattern 2: Odds snapshot join & best-price selection (mirrors the live path exactly)

**What:** For a given `(kamp_dato, hjemme_lag_id, borte_lag_id)`, query `odds_arkiv.db` for `snapshot_type='bet_time'` rows, group by `utfall_navn` (outcome), and take the **maximum** `odds` value per outcome across bookmakers — identical to `verdi_deteksjon.py`'s `beste_hjemme_odds`/`beste_borte_odds` reduction (lines 141-156, verified by direct read).

**Why:** This is not an arbitrary choice — it is the exact rule the live bot already applies. Choosing anything else (e.g. average odds, first bookmaker, median) would make the backtest validate a different pricing rule than what `06_bot.py` actually executes, reopening the "backtest doesn't match live" gap CORE-04 exists to close.

**Example:**
```python
# odds.py — new helper, extracted so both verdi_deteksjon.py (optionally,
# as a later cleanup) and backtest.py call the identical selection rule
def hent_bet_time_pris(con, kamp_dato, hjemme_lag_id, borte_lag_id):
    """
    Returnerer (beste_hjemme_odds, beste_borte_odds) for en gitt kamp på
    kamp_dato, valgt som HØYESTE pris per utfall på tvers av bookmakers —
    samme regel som verdi_deteksjon.py::finn_value_bets (D-parity).
    Returnerer (None, None) hvis arkivet ikke har noen bet_time-rad for
    denne kampen (manglende snapshot) — kalleren MÅ hoppe over kampen,
    ikke feile (Pitfall 2, ARCHITECTURE.md).
    """
    rader = con.execute(
        """
        SELECT hjemmelag, bortelag, utfall_navn, MAX(odds) as pris
        FROM odds_arkiv
        WHERE kamp_dato = ? AND snapshot_type = 'bet_time'
          AND hjemme_lag_id = ? AND borte_lag_id = ?
        GROUP BY utfall_navn
        """,
        (kamp_dato, hjemme_lag_id, borte_lag_id),
    ).fetchall()
    if not rader:
        return None, None
    priser = {r["utfall_navn"]: r["pris"] for r in rader}
    hjemme_navn = rader[0]["hjemmelag"]
    borte_navn = rader[0]["bortelag"]
    return priser.get(hjemme_navn), priser.get(borte_navn)
```
This uses SQL `MAX(odds) GROUP BY utfall_navn` instead of a Python loop — cheap, and the join key `(kamp_dato, hjemme_lag_id, borte_lag_id)` matches columns already present and indexed-adjacent in the schema (`idx_odds_arkiv_dato_type` covers `kamp_dato`; `hjemme_lag_id`/`borte_lag_id` are already resolved via `teams.finn_lag_id()` at archive time, verified in `odds.py::parse_snapshot_til_rader`).

### Pattern 3: `model.py::tren()` signature supporting both one-shot and walk-forward callers

**What:** One function, two calling conventions — `as_of=None` (one-shot, used by a rewritten `03_tren_modell.py`, produces a 3-way train/calibrate/**test** split matching the existing `kalibrering.del_kronologisk_3veis` logic for final reporting) vs. `as_of=<dato>` (walk-forward, used by `backtest.py`, produces only a 2-way train/calibrate split — no internal "test" slice, because the walk-forward loop's own out-of-sample prediction on `as_of_dato`'s games **is** the test).

**Why two different split shapes:** `03_tren_modell.py` needs a held-out test slice to report final calibration/accuracy numbers once. The walk-forward retrain inside `backtest.py` does not — creating an internal test slice there would waste data and add no signal, since every walk-forward prediction is already, by construction, out-of-sample relative to that retrain's training window.

**Trade-offs:** Two code paths inside one function (branching on `as_of`) is slightly more complex than two separate functions, but keeps the "same training logic, called by two entry points" promise CONTEXT.md's D-08-resolution requires (closing Anti-Pattern 2). Alternative: two thin wrapper functions (`tren_engangs()`, `tren_for_backtest()`) both calling a shared private `_tren_og_kalibrer()` — either is fine; this is explicitly Claude's Discretion territory per CONTEXT.md.

### Pattern 4: Structural holdout guard (BT-03)

**What:** A guard function called at the top of every date-processing iteration, raising unless the caller has explicitly opted into holdout access via a dedicated function name — not a config flag that any caller could flip.

**Verified timing/perf note:** Since the whole walk-forward loop over the full 2.5-year archive costs well under a minute (Pattern 1), there's no performance pressure to skip re-checking the guard per-date — checking it 480 times costs nothing measurable.

**Example:**
```python
# config.py (add)
HOLDOUT_START_DATO = "2024-10-01"   # se Assumptions Log A1 — bekreft eksakt dato

# backtest.py
class HoldoutLaastFeil(Exception):
    """Reist når tuning-/sweep-kode prøver å evaluere en dato i det låste
    holdout-vinduet (BT-03). Dette er IKKE en advarsel — koden skal stoppe."""


def _sikre_ikke_holdout(dato, tillat_holdout=False):
    if not tillat_holdout and dato >= config.HOLDOUT_START_DATO:
        raise HoldoutLaastFeil(
            f"{dato} er i det låste holdout-vinduet (>= {config.HOLDOUT_START_DATO}). "
            "Kun kjor_endelig_holdout_backtest() får kalle inn med tillat_holdout=True."
        )


def kjor_backtest(fra_dato, til_dato, kelly_fraksjon=None, tillat_holdout=False, **kwargs):
    """Hovedløkken. tillat_holdout er IKKE ment å settes av kallere flest —
    kun kjor_endelig_holdout_backtest() under skal noensinne sette den True."""
    for as_of_dato in odds.hent_unike_kampdatoer(fra=fra_dato, til=til_dato):
        _sikre_ikke_holdout(as_of_dato, tillat_holdout=tillat_holdout)
        # ... resten av løkken


def kjor_endelig_holdout_backtest(**kwargs):
    """DEN ENESTE funksjonen i kodebasen som får lov til å sette
    tillat_holdout=True. Kun kall denne etter at ALLE terskel-/Kelly-valg
    er fryst på train/kalibrer-slicen (BT-03)."""
    return kjor_backtest(
        fra_dato=config.HOLDOUT_START_DATO,
        til_dato="2025-04-13",
        tillat_holdout=True,
        **kwargs,
    )
```
`08_kjor_backtest.py` should only ever call `kjor_endelig_holdout_backtest()` from an explicit, separately-invoked code path (e.g. a `--holdout` flag, or a clearly separate function the developer must call by name) — never as the default action of running the script.

### Pattern 5: Bootstrap ROI CI + Wilson win-rate CI (numpy only)

**What to resample:** Individual **bets** (ledger rows), not games or dates — each bet has a `profit` (`innsats * (odds - 1)` if won else `-innsats`) and a `innsats` (stake). Resample bet indices with replacement, recompute `sum(profit)/sum(innsats)` per resample, take the 2.5th/97.5th percentiles for a 95% CI.

**How many bets is "too few":** `PITFALLS.md` (prior milestone research) already flags **under ~300-500 placed bets** as statistically inconclusive. This project's own historical value-rate (per `04_value_detector.py`'s `MIN_VALUE_TERSKEL=0.05`) is not precisely known ahead of running the engine, but with 2,413 train/calibrate games and a plausible 8-15% value-flagging rate (typical for a threshold this loose), expect roughly **190-360 flagged bets on the train/calibrate slice** — landing at or below the "inconclusive" line. **Report this honestly**: a wide bootstrap CI on ~250 bets is an expected, correct outcome, not a bug — BT-04 explicitly requires the CI to be attached precisely so this uncertainty is visible rather than hidden behind a single ROI percentage.

**Example:**
```python
# metrics.py (new)
import numpy as np

def bootstrap_roi_ci(profitter, innsatser, n_resamples=1000, seed=42, konfidensnivaa=0.95):
    """
    Bootstrap-CI for ROI over en bet-ledger. Resampler BETS (ikke kamper/
    datoer) med tilbakelegging. seed er fast (ikke fra klokken) slik at en
    gjenkjøring av samme manifest-config reproduserer nøyaktig samme CI —
    seed'en lagres i manifest.json for sporbarhet.
    """
    n = len(profitter)
    rng = np.random.default_rng(seed)
    roi_fordeling = np.empty(n_resamples)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        roi_fordeling[i] = profitter[idx].sum() / innsatser[idx].sum()
    halv_alfa = (1 - konfidensnivaa) / 2
    nedre, oevre = np.percentile(roi_fordeling, [100 * halv_alfa, 100 * (1 - halv_alfa)])
    punktestimat = profitter.sum() / innsatser.sum()
    return punktestimat, nedre, oevre


def wilson_ci(antall_vunnet, antall_totalt, z=1.96):
    """
    Wilson score-intervall for vinnrate — mer robust enn en naiv normal-
    approksimasjon på et lite/skjevt utvalg (BT-04). z=1.96 er hardkodet
    for 95% CI i stedet for å hente fra scipy.stats.norm.ppf — scipy er
    IKKE en deklarert prosjektavhengighet (se Standard Stack), og z-scoren
    for et fast konfidensnivå endrer seg aldri, så en konstant er riktig
    her, ikke en snarvei.
    """
    if antall_totalt == 0:
        return 0.0, 0.0, 0.0
    p = antall_vunnet / antall_totalt
    n = antall_totalt
    denominator = 1 + z**2 / n
    senter = (p + z**2 / (2 * n)) / denominator
    margin = (z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5)) / denominator
    return p, max(0.0, senter - margin), min(1.0, senter + margin)
```

### Pattern 6: Predict-once/simulate-many Kelly sweep (already locked, mechanics confirmed cheap)

**What:** Run the full walk-forward predict pass exactly once on the train/calibrate slice (model scoring + odds join + injury filter + value/EV computation), caching `(as_of_dato, kamp, modell_prob, odds, value, ev)` rows. Then for each Kelly fraction in `{0 (flat), 0.25, 0.5, 1.0}`, re-run only `strategy.beregn_innsats(..., kelly_fraksjon=f, ...)` and `metrics.py`'s ROI/drawdown functions against the cached rows — no model retraining, no odds re-fetch.

**Confirmed cheap:** The live timing benchmark in this session (0.4s/fit × ~24 monthly retrain points across the ~24-month train/calibrate window) means the *entire* predict pass costs roughly 10-15 seconds of model-fitting time; the sweep's 4 simulate-pass re-runs cost effectively nothing on top (pure arithmetic over a few hundred cached rows). No caching-to-disk is needed between predict and simulate passes if both run in the same `08_kjor_backtest.py` process — an in-memory list/DataFrame handoff is sufficient; only the final `kelly_sweep.json` needs to be written to disk.

**Note on "flat" Kelly fraction:** `strategy.beregn_innsats`'s signature takes `kelly_fraksjon` as a multiplier on the Kelly-derived stake — there is no existing "flat stake" mode in `strategy.py`. `08_kjor_backtest.py`/`backtest.py` will need a small branch (not a change to `strategy.py` itself, to avoid touching the live-shared pure module) for the "flat" sweep entry: e.g. `innsats = config.MIN_INNSATS` or a fixed fraction of starting bankroll, independent of Kelly math. This should be a `backtest.py`/`metrics.py`-local helper, not a `strategy.py` change (keeps the pure, zero-I/O module's contract identical for the live path).

### Pattern 7: As-of-aware injury check (requires new data — see Open Questions)

**What:** Given a precomputed player-game-log table (`PLAYER_ID`, `TEAM_ID`, `GAME_DATE`, `MIN`, one row per player per game — see Common Pitfalls for how to build it), for a given `(team_id, as_of_dato)`:
1. Compute each player's season-to-date average `MIN` using only games with `GAME_DATE < as_of_dato` **within the current NBA season** (mirrors `hent_toppspillere_for_lag`'s `MIN >= MIN_MINUTTER` filter, but season-to-date instead of full-season).
2. Take the top-3 players by that average (mirrors `ANTALL_TOPPSPILLERE`).
3. For each, look at their most recent 3 rows with `GAME_DATE < as_of_dato` and apply the same `sjekk_spiller` logic (missing entirely, or `GP < 2` / `min_snitt < 10` → flagged as uncertain).

**Performance note:** This does NOT need per-date recomputation over the whole league — only the ~10 players across the two teams playing on `as_of_dato` matter each time, so filtering the league-wide log to `< as_of_dato` and taking `.tail(3)` per relevant player is cheap even repeated 480 times (77K total player-game rows across 3 seasons is trivial for pandas).

**Example:**
```python
# skadefilter.py — new as-of-aware function, alongside the existing live ones
def sjekk_lag_helse_som_of(spillerlogg_df, team_id, lagnavn, as_of_dato, antall=ANTALL_TOPPSPILLERE):
    """
    As-of-variant av sjekk_lag_helse() — bruker en FERDIG-HENTET historisk
    spillerlogg-DataFrame (PLAYER_ID, TEAM_ID, GAME_DATE, MIN) i stedet for
    et live nba_api-kall. 'nåværende sesong' utledes av as_of_dato, ikke av
    datetime.now() (samme feil som gjeldende_sesong() ville gjort hvis
    kalt uendret fra en backtest-kontekst).
    """
    sesong_start, sesong_slutt = sesong_grenser_for_dato(as_of_dato)  # ny hjelper
    sesong_logg = spillerlogg_df[
        (spillerlogg_df["TEAM_ID"] == team_id) &
        (spillerlogg_df["GAME_DATE"] >= sesong_start) &
        (spillerlogg_df["GAME_DATE"] < as_of_dato)
    ]
    sesong_snitt = sesong_logg.groupby("PLAYER_ID").agg(
        MIN=("MIN", "mean"), PLAYER_NAME=("PLAYER_NAME", "first")
    ).reset_index()
    topp = sesong_snitt[sesong_snitt["MIN"] >= MIN_MINUTTER].sort_values("MIN", ascending=False).head(antall)

    resultat = {"lagnavn": lagnavn, "tilgjengelig": True, "advarsler": []}
    for _, sp in topp.iterrows():
        siste3 = sesong_logg[sesong_logg["PLAYER_ID"] == sp["PLAYER_ID"]].tail(3)
        gp = len(siste3)
        min_snitt = siste3["MIN"].mean() if gp else 0
        if gp < 2 or min_snitt < 10:
            resultat["tilgjengelig"] = False
            resultat["advarsler"].append(f"{sp['PLAYER_NAME']} ({sp['MIN']:.0f} min/kamp) – kun {gp} kamp(er) siste periode")
    return resultat
```

### Anti-Patterns to Avoid

- **Recomputing `beregn_lag_form` inside the retrain loop:** Unnecessary given Pattern 1 — a per-retrain-point recompute would still be *correct* (the function is safe to call repeatedly with `as_of`), just wasteful. Prefer computing once and filtering.
- **Selecting a different odds-reduction rule for the backtest than `verdi_deteksjon.py` uses live:** Breaks CORE-04 parity intent — always take best-price-across-bookmakers (Pattern 2), never average/median/first-book.
- **Silently substituting `closing` snapshots when `bet_time` is missing for a game:** This is explicitly the Anti-Pattern 3 already documented in `ARCHITECTURE.md` — skip the game instead (matches the existing project convention of skip-and-log for unresolvable data).
- **Treating a fixed-months calibration window (e.g., "last 1 month") as a per-retrain-point calibrate slice:** At the walk-forward loop's earliest retrain points (Nov/Dec 2022), a 1-month window has only ~50-100 games — far below sklearn's ~1,000-sample isotonic guidance already flagged as a concern in `03_tren_modell.py`'s own console warning. Prefer a **fraction of the expanding window** (Pattern 1's `kalibrer_andel`), which scales up automatically as more history accumulates.
- **Assuming `nba_kamper_raw.csv`/`nba_features.csv` contain player-level data for the injury filter:** They do not (verified directly) — see Common Pitfalls.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vig removal for CLV | A second vig-removal implementation for the CLV metric | `strategy.fjern_vigorish()` (already exists, already used for the value calculation) | BT-06 explicitly requires the same normalization; a second implementation reopens Pitfall 4 (vig-removal errors manufacturing fake edge) in a new spot |
| Bootstrap CI | A parametric/normal-approximation CI for ROI | Percentile-method bootstrap (Pattern 5) | Bet returns are not normally distributed (discrete win/loss with fixed payout ratios); a normal approximation on a small, skewed sample understates tail risk |
| Win-rate CI | A naive `p ± 1.96*sqrt(p(1-p)/n)` normal interval | Wilson score interval (Pattern 5) | Naive normal intervals can produce nonsensical bounds (below 0% or above 100%) on small samples — exactly the "~250 bets" scale expected here; Wilson is the standard fix and is locked in CONTEXT.md already |
| Team-name → team-ID resolution for the odds join | A fifth independent lookup dict | `teams.finn_lag_id()` (already the single canonical resolver, and `odds_arkiv.db` rows already have `hjemme_lag_id`/`borte_lag_id` resolved at archive time) | Reinventing this would be the fifth instance of the exact duplication pattern Phase 2 was built to eliminate |
| Best-price-per-outcome selection | A new "pick the best odds" function independent of the live path's logic | Extract `verdi_deteksjon.py`'s existing inline reduction into a shared helper (Pattern 2) | Two independent implementations of "best odds across bookmakers" is exactly Anti-Pattern 2 (duplicated decision logic) recreated a third time |

**Key insight:** Every "don't hand-roll" item above already has a working, tested implementation somewhere in this codebase. The discipline this phase needs is *extraction and reuse*, not new algorithm design — the actual new code is the walk-forward date loop, the SQLite join query, and the bootstrap/Wilson math (which have no existing implementation to reuse).

## Common Pitfalls

### Pitfall 1: The injury filter cannot be backtested with data that currently exists (biggest risk in this phase)

**What goes wrong:** `05_skadefilter.py`/`skadefilter.py` derives injury/availability signal from `nba_api.stats.endpoints.leaguedashplayerstats` — a **player-level, current-date-relative** query (`last_n_games=3` means "the 3 most recent games as of when the API is called," not "3 games before an arbitrary historical date"). `nba_kamper_raw.csv` and `nba_features.csv` are **team-level only** — verified directly by reading both files' columns: no `PLAYER_ID`, no per-player `MIN`, nothing player-granular exists anywhere in the two files CONTEXT.md's Integration Points section assumed the data would come from.

**Why it happens:** The original CONTEXT.md discussion (smart-discuss, autonomous mode) reasoned from the *shape* of the feature/injury adaptation problem ("as-of instead of live-today") without checking whether the underlying box-score data was even player-level. It is not.

**How to avoid:** Build a new, small, free, one-time historical player-game-log archive. Verified live in this research session: `nba_api.stats.endpoints.leaguegamelog.LeagueGameLog(player_or_team_abbreviation='P', season='2022-23', season_type_all_star='Regular Season')` returns 25,895 rows (one per player per game) with columns `PLAYER_ID, PLAYER_NAME, TEAM_ID, GAME_DATE, MIN` (numeric, not `"MM:SS"` string — confirmed `df['MIN'].dtype == int64`). Fetching this for all three seasons (`2022-23`, `2023-24`, `2024-25`) is 3 API calls — the exact same pattern `01_hent_data.py` already uses for team data, just with `player_or_team_abbreviation='P'`. No Odds API credits involved (this is `nba_api`, free, no key). This should be either a small addition inside a new module (e.g. `spillerlogg.py`, mirroring `01_hent_data.py`'s shape) or a one-off cell in `01_hent_data.py` producing a second output file `nba_spillerlogg_raw.csv`.

**Warning signs:** If the planner's task breakdown has a task that says "adapt `skadefilter.py` to accept an `as_of` parameter" with no corresponding task to acquire player-level historical data, the backtest's injury filter will either (a) silently do nothing (always pass) or (b) crash/be skipped for the whole phase.

**Phase to address:** This phase (Phase 5) — either build the small player-log acquisition step, or make an explicit, documented decision to disable the injury filter in the backtest and flag the resulting optimism bias in the manifest. See Open Questions.

### Pitfall 2: Missing/gapped odds snapshots must be skipped, not treated as zero-value

**What goes wrong:** Two known closing-line games (out of 3,645) were dropped during the Phase 4 archive build due to a post-tipoff-timestamp data-integrity fix (per `STATE.md`'s Phase 4 Plan 09 note). Any date/game without a `bet_time` row (network gaps, unresolved team names, or simply a game The Odds API never covered) must be **skipped from the ledger entirely** — not scored as "no value" (which would be a false negative, not an honest "no data").

**How to avoid:** `odds.hent_bet_time_pris()` (Pattern 2) returns `(None, None)` on a miss; `backtest.py`'s loop must explicitly check for this and `continue`, and the run manifest should report a count of "games skipped due to missing odds" alongside bet count, so a large skip rate is visible rather than silently absorbed into a smaller-than-expected bet count.

**Warning signs:** Total games processed in the manifest is silently less than the date range's actual `nba_features.csv` game count, with no skip-count reported.

### Pitfall 3: Bookmaker coverage is thinner in early 2022 (documented, date-dependent)

**What goes wrong:** Per `STATE.md`'s Phase 4 findings, the `eu`-region smoke test measured 10-11 bookmakers/game for early-range dates (Oct 2022) vs. 17-19 for late-range dates — meaning the "best price across bookmakers" reduction (Pattern 2) draws from a smaller pool early in the backtest window, which can subtly bias the earliest months' odds slightly less favorably than later months.

**How to avoid:** No code fix needed — this is a known, accepted data-quality boundary (developer already accepted it in Phase 4 rather than adding a `us`-region fallback fetch). Just don't be surprised if early-2022-23-season bet counts/EVs look slightly different in character from later months; don't investigate it as a bug.

### Pitfall 4: Warm-up period — the walk-forward loop's earliest months have tiny train/calibrate windows

**What goes wrong:** The archive starts 2022-10-24. If the first monthly retrain point is early November 2022, the "expanding window" training set at that point is only ~1-2 weeks of games (~50-100 rows), and Pattern 1's `kalibrer_andel`-based calibrate slice would be smaller still. XGBoost + isotonic on this little data will be noisy — consistent with the *already-observed* Phase 3 finding that even a full 2-month, 172-row calibration set produced worse-than-uncalibrated log-loss on this project's data.

**How to avoid:** Decide explicitly (this is an Open Question below) whether to (a) still evaluate/bet on these early months and let the wide bootstrap CI communicate the low confidence honestly, or (b) treat the first N months as a "burn-in" period excluded from the headline backtest report but still simulated (for bankroll continuity) — precedent exists in walk-forward literature for both approaches. Whichever is chosen, it must be stated explicitly in the run manifest, not silently baked into a start-date choice.

### Pitfall 5: Retrain-cadence "start of each calendar month" needs an exact anchor definition

**What goes wrong:** "Retrain monthly" is unambiguous in intent but not in exact implementation — does "start of month" mean the calendar 1st (even if no NBA games happen that day), or the first *actual* unique game date on/after the 1st? Given `odds.hent_unike_kampdatoer()` only returns dates with games, and NBA schedules have gaps (All-Star break, etc.), the cleanest anchor is: **retrain immediately before processing the first game-date of each new calendar month** (i.e., iterate `unike_kampdatoer`, and trigger a retrain whenever `as_of_dato.month != siste_retrent_maaned`).

**How to avoid:** Implement retrain-triggering as a comparison against the previous *processed* date's month, not against a fixed list of calendar-month-start dates — avoids ever needing to handle "no games on the 1st" as a special case.

### Pitfall 6: `strategy.beregn_innsats` has no "flat stake" mode built in

**What goes wrong:** BT-07's Kelly sweep needs a "flat" stake option, but `strategy.py`'s only staking function is Kelly-based (`beregn_innsats`). Calling it with `kelly_fraksjon=0` would return `0.0` for every bet (not a flat stake) since the function returns early on non-positive Kelly, and even a very small nonzero fraction still scales with the *edge*, not a fixed amount.

**How to avoid:** Implement "flat" as a `backtest.py`/`metrics.py`-local branch (e.g., a fixed stake = `MIN_INNSATS` or a fixed % of `STARTKAPITAL` per bet), not a change to the shared `strategy.py` — keeps the live-shared pure module's existing contract untouched, per the module's own explicit "commit to nothing project-specific" docstring philosophy.

## Code Examples

### Determining season boundaries for an arbitrary as_of date (backtest-side `gjeldende_sesong` equivalent)

```python
# Needed by both model.py (implicitly, via features.py which is date-based
# already) and skadefilter.py's as-of check (Pattern 7) — a date-driven,
# NOT clock-driven, version of the existing gjeldende_sesong() duplicated
# in skadefilter.py/verdi_deteksjon.py.
def sesong_grenser_for_dato(dato):
    """
    'dato' er en 'YYYY-MM-DD'-streng eller en pandas Timestamp. Returnerer
    (sesong_start, sesong_slutt) som strenger, der sesong_start er 1. okt
    samme år (eller foregående år hvis dato er før oktober) og sesong_slutt
    er 1. okt påfølgende år (eksklusiv øvre grense).

    Speiler gjeldende_sesong()s år/måned>=10-logikk, men tar dato som
    PARAMETER i stedet for å lese datetime.now() — dette ER selve as-of-
    fiksen (ARCHITECTURE.md Pitfall #5).
    """
    ts = pd.Timestamp(dato)
    if ts.month >= 10:
        return f"{ts.year}-10-01", f"{ts.year + 1}-10-01"
    return f"{ts.year - 1}-10-01", f"{ts.year}-10-01"
```

### Ledger row shape (mirrors the live bet-record dict, per CONTEXT.md's own note)

```python
# backtest.py — one row per simulated bet, written to ledger.csv
{
    "dato":         as_of_dato,          # backtest's "kjøredato" == as_of_dato here
    "kamp_dato":    as_of_dato,
    "kamp":         f"{hjemme_navn} vs {borte_navn}",
    "bet":          f"Hjemme ({hjemme_navn})" ,  # or Borte
    "odds":         valgt_odds,
    "innsats":      innsats,
    "modell":       "walk-forward",       # vs. a version/run_id tag, planner's call
    "modell_prob":  modell_sannsynlighet,
    "value":        value,
    "ev":           ev,
    "clv":          impl_prob_bet_time - impl_prob_closing,  # None if closing missing
    "status":       "venter",             # settled after faktisk resultat is revealed
    "gevinst":      None,
}
```

## State of the Art

| Old Approach | Current/Recommended Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| One-shot model trained on all history, "backtested" against dates it may have already seen (`03_tren_modell.py` today) | Walk-forward expanding-window retrain, monthly cadence, model only ever sees data strictly before the date it's scoring | This phase (Phase 5) | Closes Anti-Pattern 1 (ARCHITECTURE.md) — the single highest-priority leakage risk identified in prior research |
| Calibrator fit and evaluated on the same slice | Already fixed in Phase 3 (`kalibrering.del_kronologisk_3veis`, disjoint train/calibrate/test) | Phase 3 (prior) | This phase's `model.py` must preserve this discipline inside the walk-forward loop too (Pattern 3), not just in the one-shot path |
| Live injury filter (real nba_api injury-adjacent last-3-games query) | Backtest needs a parallel as-of historical equivalent — does NOT yet exist, needs new data (Pitfall 1) | This phase, if scoped in | Materially changes what "full decision pipeline" (BT-01) means if descoped — see Open Questions |
| Closing-line or ad-hoc odds selection for a backtest price | `bet_time` snapshot at a fixed pre-tipoff offset (already solved by Phase 4's `odds_arkiv.db` schema, 13:00 UTC "morning of" convention) | Phase 4 (prior) | This phase just needs to *consume* the already-correct snapshot type — no new timing logic needed |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `HOLDOUT_START_DATO = "2024-10-01"` is the right exact value for "the full 2024-25 season" | Architecture Pattern 4 | If the intended boundary is instead the first actual 2024-25 game date (`2024-10-22`, verified via `nba_features.csv`) or a different cutoff, the train/calibrate slice size changes by ~3 weeks/games — small but not zero impact on tuning-set statistics. Low risk either way; needs explicit planner/user confirmation, not a blocking issue. |
| A2 | Monthly retrain should trigger on "first game-date of a new calendar month encountered while iterating," not a fixed list of calendar-1st dates | Common Pitfalls #5 | If implemented differently (e.g., exactly 30-day rolling retrain), the number of model fits and their exact training windows shift, changing exact backtest numbers run-to-run — needs to be pinned once and documented in the manifest for reproducibility, but doesn't change the phase's feasibility. |
| A3 | Best-price-across-bookmakers is the correct backtest odds-selection rule, since it's what the live path already does | Architecture Pattern 2 | If the planner intends a different rule (e.g. median price, single "reference" bookmaker for consistency with CLV's closing-price comparison), CLV computation and ROI would differ meaningfully — this is presented as the default/recommended choice based on direct code evidence, not confirmed as an explicit locked decision in CONTEXT.md. |
| A4 | A new `nba_spillerlogg_raw.csv` (player-game-log) data-acquisition step is in-scope for this phase and is the correct way to make the injury filter backtestable | Common Pitfalls #1, Open Questions | This is the single highest-impact assumption in this research — CONTEXT.md's own text assumed this data already existed. If the planner/user decides this new acquisition is out of scope, BT-01's "full decision pipeline" claim needs to be either descoped (injury filter disabled in backtest, documented bias) or deferred to a follow-up phase. Needs explicit confirmation before planning proceeds. |
| A5 | `model.py`'s walk-forward calibrate-slice sizing should be fraction-based (e.g. 15% of the expanding window) rather than a fixed number of months | Architecture Pattern 1, Pitfall 4 | If a fixed-month window is used instead, early-backtest months will have extremely small/noisy calibration sets (worse than the already-flagged Phase 3 finding) — fraction-based sizing is the safer default but is not an explicit CONTEXT.md decision. |

**If this table is empty:** N/A — see entries above; none of these block planning, but A4 in particular should be surfaced to the user/planner explicitly since it changes phase scope.

## Open Questions

1. **Is the injury-filter backtest in scope for this phase, given the new data-acquisition requirement?**
   - What we know: The current live injury filter cannot be backtested with existing data (Pitfall 1). A verified, cheap (3 free API calls, no credits) fix exists: build `nba_spillerlogg_raw.csv` via `nba_api.leaguegamelog` player-level fetch.
   - What's unclear: Whether CONTEXT.md's "Claude's Discretion" grant for "the specific function signature change" was made under the (incorrect) assumption that no new data acquisition was needed. This changes the size/shape of the phase's task list meaningfully (one new data-fetch task + a new small module vs. a pure code-adaptation task).
   - Recommendation: Planner should present both options explicitly to the user at plan time: (a) build the player-log archive and get a real as-of injury filter, or (b) disable the injury filter for the backtest and document the resulting optimism bias in every run manifest (`skadefilter_aktiv: false`). Given the acquisition cost is low (3 API calls, minutes of runtime, no credits), (a) is recommended, but it is a scope decision, not a research verdict.

2. **Exact `HOLDOUT_START_DATO` value.**
   - What we know: CONTEXT.md says "the full 2024-25 season (2024-10 through 2025-04-13)." `nba_features.csv`'s actual 2024-25 games start 2024-10-22.
   - What's unclear: Whether "2024-10" means the calendar-month boundary (`2024-10-01`, cleaner constant, includes a ~3-week gap with no games — harmless) or the first actual game date.
   - Recommendation: Use `2024-10-01` as the constant (clean, unambiguous, and the ~3-week gap before the first real game contains no data either way, so behaviorally identical to using `2024-10-22`) — but state this explicitly in the plan for user sign-off.

3. **Should the walk-forward loop's earliest months (small training/calibration windows) be excluded from headline metrics or included with a wide CI?**
   - What we know: Prior Phase 3 finding shows even a 172-row calibration set produced worse-than-uncalibrated results on this data; the earliest walk-forward months will have even less.
   - What's unclear: Whether a "burn-in exclusion" period is expected by BT-04's "report on flagged-bet subset" language, or whether the bootstrap CI is trusted to communicate this naturally.
   - Recommendation: Include all months in the ledger (for bankroll/drawdown continuity), but consider reporting headline ROI/CI both "full period" and "excluding first 2-3 months" as two manifest entries — cheap to compute given both are just different date-range filters over the same cached ledger (Pattern 6's caching applies here too).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `odds_arkiv.db` (SQLite) | Odds join (BT-01, BT-06) | ✓ [VERIFIED: `ls -la` + `sqlite3` query in this session] | 187,376 rows, 480 dates, 2022-10-24 to 2025-04-13 | — |
| `nba_features.csv` | Feature table (BT-01, BT-02) | ✓ [VERIFIED: read directly, 3,638 rows, 480 unique dates] | — | — |
| `nba_kamper_raw.csv` | Team-level raw box scores (source for feature recompute if needed) | ✓ [VERIFIED: read directly] | — | — |
| `nba_api` (network) | Optional new player-log fetch (Pitfall 1 fix) | ✓ [VERIFIED: live `leaguegamelog` call succeeded in this session, 25,895 rows returned] | package present in venv | If unreachable at plan/execute time: injury filter must be disabled for the backtest (documented fallback, see Open Question 1) |
| The Odds API (network/credits) | NOT required for this phase's core loop | N/A | — | The backtest reads only the already-archived `odds_arkiv.db` — no live odds fetch, no credit spend, for the entire walk-forward loop |
| `pytest` | Test coverage for new modules | ✓ [VERIFIED: `pytest.ini` present, 129 existing tests collected successfully in this session] | project's pinned version | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** `nba_api` reachability for the new player-log fetch — fallback is documented (disable injury filter in backtest, flag the bias).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` (version per `requirements.txt`; 129 tests currently collected) |
| Config file | `pytest.ini` (`pythonpath = .`, `testpaths = tests`) |
| Quick run command | `python3 -m pytest tests/test_backtest.py tests/test_metrics.py tests/test_model.py -q` (new files, once created) |
| Full suite command | `python3 -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BT-01 | Walk-forward loop produces a ledger for a small synthetic date range | unit/integration | `pytest tests/test_backtest.py::test_kjor_backtest_produserer_ledger -x` | ❌ Wave 0 |
| BT-02 | Feature/odds/injury lookups never see data dated `>= as_of` | unit (leakage regression, extends existing `test_parity.py`) | `pytest tests/test_parity.py -x` | ⚠️ Exists but must be extended — its own docstring already instructs Phase 5 to add a live-vs-backtest side-by-side assertion |
| BT-03 | `kjor_backtest()` raises `HoldoutLaastFeil` for any date `>= HOLDOUT_START_DATO` unless called via `kjor_endelig_holdout_backtest()` | unit | `pytest tests/test_backtest.py::test_holdout_guard_reiser_feil -x` | ❌ Wave 0 |
| BT-04 | `bootstrap_roi_ci`/`wilson_ci` match hand-calculated values on a known synthetic bet sequence | unit | `pytest tests/test_metrics.py::test_bootstrap_roi_ci_kjente_verdier -x` | ❌ Wave 0 |
| BT-05 | `manifest.json` round-trips config + metrics correctly, `run_id` is unique per config | unit | `pytest tests/test_backtest.py::test_manifest_inneholder_konfig_og_metrikker -x` | ❌ Wave 0 |
| BT-06 | CLV computed as `fjern_vigorish(bet_time) - fjern_vigorish(closing)`, `None` when closing snapshot missing | unit | `pytest tests/test_metrics.py::test_clv_beregning -x` | ❌ Wave 0 |
| BT-07 | Kelly sweep produces 4 distinct entries (flat/quarter/half/full) from one cached predict pass, never re-running the walk-forward loop | unit | `pytest tests/test_backtest.py::test_kelly_sweep_bruker_cachet_prediksjoner -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/test_backtest.py tests/test_metrics.py tests/test_model.py -q`
- **Per wave merge:** `python3 -m pytest tests/ -q` (full 129+ suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_model.py` — covers `model.py::tren()`'s one-shot vs. walk-forward split behavior (Pattern 3)
- [ ] `tests/test_backtest.py` — covers the walk-forward loop, holdout guard, and Kelly-sweep caching
- [ ] `tests/test_metrics.py` — covers bootstrap CI, Wilson interval, CLV, drawdown arithmetic against hand-calculated synthetic values
- [ ] Extend `tests/test_parity.py` per its own existing docstring instruction — add the live-vs-backtest side-by-side decision-parity assertion once `backtest.py` exists
- [ ] If the player-log acquisition (Pitfall 1 fix) is in scope: `tests/test_skadefilter.py` needs new as-of-aware test cases using an injected synthetic player-log fixture (no network), mirroring the existing `siste3`/`sesong_snitt` injection pattern already used for the live path

## Security Domain

`security_enforcement` is absent from `.planning/config.json` (treated as enabled), but this phase introduces no new external attack surface: no new user input, no new secrets, no new network-facing endpoint, and no live betting/money movement (paper-trading only, per `CLAUDE.md`'s hard gate). Most ASVS categories are not applicable.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | No new auth surface — single-user local CLI tool |
| V3 Session Management | No | N/A — no sessions |
| V4 Access Control | No | N/A — no multi-user access |
| V5 Input Validation | Marginal | `HOLDOUT_START_DATO`/date-range CLI args (if `08_kjor_backtest.py` takes flags) should be validated as parseable ISO dates before use — cheap guard, prevents a malformed date silently matching zero rows instead of erroring |
| V6 Cryptography | No | No new secrets/crypto introduced this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via date/team-ID parameters into the new `odds.hent_bet_time_pris()` query | Tampering | Already mitigated by using parameterized `?` placeholders (Pattern 2's example uses `con.execute(..., (kamp_dato, hjemme_lag_id, borte_lag_id))`, never string-formatted SQL) — this matches `odds.py`'s existing convention throughout (`er_allerede_arkivert`, `arkiver_odds_rader` etc. already use parameterized queries) |
| Pickle deserialization of a walk-forward-retrained model artifact, if `model.py::lagre()` writes intermediate models to disk | Tampering (if the file is ever shared/downloaded from an untrusted source) | Already a known, accepted low-risk pattern in this project (`nba_modell.pkl`, self-generated, gitignored) — no new risk introduced as long as walk-forward intermediate models (if persisted at all) stay local/gitignored the same way |

## Sources

### Primary (HIGH confidence — direct source/data inspection or live verification in this session)
- `features.py` (repo) — `beregn_lag_form`'s per-team `shift(1).rolling()` behavior, confirming feature values don't depend on future rows
- `strategy.py` (repo) — pure vig-removal/value/EV/Kelly functions, confirmed zero-I/O and directly reusable
- `odds.py` (repo) — `odds_arkiv` SQLite schema, `parse_snapshot_til_rader`, `hent_unike_kampdatoer`
- `verdi_deteksjon.py` (repo) — live path's best-price-across-bookmakers reduction (lines 141-156), confirms Pattern 2's design
- `03_tren_modell.py`, `kalibrering.py`, `modell_utils.py` (repo) — existing one-shot train/calibrate/test split logic Pattern 3 must preserve
- `05_skadefilter.py`, `skadefilter.py` (repo) — confirmed live-only, player-level, `nba_api`-dependent injury logic (Pitfall 1)
- `nba_kamper_raw.csv`, `nba_features.csv` (repo, read via pandas in this session) — confirmed team-level-only schema, 3,638 games, 480 unique dates, holdout slice = 1,225 games (2024-10-22 to 2025-04-13)
- `odds_arkiv.db` (repo, queried via `sqlite3` in this session) — confirmed 187,376 rows, 93,522 `bet_time` / 93,854 `closing`, multi-bookmaker-per-outcome row shape
- Live `nba_api.stats.endpoints.leaguegamelog.LeagueGameLog(player_or_team_abbreviation='P', ...)` call executed in this session — confirmed 25,895-row player-game-log for 2022-23 season, numeric `MIN` column, resolves Pitfall 1
- Live XGBoost+IsotonicRegression fit timing benchmark executed in this session — confirmed ~0.4s/fit on ~2,500 rows, resolving the "monthly retrain performance" question
- `pytest.ini`, `tests/conftest.py`, `tests/test_parity.py` (repo) — confirmed existing test framework and the explicit instruction (already written into `test_parity.py`'s own docstring) for what Phase 5 must add
- `.planning/phases/05-walk-forward-backtest-engine/05-CONTEXT.md` — locked decisions
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md` — requirement text and prior-phase findings (bookmaker coverage gap, closing-line data-integrity fix, 04-09 archive stats)

### Secondary (MEDIUM confidence — prior milestone research, not re-verified live this session but internally consistent with direct code inspection above)
- `.planning/research/ARCHITECTURE.md` — walk-forward pattern, anti-patterns, leakage-safety rules (verified consistent with direct code reading)
- `.planning/research/PITFALLS.md` — bet-count-for-significance heuristic (~300-500 bets), calibration-leakage pitfall (already fixed in Phase 3)
- `.planning/research/STACK.md` — "custom pandas/numpy backtest loop, no off-the-shelf framework" recommendation, confirmed still correct given no new packages are needed
- `.planning/research/FEATURES.md` — bootstrap/Wilson-interval as the recommended CI approach for this domain

### Tertiary
- None — this research relied entirely on direct codebase/data inspection and live verification rather than external web search, since the domain (this specific project's own pipeline) is not something external documentation covers.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages, all verified already installed and in use
- Architecture (feature-reuse, odds-join patterns): HIGH — verified directly against source code and live data
- Injury-filter data gap: HIGH confidence that the gap exists (verified via direct file inspection); MEDIUM confidence on the exact recommended fix's downstream details (untested end-to-end, though the core `nba_api` call was verified live)
- Bootstrap/Wilson CI math: HIGH — standard, well-established formulas, implementable with already-available `numpy`
- Pitfalls: HIGH — cross-referenced against prior milestone research and this session's own direct data queries (bet-count estimate, warm-up period sizing)

**Research date:** 2026-08-24
**Valid until:** ~30 days (stable domain — no external API/library churn risk for this phase's dependencies; re-verify if `odds_arkiv.db` is re-archived or `nba_features.csv` is regenerated with a different schema before planning executes)

---
*Phase: 5-Walk-Forward Backtest Engine*
*Research completed: 2026-08-24*
