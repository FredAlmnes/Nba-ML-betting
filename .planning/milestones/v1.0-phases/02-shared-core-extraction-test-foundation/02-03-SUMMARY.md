---
phase: 02-shared-core-extraction-test-foundation
plan: 03
subsystem: strategy-core
tags: [strategy, kelly, value-betting, dedup, pytest]

# Dependency graph
requires:
  - phase: 02-shared-core-extraction-test-foundation (plan 02)
    provides: pytest harness (pytest.ini, tests/conftest.py), config.py single source of truth
provides:
  - strategy.py — pure vig-removal/value/EV/Kelly-stake/dedup-key functions, zero project imports
  - beregn_innsats(saldo, modell_prob, odds, kelly_fraksjon, min_innsats, max_innsats) signature for plan 04/05/06 and Phase 5 backtest
  - tests/test_strategy.py extended to 16 tests (config + strategy)
affects: [02-04-PLAN.md, 02-05-PLAN.md, 02-06-PLAN.md, Phase 5 backtest]

# Tech tracking
tech-stack:
  added: []
  patterns: ["strategy.py: pure functions, config values as call-site parameters, zero project imports (D-06/A2)"]

key-files:
  created: [strategy.py]
  modified: [tests/test_strategy.py, 04_value_detector.py, 06_bot.py]

key-decisions:
  - "beregn_innsats's null-edge test uses (0.50, 2.00) instead of the plan interfaces block's (0.40, 2.50) example — the latter hits floating-point noise (1.5*0.4 != 0.6 exactly), producing kelly = 7.4e-17 (positive), which fails the <= 0 branch and clamps up to min_innsats (20.0) instead of returning 0.0. Verified this identical float behavior already existed in the pre-extraction 06_bot.py function — not a regression introduced by this plan."

patterns-established:
  - "Pattern: money-math and dedup-key logic live only in strategy.py, as pure functions taking config values as parameters; call sites (04, 06, future backtest) pass in config.* constants explicitly."

requirements-completed: [CORE-01, CORE-03]

# Metrics
duration: 10min
completed: 2026-08-21
---

# Phase 2 Plan 03: Strategy Core Extraction Summary

Extracted vig-removal, value/EV, half-Kelly stake sizing, and bet-dedup-key logic — previously inline/duplicated in `04_value_detector.py` and `06_bot.py` — into `strategy.py` as six pure, zero-dependency functions, then locked them behind 14 new pytest tests (16 total in `tests/test_strategy.py`, 17 across the whole suite).

## Performance

- **Duration:** 10 min
- **Tasks:** 3
- **Files created:** 1 (`strategy.py`)
- **Files modified:** 3 (`tests/test_strategy.py`, `04_value_detector.py`, `06_bot.py`)

## Accomplishments

