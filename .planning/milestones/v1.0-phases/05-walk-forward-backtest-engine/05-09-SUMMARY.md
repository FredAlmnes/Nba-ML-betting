---
phase: 05-walk-forward-backtest-engine
plan: 09
subsystem: backtest-engine
tags: [backtest, staking, kelly, sweep, sensitivity-analysis, json]

# Dependency graph
requires:
  - phase: 05-walk-forward-backtest-engine
    plan: 08
    provides: simuler_bets, flat_innsats_belop, hent_metrikkserier, skriv_kjoring, kjor_og_lagre
provides:
  - "backtest.py — KELLY_ARMER, SWEEP_FIL, _sikre_prediksjoner_utenfor_holdout, kjor_kelly_sweep, skriv_kelly_sweep"
  - "kjor_og_lagre(..., kjor_sweep=False) — default-off flag that produces kelly_sweep.json from the same predict pass"
  - "BT-07's Kelly-fraction sensitivity sweep (flat/quarter/half/full) over one cached predict pass"
affects: [05-10, 05-12, 05-13]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "predict-once/simulate-many: kjor_kelly_sweep calls simuler_bets once per staking arm over a fresh shallow copy of the same cached prediction list, never re-running the retrain loop"
    - "flat arm is fraction=None, never fraction=0 — a backtest.py-local branch through flat_innsats_belop (D-05-03), because strategy.beregn_innsats returns 0.0 for every bet at kelly_fraksjon=0"
    - "structural holdout refusal: kjor_kelly_sweep has no allow-flag and never names config.HOLDOUT_START_DATO in its own source; kjor_og_lagre raises before any work when holdout and kjor_sweep are both set"

key-files:
  created: []
  modified:
    - backtest.py (Task 1: KELLY_ARMER/_sikre_prediksjoner_utenfor_holdout/kjor_kelly_sweep; Task 2: skriv_kelly_sweep + kjor_og_lagre wiring)
    - tests/test_backtest.py (Task 1: banner 7 sweep tests; Task 2: banner 7 persistence/wiring tests; Task 3: banner 8 real-data test)
    - .planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md (BT-07 row filled in)

key-decisions:
  - "Fixed a signature mismatch (Rule 1) vs. the plan's suggested oppsummer_ledger(*hent_metrikkserier(ledger), startkapital, ...) call: hent_metrikkserier's 4th element is clv_verdier, but oppsummer_ledger's 4th positional parameter is startkapital — a blind star-unpack sends the clv list into the startkapital slot and the startkapital float into the clv slot. Unpacked explicitly and passed clv_verdier as a keyword, matching bygg_manifest's existing (correct) pattern."

requirements-completed: [BT-07]

# Metrics
duration: ~20min
completed: 2026-08-27
---

# Phase 5 Plan 9: Kelly-fraction sensitivity sweep Summary

**Four-arm Kelly-fraction sweep (flat/quarter/half/full) re-staked from one cached walk-forward predict pass, written to `backtests/<run_id>/kelly_sweep.json` behind a default-off `kjor_og_lagre(kjor_sweep=True)` flag, with its own structural holdout refusal independent of the main entry point's.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3
- **Files modified:** 3 (`backtest.py`, `tests/test_backtest.py`, `05-VALIDATION.md`)

## Kontrakt for plan 05-10/05-12

