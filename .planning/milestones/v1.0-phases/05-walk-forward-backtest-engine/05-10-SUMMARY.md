---
phase: 05-walk-forward-backtest-engine
plan: 10
subsystem: cli
tags: [argparse, cli, walk-forward-backtest, holdout-guard, kelly-sweep]

# Dependency graph
requires:
  - phase: 05-walk-forward-backtest-engine (plans 05-07..05-09)
    provides: backtest.klargjor_backtestdata, backtest.kjor_og_lagre (incl. kjor_sweep),
      backtest.HoldoutLaastFeil, the manifest/sweep file layout
provides:
  - "08_kjor_backtest.py: numbered CLI entry point for the walk-forward backtest"
  - "ISO-validated --fra/--til with a computed default upper bound (dagen for holdout)"
  - "The only two-flag path (--holdout + --bekreft-holdout) into the locked 2024-25 holdout"
  - "--sweep on-switch for the Kelly-fraction sensitivity sweep"
  - "KOMME_I_GANG.md Steg 8"
affects: [05-12-full-train-calibrate-run, 05-13-holdout-spend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "argparse type= validators (iso_dato, positiv_flyt) that fail before any I/O"
    - "Cross-flag refusals via parser.error() run in a fixed, documented order in main()"
    - "kjor_holdout() is the file's single door to holdout=True, pinned by an inspect.getsource
      source-exclusion test"

key-files:
  created:
    - 08_kjor_backtest.py
    - tests/test_kjor_backtest.py
  modified:
    - KOMME_I_GANG.md

key-decisions:
  - "Default --til resolves to dag_for_holdout() (day before config.HOLDOUT_START_DATO) only
    when --holdout is absent and --til was omitted -- an explicitly typed --til is never
    overridden and the --holdout path is never clamped"
  - "Four holdout-adjacent flag combinations refused via parser.error (exit 2) before any file
    is opened: --bekreft-holdout alone, --holdout alone, --holdout+--sweep, --holdout+--fra/--til"
  - "bygg_kjoreargumenter() deliberately excludes holdout and kjor_sweep so the only place either
    token can appear is the one function whose job is to set it"

patterns-established:
  - "Real CLI-driven smoke run before writing the permanent test, comparing periode/datakvalitet
    across a plain run and a --sweep run to prove the sweep never moves a predict-pass counter"

requirements-completed: [BT-01, BT-03, BT-05, BT-07]

# Metrics
duration: ~10min (Tasks 2-3 of this continuation; Task 1 was completed and committed in an
  earlier, session-limited dispatch — see 7398ef6)
completed: 2026-08-27
---

# Phase 5 Plan 10: Walk-Forward Backtest CLI Summary

**Numbered CLI wrapper (`08_kjor_backtest.py`) around `backtest.py`'s walk-forward engine: ISO-validated date range with a computed safe default, a Kelly-sweep on-switch, and the locked 2024-25 holdout reachable only through a two-flag path that is refused four different ambiguous ways before any file is opened.**

## Performance

- **Duration:** Task 1 (parser/validators) was completed and committed in a prior, session-limited
  dispatch (commit `7398ef6`). This continuation executed Tasks 2 and 3.
- **Tasks:** 3/3 complete (1 from prior dispatch, 2 from this continuation)
- **Files modified:** 3 (`08_kjor_backtest.py`, `tests/test_kjor_backtest.py`, `KOMME_I_GANG.md`)

## Accomplishments

- `main()` dispatches on `args.holdout` alone (one `if`/`else`), and `kjor_holdout()` is provably
  the only function in the file whose source may contain `holdout=True`
  (`test_bare_holdout_funksjonen_apner_vinduet` removes its own source and greps the rest)
- Four holdout-adjacent flag combinations are refused with exit code `2` before any directory is
  created: confirmation without `--holdout`, `--holdout` without confirmation, `--holdout` +
  `--sweep`, `--holdout` + `--fra`/`--til`
- A bare invocation resolves `--til` to the day before `config.HOLDOUT_START_DATO`
  (`dag_for_holdout()`), so `python 08_kjor_backtest.py` with no flags replays the train/calibrate
  slice instead of tripping `HoldoutLaastFeil`; an explicitly typed `--til` is always honoured
  unchanged, and the `--holdout` path is never clamped
- The printed `BACKTEST-OPPSUMMERING` block carries the run id, run type, run directory, headline
  metrics, and — deliberately next to the ROI, not buried lower — the
  `kamper_hoppet_over_manglende_odds` skip count (05-RESEARCH.md Pitfall 2)
- Two real CLI-driven runs over `2022-11-15..2022-11-30` (one plain, one `--sweep`) proved the
  sweep never moves a single predict-pass counter (`periode`/`datakvalitet` byte-identical between
  the two manifests)
- A real tuning range reaching into the holdout (`--fra 2024-10-01 --til 2024-11-15`) raised
  `HoldoutLaastFeil` with exit code 1 and created no run directory — BT-03 demonstrated at the
  surface an operator actually touches
- A real `--til`-less run (`--fra 2024-04-10`) exited `0`, echoed the resolved
  `2024-09-30 (standard: dagen før holdout)`, and its `manifest.json` carries
  `periode.til_dato < config.HOLDOUT_START_DATO` — proving the documented bare command actually
  runs rather than crashes
- `KOMME_I_GANG.md` now documents Steg 8: prerequisites, the default/`--sweep`/bounded-window
  invocations, and a `⚠️` spend-once holdout warning with no copy-pasteable holdout command
- 26/26 tests pass in `tests/test_kjor_backtest.py`; full suite is 334 passed (up from 320 before
  this plan)

## Task Commits

Each task was committed atomically:

1. **Task 1: CLI parser and date/numeric validators** - `7398ef6` (feat) — completed and
   committed in a prior, session-limited dispatch
2. **Task 2: Dispatch, holdout-flag refusals, printed run summary** - `793ad8c` (feat)
3. **Task 3: Real CLI smoke run, permanent test, KOMME_I_GANG.md Steg 8** - `1d34a87` (docs)

**Plan metadata:** committed alongside this SUMMARY (see final commit below)

## Files Created/Modified

- `08_kjor_backtest.py` - Thin CLI wrapper: `iso_dato`/`positiv_flyt`/`dag_for_holdout` validators
  (Task 1), `bygg_parser` (Task 1), `bygg_kjoreargumenter`/`last_data`/`kjor_tuning`/`kjor_holdout`/
  `skriv_oppsummering`/`main` (Task 2)
- `tests/test_kjor_backtest.py` - 26 tests: validator/parser tests (Task 1), dispatch/refusal/
  summary-printing tests (Task 2), one skip-guarded real-data smoke test (Task 3)
- `KOMME_I_GANG.md` - New "Steg 8: Kjør backtesten" section; "Neste steg" bullet updated to point
  at it instead of listing backtesting as future work

## Decisions Made

- Default `--til` resolution happens only after the four holdout-combination checks in `main()`,
  because whether the default applies depends on `args.holdout` — resolving it earlier would have
  required re-checking the holdout flag inside the resolution step itself.
- `bygg_kjoreargumenter(args)` intentionally excludes `holdout` and `kjor_sweep` so the shared
  kwargs dict can never accidentally carry either token; `kjor_tuning` sets `kjor_sweep` from
  `args.sweep` and never mentions `holdout`, `kjor_holdout` sets `holdout=True` and never mentions
  `kjor_sweep`.
- `last_data()` is the file's only other exception handler beyond `iso_dato`'s narrow
  `ValueError`->`ArgumentTypeError` conversion, and it catches only `FileNotFoundError` — a
  `HoldoutLaastFeil` or `ValueError` from `kjor_og_lagre` must reach the terminal as a traceback
  with a non-zero exit, never be swallowed as a printed warning.

## Deviations from Plan

None - plan executed exactly as written across all three tasks.

## Self-Check

- `08_kjor_backtest.py` exists: FOUND
- `tests/test_kjor_backtest.py` exists: FOUND
- `KOMME_I_GANG.md` modified: FOUND
- Commit `7398ef6` (Task 1): FOUND
- Commit `793ad8c` (Task 2): FOUND
- Commit `1d34a87` (Task 3): FOUND
- `tests/test_kjor_backtest.py` — 26 passed: VERIFIED
- Full suite `tests/ -q` — 334 passed, 0 failed: VERIFIED
- Real backtests written to `backtests/20260827-225526-6fd9654f/` (plain) and
  `backtests/20260827-225535-6fd9654f/` (with `--sweep`, includes `kelly_sweep.json`): VERIFIED
  on disk, gitignored (`git status --porcelain backtests/` empty)
- Holdout-range refusal (`--fra 2024-10-01 --til 2024-11-15`) exited 1 with `HoldoutLaastFeil` and
  created no 5th run directory: VERIFIED
- Bare-default-clamp real run (`--fra 2024-04-10`, `--til` omitted) exited 0 with
  `periode.til_dato = "2024-04-14"` < `config.HOLDOUT_START_DATO = "2024-10-01"`: VERIFIED

## Self-Check: PASSED

## Kontrakt for plan 05-12/05-13

**Shipped `bygg_parser()` flags** (all defaults read live from `config.py`/`backtest.py`, never
restated as literals):

| Flag | Type | Default | Notes |
|------|------|---------|-------|
| `--fra` | `iso_dato` | `None` | earliest date in `nba_features.csv` if omitted |
| `--til` | `iso_dato` | `None` | resolves to `dag_for_holdout()` (day before `config.HOLDOUT_START_DATO`) unless `--holdout` is given |
| `--sweep` | flag | off | cannot combine with `--holdout` |
| `--holdout` | flag | off | requires `--bekreft-holdout`; cannot combine with `--sweep`/`--fra`/`--til` |
| `--bekreft-holdout` | flag | off | meaningless without `--holdout` |
| `--uten-skadefilter` | flag | off (filter ON by default) | reaches both the loader and the engine |
| `--min-value-terskel` | float | `config.MIN_VALUE_TERSKEL` (0.05) | |
| `--min-odds` | float | `config.MIN_ODDS` (1.50) | must be `<` `--maks-odds` |
| `--maks-odds` | float | `config.MAX_ODDS` (4.00) | |
| `--kelly-fraksjon` | float | `config.KELLY_FRAKSJON` (0.5) | must be in `(0, 1.0]` |
| `--startkapital` | `positiv_flyt` | `config.STARTKAPITAL` (1000.0) | must be `> 0` |
| `--min-treningskamper` | int | `backtest.MIN_TRENINGSKAMPER` (100) | |
| `--features-fil` | str | `backtest.klargjor_backtestdata`'s own default | |
| `--arkiv` | str | `backtest.klargjor_backtestdata`'s own default | |
| `--katalog` | str | `backtest.BACKTEST_KATALOG` ("backtests") | |
| `--stille` | flag | off | suppresses `backtest.py`'s own per-pass banners only |

No `--flat-innsats` and no `--innbrenning-maaneder` flag exist by design (see `08_kjor_backtest.py`
section 2 comments) — the flat stake is a sweep arm (D-05-03), and the burn-in window is a
phase-level reporting policy already in every manifest (D-05-02).

**Plan 05-12's full train/calibrate run with the sweep** — exact invocation:

```bash
python 08_kjor_backtest.py --sweep
```

No `--fra`/`--til` needed: the bare invocation already resolves `--til` to the day before
`config.HOLDOUT_START_DATO`, replaying the entire train/calibrate slice. Expect this to take
several minutes (model retrains once per processed calendar month).

**Plan 05-13's single holdout run** — exact invocation, and it is spent by running it:

```bash
python 08_kjor_backtest.py --holdout --bekreft-holdout
```

Every threshold/Kelly flag (`--min-value-terskel`, `--min-odds`, `--maks-odds`,
`--kelly-fraksjon`, `--startkapital`, `--min-treningskamper`) must already be frozen (plan 05-12's
job) before this is run — none of those flags are overridden here, so the invocation above uses
whatever `config.py` values were frozen. **The resulting `run_id` printed in the
`BACKTEST-OPPSUMMERING` block must be written into `.planning/STATE.md`** immediately afterward;
there is no way to detect from a later session that the holdout has been spent other than that
record.