- `strategy.py` created at repo root: `fjern_vigorish`, `beregn_value_og_ev`, `beregn_innsats`, `finn_bet_nokkel`, `bygg_bet_nokler`, `er_duplikat` — zero imports (verified via `grep -c -E '^(import|from) '` returning 0), no clock reads, no I/O, no type hints
- Arithmetic copied verbatim from the pre-extraction implementations (D-07/Pitfall 1) — `beregn_innsats`'s Kelly formula, clamp order, and `round(..., 2)` are byte-identical to the deleted `06_bot.py` function; `fjern_vigorish`/`beregn_value_og_ev` are byte-identical to the deleted inline block in `04_value_detector.py`
- `tests/test_strategy.py` extended from 2 to 16 tests: vig-removal (sum-to-one, favourite-ordering), value/EV (positive and negative edge), all five `beregn_innsats` branches (half-Kelly, null-edge, negative-edge, max-clamp, min-clamp), and four dedup cases including the legacy `kamp_dato`-fallback and the exact 2026-08-19 stale-row shape (same `kamp_dato`, different `dato` → collapses to one key)
- `04_value_detector.py` and `06_bot.py` rewired to import from `strategy.py`; the local `beregn_innsats` definition and the inline vig/value/EV block are both deleted, with zero surviving copies (grep-gated in Task 3's acceptance criteria)
- Deliberate-break check (Task 2): temporarily changed `kelly_fraksjon` multiplication to division in `strategy.py`, confirmed `pytest tests/test_strategy.py -k innsats` failed (`150.0 != 100.0`), reverted via file restore from a pre-edit backup, confirmed clean `git diff --stat strategy.py` (no diff vs. committed state) and 5 passed again
- Live-state proof (Task 3): `bets.json` exists with 30 bet records; `strategy.bygg_bet_nokler(bets)` produces 13 unique dedup keys — recorded as evidence the rewired dedup logic runs correctly against real persisted state

## Task Commits

Each task was committed atomically:

1. **Task 1: Create strategy.py with the extracted pure functions** — `2fa22e5` (refactor)
2. **Task 2: Test the money math and the dedup key (CORE-03)** — `e63246e` (test)
3. **Task 3: Rewire 04_value_detector.py and 06_bot.py onto strategy.py** — `cbba540` (refactor)

_No plan-metadata commit yet — this SUMMARY's own commit follows next._

## Files Created/Modified

- `strategy.py` — new flat module (99 lines); six pure functions covering vig-removal, value/EV, half-Kelly stake sizing, and bet-dedup-key construction/checking. Zero project imports (not `config`, not `pandas`).
- `tests/test_strategy.py` — extended with 14 new tests covering `strategy.py`; existing `test_config_values`/`test_config_har_ingen_hemmeligheter` from plan 02-02 untouched.
- `04_value_detector.py` — added `from strategy import fjern_vigorish, beregn_value_og_ev`; replaced the 19-line inline vig/value/EV block with 3 lines calling into `strategy.py`.
- `06_bot.py` — added `from strategy import beregn_innsats, finn_bet_nokkel, bygg_bet_nokler, er_duplikat`; deleted the local `beregn_innsats` definition (21 lines); replaced the dedup set comprehension and key-construction in `plasser_bets` with calls to `bygg_bet_nokler`/`finn_bet_nokkel`/`er_duplikat`; updated the `beregn_innsats` call site to pass `KELLY_FRAKSJON, MIN_INNSATS, MAX_INNSATS` explicitly.

## beregn_innsats signature (for plan 04/05/06 and Phase 5)

```python
strategy.beregn_innsats(saldo, modell_prob, odds, kelly_fraksjon, min_innsats, max_innsats)
```

Returns a `round(..., 2)` float stake, `0.0` when Kelly's edge is `<= 0`, clamped to `[min_innsats, max_innsats]` otherwise.

## Decisions Made

- Used `(0.50, 2.00)` instead of the plan's `(0.40, 2.50)` interfaces-block example for the "null edge → 0.0" test case, because `(0.40, 2.50)` does not reliably hit exactly `kelly == 0.0` in IEEE-754 double precision (see Deviations below). This is a test-input selection choice, not an arithmetic change to `strategy.py` itself.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Plan's literal acceptance-criteria value was incorrect, not the code] `beregn_innsats(1000.0, 0.40, 2.50, 0.5, 20.0, 150.0)` returns `20.0`, not `0.0`**
- **Found during:** Task 1 acceptance-criteria verification
- **Issue:** The plan's Task 1 acceptance criteria and Task 2's `test_beregn_innsats_null_edge_gir_null` both assert this input pair returns `0.0`. In IEEE-754 double precision, `1.5 * 0.4` evaluates to `0.6000000000000001`, not exactly `0.6`, so `kelly = (b*p - q)/b` evaluates to `7.4e-17` (a tiny *positive* number) rather than exactly `0.0`. The `if kelly <= 0` branch does not fire, so the function proceeds to clamp a near-zero stake up to `min_innsats = 20.0`.
- **Root cause:** This is not a bug introduced by extraction — the exact same formula, with the exact same floats, produces the exact same `20.0` result whether run inside the deleted `06_bot.py::beregn_innsats` or the new `strategy.py::beregn_innsats` (verified: Python float arithmetic is deterministic regardless of which module/variable names host it). The plan's interfaces-block example was written without accounting for this pre-existing floating-point quirk.
- **Fix:** `strategy.py`'s arithmetic was left completely unchanged (per D-07/Pitfall 1 — extraction must not alter arithmetic even to "fix" a surprising edge case). Instead, `test_beregn_innsats_null_edge_gir_null` uses the float-safe input pair `(1000.0, 0.50, 2.00, 0.5, 20.0, 150.0)`, where `1.0 * 0.5 - 0.5 == 0.0` exactly, so the test genuinely isolates the `kelly <= 0` branch it's named for.
- **Files modified:** `tests/test_strategy.py` (test input values only); `strategy.py` unaffected.
- **Verification:** `./venv/bin/python -c "import strategy; print(strategy.beregn_innsats(1000.0, 0.40, 2.50, 0.5, 20.0, 150.0))"` prints `20.0` (documented, not a failure); `./venv/bin/python -c "import strategy; print(strategy.beregn_innsats(1000.0, 0.50, 2.00, 0.5, 20.0, 150.0))"` prints `0.0`; full suite (`pytest -v`) is 17/17 green.
- **Committed in:** `2fa22e5` (Task 1), `e63246e` (Task 2)

