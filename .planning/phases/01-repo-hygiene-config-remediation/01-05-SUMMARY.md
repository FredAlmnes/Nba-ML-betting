---
phase: 01-repo-hygiene-config-remediation
plan: 05
subsystem: config
tags: [git-hygiene, secrets, key-rotation, phase-gate]

# Dependency graph
requires:
  - phase: 01-repo-hygiene-config-remediation
    provides: "Fail-fast ODDS_API_NOKKEL env-var loading (01-03) and superseded doc notes (01-04) that this plan's battery re-verifies end-to-end"
provides:
  - "The Odds API key leaked in commit c058a1a is rotated and dead; a rotated key lives only in a local, git-ignored .env"
  - "All four 01-VALIDATION.md checks (HYG-01 static, HYG-01 fail-fast, HYG-02 fresh clone, HYG-03 docs) re-run green against the final phase state, plus a rotation-specific assertion"
  - "Live end-to-end proof that 04_value_detector.py authenticates against The Odds API with the rotated key"
  - "Phase 1 closed: HYG-01, HYG-02, HYG-03 all satisfied"
affects: ["Phase 2 (Shared Core Extraction) — can now build on a repo with no live secret exposure and no doc/code drift", "Phase 5 (backtest) — inherits a clean, non-leaking config baseline"]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - .env (git-ignored, not committed — contains the rotated key)
  modified: []

key-decisions:
  - "Task 1 (key rotation) is a human-only account action per D-02 — no agent wrote or touched the key value; only verified its presence and shape after the fact."
  - "D-03 (git-history scrubbing of the leaked key in c058a1a) remains explicitly deferred, not performed — rotation is treated as complete mitigation for the live-exposure threat (T-01-14), while the historical-value-still-in-history risk (T-01-15) is accepted and recorded here rather than silently dropped."
  - "D-08 (deletion of scratch artifacts _linux_pkgs/, _pip_tmp/, _wheels/, _test.bin, test_write.tmp) remains deferred — plan 01 chose ignore-only, and this plan does not revisit that choice."

patterns-established: []

requirements-completed: [HYG-01, HYG-02, HYG-03]

# Metrics
duration: 12min
completed: 2026-08-20
---

# Phase 1 Plan 5: Key Rotation & Phase 1 Acceptance Summary

**Closed the human half of HYG-01 by rotating the leaked Odds API key into a local, git-ignored `.env`, re-ran the full Phase 1 verification battery green end-to-end, proved the rotated key authenticates against The Odds API in a live run, and closed out Phase 1 with two items explicitly carried forward as deferred (not resolved): git-history scrubbing and scratch-artifact deletion.**

## Performance

- **Duration:** ~12 min (across the checkpoint pause and this continuation)
- **Completed:** 2026-08-20
- **Tasks:** 3 (Task 1: human-action checkpoint; Task 2: automated verification battery; Task 3: human-verify checkpoint)
- **Files modified:** 0 tracked files (`.env` is git-ignored by design; no source files changed in this plan)

## Accomplishments

### Task 1 — Key rotation (human-action checkpoint)

The developer rotated the Odds API key at the-odds-api.com and placed the new value in a local `.env`, copied from `.env.example`. Verified post-hoc rather than trusted at face value:

- `.env` exists at repo root and contains an `ODDS_API_NOKKEL=` line
- `git status --short` does not list `.env` in any state
- `git check-ignore -v .env` confirms it matches `.gitignore` line 7
- The loaded value is **not** the leaked literal `afc4f647c551e760f59f837769f5a3a1`

**Developer's resume-signal answer:** `"rotated"`

### Task 2 — Full Phase 1 verification battery (re-run fresh in this session)

All four `01-VALIDATION.md` checks plus the rotation-specific assertion were re-run from the repo root, output captured verbatim below.

```
== HYG-01 static ==
OK

== HYG-01 rotasjon ==
ROTERT OK

== HYG-01 fail-fast ==
FEIL: Miljøvariabelen ODDS_API_NOKKEL er ikke satt.
Kopier .env.example til .env og fyll inn din egen nøkkel:
  ODDS_API_NOKKEL=din-nøkkel-her
Hent en gratis nøkkel fra https://the-odds-api.com
exit=1
FAILFAST OK
.env gjenopprettet

== HYG-02 fresh clone ==
IMPORT OK
ingen .env i klonen (korrekt)

== HYG-03 dokumenter ==
KALIBRERING_RAPPORT.md OK
ENDRINGER_SUMMARY.txt OK
terskler uendret OK

== scratch ==
ingen scratch i git status
```

