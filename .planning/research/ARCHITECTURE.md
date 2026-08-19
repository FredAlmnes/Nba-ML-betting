# Architecture Research

**Domain:** Solo-maintained Python sports-betting value-detection system with a historical-backtesting requirement
**Researched:** 2026-08-19
**Confidence:** HIGH (architectural pattern — shared-core-between-backtest-and-live is well established in quant/algo-trading tooling, e.g. NautilusTrader, QuantConnect LEAN, Freqtrade); MEDIUM (specifics of Odds-API historical-snapshot timing, since this is domain-specific and not covered by generic backtesting literature)

## Standard Architecture

### System Overview

The dominant pattern across mature backtesting ecosystems (NautilusTrader, QuantConnect/LEAN, Freqtrade, Backtrader) is **one strategy/decision core, two data-and-execution adapters** — never two parallel implementations of the decision logic. Backtest and live differ only in *where data comes from* and *what happens to a decision after it's made* (simulate a fill vs. place a real order / log a paper bet).

```text
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA LAYER (adapters)                        │
├───────────────────────────┬───────────────────────────────────────────┤
│  Historical source         │  Live source                              │
│  - game results (as-of)    │  - today's odds (The Odds API live)       │
│  - odds snapshots (Odds    │  - today's team form / injuries           │
│    API historical replay)  │                                            │
└─────────────┬───────────────────────────────┬─────────────────────────┘
              │  same normalized schema        │
              ▼                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SHARED DECISION CORE (one copy, pure functions)   │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐            │
│  │ features.py    │  │ model.py       │  │ strategy.py    │            │
│  │ (as-of-safe    │→ │ (calibrated    │→ │ (value/EV,     │            │
│  │  rolling stats)│  │  predict_proba)│  │  filters, Kelly)│           │
│  └───────────────┘  └───────────────┘  └───────────────┘            │
│  ┌───────────────┐                                                    │
│  │ teams.py       │  (single team-name resolver, used by every layer) │
│  └───────────────┘                                                    │
└─────────────┬───────────────────────────────┬─────────────────────────┘
              ▼                                 ▼
┌───────────────────────────┐   ┌───────────────────────────────────────┐
│  BACKTEST ENGINE            │   │  LIVE ORCHESTRATOR                    │
│  - walk-forward loop over   │   │  - runs once/day                      │
│    historical dates          │   │  - settles pending bets                │
│  - simulated bankroll/ledger│   │  - real bankroll.json / bets.json      │
│  - ROI / drawdown / CLV     │   │  - dashboard.html                      │
└───────────────────────────┘   └───────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|-------------------------|
| Data adapters | Fetch and normalize data into a schema that's identical whether it came from a historical replay or a live call | Thin wrapper functions returning DataFrames/records with the same column names regardless of source; historical odds adapter wraps The Odds API `/historical/` endpoint, live adapter wraps the current-odds endpoint — both return the same `OddsSnapshot`-shaped rows |
| `features.py` (shared) | Compute point-in-time-safe features from raw game rows given an `as_of` cutoff | Pure function `build_features(games_df, as_of=None)`; internally still uses `shift(1)` rolling windows, but additionally filters input rows to `game_date < as_of` so it's safe to call with a full multi-season DataFrame during backtesting, not just the "already-trimmed-to-past" data implicit in the live path today |
| `model.py` (shared) | Train, calibrate, persist, and load the classifier; expose `predict_proba` | Same `KalibrertModell`-style wrapper, but training becomes a callable `train(features_df, as_of=None)` so the backtest engine can retrain on a rolling/expanding window instead of reusing one model across the whole backtest period |
| `teams.py` (shared) | Resolve any team name/abbreviation string (from either API) to one canonical ID | One dictionary + one fuzzy-match function, built once, imported everywhere — replaces the four independent copies |
| `strategy.py` (shared) | Turn `(model_prob, odds, injury_status)` into a bet/no-bet decision and a stake size | Pure functions: `implied_prob()`, `value_and_ev()`, `passes_filters(config)`, `kelly_stake(config)` — no I/O, no file reads, fully unit-testable, called identically by backtest and live |
| Backtest engine | Replay the shared decision core day-by-day over history with a simulated bankroll | Event/date-driven loop (see Pattern 1 below); this is new code, does not exist today |
| Live orchestrator | Daily run: settle, decide (via shared core), stake, persist, report | Refactor of `06_bot.py`, but importing `strategy.py`/`features.py`/`model.py` as library calls instead of shelling out to `04_value_detector.py`/`05_skadefilter.py` via `subprocess` |

## Recommended Project Structure

```
nba_betting/
├── nba_betting/                    # importable package (the fix for "no package structure")
│   ├── __init__.py
│   ├── config.py                   # env-loaded settings (API keys, thresholds) — one source of truth
│   ├── data/
│   │   ├── __init__.py
│   │   ├── games.py                 # nba_api box-score fetch + home/away reshape (was 01_)
│   │   ├── odds.py                  # unified live + historical Odds API client, same output schema
│   │   ├── injuries.py              # player minutes/availability fetch, as-of-aware (was 05_'s data half)
│   │   └── teams.py                 # SINGLE team-name → team-ID resolver
│   ├── features.py                  # SINGLE feature-engineering function (was 02_ + duplicated block in 04_)
│   ├── model.py                     # KalibrertModell wrapper + train()/load()/save() (was modell_utils.py + 03_)
│   ├── strategy.py                  # pure decision logic: value/EV, filters, Kelly stake (was logic half of 04_/06_)
│   ├── ledger.py                    # bankroll/bet JSON read-write + settlement (was state half of 06_)
│   ├── dashboard.py                 # HTML report generation, parameterized so backtest + live both use it
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── engine.py                # walk-forward replay loop, simulated bankroll
│   │   └── metrics.py               # ROI, max drawdown, CLV vs. closing line
│   └── live/
│       ├── __init__.py
│       └── bot.py                   # daily orchestration — imports the shared modules directly, no subprocess
├── scripts/                         # thin CLI entry points only — argparse + call into package + print result
│   ├── fetch_data.py                # replaces 01_
│   ├── train_model.py               # replaces 03_
│   ├── run_bot.py                   # replaces 06_
│   └── run_backtest.py              # new
├── tests/
│   ├── test_features.py             # incl. explicit leakage regression test (see Pattern 2)
│   ├── test_strategy.py             # pure-function tests, no network/fixtures needed
│   ├── test_teams.py                # every known odds-API team string resolves correctly
│   └── test_parity.py               # golden test: live path and backtest path agree on a fixed historical date
├── data/                            # gitignored: raw/features/model artifacts (replaces loose root CSVs)
├── state/                           # gitignored: bankroll.json, bets.json (real ledger)
├── backtests/                       # gitignored: per-run backtest ledgers + reports (separate from live state)
├── pyproject.toml
└── .env.example                     # documents required env vars (fixes the hardcoded API key)
```

### Structure Rationale

- **`nba_betting/` package vs. flat scripts:** the single biggest enabler of "backtest and live can't drift apart" is that there is only *one* copy of `features.py`/`strategy.py`/`teams.py` to import, not two implementations to keep in sync by hand. This directly targets the two anti-patterns already identified in `.planning/codebase/ARCHITECTURE.md` (duplicated team lookup, duplicated feature logic).
- **`scripts/` stays thin:** solo-maintainer projects don't need a CLI framework or service layer — argparse-based scripts that call into the package are enough. This preserves the "run one command per task" workflow the project already has, it just stops those commands from *containing* the logic.
- **`backtest/` separate from `live/`:** both depend on the same core (`features.py`, `model.py`, `strategy.py`), but must never share *state*. Backtest bankroll/ledger files must never be written to the same `state/bankroll.json` the live bot reads — mixing them is a realistic and dangerous failure mode (a backtest run corrupting or being mistaken for real paper-trading history). Separate `backtests/` directory enforces this by construction.
- **No database, no service layer, no async:** this is explicitly *not* warranted here — one process, once a day, single user. Flat files (CSV/JSON, or SQLite if the bet ledger schema starts needing queries the JSON approach makes awkward — e.g. "what's ROI by odds bucket") remain appropriate. Introducing FastAPI, a task queue, or a DB engine would be over-engineering for this project's actual scale.
- **Norwegian naming convention:** keep it at the *identifier* level (function/variable names, docstrings, config constants) as the project already does — this structure recommendation only changes module/file organization (which was already inconsistently English/Norwegian, e.g. `feature_engineering` vs `skadefilter`), not the language of the code inside those modules.

## Architectural Patterns

### Pattern 1: Walk-forward replay loop with as-of-aware retraining

**What:** The backtest engine iterates chronologically through historical dates. At each date `D`, it (a) rebuilds/updates the model using *only* data with `game_date < D` (or a rolling/expanding window, retrained on a cadence — e.g. monthly — rather than every single day, to keep it cheap), (b) computes features for that day's games using the same `as_of=D` cutoff, (c) fetches the historical odds snapshot for those games as it existed at a chosen realistic pre-tipoff offset (not the closing line), (d) runs the same `strategy.py` functions the live bot uses to decide bet/no-bet and stake size, and (e) only *after* recording the bet, reveals the actual game result to settle it and update the simulated bankroll.

**When to use:** Any time historical performance of a decision system (not just a classifier) needs to be assessed — this is the standard technique in quant backtesting (walk-forward analysis) and applies directly here because the thing under test is "model + threshold + odds filter + Kelly staking," not the model in isolation.

**Trade-offs:** More expensive than a single train/test split (retraining N times over the backtest period) and more code than "just run the pickled model over history." But a single static model tested "backward" over dates it may have already seen in training (the current `03_tren_modell.py` trains on 2022-23 through 2024-25 with only a 2-month holdout) is not a valid backtest of the live system — it would silently leak future information into every prediction for any date that was in the model's training set. **This is very likely the single highest-priority leakage risk for this project** given the current one-shot training approach.

**Example:**
```python
# backtest/engine.py
def run_backtest(games_df, odds_source, config, retrain_every="MS"):
    bankroll = SimulatedLedger(start=config.start_bankroll)
    model = None
    last_retrain = None
    for as_of_date in trading_dates(games_df, config.start_date, config.end_date):
        if model is None or should_retrain(as_of_date, last_retrain, retrain_every):
            train_df = games_df[games_df["game_date"] < as_of_date]
            model = train_model(build_features(train_df))  # nba_betting.model / features
            last_retrain = as_of_date

        todays_games = games_df[games_df["game_date"] == as_of_date]
        feats = build_features(games_df, as_of=as_of_date).loc[todays_games.index]
        odds = odds_source.snapshot_before_tipoff(as_of_date, offset_hours=config.odds_lead_time)

        for game, prob, market in zip(todays_games.itertuples(), model.predict_proba(feats), odds):
            decision = strategy.evaluate(prob, market, config)   # SAME function live bot calls
            if decision.bet:
                stake = strategy.kelly_stake(decision, bankroll.balance, config)
                bankroll.place(game, decision, stake)

        bankroll.settle(as_of_date, results=actual_results_for(as_of_date))  # results revealed only now
    return bankroll.report()
