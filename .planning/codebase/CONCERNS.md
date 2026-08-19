# Codebase Concerns

**Analysis Date:** 2026-08-19

## Security Considerations

**Hardcoded API key committed to a PUBLIC GitHub repository:**
- Risk: `04_value_detector.py:30` defines `API_NØKKEL = "[REDACTED — see file]"` (The Odds API key) as a plaintext string literal. This value has been present since the initial commit (`c058a1a`) and is still in the current working tree/diff.
- Repo visibility: `git remote -v` shows `origin = https://github.com/FredAlmnes/Nba-ML-betting.git`, confirmed **PUBLIC** via `gh repo view`. The key is live and scrapable by anyone (and by GitHub secret-scanning bots) right now.
- Files: `04_value_detector.py:30`, referenced at `04_value_detector.py:54`. Also documented as the expected pattern in `KOMME_I_GANG.md:45` ("Lim inn API-nøkkelen din i `04_value_detector.py`") — i.e. the setup guide itself instructs users to hardcode secrets into tracked source rather than use an env var.
- Current mitigation: None. `.gitignore` already excludes `.env` (line 7 of `.gitignore`), so the pattern for keeping secrets out of git exists in the project but is unused for this key.
- Recommendations:
  1. Rotate the key immediately at the-odds-api.com (assume it is compromised).
  2. Read it from an environment variable (`os.environ["ODDS_API_KEY"]`) or a git-ignored `.env` file loaded via `python-dotenv`.
  3. Scrub the key from git history (`git filter-repo` / BFG) since it has been public since the first commit — a simple new commit does not remove it from history.
  4. Update `KOMME_I_GANG.md` to describe the env-var setup instead of "paste your key into the source file".

**Pickle-based model loading:**
- Risk: `04_value_detector.py:41` (`pickle.load`) and `06_bot.py` (via the pipeline) deserialize `nba_modell.pkl` with Python's `pickle`, which executes arbitrary code embedded in the file on load. Low risk today since the file is self-generated and git-ignored, but if `nba_modell.pkl` is ever shared, downloaded, or restored from an untrusted backup, this is an arbitrary-code-execution vector.
- Files: `03_tren_modell.py:168` (writer), `04_value_detector.py:40` (reader), `modell_utils.py` (custom class required to unpickle).
- Recommendation: if the model is ever distributed outside this machine, switch to a safer serialization (e.g. `joblib` with a documented schema, or export raw XGBoost booster + isotonic knots as JSON/arrays) rather than raw `pickle`.

## Missing Critical Runtime File (breaks fresh clone)

**`modell_utils.py` is untracked but required at runtime:**
- Problem: `git status` shows `modell_utils.py` as untracked (`??`), yet both `03_tren_modell.py:20` and `04_value_detector.py:23` do `from modell_utils import KalibrertModell`, and `nba_modell.pkl` was pickled using that exact class (`03_tren_modell.py:166`). Unpickling requires the class to be importable at the same module path.
- Impact: anyone who clones the repo (or a CI/scheduled-task runner that does a fresh checkout) gets an immediate `ModuleNotFoundError` in step 3 and step 4, and any regenerated `nba_modell.pkl` becomes unloadable elsewhere. This is a "works on my machine only" landmine.
- Fix approach: `git add modell_utils.py` and commit it. This is the single highest-priority non-security fix — the pipeline is currently non-reproducible without it.

## Tech Debt

