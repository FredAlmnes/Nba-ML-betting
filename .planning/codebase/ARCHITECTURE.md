<!-- refreshed: 2026-08-19 -->
# Architecture

**Analysis Date:** 2026-08-19

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    OFFLINE TRAINING PIPELINE                 │
│                  (run manually, in order, once)               │
├──────────────────┬──────────────────┬───────────────────────┤
│  01_hent_data.py │ 02_feature_       │  03_tren_modell.py    │
│  (fetch raw      │ engineering.py    │  (train + calibrate   │
│   NBA game data) │ (rolling-window   │   XGBoost model)      │
│                   │  features)        │                       │
│  writes:          │ writes:           │  writes:              │
│  nba_kamper_      │ nba_features.csv  │  nba_modell.pkl       │
│  raw.csv          │                   │                       │
└────────┬──────────┴─────────┬─────────┴──────────┬────────────┘
         │                    │                     │
         ▼                    ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   DAILY OPERATIONAL PIPELINE                 │
│                (orchestrated by 06_bot.py via subprocess)     │
├───────────────────────────┬───────────────────────────────────┤
│  04_value_detector.py     │  05_skadefilter.py                │
│  (fetch live odds,        │  (cross-check top players'        │
│   score with nba_modell   │   recent minutes, flag injury     │
│   .pkl, flag value bets)  │   risk on value_bets_idag.csv)    │
│                            │                                    │
│  writes:                  │  writes:                          │
│  value_bets_idag.csv      │  value_bets_med_skadefilter.csv   │
└───────────────┬────────────┴───────────────────┬─────────────┘
                │                                 │
                ▼                                 ▼
┌─────────────────────────────────────────────────────────────┐
│  06_bot.py — orchestrator + stateful ledger + report          │
│  - settles yesterday's pending bets against NBA results       │
│  - runs 04 → 05 as subprocesses                                │
│  - sizes new bets with half-Kelly criterion                    │
│  - persists state to bankroll.json / bets.json                │
│  - renders self-contained dashboard.html (inline JS/CSS)       │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Data ingestion | Pull raw per-team-per-game box scores from `nba_api`, reshape to one row per game (home vs. away) | `01_hent_data.py` |
| Feature engineering | Compute leakage-safe rolling-window (last 10 games, `shift(1)`) team-form stats and home/away differential features | `02_feature_engineering.py` |
| Model training | Train XGBoost classifier with time-series train/test split, evaluate (accuracy/log-loss/Brier), fit isotonic calibrator, persist model | `03_tren_modell.py` |
| Calibration wrapper | Wrap raw XGBoost probabilities through isotonic regression behind a `predict_proba`-compatible interface | `modell_utils.py` |
| Value detection | Fetch live odds (The Odds API), fetch fresh team form, score with calibrated model, compute value/EV, flag bets, always rewrite output CSV | `04_value_detector.py` |
| Injury filter | Fetch league-wide player stats (last-3-games + season), identify each team's top-3 minutes players, flag bets where a key player is missing/limited | `05_skadefilter.py` |
| Orchestration & bankroll ledger | Settle pending bets, run 04→05 as subprocesses, size stakes via half-Kelly, dedupe against full bet history, persist JSON state, generate dashboard | `06_bot.py` |
| Debug utility | Ad hoc manual script to inspect NBA API results for a specific matchup/date | `debug_kamp.py` |

## Pattern Overview

**Overall:** Linear, file-based batch pipeline of standalone numbered scripts (`01_` → `06_`). Not a package, framework, or service — each script is a top-level executable module with side effects at import time (module-level code runs on `python NN_script.py`, no `if __name__ == "__main__"` guard except in `06_bot.py`).

