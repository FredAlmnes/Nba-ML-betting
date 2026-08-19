# Testing Patterns

**Analysis Date:** 2026-08-19

## Test Framework

**Runner:** None. No `pytest`, `unittest`, `nose`, or any other test runner is configured or
installed. `requirements.txt` lists only runtime dependencies (`nba_api`, `pandas`, `numpy`,
`scikit-learn`, `xgboost`, `requests`) — no test/dev dependencies.

**Assertion Library:** None.

**Config:** No `pytest.ini`, `pyproject.toml`, `tox.ini`, `setup.cfg`, or `conftest.py` exists
anywhere in the repository.

**Run Commands:** Not applicable — there is no automated test suite to run.

```bash
find . -iname "*test*" -not -path "*/venv/*"
# ./_test.bin        <- 100MB binary artifact from a prior pip/venv operation, not a test file
# ./test_write.tmp   <- empty temp file, not a test file
```

Neither of the two files matching `*test*` in the repo root is an actual test — they are
leftover scratch/temp artifacts (see CONCERNS if a concerns audit is run; `_test.bin` is a
104MB binary file and `test_write.tmp` is an empty 0-byte file, both currently untracked in git
status and likely safe to delete).

## Test File Organization

**Location:** None exists. There is no `tests/` directory, no `__tests__/` directory, and no
co-located `*_test.py` / `test_*.py` files.

**Naming:** Not applicable.

**Structure:** Not applicable.

## Verification Approach Actually Used

This codebase has **no automated tests**. Correctness is currently verified through three
informal, manual mechanisms — understand these before changing behavior, since they are the
only signal a change didn't break something:

**1. Print-narrated manual runs.**
Every pipeline script (`01_hent_data.py` through `06_bot.py`) prints its own progress and
intermediate results at each step (row counts, computed statistics, sample data previews).
A developer runs the script manually and eyeballs the printed output to confirm it behaved
as expected. Example from `01_hent_data.py`:
```python
print(f"\nTotalt {len(df)} rader hentet")
print("\nKolonner tilgjengelig:")
print(df.columns.tolist())
...
print("\nEksempel på data (første 5 rader):")
print(df[["GAME_DATE", "TEAM_ABBREVIATION", "MATCHUP", "WL", "PTS", "FG_PCT", "REB", "AST"]].head())
```
When adding new pipeline logic, follow this same pattern: print row counts and a `.head()`
preview after any transformation step, so a human running the script can visually confirm
correctness in lieu of an assertion.

**2. Model evaluation metrics as the "test" for the ML step.**
`03_tren_modell.py` computes accuracy, log-loss, and Brier score on a held-out time-series
test split, prints a before/after calibration comparison table, and prints a 10-bucket
calibration diagnostic (predicted probability vs. actual observed hit rate per bucket). This
is the closest thing to a regression check in the codebase — if a change to feature
engineering or model config degrades these numbers meaningfully versus previous runs (noted
by hand in `KALIBRERING_RAPPORT.md`), that is the signal something regressed. There is no
automated threshold/assertion on these metrics; a human reads the printed values.

**3. Standalone debug scripts for targeted manual investigation.**
`debug_kamp.py` is a purpose-built, throwaway-style script (not reused, not parameterized via
CLI args — values like `KAMP_DATO`, `HJEMME_LAG`, `BORTE_LAG` are hardcoded constants at the
top) used to manually investigate a specific data discrepancy (in this case, confirming an
NBA game result for a specific date via direct API queries). **Convention:** when debugging a
data/pipeline discrepancy, create a new small script in this same style (hardcoded constants
at top, direct API calls, plain `print()` output) rather than adding ad-hoc `print()` statements
into the numbered pipeline scripts and reverting them later.

## Mocking

**Framework:** None — no `unittest.mock`, `pytest-mock`, or `responses`/`vcr` HTTP-mocking
library is used anywhere. All scripts call live external services directly every time they
run (`nba_api` endpoints in `01`, `04`, `05`, `06`; The Odds API HTTP endpoint in `04`).

**What to Mock (if tests were introduced):** External network calls are the only real
candidates for mocking, and they are concentrated in a few functions, making them the natural
seam for future test isolation:
- `nba_api.stats.endpoints.leaguegamefinder.LeagueGameFinder(...)` — used in
  `01_hent_data.py`, `04_value_detector.py` (via `teamgamelogs`), `05_skadefilter.py`
  (via `leaguedashplayerstats`), `06_bot.py` (`hent_kampresultat()`).
- `requests.get(...)` against `https://api.the-odds-api.com/...` — used once in
  `04_value_detector.py`.