**Documented remediation plan appears to have been silently reverted:**
- Issue: `ENDRINGER_SUMMARY.txt` and `KALIBRERING_RAPPORT.md` (both untracked, dated "April 6, 2026") describe a specific fix for a losing model: add `KALIBRERING_FAKTOR = 0.60`, raise `MIN_VALUE_TERSKEL` from `0.05` → `0.20`, lower `MAX_ODDS` from `4.00` → `2.50`, and add `MIN_SIKKERHET = 0.65` to `04_value_detector.py`. The current `04_value_detector.py` (last modified Aug 19, per file mtime) has **none** of these: `MIN_VALUE_TERSKEL = 0.05` (`04_value_detector.py:31`), `MAX_ODDS = 4.00` (`04_value_detector.py:33`), no `KALIBRERING_FAKTOR`, no `MIN_SIKKERHET`. These are exactly the "FØR ENDRING" (before-fix) values the reports say caused a 17% win rate / −67% ROI backtest.
- Instead, a *different* fix was implemented in `03_tren_modell.py:132-166`: isotonic-regression calibration wrapped in `modell_utils.KalibrertModell`, applied at the model level rather than via a manual `×0.60` multiplier at the detector level. This may be an intentional, better replacement — but the two markdown reports were left in place, uncommitted, describing a plan that does not match the code, which will mislead future readers (including future Claude sessions) about why the current thresholds are what they are.
- Files: `ENDRINGER_SUMMARY.txt`, `KALIBRERING_RAPPORT.md`, `04_value_detector.py:31-33`, `03_tren_modell.py:132-172`.
- Impact: `bankroll.json` shows the live bankroll fell from `STARTKAPITAL = 1000` kr to `74.88` kr (a ~92.5% drawdown) across the recorded `historikk` — consistent with the pre-fix, loss-making configuration still being what actually runs in production via `06_bot.py` → `04_value_detector.py`.
- Fix approach: decide whether the isotonic-calibration approach in `03_tren_modell.py` is the intended replacement for the manual threshold changes. If so, delete or rewrite the two stale report files to reflect what's actually deployed. If not, re-apply the `MIN_VALUE_TERSKEL`/`MAX_ODDS`/`MIN_SIKKERHET` changes to `04_value_detector.py`. Either way, stop the bot (or accept the risk) until this is resolved — real (virtual) money is being lost under a configuration the project's own prior analysis flagged as unprofitable.

**Calibration is evaluated on the same data it was fit on (leakage in the reported metrics):**
- Issue: in `03_tren_modell.py`, the isotonic regressor is fit with `kalibrerer.fit(y_rå, y_test)` (`03_tren_modell.py:143`) and then immediately evaluated with `kalibrerer.predict(y_rå)` against the same `y_test` (`03_tren_modell.py:145-147`, and the calibration diagnostic bucket table at `03_tren_modell.py:156-161`). This means the printed "Kalibrert" log-loss/Brier scores and the per-bucket calibration diagnostic are measuring fit quality on the calibrator's own training data, not out-of-sample performance — the reported calibration quality is optimistically biased and cannot be trusted to reflect real-world behavior.
- Files: `03_tren_modell.py:61-172`.
- Fix approach: split off a third, calibration-only holdout slice (e.g. train / calibrate / test three-way split) so the calibrator is fit on one slice and evaluated on a disjoint slice, consistent with the project's own stated principle of never testing on data used elsewhere in the pipeline (`03_tren_modell.py:10-12`, `02_feature_engineering.py:90-91`).

