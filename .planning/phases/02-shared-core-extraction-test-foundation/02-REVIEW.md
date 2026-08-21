---
phase: 02-shared-core-extraction-test-foundation
reviewed: 2026-08-21T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - 02_feature_engineering.py
  - 04_value_detector.py
  - 05_skadefilter.py
  - 06_bot.py
  - config.py
  - debug_kamp.py
  - features.py
  - strategy.py
  - teams.py
  - tests/conftest.py
  - tests/test_features.py
  - tests/test_oppsett.py
  - tests/test_parity.py
  - tests/test_strategy.py
  - tests/test_teams.py
findings:
  critical: 3
  warning: 6
  info: 3
  total: 12
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-08-21T00:00:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

The shared-core extraction itself (`teams.py`, `features.py`, `strategy.py`) is clean, well-documented, and backed by genuinely useful determinism/leakage/dedup tests. That part of the phase is solid. The problems found are concentrated in the files that were touched only incidentally by the refactor (`06_bot.py`, `05_skadefilter.py`, `04_value_detector.py`) and in one real security gap in the dashboard HTML generator that pre-dates this phase but is still live in the reviewed code.

Three issues are classified Critical: an unescaped-HTML injection path from third-party odds-API team names into `dashboard.html`, a bankroll-history double-checkpoint bug that silently records a stale (pre-new-bets) balance for "today" whenever both settlement and new placements happen on the same run, and a fallback code path in `hent_kampresultat` that can attribute a bet's win/loss based on the wrong physical game. The remaining findings are consistency/robustness gaps (an `exit()` call that returns exit code 0 and defeats the exact failure-masking guard the codebase documents elsewhere, duplicated season-calculation logic that the phase's own stated goal was to eliminate, and unguarded division in the new "core" strategy functions).

## Critical Issues

### CR-01: Unescaped team/bet data injected into dashboard HTML via `innerHTML`

**File:** `06_bot.py:820-838`
**Issue:** `generer_dashboard()` embeds `bets` as a JSON literal (`const bets = {bets_json};`, line 289/700) and then the dashboard's own JS builds table rows with `tbody.innerHTML += `<tr>...${{lag}}...${{mot}}...`` (lines 830-838), where `lag`/`mot` come from splitting `b.kamp` — a string built in `04_value_detector.py:201` as `f"{hjemme_navn} vs {borte_navn}"` directly from the raw `home_team`/`away_team` fields returned by The Odds API (third-party, uncontrolled input). Nothing sanitizes or escapes these values before they are concatenated into an `innerHTML` template literal. If the odds API (or a compromised/malicious mirror of it, or a MITM'd response since the odds request uses `requests.get` without pinning) ever returns a team name containing `<img src=x onerror=...>` or similar markup, it executes as HTML/JS the moment `dashboard.html` is opened in a browser. This is a textbook stored-XSS pattern: external data → CSV → `bets.json` → JSON-embedded-in-`<script>` → `innerHTML` with no escaping.
**Fix:** Do not build HTML via template-literal string concatenation for untrusted fields. Use `textContent`/DOM node creation for `lag`, `mot`, and any other odds-API-derived string, e.g.:
```javascript
const tr = document.createElement('tr');
const tdMatch = document.createElement('td');
const main = document.createElement('div');
main.className = 'match-main';
main.textContent = lag;               // safe: no HTML parsing
const sub = document.createElement('div');
sub.className = 'match-sub';
sub.textContent = `vs ${mot}`;
tdMatch.append(main, sub);
tr.appendChild(tdMatch);
// ...append remaining cells the same way, then tbody.appendChild(tr)
```
Alternatively, HTML-escape every interpolated string (`lag`, `mot`, `b.value`) before building the template literal.

### CR-02: Bankroll history records a stale balance when both settlement and new bets happen in the same run

**File:** `06_bot.py:170-177` and `06_bot.py:965-969`
**Issue:** `sjekk_resultater()` appends today's `historikk` entry (with `ny_saldo`, the post-settlement balance) as soon as any bet is settled (`endringer == True`), guarded by "only add if no entry exists for today" (lines 173-177). Later, `main()` runs the pipeline and places new bets via `plasser_bets()`, which further reduces `bankroll_data["saldo"]` by the new stakes — and then tries to append today's history point again (lines 965-969), guarded by the *same* "only if no entry exists for today" check. Since `sjekk_resultater()` already inserted an entry for today earlier in the same run, this second append is always skipped. The result: on any day where the bot both settles previous bets AND places new bets (the common case), `bankroll_data["historikk"]` for today ends up holding the balance from right after settlement, not the true end-of-day balance after new stakes were deducted. The dashboard's bankroll curve (`06_bot.py:842-914`) and win-rate/ROI reporting for "today" will silently understate stakes placed that day.
**Fix:** Either only ever write the daily history point once, at the very end of `main()`, after both settlement and placement have completed (remove the append from inside `sjekk_resultater()`), or make the later check update the existing entry instead of skipping:
```python
# main(), replace the "append if missing" block with an upsert:
today = str(date.today())
entry = next((h for h in bankroll_data["historikk"] if h["dato"] == today), None)
if entry is None:
    bankroll_data["historikk"].append({"dato": today, "saldo": bankroll_data["saldo"]})
else:
    entry["saldo"] = bankroll_data["saldo"]
```

