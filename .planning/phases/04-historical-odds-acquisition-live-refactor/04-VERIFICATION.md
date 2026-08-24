---
phase: 04-historical-odds-acquisition-live-refactor
verified: 2026-08-24T15:03:26Z
status: passed
score: 8/8 must-haves verified
overrides_applied: 0
---

# Phase 4: Historical Odds Acquisition & Live Refactor Verification Report

**Phase Goal:** Historical odds needed for backtesting are fetched once and archived permanently so further backtest iteration costs no additional API credits, and the live bot runs on the exact same shared core the backtest will use.
**Verified:** 2026-08-24T15:03:26Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

Truths merged from ROADMAP.md Success Criteria (Step 2a) and the 9 plans' `must_haves.truths` (Step 2b/2c). All were checked directly against the codebase and running artifacts, not against SUMMARY.md claims.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Historical odds fetched via sport-wide historical endpoint, one call per unique game date, persisted permanently in SQLite | ✓ VERIFIED | `odds.py::hent_historisk_odds_snapshot` calls `v4/historical/sports/{sport}/odds` (grepped, matches `x-requests-last` credit accounting). `odds_arkiv.db` queried directly: 480 distinct `kamp_dato` for `bet_time`, 480 for `closing`, 93,522 + 93,854 rows. |
| 2 | Re-running the fetch for an already-archived date consumes zero additional API credits | ✓ VERIFIED | Independently executed `venv/bin/python3 07_hent_historisk_odds.py --snapshot-type bet_time --maks-kreditt 1000 --utfor --fra 2023-01-15 --til 2023-01-16` (real `--utfor` mode, not dry-run) against the live archive. Output: "allerede arkivert - hopper over (gratis)" x2, `kreditt_brukt: 0`, exit 0. `kreditt_logg` row count and last row unchanged before/after (2203 rows, same last id). Also covered by `tests/test_odds.py::test_er_allerede_arkivert_hindrer_dobbelt_kall` (mocked HTTP, `mock_get.call_count == 0`). |
| 3 | The SQLite archive can reconstruct "odds as known on date D" for any archived date, independent of the live API | ✓ VERIFIED | `04-ARKIV-RAPPORT.md` section 7 documents a reconstruction query for 2024-01-15 read 100% from disk; independently re-ran the underlying query pattern via SQL — 278 rows for that date share one `snapshot_timestamp`, no network access required. |
| 4 | `06_bot.py` calls into the shared core directly instead of invoking `04_value_detector.py`/`05_skadefilter.py` as subprocesses | ✓ VERIFIED | `grep -n "subprocess\|python3.10\|PYTHONPATH" 06_bot.py` → zero matches. `06_bot.py` imports `odds`, `skadefilter`, `verdi_deteksjon`, `teams.finn_lag`, `config.*`, `strategy.*` directly. `kjør_pipeline()` calls `verdi_deteksjon.finn_value_bets(...)` and `skadefilter.filtrer_bets_for_skader(...)` in-process. |
| 5 | A failure inside the value pipeline degrades to "no value bets today" instead of crashing the bot | ✓ VERIFIED | `06_bot.py:228` — `except (Exception, SystemExit) as e:` crash barrier around `kjør_pipeline`'s body (comment explains bare `except Exception` would not catch `SystemExit`, which `sys.exit(1)` in the shared modules can raise). `tests/test_bot.py::test_pipeline_feil_degraderer_grasiost` exists and passes. |
| 6 | Post-tipoff-snapshot data-integrity bug in `parse_snapshot_til_rader` (closing lines taken after commence_time) is fixed and enforced | ✓ VERIFIED | Code at `odds.py:496`: `if snapshot_type == "closing" and _parse_iso(snapshot_timestamp) >= _parse_iso(kamp["commence_time"]): continue`. Five dedicated tests (`test_closing_snapshot_etter_avspark_droppes_helt`, `test_closing_snapshot_nøyaktig_ved_avspark_droppes_ogsaa`, `test_bet_time_snapshot_etter_avspark_arkiveres_fortsatt`, `test_closing_snapshot_foer_avspark_arkiveres_normalt`) pass. Independently queried `odds_arkiv.db`: `SELECT COUNT(*) FROM odds_arkiv WHERE snapshot_type='closing' AND snapshot_timestamp > commence_time` → 0 rows. |
| 7 | Importing the injury filter / value detector no longer triggers any network call, model load, or CSV write at import time | ✓ VERIFIED | `skadefilter.py`/`verdi_deteksjon.py` module docstrings and code confirm all `nba_api`/pickle/CSV work moved inside functions. `tests/test_skadefilter.py::test_import_skadefilter_gjor_ingen_nettverkskall` and `tests/test_verdi_deteksjon.py::test_import_verdi_deteksjon_gjor_ingen_nettverkskall` reload the modules with the network entry point patched to raise on call — both pass. |
| 8 | Full archive coverage (480/480 dates, both snapshot types) with any gaps named explicitly, not silently missing | ✓ VERIFIED | `04-ARKIV-RAPPORT.md` names exactly 2 games (Suns@Kings 2023-03-11, Mavericks@Blazers 2025-01-09) with a missing `closing` line, explaining root cause (post-tipoff snapshot, correctly dropped by the truth-6 fix) — no date-level gaps. Independently confirmed via direct SQL query (see truth 1). |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `odds.py` | SQLite archive layer, timestamp/parsing logic, HTTP client, backfill driver | ✓ VERIFIED | 743 lines. Contains `apne_arkiv`, `er_allerede_arkivert`, `arkiver_odds_rader`, `logg_kreditt`, `parse_snapshot_til_rader`, `kamp_dato_fra_commence`, `morgen_tidspunkt`, `hent_live_odds`, `hent_historisk_odds_snapshot`, `hent_historiske_events`, `_utfor_kall`, `hent_unike_kampdatoer`, `kjor_backfill`. |
| `07_hent_historisk_odds.py` | Resumable, dry-run-by-default CLI for the backfill | ✓ VERIFIED | Exists, `if __name__ == "__main__":` guard, `--utfor`/`--maks-kreditt` args confirmed via live execution. |
| `skadefilter.py` | Importable injury-filter core, zero import-time network | ✓ VERIFIED | 246 lines, `def filtrer_bets_for_skader` present, imports `teams.finn_lag_id` (shared resolver, no duplicate dict). |
| `05_skadefilter.py` | Thin CLI wrapper | ✓ VERIFIED | Exists, imports from `skadefilter`. |
| `verdi_deteksjon.py` | Importable value-detection core | ✓ VERIFIED | 227 lines, `def finn_value_bets` present, imports `odds.hent_live_odds`, `features.bygg_feature_rad`, `strategy.*`, `teams.finn_lag_id`. |
| `04_value_detector.py` | Thin CLI wrapper | ✓ VERIFIED | Exists (1879 bytes), thin wrapper around `verdi_deteksjon`. |
| `06_bot.py` | Direct-import orchestration, no subprocess/PYTHONPATH | ✓ VERIFIED | `kjør_pipeline()` present; no `subprocess`/`python3.10` references. |
| `odds_arkiv.db` | Permanent SQLite odds archive | ✓ VERIFIED | 67MB file, `odds_arkiv` + `kreditt_logg` tables, 480/480 dates both snapshot types, gitignored (`.gitignore:17`). |
| `04-ARKIV-RAPPORT.md` | Coverage/cost/gap report | ✓ VERIFIED | 151 lines, every number independently spot-checked against live SQL queries and matched exactly. |
| `tests/test_odds.py` | Archive, parsing, HTTP, backfill tests | ✓ VERIFIED | 57 test functions, all pass. |
| `tests/test_skadefilter.py`, `tests/test_verdi_deteksjon.py`, `tests/test_bot.py` | Extraction/degradation regression tests | ✓ VERIFIED | Present and passing. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `07_hent_historisk_odds.py` | `odds.kjor_backfill` | import + call in `__main__` guard | ✓ WIRED | Confirmed by live execution — real invocation reached `kjor_backfill` and printed its summary output. |
| `kjor_backfill` | `er_allerede_arkivert` | SELECT-before-fetch check before any `requests.get` | ✓ WIRED | Verified in code (`odds.py:644`) and by the zero-credit live re-run spot-check. |
| `06_bot.py` | `verdi_deteksjon.finn_value_bets` | direct in-process call | ✓ WIRED | `06_bot.py:212`. |
| `06_bot.py` | `skadefilter.filtrer_bets_for_skader` | direct in-process call | ✓ WIRED | `06_bot.py:223`. |
| `verdi_deteksjon.py` | `odds.hent_live_odds` | shared odds client | ✓ WIRED | Import present, live odds no longer fetched via inline HTTP in `04_value_detector.py`. |
| `verdi_deteksjon.py`/`skadefilter.py` | `teams.finn_lag_id` | shared team resolver | ✓ WIRED | Both modules import from `teams`, no duplicate lookup dict introduced. |
| `odds_arkiv.db` | `nba_features.csv GAME_DATE_HJEMME` | `kamp_dato` join key | ✓ WIRED | Cross-reference table in `04-ARKIV-RAPPORT.md` section 4 (3638/3638 bet_time, 3636/3638 closing with 2 named exceptions), independently plausible given direct DB query results. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Zero-credit re-run of an already-archived date, real (non-mocked) execution | `venv/bin/python3 07_hent_historisk_odds.py --snapshot-type bet_time --maks-kreditt 1000 --utfor --fra 2023-01-15 --til 2023-01-16` | `kreditt_brukt: 0`, exit 0, `kreditt_logg` unchanged (2203 rows before/after, same last row) | ✓ PASS |
| No subprocess/PYTHONPATH hack remains in `06_bot.py` | `grep -n "subprocess\|python3.10\|PYTHONPATH" 06_bot.py` | no matches | ✓ PASS |
| Post-tipoff closing-snapshot bug is fixed archive-wide | `SELECT COUNT(*) FROM odds_arkiv WHERE snapshot_type='closing' AND snapshot_timestamp > commence_time` | `0` | ✓ PASS |
| Full test suite passes | `venv/bin/python3 -m pytest tests/ -q` | `129 passed in 1.88s` | ✓ PASS |
| Archive coverage matches claimed 480/480 for both snapshot types | direct SQL against `odds_arkiv.db` | `bet_time: 480 dates`, `closing: 480 dates` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|--------------|-------------|--------|----------|
| ODDS-01 | 04-01, 04-03, 04-04, 04-05, 04-07, 04-09 | Historical odds fetched via sport-wide endpoint, archived permanently, zero-cost re-run | ✓ SATISFIED | Live zero-credit re-run spot-check, 480/480 date coverage confirmed by direct SQL, `04-ARKIV-RAPPORT.md` cross-checked. |
| ODDS-02 | 04-02, 04-04, 04-06, 04-08 | `06_bot.py` imports shared core directly, no subprocess | ✓ SATISFIED | grep confirms no subprocess/PYTHONPATH; `kjør_pipeline` calls `verdi_deteksjon`/`skadefilter` in-process; crash barrier present and tested. |

