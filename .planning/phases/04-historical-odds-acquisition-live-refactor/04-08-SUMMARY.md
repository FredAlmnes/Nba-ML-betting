---
phase: 04-historical-odds-acquisition-live-refactor
plan: 08
subsystem: bot-orchestration
tags: [refactor, tdd, kjor-pipeline, crash-barrier, subprocess-removal]

# Dependency graph
requires:
  - phase: 04-02
    provides: "skadefilter.py's filtrer_bets_for_skader()/skriv_skadefilter_csv() — the importable injury-filter core this plan wires in-process"
  - phase: 04-06
    provides: "verdi_deteksjon.py's last_modell()/finn_value_bets()/skriv_value_bets_csv() — the importable value-detection core this plan wires in-process"
provides:
  - "06_bot.py's kjør_pipeline() — calls odds.hent_api_nokkel(), verdi_deteksjon.*, and skadefilter.* directly in-process, with an explicit except (Exception, SystemExit) crash barrier replacing the old subprocess boundary's accidental one"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "except (Exception, SystemExit) as the explicit, documented replacement for an accidental process-boundary crash barrier, when in-process code can call sys.exit() (Pitfall 5, 04-RESEARCH.md)"

key-files:
  created: [tests/test_bot.py]
  modified: [06_bot.py, skadefilter.py, verdi_deteksjon.py, .planning/REQUIREMENTS.md]

key-decisions:
  - "Reworded two pre-existing docstring lines in skadefilter.py (04-02) and verdi_deteksjon.py (04-06) that used the literal substring 'subprocess' — they tripped this plan's own repo-wide subprocess grep acceptance check (same self-reference pitfall 04-04-SUMMARY.md/04-06-SUMMARY.md hit with load_dotenv()/requests.get); no behavior change, prose-only"

patterns-established: []

requirements-completed: [ODDS-02]

# Metrics
duration: ~25min
completed: 2026-08-24
---

# Phase 4 Plan 8: Direct-Call Bot Orchestration Summary

**Replaced 06_bot.py's two subprocess.run() shell-outs to 04_value_detector.py/05_skadefilter.py with direct in-process calls to odds.py/verdi_deteksjon.py/skadefilter.py, deleted the hardcoded python3.10 PYTHONPATH hack those subprocesses needed, and explicitly restored the crash barrier the process boundary used to provide by accident — proven end-to-end by a real, developer-approved daily run.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-24 (continuation of Phase 4 execution)
- **Completed:** 2026-08-24
- **Tasks:** 2 completed (1 auto/TDD, 1 checkpoint:human-verify)
- **Files modified:** 4 (tests/test_bot.py created; 06_bot.py, skadefilter.py, verdi_deteksjon.py modified)

## Accomplishments