### CR-03: `hent_kampresultat` can attribute a bet's result to the wrong physical game

**File:** `06_bot.py:69-122` (specifically lines 112-117)
**Issue:** The function queries games for the team stored as "hjemme" and filters to those whose `MATCHUP` contains the away team's abbreviation. It then prefers the row where `MATCHUP` contains `"vs."` (i.e., the queried team was actually at home) via `hjemme_kamper`, falling back to `df.iloc[0]` — which may be an `"@"` (away) row for the queried team — when no `"vs."` row exists in the ±3-day window. `rad["WL"]` is then used unconditionally to decide `"hjemme"` vs `"borte"`, i.e., the code assumes the selected row corresponds to the bet's home fixture even in the fallback case, where it does not. Notably, `er_hjemmekamp` is computed (line 116) to capture exactly this distinction but is **never used** — dead code that suggests the safeguard was intended but not wired in. If the only game found in the search window between these two teams within ±3 days is the reverse fixture (the "home" team playing away), the function will silently report the wrong side as the winner, corrupting `bet["status"]`/`bet["gevinst"]` and the bankroll ledger with no error or warning.
**Fix:** Use the computed distinction instead of discarding it — only trust the result when a genuine home-fixture row was found; otherwise treat it as "no result yet" (return `None`) rather than guessing from an away-fixture row:
```python
if hjemme_kamper.empty:
    return None  # Only a reverse/away fixture found in-window — don't guess.
rad = hjemme_kamper.iloc[0]
return "hjemme" if rad["WL"] == "W" else "borte"
```

## Warnings

### WR-01: `05_skadefilter.py` uses bare `exit()`, defeating the exit-code convention the codebase explicitly documents

**File:** `05_skadefilter.py:157` and `05_skadefilter.py:165`
**Issue:** `04_value_detector.py:45` and `:79` both go out of their way to use `sys.exit(1)` with an inline comment explaining why: `"NB: bare exit() gir exitkode 0 (=suksess) og gjemmer feilen for 06_bot.py"`. `05_skadefilter.py`, which is invoked as a subprocess by `06_bot.py::kjør_pipeline()` exactly like `04_value_detector.py` is, ignores that documented rule and calls bare `exit()` after catching `FileNotFoundError` (line 157) and after finding an empty `value_bets_idag.csv` (line 165). Bare `exit()` raises `SystemExit(None)`, which subprocess reports as return code 0 — a "success" signal even though the script did nothing useful. In the current pipeline ordering this is low-probability (04 always writes `value_bets_idag.csv` first), but it's a real gap for anyone running `05_skadefilter.py` standalone or if the pipeline order ever changes, and it directly contradicts a rule the codebase itself calls "important."
**Fix:**
```python
import sys
...
except FileNotFoundError:
    print("Finner ikke 'value_bets_idag.csv' – kjør 04_value_detector.py først!")
    sys.exit(1)
```
(The empty-dataframe branch at line 165 legitimately writes output and can keep `exit()`/`sys.exit(0)`, since it's a genuine no-op success case — but note the inconsistency for future readers.)

### WR-02: Season-calculation logic duplicated instead of extracted, despite that being this phase's stated goal

**File:** `04_value_detector.py:92-100`, `05_skadefilter.py:24-32`
**Issue:** `gjeldende_sesong()` (04) and `_gjeldende_sesong()` (05) are byte-for-byte identical implementations of "compute the current NBA season string from today's date." This is precisely the kind of drift risk the phase's own module docstrings call out for `teams.py`/`features.py`/`strategy.py` ("denne typen drift denne fasen finnes for å stoppe" — features.py:9). It was left out of the consolidation: a future change to the season-boundary rule (e.g., handling the actual season start date more precisely instead of a hardcoded month-10 cutoff) requires editing two files in lockstep with no test enforcing they stay in sync.
**Fix:** Move `gjeldende_sesong()` into `config.py` or a new small shared module (e.g., `nba_sesong.py`) and import it from both `04_value_detector.py` and `05_skadefilter.py`.

### WR-03: Shared `strategy.py` core functions have no input validation, risking `ZeroDivisionError`

**File:** `strategy.py:16-32` (`fjern_vigorish`), `strategy.py:48-71` (`beregn_innsats`)
**Issue:** `fjern_vigorish` divides by `odds_hjemme`/`odds_borte` directly (line 25-26); `beregn_innsats` computes `b = odds - 1.0` and later divides by `b` (line 64). Both functions are explicitly positioned in the module docstring as the shared core that "Fase 5s backtest" will import identically. Today's live callers happen to always pass odds already clamped to `[MIN_ODDS, MAX_ODDS] = [1.50, 4.00]` by `04_value_detector.py`, so the risk is currently dormant — but a future backtest iterating over raw historical odds CSVs (which can and do contain `0`, `1.0`, or malformed values from data vendors) will hit a `ZeroDivisionError` with no guard and no clear error message pointing at the offending row.
**Fix:** Add a cheap guard at the top of each function:
```python
def fjern_vigorish(odds_hjemme, odds_borte):
    if odds_hjemme <= 1.0 or odds_borte <= 1.0:
        raise ValueError(f"Ugyldige odds: {odds_hjemme}, {odds_borte}")
    ...

def beregn_innsats(saldo, modell_prob, odds, kelly_fraksjon, min_innsats, max_innsats):
    if odds <= 1.0:
        raise ValueError(f"Ugyldige odds: {odds}")
    ...
```

### WR-04: `teams.py` substring fallback resolves ambiguous matches by dict-insertion order, not specificity

**File:** `teams.py:43-55`
**Issue:** `finn_lag()`'s fallback loop (`for nøkkel, info in LAG_OPPSLAG.items(): if nøkkel in navn or navn in nøkkel: return info`) returns the *first* key (in `LAG_OPPSLAG`'s insertion order, which follows whatever order `nba_api.stats.static.teams.get_teams()` happens to return) that satisfies a loose bidirectional substring test, not the best or most specific match. This ordering is an implementation detail of a third-party library, not something this module controls or pins. `tests/test_teams.py` covers several known-good cases (`"LA Clippers"`, `"Philadelphia 76ers"`, etc.) but does not exercise a genuinely ambiguous pair, so a future NBA team name/nickname (or a nba_api version bump that reorders `get_teams()`) could silently start resolving to a different team than intended, in a codebase where a wrong team resolution directly corrupts the model's feature row (via `04_value_detector.py`), injury-filter status (`05_skadefilter.py`), and settlement outcome (`06_bot.py`).
**Fix:** At minimum, make the fallback deterministic and prefer the most specific (longest) key match rather than first-found:
```python
def finn_lag(navn):
    navn = navn.lower()
    if navn in LAG_OPPSLAG:
        return LAG_OPPSLAG[navn]
    kandidater = [(nøkkel, info) for nøkkel, info in LAG_OPPSLAG.items()
                  if nøkkel in navn or navn in nøkkel]
    if not kandidater:
        return None
    kandidater.sort(key=lambda kv: len(kv[0]), reverse=True)
    return kandidater[0][1]
```

