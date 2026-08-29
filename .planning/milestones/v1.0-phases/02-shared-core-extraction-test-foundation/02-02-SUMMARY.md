---
phase: 02-shared-core-extraction-test-foundation
plan: 02
subsystem: testing
tags: [pytest, config, kelly, value-betting]

# Dependency graph
requires:
  - phase: 02-shared-core-extraction-test-foundation (plan 01)
    provides: staging-disposition-decision (include pre-existing WIP), debug_kamp.py disposition
provides:
  - repo's first automated test harness (pytest.ini, requirements-dev.txt, tests/)
  - shared tests/conftest.py fixtures (kamper_df, fremtidige_kamper_df, as_of_dato) for plan 06
  - config.py as single source of truth for the 7 strategy constants
  - 04_value_detector.py and 06_bot.py importing constants from config.py instead of local literals
  - tests/test_strategy.py with a regression tripwire on config values (CORE-02)
affects: [02-03-PLAN.md, 02-06-PLAN.md]

# Tech tracking
tech-stack:
  added: [pytest 9.1.1]
  patterns: ["pytest.ini pythonpath = . for flat-module repo-root imports", "config.py UPPER_SNAKE_CASE single-source-of-truth constants"]

key-files:
  created: [requirements-dev.txt, pytest.ini, tests/conftest.py, tests/test_oppsett.py, config.py, tests/test_strategy.py]
  modified: [04_value_detector.py, 06_bot.py]

key-decisions:
  - "config.py constants reformatted to single-space '= ' alignment (rather than the aligned-padding style copied verbatim from 06_bot.py's interfaces block) so the plan's own acceptance-criteria grep pattern matches all 7 constants"
  - "config.py docstring avoids the literal string 'ODDS_API_NOKKEL' when explaining that secrets stay out of the file, so the file itself doesn't trip its own no-secrets grep check"

patterns-established:
  - "Pattern: strategy/config constants live only in config.py; call sites import by name, never redeclare"

requirements-completed: [CORE-02, CORE-03]

# Metrics
duration: 12min
completed: 2026-08-21
---

# Phase 2 Plan 02: Test Harness and Config Extraction Summary

Installed the repo's first-ever pytest harness (9.1.1) with shared deterministic fixtures, then collapsed the seven strategy constants (`MIN_VALUE_TERSKEL`, `MIN_ODDS`, `MAX_ODDS`, `KELLY_FRAKSJON`, `MAX_INNSATS`, `MIN_INNSATS`, `STARTKAPITAL`) that previously lived as duplicate literals in `04_value_detector.py` and `06_bot.py` into a single `config.py`, locked by a regression test.

## Performance

- **Duration:** 12 min
- **Tasks:** 3
- **Files created:** 6 (`requirements-dev.txt`, `pytest.ini`, `tests/conftest.py`, `tests/test_oppsett.py`, `config.py`, `tests/test_strategy.py`)
- **Files modified:** 2 (`04_value_detector.py`, `06_bot.py`)

## Accomplishments
- pytest 9.1.1 installed and configured (`pytest.ini`: `pythonpath = .`, `testpaths = tests`) — `tests/` can `import config`/`modell_utils` from repo root with zero `sys.path` hacks
- `tests/conftest.py` gives plan 06's feature/parity tests deterministic `kamper_df` (10 games), `fremtidige_kamper_df` (2 future/boundary games), and `as_of_dato` fixtures — no `random`/`datetime.now()`
- `config.py` is now the single place all 7 strategy constants are assigned a literal value; both `04_value_detector.py` and `06_bot.py` import from it
- `tests/test_strategy.py::test_config_values` is a deliberate tripwire — manually verified it fails when `MAX_ODDS` is tampered with, and passes again once reverted

## Task Commits

Each task was committed atomically:

1. **Task 1: Install pytest and create the test harness** - `7c09904` (test)
2. **Task 2: Create config.py and rewire 04_value_detector.py/06_bot.py** - `7efd00b` (refactor)
3. **Task 3: Lock the config values behind a regression test** - `378d7f7` (test)

_No plan-metadata commit yet — this SUMMARY's own commit follows next._

## Files Created/Modified
- `requirements-dev.txt` - dev-only dependency file, `pytest>=9.1.1`, kept separate from runtime `requirements.txt`
- `pytest.ini` - `[pytest]` section with `pythonpath = .` and `testpaths = tests`
- `tests/conftest.py` - `LAG_IDER`, `kamper_df`, `fremtidige_kamper_df`, `as_of_dato` fixtures (deterministic synthetic raw-game rows matching the 02_feature_engineering.py schema)
- `tests/test_oppsett.py` - `test_repo_rot_er_importerbar` proves `pythonpath = .` works before real tests depend on it
- `config.py` - new flat module; single source of truth for the 7 strategy constants, with a comment stating the Odds API key deliberately stays out of it
- `04_value_detector.py` - deleted 3 literal constant lines, added `from config import MIN_VALUE_TERSKEL, MIN_ODDS, MAX_ODDS`
- `06_bot.py` - deleted 4 literal constant lines, added `from config import KELLY_FRAKSJON, MAX_INNSATS, MIN_INNSATS, STARTKAPITAL`; this commit also carries the developer's pre-existing ~1009-line uncommitted WIP on this file, per the `include` decision recorded in `02-01-SUMMARY.md`
- `tests/test_strategy.py` - `test_config_values` (regression tripwire, D-07) and `test_config_har_ingen_hemmeligheter` (no-secrets check)

