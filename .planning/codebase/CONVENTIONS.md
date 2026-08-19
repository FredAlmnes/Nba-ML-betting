# Coding Conventions

**Analysis Date:** 2026-08-19

## Overview

This is a small, single-author Python data/ML pipeline (not a package). There is no
build system, no `pyproject.toml`/`setup.py`, no linter config, and no formatter config.
Conventions below are inferred purely from the existing source files:
`01_hent_data.py`, `02_feature_engineering.py`, `03_tren_modell.py`, `04_value_detector.py`,
`05_skadefilter.py`, `06_bot.py`, `modell_utils.py`, `debug_kamp.py`.

## Naming Patterns

**Files:**
- Pipeline steps are numbered scripts run in sequence: `01_hent_data.py`, `02_feature_engineering.py`,
  `03_tren_modell.py`, `04_value_detector.py`, `05_skadefilter.py`, `06_bot.py`.
  The numeric prefix encodes execution order — always continue this pattern for new pipeline
  stages (e.g. a new step would be `07_<beskrivelse>.py`).
- One-off/debug scripts live at repo root without a number prefix, e.g. `debug_kamp.py`.
- Shared code that multiple numbered scripts import goes in a plain-named module,
  e.g. `modell_utils.py` (imported by `03_tren_modell.py` and `04_value_detector.py`
  via `from modell_utils import KalibrertModell`).

**Language: Norwegian identifiers, English libraries.**
- All variable/function names, comments, print output, and docstrings are written in
  **Norwegian (bokmål)**, e.g. `alle_lag`, `sesonger`, `kamp_dato`, `beregn_innsats`,
  `hent_kampresultat`, `lag_oppslag`. This is a strict, consistent convention across every
  file — new code must follow it (do not introduce English identifiers into these scripts).
- Third-party library/API names and their own field names stay in English as-is
  (e.g. `GAME_ID`, `TEAM_ABBREVIATION`, `PTS`, `season_nullable`, `predict_proba`).

**Functions:**
- `snake_case`, Norwegian verbs/nouns: `les_bankroll()`, `lagre_json()`, `beregn_innsats()`,
  `hent_kampresultat()`, `sjekk_resultater()`, `kjør_pipeline()`, `plasser_bets()`,
  `generer_dashboard()`.
- Private/internal helpers prefixed with a single underscore when local to a script,
  e.g. `_gjeldende_sesong()`, `_hent_spillerdata()` in `05_skadefilter.py`.
- Norwegian special characters (æ, ø, å) are used freely in identifiers where natural,
  e.g. `kjør_pipeline`, `gjeldende_sesong`, `år`, `måned`. This works because all files
  are plain UTF-8 `.py` — no ASCII-only restriction is enforced.

**Variables:**
- `snake_case` throughout, e.g. `feature_kolonner`, `maal_kolonne`, `value_bets`, `kamp_dato_rad`.
- Norwegian domain vocabulary is used consistently for the same concept across files —
  reuse these terms rather than inventing synonyms:
  - `hjemme` = home, `borte` = away
  - `kamp` = game/match, `sesong` = season, `lag` = team
  - `innsats` = stake, `saldo`/`bankroll` = balance, `gevinst` = profit/payout
  - `sannsynlighet`/`sann` = probability, `terskel` = threshold
  - `oppslag` = lookup table (dict), e.g. `lag_oppslag = {navn: team_id}`
- Constant-like config values are `UPPER_SNAKE_CASE` at module top, e.g.
  `MIN_VALUE_TERSKEL`, `MIN_ODDS`, `MAX_ODDS`, `API_NØKKEL` (`04_value_detector.py`),
  `STARTKAPITAL`, `KELLY_FRAKSJON`, `MAX_INNSATS`, `MIN_INNSATS`, `BANKROLL_FIL`,
  `BETS_FIL`, `DASHBOARD_FIL` (`06_bot.py`).
- Aligned assignment/dict-literal spacing is used deliberately for readability — extra
  spaces before `=` or `:` to align a block of related statements, e.g. in `modell_utils.py`:
  ```python
  self.modell               = modell
  self.kalibrerer           = kalibrerer
  self.feature_importances_ = modell.feature_importances_
  ```
  and in `06_bot.py`:
  ```python
  bet["status"]   = "vant"
  bet["gevinst"]  = gevinst
  ny_saldo       += gevinst
  ```
  Follow this alignment style when adding blocks of related assignments.

