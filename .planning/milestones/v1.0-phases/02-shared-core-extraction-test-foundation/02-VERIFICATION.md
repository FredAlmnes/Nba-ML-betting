---
phase: 02-shared-core-extraction-test-foundation
verified: 2026-08-21T14:00:00Z
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 2: Shared Core Extraction & Test Foundation Verification Report

**Phase Goal:** Feature engineering, team-name resolution, and value/stake strategy logic exist in exactly one place, imported identically by the live path and the (future) backtest path, with automated tests protecting the money-math functions.
**Verified:** 2026-08-21
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Phase 2 Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `features.py`, `strategy.py`, `teams.py` exist as shared modules; no duplicate reimplementation remains in `02_feature_engineering.py`, `04_value_detector.py`, `05_skadefilter.py`, `06_bot.py` | ✓ VERIFIED | All three modules exist, are substantive (99–144 lines), byte-compile, and are imported by name in the four pipeline files (grep-verified below). Independent greps for `get_teams()`, the 9-stat literal list, `beregn_innsats`/`beregn_lag_form`/`finn_lag`/`fjern_vigorish` definitions confirm each exists exactly once in its shared module, with zero duplicates in the pipeline files. One pre-existing, unrelated call to `nba_api`'s `get_teams()` remains in `01_hent_data.py` (enumerates all 30 teams for historical fetch, not a name resolver) — correctly out of scope of D-03's four targeted duplicates and explicitly documented in `02-04-SUMMARY.md`/`02-06-SUMMARY.md`. |
| 2 | `MIN_VALUE_TERSKEL`, `MAX_ODDS`, Kelly fraction live in a single config module imported by the live path (no second place to set them) | ✓ VERIFIED | `config.py` holds all 7 strategy constants at their pre-phase values (0.05/1.50/4.00/0.5/150.0/20.0/1000.0), confirmed both by direct file read and by the passing `test_config_values` tripwire. `04_value_detector.py` and `06_bot.py` both `from config import ...`; grep confirms zero literal re-assignments of any of the 7 constants outside `config.py`. |
| 3 | A `pytest` suite covers `beregn_innsats` and the bet-dedup logic, and passes | ✓ VERIFIED | Ran `./venv/bin/python -m pytest -v` myself: **37/37 passed**. Covers all 5 `beregn_innsats` branches (half-Kelly, null-edge, negative-edge, max-clamp, min-clamp) and 4 dedup cases including the legacy `kamp_dato`-fallback and the exact 2026-08-19 stale-row bug shape. Deliberate-break checks recorded in `02-02-SUMMARY.md`/`02-03-SUMMARY.md` confirm the tests are load-bearing, not vacuous. |
| 4 | A parity/leakage regression test proves the live path and backtest path produce an identical decision for the same historical date/game | ✓ VERIFIED (scoped per D-12) | The backtest path does not exist until Phase 5, so this cannot literally be a live-vs-backtest integration test yet. `.planning/phases/02-shared-core-extraction-test-foundation/02-CONTEXT.md` D-12 explicitly pre-scopes this (documented during context-gathering, not invented post-hoc) to a determinism/leakage-regression test on the shared core. `tests/test_parity.py` (7 tests, all passing) proves `features.py`/`strategy.py` are referentially transparent, input-order-independent, and leakage-safe at the strict `as_of` boundary, plus a full simulated bet-decision chain (`simuler_bet_beslutning`) is proven identical across two independent invocations for 3 input sets. The module docstring states the D-12 scoping and names exactly what Phase 5 must add. This is a legitimate, pre-declared scope reduction, not a shortcut. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `strategy.py` | Pure value/EV/vig/Kelly/dedup functions, zero project imports | ✓ VERIFIED | 100 lines, 6 functions (`fjern_vigorish`, `beregn_value_og_ev`, `beregn_innsats`, `finn_bet_nokkel`, `bygg_bet_nokler`, `er_duplikat`), 0 imports (`grep -c -E '^(import|from) '` = 0), no I/O, no clock reads, no type hints. |
| `teams.py` | Single canonical team resolver | ✓ VERIFIED | 62 lines, `bygg_lag_oppslag`/`finn_lag`/`finn_lag_id`, `LAG_OPPSLAG` built once at import (90 keys), returns `None` for unknown names (tested). |
| `features.py` | Shared as_of-aware rolling-window computation + single stat list | ✓ VERIFIED | 144 lines, `STATS_KOLONNER` (9 stats), `DIFF_STATS` (7-stat batch subset, divergence documented in-comment), `beregn_lag_form(df_raw, vindu, as_of=None)` with strict `<` filter, `df` → `df_raw` closure bug fixed (verified: 3 `df_raw[` references, 0 bare `df[` references), `snitt_fra_kamplogg`, `bygg_feature_rad`. |
| `config.py` | Single source of truth for strategy constants | ✓ VERIFIED | 21 lines, all 7 constants at pre-phase values, Odds API key deliberately absent (0 hits for `ODDS_API`/`API_NØKKEL`). |
| `tests/conftest.py` + `tests/test_*.py` | pytest harness and money-math/dedup/team/feature/parity tests | ✓ VERIFIED | `pytest.ini` (`pythonpath = .`, `testpaths = tests`), `requirements-dev.txt` (pytest only, not leaked into `requirements.txt`). 37 tests across 5 test files, all passing (independently re-run). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `04_value_detector.py` | `strategy.py` | `from strategy import fjern_vigorish, beregn_value_og_ev` | ✓ WIRED | Import present; inline vig/value/EV arithmetic (`impl_sann_hjemme = 1 / ...`) confirmed absent via grep. |
| `06_bot.py` | `strategy.py` | `from strategy import beregn_innsats, finn_bet_nokkel, bygg_bet_nokler, er_duplikat` | ✓ WIRED | Import present; local `def beregn_innsats` confirmed absent; dedup call site uses `bygg_bet_nokler(bets)` / `finn_bet_nokkel(...)` / `er_duplikat(...)`. |
| `04_value_detector.py`, `05_skadefilter.py` | `teams.py` | `from teams import finn_lag_id` | ✓ WIRED | Both files import and call `finn_lag_id(...)`; no local `lag_oppslag` dict remains in either. |
| `06_bot.py`, `debug_kamp.py` | `teams.py` | `from teams import finn_lag` | ✓ WIRED | Both import and call `finn_lag(...)`; `06_bot.py`'s former `def finn_lag` closure confirmed absent. |
| `02_feature_engineering.py`, `04_value_detector.py` | `features.py` | `from features import ...` | ✓ WIRED | Both import; `02`'s local `beregn_lag_form` definition confirmed absent; `04`'s inline feature-row loop and hardcoded stat dict confirmed absent. Re-running `02_feature_engineering.py` reproduces a byte-identical `nba_features.csv` (independently verified — see Behavioral Spot-Checks). |
| `04_value_detector.py`, `06_bot.py` | `config.py` | `from config import ...` | ✓ WIRED | Both import; all 7 constant literals confirmed absent from both files outside `config.py`. |