- `06_bot.py`'s `kjør_pipeline()` rewritten to call `odds.hent_api_nokkel()`, `verdi_deteksjon.last_modell()`/`finn_value_bets()`/`skriv_value_bets_csv()`, and `skadefilter.filtrer_bets_for_skader()`/`skriv_skadefilter_csv()` directly — no `subprocess.run`, no `sys.executable` — while preserving the exact same console narration (`Kjører value detector...` / `Kjører skadefilter...`) and return contract (`DataFrame` of `Skadestatus`-`OK` rows, or `None`)
- The hardcoded `venv/lib/python3.10/site-packages` `PYTHONPATH` construction (D-05/D-06 tech debt, present since before Phase 1) is gone, along with the `subprocess`/`sys` imports it required
- The crash barrier the subprocess boundary used to provide by accident is now explicit: the whole pipeline body is wrapped in `try: ... except (Exception, SystemExit) as e: print(...); return None`, with an inline comment explaining why the `SystemExit` half is load-bearing — `odds.hent_api_nokkel()`/`odds._utfor_kall()` both call `sys.exit(1)` on failure, which is a `BaseException` subclass a bare `except Exception` would NOT catch, and which would now kill the bot mid-run before `sjekk_resultater`'s settled bets and updated bankroll are persisted
- `verdi_deteksjon.skriv_value_bets_csv()`/`skadefilter.skriv_skadefilter_csv()` are still called unconditionally even though `06_bot.py` no longer reads the CSVs back — preserves the operator's daily audit artefacts and 05's standalone-run contract, per the plan's explicit instruction (avoids reintroducing the 2026-08-19 stale-file bug)
- `tests/test_bot.py` (new, 8 tests): success path (only `Skadestatus` `OK` rows returned), `test_pipeline_feil_degraderer_grasiost` (RuntimeError from `finn_value_bets` degrades to `None`, does not propagate), `SystemExit(1)` from `odds.hent_api_nokkel()` degrades to `None` (the Pitfall 5 case), exception from `skadefilter.filtrer_bets_for_skader` degrades to `None`, empty `value_bets` list returns `None`, all-`USIKKER` bets returns `None`, importing `06_bot.py` via `importlib` makes no `nba_api` call, and a source-level grep-equivalent assertion that no `subprocess`/`python3.10`/`PYTHONPATH` string remains in the file
- Full TDD gate followed: RED commit (8 failing tests — `AttributeError: <module 'bot'> has no attribute 'odds'`, confirming `06_bot.py` still used `subprocess`) → GREEN commit (implementation, all 8 new tests pass, full 125-test suite green)
- Task 2 (checkpoint:human-verify): the developer ran `venv/bin/python 06_bot.py` for real against the live Odds API and real `nba_api` endpoints. Outcome, verbatim from the coordinator: **"ja det er godkjent"** ("yes, approved") — confirmed no `ModuleNotFoundError`, and the full daily cycle completed: settled a pending bet, ran the value detector, ran the skadefilter, placed a new bet, and regenerated `dashboard.html`. This closes Pitfall 6 (04-RESEARCH.md) by running rather than by assuming — the `python3.10` PYTHONPATH removal is proven safe against the real, multi-interpreter-version committed `venv/`.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for kjør_pipeline direct-call refactor** - `75c0863` (test)
2. **Task 1 (GREEN): Direct-call kjør_pipeline + restored crash barrier** - `64d78d7` (feat)
3. **Task 2 (checkpoint:human-verify): Real daily run** - no code commit (verification-only task); outcome recorded here per the checkpoint's own instruction

## Files Created/Modified

- `tests/test_bot.py` (new, 185 lines) - 8 tests covering the graceful-degradation matrix for the direct-call pipeline, including the `SystemExit` case; loads `06_bot.py` via the `importlib.util.spec_from_file_location` recipe (leading-digit filename) and stubs `bot.odds`/`bot.verdi_deteksjon`/`bot.skadefilter` with `SimpleNamespace` fakes so no test ever touches the network, the model pickle, or the real JSON state files
- `06_bot.py` - `kjør_pipeline()` rewritten (imports: `subprocess`/`sys` removed, `odds`/`skadefilter`/`verdi_deteksjon` added); docstring updated to explain the in-process call chain and the explicit crash-barrier rationale
- `skadefilter.py` - one docstring line reworded (self-reference pitfall, see Decisions)
- `verdi_deteksjon.py` - one docstring line reworded (self-reference pitfall, see Decisions)
- `.planning/REQUIREMENTS.md` - ODDS-02 marked complete; traceability row updated to `Phase 4 | Complete`

## Decisions Made