**Types/Classes:**
- `PascalCase`, Norwegian, e.g. `KalibrertModell` (`modell_utils.py`). Only one class exists
  in the whole codebase — the project is otherwise purely script/function-based (no OOP
  layering, no data classes, no type hints anywhere).

## Code Style

**Formatting:**
- No formatter (no Black/Ruff/autopep8 config present). Style is hand-maintained but fairly
  consistent: 4-space indentation, blank line between logical blocks, no trailing semicolons.
- No type hints are used anywhere in the codebase (`def beregn_innsats(saldo, modell_prob, odds):`
  not `def beregn_innsats(saldo: float, ...)`). Do not introduce type hints inconsistently in
  isolated files — if adopted, it should be a deliberate, codebase-wide change.

**Linting:**
- No linter config exists (no `.flake8`, `ruff.toml`, `pyproject.toml`). No enforced rule set —
  match existing style by eye.

**Section banners:**
- Every script divides its logic into numbered steps using a comment banner pattern:
  ```python
  # -------------------------------------------------------
  # 1. Hent liste over alle NBA-lag
  # -------------------------------------------------------
  ```
  This is used pervasively in `01_hent_data.py`, `02_feature_engineering.py`,
  `03_tren_modell.py`, `04_value_detector.py`, `05_skadefilter.py`, and `06_bot.py`
  (both as top-of-script step markers and above individual function groups). New pipeline
  code should use this same banner style to mark logical sections.

**Module docstrings:**
- Every script/module opens with a triple-quoted docstring explaining, in Norwegian, what the
  step does and why, often including the pipeline position (`STEG 1: ...`, `STEG 2: ...`) and
  a short conceptual explanation. See top of `01_hent_data.py`, `02_feature_engineering.py`,
  `03_tren_modell.py`, `04_value_detector.py`, `05_skadefilter.py`, `06_bot.py`.

**Print-based narration:**
- Scripts are designed to be run interactively/manually and narrate their own progress via
  `print()` statements at every step (not a logging framework) — e.g.
  `print(f"Henter kamper for sesong {sesong}...")`, `print(f"Fant {len(alle_lag)} lag")`.
  This doubles as the only "test output" a human reviews after each run. New pipeline steps
  should keep this narration style: print what is about to happen, then print the result/count.
- Emoji are used in `06_bot.py` and `05_skadefilter.py` print statements as status indicators:
  `✅` (success/win), `❌` (failure/loss), `⚠️` (warning), `🎯` (bet placed), `⏭️` (skipped).
  Follow this convention for new status output in those two scripts; the data-pipeline scripts
  (`01`–`03`) do not use emoji and keep plain text status lines.

## Import Organization

**Order:** Standard library first, then third-party, then local modules — no blank-line
grouping enforced strictly, but the pattern holds across files, e.g. `06_bot.py`:
```python
import json
import os
import subprocess
import sys
from datetime import datetime, date, timedelta
import pandas as pd
import time
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.static import teams
```
Local imports (e.g. `from modell_utils import KalibrertModell`) appear last, sometimes with an
inline comment explaining why the import exists (`04_value_detector.py`: `# nødvendig for å laste pickle`).

**Path Aliases:** None — this is a flat script directory, no package structure, no `src/` layout.

## Error Handling

**Patterns:**
- Broad `try/except Exception` around external API calls, returning a sentinel (`None` or an
  empty DataFrame) rather than propagating, e.g. `hent_kampresultat()` in `06_bot.py` returns
  `None` on any exception; `_hent_spillerdata()` in `05_skadefilter.py` returns
  `pd.DataFrame()` on failure and prints the exception inline:
  ```python
  except Exception as e:
      print(f"  (Kunne ikke hente {season_type} data: {e})")
      return pd.DataFrame()
  ```