**Key Characteristics:**
- **Stage boundary = CSV/JSON/pickle file on disk.** Every stage reads the previous stage's output file from the working directory and writes its own output file; there is no in-memory hand-off between stages except within `06_bot.py`, which shells out via `subprocess.run` and then re-reads the resulting CSV.
- **No web server, no long-running process.** `06_bot.py` is meant to be invoked once per day (e.g. via cron/Task Scheduler) and exits after writing state + regenerating `dashboard.html`, which is a static, self-contained HTML file opened manually in a browser.
- **Norwegian identifiers throughout.** Function/variable names, docstrings, and print statements are in Norwegian (e.g., `hent_data`, `lagstats`, `beregn_innsats`, `kjør_pipeline`). Any new code should follow this convention to stay consistent.
- **Heavy inline documentation.** Scripts are written pedagogically, with numbered section comments (`# --- 1. ... ---`) explaining ML/betting concepts (data leakage, time-series split, Kelly criterion) directly above the relevant code.

## Layers

**Data acquisition layer:**
- Purpose: Talk to `nba_api` (historical + live stats) and The Odds API (live bookmaker odds)
- Location: `01_hent_data.py`, `04_value_detector.py` (odds + fresh stats fetch), `05_skadefilter.py` (player stats fetch), `06_bot.py::hent_kampresultat`, `debug_kamp.py`
- Contains: HTTP/SDK calls, rate-limit `time.sleep()` calls, team-name lookup dictionaries built from `nba_api.stats.static.teams`
- Depends on: `nba_api` package, `requests` (for The Odds API), network access
- Used by: feature engineering and value-detection stages

**Feature engineering layer:**
- Purpose: Turn raw per-game rows into model-ready numeric features with no future-data leakage
- Location: `02_feature_engineering.py` (offline/historical), inline feature-building block in `04_value_detector.py` (live/online — must mirror the same column names and stat set as `02`)
- Contains: `pandas` groupby/rolling/shift transforms, differential (`DIFF_*`) feature construction
- Depends on: raw CSV columns and naming conventions established in `01_hent_data.py`
- Used by: model training (`03`) and scoring (`04`) — **the feature set (`stats` list, `HJEMME_RULL_*`/`BORTE_RULL_*`/`DIFF_*` naming) is duplicated between `02_feature_engineering.py` and `04_value_detector.py` and must be kept in sync manually**

**Model layer:**
- Purpose: Learn P(home team wins) and produce calibrated probabilities
- Location: `03_tren_modell.py` (training), `modell_utils.py` (the `KalibrertModell` wrapper class used both to train and to unpickle), `nba_modell.pkl` (serialized artifact — gitignored, regenerated locally)
- Contains: `xgboost.XGBClassifier`, `sklearn.isotonic.IsotonicRegression`
- Depends on: `nba_features.csv`
- Used by: `04_value_detector.py` (loads pickle, calls `predict_proba`)

**Decisioning / value-betting layer:**
- Purpose: Convert model probability + market odds into a value/EV signal and a filtered, injury-aware bet list
- Location: `04_value_detector.py`, `05_skadefilter.py`
- Contains: implied-probability normalization (removing vig), value threshold (`MIN_VALUE_TERSKEL`), odds-range filter (`MIN_ODDS`/`MAX_ODDS`), player-availability heuristic (top-3 minutes players present in last 3 games)
- Depends on: `nba_modell.pkl`, live odds API, live `nba_api` player stats
- Used by: `06_bot.py`

**Orchestration / state layer:**
- Purpose: Daily entry point; owns persistent state (bankroll, bet ledger) and reporting
- Location: `06_bot.py`
- Contains: JSON read/write helpers (`les_json`/`lagre_json`), bet settlement (`sjekk_resultater`), half-Kelly stake sizing (`beregn_innsats`), subprocess orchestration (`kjør_pipeline`), bet placement with dedup (`plasser_bets`), HTML dashboard generation (`generer_dashboard`)
- Depends on: `04_value_detector.py`, `05_skadefilter.py` (invoked as subprocesses), `bankroll.json`, `bets.json`
- Used by: cron/manual daily invocation (`python 06_bot.py`)

