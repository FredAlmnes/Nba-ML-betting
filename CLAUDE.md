<!-- GSD:project-start source:PROJECT.md -->
## Project

**NBA Value Betting Bot**

A personal, paper-trading NBA moneyline value-betting system: it trains a calibrated XGBoost model on historical NBA team stats, compares model-implied win probabilities against live bookmaker odds to flag "value" bets, filters out bets where a key player is injured, and tracks a virtual bankroll with half-Kelly stake sizing. No real money is at risk yet — it's a single-user research/validation project run manually or via a daily script.

**Core Value:** The bot must demonstrate a **positive, validated ROI over a proper historical backtest** before it's trusted with anything beyond paper trading. Win rate or model accuracy alone don't matter if the actual betting strategy (value threshold + staking + filters) doesn't make money against real historical odds.

### Constraints

- **Scope**: Moneyline only for v1 — spread/totals explicitly deferred, not because they're hard but to keep validation focused on one strategy at a time.
- **Risk**: No real-money betting until backtested + paper-traded evidence of positive ROI exists — this is a hard gate, not a suggestion.
- **Data**: Historical odds backtesting depends on The Odds API's historical endpoint (rate limits / API cost apply — same key that needs rotating).
- **Language/style**: Existing codebase uses Norwegian identifiers and comments throughout; new/modified code should stay consistent with this unless a decision is made to deviate.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3 - entire pipeline (`01_hent_data.py`, `02_feature_engineering.py`, `03_tren_modell.py`, `04_value_detector.py`, `05_skadefilter.py`, `06_bot.py`, `modell_utils.py`, `debug_kamp.py`)
- HTML/CSS/JavaScript - `dashboard.html` is a single, self-contained file generated as a Python f-string inside `06_bot.py` (`generer_dashboard()`, `06_bot.py:323-961`). No separate frontend source files, no bundler, no npm project. `dashboard_tom.html` is a static empty-state template committed alongside it.
## Runtime
- Python 3.14.3 per the committed `venv/pyvenv.cfg` (`home = /opt/homebrew/opt/python@3.14/bin`), built with Homebrew's `python@3.14`.
- **Inconsistency:** `venv/lib/` contains site-packages for three different Python versions simultaneously — `python3.10`, `python3.11`, and `python3.14` (`venv/lib/`). The active venv is 3.14, but `06_bot.py:233` hardcodes a `python3.10` site-packages path when constructing `PYTHONPATH` for subprocess calls to `04_value_detector.py` and `05_skadefilter.py`:
- pip (no version pinned)
- Lockfile: missing. Only `requirements.txt` with loose `>=` bounds; no `requirements-lock.txt`, `Pipfile.lock`, or `poetry.lock`. Installed versions in the committed `venv/` (found via `venv/lib/python3.14/site-packages/*.dist-info`) are newer than the floors in `requirements.txt` — e.g. `nba_api` 1.11.4 vs `>=1.4.0` required, `xgboost` 3.2.0 vs `>=2.0.0`, `pandas` 3.0.1 vs `>=2.0.0`, `scikit-learn` 1.8.0 vs `>=1.3.0`, `numpy` 2.4.3 vs `>=1.24.0`, `requests` 2.33.0 vs `>=2.31.0`.
- Note: the `venv/` directory itself is committed to the repo (large binary/site-packages tree under version control), along with build-artifact-looking directories `_linux_pkgs/`, `_pip_home/`, `_pip_tmp/`, `_wheels/`, and a 100MB `_test.bin` at repo root.
## Frameworks
- xgboost `XGBClassifier` (`03_tren_modell.py:79`) - gradient-boosted trees for win-probability prediction
- scikit-learn `IsotonicRegression` (`03_tren_modell.py:19,142`) - post-hoc probability calibration wrapped by `modell_utils.KalibrertModell`
- pandas / numpy - used throughout for all data loading, feature engineering, and CSV I/O
- None detected. No `pytest`, `unittest`, or test files/config anywhere in the repo (`ad hoc` script `debug_kamp.py` is a manual debugging script, not an automated test).
- None detected. No linter config (no `.eslintrc`, no `ruff`/`flake8`/`black` config), no CI config (no `.github/workflows`), no `Makefile`.
## Key Dependencies
- `nba_api` (`requirements.txt:1`) - unofficial wrapper around stats.nba.com endpoints; used in `01_hent_data.py`, `04_value_detector.py`, `05_skadefilter.py`, `06_bot.py` for historical games, live team/player stats, and result verification. Free, no API key, but rate-limited (scripts add manual `time.sleep()` calls between calls, e.g. `01_hent_data.py:48`, `04_value_detector.py:99`, `05_skadefilter.py:49`).
- `xgboost` - model training (`03_tren_modell.py`) and inference (`04_value_detector.py`).
- `scikit-learn` - `IsotonicRegression` calibration and `accuracy_score`/`log_loss`/`brier_score_loss` metrics (`03_tren_modell.py`).
- `requests` - HTTP client for The Odds API (`04_value_detector.py:17,61`).
- `pandas`/`numpy` - dataframe manipulation across every script; also used for feature rolling-window calculations (`02_feature_engineering.py`).
- `pickle` (stdlib) - model persistence to `nba_modell.pkl` (`03_tren_modell.py:168-172`, loaded in `04_value_detector.py:40-41`). Requires `modell_utils.KalibrertModell` to be importable at unpickle time.
- `json` (stdlib) - persistence for `bankroll.json` and `bets.json` state files (`06_bot.py:59-65`).
- `subprocess` (stdlib) - `06_bot.py:229-246` shells out to run `04_value_detector.py` and `05_skadefilter.py` as separate processes rather than importing them as modules.
## Configuration
- No `.env` file usage in code (no `os.environ` reads for secrets, no `python-dotenv`). The only `os.environ` usage is `06_bot.py:232`, which copies the current environment to pass to subprocesses (adding `PYTHONPATH`), not to read config.
- `.gitignore` excludes `.env` preemptively, but it is not actually used.
- **Secret handling concern:** The Odds API key is hardcoded directly as a Python literal in `04_value_detector.py` (`API_NØKKEL = "..."`, line 30) rather than loaded from an environment variable or secrets file. See INTEGRATIONS.md.
- No build config exists. `requirements.txt` is the only "config" artifact; it is 6 lines, unpinned (`>=` only).
## Platform Requirements
- macOS (Homebrew-based Python install path in `venv/pyvenv.cfg`), Python 3.10–3.14 compatible (venv shows artifacts of multiple interpreter versions).
- Manual, sequential script execution per `KOMME_I_GANG.md`: `01_hent_data.py` → `02_feature_engineering.py` → `03_tren_modell.py` → `04_value_detector.py` → (`05_skadefilter.py`) → `06_bot.py`.
- No containerization (no `Dockerfile`, no `docker-compose.yml`).
- No deployment target configured. `06_bot.py` is designed to be run "daily" (per its own docstring, `06_bot.py:12-13`) but there is no cron job, systemd timer, GitHub Action, or scheduler defined in the repo (`crontab -l` on this machine returns empty). Running the daily bot is a manual, external operational step.
- Output artifacts are local files only: `bankroll.json`, `bets.json`, `dashboard.html` (opened manually in a browser per `06_bot.py:1031`), and various CSVs (`nba_kamper_raw.csv`, `nba_features.csv`, `value_bets_idag.csv`, `value_bets_med_skadefilter.csv`). All of these are gitignored except the two markdown/txt report files at the repo root.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Overview
## Naming Patterns
- Pipeline steps are numbered scripts run in sequence: `01_hent_data.py`, `02_feature_engineering.py`,
- One-off/debug scripts live at repo root without a number prefix, e.g. `debug_kamp.py`.
- Shared code that multiple numbered scripts import goes in a plain-named module,
- All variable/function names, comments, print output, and docstrings are written in
- Third-party library/API names and their own field names stay in English as-is
- `snake_case`, Norwegian verbs/nouns: `les_bankroll()`, `lagre_json()`, `beregn_innsats()`,
- Private/internal helpers prefixed with a single underscore when local to a script,
- Norwegian special characters (æ, ø, å) are used freely in identifiers where natural,
- `snake_case` throughout, e.g. `feature_kolonner`, `maal_kolonne`, `value_bets`, `kamp_dato_rad`.
- Norwegian domain vocabulary is used consistently for the same concept across files —
- Constant-like config values are `UPPER_SNAKE_CASE` at module top, e.g.
- Aligned assignment/dict-literal spacing is used deliberately for readability — extra
- `PascalCase`, Norwegian, e.g. `KalibrertModell` (`modell_utils.py`). Only one class exists
## Code Style
- No formatter (no Black/Ruff/autopep8 config present). Style is hand-maintained but fairly
- No type hints are used anywhere in the codebase (`def beregn_innsats(saldo, modell_prob, odds):`
- No linter config exists (no `.flake8`, `ruff.toml`, `pyproject.toml`). No enforced rule set —
- Every script divides its logic into numbered steps using a comment banner pattern:
- Every script/module opens with a triple-quoted docstring explaining, in Norwegian, what the
- Scripts are designed to be run interactively/manually and narrate their own progress via
- Emoji are used in `06_bot.py` and `05_skadefilter.py` print statements as status indicators:
## Import Organization
## Error Handling
- Broad `try/except Exception` around external API calls, returning a sentinel (`None` or an
- HTTP failures are checked via status code, not exceptions, and terminate the script with a
- Missing-file errors use `try/except FileNotFoundError` with a user-facing instruction message,
- `06_bot.py` treats subprocess failures from `04_value_detector.py`/`05_skadefilter.py` as
- No custom exception classes exist anywhere in the codebase. No `raise` statements were
## Logging
- f-strings for all interpolated output: `print(f"Fant {len(alle_lag)} lag")`.
- Numeric formatting is applied inline for readability: `.1%` for percentages
- Section headers use `"=" * 60` or `"─" * 50` separators printed before major output blocks,
## Comments
- Comments explain *why*, not *what* — especially around ML/finance pitfalls, e.g.
- Inline trailing comments annotate config constants with their practical meaning, e.g.
- Dated "bugfix" comments are used to record historical gotchas directly in code rather than
- Function docstrings are short, Norwegian, and explain purpose + return contract, e.g.
- No JSDoc-equivalent/type annotation convention (Python, no type hints, no Sphinx/Google-style
## Function Design
## Module Design
- Tabular data between pipeline stages: CSV via `pandas.DataFrame.to_csv(..., index=False)`
- Trained model artifact: `pickle`, saved as a dict with named keys, not the bare model —
- Application/runtime state (bot bankroll + bet history): JSON via small `les_json`/`lagre_json`
## Secrets / Configuration
- No `.env` / environment-variable based config is used. The Odds API key lives as a plain
- `.gitignore` excludes generated/personal data (`venv/`, `__pycache__/`, `*.pyc`, `.env`,
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Overview
```text
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
- **Stage boundary = CSV/JSON/pickle file on disk.** Every stage reads the previous stage's output file from the working directory and writes its own output file; there is no in-memory hand-off between stages except within `06_bot.py`, which shells out via `subprocess.run` and then re-reads the resulting CSV.
- **No web server, no long-running process.** `06_bot.py` is meant to be invoked once per day (e.g. via cron/Task Scheduler) and exits after writing state + regenerating `dashboard.html`, which is a static, self-contained HTML file opened manually in a browser.
- **Norwegian identifiers throughout.** Function/variable names, docstrings, and print statements are in Norwegian (e.g., `hent_data`, `lagstats`, `beregn_innsats`, `kjør_pipeline`). Any new code should follow this convention to stay consistent.
- **Heavy inline documentation.** Scripts are written pedagogically, with numbered section comments (`# --- 1. ... ---`) explaining ML/betting concepts (data leakage, time-series split, Kelly criterion) directly above the relevant code.
## Layers
- Purpose: Talk to `nba_api` (historical + live stats) and The Odds API (live bookmaker odds)
- Location: `01_hent_data.py`, `04_value_detector.py` (odds + fresh stats fetch), `05_skadefilter.py` (player stats fetch), `06_bot.py::hent_kampresultat`, `debug_kamp.py`
- Contains: HTTP/SDK calls, rate-limit `time.sleep()` calls, team-name lookup dictionaries built from `nba_api.stats.static.teams`
- Depends on: `nba_api` package, `requests` (for The Odds API), network access
- Used by: feature engineering and value-detection stages
- Purpose: Turn raw per-game rows into model-ready numeric features with no future-data leakage
- Location: `02_feature_engineering.py` (offline/historical), inline feature-building block in `04_value_detector.py` (live/online — must mirror the same column names and stat set as `02`)
- Contains: `pandas` groupby/rolling/shift transforms, differential (`DIFF_*`) feature construction
- Depends on: raw CSV columns and naming conventions established in `01_hent_data.py`
- Used by: model training (`03`) and scoring (`04`) — **the feature set (`stats` list, `HJEMME_RULL_*`/`BORTE_RULL_*`/`DIFF_*` naming) is duplicated between `02_feature_engineering.py` and `04_value_detector.py` and must be kept in sync manually**
- Purpose: Learn P(home team wins) and produce calibrated probabilities
- Location: `03_tren_modell.py` (training), `modell_utils.py` (the `KalibrertModell` wrapper class used both to train and to unpickle), `nba_modell.pkl` (serialized artifact — gitignored, regenerated locally)
- Contains: `xgboost.XGBClassifier`, `sklearn.isotonic.IsotonicRegression`
- Depends on: `nba_features.csv`
- Used by: `04_value_detector.py` (loads pickle, calls `predict_proba`)
- Purpose: Convert model probability + market odds into a value/EV signal and a filtered, injury-aware bet list
- Location: `04_value_detector.py`, `05_skadefilter.py`
- Contains: implied-probability normalization (removing vig), value threshold (`MIN_VALUE_TERSKEL`), odds-range filter (`MIN_ODDS`/`MAX_ODDS`), player-availability heuristic (top-3 minutes players present in last 3 games)
- Depends on: `nba_modell.pkl`, live odds API, live `nba_api` player stats
- Used by: `06_bot.py`
- Purpose: Daily entry point; owns persistent state (bankroll, bet ledger) and reporting
- Location: `06_bot.py`
- Contains: JSON read/write helpers (`les_json`/`lagre_json`), bet settlement (`sjekk_resultater`), half-Kelly stake sizing (`beregn_innsats`), subprocess orchestration (`kjør_pipeline`), bet placement with dedup (`plasser_bets`), HTML dashboard generation (`generer_dashboard`)
- Depends on: `04_value_detector.py`, `05_skadefilter.py` (invoked as subprocesses), `bankroll.json`, `bets.json`
- Used by: cron/manual daily invocation (`python 06_bot.py`)
## Data Flow
### Offline training path (run once / periodically to refresh the model)
### Daily operational path (triggered by running `06_bot.py`)
- All persistent state lives in two flat JSON files at the repo root: `bankroll.json` (current `saldo` + `historikk` time series) and `bets.json` (full list of bet records with `status` in `{"venter", "vant", "tapte"}`). There is no database. Concurrency is not handled — `06_bot.py` assumes single-process, single-invocation-per-day execution.
- Intermediate pipeline artifacts (`nba_kamper_raw.csv`, `nba_features.csv`, `nba_modell.pkl`, `value_bets_idag.csv`, `value_bets_med_skadefilter.csv`) are treated as disposable/regeneratable caches and are gitignored.
## Key Abstractions
- Purpose: Present a single object with a `predict_proba(X)` method that internally chains the raw XGBoost model's output through the fitted isotonic regressor, so downstream code (`04_value_detector.py`) doesn't need to know calibration happened
- Examples: `modell_utils.py:8-22`
- Pattern: Adapter/decorator around an sklearn-like estimator; must be importable wherever the pickle is unpickled (both `03_tren_modell.py` and `04_value_detector.py` import `KalibrertModell` from `modell_utils` for this reason)
- Purpose: Map free-text team names/nicknames/abbreviations (as returned by different APIs — `nba_api` vs. The Odds API) to a canonical `nba_api` team ID
- Examples: built ad hoc in `04_value_detector.py:117-123`, `05_skadefilter.py:168-172`, `06_bot.py:79-92`, `debug_kamp.py:13-16`
- Pattern: Not shared/centralized — each script rebuilds its own variant of this dictionary independently, with slightly different key sets (full name / nickname / abbreviation) and slightly different fuzzy-matching logic (substring containment). This duplication is a notable inconsistency risk (see CONCERNS.md if generated).
- Purpose: A plain dict representing one placed bet, shared between `bets.json`, the in-memory `bets` list in `06_bot.py`, and the dashboard's embedded JSON
- Fields: `dato`, `kamp_dato`, `kamp`, `bet`, `odds`, `innsats`, `modell`, `modell_prob`, `value`, `ev`, `status`, `gevinst`
- Pattern: No schema validation or dataclass — treated as a duck-typed dict throughout `06_bot.py:296-309`
## Entry Points
- Location: `06_bot.py:967` (`main()`, guarded by `if __name__ == "__main__":`)
- Triggers: Manual `python 06_bot.py` invocation or an external scheduler (cron/Task Scheduler) — no scheduler is defined in-repo
- Responsibilities: Full daily cycle — settle, fetch, filter, stake, persist, render dashboard
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
### Top-level module code instead of functions/`main()`
## Error Handling
- API/network failures: `04_value_detector.py:63-67` checks `respons.status_code != 200`, prints the error body, and calls `sys.exit(1)` (explicitly noted in a comment as important — bare `exit()` would return exit code 0 and hide the failure from `06_bot.py`'s subprocess-return-code check)
- Per-item failures inside loops are swallowed silently and skipped (e.g., `04_value_detector.py:143-150` skips a game if team IDs can't be resolved; `06_bot.py:135-136` catches broad `except Exception: return None` in `hent_kampresultat`)
- `05_skadefilter.py:41-53` wraps each `nba_api` call in a broad `try/except Exception as e:` that prints and returns an empty DataFrame, allowing the pipeline to continue with partial data rather than fail loudly
- Missing-file handling: `05_skadefilter.py:153-157` catches `FileNotFoundError` on `value_bets_idag.csv` and calls `exit()` with a instructive message telling the user to run `04_value_detector.py` first
## Cross-Cutting Concerns
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
