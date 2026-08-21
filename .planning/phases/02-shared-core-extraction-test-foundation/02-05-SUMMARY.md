---
phase: 02-shared-core-extraction-test-foundation
plan: 05
subsystem: feature-engineering
tags: [features, train-serve-skew, pandas, pytest, refactor]

# Dependency graph
requires:
  - phase: 02-shared-core-extraction-test-foundation (plan 04)
    provides: teams.py canonical resolver pattern (module docstring/style precedent), pytest harness, config.py pattern
provides:
  - features.py — single implementation of the rolling-window team-form computation (beregn_lag_form), the nine-stat STATS_KOLONNER list, the seven-stat DIFF_STATS subset, snitt_fra_kamplogg, and bygg_feature_rad
  - tests/test_features.py — 7 tests covering the RULL_ column contract, shift(1) NaN behaviour, the strict-< as_of boundary, and the 27-key live feature-row naming contract
  - as_of-aware beregn_lag_form ready for Phase 5's walk-forward backtest to call unchanged
affects: [02-06-PLAN.md, Phase 4 (ODDS-02 subprocess->import refactor), Phase 5 backtest]

tech-stack:
  added: []
  patterns: ["features.py: single STATS_KOLONNER/DIFF_STATS constants, as_of pre-filter (strict <) as defense-in-depth ahead of the already-leakage-safe shift(1).rolling(...) computation"]

key-files:
  created: [features.py, tests/test_features.py]
  modified: [02_feature_engineering.py, 04_value_detector.py]

key-decisions:
  - "df -> df_raw closure-bug fix (known_defect): beregn_lag_form's body previously read the module-level global df three times instead of its own df_raw parameter. Fixed during extraction; proven output-preserving by byte-identical cmp of a pre-edit baseline nba_features.csv against the post-edit regeneration (987655 bytes, 3638 games, IDENTISK)."
  - "Batch-vs-live DIFF_ column divergence recorded, not normalized: 02_feature_engineering.py builds DIFF_ for 7 stats (DIFF_STATS), 04_value_detector.py's bygg_feature_rad builds DIFF_ for all 9 (STATS_KOLONNER). Pre-existing, harmless today because 04_value_detector.py filters with [feature_kolonner] before predict. Documented in a features.py comment for Phase 5 to resolve if backtest parity requires it."
  - "03_tren_modell.py deliberately left untouched and never staged in any of this plan's 3 commits, per D-09."

patterns-established:
  - "Pattern: as_of pre-filter on the raw input DataFrame (strict < GAME_DATE_HJEMME), applied before the existing shift(1).rolling(...) computation — defense-in-depth, not a rolling-window redesign. Ready for Phase 5's walk-forward backtest to call beregn_lag_form unchanged."

requirements-completed: [CORE-01]

# Metrics
duration: 8min
completed: 2026-08-21
---

# Phase 2 Plan 05: Feature Engineering Unification Summary

Single-sourced the rolling-window team-form computation into `features.py` (fixing a latent parameter-shadowing bug along the way), proved the fix output-preserving via a byte-identical `cmp` of the regenerated `nba_features.csv` against a pre-edit baseline, and rewired both `02_feature_engineering.py` (batch) and `04_value_detector.py` (live) onto the shared module.

## Performance

- **Duration:** ~8 min
- **Tasks:** 3
- **Files created:** 2 (`features.py`, `tests/test_features.py`)
- **Files modified:** 2 (`02_feature_engineering.py`, `04_value_detector.py`)

## Accomplishments