## Data Flow

### Offline training path (run once / periodically to refresh the model)

1. `01_hent_data.py` calls `nba_api` for 2022-23 through 2024-25 regular-season games, reshapes to one row per game with `_HJEMME`/`_BORTE` (home/away) suffixed columns, writes `nba_kamper_raw.csv` (`01_hent_data.py:100-102`)
2. `02_feature_engineering.py` reads `nba_kamper_raw.csv`, computes per-team rolling 10-game averages with `shift(1)` to prevent leakage (`02_feature_engineering.py:89-95`), builds `DIFF_*` differential features (`02_feature_engineering.py:132-136`), drops rows with insufficient history, writes `nba_features.csv`
3. `03_tren_modell.py` reads `nba_features.csv`, splits by date (last 2 months = test set) (`03_tren_modell.py:61-67`), trains `xgb.XGBClassifier`, evaluates, fits an `IsotonicRegression` calibrator on test-set predictions, wraps both in `KalibrertModell`, pickles to `nba_modell.pkl` (`03_tren_modell.py:166-172`)

### Daily operational path (triggered by running `06_bot.py`)

1. `06_bot.py::main()` loads `bankroll.json`/`bets.json` state (`06_bot.py:972-974`)
2. Settles any bets whose `kamp_dato` is in the past via `sjekk_resultater()`, which re-queries `nba_api.leaguegamefinder` for the actual result and updates `saldo`/bet status (`06_bot.py:141-195`)
3. `kjør_pipeline()` shells out to `04_value_detector.py` then `05_skadefilter.py` as subprocesses with an augmented `PYTHONPATH` (`06_bot.py:229-253`)
   - `04_value_detector.py` loads `nba_modell.pkl`, fetches today's odds and fresh team stats, scores each game, always overwrites `value_bets_idag.csv` (even when empty, to avoid stale-data reuse) (`04_value_detector.py:261-277`)
   - `05_skadefilter.py` reads `value_bets_idag.csv`, checks top-3-minutes players' recent availability per team, writes `value_bets_med_skadefilter.csv` with `Skadestatus`/`Skadeinfo` columns
4. `06_bot.py` reads back `value_bets_med_skadefilter.csv`, filters to `Skadestatus` containing `"OK"` (`06_bot.py:251-253`)
5. `plasser_bets()` dedupes against the full bet history (keyed on `(kamp, bet, kamp_dato)`), sizes each stake with half-Kelly (`beregn_innsats()`, `06_bot.py:202-222`), caps stake to `[MIN_INNSATS, MAX_INNSATS]`, appends to `bets` list, decrements in-memory `saldo` (`06_bot.py:256-316`)
6. State is persisted (`bankroll.json`, `bets.json`) and `generer_dashboard()` renders a single self-contained `dashboard.html` (inline CSS + Three.js visualization + embedded JSON) (`06_bot.py:323-960`)

**State Management:**
- All persistent state lives in two flat JSON files at the repo root: `bankroll.json` (current `saldo` + `historikk` time series) and `bets.json` (full list of bet records with `status` in `{"venter", "vant", "tapte"}`). There is no database. Concurrency is not handled — `06_bot.py` assumes single-process, single-invocation-per-day execution.
- Intermediate pipeline artifacts (`nba_kamper_raw.csv`, `nba_features.csv`, `nba_modell.pkl`, `value_bets_idag.csv`, `value_bets_med_skadefilter.csv`) are treated as disposable/regeneratable caches and are gitignored.

## Key Abstractions

**`KalibrertModell` (calibration wrapper):**
- Purpose: Present a single object with a `predict_proba(X)` method that internally chains the raw XGBoost model's output through the fitted isotonic regressor, so downstream code (`04_value_detector.py`) doesn't need to know calibration happened
- Examples: `modell_utils.py:8-22`
- Pattern: Adapter/decorator around an sklearn-like estimator; must be importable wherever the pickle is unpickled (both `03_tren_modell.py` and `04_value_detector.py` import `KalibrertModell` from `modell_utils` for this reason)