```

### Pattern 2: Leakage regression test (parity test between paths)

**What:** A test that runs one fixed historical game through both `features.py`/`strategy.py` called with `as_of` set to that game's date, and independently through whatever the live path does, and asserts they produce the same predicted probability, value/EV, and stake. Also: a test that asserts `build_features(df, as_of=D)` is unaffected by rows appended to `df` with `game_date >= D` — i.e., appending future games to the input DataFrame must not change any feature value for past dates.

**When to use:** Add this as soon as `features.py`/`strategy.py` are extracted into shared modules, and run it in CI (even a minimal local `pytest` run) on every change — it is the concrete mechanism that prevents the drift that already happened once (the documented `KALIBRERING_RAPPORT.md` fix that was never applied to `04_value_detector.py`).

**Trade-offs:** Requires fixing a small "golden" historical dataset/date as a fixture, and requires the refactor (Pattern 3) to actually happen — without a single shared module to call from both paths, there is nothing for this test to compare against except two hand-maintained implementations, which is the current broken state.

**Example:**
```python
# tests/test_parity.py
def test_feature_leakage_safety():
    df = load_fixture_games()  # multiple seasons
    before = build_features(df, as_of=date(2024, 12, 1))
    df_with_future = pd.concat([df, load_fixture_future_games()])
    after = build_features(df_with_future, as_of=date(2024, 12, 1))
    pd.testing.assert_frame_equal(before, after)  # future rows must not change past features

