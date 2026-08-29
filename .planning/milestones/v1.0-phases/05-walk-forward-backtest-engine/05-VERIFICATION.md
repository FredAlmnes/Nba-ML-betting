---
phase: 05-walk-forward-backtest-engine
verified: 2026-08-29T10:00:00Z
status: passed
score: 5/5 success criteria verified, 7/7 BT requirements verified
overrides_applied: 0
---

# Phase 5: Walk-Forward Backtest Engine Verification Report

**Phase Goal:** The full betting decision pipeline (model score → value threshold → odds filter → injury filter → half-Kelly stake) can be replayed chronologically against archived historical odds, producing reproducible, leakage-safe ROI/drawdown/CLV evidence gated by a locked holdout — the project's actual Core Value deliverable.
**Verified:** 2026-08-29T10:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A walk-forward backtest replays model→value→odds→injury→stake chronologically across 2022-23..2024-25 using archived historical odds | ✓ VERIFIED | `backtest.py::kjor_backtest` (1283 lines) drives a per-date loop calling `model.py` (retrain/score), `strategy.py` (value/EV threshold), `odds.py` (archived best-price lookup), `skadefilter.py::sjekk_lag_helse_som_of` (as-of injury check), and `simuler_bets` (flat or Kelly stake). Two real runs executed end-to-end: tuning slice `20260828-095233-3cc4a836` (2022-10-24 → 2024-04-14, 2302 games, 52 bets) and holdout `20260829-092351-3cc4a836` (2024-10-22 → 2025-04-13, 1225 games, 19 bets). Both produced full manifests with real ledgers on disk (`backtests/<run_id>/manifest.json`, `ledger.csv`). |
| 2 | Every data point (odds, injury status, rolling stats) is provably filtered to "known as of date D" — structurally, not by convention | ✓ VERIFIED | `features.py`/`skadefilter.py::hent_sesonglogg_som_of` filter strictly `< as_of_dato` (verified in code, `skadefilter.py:305-323`, docstring explicitly notes boundary row on `as_of` itself is excluded, "ALDRI <="). `odds.py` archived lookups select snapshots at/ before `bet_time`, separately from `closing`. `tests/test_parity.py` contains dedicated leakage-regression tests (`test_fremtidige_rader_endrer_ikke_tidligere_features`, `test_grenserad_paa_as_of_er_ekskludert`) plus a live-vs-backtest decision-parity test with an explicit discriminating-power self-check (`test_paritetsassertionen_har_diskriminerende_kraft`, i.e. the test is proven capable of failing, not vacuously green). All pass. |
| 3 | A locked, never-touched final holdout slice is checked exactly once, after all threshold/parameter decisions are frozen — enforced by code | ✓ VERIFIED | `backtest.py::_sikre_ikke_holdout` raises `HoldoutLaastFeil` for any date `>= config.HOLDOUT_START_DATO` ("2024-10-01") unless `tillat_holdout=True`, and this guard is checked twice per iteration (pre-flight + per-date) inside `kjor_backtest`. Only one function, `kjor_endelig_holdout_backtest`, is ever allowed to pass `tillat_holdout=True` — `tests/test_kjor_backtest.py` asserts via source-level grep that no other call site contains `holdout=True`. The holdout was spent exactly once: `05-HOLDOUT-RESULTAT.md` documents three independent pre-run scans (filesystem `backtests/*/manifest.json` type field, `STATE.md` register, planning-artifact grep) all showing zero prior holdout runs, followed by one confirmed run (`20260829-092351-3cc4a836`, `periode.fra_dato = "2024-10-22" > HOLDOUT_START_DATO`). `.planning/STATE.md` records `HOLDOUT BRUKT: ja` with the run_id. |
| 4 | A backtest run produces a reproducible, versioned run manifest (config + date range + ROI + win rate + max drawdown + bet count + CI), enabling before/after comparison against the live config | ✓ VERIFIED | `backtests/20260829-092351-3cc4a836/manifest.json` (inspected directly) contains `run_id`, `konfig` (all 15 frozen parameters), `periode` (date range + game/date counts), `datakvalitet` (skip/edge counters), and `metrikker` (roi, roi_ci_nedre/oevre, vinnrate + CI, maks_drawdown, antall_bets, clv_snitt, andel_slo_closing, bootstrap params) — both for the full period and a burn-in-excluded sensitivity slice. `05-HOLDOUT-RESULTAT.md` §6 contains an explicit, honestly-caveated before/after table against the live losing config (bankroll 1000→74.88kr live vs 1000→905kr holdout), with the caveat that the "before" side is not reconstructable (gitignored, empty history) clearly stated rather than fabricated. |
| 5 | CLV is reported per bet and in aggregate, and a Kelly-fraction sensitivity sweep (flat/quarter/half/full) shows ROI sensitivity to staking assumption | ✓ VERIFIED | `metrics.py::beregn_clv` computes vig-free closing-minus-bet-time probability delta per bet, with `None` (not silently dropped) when a closing snapshot is missing; `datakvalitet.bets_uten_clv` counter tracks this. Both real runs report `clv_snitt`/`antall_med_clv`/`andel_slo_closing`. `backtest.py::kjor_kelly_sweep` re-simulates stakes across flat/0.25/0.5/1.0 from one cached prediction pass (no re-run of the walk-forward loop) and is exercised by `test_kelly_sweep_har_fire_armer_i_laast_rekkefolge`, `test_ekte_sweep_gir_fire_armer_fra_en_predict_pass`. The frozen tuning run's `kelly_sweep.json` shows near-identical ROI but dramatically different max drawdown (7.8% flat vs 47-49% for any Kelly fraction) across the four arms — a genuine sensitivity finding, not a stub. |