- HTTP failures are checked via status code, not exceptions, and terminate the script with a
  non-zero exit code — `04_value_detector.py`:
  ```python
  if respons.status_code != 200:
      print(f"Feil ved henting av odds: {respons.status_code}")
      print(respons.text)
      import sys
      sys.exit(1)  # NB: bare exit() gir exitkode 0 (=suksess) og gjemmer feilen for 06_bot.py
  ```
  Note the explicit comment about why `sys.exit(1)` (not bare `exit()`) is required — this
  matters because `06_bot.py` checks subprocess `returncode` when invoking this script via
  `subprocess.run`. Preserve non-zero exit codes on failure in any script invoked by `06_bot.py`.
- Missing-file errors use `try/except FileNotFoundError` with a user-facing instruction message,
  e.g. `05_skadefilter.py`:
  ```python
  try:
      value_df = pd.read_csv("value_bets_idag.csv")
  except FileNotFoundError:
      print("Finner ikke 'value_bets_idag.csv' – kjør 04_value_detector.py først!")
      exit()
  ```
- `06_bot.py` treats subprocess failures from `04_value_detector.py`/`05_skadefilter.py` as
  "no bets today" rather than crashing — `kjør_pipeline()` returns `None` and logs the last
  500 chars of stderr:
  ```python
  if result.returncode != 0:
      print(f"  Feil i 04_value_detector.py:\n{result.stderr[-500:]}")
      return None
  ```
- No custom exception classes exist anywhere in the codebase. No `raise` statements were
  found in the numbered pipeline scripts — errors are handled by returning sentinels/None and
  printing, never by raising up the call stack.

## Logging

**Framework:** None — plain `print()` calls only, no `logging` module usage anywhere.

**Patterns:**
- f-strings for all interpolated output: `print(f"Fant {len(alle_lag)} lag")`.
- Numeric formatting is applied inline for readability: `.1%` for percentages
  (`f"{value_hjemme:+.1%}"`), `.0f` for currency amounts (`f"{gevinst:.0f} kr"`),
  `:.4f` for precision metrics like log-loss/Brier score.
- Section headers use `"=" * 60` or `"─" * 50` separators printed before major output blocks,
  e.g. `06_bot.py`: `print("=" * 60)` before the bot's daily summary, `print(f"\n{'─'*50}")`
  between per-match skadefilter checks in `05_skadefilter.py`.

## Comments

**When to Comment:**
- Comments explain *why*, not *what* — especially around ML/finance pitfalls, e.g.
  `02_feature_engineering.py`: `# shift(1) betyr "bruk forrige kamps verdi" – ikke dagens... avgjørende for å unngå "data leakage"!`
  and `03_tren_modell.py`: `# Vi må ALDRI trene på fremtidige data!`
- Inline trailing comments annotate config constants with their practical meaning, e.g.
  `06_bot.py`: `KELLY_FRAKSJON = 0.5 # Halvt Kelly (konservativt – reduserer varians)`.
- Dated "bugfix" comments are used to record historical gotchas directly in code rather than
  in a changelog, e.g. `06_bot.py`: `# ... (bug fikset 2026-08-19) blir bettet på nytt.`
  When fixing a subtle bug in these scripts, follow this pattern: leave a short dated inline
  comment explaining the failure mode that was fixed, since there is no CHANGELOG file.

**Docstrings:**
- Function docstrings are short, Norwegian, and explain purpose + return contract, e.g.
  ```python
  def hent_kampresultat(hjemme_lag, borte_lag, kamp_dato):
      """
      Henter faktisk kampresultat fra NBA API.
      Returnerer 'hjemme', 'borte', eller None (ikke spilt ennå).
      """
  ```
- No JSDoc-equivalent/type annotation convention (Python, no type hints, no Sphinx/Google-style
  sections like `Args:`/`Returns:` — docstrings are prose, not structured).

## Function Design

**Size:** Functions are generally short (10–40 lines) and single-purpose, but module-level
"script body" code (top-level statements outside functions) is long and linear — e.g.
`01_hent_data.py` and `02_feature_engineering.py` are almost entirely top-level procedural
code with only one or two helper functions (`beregn_lag_form`). `06_bot.py` is more function-
decomposed (`les_bankroll`, `sjekk_resultater`, `beregn_innsats`, `kjør_pipeline`,
`plasser_bets`, `generer_dashboard`, `main`) because it is re-run daily via cron/scheduler
rather than manually. **Convention:** one-shot/manual pipeline scripts (`01`–`05`) may stay
mostly top-level procedural; anything meant to run unattended/repeatedly (like `06_bot.py`)
should be decomposed into named functions with a `main()` entry point guarded by
`if __name__ == "__main__":`.