def test_backtest_and_live_agree_on_fixed_date():
    game = fixture_game(date(2024, 12, 1))
    backtest_decision = strategy.evaluate(*backtest_inputs_for(game))
    live_decision = strategy.evaluate(*live_style_inputs_for(game))  # same function, different adapter
    assert backtest_decision == live_decision
```

### Pattern 3: Ports-and-adapters for data sources (minimal form)

**What:** Data-fetching functions return a normalized shape (e.g. a DataFrame with fixed column names for odds regardless of whether it came from the live endpoint or the historical-replay endpoint) so the decision core never needs to know which source it's looking at. This is *not* full hexagonal architecture with interfaces/DI containers — for a solo project, "two functions with the same return schema" is enough; no abstract base classes or plugin registries needed.

**When to use:** Specifically for `data/odds.py` (live odds fetch vs. The Odds API historical-snapshot fetch) and `data/games.py`/`data/injuries.py` (live "recent games" query vs. historical as-of query) — anywhere the backtest and live paths need the same downstream shape from different upstream calls.

**Trade-offs:** Slightly more indirection than the current "just build a DataFrame inline" approach, but this is what actually stops the "duplicated inline feature block in `04_value_detector.py`" problem from recurring in a third place (the backtest).

## Data Flow

### Live path (daily)

```
06_bot.py-equivalent (live/bot.py)
  → settle pending bets (ledger.py, using actual results)
  → data/odds.py: fetch today's live odds
  → data/games.py: fetch today's team form (recent games)
  → data/injuries.py: fetch today's player availability
  → features.py: build_features(..., as_of=today)   [SAME function as backtest]
  → model.py: load pickled model, predict_proba
  → strategy.py: evaluate() / kelly_stake()          [SAME functions as backtest]
  → ledger.py: place bets, persist state/bankroll.json, state/bets.json
  → dashboard.py: render dashboard.html