- `features.py` created at repo root: `STATS_KOLONNER` (9 stats), `RULLENDE_VINDU` (10), `DIFF_STATS` (7-stat batch subset with a comment documenting the pre-existing batch-vs-live divergence), `beregn_lag_form(df_raw, vindu, as_of=None)`, `snitt_fra_kamplogg(df_logg)`, `bygg_feature_rad(hjemme_stats, borte_stats)`.
- Fixed the known `df` → `df_raw` closure bug during extraction (three occurrences: lines building `hjemme_df`, `borte_df`, and `borte_df["VANT"]`) — the function now genuinely reads its own parameter instead of a module-level global, making it callable by `04_value_detector.py` and, later, Phase 5's backtest.
- Added a strict-`<` `as_of` pre-filter as defense-in-depth ahead of the already-leakage-safe `shift(1).rolling(...)` computation, so a future walk-forward backtest can call the function unchanged.
- `tests/test_features.py` created with 7 tests: row-count contract, `RULL_` column contract, `shift(1)` NaN behaviour on a team's first game, the strict-`<` `as_of` boundary, `as_of=None` opt-out default, `snitt_fra_kamplogg`'s stat dict, and the 27-key `bygg_feature_rad` naming contract.
- `02_feature_engineering.py` and `04_value_detector.py` both rewired to import from `features.py`; zero surviving copies of the stat list, the rolling-window logic, or the feature-row naming.
- Golden-file proof: regenerated `nba_features.csv` is byte-identical (`cmp` exit 0, "IDENTISK") to a baseline captured from the pre-edit code — 987,655 bytes, 3,638 games, "Fjernet 47 rader" / "Gjenstående kamper: 3638" identical in both runs.
- Deliberate-break check (Task 2): temporarily changed the `as_of` filter from `<` to `<=` — `test_as_of_filtrerer_bort_kampen_selv` **FAILED** as expected (the boundary-date game leaked into its own result set: `AssertionError: assert '0022400010' not in {'0022400010'}`). Reverted to `<` — test **PASSED** again. Confirms the boundary assertion is load-bearing, not vacuous.
- Full suite green at 30/30 (23 pre-existing + 7 new).

## Task Commits

Each task was committed atomically:

1. **Task 1: Create features.py with the as_of-aware rolling-window computation and the single stat list** — `d01bf36` (refactor)
2. **Task 2: Test the feature contract against the synthetic fixture** — `30e6e95` (test)
3. **Task 3: Rewire both paths onto features.py and prove the output is byte-identical** — `1121bbc` (refactor)

## Files Created/Modified

- `features.py` — new flat module (143 lines). `STATS_KOLONNER`/`RULLENDE_VINDU`/`DIFF_STATS` single-sourced constants; `beregn_lag_form` (the fixed, `as_of`-aware rolling-window function); `snitt_fra_kamplogg`/`bygg_feature_rad` (the two live-path helpers extracted from `04_value_detector.py`).
- `tests/test_features.py` — 7 tests, consumes `kamper_df`/`fremtidige_kamper_df`/`as_of_dato` fixtures from `tests/conftest.py` (plan 02-02), builds one inline game-log-shaped fixture for `snitt_fra_kamplogg` per plan instruction.
- `02_feature_engineering.py` — deleted the local `beregn_lag_form` definition (62 lines removed); added `from features import beregn_lag_form, DIFF_STATS`; DIFF loop now iterates `DIFF_STATS` instead of a hardcoded 7-stat literal.
- `04_value_detector.py` — `hent_siste_lagstats` now returns `snitt_fra_kamplogg(df)` instead of a hardcoded 9-key dict; the inline feature-row loop replaced with `bygg_feature_rad(hjemme_stats, borte_stats)`; added `from features import STATS_KOLONNER, snitt_fra_kamplogg, bygg_feature_rad`.

## Golden-File Verification

```
$ ./venv/bin/python 02_feature_engineering.py   # BEFORE any edit
Fjernet 47 rader pga. manglende historikk
Gjenstående kamper til modellering: 3638
$ cp nba_features.csv "${TMPDIR}/nba_features_baseline.csv"   # 987655 bytes

# ... edits applied (Task 1, Task 3) ...

$ ./venv/bin/python 02_feature_engineering.py   # AFTER extraction + df_raw fix
Fjernet 47 rader pga. manglende historikk
Gjenstående kamper til modellering: 3638
$ cmp nba_features.csv "${TMPDIR}/nba_features_baseline.csv" && echo IDENTISK
IDENTISK
```

## Repo-wide stat-list grep

```
$ grep -rn '"PTS", *"FG_PCT", *"FT_PCT"' --include="*.py" . | grep -v "^./venv/"
features.py:18:STATS_KOLONNER = ["PTS", "FG_PCT", "FT_PCT", "FG3_PCT", "REB", "AST", "TOV", "PLUS_MINUS", "VANT"]
```

Exactly one hit, in `features.py` — no surviving hardcoded copies.

## Deliberate-Break Check (Task 2, Pitfall 3)

```
# Changed features.py's as_of filter from < to <= temporarily:
$ ./venv/bin/python -m pytest tests/test_features.py::test_as_of_filtrerer_bort_kampen_selv -v
FAILED — AssertionError: assert '0022400010' not in {'0022400010'}
# Reverted to <:
$ ./venv/bin/python -m pytest tests/test_features.py::test_as_of_filtrerer_bort_kampen_selv -v
PASSED
```

## Decisions Made