**Score:** 5/5 truths verified

### BT Requirements Coverage

| Requirement | Description | Status | Evidence |
|---|---|---|---|
| BT-01 | Walk-forward chronological replay of full pipeline | ✓ SATISFIED | See truth #1. Both half-Kelly (`test_kelly_sweep_*`, `--kelly-fraksjon`) and the final flat-stake mode (`--flat`) are implemented and tested; the frozen final config uses flat staking, a documented evidence-driven outcome (see Context note below), not a missing feature. |
| BT-02 | All replay data filtered to "known as of date D" | ✓ SATISFIED | See truth #2. |
| BT-03 | Locked holdout checked exactly once, enforced by code | ✓ SATISFIED | See truth #3. |
| BT-04 | ROI/win rate/max drawdown on flagged-bet subset with bet count + CI on every headline number | ✓ SATISFIED | `metrics.py` computes `bootstrap_roi_ci` and `wilson_ci`; both real-run manifests attach `roi_ci_nedre/oevre` and `vinnrate_ci_nedre/oevre` to every headline metric, plus `antall_bets`. Confirmed hand-calculated-value tests pass (`test_bootstrap_roi_ci_kjente_verdier`). |
| BT-05 | Reproducible, versioned run manifest enabling before/after comparison | ✓ SATISFIED | See truth #4. `run_id` is content-derived (`test_manifest_inneholder_konfig_og_metrikker`), each run writes an immutable `backtests/<run_id>/` directory. |
| BT-06 | CLV per bet and in aggregate | ✓ SATISFIED | See truth #5. |
| BT-07 | Kelly-fraction sensitivity sweep (flat/quarter/half/full) | ✓ SATISFIED | See truth #5. |