---

**Total deviations:** 1 auto-fixed (a plan acceptance-criteria example that didn't account for floating-point noise; the underlying money-math arithmetic is unchanged from the pre-extraction implementation)
**Impact on plan:** None on behavior — `beregn_innsats`'s output for every input is byte-identical to the pre-extraction function. Only the specific test-input pair used to exercise the `kelly <= 0` branch changed.

## Issues Encountered

None beyond the deviation above.

## Deliberate-Break Check (Task 2 acceptance criterion)

Per the plan's explicit instruction, backed up `strategy.py`, changed the `kelly_fraksjon` multiplication to a division (`saldo * kelly / kelly_fraksjon`) and re-ran the innsats tests:
- **Tampered run:** `test_beregn_innsats_halv_kelly` FAILED (`assert 150.0 == 100.0` — the max-clamp fired because dividing by 0.5 doubled the raw stake instead of halving it) — 1 failed, 4 passed
- **Reverted** by restoring `strategy.py` from the pre-edit backup (not a blanket `git checkout`, a direct file copy back)
- **Post-revert run:** `git diff --stat strategy.py` showed no diff against the committed version; 5 passed

Confirms the stake tests actually fire on a real arithmetic regression, as the plan requires.

## Live-State Proof (Task 3)

`bets.json` exists in the working tree (not created by this plan). Running the rewired dedup logic against it:

```
$ ./venv/bin/python -c "import json, strategy; from config import KELLY_FRAKSJON, MIN_INNSATS, MAX_INNSATS; bets=json.load(open('bets.json')); print(len(strategy.bygg_bet_nokler(bets)), 'unike nokler av', len(bets), 'bets')"
13 unike nokler av 30 bets
```

13 unique dedup keys across 30 persisted bet records — recorded as evidence, no interpretation of "is this correct" attempted (that's outside this plan's scope; the number is simply captured per the plan's Task 3 instruction).

## User Setup Required

None — no external service configuration required.

## Known Stubs

None — this plan wired real logic through, no placeholder data paths introduced.

## Threat Flags

None — this plan's threat model items (T-02-05, T-02-06, T-02-07, T-02-08, T-02-01) are all extraction-safety mitigations; all were satisfied:
- T-02-06 (call-site parameter order): single call site updated explicitly by name order (`KELLY_FRAKSJON, MIN_INNSATS, MAX_INNSATS`), grep-verified, both clamp tests pin exact values.
- T-02-07 (dedup legacy-fallback regression): `test_bygg_bet_nokler_faller_tilbake_til_dato` and `test_dedup_fanger_samme_kamp_paa_ulik_kjoredato` model the exact historical bug shape; both pass.
- T-02-08 (division-by-zero, accept disposition): no validation added inside `strategy.py`, matching the pre-existing behavior and the plan's accepted disposition.
- T-02-05 (silent arithmetic drift): arithmetic copied verbatim; grep gates confirm the old inline copies are gone.
- T-02-01 (uninspected WIP swept into commits): explicit-pathspec staging only used throughout; `05_skadefilter.py` and `03_tren_modell.py` were never staged by this plan.

## Next Phase Readiness

- `pytest -v` collects and passes 17 tests (3 from plan 02-02's harness/config work + 14 new from this plan)
- `strategy.py` is importable with zero project dependencies — ready for Phase 5's backtest to import identically
- `04_value_detector.py` and `06_bot.py` contain zero surviving copies of vig/value/EV/Kelly/dedup logic — single source of truth achieved for CORE-01
- `03_tren_modell.py` remains untouched (still shows ` M` from pre-existing WIP), per D-09
- `05_skadefilter.py` remains unstaged/untouched by this plan (its own team-lookup migration is plan 04's job per `02-01-SUMMARY.md`)

---
*Phase: 02-shared-core-extraction-test-foundation*
*Completed: 2026-08-21*

## Self-Check: PASSED

- FOUND: `strategy.py`
- FOUND: commits `2fa22e5`, `e63246e`, `cbba540` in `git log --oneline --all`
