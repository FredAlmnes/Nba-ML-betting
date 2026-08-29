---
phase: 01-repo-hygiene-config-remediation
reviewed: 2026-08-20T19:50:53Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - .env.example
  - .gitignore
  - 04_value_detector.py
  - ENDRINGER_SUMMARY.txt
  - KALIBRERING_RAPPORT.md
  - KOMME_I_GANG.md
  - modell_utils.py
  - requirements.txt
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-08-20T19:50:53Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed the repo-hygiene/config-remediation file set: the `.env`-based API key loading in `04_value_detector.py`, its supporting `.env.example`/`requirements.txt` changes, the newly-tracked `modell_utils.py`, the hardened `.gitignore`, and the two "superseded" narrative docs (`ENDRINGER_SUMMARY.txt`, `KALIBRERING_RAPPORT.md`) plus `KOMME_I_GANG.md`.

The core remediation is sound: the hardcoded Odds API key literal is gone from `04_value_detector.py`, replaced by a fail-fast `os.environ.get("ODDS_API_NOKKEL")` load via `python-dotenv`; `.env` is confirmed git-ignored and not tracked; `modell_utils.py` is now tracked so a fresh clone can unpickle `nba_modell.pkl`; `.gitignore` now correctly ignores the scratch-artifact directories (verified via `git check-ignore`); and the leaked key was rotated per `01-05-SUMMARY.md`. No hardcoded secrets, `eval`, or other dangerous patterns were found in the reviewed file set (grep-verified).

Remaining issues are all Warning/Info tier: a missing HTTP timeout on the live odds fetch, the still-recoverable leaked key literal in git history (already an accepted/deferred risk per `01-05-SUMMARY.md`, but re-surfaced here since it's a live fact about the reviewed code's blast radius), an unstripped env-var read, a commit-hygiene note, dead code (duplicate `import sys`), and an over-broad "superseded" disclaimer in `ENDRINGER_SUMMARY.txt` that doesn't cover a factually false claim about an automated scheduler. None of these rise to Critical for this phase's stated scope (secret hygiene + doc/code drift reconciliation).

## Warnings

### WR-01: Live odds fetch has no request timeout

**File:** `04_value_detector.py:73`
**Issue:** `respons = requests.get(url, params=params)` has no `timeout=` argument. If `api.the-odds-api.com` hangs or the connection stalls, this call blocks indefinitely. Since `06_bot.py` invokes this script as a subprocess with no watchdog/kill-timeout of its own (per architecture notes: process-boundary coupling, no async), a stalled request here hangs the entire daily bot run with no diagnostic output.
**Fix:**
```python
respons = requests.get(url, params=params, timeout=15)
```

### WR-02: Leaked API key literal remains permanently recoverable from git history

**File:** `04_value_detector.py` (pre-`cb2f028` history), `.gitignore`
**Issue:** The key that was hardcoded as `API_NØKKEL = "afc4f647c551e760f59f837769f5a3a1"` prior to this phase is no longer present in any currently-reviewed working-tree file (grep-verified clean), and `01-05-SUMMARY.md` confirms it has been rotated dead at the-odds-api.com. However, the literal value is still trivially recoverable via `git log -p` / `git show <pre-cb2f028-commit>` from anyone with read access to the repo (or any fork/clone taken before rotation). This is already tracked as an explicitly deferred decision (D-03, "git-history scrubbing... deferred... accepted residual risk T-01-15") in `01-05-SUMMARY.md`/`STATE.md`, so this finding is not new information — it is re-surfaced here because a review of "is any secret currently exposed by this code" should not silently omit it. Rotation neutralizes live exploitability; the historical value's mere presence in history is the residual (accepted) risk.
**Fix:** No action required beyond what's already tracked, unless the repo is or becomes public — in which case history-rewriting (`git filter-repo` / BFG) plus a forced re-clone by any collaborators would be the standard remediation, as already noted in the phase's deferred-items table.

### WR-03: "SUPERSEDED" disclaimer in ENDRINGER_SUMMARY.txt doesn't cover the false "automated scheduler" claim