**No orphaned requirements** — REQUIREMENTS.md's Phase 5 mapping (BT-01..BT-07) matches exactly what the 13 plan SUMMARYs claim and what the code delivers.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `backtest.py` | Walk-forward engine, holdout guard, manifest/ledger writer, Kelly sweep | ✓ VERIFIED | 1283 lines, substantive, wired into `08_kjor_backtest.py` CLI and `tests/test_backtest.py` (104 tests) |
| `metrics.py` | ROI/win-rate/drawdown/CI/CLV | ✓ VERIFIED | 388 lines, wired into `backtest.py`, covered by `tests/test_metrics.py` (23 tests) |
| `model.py` | as_of-aware train/calibrate with D-05-05 calibration floor | ✓ VERIFIED | 270 lines; `MIN_KALIBRERINGSKAMPER`/`MIN_TRENING_ETTER_KALIBRERING` floors present and enforced; `tests/test_model.py` (13 tests) |
| `odds.py` | Best-price-per-outcome for bet_time and closing, archived lookup | ✓ VERIFIED | 927 lines; used by both `backtest.py` and `verdi_deteksjon.py` (parity-tested) |
| `skadefilter.py` | As-of-aware injury filter | ✓ VERIFIED | 425 lines; `sesong_grenser_for_dato`/`sjekk_lag_helse_som_of` present, strict `<` boundary; `tests/test_skadefilter.py` (22 tests) |
| `08_kjor_backtest.py` | CLI entry point with ISO date validation, two-flag holdout path | ✓ VERIFIED | 589 lines; `--help` runs cleanly (exit 0); validates `--holdout`+`--bekreft-holdout`, rejects `--min-treningskamper` below the calibration floor and negative `--min-value-terskel` (post-review fixes, confirmed present in code) |
| `05-FROSNE-BESLUTNINGER.md` | Frozen tuning-slice decisions, pre-holdout | ✓ VERIFIED | Documents the full exploration trail including a real mid-phase calibration bug (D-05-05) discovered and fixed before freezing |
| `05-HOLDOUT-RESULTAT.md` | Holdout run result + before/after | ✓ VERIFIED | Documents an honest, statistically inconclusive holdout result (ROI CI straddles zero, n=19 well below the ~300-500 line noted in project research) and explicitly declines to draw an unsupported conclusion |
| `backtests/20260829-092351-3cc4a836/manifest.json` | Holdout run artifact | ✓ VERIFIED | Inspected directly on disk; matches documented values exactly |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `08_kjor_backtest.py` | `backtest.kjor_backtest` / `kjor_endelig_holdout_backtest` | direct import + CLI arg wiring | WIRED | Confirmed via grep and `--help` execution |
| `backtest.py` | `model.py` | `model.tren`/`del_for_trening` per retrain cadence | WIRED | `as_of=dato` passed at `backtest.py:314` |
| `backtest.py` | `skadefilter.py` | `sjekk_lag_helse_som_of` per candidate | WIRED | Confirmed in code |
| `backtest.py` | `odds.py` | archived best-price + closing snapshot lookup | WIRED | Confirmed, shared with live path (`verdi_deteksjon.py`), parity-tested |
| `backtest.py` | `metrics.py` | ROI/CI/CLV/drawdown computation feeding manifest | WIRED | `bygg_manifest` calls into `metrics.py` functions |
| `verdi_deteksjon.py` (live) | `backtest.py` (replay) | shared `strategy.py`/`features.py`/`odds.py` core | WIRED, tested for parity | `tests/test_parity.py::test_identisk_bet_beslutning_live_og_backtest` proves identical decisions with a discriminating-power self-check |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Full test suite passes | `./venv/bin/python3 -m pytest tests/ -q` | `349 passed, 45 warnings in 31.83s` | ✓ PASS (independently re-run, not just trusted from SUMMARY) |
| CLI runs and exposes documented flags | `./venv/bin/python3 08_kjor_backtest.py --help` | exit 0, full flag list incl. `--holdout`, `--bekreft-holdout`, `--flat`, `--sweep` | ✓ PASS |
| Post-review fix CR-01 present in code | `grep -n "min_treningskamper < _min_vindu" 08_kjor_backtest.py` | found at line 537, `parser.error` on violation | ✓ PASS |
| Post-review fix WR-01 present in code | `grep -n "min_value_terskel < 0" 08_kjor_backtest.py` | found at line 523, `parser.error` on violation | ✓ PASS |
| Holdout guard is structural | `grep -n "HoldoutLaastFeil\|_sikre_ikke_holdout" backtest.py` | raised in `kjor_backtest` pre-flight + per-iteration; only `kjor_endelig_holdout_backtest` passes `tillat_holdout=True` | ✓ PASS |
| Engine code unchanged since freeze except reviewed CLI validation fix | `git diff --name-only 33bbae1..HEAD -- config.py strategy.py backtest.py metrics.py model.py odds.py skadefilter.py features.py spillerlogg.py modell_utils.py 08_kjor_backtest.py` | only `08_kjor_backtest.py` (the CR-01/WR-01 validation-only fix, post-holdout) | ✓ PASS |
| Working tree clean, no uncommitted engine changes | `git status --porcelain` | only `.planning/config.json` modified (unrelated) | ✓ PASS |

### Anti-Patterns Found

None blocking. The 05-REVIEW.md code review (run independently, same day) found one CRITICAL (CR-01: `--min-treningskamper` could silently defeat the D-05-05 calibration floor) and one WARNING (WR-01: no bounds check on `--min-value-terskel`) — **both were fixed in commit `8583c6b`, verified present in code above, and covered by new regression tests** (confirmed in the full 349-test run). Two lower-severity warnings (WR-02: burn-in window computed from ledger-present months rather than calendar months when early coverage is thin; WR-03: `klargjor_backtestdata` reads the features CSV twice) were explicitly deferred as documented follow-up, correctly assessed as non-blocking (they don't affect the completed holdout run's already-frozen defaults) and do not touch the Phase 5 goal's core deliverable (holdout enforcement, leakage prevention, CLV, sweep).

