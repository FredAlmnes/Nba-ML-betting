# Phase 1: Repo Hygiene & Config Remediation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-19
**Phase:** 1-Repo Hygiene & Config Remediation
**Areas discussed (auto mode — recommended option selected for each):** API key handling, modell_utils.py tracking, doc/code reconciliation, scratch artifacts

---

## API key handling (HYG-01)

| Option | Description | Selected |
|--------|-------------|----------|
| python-dotenv + `.env` (git-ignored) | Standard Python env-var config pattern, matches STACK.md research | ✓ |
| Bare `os.environ`, no dotenv | Requires user to export the var in shell every session, more friction | |
| Config file (non-.env) | Adds a new convention when `.gitignore` already has `.env` support | |

**User's choice:** [auto] python-dotenv + `.env` (recommended default per research/STACK.md)
**Notes:** Key rotation itself is a manual step only the user can do on the-odds-api.com. Git history scrubbing considered and explicitly deferred — destructive, force-push required, public repo, needs separate explicit approval.

---

## modell_utils.py tracking (HYG-02)

| Option | Description | Selected |
|--------|-------------|----------|
| `git add` + commit as-is | File is already correct, just untracked | ✓ |
| Refactor while tracking | Bundle cleanup with tracking | |

**User's choice:** [auto] Track as-is, no refactor bundled in
**Notes:** Keeps this phase's scope to hygiene only — refactoring is Phase 2's job (CORE-01).

---

## Reconciling documented fix vs. running code (HYG-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Apply the old proposed thresholds now | KALIBRERING_RAPPORT.md's `MIN_VALUE_TERSKEL=0.20`/`MAX_ODDS=2.50` | |
| Mark as superseded, keep current thresholds | Docs get a note; running behavior doesn't change until Phase 5 validates values | ✓ |

**User's choice:** [auto] Mark as superseded (recommended — matches PROJECT.md's explicit stance against more unvalidated threshold guessing)
**Notes:** Applying the old report's numbers now would repeat the exact failure mode (in-sample/undeployed guessing) the whole project exists to fix. Validated numbers come from Phase 5's backtest only.

---

## Scratch/build artifacts

| Option | Description | Selected |
|--------|-------------|----------|
| Gitignore + auto-delete | Clean immediately | |
| Gitignore only, flag deletion for user confirmation | Safer — don't destroy local files without explicit confirmation | ✓ |

**User's choice:** [auto] Gitignore only; deletion deferred pending explicit user confirmation
**Notes:** `_linux_pkgs/`, `_pip_tmp/`, `_wheels/`, `_test.bin`, `test_write.tmp` look like accidental local artifacts but weren't confirmed as safe to delete.

---

## Claude's Discretion

- Exact wording of the "superseded" header note on `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt`
- Whether those two docs stay at repo root or move into a `docs/`/`.planning/` archive folder

## Deferred Ideas

- Git history scrubbing (BFG/`git filter-repo`) to remove the leaked key from all past commits — needs separate explicit user approval outside autonomous phase execution
- Deletion of scratch/build artifacts — gitignored now, actual deletion needs explicit user confirmation