**Parameters:** Plain positional/keyword parameters, no `*args`/`**kwargs` patterns, no
dataclasses or config objects — config is passed as loose primitives (`saldo`, `modell_prob`,
`odds`) or read from module-level `UPPER_SNAKE_CASE` constants directly inside functions
(e.g. `beregn_innsats` reads `KELLY_FRAKSJON`, `MAX_INNSATS`, `MIN_INNSATS` as globals rather
than as parameters).

**Return Values:** Functions that can "fail" return `None`/empty-collection sentinels rather
than raising (see Error Handling above). Functions that transform data return the transformed
value directly (typically a DataFrame, dict, or tuple of `(bets, bankroll_data)` /
`(bets, bankroll_data, nye_bets)` in `06_bot.py`), mutating input dict/list arguments in place
and also returning them — callers reassign, e.g. `bets, bankroll_data = sjekk_resultater(bets, bankroll_data)`.

## Module Design

**Exports:** No `__all__`, no package `__init__.py` — this is a flat script directory, not an
installable package. Cross-script sharing happens through direct `import` of the file (e.g.
`from modell_utils import KalibrertModell`) or, for the numbered pipeline, through
`subprocess.run([sys.executable, "0N_script.py"], ...)` invocation from `06_bot.py`
(`kjør_pipeline()`), NOT via Python import — the numbered scripts communicate via files on
disk (CSV/JSON/pickle), not function calls. When adding a new pipeline stage, follow this
same pattern: read inputs from the previous stage's output file, write outputs to a new file,
and print machine-readable-enough status for the calling script to react to (via exit code)
rather than importing internals.

**Barrel Files:** Not applicable (no package structure).

**Persistence format conventions:**
- Tabular data between pipeline stages: CSV via `pandas.DataFrame.to_csv(..., index=False)`
  / `pd.read_csv(...)`, e.g. `nba_kamper_raw.csv` → `nba_features.csv` → `value_bets_idag.csv`
  → `value_bets_med_skadefilter.csv`.
- Trained model artifact: `pickle`, saved as a dict with named keys, not the bare model —
  `03_tren_modell.py`:
  ```python
  with open("nba_modell.pkl", "wb") as f:
      pickle.dump({"modell": kalibrert_modell, "feature_kolonner": feature_kolonner}, f)
  ```
  Any consumer of `nba_modell.pkl` must `from modell_utils import KalibrertModell` before
  unpickling, since the pickle references that class.
- Application/runtime state (bot bankroll + bet history): JSON via small `les_json`/`lagre_json`
  helpers in `06_bot.py`, always opened with `encoding="utf-8"` and written with
  `ensure_ascii=False, indent=2` (so Norwegian characters remain readable in the file):
  ```python
  def lagre_json(fil, data):
      with open(fil, "w", encoding="utf-8") as f:
          json.dump(data, f, ensure_ascii=False, indent=2)
  ```
  Follow this exact pattern (`ensure_ascii=False, indent=2`, utf-8) for any new JSON persistence.

## Secrets / Configuration

- No `.env` / environment-variable based config is used. The Odds API key lives as a plain
  string literal at the top of `04_value_detector.py`: `API_NØKKEL = "[REDACTED — see file]"`.
  **This means the file currently commits/exposes a live API key in source** — be aware of
  this when editing or sharing `04_value_detector.py`; see CONCERNS-equivalent note if a
  concerns audit is done. Do not add further secrets as literals; if extending config, prefer
  environment variables even though the current pattern doesn't use them.
- `.gitignore` excludes generated/personal data (`venv/`, `__pycache__/`, `*.pyc`, `.env`,
  `nba_kamper_raw.csv`, `nba_features.csv`, `nba_modell.pkl`, `value_bets_idag.csv`,
  `value_bets_med_skadefilter.csv`, `bankroll.json`, `bets.json`, `dashboard.html`,
  `dashboard_tom.html`, `.DS_Store`) — these are all regenerated by running the pipeline and
  should not be hand-edited or committed.

---

*Convention analysis: 2026-08-19*