No `TBD`/`FIXME`/`XXX` debt markers found in the reviewed production files (`backtest.py`, `metrics.py`, `model.py`, `odds.py`, `skadefilter.py`, `08_kjor_backtest.py`).

### Context Note: Half-Kelly and the Frozen Configuration

Per the verification brief, half-Kelly is not part of the final frozen/holdout configuration. This was checked and confirmed as a legitimate, well-documented evidence-driven outcome rather than an unimplemented feature: `strategy.py`/`backtest.py` fully implement half-Kelly staking (`--kelly-fraksjon 0.5` is a supported, tested CLI path), and the Kelly sweep in the frozen tuning run explicitly evaluated it alongside flat/quarter/full. The developer chose flat staking because it produced materially lower max drawdown (7.8% vs 47-49%) for statistically indistinguishable ROI on the same 52 bets — documented transparently in `05-FROSNE-BESLUTNINGER.md`. This is treated as satisfying BT-01/BT-07, not as a gap.

### Context Note: 05-VALIDATION.md Frontmatter Accuracy

`05-VALIDATION.md`'s frontmatter (`status: complete`, `nyquist_compliant: true`) was checked against the final phase state rather than trusted at face value. The document body itself was updated through plan 05-13 (its "Manual-Only Verifications" table has both BT-01/BT-04 and BT-03 rows marked "✅ utført 2026-08-29" with the correct final run_ids), and its final full-suite gate entry (344 passed, plan 05-11) predates the post-completion code-review fix that brought the suite to 349 — this is expected staleness (the validation doc's job ends at the plan-11 full-suite gate; the review and its 3 new tests happened later, on 2026-08-29, and are separately documented in `05-REVIEW.md`). The frontmatter label is accurate: the validation contract was in fact completed and its approval was genuinely obtained (documented AskUserQuestion responses cross-referenced in both `05-FROSNE-BESLUTNINGER.md` and `05-HOLDOUT-RESULTAT.md`). No discrepancy found that would invalidate the `complete`/`nyquist_compliant: true` claim.

### Human Verification Required

None. All must-haves are structurally verifiable in code and were independently re-executed (test suite, CLI, manifest inspection, git diff) rather than taken on SUMMARY.md's word.

### Gaps Summary

No gaps found. This phase delivers a genuinely functioning, structurally-safeguarded walk-forward backtest engine:

- The holdout guard is enforced in code (`HoldoutLaastFeil`), not just convention, and was actually spent exactly once with a documented triple-scan pre-check.
- As-of filtering for features, odds, and injury status is implemented with explicit strict-inequality boundaries and is covered by dedicated leakage-regression tests, including a test that proves the parity assertion itself is capable of failing (not vacuous).
- Two real runs (tuning + holdout) produced genuine manifests/ledgers on disk with real numbers — including an honestly negative/inconclusive holdout result (ROI -25.0%, CI straddling zero, n=19 bets, well below the project's own ~300-500 bet threshold for statistical significance noted in PITFALLS.md). The phase does NOT claim proven positive ROI — it correctly reports "Ikke avgjort" (undecided) against the Core Value gate, which is the honest and expected outcome of a properly-run holdout on a small sample, not a failure of the engine.
- A same-day independent code review found and the team fixed two real defects (CR-01, WR-01) before this verification; both fixes are confirmed present in code and covered by new tests. Two remaining lower-severity warnings are correctly non-blocking and documented as deferred follow-up.
- Half-Kelly staking exists and is tested; the frozen final configuration uses flat staking for a documented, evidence-based reason (dramatically lower drawdown for equivalent ROI on a small sample) — this does not constitute an unmet requirement.

The phase goal — "the full pipeline can be replayed chronologically... producing reproducible, leakage-safe ROI/drawdown/CLV evidence gated by a locked holdout" — is achieved. Whether the resulting evidence itself shows a positive-ROI strategy is a separate, honestly-answered question ("Ikike avgjort") that the roadmap correctly does not require this phase to answer affirmatively — Phase 5's job was to build the trustworthy measurement instrument, not to guarantee what it measures.

---

_Verified: 2026-08-29T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