All acceptance criteria for Task 2 are met:
- HYG-01 static: zero occurrences of the leaked literal outside comments, no `API_NØKKEL = "` literal assignment, `os.environ.get("ODDS_API_NOKKEL")` present
- HYG-01 rotation: `ROTERT OK` — the loaded `.env` value is neither empty nor the leaked literal
- HYG-01 fail-fast: exit code exactly 1, error names `ODDS_API_NOKKEL`, no `Laster inn trent modell` reached, `.env` restored afterward
- HYG-02: fresh temp clone imports `KalibrertModell` cleanly and contains no `.env`
- HYG-03: both historical docs carry `SUPERSEDED` notes, live thresholds (`MIN_VALUE_TERSKEL=0.05`, `MAX_ODDS=4.00`) unchanged
- Scratch: no scratch artifacts appear in `git status --porcelain`

### Task 3 — Phase acceptance (human-verify checkpoint, approved)

1. **Live run.** `04_value_detector.py` was run with the rotated `.env` in place. It loaded the model, authenticated with the new key, printed "Henter dagens NBA-odds...", fetched 41 NBA games with odds, and reported "Gjenstående API-kall denne måneden: 499" — proving the new rotated key authenticates end-to-end and the fail-fast/env-var wiring works in a real run, then proceeded into value-bet computation.
2. **Supersession clarity.** The developer read the notes atop `KALIBRERING_RAPPORT.md` and `ENDRINGER_SUMMARY.txt` and confirmed both state plainly and unhedged that (a) the proposed values were never applied, (b) the live values are `MIN_VALUE_TERSKEL=0.05` / `MAX_ODDS=4.00`, and (c) validated replacements come from the Phase 5 backtest. No rewording was requested.
3. **Setup guide.** The developer read "Steg 4" in `KOMME_I_GANG.md` and confirmed it teaches the `.env`/`ODDS_API_NOKKEL` convention with no mention of hardcoding a key into source.
4. **Deferred items acknowledged** (see below) — recorded here and in `STATE.md`, not resolved in this plan.

**Developer's resume-signal answer:** `"approved"`

## Task Commits

This plan produced no source-code changes — Task 1 is a human account action (no repo diff besides the git-ignored `.env`), and Task 2 is verification-only (`files_modified: []` per plan frontmatter). No per-task commits were required. The only commit from this plan is the final metadata commit recorded below.

## Files Created/Modified

- `.env` (created, git-ignored, not committed) — contains the rotated `ODDS_API_NOKKEL` value, verified distinct from the leaked literal

No tracked source files were created or modified by this plan.

## Decisions Made

See `key-decisions` in frontmatter: rotation is a human-only action (D-02); git-history scrubbing (D-03) and scratch-artifact deletion (D-08) remain explicitly deferred rather than performed.

## Deviations from Plan

None — plan executed exactly as written across all three tasks.

## Issues Encountered

None. Both checkpoints resolved on the developer's first response ("rotated", then "approved") with no supersession-note rewrites required.

## Deferred Items (carried forward, not resolved by this plan)

| Item | Decision ID | Why deferred | Where tracked going forward |
|------|-------------|---------------|------------------------------|
| Git-history scrubbing of the leaked key value in commit `c058a1a` | D-03 | Requires a destructive force-push on a repo that has been public and may have been cloned/forked — needs its own explicit decision, not a side effect of this phase. Rotation neutralizes the leaked value's usefulness (T-01-14 mitigated); the value remaining readable in history is an accepted residual risk (T-01-15). | `STATE.md` Blockers/Concerns |
| Deletion of scratch artifacts (`_linux_pkgs/`, `_pip_tmp/`, `_wheels/`, `_test.bin`, `test_write.tmp`) | D-08 | Plan 01 (pre-flight) chose ignore-only over deletion; this plan does not revisit that choice. | `STATE.md` Blockers/Concerns |

## User Setup Required

None further — the one piece of human-only setup this plan needed (key rotation at the-odds-api.com) was completed in Task 1.

## Next Phase Readiness

Phase 1 is complete. All three success criteria from `ROADMAP.md` are met:

1. A fresh `git clone` + `pip install` can load `nba_modell.pkl` without an `ImportError` (`modell_utils.py` tracked — HYG-02, plan 02)
2. No Odds API key is hardcoded in source; `04_value_detector.py` reads it from `ODDS_API_NOKKEL`, and the previously-exposed key is rotated and dead (HYG-01, plans 03 + 05)
3. `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` are reconciled with the running code via explicit supersession notes (HYG-03, plan 04)

Phase 2 (Shared Core Extraction & Test Foundation) can proceed on a repo with no live secret exposure and no doc/code drift. The two deferred items (git-history scrubbing, scratch-artifact deletion) are recorded as open decisions in `STATE.md` and do not block Phase 2.

---
*Phase: 01-repo-hygiene-config-remediation*
*Completed: 2026-08-20*

## Self-Check: PASSED

- FOUND: .planning/phases/01-repo-hygiene-config-remediation/01-05-SUMMARY.md
- FOUND: .env exists at repo root (git-ignored, verified via `git check-ignore -v .env`)
- VERIFIED: HYG-01/HYG-02/HYG-03 battery re-run green in this session (output above)