**Duplicated, inconsistent team-name resolution logic across three files:**
- Issue: `04_value_detector.py:140-146`, `05_skadefilter.py:196-199`, and `06_bot.py:79-92` each implement their own ad hoc team-name → team-ID/team-info lookup, using different heuristics (last-word split vs. full-name substring vs. bidirectional substring `in` matching). None share a common helper.
- Files: `04_value_detector.py:116-146`, `05_skadefilter.py:167-199`, `06_bot.py:76-98`.
- Impact: a team name that fails to resolve in one script may resolve fine in another (or vice versa), producing silent inconsistencies (a bet gets priced in `04` but the skade-filter or result-checker can't find the team). Bugs fixed in one lookup (e.g. the bidirectional substring match in `06_bot.py:89-91`) aren't automatically applied to the other two.
- Fix approach: extract a single `finn_lag(navn) -> team_info` helper into a shared module (alongside `modell_utils.py`) and import it in all three scripts.

**Hardcoded, version-pinned venv path inside `06_bot.py`:**
- Issue: `06_bot.py:233` hardcodes `venv/lib/python3.10/site-packages` into `PYTHONPATH` before shelling out to `04_value_detector.py` / `05_skadefilter.py`. The actual venv (`venv/pyvenv.cfg`) is currently built against **Python 3.14**, and `venv/lib/` on disk contains three separate, likely-stale site-packages trees (`python3.10`, `python3.11`, `python3.14`) — evidence the venv has been recreated multiple times with different interpreter versions without cleaning up the old ones.
- Files: `06_bot.py:229-246`, `venv/pyvenv.cfg`.
- Impact: if the venv is ever rebuilt again (new Python version), this path silently stops matching, dependencies won't be found via the injected `PYTHONPATH`, and the subprocess calls to `04_value_detector.py`/`05_skadefilter.py` will fail in a way that's non-obvious (wrong/missing packages rather than a clear "path not found" error).
- Fix approach: derive the site-packages path dynamically (e.g. `sysconfig.get_paths()["purelib"]` on the venv's own interpreter, or better: just invoke the venv's `python` binary directly instead of `sys.executable` + manual `PYTHONPATH` surgery) and delete the two unused `python3.10`/`python3.11` site-packages trees.

**Unused/dead computation:**
- `06_bot.py:132` computes `er_hjemmekamp` but the variable is never read afterward (the function returns on the next line using `rad["WL"]` directly). Harmless but confusing — reads like it should gate the return logic and doesn't.

**No pinned dependency versions:**
- `requirements.txt` uses only lower-bound (`>=`) constraints for every package (`nba_api>=1.4.0`, `pandas>=2.0.0`, `numpy>=1.24.0`, `scikit-learn>=1.3.0`, `xgboost>=2.0.0`, `requests>=2.31.0`) and there is no lockfile. A fresh `pip install -r requirements.txt` today can silently pull newer major versions than what the pickled `nba_modell.pkl` / `KalibrertModell` were built and tested against, risking unpickling errors or subtly different `predict_proba` behavior after a re-train.
- File: `requirements.txt`.
- Fix approach: pin exact versions (or add a lockfile via `pip-compile`/`uv`) once the current environment is known-good.

## Fragile Areas

**Broad exception swallowing hides result-checking failures:**
- Files: `06_bot.py:104-138` (`hent_kampresultat`).
- Why fragile: the entire NBA-API lookup (team resolution, date math, `LeagueGameFinder` call, dataframe filtering) is wrapped in a bare `except Exception: return None` (`06_bot.py:135-136`). The caller (`sjekk_resultater`, `06_bot.py:141-195`) treats `None` as "game not played yet" (`06_bot.py:164-166`, prints "Ingen resultat funnet ennå"), so a genuine error (network failure, NBA API schema change, rate limiting) is indistinguishable from "not played yet" — a bet can stay stuck in `"venter"` status indefinitely with no visible error, silently corrupting the bankroll/win-rate stats shown on the dashboard.
- Safe modification: log the exception (at least to stderr) before returning `None`, and/or track consecutive failures per bet so a persistent error is surfaced differently from "not yet played".
- Test coverage: none — there are no automated tests anywhere in this repo (see Test Coverage Gaps below), so this path has only ever been validated by manual runs.

**Team/game matching relies on fuzzy substring heuristics:**
- Files: `06_bot.py:85-92` (`finn_lag`), `06_bot.py:123` (`df["MATCHUP"].str.lower().str.contains(borte_abbr)`), `05_skadefilter.py:196-199`, `04_value_detector.py:140-146`.
- Why fragile: matching is done via bidirectional substring containment (`nøkkel in navn or navn in nøkkel`) or by using only the last whitespace-separated word of a team name as a lookup key (`04_value_detector.py:140-141`, e.g. `"Portland Trail Blazers".split()[-1]` → `"Blazers"`, which may not match the nickname key `"trail blazers"` in `lag_oppslag`, silently dropping that game from value-bet consideration at `04_value_detector.py:148-150`).
- Safe modification: any change to team-name formatting from the-odds-api.com or nba_api (e.g. a team relocation/rename) needs manual verification against all three lookup implementations, since none are covered by tests.

**Bet-grading depends on a specific CSV freshness bug already patched once via a comment-only workaround:**
- File: `06_bot.py:260-278` (`plasser_bets`), see the inline comment at `06_bot.py:262-263`: "sikkerhetsnettet mot at en gammel/stale rad fra pipelinen (bug fikset 2026-08-19) blir bettet på nytt" (safety net against a stale row from the pipeline, from a bug fixed 2026-08-19, being re-bet).
- Why fragile: the fix is a dedup/`kamp_dato < today` guard bolted onto `plasser_bets`, not a fix at the source of the staleness (`kjør_pipeline()`/`04_value_detector.py` writing `value_bets_idag.csv`). If `04_value_detector.py` fails partway or is re-run against cached data, the same class of stale-row bug could resurface in a form the current guard doesn't anticipate.
- Test coverage: none. This is exactly the kind of date/dedup edge case that would benefit from a small unit test around `plasser_bets`.

## Scaling Limits

**NBA API rate limiting via blocking `time.sleep`:**
- Current capacity: every per-team/per-player NBA-API call is followed by a hardcoded `time.sleep(...)` (`01_hent_data.py:48` → 1s per season; `04_value_detector.py:99` → 0.5s per team per game; `05_skadefilter.py:49` → 1.0s per request; `06_bot.py:117` → 0.6s per bet result check). With ~30 recorded bets (`bets.json`) and a handful of NBA games/day this is currently fine (single-digit minutes per run).
- Limit: this is a purely sequential, single-threaded pipeline — as `bets.json` grows (season progresses) or if the model is pointed at a full-season backtest, `01_hent_data.py`'s per-season fetch and `06_bot.py`'s per-bet result-check loop will scale linearly and could turn a few-minute daily run into a much longer one.
- Scaling path: batch result-checking (the same `LeagueGameFinder` date-range call could resolve multiple bets at once instead of one call per bet) or cache `teams.get_teams()` (currently re-fetched inside `hent_kampresultat` on every single bet check, `06_bot.py:76`, instead of once per `sjekk_resultater` call).

## Test Coverage Gaps

**No automated tests exist anywhere in the repository:**
- What's not tested: everything, including the financial math that directly determines real position sizing — `beregn_innsats` (Kelly-criterion stake sizing, `06_bot.py:202-222`), bet dedup/staleness logic in `plasser_bets` (`06_bot.py:256-316`), win/loss grading in `sjekk_resultater` (`06_bot.py:141-195`), and the value/EV computation in `04_value_detector.py:206-213`.
- Files: no `test_*.py`, `*_test.py`, `pytest.ini`, or test framework dependency anywhere in `requirements.txt` or the repo tree.
- Risk: a subtle bug in Kelly-fraction math, odds parsing, or dedup-key construction directly and silently mis-sizes or duplicates real (virtual) bets — exactly the class of bug the `06_bot.py:262-263` comment shows already happened once in production before being noticed.
- Priority: High for `beregn_innsats` and `plasser_bets` dedup logic specifically (pure functions, cheap to unit test, directly control money at risk); Medium for the NBA-API-dependent functions (harder to test without mocking `nba_api`/`requests`).

## Repository Hygiene / Scratch Artifacts

**~470MB of vendored/build artifacts sitting in the repo root, untracked and not gitignored:**
- `_linux_pkgs/` (323MB) — a full set of Linux-platform wheels/extracted packages (numpy, pandas, scikit-learn, scipy, xgboost, etc.), presumably staged for deploying the bot to a Linux host/cron server.
- `_wheels/` (48MB) — additional wheel files.
- `_pip_tmp/`, `_pip_home/` — pip scratch/cache directories.
- `_test.bin` (100MB) — an apparently arbitrary 100MB binary blob (likely a disk-space/upload test artifact).
- `test_write.tmp` (0 bytes) — an empty scratch file.
- Files: `_linux_pkgs/`, `_wheels/`, `_pip_tmp/`, `_pip_home/`, `_test.bin`, `test_write.tmp` (all shown as untracked or absent from `git status` because `_pip_home` happens to be empty, but none are covered by `.gitignore`).
- Impact: none of these are excluded in `.gitignore`. A careless `git add -A` / `git add .` would stage roughly half a gigabyte of throwaway binary/vendor content into version control, bloating the repo permanently (git does not shrink after a later `git rm` without a history rewrite).
- Fix approach: delete `_test.bin` and `test_write.tmp` outright (they serve no purpose in the repo); if `_linux_pkgs/` / `_wheels/` / `_pip_tmp/` / `_pip_home/` are still needed for a deployment workflow, move them outside the repo (or add explicit `.gitignore` entries: `_linux_pkgs/`, `_wheels/`, `_pip_tmp/`, `_pip_home/`, `_test.bin`, `*.tmp`) so they can never be accidentally committed.

**Stale/duplicate report docs cluttering the project root:**
- `ENDRINGER_SUMMARY.txt` and `KALIBRERING_RAPPORT.md` (both untracked, dated April 6 2026) describe a since-diverged remediation plan (see Tech Debt above) and sit in the repo root rather than a `docs/` folder. `debug_kamp.py` (untracked) is a one-off manual debugging script hardcoded to a specific historical matchup (`06_bot.py`-style logic duplicated for a single OKC vs SAS game on `2026-05-27`, `debug_kamp.py:9-11`) with no generalized purpose.
- Fix approach: either commit these intentionally (move reports to `docs/`, keep `debug_kamp.py` as a documented debugging utility with a generic team/date argument instead of hardcoded values) or delete them if they're one-off scratch work that's no longer useful.

---

*Concerns audit: 2026-08-19*
