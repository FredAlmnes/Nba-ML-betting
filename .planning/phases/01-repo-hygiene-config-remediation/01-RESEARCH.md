# Phase 1: Repo Hygiene & Config Remediation - Research

**Researched:** 2026-08-19
**Domain:** Repo hygiene — secret management (env vars), git tracking of a previously-untracked runtime file, and doc/code drift reconciliation, in a single-user, no-CI, flat-script Python repo
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**API key handling (HYG-01)**
- **D-01:** Move `API_NØKKEL` in `04_value_detector.py` to an environment variable, loaded via `python-dotenv` from a git-ignored `.env` file (matches STACK.md research recommendation). Fail fast with a clear error message if the env var is missing — don't silently continue.
- **D-02:** Key rotation on the-odds-api.com is a manual account action only the user can perform — Claude cannot do this. CONTEXT flags it as a required manual step the user must complete (rotate old key, put new key in `.env`), not something the executor agent can do itself.
- **D-03:** Git history scrubbing (BFG/`git filter-repo` to remove the key from all past commits) is explicitly OUT OF SCOPE for this phase. It's a destructive, force-push-requiring operation on a public repo that may have been cloned/forked by others — requires explicit separate user approval outside of an autonomous phase execution. Rotating the key neutralizes the practical risk (old key becomes worthless) without needing history rewrite. Noted in Deferred Ideas.

**modell_utils.py tracking (HYG-02)**
- **D-04:** Simply `git add modell_utils.py` and commit it — no code changes needed, it's already correct per ARCHITECTURE.md, just untracked. Verify `.gitignore` doesn't have a pattern accidentally excluding it.

**Reconciling the documented fix vs. running code (HYG-03)**
- **D-05:** Do NOT apply the old proposed threshold values from `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` (`MIN_VALUE_TERSKEL=0.20`, `MAX_ODDS=2.50`) into the running code now. Per PROJECT.md's core value and Phase 5's whole purpose, threshold values must come from backtest validation, not another guess — applying the old report's numbers now would repeat exactly the pattern this project is trying to fix.
- **D-06:** Instead, mark both documents as historical/superseded: add a clear header note to `KALIBRERING_RAPPORT.md` and `ENDRINGER_SUMMARY.txt` stating they describe a fix that was drafted but never deployed, and that validated threshold values will come from the Phase 5 backtest instead. Leave the currently-running thresholds (`MIN_VALUE_TERSKEL=0.05`, `MAX_ODDS=4.00`) as-is — don't change strategy behavior in this phase, only fix the doc/code mismatch so it's no longer silently misleading.
- **D-07:** Do not build the shared config module here — that's explicitly Phase 2 (CORE-02). This phase's job is just to stop the docs from lying about what's running.

**Scratch/build artifacts**
- **D-08:** `_linux_pkgs/`, `_pip_tmp/`, `_wheels/`, `_test.bin`, `test_write.tmp` look like accidental local environment-setup artifacts (pip cache/build scratch), not intentional project files. Recommend adding matching patterns to `.gitignore`. **Do not delete these files without explicit user confirmation during execution** — they're untracked but may still be something the user wants to keep locally; flag them for the user to confirm deletion rather than having the executor remove them silently.
- **D-09:** `debug_kamp.py` is an existing, intentional manual debug utility (per ARCHITECTURE.md) — out of scope for this phase, leave as-is.

### Claude's Discretion
- Exact wording of the "superseded" header note on the two markdown reports — executor can phrase this naturally as long as it's unambiguous that the proposed values were never deployed and validated values will come from Phase 5.
- Whether to keep `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` at repo root or move them into a `docs/` or `.planning/` archive folder — either is fine as long as the supersession note is added; don't delete them, they're useful history.