```python
KELLY_ARMER = (
    ("flat", None), ("kvart", 0.25), ("halv", 0.5), ("full", 1.0),
)   # tuple of tuples — not mutable in place; flat's fraction is None, never 0

SWEEP_FIL = "kelly_sweep.json"

_sikre_prediksjoner_utenfor_holdout(prediksjoner)
# -> None; raises HoldoutLaastFeil if any as_of_dato OR kamp_dato across the
#    cached rows is >= config.HOLDOUT_START_DATO. Delegates entirely to plan
#    05-07's _sikre_ikke_holdout with the default (rejecting) flag.

kjor_kelly_sweep(prediksjoner, run_id=None, startkapital=config.STARTKAPITAL,
                  min_innsats=config.MIN_INNSATS, maks_innsats=config.MAX_INNSATS,
                  armer=KELLY_ARMER, opprettet=None, skriv_ut=True)
# -> sweep dict. No parameter name contains "holdout"; the function's own
#    source never names config.HOLDOUT_START_DATO or tillat_holdout — both
#    are asserted by a source-grep test. Calls simuler_bets exactly once per
#    arm over list(prediksjoner) (fresh shallow copy each time, rows read-only).

skriv_kelly_sweep(run_id, sweep, katalog=BACKTEST_KATALOG)
# -> written file path. Validates run_id via _valider_run_id, requires the
#    run directory to ALREADY exist (FileNotFoundError otherwise — a sweep
#    is a sub-output of a run, never its own run), opens SWEEP_FIL in
#    exclusive-creation mode "x" (FileExistsError on a second write, never
#    overwrites an earlier sweep).

kjor_og_lagre(..., innbrenning_maaneder=INNBRENNING_MANEDER,
              kjor_sweep=False, skriv_ut=True)
# -> (sti, manifest, ledger)   # UNCHANGED return shape — kjor_sweep never
#    adds a 4th return value; the sweep dict lands on disk only.
# Raises ValueError at the top of the function, before any predict pass and
# before any directory is created, when holdout=True and kjor_sweep=True
# together. When kjor_sweep=True (and holdout=False), runs kjor_kelly_sweep
# AFTER skriv_kjoring has returned, over the SAME in-memory `prediksjoner`
# list simuler_bets already consumed, then calls skriv_kelly_sweep(run_id, sweep).
```

**Sweep dict — top-level key order:** `run_id, opprettet, type, basis_arm, kilde, staking, bootstrap, armer`.
`type` is the literal string `"kelly-sweep"`. `basis_arm` is the `etikett` of the arm whose
`kelly_fraksjon` equals `config.KELLY_FRAKSJON` (`"halv"` today), or `None` if no arm matches.
`kilde` = `{antall_prediksjoner, fra_dato, til_dato}` (`fra_dato`/`til_dato` are min/max
`kamp_dato` across the cached rows, `None` for an empty list). `staking` = `{startkapital,
min_innsats, maks_innsats, flat_innsats_andel, flat_innsats}`. `bootstrap` = `{seed,
n_resamples}` — same `BOOTSTRAP_SEED`/`BOOTSTRAP_N_RESAMPLES` module constants plan 05-08 defined.