No orphaned requirements — REQUIREMENTS.md maps only ODDS-01 and ODDS-02 to Phase 4, and both appear in plan frontmatter `requirements:` fields.

### Anti-Patterns Found

None. Scanned `odds.py`, `skadefilter.py`, `verdi_deteksjon.py`, `06_bot.py`, `07_hent_historisk_odds.py`, `04_value_detector.py`, `05_skadefilter.py` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` and stub-language patterns — zero matches in all seven files.

### Human Verification Required

None. The two `checkpoint:human-verify` gates relevant to this phase's goal (04-04's `tenacity` package-legitimacy approval, and 04-08's real end-to-end daily-run approval covering the subprocess removal) were already executed and explicitly approved by the developer during plan execution (`"godkjent: tenacity"`, `"ja det er godkjent"` — recorded verbatim in `04-04-SUMMARY.md` and `04-08-SUMMARY.md`). 04-07's and 04-09's credit-ceiling/coverage checkpoints were likewise resolved with recorded developer decisions (`"godkjent: bet_time maks-kreditt=5500, closing maks-kreditt=13500"`). No `<human-check>` blocks were found deferred inside `auto`-type tasks across any of the 9 plans.

### Gaps Summary

No gaps. All roadmap Success Criteria and all plan-level must-haves were independently verified against the running codebase and live database, not just against SUMMARY.md narrative:

- The zero-additional-credit re-run claim (ODDS-01's core promise) was proven by actually executing the CLI in real (`--utfor`) mode against the live archive, not just by trusting the mocked unit test.
- The subprocess/PYTHONPATH removal (ODDS-02) was proven by direct grep of the current `06_bot.py` source.
- The post-tipoff closing-snapshot bug fix was proven both by test coverage and by a direct SQL integrity check against the full 93,854-row `closing` archive (0 violations).
- The full pytest suite (129 tests) passes with no skips or failures.

Two data-quality caveats are explicitly named in `04-ARKIV-RAPPORT.md` (2 games with no closing line; early-season eu-region bookmaker thinness) and are correctly scoped as known limitations for Phase 5, not phase-4 gaps — the phase's own success criteria require gaps to be *named*, not eliminated, and they are.

---

*Verified: 2026-08-24T15:03:26Z*
*Verifier: Claude (gsd-verifier)*