- Reworded two pre-existing docstring lines in `skadefilter.py` (04-02) and `verdi_deteksjon.py` (04-06) that used the literal substring `subprocess` when describing the *old* architecture — they tripped this plan's own acceptance-criteria grep (`grep -rn "subprocess" --include=*.py . | grep -v venv/ | grep -v tests/` must return nothing). Same self-reference pitfall `04-04-SUMMARY.md`/`04-06-SUMMARY.md` documented for `load_dotenv()`/`requests.get`. No behavior change — prose-only, caught before commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Reworded self-referential "subprocess" docstring mentions in skadefilter.py/verdi_deteksjon.py**
- **Found during:** Task 1 acceptance-criteria verification
- **Issue:** Both files (created in prior plans 04-02/04-06, out of this plan's `files_modified` scope) contained the literal word "subprocess" in explanatory docstring prose about the pre-refactor architecture, tripping this plan's own repo-wide `grep -rn "subprocess"` acceptance check
- **Fix:** Reworded the two lines to say "en egen underprosess" instead of the literal string, preserving the same meaning
- **Files modified:** `skadefilter.py`, `verdi_deteksjon.py`
- **Commit:** `64d78d7` (folded into the GREEN commit, caught pre-commit)

## Issues Encountered

None beyond the self-reference grep trip above (caught and fixed before any commit landed in a failing state).

## User Setup Required

None — Task 2's real end-to-end run was performed by the developer directly (live Odds API call + real `nba_api` calls), per the plan's explicit instruction that this must be the developer's own invocation, not the executor's, since it mutates real paper-trading state (`bankroll.json`/`bets.json`) and spends a live API credit.

**Post-verification state note:** after the Task 2 run was approved, the coordinator separately requested (outside this plan's scope, in the main session) that `bankroll.json`/`bets.json` be reset to a clean starting state (`{"saldo": 1000.0, "historikk": []}` / `[]`) before resuming betting going forward. That reset happened *after* the verification run and does not affect this plan's correctness — the checkpoint's purpose (proving the refactored pipeline runs end-to-end without a `ModuleNotFoundError` and completes the full daily cycle) was already satisfied by the run itself.

## TDD Gate Compliance

RED gate: `75c0863` (`test(04-08): add failing tests for kjør_pipeline direct-call refactor`) — confirmed failing before the rewrite (`AttributeError: <module 'bot'> has no attribute 'odds'`, since the old `kjør_pipeline()` still shelled out via `subprocess.run`).
GREEN gate: `64d78d7` (`feat(04-08): call value detector and injury filter in-process from 06_bot.py`) — all 8 new tests pass, full 125-test suite green.
No REFACTOR commit needed — the one docstring self-reference fix was folded into the GREEN commit itself, caught before commit.

## Checkpoint Outcome (Task 2)

**Type:** checkpoint:human-verify (gate="blocking")
**Resume signal received:** `godkjent` — verbatim from the coordinator: *"ja det er godkjent"* ("yes, approved"). They confirmed the live `venv/bin/python 06_bot.py` run behaved correctly: no `ModuleNotFoundError`, full daily cycle completed (settled a bet, ran value detector, ran skadefilter, placed a new bet, regenerated dashboard).
**No-games-day outcome:** not applicable — real games were in progress and the pipeline placed a bet.
**ModuleNotFoundError:** none occurred. D-06 (removing the hardcoded `python3.10` `PYTHONPATH` hack) is proven safe against the real, multi-interpreter-version committed `venv/`.
**PYTHONPATH hack reinstated:** no — not needed, per the above.

## Next Phase Readiness

- ODDS-02 is now fully satisfied: no `subprocess` invocation of the value-detector/skadefilter pipeline remains anywhere in the codebase (verified via repo-wide grep excluding `venv/`/`tests/`), and the removal is proven safe by a real, human-approved daily run — not just by successful imports.
- This was ODDS-02's last piece (both extraction halves landed in 04-02/04-06); Phase 4's remaining open item is ODDS-01's full paid historical backfill, tracked separately in plan 04-09.
- No blockers.

---
*Phase: 04-historical-odds-acquisition-live-refactor*
*Completed: 2026-08-24*

## Self-Check: PASSED

- FOUND: tests/test_bot.py
- FOUND: .planning/phases/04-historical-odds-acquisition-live-refactor/04-08-SUMMARY.md
- FOUND: 75c0863 (test RED commit)
- FOUND: 64d78d7 (feat GREEN commit)