### WR-05: Hardcoded `python3.10` site-packages path in a Python 3.14 venv

**File:** `06_bot.py:197`
**Issue:** `kjør_pipeline()` constructs `PYTHONPATH` using a hardcoded `venv/lib/python3.10/site-packages` path while the committed venv (`venv/pyvenv.cfg`) is Python 3.14. This entry is currently harmless (a nonexistent path added to `PYTHONPATH` is silently ignored), but it's dead/misleading configuration in the exact file this phase touched, and it will actively break subprocess dependency resolution the day someone removes the stale `python3.10` site-packages tree from `venv/lib/` (already flagged as clutter in the project's own tech context).
**Fix:** Derive the interpreter's own site-packages path dynamically instead of hardcoding a version string:
```python
import sysconfig
venv_site = sysconfig.get_paths()["purelib"]
```

### WR-06: Duplicate `import sys` in `04_value_detector.py`

**File:** `04_value_detector.py:19` and `04_value_detector.py:78`
**Issue:** `sys` is imported at module top (line 19) and then re-imported inside the `if respons.status_code != 200:` block (line 78). Harmless but redundant, and a sign the error-handling block was written/copied without checking existing imports.
**Fix:** Remove the redundant `import sys` at line 78.

## Info

### IN-01: Dead variable `er_hjemmekamp` never used

**File:** `06_bot.py:116`
**Issue:** `er_hjemmekamp = bool(...)` is computed but never referenced afterward (see also CR-03, which explains why this dead code is actually evidence of a missing safeguard).
**Fix:** Either wire it into the return logic (see CR-03 fix) or remove it if truly unused.

### IN-02: No-op statement `ny_saldo -= 0`

**File:** `06_bot.py:165`
**Issue:** `ny_saldo -= 0  # Innsatsen er allerede trukket ved plassering` is a statement that does nothing; the comment alone would suffice.
**Fix:** Remove the line, keep the comment for context if desired.

### IN-03: Stale docstring/comments in `debug_kamp.py` reference a different matchup than the one actually configured

**File:** `debug_kamp.py:1-3, 25, 42`
**Issue:** The module docstring says `"Debug: Finn Minnesota vs Denver resultatet manuelt"` and inline comments say `"Søk med Minnesota sin ID"` / `"Søk med Denver sin ID også"`, but the actual hardcoded constants are `HJEMME_LAG = "Oklahoma City Thunder"` / `BORTE_LAG = "San Antonio Spurs"`. This is a one-off debug script (explicitly out of the automated pipeline) so impact is limited, but stale comments in a script whose entire purpose is manual investigation are actively misleading for whoever reuses it next.
**Fix:** Update the docstring/comments to match the current hardcoded teams, or better, generalize the comments to not name specific teams at all.

---

_Reviewed: 2026-08-21T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
