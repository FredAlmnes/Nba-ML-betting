# Technology Stack

**Analysis Date:** 2026-08-19

## Languages

**Primary:**
- Python 3 - entire pipeline (`01_hent_data.py`, `02_feature_engineering.py`, `03_tren_modell.py`, `04_value_detector.py`, `05_skadefilter.py`, `06_bot.py`, `modell_utils.py`, `debug_kamp.py`)

**Secondary:**
- HTML/CSS/JavaScript - `dashboard.html` is a single, self-contained file generated as a Python f-string inside `06_bot.py` (`generer_dashboard()`, `06_bot.py:323-961`). No separate frontend source files, no bundler, no npm project. `dashboard_tom.html` is a static empty-state template committed alongside it.

There is no `package.json`, no Node.js runtime, and no client-side build tooling anywhere in the repo — the "frontend" is a plain HTML string written to disk by Python.

## Runtime

**Environment:**
- Python 3.14.3 per the committed `venv/pyvenv.cfg` (`home = /opt/homebrew/opt/python@3.14/bin`), built with Homebrew's `python@3.14`.
- **Inconsistency:** `venv/lib/` contains site-packages for three different Python versions simultaneously — `python3.10`, `python3.11`, and `python3.14` (`venv/lib/`). The active venv is 3.14, but `06_bot.py:233` hardcodes a `python3.10` site-packages path when constructing `PYTHONPATH` for subprocess calls to `04_value_detector.py` and `05_skadefilter.py`:
  ```python
  venv_site = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "lib", "python3.10", "site-packages")
  ```
  This is a latent version-mismatch risk (see CONCERNS.md if generated).

**Package Manager:**
- pip (no version pinned)
- Lockfile: missing. Only `requirements.txt` with loose `>=` bounds; no `requirements-lock.txt`, `Pipfile.lock`, or `poetry.lock`. Installed versions in the committed `venv/` (found via `venv/lib/python3.14/site-packages/*.dist-info`) are newer than the floors in `requirements.txt` — e.g. `nba_api` 1.11.4 vs `>=1.4.0` required, `xgboost` 3.2.0 vs `>=2.0.0`, `pandas` 3.0.1 vs `>=2.0.0`, `scikit-learn` 1.8.0 vs `>=1.3.0`, `numpy` 2.4.3 vs `>=1.24.0`, `requests` 2.33.0 vs `>=2.31.0`.
- Note: the `venv/` directory itself is committed to the repo (large binary/site-packages tree under version control), along with build-artifact-looking directories `_linux_pkgs/`, `_pip_home/`, `_pip_tmp/`, `_wheels/`, and a 100MB `_test.bin` at repo root.

## Frameworks

**Core:**
- xgboost `XGBClassifier` (`03_tren_modell.py:79`) - gradient-boosted trees for win-probability prediction
- scikit-learn `IsotonicRegression` (`03_tren_modell.py:19,142`) - post-hoc probability calibration wrapped by `modell_utils.KalibrertModell`
- pandas / numpy - used throughout for all data loading, feature engineering, and CSV I/O

**Testing:**
- None detected. No `pytest`, `unittest`, or test files/config anywhere in the repo (`ad hoc` script `debug_kamp.py` is a manual debugging script, not an automated test).

**Build/Dev:**
- None detected. No linter config (no `.eslintrc`, no `ruff`/`flake8`/`black` config), no CI config (no `.github/workflows`), no `Makefile`.

## Key Dependencies

**Critical:**
- `nba_api` (`requirements.txt:1`) - unofficial wrapper around stats.nba.com endpoints; used in `01_hent_data.py`, `04_value_detector.py`, `05_skadefilter.py`, `06_bot.py` for historical games, live team/player stats, and result verification. Free, no API key, but rate-limited (scripts add manual `time.sleep()` calls between calls, e.g. `01_hent_data.py:48`, `04_value_detector.py:99`, `05_skadefilter.py:49`).
- `xgboost` - model training (`03_tren_modell.py`) and inference (`04_value_detector.py`).
- `scikit-learn` - `IsotonicRegression` calibration and `accuracy_score`/`log_loss`/`brier_score_loss` metrics (`03_tren_modell.py`).
- `requests` - HTTP client for The Odds API (`04_value_detector.py:17,61`).
- `pandas`/`numpy` - dataframe manipulation across every script; also used for feature rolling-window calculations (`02_feature_engineering.py`).

**Infrastructure:**
- `pickle` (stdlib) - model persistence to `nba_modell.pkl` (`03_tren_modell.py:168-172`, loaded in `04_value_detector.py:40-41`). Requires `modell_utils.KalibrertModell` to be importable at unpickle time.
- `json` (stdlib) - persistence for `bankroll.json` and `bets.json` state files (`06_bot.py:59-65`).
- `subprocess` (stdlib) - `06_bot.py:229-246` shells out to run `04_value_detector.py` and `05_skadefilter.py` as separate processes rather than importing them as modules.

## Configuration

**Environment:**
- No `.env` file usage in code (no `os.environ` reads for secrets, no `python-dotenv`). The only `os.environ` usage is `06_bot.py:232`, which copies the current environment to pass to subprocesses (adding `PYTHONPATH`), not to read config.
- `.gitignore` excludes `.env` preemptively, but it is not actually used.
- **Secret handling concern:** The Odds API key is hardcoded directly as a Python literal in `04_value_detector.py` (`API_NØKKEL = "..."`, line 30) rather than loaded from an environment variable or secrets file. See INTEGRATIONS.md.

**Build:**
- No build config exists. `requirements.txt` is the only "config" artifact; it is 6 lines, unpinned (`>=` only).

## Platform Requirements

**Development:**
- macOS (Homebrew-based Python install path in `venv/pyvenv.cfg`), Python 3.10–3.14 compatible (venv shows artifacts of multiple interpreter versions).
- Manual, sequential script execution per `KOMME_I_GANG.md`: `01_hent_data.py` → `02_feature_engineering.py` → `03_tren_modell.py` → `04_value_detector.py` → (`05_skadefilter.py`) → `06_bot.py`.
- No containerization (no `Dockerfile`, no `docker-compose.yml`).

**Production:**
- No deployment target configured. `06_bot.py` is designed to be run "daily" (per its own docstring, `06_bot.py:12-13`) but there is no cron job, systemd timer, GitHub Action, or scheduler defined in the repo (`crontab -l` on this machine returns empty). Running the daily bot is a manual, external operational step.
- Output artifacts are local files only: `bankroll.json`, `bets.json`, `dashboard.html` (opened manually in a browser per `06_bot.py:1031`), and various CSVs (`nba_kamper_raw.csv`, `nba_features.csv`, `value_bets_idag.csv`, `value_bets_med_skadefilter.csv`). All of these are gitignored except the two markdown/txt report files at the repo root.

---

*Stack analysis: 2026-08-19*
