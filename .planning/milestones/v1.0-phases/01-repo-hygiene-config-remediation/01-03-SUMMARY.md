---
phase: 01-repo-hygiene-config-remediation
plan: 03
subsystem: infra
tags: [secrets, env-var, python-dotenv, git-hygiene]

# Dependency graph
requires:
  - phase: 01-repo-hygiene-config-remediation
    provides: "Pre-flight decisions from 01-01 (WIP-inclusion decision, python-dotenv approval); .gitignore/.env exclusion from 01-02"
provides:
  - "04_value_detector.py no longer hardcodes the Odds API key; reads ODDS_API_NOKKEL from environment via python-dotenv"
  - "Fail-fast missing-key path: exits 1 with a clear Norwegian message before touching the model or the network"
  - ".env.example committed, documenting the required env var name with a placeholder"
  - "KOMME_I_GANG.md Steg 4 corrected to teach the .env convention instead of hardcoding"
  - "Pre-existing 72-line WIP in 04_value_detector.py (dynamic season detection, MAX_ODDS, sys.exit(1) fix, KampDato tracking) now committed"
affects: ["01-repo-hygiene-config-remediation plan 05 (key rotation)"]

# Tech tracking
tech-stack:
  added: [python-dotenv>=1.2.3]
  patterns: ["fail-fast os.environ.get() + explicit falsiness check + sys.exit(1), matching existing codebase error-handling style", "env var name transliterated to ASCII (ODDS_API_NOKKEL) while Python identifier stays Norwegian (API_NØKKEL)"]

key-files:
  created:
    - .env.example
  modified:
    - requirements.txt
    - 04_value_detector.py
    - KOMME_I_GANG.md

key-decisions:
  - "Env var name is ASCII ODDS_API_NOKKEL, not ODDS_API_NØKKEL — bash/zsh cannot export a variable name containing Ø ('not a valid identifier'), which would break shell export, cron/launchd env blocks, and the missing-key verification command. The Python identifier stays API_NØKKEL, preserving the Norwegian-identifier convention where it actually applies."
  - "Squashed a premature standalone commit (requirements.txt + .env.example) via git reset --soft HEAD~1 and re-committed together with 04_value_detector.py and KOMME_I_GANG.md as one combined commit, matching the plan's explicit Task 3 instruction and its acceptance criterion that HEAD contain exactly four files — same self-correction pattern used in 01-02."
  - "KOMME_I_GANG.md folded into this plan's scope (RESEARCH.md Open Question 1) — leaving it unaddressed would recreate the doc/code mismatch HYG-03 fixes elsewhere in this phase."

patterns-established:
  - "Pattern: when a plan's acceptance criteria assert an exact file-set on a single commit (git show --stat HEAD), verify staged content before committing rather than committing incrementally per task — self-correct via soft reset if an early task is committed prematurely."

requirements-completed: [HYG-01]

# Metrics
duration: 15min
completed: 2026-08-20
---

# Phase 1 Plan 3: Env-Var API Key Load Summary

**Removed the hardcoded Odds API key from `04_value_detector.py`, replacing it with a fail-fast `ODDS_API_NOKKEL` env-var load via `python-dotenv`, verified empirically to exit 1 with a clear Norwegian message before any model load or network call.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-08-20T19:00:00Z (approx)
- **Completed:** 2026-08-20T19:15:06Z
- **Tasks:** 3
- **Files modified:** 4 (`requirements.txt`, `.env.example` created, `04_value_detector.py`, `KOMME_I_GANG.md`)

## Accomplishments
- Declared and installed `python-dotenv>=1.2.3` (confirmed importable in the project venv)
- Created `.env.example` documenting `ODDS_API_NOKKEL` with an obvious placeholder, never a real secret
- Replaced the hardcoded key literal in `04_value_detector.py` with `os.environ.get("ODDS_API_NOKKEL")` behind an explicit `if not API_NØKKEL: ... sys.exit(1)` guard, placed structurally before the `nba_modell.pkl` load
- Proved empirically (not assumed) that running the script with the env var unset and no `.env` present exits with code exactly `1`, prints a message naming `ODDS_API_NOKKEL`, and never reaches `Laster inn trent modell` — i.e., fails before model load and before any network call
- Corrected `KOMME_I_GANG.md` Steg 4 to teach the `.env` convention, removing the exact "paste your key into source" anti-pattern instruction
- Preserved the pre-existing 72-line WIP in `04_value_detector.py` (dynamic season detection via `gjeldende_sesong()`, `MAX_ODDS` constant, `sys.exit(1)` fix on the odds-fetch error path, `KampDato` tracking in the output CSV) per the 01-01-SUMMARY.md developer decision to include it in this commit
- Left `MIN_VALUE_TERSKEL = 0.05` and `MAX_ODDS = 4.00` unchanged (D-05) — no threshold values touched
- Confirmed `03_tren_modell.py`, `05_skadefilter.py`, `06_bot.py` remain untouched, modified-but-uncommitted, exactly as before this plan ran

## Task Commits