### Data-Flow Trace (Level 4)

Not applicable — this phase produces no UI/dashboard-rendering artifacts; it is a pure library-extraction phase. `strategy.py`/`teams.py`/`features.py`/`config.py` are called synchronously by `04_value_detector.py`/`06_bot.py`/`05_skadefilter.py` with real arguments at each call site (verified above), not hardcoded/empty stand-ins.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes | `./venv/bin/python -m pytest -v` | `37 passed in 0.21s` | ✓ PASS |
| All pipeline/shared files byte-compile | `./venv/bin/python -m py_compile config.py strategy.py teams.py features.py 02_feature_engineering.py 04_value_detector.py 05_skadefilter.py 06_bot.py debug_kamp.py` | exit 0 | ✓ PASS |
| Feature engineering output is stable/reproducible | Copied current `nba_features.csv`, re-ran `02_feature_engineering.py`, `cmp`'d the two | `IDENTICAL` (byte-for-byte, 987,655 bytes, 3,638 games) | ✓ PASS |
| No duplicate `get_teams()` resolver logic | `grep -rn "get_teams()" --include="*.py" .` (excl. venv/tests) | 1 real call in `teams.py` + 1 pre-existing, documented, out-of-scope call in `01_hent_data.py` (roster enumeration, not name resolution) | ✓ PASS (matches documented exception) |
| Strategy constants single-sourced | `grep -rn -E "^(MIN_VALUE_TERSKEL|MIN_ODDS|MAX_ODDS|KELLY_FRAKSJON|MAX_INNSATS|MIN_INNSATS|STARTKAPITAL) *="` | 7 hits, all in `config.py` | ✓ PASS |
| No debt markers (TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER) in phase-touched files | grep across all 15 phase-modified/created files | 0 hits | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| CORE-01 | 02-03, 02-04, 02-05 | Feature/team/strategy logic extracted into shared modules, imported identically, no duplicate implementations | ✓ SATISFIED | `strategy.py`, `teams.py`, `features.py` created and wired; de-duplication greps confirm zero surviving duplicates (with documented `01_hent_data.py` exception, correctly out of D-03's scope). |
| CORE-02 | 02-02 | Strategy parameters in a single source-of-truth config imported by live path | ✓ SATISFIED | `config.py` created; both `04_value_detector.py` and `06_bot.py` import from it; regression test locks all 7 values. |
| CORE-03 | 02-02, 02-03 | Unit tests cover `beregn_innsats` and bet-dedup logic | ✓ SATISFIED | 5 `beregn_innsats` tests + 4 dedup tests in `tests/test_strategy.py`, all passing; deliberate-break checks confirm they are load-bearing. |
| CORE-04 | 02-06 | Parity/leakage regression test confirms identical decisions across live/backtest paths | ✓ SATISFIED (scoped per documented D-12) | `tests/test_parity.py` proves determinism/order-independence/leakage-safety of the shared core; scoping rationale and Phase 5 follow-up instruction recorded in the test file's own module docstring. |

REQUIREMENTS.md traceability table independently cross-checked: CORE-01 through CORE-04 all marked "Complete" for Phase 2, matching the evidence above. No orphaned requirements found for this phase (only CORE-01..04 map to Phase 2 in REQUIREMENTS.md, and all four appear in plan frontmatter `requirements:` fields).

### Anti-Patterns Found

None blocking. `02-REVIEW.md` (code review, run separately) flagged 3 Critical and 6 Warning findings, but **all of them are located in pre-existing, developer-authored WIP code inside `06_bot.py`/`05_skadefilter.py` that predates this phase** (bankroll-history double-checkpoint bug, dashboard XSS via unescaped `innerHTML`, wrong-game result attribution in `hent_kampresultat`, bare `exit()` in `05_skadefilter.py`, duplicated season-calculation helper, hardcoded `python3.10` venv path) — none of them are in the shared-core files this phase created (`strategy.py`/`teams.py`/`features.py`/`config.py`), and none of them relate to CORE-01 through CORE-04. The developer explicitly chose "include" in the Plan 01 pre-flight gate, accepting that this WIP would ride along in the extraction commits; `02-REVIEW.md` itself states "The shared-core extraction itself ... is clean, well-documented, and backed by genuinely useful ... tests. That part of the phase is solid." One finding (WR-03: `strategy.py`'s `fjern_vigorish`/`beregn_innsats` have no input-validation guard against `odds <= 1.0`) does touch the newly-created shared core, but is an intentional, phase-documented deferral (threat `T-02-08`, disposition "accept" — adding validation would be a behavior change forbidden by this phase's extraction-only mandate) rather than an unaddressed gap. None of these findings block Phase 2's own goal; they are candidates for a future cleanup plan, most naturally Phase 4 (which already touches `06_bot.py` for the ODDS-02 subprocess→import refactor) — flagged here for developer awareness, not as a Phase 2 gap.

### Human Verification Required

None. This phase's deliverables (shared Python modules + pytest suite) are fully mechanically verifiable: every claim was independently re-checked against the actual codebase (file contents, grep-based de-duplication audits, byte-compile, live test-suite execution, and a from-scratch re-run of the feature-engineering pipeline confirming byte-identical output). No UI, no external service integration, and no real-time behavior was introduced by this phase.

### Gaps Summary

No gaps found. All four ROADMAP Phase 2 success criteria are independently verified against the actual codebase (not just SUMMARY claims): the shared core (`strategy.py`, `teams.py`, `features.py`, `config.py`) is real, substantive, wired into every pipeline file that used to carry a duplicate, and protected by a genuinely load-bearing 37-test pytest suite (re-run and confirmed green in this verification). The one requirement (CORE-04) that could not be satisfied to its literal wording was pre-scoped down via an explicit, documented developer/planning decision (D-12) because its full satisfaction depends on the Phase 5 backtest engine that does not exist yet — this is a legitimate, declared scope reduction with a concrete follow-up instruction left in the test file itself, not an unacknowledged shortfall. Code-review findings exist but are confined to pre-existing WIP code outside this phase's actual deliverables and do not block phase-goal achievement.

---

_Verified: 2026-08-21_
_Verifier: Claude (gsd-verifier)_