- The `df` → `df_raw` fix from `<known_defect>` was applied exactly as scoped: three occurrences changed, nothing else in the function's logic touched. Proven output-preserving by the golden-file `cmp`, not just asserted.
- The batch-vs-live `DIFF_` column count divergence (7 stats vs. 9 stats) was deliberately NOT normalized — doing so would change the trained model's feature schema, which D-05/D-07 forbid this phase from touching. Recorded as a `features.py` comment and here for Phase 5.
- `STATS_KOLONNER` was imported into `04_value_detector.py` per the plan's explicit interface spec even though it is not directly referenced in that file's own code (it is consumed transitively via `snitt_fra_kamplogg`/`bygg_feature_rad`) — kept per the plan's literal `<key_links>` requirement so the import surface documents the shared dependency explicitly.

## Findings for Phase 5

**Batch-vs-live `DIFF_` column divergence (7 vs. 9 stats):** `02_feature_engineering.py`'s DIFF loop (training-time) builds `DIFF_` columns for 7 stats (`DIFF_STATS` — excludes `FT_PCT` and `FG3_PCT`). `04_value_detector.py`'s `bygg_feature_rad` (live-scoring-time, via `features.py`) builds `DIFF_` columns for all 9 stats (`STATS_KOLONNER`). This is pre-existing behavior, unchanged by this plan. It is harmless today only because `04_value_detector.py` filters the live feature row down to `feature_kolonner` (the model's actual trained columns) before calling `predict_proba`. If Phase 5's backtest ever needs to build a feature row without that same filter step, or if a future retrain changes which columns the model trains on, this divergence becomes load-bearing and should be resolved (either by having the live path build only 7 DIFF columns, or by explicitly documenting why 2 extra live-only DIFF columns are safe to compute-and-discard on every call).

## Deviations from Plan

None - plan executed exactly as written, including the one deliberate `known_defect` fix (`df` → `df_raw`), which was explicitly scoped as in-plan, not an out-of-scope deviation.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Known Stubs

None - all extracted functions are wired to real call sites with real logic; no placeholder data paths introduced.

## Threat Flags

None - this plan's threat model items (T-02-13, T-02-14, T-02-15, T-02-16, T-02-01) were all mitigations for this exact extraction; all satisfied:
- T-02-13 (train/serve skew via stat-list/naming divergence): `STATS_KOLONNER` single-sourced; repo-wide grep confirms exactly one hardcoded stat list; `test_bygg_feature_rad_kolonnenavn` pins the 27-key naming contract.
- T-02-14 (leakage via `<=` instead of `<`): strict `<` grep-asserted; `test_as_of_filtrerer_bort_kampen_selv` asserts the boundary row is excluded; the deliberate-break check proved the assertion is not vacuous.
- T-02-15 (`df` → `df_raw` fix silently altering trained-model input): byte-level `cmp` of the regenerated `nba_features.csv` against the pre-edit baseline across 3,638 games — IDENTISK, zero divergence.
- T-02-16 (DoS via `snitt_fra_kamplogg` raising `KeyError` on malformed `nba_api` response): accepted per plan — identical to current behaviour, `len(df) < 3` guard preserved unchanged in `04_value_detector.py`.
- T-02-01 (uninspected WIP swept into commits): explicit-pathspec staging used throughout (`git add features.py`, `git add tests/test_features.py`, `git add 02_feature_engineering.py 04_value_detector.py`); `03_tren_modell.py` and `.planning/config.json` never staged by this plan.

## Next Phase Readiness

- `pytest -v` collects and passes 30 tests (23 from plans 02-02/02-03/02-04 + 7 new from this plan)
- `features.py` is importable with a single upstream dependency (`pandas`) — ready for Phase 5's backtest to call `beregn_lag_form(..., as_of=D)` identically
- `02_feature_engineering.py` and `04_value_detector.py` contain zero surviving copies of the rolling-window logic, the stat list, or the feature-row naming — CORE-01's feature-engineering half is now single-sourced (team-name resolution was closed in plan 04, value/EV/Kelly in plan 03)
- `03_tren_modell.py` remains untouched (still shows ` M` from pre-existing WIP), per D-09
- The batch-vs-live `DIFF_` column divergence (7 vs. 9 stats) is documented above for Phase 5 to resolve if backtest parity requires it

---
*Phase: 02-shared-core-extraction-test-foundation*
*Completed: 2026-08-21*

## Self-Check: PASSED

- FOUND: `features.py`
- FOUND: `tests/test_features.py`
- FOUND: commits `d01bf36`, `30e6e95`, `1121bbc` in `git log --oneline --all`