```

### Backtest path (on demand)

```
scripts/run_backtest.py
  → data/games.py: load full historical game history
  → data/odds.py: load/fetch historical odds snapshots (cached locally — rate-limited/costly)
  → backtest/engine.py: walk-forward loop over historical dates
      → features.py: build_features(..., as_of=D)     [SAME function as live]
      → model.py: train_model(..., as_of=D) on rolling/expanding window   [walk-forward retrain]
      → strategy.py: evaluate() / kelly_stake()        [SAME functions as live]
      → simulated ledger: place bet now, settle later once result for date D is revealed
  → backtest/metrics.py: ROI, drawdown, CLV
  → backtests/<run_id>/report + ledger (kept separate from live state/)
```

### Key leakage-safety rules (specific to this domain)

1. **Never let one model serve the whole backtest period.** Retrain walk-forward (expanding or rolling window) on a fixed cadence; a model trained on 2022–2025 cannot be validly used to "backtest" a 2023 date it may have been trained on.
2. **Filter by date, not by row order.** `features.py` must accept an `as_of` cutoff and filter *all* upstream data (games, injuries) to `game_date < as_of` before computing rolling stats — not merely rely on `shift(1)` within an already-historical DataFrame, since the backtest will hand it a full multi-season DataFrame that includes rows *after* the cutoff.
3. **Simulate realistic bet-placement timing for odds, not closing lines.** Decide a fixed offset before tipoff (matching whenever the live bot actually runs, e.g. "odds as of the morning of game day") and always sample the historical odds snapshot at that same offset — using closing-line odds in the backtest overstates or understates edge versus what the live bot could ever actually see.
4. **Reveal game results only after the bet decision is recorded**, even though the backtest obviously has the final result on disk already — the engine's control flow should mirror live timing (decide → later settle), not compute value/EV using a results column that's already in scope.
5. **Injury/availability data must also be as-of-aware.** The current `05_skadefilter.py` looks at "last 3 games" relative to *today* — the backtest equivalent must look at the 3 games before the *simulated* date, not use the live "today" concept.
6. **Treat missing historical odds honestly.** If The Odds API's historical endpoint doesn't have a snapshot for a given game/date/book, skip that game in the backtest rather than substituting a nearby-in-time snapshot from after the cutoff.

## Scaling Considerations

This is a single-user, once-a-day system — traditional "users" scaling is not the relevant axis. The dimension that actually grows is **backtest iteration volume** (how many times you re-run history while tuning) and **historical data volume** (more seasons, more books).

| Scale | Architecture Adjustments |
|-------|---------------------------|
| Current (1 model, a few backtest runs) | Flat files (CSV/pickle/JSON) are fine; cache historical odds snapshots to disk once fetched (Odds API historical calls cost quota) so repeated backtest runs don't re-fetch |
| Iterating on strategy params frequently (dozens of backtest runs/week) | Separate the *expensive* part (feature/model computation per as-of date) from the *cheap* part (strategy threshold sweep) — precompute and cache `(as_of_date, features, model_prob)` once, then run many `strategy.py` parameter sweeps against that cache without recomputing features/retraining each time |
| Multiple seasons + multiple sports/markets later | Bet ledger schema outgrows flat JSON once you want to query "ROI by odds bucket by season by market" — SQLite (still zero-ops, still solo-friendly) becomes worth it before a real DB/service does |

### Scaling Priorities

1. **First bottleneck:** Historical odds API quota/cost during backtest development — mitigate by caching every historical snapshot fetched to a local file/SQLite table keyed by `(game, book, snapshot_time)`, so backtests are replayable offline after the first fetch.
2. **Second bottleneck:** Backtest wall-clock time from walk-forward retraining — mitigate by decoupling "compute predictions for every historical date" (slow, run once, cache) from "sweep strategy thresholds against cached predictions" (fast, run many times) — see Pattern 1's engine, split into a `predict` pass and a `simulate` pass if threshold-tuning iteration speed becomes a problem.

## Anti-Patterns

### Anti-Pattern 1: Backtesting with a single model trained on the full (or overlapping) date range

**What people do:** Reuse the one pickled model (trained once on all available history) to "backtest" the strategy across that same history, only varying the value threshold / odds filter / stake size.
**Why it's wrong:** The model has already seen the outcomes of the very games being "backtested" (directly, if in its training set, or indirectly, since team rolling-form features for date D depend on data the model implicitly calibrated against). Any ROI number produced this way is not evidence the strategy would have worked — it's evidence the model memorized patterns in data it was trained on. This is the most damaging and least visible form of lookahead bias in this specific project, because the model training pipeline already looks leakage-safe at the *feature* level (`shift(1)` is correctly used), which can create false confidence that leakage isn't possible.
**Do this instead:** Walk-forward retrain (Pattern 1) — every backtest prediction must come from a model that only saw data strictly before that prediction's date.

### Anti-Pattern 2: Duplicating feature/decision logic "just for the backtest, to keep it simple"

**What people do:** Write a standalone `backtest.py` script that reimplements feature engineering and value/EV logic inline (fast to write, no refactor needed) rather than extracting shared modules first.
**Why it's wrong:** This project has already experienced this exact failure mode twice — feature logic duplicated between `02_feature_engineering.py`/`04_value_detector.py`, and team-name lookup duplicated across four files. Adding a backtest as a *third* independent implementation of the same logic guarantees a third drift point, and worse, makes the backtest's results non-representative of what the live bot would actually do (defeating its entire purpose).
**Do this instead:** Extract `features.py`, `strategy.py`, `teams.py` as shared modules *before* writing the backtest engine, and add the parity test (Pattern 2) so future changes can't silently diverge again.

### Anti-Pattern 3: Using closing-line or same-day-average odds for historical backtest scoring

**What people do:** Pull "the odds for this game" from the historical endpoint without pinning a specific pre-tipoff snapshot time, often defaulting to whatever's easiest to query (closing line, or an average across the day).
**Why it's wrong:** Closing lines are the market's most-informed price — betting against them looks artificially profitable in backtest (the "beat the closing line" edge doesn't exist if you could only ever have bet at the earlier, softer line the live bot actually sees each morning) or artificially unprofitable if the backtest instead systematically picks a worse snapshot than the live bot would realistically catch.
**Do this instead:** Fix one realistic pre-tipoff offset that matches when the live bot actually runs (Data Flow rule 3) and use it consistently for every backtested bet.

### Anti-Pattern 4: Keeping backtest and live bankroll/ledger state in the same files

**What people do:** Point the backtest engine's ledger writer at the same `bankroll.json`/`bets.json` the live bot reads, "just to reuse the existing settlement code."
**Why it's wrong:** A backtest run overwriting or appending to the real paper-trading ledger corrupts the one piece of ground-truth evidence (`PROJECT.md`'s "Core Value": validated ROI) this whole project exists to produce.
**Do this instead:** Separate `state/` (live, real) from `backtests/<run_id>/` (simulated, disposable/reproducible) at the directory level, even though both use the same `ledger.py` code (parameterized by output path).

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|----------------------|-------|
| `nba_api` (unofficial NBA stats API) | Wrapped in `data/games.py`/`data/injuries.py`, rate-limited with `time.sleep()` (already the case today) | For backtesting, historical box scores are just past rows of the same endpoint — no separate "historical mode" needed here, only the `as_of` filtering in `features.py` matters |
| The Odds API — live odds | `data/odds.py::fetch_live_odds()` | Existing behavior; key must move to environment variable (`PROJECT.md` flags the current hardcoded key as a leaked-secret risk, unrelated to but should be fixed alongside this refactor) |
| The Odds API — historical odds | `data/odds.py::fetch_historical_odds(date, offset_hours)` | Separate, rate-limited/paid endpoint; cache every response fetched (local file or SQLite) since re-running backtests shouldn't re-spend quota; must return the *same normalized schema* as the live fetch so `strategy.py` doesn't need to know which one it received |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|----------------|-------|
| `data/*` ↔ `features.py`/`model.py`/`strategy.py` | Direct function calls, DataFrames/dataclasses in memory | No more CSV-file-as-API-contract between stages for the decision core — file-based handoff is fine for large training artifacts (`nba_features.csv`) but the backtest/live decision path should not round-trip through disk between every step the way `06_bot.py`'s subprocess calls do today |
| `backtest/engine.py` / `live/bot.py` ↔ shared core | Both import `features.py`, `model.py`, `strategy.py`, `teams.py` directly (no subprocess boundary) | This is the change that most directly fixes the "process-boundary coupling" anti-pattern already flagged in `.planning/codebase/ARCHITECTURE.md` (`06_bot.py` currently shells out to `04_value_detector.py`/`05_skadefilter.py` and can only observe exit codes + stderr text) |
| `ledger.py` ↔ storage | JSON files for live (`state/`), JSON or SQLite for backtest runs (`backtests/<run_id>/`) | Keep the interface the same (`place()`, `settle()`, `report()`) regardless of backing store, so `dashboard.py` can render either |

## Suggested Build Order (for roadmap)

1. **Extract shared core first:** `teams.py`, `features.py` (with `as_of` parameter), `strategy.py` (pure functions) — with unit tests, including the leakage regression test (Pattern 2). This alone fixes two of the four anti-patterns already documented and is a prerequisite for everything below (building the backtest against duplicated logic just creates a third drift point).
2. **Fix the flagged hygiene issues alongside the extraction, not after:** move the API key to an environment variable, get `modell_utils.py`'s replacement tracked in git — cheap to do while those files are already being touched.
3. **Refactor the live path to import the shared core** (`live/bot.py` calling `features.py`/`strategy.py` directly instead of subprocessing `04_value_detector.py`/`05_skadefilter.py`). Do this *before or alongside* building the backtest, not after — if the live path isn't updated to use the shared modules, the backtest is validating logic the live bot doesn't actually run, reintroducing the original drift problem in a new form.
4. **Build the historical-odds acquisition/caching layer** (`data/odds.py::fetch_historical_odds`) — this is a hard dependency for the backtest engine and is rate-limited/costly, so get the caching right early.
5. **Build the walk-forward backtest engine** (`backtest/engine.py`, `backtest/metrics.py`) using the now-shared `features.py`/`model.py`/`strategy.py` — including walk-forward retraining (Pattern 1/Anti-Pattern 1), since this is the step that actually answers "is this a threshold problem or a deeper model/feature problem."
6. **Only after the backtest engine exists and runs, use it to investigate root cause** (per `PROJECT.md`'s Active requirement) and to select validated strategy parameters — this should not happen out of order, since any threshold tuning done before the backtest exists is exactly the "guessing again" failure mode the project is trying to avoid.

## Sources

- [How To Avoid Bias in Backtesting](https://fortraders.com/blog/how-to-avoid-bias-in-backtesting) — MEDIUM confidence, general trading context, principles transfer directly to sports-odds backtesting
- [Understanding Look-Ahead Bias and How to Avoid It in Trading Strategies](https://www.marketcalls.in/machine-learning/understanding-look-ahead-bias-and-how-to-avoid-it-in-trading-strategies.html) — MEDIUM confidence
- [Freqtrade — Lookahead analysis](https://www.freqtrade.io/en/stable/lookahead-analysis/) — MEDIUM-HIGH confidence; official docs of a widely-used solo/small-team-maintained open-source trading bot, directly comparable in scale/architecture to this project (shared strategy code path for backtest and live)
- [NautilusTrader](https://nautilustrader.io/) — HIGH confidence for the "shared engine semantics between backtest and live" architectural principle (official project description)
- [QuantConnect / LEAN — Backtesting docs](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting) — HIGH confidence for the same shared-code principle at larger scale
- [QuantStart — Backtesting Systematic Trading Strategies in Python](https://www.quantstart.com/articles/backtesting-systematic-trading-strategies-in-python-considerations-and-open-source-frameworks/) — MEDIUM confidence, event-driven backtester rationale
- Project-internal: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`, `.planning/PROJECT.md` — source of the existing anti-patterns (duplicated team lookup, duplicated feature logic, subprocess coupling, no `as_of` concept anywhere) this research addresses directly

---
*Architecture research for: solo-maintained Python sports-betting value-detection + historical-backtesting system*
*Researched: 2026-08-19*