1. **Task 1: Declare/install python-dotenv, create .env.example** - staged, then squashed into the Task 3 combined commit (see below)
2. **Task 2: Replace hardcoded key with fail-fast env-var load** - staged, then included in the Task 3 combined commit
3. **Task 3: Correct KOMME_I_GANG.md and commit the HYG-01 change set** - `cb2f028` (fix)

**Plan metadata:** (this SUMMARY.md commit, see final commit below)

_Note: the plan's Task 3 action explicitly required staging and committing all four files (`04_value_detector.py`, `.env.example`, `requirements.txt`, `KOMME_I_GANG.md`) as a single commit, with an acceptance criterion asserting `git show --stat --name-only --format= HEAD` lists exactly those four paths. Task 1's files were initially committed standalone (`de4dea2`); this was caught before Task 3 and corrected via `git reset --soft HEAD~1` (safe: local-only, unpushed commit), then all four files were staged and committed together as `cb2f028`, satisfying the plan's exact-file-set acceptance criterion._

## Files Created/Modified
- `requirements.txt` - appended `python-dotenv>=1.2.3`, matching the existing loose `>=` style, no reordering
- `.env.example` - new, three lines: two Norwegian comments plus `ODDS_API_NOKKEL=din-nokkel-her` placeholder
- `04_value_detector.py` - added `import os`, `import sys`, `from dotenv import load_dotenv`, `load_dotenv()` call before KONFIGURASJON; replaced the hardcoded key literal with `os.environ.get("ODDS_API_NOKKEL")` + fail-fast guard; updated module docstring line 14 to point at `.env`/`.env.example`; carries the pre-existing 72-line WIP (season detection, MAX_ODDS, sys.exit(1) fix, KampDato tracking)
- `KOMME_I_GANG.md` - rewrote Steg 4 to describe copying `.env.example` to `.env` and setting `ODDS_API_NOKKEL`, removed the "paste key into source" instruction entirely

## Decisions Made
- **`ODDS_API_NOKKEL` (ASCII), not `ODDS_API_NØKKEL`:** verified this session that neither bash nor zsh can export a variable name containing `Ø` (`export ODDS_API_NØKKEL=x` → "not a valid identifier" in bash, "not valid in this context" in zsh). Using the ASCII name keeps the variable settable via shell export, cron/launchd env blocks, and the plan's own verification command. The Python identifier `API_NØKKEL` is unchanged, preserving the Norwegian-identifier convention at the language level where it's actually enforceable.
- **KOMME_I_GANG.md folded into HYG-01 scope:** RESEARCH.md's Open Question 1 asked whether this file was in scope; resolved yes — leaving Steg 4 instructing users to hardcode the key would recreate exactly the doc/code mismatch HYG-03 fixes elsewhere in this phase.
- **Combined single commit for all four files:** followed the plan's explicit Task 3 staging instruction and its acceptance criterion (`git show --stat --name-only --format= HEAD` must list exactly four paths), requiring a self-correction (soft reset) after Task 1's files were prematurely committed alone.

## Deviations from Plan

None from a scope/content perspective — all three tasks executed exactly as specified (package declared/installed, `.env.example` created, key replaced with fail-fast env-var load, docstring/setup-guide corrected, thresholds untouched). One process-level self-correction: Task 1's files (`requirements.txt`, `.env.example`) were initially committed standalone before Task 3's explicit combined-commit instruction was fully accounted for; caught immediately, corrected via `git reset --soft HEAD~1` on the just-created local commit (no shared/pushed history affected), then recommitted together with `04_value_detector.py` and `KOMME_I_GANG.md` in the single commit the plan requires. This mirrors the identical self-correction pattern documented in `01-02-SUMMARY.md`.

## Issues Encountered

None blocking. The commit-granularity self-correction described above was resolved immediately and safely (local-only, unpushed commit).

## User Setup Required

None for this plan's own scope. Key rotation on the-odds-api.com (D-02) remains an outstanding manual action for the developer, deferred to plan 05 per CONTEXT.md — this plan only changes how the key is *loaded*, it does not (and cannot) rotate the already-exposed value.

## Next Phase Readiness

- HYG-01's code half is closed: no key literal exists in tracked source (`git show HEAD:04_value_detector.py` contains zero occurrences of the leaked literal), the script fails fast and clearly when `ODDS_API_NOKKEL` is unset, and `.env.example` plus the corrected `KOMME_I_GANG.md` teach a fresh clone the required convention without reading source.
- Key rotation on the-odds-api.com (T-01-10, D-02) is still outstanding — the exposed literal remains readable in git history at commit `c058a1a` (history scrubbing explicitly deferred per D-03). This is a real, open risk until the developer rotates the key in plan 05.
- Plan 04 (HYG-03: doc/code drift reconciliation on `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt`) can proceed — this plan did not touch either file.
- Plan 05 can proceed to close key rotation once the developer performs the manual the-odds-api.com dashboard action.
- No blockers introduced by this plan.

---
*Phase: 01-repo-hygiene-config-remediation*
*Completed: 2026-08-20*

## Self-Check: PASSED

- FOUND: .env.example
- FOUND: 04_value_detector.py
- FOUND: KOMME_I_GANG.md
- FOUND: requirements.txt
- FOUND: 01-03-SUMMARY.md
- FOUND: cb2f028 (commit exists in git log)