## Decisions Made
- Reformatted the second group of `config.py` constants (`KELLY_FRAKSJON`/`MAX_INNSATS`/`MIN_INNSATS`/`STARTKAPITAL`) from `06_bot.py`'s aligned-padding style to plain single-space `= ` — the plan's own acceptance-criteria grep (`'KELLY_FRAKSJON = \|...'`) requires exact single-space matching across all 7 constants; this is a formatting-only change, values are byte-identical to the original literals.
- Reworded `config.py`'s docstring to avoid literally containing the string `ODDS_API_NOKKEL` when explaining that the Odds API key doesn't live in the file — the initial docstring wording accidentally tripped the plan's own `grep -c 'ODDS_API_NOKKEL\|API_NØKKEL' config.py` no-secrets check by mentioning the env var name in prose. Reworded to describe the same fact without the literal string; `test_config_har_ingen_hemmeligheter` now also passes cleanly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] config.py constant formatting didn't match acceptance-criteria grep pattern**
- **Found during:** Task 2, acceptance-criteria verification
- **Issue:** The plan's interfaces block copied `06_bot.py`'s aligned-padding constant style (e.g. `KELLY_FRAKSJON    = 0.5`) verbatim, but the plan's own acceptance criterion greps for `'KELLY_FRAKSJON = '` (single space) and expects a count of 7 across all constants combined with the other three from `04_value_detector.py` (which already used single-space style). Aligned padding on the second group caused the combined grep to undercount (3 instead of 7).
- **Fix:** Reformatted all 4 constants copied from `06_bot.py` to single-space `= ` alignment in `config.py`. Values, comments, and semantics unchanged.
- **Files modified:** `config.py`
- **Verification:** `grep -c 'MIN_VALUE_TERSKEL = \|MIN_ODDS = \|MAX_ODDS = \|KELLY_FRAKSJON = \|MAX_INNSATS = \|MIN_INNSATS = \|STARTKAPITAL = ' config.py` returns 7
- **Committed in:** `7efd00b` (Task 2 commit)

**2. [Rule 1 - Bug] config.py docstring self-tripped the no-secrets acceptance check**
- **Found during:** Task 2, acceptance-criteria verification
- **Issue:** The docstring explaining that the Odds API key stays out of `config.py` referenced the env var name `ODDS_API_NOKKEL` in prose, which caused `grep -c 'ODDS_API_NOKKEL\|API_NØKKEL' config.py` to return 1 instead of the required 0 — a false positive on the file's own "no secret moved here" documentation.
- **Fix:** Reworded the docstring to explain the same fact ("Odds-API-nøkkelen ligger IKKE her med vilje... forblir en miljøvariabel-innlesning i 04_value_detector.py") without using the literal env var name string.
- **Files modified:** `config.py`
- **Verification:** `grep -c 'ODDS_API_NOKKEL\|API_NØKKEL' config.py` returns 0; `tests/test_strategy.py::test_config_har_ingen_hemmeligheter` passes
- **Committed in:** `7efd00b` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — bugs in matching the plan's own literal acceptance-criteria strings, not behavior/value changes)
**Impact on plan:** Cosmetic formatting/wording only; all 7 constant values remain byte-identical to their pre-phase literals (verified via `test_config_values`). No scope creep.

## Issues Encountered
None beyond the two auto-fixes above.

## Deliberate-Break Check (Task 3 acceptance criterion)

Per the plan's explicit instruction, manually tampered `config.py`'s `MAX_ODDS` from `4.00` to `5.00` and re-ran `tests/test_strategy.py`:
- **Tampered run:** `test_config_values` FAILED (`assert 5.0 == 4.0`), `test_config_har_ingen_hemmeligheter` still passed — 1 failed, 1 passed
- **Reverted via** `git checkout -- config.py` (sanctioned single-file revert, not a blanket reset)
- **Post-revert run:** both tests PASSED — 2 passed

Confirms the tripwire actually fires on a silent config change, as CORE-02/D-07 require.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `pytest -v` collects and passes 3 tests (`test_repo_rot_er_importerbar`, `test_config_values`, `test_config_har_ingen_hemmeligheter`)
- `config.py` is the sole source of truth for all 7 strategy constants; `04_value_detector.py`/`06_bot.py` both import from it
- `tests/conftest.py`'s `kamper_df`/`fremtidige_kamper_df`/`as_of_dato` fixtures are ready for plan 06's `test_features.py`/`test_parity.py` to consume without re-deriving fixture construction
- `03_tren_modell.py` remains untouched (still shows ` M` from pre-existing WIP), per D-09
- Plan 03 (`strategy.py` extraction) can now import `config.py`'s constants at call sites for `beregn_innsats`/value-EV functions

---
*Phase: 02-shared-core-extraction-test-foundation*
*Completed: 2026-08-21*

## Self-Check: PASSED

- FOUND: `requirements-dev.txt`, `pytest.ini`, `tests/conftest.py`, `tests/test_oppsett.py`, `config.py`, `tests/test_strategy.py`, this SUMMARY.md
- FOUND: commits `7c09904`, `7efd00b`, `378d7f7` in `git log --oneline --all`