**Per-arm dict — key order:** `etikett, kelly_fraksjon, flat_innsats, metrikker, tellere`.
`metrikker` is a full `metrics.oppsummer_ledger` return dict (same 18 keys plan 05-08's
manifest `metrikker` block carries). `tellere` is that arm's own `resultat_sim` dict
(plan 05-08's 13-key counter list), copied via `copy.deepcopy` — this is what makes the
flat-vs-Kelly bet-count difference explainable from the file via `kandidater_uten_kelly_edge`.

## Ekte sweep 2022-10-24..2022-12-31

Ran `backtest.kjor_og_lagre(backtest.klargjor_backtestdata(fra="2022-10-24",
til="2022-12-31"), min_treningskamper=100, kjor_sweep=True, skriv_ut=False)` against the
real `nba_features.csv`, `odds_arkiv.db` and `nba_spillerlogg_raw.csv`. Predict-pass
counters in the new `manifest.json` reproduced plan 05-08's recorded run of the identical
window exactly (`datoer_totalt` 66, `datoer_hoppet_over_for_lite_treningsgrunnlag` 15,
`datoer_behandlet` 51, `kamper_totalt` 388, `retreninger` 2, `kamper_hoppet_over_manglende_odds`
0, `kamper_hoppet_over_ukjent_lag` 0) — confirming Tasks 1/2 changed nothing upstream of the
sweep.

`run_id`: `20260827-140650-6fd9654f`

```json
"kilde": {"antall_prediksjoner": 102, "fra_dato": "2022-11-09", "til_dato": "2022-12-31"},
"staking": {"startkapital": 1000.0, "min_innsats": 20.0, "maks_innsats": 150.0,
            "flat_innsats_andel": 0.02, "flat_innsats": 20.0},
"bootstrap": {"seed": 42, "n_resamples": 1000}
```

| etikett | kelly_fraksjon | flat_innsats | antall_bets | roi | roi_ci_nedre | roi_ci_oevre | maks_drawdown_kroner | maks_drawdown_andel | kandidater_uten_kelly_edge |
|---------|-----------------|---------------|-------------|-----|--------------|--------------|-----------------------|----------------------|-----------------------------|
| flat | None | 20.0 | 102 | 0.1144 | -0.1198 | 0.3510 | 227.60 | 0.1920 | 0 |
| kvart | 0.25 | None | 102 | 0.0575 | -0.1922 | 0.3306 | 1524.21 | 0.7567 | 0 |
| halv | 0.5 | None | 102 | 0.1073 | -0.1389 | 0.3523 | 1585.76 | 0.6225 | 0 |
| full | 1.0 | None | 102 | 0.1140 | -0.1267 | 0.3550 | 1669.73 | 0.6829 | 0 |

**This is a plumbing check over 51 dates, not a verdict.** Every arm's 95% ROI confidence
interval spans roughly -13% to +35% — far too wide to say anything about which fraction is
best. No Kelly fraction is recommended here; plan 05-12's checkpoint owns that judgment on
the full multi-season run.

## Basisarmen mot manifestet

The `"halv"` arm (`kelly_fraksjon=0.5`, matching `config.KELLY_FRAKSJON`) is named by
`basis_arm`. Its `metrikker` block equals the same run's `manifest.json` `metrikker` block
exactly — verified by direct dict equality (`basis["metrikker"] == m["metrikker"]`), not
just spot-checked fields — because it is produced from the same staking configuration over
the same cached predictions. This equality is what makes the other three arms
interpretable as differing only in staking rule.

## Hvorfor armene ikke har like mange bets

In this particular 51-date window, all four arms happened to place the same 102 bets
(`kandidater_uten_kelly_edge` is 0 for every arm) — no candidate in this window had a
non-positive Kelly edge. This is a property of the data, not of the mechanism: the
synthetic unit test `test_flat_armen_better_kandidater_kelly_armene_hopper_over` proves the
general case directly — the flat arm bets candidates whose Kelly edge is non-positive
(`modell_prob <= 1/odds`) while the three Kelly arms skip them, because
`strategy.beregn_innsats` returns `0.0` whenever `kelly*(b*p-q)/b <= 0` independently of the
fraction. Whenever this happens on real data, `kandidater_uten_kelly_edge` in each arm's
`tellere` block is where a reader sees the count, so the difference is explainable straight
from `kelly_sweep.json` alone.

## Holdout-status

This plan did NOT spend the holdout, and structurally cannot: `kjor_kelly_sweep` has no
parameter whose name contains `holdout`, and its own source (`inspect.getsource`) never
names `config.HOLDOUT_START_DATO` or `tillat_holdout` — it delegates the entire comparison
to plan 05-07's `_sikre_ikke_holdout` via `_sikre_prediksjoner_utenfor_holdout`, run before
any staking. The composed `kjor_og_lagre(holdout=True, kjor_sweep=True)` call raises
`ValueError` before either predict entry point runs and before any directory is created
(`test_sweep_og_holdout_er_gjensidig_utelukkende`). Plan 05-13 still owns the single,
scored, ever-spent holdout run.

## Accomplishments

- **Task 1** — `KELLY_ARMER`, `SWEEP_FIL`, `_sikre_prediksjoner_utenfor_holdout`,
  `kjor_kelly_sweep`: the four-arm sweep over one cached prediction list, with its own
  holdout pre-flight over both `as_of_dato` and `kamp_dato`, a shared bootstrap seed across
  all four arms, and a `basis_arm` field naming the arm that mirrors `config.KELLY_FRAKSJON`.
  92/92 tests pass (76 inherited from plan 05-08 + 16 new).
- **Task 2** — `skriv_kelly_sweep`, `kjor_og_lagre(kjor_sweep=False)`: persistence into
  `backtests/<run_id>/kelly_sweep.json`, mirroring `skriv_kjoring`'s path-containment
  discipline, requiring the run directory to pre-exist and refusing to overwrite an earlier
  sweep; the composed entry point refuses `holdout=True, kjor_sweep=True` before any work.
  103/103 tests pass.
- **Task 3** — real-archive sweep run reproducing plan 05-08's exact predict-pass counters
  and its own basis-arm-equals-manifest property, one permanent skip-guarded real-data test,
  and `05-VALIDATION.md`'s BT-07 row filled in (last unassigned row in the table).
  104/104 tests pass; full suite 308/308 green.

## Task Commits

| Task | Commits |
|------|---------|
| 1 | `fd5fd0d` test(05-09): add failing tests for Kelly-fraction sweep over cached predictions; `c549e83` feat(05-09): implement kjor_kelly_sweep |
| 2 | `5d35cbc` test(05-09): add failing tests for kelly_sweep.json persistence and kjor_og_lagre wiring; `8cfaa9e` feat(05-09): implement skriv_kelly_sweep and wire kjor_sweep into kjor_og_lagre |
| 3 | `6e03253` test(05-09): add permanent real-data Kelly sweep test and fill in BT-07 validation row |

## TDD Gate Compliance

Both TDD tasks (1 and 2) show `test(...)` commits immediately before their corresponding
`feat(...)` commits in git log: `fd5fd0d` -> `c549e83` for Task 1, `5d35cbc` -> `8cfaa9e` for
Task 2. Task 1's RED commit was verified failing before implementation existed (13 of 92
tests failed with `TypeError`/`AttributeError` for the not-yet-implemented sweep function —
see Deviations below for the specific bug this caught). Task 2's tests were authored
against the Task 1 implementation already in place and verified to fail
(`AttributeError: module 'backtest' has no attribute 'skriv_kelly_sweep'`) before
`skriv_kelly_sweep`/the `kjor_sweep` wiring were written. Task 3 is untyped `tdd` (plain
`type="auto"`) and committed as a single `test(...)` commit per its non-TDD nature.