### Deferred Ideas (OUT OF SCOPE)
- **Git history scrubbing** (removing the leaked key from all past commits via BFG/`git filter-repo`) — belongs outside this phase's autonomous execution. It's destructive (rewrites history, needs force-push) on a repo that's been public since the initial commit. Surface to the user as a separate explicit decision once the key is rotated, not bundled into Phase 1's automated work.
- **Deleting scratch/build artifacts** (`_linux_pkgs/`, `_pip_tmp/`, `_wheels/`, `_test.bin`, `test_write.tmp`) — gitignore them now; actual deletion needs explicit user confirmation, not autonomous execution.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|--------------------|
| HYG-01 | The Odds API key is loaded from an environment variable (not hardcoded in source) and the previously-exposed key is rotated | `python-dotenv` fail-fast pattern documented in Architecture Patterns → Pattern 1; `.env`/`.env.example` file structure in Recommended Project Structure; key rotation confirmed as manual/user-only action (D-02, not executor scope) — verification approach in Validation Architecture → Phase Requirements → Test Map |
| HYG-02 | `modell_utils.py` is tracked in git so a fresh clone can unpickle `nba_modell.pkl` without breaking | Confirmed via `git check-ignore` this session that no `.gitignore` pattern excludes it; safe `git add`/commit mechanics documented in Architecture Patterns → Pattern 3 (explicit-filename staging, given other untracked scratch artifacts present) |
| HYG-03 | The documented fix in `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` is reconciled with the running code — either applied, or explicitly superseded once backtest-validated values exist, so docs and running config never silently diverge again | Confirmed via direct file read this session that neither report's proposed values are present in `04_value_detector.py` (still `MIN_VALUE_TERSKEL=0.05`, `MAX_ODDS=4.00`); example "superseded" header wording provided in Code Examples; documentation-only fix, no threshold changes, per D-05/D-06 |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

`CLAUDE.md` is GSD-generated (mirrors PROJECT.md/STACK.md/CONVENTIONS.md/ARCHITECTURE.md), not a hand-written custom-directives file, but it does carry a few actionable constraints relevant to planning this phase:

- **Language/style:** "Existing codebase uses Norwegian identifiers and comments throughout; new/modified code should stay consistent with this unless a decision is made to deviate." Applies directly to HYG-01's new env var name (`ODDS_API_NØKKEL`, not `ODDS_API_KEY`) and any new print/error messages (Norwegian, matching `04_value_detector.py`'s existing `print(f"Feil ved henting...")` style).
- **No `.env` usage currently exists in code** (per CLAUDE.md's Configuration section) — confirms this phase introduces a genuinely new convention, not a partially-adopted one; the `.gitignore` `.env` line is the only existing scaffolding.
- **GSD workflow enforcement:** "Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it." — procedural constraint on the executor, not on code content; noted for completeness, not a planning input.
- **No formatter/linter config exists** — no style tool to run/conform to beyond hand-matching existing conventions (snake_case, Norwegian identifiers, f-string logging, `sys.exit(1)` fatal-error pattern).

None of these constraints conflict with CONTEXT.md's locked decisions (D-01 through D-09) — they reinforce the Norwegian-identifier convention already reflected in this research's code examples (`ODDS_API_NØKKEL`, Norwegian error strings).

## Summary

This is a low-complexity, mechanical remediation phase, not a domain-research-heavy one — confirmed by `.planning/research/SUMMARY.md`. The three requirements (HYG-01/02/03) map to three independent, narrow fixes, each already fully diagnosed in `.planning/codebase/CONCERNS.md`:

1. **HYG-01 (leaked API key):** `04_value_detector.py:30` hardcodes `API_NØKKEL = "<the odds api key>"`. Fix is to load it via `python-dotenv` from a git-ignored `.env` file, matching the existing (but currently unused) `.env` pattern already in `.gitignore`. Fail fast with `sys.exit(1)` if the env var is missing, mirroring the existing fatal-error pattern at `04_value_detector.py:63-67`. Key rotation and git-history scrubbing are explicitly out of scope for the executor (rotation is a manual, human-only action on the-odds-api.com; history scrubbing is deferred per D-03).
2. **HYG-02 (untracked `modell_utils.py`):** Confirmed not excluded by `.gitignore` (`git check-ignore` returns nothing). This is a one-line `git add modell_utils.py && git commit`, no code changes.
3. **HYG-03 (doc/code drift):** `KALIBRERING_RAPPORT.md` and `ENDRINGER_SUMMARY.txt` describe a threshold change (`MIN_VALUE_TERSKEL` 0.05→0.20, `MAX_ODDS` 4.00→2.50, plus a `KALIBRERING_FAKTOR`/`MIN_SIKKERHET` that don't exist in code at all) that was never applied. Per D-05/D-06, the fix is a documentation-only "superseded" header on both files — no code/threshold changes in this phase.

**Primary recommendation:** Treat this phase as three independent, sequential, low-risk file edits + one `git add`/commit. No new architecture, no new test framework is warranted — verification is manual/smoke-test style (run the script, confirm behavior), consistent with the rest of the repo's testing posture (zero existing automated tests).

## Architectural Responsibility Map

This project has no multi-tier architecture (no browser, no frontend server, no API server, no CDN, no database) — it is a single local Python process pipeline run manually or via a daily script. The standard tier table does not map cleanly; the table below substitutes the project's own layer vocabulary (per `ARCHITECTURE.md`) for the standard tiers, noting where each phase capability lives.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| API key / secret loading | Local script runtime (`04_value_detector.py`, module-level config) | — | No API/backend tier exists in this project; the "backend" *is* the local script process. `os.environ` + `python-dotenv` is the correct mechanism at this tier. |
| `modell_utils.py` git tracking | Version control (git) | — | Not a runtime tier at all — this is a repository-hygiene fix (`git add`), unrelated to any execution layer. |
| Doc/code drift reconciliation | Documentation (`KALIBRERING_RAPPORT.md`, `ENDRINGER_SUMMARY.txt`) | Local script runtime (`04_value_detector.py` config constants, read-only in this phase) | Docs must accurately describe what the runtime tier is actually doing; this phase edits docs only, not the runtime constants they describe. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `python-dotenv` | 1.2.3 (latest on PyPI, verified 2026-08-19) [VERIFIED: PyPI registry] | Loads key=value pairs from a `.env` file into `os.environ` at process start | De facto standard for local secret/config loading in Python scripts with no framework (Flask/Django have their own conventions; this is a flat-script repo). Already recommended independently in `.planning/research/STACK.md` for the same file/line. Zero-config, single function call (`load_dotenv()`), no new architecture. |

**Package name provenance:** `python-dotenv` was already named in this project's own prior research (`.planning/research/STACK.md`, itself sourced from PyPI JSON API lookups) and is widely known training-data knowledge — tag `[ASSUMED]` per provenance rule since the *name* was not re-discovered via Context7/official docs in this research session, even though its PyPI existence and current version were independently re-verified below.

### Supporting
None needed. No other new dependency is required for this phase — HYG-02 and HYG-03 involve no new libraries at all.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `python-dotenv` + `os.environ` | Plain `os.environ` with no `.env` loader (export in shell profile / systemd env) | Viable but worse UX for a single-user local script re-run manually and via cron/Task Scheduler on different machines — `.env` file is the simpler, more portable convention, and matches the `.gitignore` pattern the repo already reserves for it. Not recommended; no reason to deviate from what's already the documented plan (STACK.md, CONTEXT.md D-01). |
| `.env` file | OS keychain / secrets manager (e.g. macOS Keychain via `keyring` package) | Overkill for a single-user, single-machine, non-production paper-trading script. Adds a new dependency and platform-specific code for a threat model (local secret at rest) that `.env` + `.gitignore` already adequately addresses. |

**Installation:**
```bash
pip install python-dotenv
```

**Version verification:** Confirmed via `pip index versions python-dotenv` against the live PyPI index (2026-08-19): current release `1.2.3`, with a full prior release history back to `0.1.0` — actively maintained, no signs of abandonment. `[VERIFIED: PyPI registry]`

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `python-dotenv` | PyPI | Long-established (since ~2014, per version history to 0.1.0) | Very high (tens of millions/week — one of the most-depended-upon Python packages) | `github.com/theskumar/python-dotenv` | `[OK]` (slopcheck note: "Name starts with 'python-' — classic LLM naming pattern. Name looks like LLM bait but package is established.") | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

slopcheck ran successfully against the live PyPI registry (`slopcheck install python-dotenv`) and returned `[OK]`, explicitly noting the package name superficially resembles an LLM-hallucination naming pattern but is a genuinely established package. No postinstall-script check performed (Node.js-specific step, not applicable — this is a Python phase). This is the only external package this phase installs.

## Architecture Patterns

### System Architecture Diagram

This phase makes no changes to data flow — it only changes *where a config value is read from* and *what git tracks*. The relevant slice of the existing pipeline:

```text
.env (new, git-ignored, local only)
   │  ODDS_API_NØKKEL=xxxx
   ▼
python-dotenv: load_dotenv()  ──▶  os.environ
   │
   ▼
04_value_detector.py
   │  os.environ["ODDS_API_NØKKEL"]  (KeyError / missing ──▶ sys.exit(1), fail fast)
   ▼
requests.get(url, params={"apiKey": ...})  ──▶  The Odds API
```

```text
modell_utils.py (currently untracked)
   │
   │  git add modell_utils.py && git commit
   ▼
tracked in git  ──▶  fresh clone includes it  ──▶  03_tren_modell.py / 04_value_detector.py
                                                     `from modell_utils import KalibrertModell`
                                                     succeeds instead of ModuleNotFoundError
```

```text
KALIBRERING_RAPPORT.md / ENDRINGER_SUMMARY.txt (untracked, describe undeployed fix)
   │
   │  add "SUPERSEDED" header note (no threshold/code changes)
   ▼
docs now explicitly say: "these proposed values were never deployed;
validated values will come from Phase 5 backtest instead"
   │
   ▼
04_value_detector.py keeps running MIN_VALUE_TERSKEL=0.05, MAX_ODDS=4.00 (unchanged)
```

### Recommended Project Structure

No new directories needed. This phase touches:
```
.
├── .env                        # NEW — git-ignored, holds ODDS_API_NØKKEL, created locally by user (not by executor, see Pitfall below)
├── .env.example                # NEW (recommended) — committed, documents required var name with placeholder value
├── .gitignore                  # EDIT — add scratch-artifact patterns
├── 04_value_detector.py        # EDIT — load key from env var, fail fast if missing
├── modell_utils.py             # git add (no code change)
├── KALIBRERING_RAPPORT.md      # EDIT — add superseded header
└── ENDRINGER_SUMMARY.txt       # EDIT — add superseded header
```

### Pattern 1: Fail-fast environment variable loading (matches existing codebase convention)

**What:** Load `.env` via `python-dotenv`, read the required var via `os.environ[...]` (not `.get()` with a silent default), and exit with a clear, actionable message if it's missing — reusing the exact `sys.exit(1)` pattern the codebase already uses for API failures.

**When to use:** Any required secret/config value that the script cannot run without.

**Example:**
```python
# Source: python-dotenv official README (github.com/theskumar/python-dotenv) +
# existing codebase pattern at 04_value_detector.py:63-67 (sys.exit(1), not bare exit())
import os
import sys
from dotenv import load_dotenv

load_dotenv()  # reads .env in the current working directory into os.environ

API_NØKKEL = os.environ.get("ODDS_API_NØKKEL")
if not API_NØKKEL:
    print("FEIL: Miljøvariabelen ODDS_API_NØKKEL er ikke satt.")
    print("Opprett en .env-fil i prosjektroten med linjen:")
    print("  ODDS_API_NØKKEL=din-nøkkel-her")
    print("Hent en gratis nøkkel fra https://the-odds-api.com")
    sys.exit(1)  # NB: bare exit() gir exitkode 0 og skjuler feilen for 06_bot.py
```

**Why `os.environ.get(...)` + explicit `if not` check, not `os.environ["..."]` bare subscript:** a bare `KeyError` from `os.environ["ODDS_API_NØKKEL"]` produces a raw traceback, not the codebase's established user-facing Norwegian error-message convention. The explicit check preserves the existing error-handling style (see CONVENTIONS.md: "Missing-file errors use `try/except FileNotFoundError` with a user-facing instruction message").

**Load order caveat:** `load_dotenv()` must run *before* the `API_NØKKEL = ...` line executes — since this script has no `main()` guard and runs top-to-bottom on import/execution (per ARCHITECTURE.md's "Top-level module code instead of functions" anti-pattern, which this phase does not need to fix), the `load_dotenv()` call should be placed immediately after the imports, before the "KONFIGURASJON" section.

### Pattern 2: `.env.example` as committed documentation of required config

**What:** A committed, secret-free file listing the required env var name with a placeholder, so a fresh clone knows what to create without guessing.

**When to use:** Whenever `.env` is introduced as a new convention in a repo that has never used one — the repo's own `KOMME_I_GANG.md` setup guide currently instructs users to "Lim inn API-nøkkelen din i `04_value_detector.py`" (paste your key into the source file, `KOMME_I_GANG.md:45`), which is the exact anti-pattern this phase fixes. Note: updating `KOMME_I_GANG.md`'s setup instructions is not explicitly listed in CONTEXT.md's decisions — flagged in Open Questions below for the planner to scope in or explicitly defer.

**Example:**
```bash
# .env.example (committed)
ODDS_API_NØKKEL=your-the-odds-api-key-here
```

### Pattern 3: Safe `git add` of a previously-untracked, already-correct file

**What:** For HYG-02, no code changes are needed — only a git-tracking fix.

**Mechanics:**
```bash
# 1. Confirm .gitignore does not accidentally exclude the file (already verified this session:
#    `git check-ignore -v modell_utils.py` returns no match — it is NOT excluded)
git check-ignore -v modell_utils.py   # expect: no output = not ignored

# 2. Stage explicitly by filename — never `git add -A` / `git add .` in this repo right now,
#    because the working tree also contains untracked scratch artifacts (_linux_pkgs/, _wheels/,
#    _test.bin, etc. — see D-08) that must NOT be committed
git add modell_utils.py

# 3. Verify staged contents before committing — confirm only the intended file is staged
git status --short   # expect: "A  modell_utils.py" and nothing else newly staged

# 4. Commit
git commit -m "fix: track modell_utils.py so a fresh clone can unpickle nba_modell.pkl"
```

**Why this matters here specifically:** the repo currently has 6 other untracked items (`ENDRINGER_SUMMARY.txt`, `KALIBRERING_RAPPORT.md`, `_linux_pkgs/`, `_pip_tmp/`, `_test.bin`, `_wheels/`, `debug_kamp.py`, `test_write.tmp` per `git status --short`), several of which must explicitly NOT be committed (scratch artifacts) or must be committed with accompanying doc edits, not bare `git add`. A blanket `git add -A` at any point in this phase would sweep in the 100MB `_test.bin` and other scratch artifacts — this is the single highest-risk mechanical mistake an executor could make in this phase.

### Anti-Patterns to Avoid
- **`git add -A` / `git add .` anywhere in this phase:** the working tree has multiple untracked scratch artifacts (`_test.bin` at ~100MB, `_linux_pkgs/`, `_wheels/`, `_pip_tmp/`) that must not be committed. Always `git add <specific-file>`.
- **Silently defaulting the env var to the old hardcoded value if missing:** defeats the purpose of HYG-01 — must fail loudly (`sys.exit(1)`), not fall back.
- **Applying the `KALIBRERING_RAPPORT.md` threshold values to `04_value_detector.py` "since we're in there anyway":** explicitly forbidden by D-05 — those values were never backtest-validated; applying them now repeats the exact anti-pattern (undocumented, unvalidated threshold change) this phase exists to stop.
- **Deleting `_linux_pkgs/`, `_pip_tmp/`, `_wheels/`, `_test.bin`, `test_write.tmp` autonomously:** per D-08, these must only be added to `.gitignore` in this phase; deletion requires explicit user confirmation, not autonomous executor action.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Loading `.env` file into environment | A custom `.env` parser (`open(".env").readlines()` + manual split/strip) | `python-dotenv`'s `load_dotenv()` | Handles quoting, comments, multiline values, `export` prefixes, encoding edge cases that a naive parser will get wrong eventually; single well-maintained dependency, not worth reinventing for one env var. |

**Key insight:** This phase has almost nothing to hand-roll — it is two file edits, one dependency add, one `git add`, and two markdown header edits. Resist the temptation to "improve while you're in there" (e.g., don't refactor `04_value_detector.py`'s top-level execution style, don't touch team-name resolution, don't touch thresholds — all explicitly out of scope per D-05/D-07 and the Phase 2 boundary).

## Common Pitfalls

### Pitfall 1: Executor creates/populates the actual `.env` file with a real key
**What goes wrong:** An autonomous executor cannot obtain a new/rotated API key (that requires the user logging into the-odds-api.com, per D-02) — if the executor tries to create a working `.env`, it will either reuse the leaked key (defeats the purpose) or fail.
**Why it happens:** Natural instinct to "make the script actually runnable" as part of verification.
**How to avoid:** The executor's job is: (1) change the code to read from env var + fail fast, (2) create `.env.example` (no real secret), (3) leave the actual `.env` file creation and key rotation as an explicit manual step for the user (per D-02). Verification of HYG-01 should be: confirm the script fails with the new clear error message when `.env`/env var is absent (proves the fail-fast path works), not a full live run against The Odds API.
**Warning signs:** A commit accidentally includes a `.env` file, or the old key literal reappears anywhere in a new commit's diff.

### Pitfall 2: `.env` gets committed despite `.gitignore` already excluding it
**What goes wrong:** `.gitignore` already has a `.env` line (confirmed: `.gitignore:7`), so this is low-risk, but worth an explicit check since the whole phase is about not leaking secrets.
**How to avoid:** After creating any `.env`/`.env.example` files, run `git status --short` and confirm `.env` (without `.example`) shows as ignored/absent, never as `??` or staged. `.env.example` (no real secret) is fine to commit.
**Warning signs:** `git status` shows `.env` as untracked-but-not-ignored, or `git add` accepts it without a warning.

### Pitfall 3: Reviewing a suspicious file's contents before staging (general safety, applies directly here)
**What goes wrong:** This phase involves staging previously-untracked files (`modell_utils.py`) and editing files that historically contained a real secret (`04_value_detector.py`). A careless `git add`/commit after editing could re-commit the key if the edit doesn't fully remove the literal.
**How to avoid:** After editing `04_value_detector.py`, `git diff` (not just `git status`) before staging, to visually confirm the hardcoded key string is gone and only `os.environ`-based code remains. Same for any other file touched in this phase — always inspect `git diff`/`git status` output before commit, not just trust the edit was correct.
**Warning signs:** A `git diff` that still shows a long alphanumeric string literal assigned to any variable resembling a key/token/secret.

### Pitfall 4: Doc "superseded" note is ambiguous about whether values are live
**What goes wrong:** If the header note on `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` is vague ("this may be outdated"), a future reader (including a future Claude session, per the existing CONCERNS.md finding) could still misattribute current bot behavior to this "fix."
**How to avoid:** State explicitly and unambiguously: (1) these specific values were never applied to running code, (2) the values currently running are X/Y (name them), (3) validated replacement values will come from the Phase 5 backtest, not from this document. Per D-06/discretion note, exact wording is executor's discretion as long as these three facts are unambiguous.
**Warning signs:** A header note that hedges ("might not be current") rather than stating the fact plainly ("NOT deployed — superseded").

### Pitfall 5: `KOMME_I_GANG.md` setup guide still tells users to hardcode the key
**What goes wrong:** `KOMME_I_GANG.md:45` currently says "Lim inn API-nøkkelen din i `04_value_detector.py`" — if left as-is after HYG-01, the setup guide actively contradicts the new env-var convention and could lead a future user (or future Claude session following the guide) to reintroduce a hardcoded key.
**Why it happens:** Not explicitly listed as in-scope in CONTEXT.md's decisions (only `04_value_detector.py:30` is named as the file to fix) — easy to miss since it's a separate file.
**How to avoid:** Flagged as an Open Question below — recommend the planner either explicitly include a `KOMME_I_GANG.md` update in HYG-01's task scope, or explicitly note it as deferred with a reason. Leaving it silently unaddressed reintroduces a doc/code mismatch of the same flavor HYG-03 is fixing elsewhere in this same phase.
**Warning signs:** None yet — this is a proactive catch, not an already-materialized bug.

## Code Examples

### Fail-fast env var pattern (full context)
```python
# Source: pattern synthesized from python-dotenv README (github.com/theskumar/python-dotenv)
# + existing codebase pattern at 04_value_detector.py:63-67
import os
import sys
from dotenv import load_dotenv

load_dotenv()

API_NØKKEL = os.environ.get("ODDS_API_NØKKEL")
if not API_NØKKEL:
    print("FEIL: ODDS_API_NØKKEL mangler. Opprett en .env-fil (se .env.example).")
    sys.exit(1)
```

### `.gitignore` additions for scratch artifacts (D-08)
```gitignore
# Lokale build/pip-scratch-artefakter (ikke del av prosjektet)
_linux_pkgs/
_pip_tmp/
_pip_home/
_wheels/
_test.bin
test_write.tmp
```
Note: `_pip_home/` was not in CONTEXT.md's explicit D-08 list (it's currently an empty directory so it doesn't show in `git status`), but matches the same "pip scratch artifact" naming pattern as the three sibling directories — worth including proactively so it doesn't surface as a surprise `??` entry later. Flagged for planner discretion.

### Superseded-doc header note (example wording, per D-06/discretion)
```markdown
> **⚠️ SUPERSEDED — NOT DEPLOYED.** This document describes a threshold/calibration change
> (`MIN_VALUE_TERSKEL` 0.05→0.20, `MAX_ODDS` 4.00→2.50, plus a calibration factor and
> minimum-confidence filter) that was drafted on 2026-04-06 but **was never applied** to
> `04_value_detector.py`. The code has always continued running the original values
> (`MIN_VALUE_TERSKEL=0.05`, `MAX_ODDS=4.00`). Validated replacement threshold values will
> come from the Phase 5 walk-forward backtest, not from this document. Kept for historical
> context only — do not apply these numbers directly to running code.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Hardcoded secret literal in tracked source | `.env` (git-ignored) + `python-dotenv` + `os.environ` | N/A — this has been standard Python practice for years, not a recent change | Removes the secret from any future commit; does not retroactively remove it from git history (D-03, deferred). |

**Deprecated/outdated:** N/A — no library/API deprecation involved in this phase.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | `python-dotenv` is the correct/intended package name (not a similarly-named alternative) | Standard Stack | Low — name matches this project's own prior STACK.md research, PyPI existence + version independently reconfirmed this session, and slopcheck rated it `[OK]` as an established package. |

**If this table is empty:** N/A — one low-risk assumption logged above (package-name provenance only; existence/version/legitimacy were independently verified).

## Open Questions

1. **Should `KOMME_I_GANG.md`'s setup instructions be updated as part of HYG-01?**
   - What we know: `KOMME_I_GANG.md:45` currently instructs pasting the key directly into `04_value_detector.py` — the exact anti-pattern HYG-01 fixes. CONTEXT.md's decisions only name `04_value_detector.py` as the file to change.
   - What's unclear: Whether this was an intentional scope-narrowing by the user during `/gsd:discuss-phase`, or simply not mentioned.
   - Recommendation: Planner should either fold a one-line `KOMME_I_GANG.md` edit into the HYG-01 task (cheap, consistent, prevents a fresh doc/code mismatch), or explicitly note it as deferred. Low effort either way — flagging so it's a deliberate choice, not an oversight.

2. **Should `_pip_home/` be added to `.gitignore` alongside the four scratch patterns named in D-08?**
   - What we know: It's the same category of local pip-scratch artifact as `_pip_tmp/`/`_wheels/`/`_linux_pkgs/`, but currently empty (doesn't show in `git status` since git doesn't track empty dirs) and wasn't named in CONTEXT.md's D-08 list.
   - What's unclear: Whether its omission from D-08 was deliberate or just because it wasn't visible in `git status --short` at discussion time.
   - Recommendation: Include it proactively in the `.gitignore` addition — zero downside, prevents a future surprise `??` entry if it gets populated again.

3. **Should `.env.example` be created as part of HYG-01?**
   - What we know: Not explicitly requested in CONTEXT.md, but is the standard companion pattern to introducing `.env`-based config in a repo that's never had one, and directly supports the phase's stated goal ("a fresh clone... can be configured... without exposing secrets").
   - What's unclear: Nothing blocking — this is a small, safe, additive file.
   - Recommendation: Include it; it's the standard way a fresh clone discovers what env var name to set without reading source code.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|----------|
| `python-dotenv` | HYG-01 | ✗ (not currently installed in `venv`) | — (latest: 1.2.3) | None needed — trivial `pip install python-dotenv`, no fallback required. |
| git | HYG-02, HYG-03 | ✓ | (repo already git-managed) | — |
| Python 3.14 venv | All | ✓ | 3.14.3 (per `venv/pyvenv.cfg`) | — |

**Missing dependencies with no fallback:** none — `python-dotenv` install is a zero-risk, one-line `pip install`.
**Missing dependencies with fallback:** none applicable.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None installed (`pytest` not in `requirements.txt`; confirmed zero test files/config anywhere in repo per `.planning/codebase/STACK.md`) |
| Config file | none — see Wave 0 |
| Quick run command | N/A — no framework; use manual/smoke verification (see below) |
| Full suite command | N/A |

This phase does not warrant introducing `pytest` — it contains no testable business logic (no functions with meaningful input/output contracts are added; changes are config-loading, git-tracking, and doc edits). Automated test-framework setup is explicitly scoped to Phase 2 (CORE-03) per `ROADMAP.md`. Verification here is manual/smoke-test style, matching the rest of the repo's current testing posture.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Verification Command | File Exists? |
|--------|----------|-----------|------------------------|--------------|
| HYG-01 | Missing `ODDS_API_NØKKEL` env var causes a clear fatal error (exit code 1), not a silent failure or crash traceback | smoke (manual) | `unset ODDS_API_NØKKEL; python 04_value_detector.py; echo $?` — expect the FEIL message and exit code `1` | N/A — no test file needed, manual script invocation |
| HYG-01 | With `ODDS_API_NØKKEL` set (e.g. via a real `.env` after user rotates the key), the script reads the key from the env, not from a hardcoded literal | smoke (manual) + static check | `grep -n 'API_NØKKEL = "' 04_value_detector.py` should return nothing (no literal secret assignment remains); `grep -n 'os.environ' 04_value_detector.py` should show the new read | N/A |
| HYG-02 | Fresh clone can `import modell_utils` without `ModuleNotFoundError` | smoke (manual) | `git ls-files | grep modell_utils.py` (confirms tracked) + `git clone` to a temp dir and `python -c "from modell_utils import KalibrertModell"` | N/A |
| HYG-03 | `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` no longer silently imply their proposed values are live | manual review | Read the added header note; confirm it states the values were never deployed and names the actual running values | N/A |

### Sampling Rate
- **Per task commit:** Run the relevant smoke check above (e.g. `grep` for the removed literal, or the missing-env-var exit-code check) immediately after each file edit.
- **Per wave merge:** N/A — this phase is small enough to be a single wave; re-run all four smoke checks before considering the phase complete.
- **Phase gate:** All four manual checks above pass before `/gsd:verify-work`.

### Wave 0 Gaps
None — no test framework install is warranted for this phase (see Test Framework note above). If the planner nonetheless wants a first automated test in this repo ahead of Phase 2, a minimal option would be a single `pytest` test asserting `04_value_detector.py` raises `SystemExit(1)` when `ODDS_API_NØKKEL` is unset (using `monkeypatch.delenv` + `pytest.raises(SystemExit)`), but this pulls the top-level-script-execution refactor (currently out of scope, see ARCHITECTURE.md's "Top-level module code" anti-pattern) into scope prematurely, since the whole config block executes on import. Recommend deferring this to Phase 2, where `CORE-02`'s shared config module naturally makes the value testable in isolation.

*(No gaps blocking this phase — manual smoke verification is sufficient and appropriate given zero existing test infrastructure and no business logic being added.)*

## Security Domain

### Applicable ASVS Categories

This project has no authentication, session management, or access-control surface (single-user, no login, no server) — most ASVS categories do not apply. The relevant category for this phase is secrets/credential storage, which ASVS folds under Cryptography (V6) in spirit (credential-at-rest handling), though this phase is really "basic secrets hygiene" rather than a cryptographic control.

| ASVS Category | Applies | Standard Control |
|----------------|---------|-------------------|
| V2 Authentication | No | N/A — no login/auth system exists in this project |
| V3 Session Management | No | N/A — no sessions |
| V4 Access Control | No | N/A — single local user, no multi-user access control |
| V5 Input Validation | No (not touched by this phase) | N/A for HYG-01/02/03 specifically |
| V6 Cryptography / Secrets Management | Yes | Secrets loaded from environment variables via `python-dotenv`, sourced from a git-ignored `.env` file — never hardcoded in tracked source. `[CITED: OWASP ASVS secrets-management principle — credentials must not be stored in source code]` |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Hardcoded secret committed to a public git repo (already occurred: `04_value_detector.py:30`, public since initial commit `c058a1a`) | Information Disclosure | Move to env var (this phase) + rotate the exposed key (manual user action, D-02) + treat the old key as permanently compromised. Git history scrubbing (BFG/`git filter-repo`) is the complete fix but is explicitly deferred (D-03) — rotation alone neutralizes the practical risk without a destructive force-push. |
| Accidental re-commit of a secret via a careless `git add -A`/`.env` slip | Information Disclosure | `.gitignore` already excludes `.env`; this phase adds `.env.example` (no secret) as the committed counterpart. Always `git diff`/`git status` before staging (see Pitfall 3). |

## Sources

### Primary (HIGH confidence)
- `pip index versions python-dotenv` — live PyPI registry query, 2026-08-19: confirmed current version `1.2.3` and full release history. `[VERIFIED: PyPI registry]`
- `slopcheck install python-dotenv` — live PyPI-backed legitimacy check, 2026-08-19: `[OK]` verdict, established package. `[VERIFIED: PyPI registry]`
- Direct codebase inspection this session: `04_value_detector.py` (lines 1-70), `modell_utils.py` (full file), `.gitignore` (full file), `KALIBRERING_RAPPORT.md` (full file), `ENDRINGER_SUMMARY.txt` (full file), `KOMME_I_GANG.md` (full file), `requirements.txt` (full file), `git status --short`, `git check-ignore -v modell_utils.py`, `git ls-files | grep modell_utils` (confirms currently untracked), `./venv/bin/pip show python-dotenv` (confirms not currently installed). `[VERIFIED: codebase]`
- `.planning/codebase/CONCERNS.md`, `.planning/codebase/INTEGRATIONS.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONVENTIONS.md` — prior codebase-audit research, read this session. `[CITED: internal project docs]`
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/phases/01-repo-hygiene-config-remediation/01-CONTEXT.md` — canonical phase scope/decisions, read this session. `[CITED: internal project docs]`

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md`, `.planning/research/PITFALLS.md` — prior milestone-level research (dated 2026-08-19, same day), independently recommending `python-dotenv` for the same fix and documenting Pitfall 6 (config drift) / Pitfall 7 (untracked file) as already-materialized. `[CITED: internal project research]`

### Tertiary (LOW confidence)
None — no unverified WebSearch-only claims were needed for this phase; the fix set is small enough to fully verify directly against the codebase and PyPI.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — single package, version/legitimacy independently verified against PyPI and slopcheck this session
- Architecture: HIGH — no new architecture; all patterns directly observed in the existing codebase this session
- Pitfalls: HIGH — five of five pitfalls are either already-documented, already-occurred issues (per CONCERNS.md/PITFALLS.md) or directly derived from files read this session, not speculative

**Research date:** 2026-08-19
**Valid until:** 30 days (stable domain — no fast-moving library APIs involved; re-verify `python-dotenv` version if this phase is executed significantly later)