**Team lookup dictionary (`lag_oppslag`):**
- Purpose: Map free-text team names/nicknames/abbreviations (as returned by different APIs — `nba_api` vs. The Odds API) to a canonical `nba_api` team ID
- Examples: built ad hoc in `04_value_detector.py:117-123`, `05_skadefilter.py:168-172`, `06_bot.py:79-92`, `debug_kamp.py:13-16`
- Pattern: Not shared/centralized — each script rebuilds its own variant of this dictionary independently, with slightly different key sets (full name / nickname / abbreviation) and slightly different fuzzy-matching logic (substring containment). This duplication is a notable inconsistency risk (see CONCERNS.md if generated).

**Bet record (implicit schema, not a class):**
- Purpose: A plain dict representing one placed bet, shared between `bets.json`, the in-memory `bets` list in `06_bot.py`, and the dashboard's embedded JSON
- Fields: `dato`, `kamp_dato`, `kamp`, `bet`, `odds`, `innsats`, `modell`, `modell_prob`, `value`, `ev`, `status`, `gevinst`
- Pattern: No schema validation or dataclass — treated as a duck-typed dict throughout `06_bot.py:296-309`

## Entry Points

**`06_bot.py` (primary/only intended daily entry point):**
- Location: `06_bot.py:967` (`main()`, guarded by `if __name__ == "__main__":`)
- Triggers: Manual `python 06_bot.py` invocation or an external scheduler (cron/Task Scheduler) — no scheduler is defined in-repo
- Responsibilities: Full daily cycle — settle, fetch, filter, stake, persist, render dashboard

**Individual pipeline scripts (secondary/manual entry points):**
- `01_hent_data.py`, `02_feature_engineering.py`, `03_tren_modell.py`: run manually, in order, to (re)build the model from scratch; no `main()` guard, executes top-to-bottom on import
- `04_value_detector.py`, `05_skadefilter.py`: can be run manually and standalone (both read/write the same CSVs `06_bot.py` uses), or invoked as subprocesses by `06_bot.py`
- `debug_kamp.py`: standalone manual debugging script, not part of any automated flow, has a hardcoded matchup/date needing manual editing to reuse

## Architectural Constraints

- **Threading:** Entirely single-threaded, synchronous, sequential execution. No async/await, no worker threads, no queues.
- **Global state:** No in-process global mutable state beyond normal Python module-level variables (e.g. config constants like `API_NØKKEL`, `MIN_VALUE_TERSKEL` in `04_value_detector.py:30-33`, `KELLY_FRAKSJON`/`MAX_INNSATS` in `06_bot.py:33-38`). Actual "global state" is externalized to `bankroll.json`/`bets.json` on disk, which acts as the source of truth across runs.
- **Circular imports:** None — `modell_utils.py` is a leaf dependency imported by `03_tren_modell.py` and `04_value_detector.py` only.
- **Working-directory dependence:** All file I/O uses bare relative filenames (`"nba_modell.pkl"`, `"bankroll.json"`, etc.) rather than paths resolved from `__file__`, except the one `os.path.dirname(os.path.abspath(__file__))` usage in `06_bot.py:233` for `PYTHONPATH`. This means every script must be run with the repo root as the current working directory, or file I/O will fail/write to the wrong location.
- **Process-boundary coupling:** `06_bot.py` invokes `04_value_detector.py` and `05_skadefilter.py` via `subprocess.run([sys.executable, "04_value_detector.py"], ...)` rather than importing them as modules (`06_bot.py:235-243`). This is necessary because those scripts execute top-level code with no importable functions/guards, but it means errors are only visible through captured stderr text matching, and there's no typed return value — the only contract is "exit code 0 + a CSV file written to disk."
- **Feature-list duplication:** The feature engineering logic (which raw stats to average, which `DIFF_*` columns to build) is implemented twice — once in `02_feature_engineering.py` (historical/batch) and once inline in `04_value_detector.py` (live/online). Any change to the feature set requires updating both files identically or the model will silently receive a different feature schema at inference time than at training time.