- `subprocess.run([sys.executable, "0N_script.py"], ...)` — used in `06_bot.py`'s
  `kjør_pipeline()` to invoke `04_value_detector.py` and `05_skadefilter.py` as
  child processes; this is itself a seam that would need mocking/stubbing to unit-test
  `kjør_pipeline()` in isolation.

**What NOT to Mock:** Pure data-transformation logic is currently untested but has no external
dependencies, making it the most valuable and easiest target if tests are ever added — e.g.
`beregn_lag_form()` (rolling stats, `02_feature_engineering.py`), `beregn_innsats()` (Kelly
criterion sizing, `06_bot.py`), `KalibrertModell.predict_proba()` (`modell_utils.py`). These
could be tested with plain in-memory DataFrames/floats and no mocking at all.

## Fixtures and Factories

**Test Data:** None exists — no `fixtures/` directory, no factory functions, no sample/golden
CSV files checked into git for testing purposes. The CSVs that do exist at repo root
(`nba_kamper_raw.csv`, `nba_features.csv`, `value_bets_idag.csv`,
`value_bets_med_skadefilter.csv`) are pipeline *outputs* (regenerated by running the scripts),
not test fixtures, and are excluded from git via `.gitignore`.

**Location:** Not applicable.

## Coverage

**Requirements:** None enforced. No coverage tool (`coverage.py`, `pytest-cov`) is installed
or configured. Current coverage is effectively 0% (no test suite exists to measure).

**View Coverage:** Not applicable.

## Test Types

**Unit Tests:** None exist. If introduced, the highest-value initial targets (pure functions,
no I/O) are:
- `beregn_lag_form()` in `02_feature_engineering.py` — verify `shift(1)` correctly prevents
  same-game data leakage and rolling window math is correct for a small synthetic DataFrame.
- `beregn_innsats()` (Kelly sizing) in `06_bot.py` — verify negative-edge returns `0.0`,
  min/max stake clamping (`MIN_INNSATS`/`MAX_INNSATS`) is respected, and the half-Kelly
  fraction (`KELLY_FRAKSJON`) is applied correctly.
- `KalibrertModell.predict_proba()` in `modell_utils.py` — verify it correctly wraps a stub
  model + stub calibrator and returns a two-column `[1-p, p]` array.
- `gjeldende_sesong()` / `_gjeldende_sesong()` (duplicated in `04_value_detector.py` and
  `05_skadefilter.py`) — verify the October season-rollover boundary logic
  (month >= 10 → `"{year}-{year+1 short}"`, else previous season) with a mocked "now".

**Integration Tests:** None exist. If introduced, the natural integration boundary is
file-based, matching the existing architecture: run script N against a small fixture input
CSV/JSON and assert on the output CSV/JSON it writes (e.g. feed `02_feature_engineering.py`
a tiny synthetic `nba_kamper_raw.csv` and assert `nba_features.csv` has the expected
`DIFF_*` columns and no leaked future data).

**E2E Tests:** Not used. The closest equivalent is manually running `06_bot.py` end-to-end
against live APIs and inspecting `dashboard.html` / `bankroll.json` / `bets.json` by eye.

## Common Patterns

**Async Testing:** Not applicable — no async code exists in the codebase (all I/O is
synchronous, using `time.sleep(...)` for API rate limiting rather than async concurrency,
e.g. `time.sleep(1)` in `01_hent_data.py`, `time.sleep(0.5)`/`time.sleep(0.6)` in
`04_value_detector.py`/`06_bot.py`).

**Error Testing:** Not applicable — no tests exist. Error paths (see CONVENTIONS.md's Error
Handling section) are currently only verified manually by observing printed output when a
script is run under a failure condition (e.g. missing `value_bets_idag.csv`, non-200 API
response, empty API result set).

## Recommendation for Introducing Tests

If test coverage is added to this project in a future phase, the pragmatic starting point
given the current architecture (flat scripts, file-based I/O between stages, heavy live
external API usage) is:
1. Add `pytest` to a new `requirements-dev.txt` (do not add it to `requirements.txt`, which is
   reserved for runtime deps per current convention).
2. Extract the pure-logic functions listed under "Unit Tests" above (`beregn_lag_form`,
   `beregn_innsats`, `KalibrertModell.predict_proba`, season-rollover logic) — these already
   have no I/O dependency and can be tested with in-memory data immediately, no mocking setup
   required.
3. Only after unit coverage exists, consider `responses`/`unittest.mock` for the `nba_api`
   and `requests` call sites listed under "Mocking" above.

---

*Testing analysis: 2026-08-19*