## Files Created/Modified

- `backtest.py` — modified (Task 1: banner 6, `KELLY_ARMER`/`_sikre_prediksjoner_utenfor_holdout`/`kjor_kelly_sweep`; Task 2: `skriv_kelly_sweep` + `kjor_og_lagre(kjor_sweep=False)` wiring)
- `tests/test_backtest.py` — modified (Task 1: banner 7, 16 sweep tests; Task 2: banner 7 continued, 11 persistence/wiring tests; Task 3: banner 8, 1 permanent real-data test)
- `.planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md` — modified (BT-07 row: plan `05-09`, wave `7`, task `05-09-01`, threat `T-05-09-01`, File Exists `tests/test_backtest.py`)

## Decisions Made

- No new decisions beyond D-05-01/D-05-03, both applied as locked: the holdout boundary
  (`config.HOLDOUT_START_DATO`) via delegation to plan 05-07's guard, and the flat stake
  (`flat_innsats_belop`, D-05-03's recommended option) as a `backtest.py`-local branch with
  fraction `None`, never `0`.
- D-05-02's ex-burn-in metric set is deliberately NOT repeated per arm — recorded explicitly
  in `kjor_kelly_sweep`'s docstring so it does not read as an oversight. The burn-in question
  is answered once, by `manifest.json`, over the basis arm; the sweep's question is staking
  sensitivity.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's suggested `oppsummer_ledger(*hent_metrikkserier(ledger), startkapital, ...)` call mismatches the real signature**
- **Found during:** Task 1, first GREEN verification run (`test_kelly_sweep_bruker_cachet_prediksjoner` and 12 other new tests failed with `TypeError: 'float' object is not iterable`)
- **Issue:** The plan's `<action>` text specifies `metrikker` as
  `oppsummer_ledger(*hent_metrikkserier(ledger), startkapital, n_resamples=..., seed=...)`.
  `hent_metrikkserier` returns a 4-tuple `(profitter, innsatser, vant_flagg, clv_verdier)`,
  but `oppsummer_ledger`'s real signature is
  `(profitter, innsatser, vant_flagg, startkapital, clv_verdier=None, ...)` — `startkapital`
  is the 4th *positional* parameter, not `clv_verdier`. A blind star-unpack fills
  `oppsummer_ledger`'s `startkapital` slot with the clv list and its `clv_verdier` slot with
  the startkapital float, producing a `TypeError` deep inside `metrics.beregn_maks_drawdown`
  when it tried to iterate a float.
- **Fix:** Unpacked `hent_metrikkserier(ledger)` into named variables first, then called
  `oppsummer_ledger(profitter, innsatser, vant_flagg, startkapital, clv_verdier=clv_verdier,
  n_resamples=BOOTSTRAP_N_RESAMPLES, seed=BOOTSTRAP_SEED)` — the same explicit-unpack-then-
  keyword pattern `bygg_manifest` (plan 05-08) already uses correctly. Applied the identical
  fix to the mirroring assertion in `test_basis_armen_reproduserer_simuler_bets`.
- **Files modified:** `backtest.py`, `tests/test_backtest.py`
- **Verification:** `python3 -m pytest tests/test_backtest.py -q` → `92 passed` (was 13 failed before the fix)
- **Committed in:** `c549e83` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — a bug in the plan's own suggested code, caught
immediately by the RED-then-GREEN cycle before any commit)
**Impact on plan:** Zero behavioral change to the intended sweep semantics — the fix makes
`kjor_kelly_sweep` compute exactly the metrics the plan specifies, just via a call that
actually matches `oppsummer_ledger`'s real parameter order. No scope creep.