## Anti-Patterns

### Duplicated team-name resolution logic

**What happens:** Four different scripts (`04_value_detector.py`, `05_skadefilter.py`, `06_bot.py`, `debug_kamp.py`) each independently rebuild a `lag_oppslag` (team lookup) dictionary from `nba_api.stats.static.teams`, with slightly different key normalization (lowercase full name only vs. full name + nickname + abbreviation) and different fuzzy-match fallback logic (`04_value_detector.py:116-123` vs. `05_skadefilter.py:167-172` vs. `06_bot.py:76-92`).
**Why it's wrong:** A mismatch between how The Odds API names teams and how `nba_api` names teams can silently fail in one script but not another, and any bug fix must be applied in up to four places.
**Do this instead:** Extract a single `hent_lag_oppslag()` / `finn_lag()` helper into `modell_utils.py` (which is already the shared module) and import it everywhere team-name resolution is needed.

### Top-level module code instead of functions/`main()`

**What happens:** `01_hent_data.py`, `02_feature_engineering.py`, `03_tren_modell.py`, `04_value_detector.py`, `05_skadefilter.py`, and `debug_kamp.py` all execute directly at module/import scope with no functions wrapping the logic and no `if __name__ == "__main__":` guard.
**Why it's wrong:** These scripts cannot be unit tested or imported without side effects (network calls, file writes, `sys.exit()`), and `06_bot.py` is forced to run them as opaque subprocesses instead of calling functions and getting typed return values/exceptions.
**Do this instead:** Follow the pattern already used in `06_bot.py` — wrap logic in functions and add `if __name__ == "__main__": main()` — so scripts remain runnable standalone but also become importable/testable/composable.

## Error Handling

**Strategy:** Minimal and inconsistent — mostly print-and-continue or print-and-exit, no custom exception types, no centralized error handling or logging.

**Patterns:**
- API/network failures: `04_value_detector.py:63-67` checks `respons.status_code != 200`, prints the error body, and calls `sys.exit(1)` (explicitly noted in a comment as important — bare `exit()` would return exit code 0 and hide the failure from `06_bot.py`'s subprocess-return-code check)
- Per-item failures inside loops are swallowed silently and skipped (e.g., `04_value_detector.py:143-150` skips a game if team IDs can't be resolved; `06_bot.py:135-136` catches broad `except Exception: return None` in `hent_kampresultat`)
- `05_skadefilter.py:41-53` wraps each `nba_api` call in a broad `try/except Exception as e:` that prints and returns an empty DataFrame, allowing the pipeline to continue with partial data rather than fail loudly
- Missing-file handling: `05_skadefilter.py:153-157` catches `FileNotFoundError` on `value_bets_idag.csv` and calls `exit()` with a instructive message telling the user to run `04_value_detector.py` first

## Cross-Cutting Concerns

**Logging:** None — all diagnostics go through `print()` statements with Norwegian text and emoji status markers (✅/⚠️/❌). No log levels, no log files, no structured logging.
**Validation:** None — no schema validation of CSV/JSON contents, no type checking beyond ad hoc `pd.notna()` checks before casting (`06_bot.py:280`, `06_bot.py:269`). Data shape mismatches between pipeline stages (e.g., a feature column renamed in `02` but not `04`) would surface only as a `KeyError` at runtime.
**Authentication:** A single hardcoded API key for The Odds API lives directly in source at `04_value_detector.py:30` (`API_NØKKEL = "..."`) rather than being loaded from an environment variable or `.env` file — this is a secrets-in-source-control risk, not just a convention gap.

---

*Architecture analysis: 2026-08-19*