**File:** `ENDRINGER_SUMMARY.txt:1-18, 117-123, 189-196`
**Issue:** The banner at the top of the file explicitly disclaims only the calibration factor, value threshold, and odds-range changes ("MIN_VALUE_TERSKEL 0.05 til 0.20, MAX_ODDS 4.00 til 2.50... ble ALDRI anvendt"). It does not disclaim the file's separate, unrelated claim that "Bot vil kjøre automatisk med nye parametre fra neste scheduled run" / "BOT KJØRER AUTOMATISK ✓ Scheduled task kjører hver dag" (lines 120-123, 192). Per the architecture notes (`CLAUDE.md`) there is no cron job, systemd timer, or GitHub Action anywhere in this repo, and `crontab -l` returns empty — this claim was false when written and remains uncorrected. A future reader (human or AI agent) relying on this "historical context" doc could reasonably conclude an automated scheduler exists and was simply never wired up to new parameters, rather than that no scheduler has ever existed.
**Fix:** Extend the top banner (or add an inline note near line 120) to also disclaim the "scheduled task" claim, e.g.: "The 'scheduled task runs automatically' claim below was also never true — no cron/systemd/CI scheduler has ever existed in this repo; `06_bot.py` is invoked manually."

### WR-04: `ODDS_API_NOKKEL` value read without stripping whitespace

**File:** `04_value_detector.py:36`
**Issue:** `API_NØKKEL = os.environ.get("ODDS_API_NOKKEL")` is used as-is. If a user pastes the key into `.env` with trailing whitespace or a stray newline (a common copy-paste mistake, e.g. from a terminal or PDF), the value is non-empty so the `if not API_NØKKEL:` fail-fast check passes, but the malformed key gets sent to The Odds API and fails auth with an opaque non-200 response — the fail-fast UX this phase specifically added is bypassed for this class of mistake, and the resulting error message (`Feil ved henting av odds: 401` + raw response body) gives no hint that the root cause is a formatting issue in `.env`.
**Fix:**
```python
API_NØKKEL = (os.environ.get("ODDS_API_NOKKEL") or "").strip()
```

## Info

### IN-01: Redundant duplicate `import sys`

**File:** `04_value_detector.py:78`
**Issue:** `sys` is already imported at module level (line 19). The `import sys` inside the `if respons.status_code != 200:` block is dead/redundant — harmless but a leftover from patching in `sys.exit(1)` without checking the existing imports.
**Fix:**
```python
if respons.status_code != 200:
    print(f"Feil ved henting av odds: {respons.status_code}")
    print(respons.text)
    sys.exit(1)  # NB: bare exit() gir exitkode 0 (=suksess) og gjemmer feilen for 06_bot.py
```

### IN-02: Commit mixes unrelated feature changes into a "load key from env var" fix commit

**File:** `04_value_detector.py` (commit `cb2f028`)
**Issue:** Commit `cb2f028`'s message describes it as "load Odds API key from ODDS_API_NOKKEL env var instead of hardcoding it," but the diff also introduces `MAX_ODDS`, dynamic season detection (`gjeldende_sesong()`), and new `KampDato`/`Modell_prob` output columns — a materially different behavior change (odds now upper-bounded, CSV schema changed) bundled into a security-fix commit. The commit body does disclose this ("Carries forward pre-existing uncommitted WIP... per 01-01-SUMMARY.md developer decision"), so it's a traceable, intentional choice rather than a hidden defect — flagging only as a commit-hygiene note for future `git bisect`/`git blame` usage, since a reviewer skimming commit titles for security-relevant changes could miss the behavior change.
**Fix:** None required retroactively; for future phases, prefer splitting security-sensitive fixes from unrelated behavior changes into separate commits even when both are already-decided/pre-existing WIP.

### IN-03: `KampDato` derived from truncated UTC timestamp can be off by one calendar day from the "local" NBA game date

**File:** `04_value_detector.py:235` (`kamp_dato_str = kamp_tid[:10] if kamp_tid else str(datetime.now().date())`)
**Issue:** `kamp_tid` (`kamp["commence_time"]`) is a UTC ISO-8601 timestamp from The Odds API. Slicing the first 10 characters yields the UTC calendar date, which can differ from the US-local calendar date fans/users associate with the game (e.g., a 10pm ET tip-off is 02:00–03:00 UTC the *next* day). This is currently absorbed downstream by `06_bot.py::hent_kampresultat`'s explicit ±3-day search window when settling results, so it is not causing observed failures today, but it is a latent inaccuracy in the date this file writes to `value_bets_idag.csv` / `bets.json` (`kamp_dato`), and any future consumer of that field that does an exact-date match (rather than a windowed search) would be affected.
**Fix:** Convert to the game's local date before truncating, e.g. using the US Eastern zone NBA scheduling conventions (`zoneinfo.ZoneInfo("America/New_York")`) rather than raw UTC-date truncation, or document the UTC-date convention explicitly in a comment so downstream consumers know not to do exact-date matching.

---

_Reviewed: 2026-08-20T19:50:53Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