### Documentation-verification note (not a deviation, not a defect)

Task 3's acceptance criteria include `grep -c 'Wave 0' 05-VALIDATION.md` expected to output
`1`. The file already contained 3 pre-existing "Wave 0" occurrences unrelated to any table
row (a `## Wave 0 Requirements` heading plus two generic checklist bullets) before this plan
touched anything — confirmed via `git show HEAD~5:...05-VALIDATION.md`. After filling in the
BT-07 row, `grep -c '❌ Wave 0'` correctly outputs `0` (no row claims a missing test file, the
substantive property the criterion was checking for) and `grep -cE '^\| 05-XX-XX \|'` outputs
`0` (no unassigned row remains) — both satisfied. The literal `grep -c 'Wave 0'` count of `1`
was not achievable given the file's pre-existing content and was not something this plan's
scope authorized fixing (touching the checklist bullets is outside "fill in the BT-07 row").

## Issues Encountered

None beyond the deviation documented above. System `python3` still lacks
`pytest`/`xgboost`/`pandas` on this machine (consistent with every prior Phase 5 plan) — all
verification ran via `./venv/bin/python3`.

## User Setup Required

None. All output is local, gitignored (`backtests/`), and requires no new credentials or
configuration.

## Next Phase Readiness

- Plan 05-10 (`08_kjor_backtest.py`) can put `kjor_og_lagre`'s `kjor_sweep` flag behind an
  explicit CLI flag; the `(sti, manifest, ledger)` return shape is unchanged, so no CLI code
  needs to branch on whether a sweep was requested beyond passing the flag through.
- Plan 05-12 (full run + freeze checkpoint) has a real `kelly_sweep.json` shape to expect and
  a self-describing file (staking knobs, bootstrap seed, `kilde` provenance) to read when
  choosing the Kelly fraction before the holdout is spent.
- Plan 05-13's holdout run remains unspent and structurally protected: `kjor_kelly_sweep`
  cannot reach it (no allow-flag, no token naming the boundary), and
  `kjor_og_lagre(holdout=True, kjor_sweep=True)` is refused outright.
- Full pytest suite green (308 tests); no blockers for Plan 05-10.

---
*Phase: 05-walk-forward-backtest-engine*
*Completed: 2026-08-27*

## Self-Check: PASSED

- `backtest.py` exists and contains `kjor_kelly_sweep`, `skriv_kelly_sweep` — FOUND
- `tests/test_backtest.py` exists and contains `test_kelly_sweep_bruker_cachet_prediksjoner` — FOUND
- `.planning/phases/05-walk-forward-backtest-engine/05-VALIDATION.md` — FOUND
- `.planning/phases/05-walk-forward-backtest-engine/05-09-SUMMARY.md` — FOUND
- `backtests/20260827-140650-6fd9654f/{manifest.json,ledger.csv,kelly_sweep.json}` exist on disk — FOUND
- Commits `fd5fd0d`, `c549e83`, `5d35cbc`, `8cfaa9e`, `6e03253` exist in `git log` — FOUND
- `python3 -m pytest tests/ -q` — 308 passed
