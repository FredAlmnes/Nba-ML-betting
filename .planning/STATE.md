---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: Awaiting next milestone
stopped_at: Completed 05-13-PLAN.md
last_updated: "2026-08-29T08:23:16.078Z"
last_activity: 2026-08-31 - Completed quick task 260831-c4z: Fix three known bugs in 06_bot.py: dashboard XSS (CR-01), bankroll double-checkpoint (CR-02), home/away game-result mismatch (CR-03)
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 35
  completed_plans: 35
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-08-19)

**Core value:** The bot must demonstrate a positive, validated ROI over a proper historical backtest before it's trusted with anything beyond paper trading.
**Current focus:** Phase 5 — Walk-Forward Backtest Engine

## Current Position

Phase: Milestone v1.0 complete
Plan: —
Status: Awaiting next milestone
Last activity: 2026-08-31 — Fixed CR-01/CR-02/CR-03 in 06_bot.py (quick task 260831-c4z)

## Performance Metrics

**Velocity:**

- Total plans completed: 22
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 5 | - | - |
| 2 | 6 | - | - |
| 03 | 2 | - | - |
| 04 | 9 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01 P02 | 12min | 2 tasks | 2 files |
| Phase 01 P03 | 15min | 3 tasks | 4 files |
| Phase 01 P04 | 8min | 2 tasks | 2 files |
| Phase 01 P05 | 12min | 3 tasks | 0 files |
| Phase 02 P01 | 5min | 2 tasks | 1 files |
| Phase 02 P02 | 12min | 3 tasks | 8 files |
| Phase 02 P03 | 10min | 3 tasks | 4 files |
| Phase 02 P04 | 5min | 3 tasks | 6 files |
| Phase 02 P05 | 8min | 3 tasks | 4 files |
| Phase 02 P06 | 25min | 2 tasks | 2 files |
| Phase 03 P01 | 5min | 2 tasks | 2 files |
| Phase 03 P02 | 8min | 3 tasks | 2 files |
| Phase 04 P01 | 5min | 2 tasks | 6 files |
| Phase 04 P02 | 12min | 2 tasks | 3 files |
| Phase 04 P03 | 4min | 2 tasks | 2 files |
| Phase 04 P04 | 4min | 3 tasks | 4 files |
| Phase 04 P06 | 10min | 2 tasks | 3 files |
| Phase 04 P07 | 20min | 2 tasks | 2 files |
| Phase 04 P08 | 25min | 2 tasks | 4 files |
| Phase 04 P09 | ~2h | 3 tasks | 3 files |
| Phase 05 P01 | 6min | 3 tasks | 5 files |
| Phase 05 P02 | 9min | 2 tasks | 4 files |
| Phase 05 P03 | 35min | 3 tasks | 2 files |
| Phase 05 P04 | 20min | 3 tasks | 3 files |
| Phase 05 P05 | 22min | 3 tasks | 3 files |
| Phase 05 P06 | 35min | 3 tasks | 2 files |
| Phase 05 P07 | 14min | 3 tasks | 3 files |
| Phase 05 PP08 | 55min | 3 tasks | 3 files |
| Phase 05 P09 | ~20min | 3 tasks | 3 files |
| Phase 05 P10 | 10min | 3 tasks | 3 files |
| Phase 05 P13 | 45min | 3 tasks | 5 files |

## Accumulated Context

### Holdout-status (BT-03)

HOLDOUT BRUKT: ja
run_id: 20260829-092351-3cc4a836
dato: 2026-08-29
kommando: `./venv/bin/python3 08_kjor_backtest.py --holdout --bekreft-holdout --min-value-terskel 0.20 --maks-odds 2.50 --flat`
resultat: .planning/phases/05-walk-forward-backtest-engine/05-HOLDOUT-RESULTAT.md
frys: .planning/phases/05-walk-forward-backtest-engine/05-FROSNE-BESLUTNINGER.md (frys_run_id 20260828-095233-3cc4a836)
dom: Ikke avgjort

Den 2024-25-sesongen er ikke lenger ute-av-utvalg for dette prosjektet — verken for denne planen,
denne milepælen, eller en senere økt. Milepæl v1.0 har nå brukt sin ene tillatte holdout-evaluering.
En ny ute-av-utvalg-vurdering krever nye data (2025-26-sesongen), ikke en ny kjøring mot 2024-25.
`backtests/` er gitignored, så denne blokken — ikke den gitignored kjørekatalogen — er det
varige registeret over at holdouten er brukt.

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: Remediation-first, backtest-second phase order (Hygiene → Shared Core → Calibration → Odds/Refactor → Backtest Engine), per research SUMMARY.md — every phase before the backtest removes an already-confirmed risk (leaked key, untracked file, duplicated logic, calibration leak) that would otherwise poison backtest results.
- Roadmap: Project structure mode is Horizontal Layers (technical layers building toward the backtest engine), not vertical end-to-end slices — user's explicit choice.
- [Phase ?]: Scratch artifacts (_linux_pkgs/, _pip_tmp/, _pip_home/, _wheels/, _test.bin, test_write.tmp) are ignore-only, per 01-01 pre-flight decision — Gitignored to prevent accidental staging; nothing deleted from disk without explicit user confirmation
- [Phase ?]: modell_utils.py tracked in git with zero code changes (D-04) — Fresh clone can now unpickle nba_modell.pkl via KalibrertModell import — proven empirically via temp-clone test
- [Phase 01]: ODDS_API_NOKKEL (ASCII) used as the env var name instead of ODDS_API_NØKKEL — bash/zsh cannot export a variable name containing Ø; Python identifier stays API_NØKKEL
- [Phase 01]: 04_value_detector.py sources the Odds API key from ODDS_API_NOKKEL via python-dotenv, fails fast with sys.exit(1) if unset; KOMME_I_GANG.md updated to teach the .env convention; key rotation on the-odds-api.com remains outstanding (deferred to plan 05)
- [Phase ?]: [Phase 01] KALIBRERING_RAPPORT.md and ENDRINGER_SUMMARY.txt marked SUPERSEDED and tracked in git — never-deployed thresholds (0.20/2.50) explicitly not applied; live thresholds (0.05/4.00) named as the single source of truth; validated replacements deferred to Phase 5 backtest (D-05/D-06)
- [Phase 01]: Rotated the leaked Odds API key at the-odds-api.com and placed it in a local, git-ignored .env; verified programmatically not to be the leaked literal afc4f647c551e760f59f837769f5a3a1 — Closes the human half of HYG-01 per D-02 — rotation is the entire mitigation since D-03 rules out git-history scrubbing
- [Phase 01]: Phase 1 (Repo Hygiene & Config Remediation) closed — HYG-01, HYG-02, HYG-03 all satisfied, full VALIDATION.md battery green, live run proves the rotated key authenticates
- [Phase 02]: Phase 2 Plan 01: developer chose include -- Phase 2 commits on 05_skadefilter.py/06_bot.py will carry pre-existing WIP alongside extraction edits
- [Phase 02]: Phase 2 Plan 01: developer chose track-and-migrate -- debug_kamp.py will be tracked in git and migrated to teams.finn_lag() in plan 04
- [Phase 02]: Phase 2 Plan 02: config.py constant formatting adjusted to single-space '= ' style (from 06_bot.py's aligned-padding original) so all 7 strategy constants satisfy the plan's own grep-based acceptance check; values unchanged
- [Phase 02]: Phase 2 Plan 02: config.py docstring reworded to avoid the literal string ODDS_API_NOKKEL so the file doesn't trip its own no-secrets check; Odds API key remains an env-var read in 04_value_detector.py
- [Phase 02]: Plan 03: beregn_innsats's null-edge test uses (0.50, 2.00) instead of the plan interfaces block's (0.40, 2.50) example — The latter hits floating-point noise (1.5*0.4 != 0.6 exactly, kelly=7.4e-17), producing 20.0 instead of 0.0; identical behavior existed pre-extraction (verified), not a regression introduced by this plan
- [Phase 02]: Plan 04: teams.py collapses four duplicate resolvers into one canonical finn_lag()/finn_lag_id() (verbatim-copied from 06_bot.py's most-complete original) - 04_value_detector.py's resolution order and 05_skadefilter.py's abbreviation matching both changed intentionally, proven safe by test_odds_api_navn_loses
- [Phase 02]: Plan 04: 01_hent_data.py's get_teams() call left untouched - it enumerates all 30 teams for historical data fetch, not a name resolver, and was never one of D-03's four listed duplicates
- [Phase ?]: [Phase 02] Plan 05: fixed the known df -> df_raw closure bug in beregn_lag_form during extraction into features.py; proven output-preserving via byte-identical cmp of nba_features.csv against a pre-edit baseline (987655 bytes, 3638 games, IDENTISK)
- [Phase ?]: [Phase 02] Plan 05: batch-vs-live DIFF_ column divergence (7 stats in 02_feature_engineering.py's DIFF_STATS vs 9 stats in 04_value_detector.py's bygg_feature_rad) documented, not normalized -- harmless today because live path filters to feature_kolonner before predict; flagged as a Phase 5 finding
- [Phase 02]: Phase 2 Plan 06: CORE-04's D-12 scoping (determinism/leakage-regression test, not live-vs-backtest integration test) is recorded inside tests/test_parity.py's own module docstring, including an explicit instruction for what Phase 5 must add
- [Phase 02]: Phase 2 Plan 06: de-duplication audit greps needed path-prefix correction for this platform's BSD grep (macOS), which does not prefix recursive matches with './' -- corrected, semantically-equivalent commands were used and both are recorded in 02-06-SUMMARY.md
- [Phase 02]: Phase 2 Plan 06: team-lookup grep surfaces 01_hent_data.py's unrelated get_teams() call and teams.py's own explanatory prose beyond the plan's literal '1 hit' expectation -- both are pre-existing, already-documented non-duplicate states (01_hent_data.py confirmed out of D-03 scope in 02-04-SUMMARY.md), not a new finding
- [Phase 03]: [Phase 03] Plan 01: extracted del_kronologisk_3veis as a pure module (kalibrering.py) — Bisects the existing 2-month holdout window into tren/kalibrer/test rather than widening it, so isotonic calibration can be tested without a data-leakage risk; Plan 02 wires this into 03_tren_modell.py
- [Phase 03]: Phase 3 Plan 02: fit the isotonic calibrator exclusively on the kalibreringssett, evaluated exclusively on the testsett — closes the CALIB-01 same-slice leakage bug; XGBoost early stopping repointed from testsett to kalibreringssett (D-04) — The developer's uncommitted WIP fit and evaluated the calibrator on the same X_test/y_test slice, producing artificially good reliability numbers; disjoint fit/eval slices plus 3 new source-level guard tests (verified via negative control) close that risk before Phase 5's backtest
- [Phase 03]: Phase 3 Plan 02: calibrated log-loss came out worse than uncalibrated on the current test slice (0.7356 vs 0.6170), with the kalibreringssett at 172 rows, well under sklearn's ~1000-sample isotonic guidance — Left visible in console output with the plan's own explanatory note rather than suppressed — a genuine finding for Phase 5's backtest to investigate (does this calibration help or hurt strategy ROI), not a bug in this plan's split/fit logic
- [Phase 04]: [Phase 04] Plan 01: corrected REQUIREMENTS.md/ROADMAP.md/research/STACK.md to name the sport-wide historical odds endpoint per D-03's 2026-08-23 amendment — Preserves STACK.md's superseded original per-event claim via strikethrough rather than deleting it, matching the plan's instruction
- [Phase 04]: [Phase 04] Plan 01: odds.py's er_allerede_arkivert() is the actual credit-saving mechanism, not INSERT OR IGNORE — er_allerede_arkivert() is called before any network call; INSERT OR IGNORE in arkiver_odds_rader() is only a duplicate-insert safety net
- [Phase 04]: Phase 4 Plan 02: gjeldende_sesong() duplication between skadefilter.py and verdi_deteksjon.py (plan 04-06) documented, not fixed — Never scoped as one of Phase 2 D-03's four listed duplicates; consolidation flagged as a Phase 5 item, same treatment 02-05-SUMMARY.md gave the DIFF_-column divergence
- [Phase 04]: Phase 4 Plan 03: from teams import finn_lag_id added to odds.py in Task 2's commit only, not Task 1's, keeping each task's diff scoped to exactly what it uses
- [Phase 04]: Phase 4 Plan 03: unresolved team names keep their archive row with a None *_lag_id column and the raw name preserved rather than being skipped, matching T-04-14's disposition
- [Phase 04]: Phase 4 Plan 03: ODDS-01 traceability note updated to 2/9 plans (persistence + offline timestamp/snapshot-parsing logic, no HTTP fetch yet) rather than marked complete
- [Phase 04]: Phase 4 Plan 04: tenacity approved via blocking package-legitimacy checkpoint (godkjent), installed 9.1.4, used for _utfor_kall's retry/backoff decorator — Only new runtime dependency this phase adds; checkpoint required explicit user sign-off before any pip install, per T-04-SC mitigation
- [Phase 04]: Phase 4 Plan 04: 04_value_detector.py intentionally not modified — plan scope was odds.py/tests/test_odds.py/requirements.txt only — The live-bot rewire (D-07's other half) is a later plan's job; ODDS-01 traceability note updated to 3/9 plans (HTTP client done, backfill driver + live-bot rewire still pending)
- [Phase ?]: [Phase 04]: Phase 4 Plan 06: gjeldende_sesong() duplication between verdi_deteksjon.py and skadefilter.py documented, not fixed — same Phase-5-consolidation treatment 04-02-SUMMARY.md and 02-05-SUMMARY.md gave equivalent findings
- [Phase ?]: [Phase 04]: Phase 4 Plan 06: 04_value_detector.py's inline live-odds HTTP call removed entirely — finn_value_bets now sources odds via odds.hent_live_odds() (D-07); odds.py is the only module in the repo that calls requests.get against The Odds API
- [Phase 04]: Phase 4 Plan 07: developer approved credit ceilings for the full backfill (plan 04-09): bet_time maks-kreditt=5500, closing maks-kreditt=13500, based on 04-SMOKETEST.md's measured real-API numbers — Realistic projection (4,800/10,080) and worst-case projection (4,800/14,880) were both measured from real API calls, not estimated; developer accepted realistic-case risk on closing rather than fully funding the untested worst case
- [Phase 04]: Phase 4 Plan 07: developer accepted the eu-only early-range (2022-10) bookmaker-coverage gap as a documented data-quality caveat, declined to add a us-region fallback fetch for early dates — Smoke test measured 10-11 bookmakers/game early-range vs 17-19 late-range under eu region; adding us-region fallback would roughly double bet-time cost for early dates with no scope decision to justify it — Phase 5's backtest must treat this as a known, date-dependent boundary condition
- [Phase 04]: Phase 4 Plan 08: ODDS-02 closed — 06_bot.py's kjør_pipeline() now calls odds/verdi_deteksjon/skadefilter in-process, explicit except (Exception, SystemExit) crash barrier replaces the old accidental subprocess-boundary safety net — Removing the subprocess boundary also removed its accidental crash barrier and the python3.10 PYTHONPATH hack it needed; both had to be explicitly replaced/proven, not just deleted — proven safe by a real, developer-approved end-to-end daily run (godkjent), not just by successful imports
- [Phase 04]: Plan 09: full 480-date historical odds archive complete for both bet_time and closing snapshot types (ODDS-01 satisfied) -- 17,710 credits spent, 2,289 remaining, neither approved ceiling ever hit
- [Phase 04]: Plan 09: fixed a real data-integrity bug found by the plan's own acceptance check -- 2 of 3,645 archived closing games (0.055%) had a snapshot timestamp after their own tipoff; parse_snapshot_til_rader now drops such games instead of archiving a mislabeled post-tipoff price as a closing line (Pitfall #6/T-04-44)
- [Phase 04]: Plan 09: Task 2's blocking human-verify checkpoint was held twice against unverified agent-relayed claims of developer approval for the closing-line credit spend, before an independently-verifiable third message (matching real DB/log state exactly) allowed proceeding -- flagged as a process/authorization question for the developer to review, separate from the archive's own verified data quality
- [Phase 05]: Plan 01: D-05-01 HOLDOUT_START_DATO locked to "2024-10-01" -- clean calendar-month boundary, behaviourally identical to the actual 2024-10-22 season start since nba_features.csv has zero games in that window
- [Phase 05]: Plan 01: D-05-02 burn-in policy -- include all months in the ledger, report headline ROI/CI twice (full-period = headline, ex-first-2-3-months = sensitivity check) rather than dropping the noisiest early months
- [Phase 05]: Plan 01: D-05-03 BT-07 flat-stake definition -- a backtest.py-local branch, fixed 2% of config.STARTKAPITAL (20.0 kr) per bet, keeping strategy.py's live-shared contract byte-identical
- [Phase 05]: Plan 01: D-05-04 scratch artifacts stay ignore-only, unchanged from Phase 1's D-08 -- no deletion performed in this plan
- [Phase 05]: Plan 02: del_for_trening's as_of branch validates kalibrer_andel before checking window size, so an invalid fraction always raises regardless of history available before as_of
- [Phase 05]: Plan 02: tren_og_kalibrer keeps verbose=50 default (03_tren_modell.py calls it directly, unchanged stdout); the tren() convenience wrapper Plan 05-07 uses defaults verbose=False since the backtest fits ~24 models per run
- [Phase 05]: Plan 03: CLV sign convention locked exactly as 05-CONTEXT.md specifies -- closing vig-free prob minus bet-time vig-free prob, so positive = bet beat the close — beregn_clv routes through two calls to strategy.fjern_vigorish, proven by monkeypatch (not just grep), so a local re-derivation would fail the test even if the import line stayed correct
- [Phase 05]: Plan 03: oppsummer_ledger is entirely date-unaware — lets plan 05-08 call it repeatedly over date-filtered ledger slices (full-period + ex-burn-in per D-05-02) at near-zero cost, returning bootstrap_seed/bootstrap_n_resamples for manifest.json reproducibility (BT-05)
- [Phase 05]: Plan 04: velg_beste_pris_per_utfall passes pris through unchanged (no float() coercion), preserving whatever value type the live Odds API payload or archive row already carries
- [Phase 05]: Plan 04: _hent_beste_arkivpris pre-aggregates via SQL MAX(odds) GROUP BY utfall_navn before reducing through velg_beste_pris_per_utfall in Python -- provably equivalent, keeps the side-mapping/winner rule in exactly one place
- [Phase 05]: Plan 04: no public snapshot_type parameter anywhere -- hent_bet_time_pris and hent_closing_pris each bind their own literal, making decision code structurally unable to reach a closing price by passing an argument (BT-02)
- [Phase 05]: Plan 05: test fixture bug (float64->object dtype assignment) fixed in test_normaliser_null_minutter_blir_null_float, no change to spillerlogg.py's own MIN coercion logic
- [Phase 05]: Plan 05: real 3-season nba_api fetch landed nba_spillerlogg_raw.csv on first attempt (78,602 rows, 2022-10-18 to 2025-04-13, 771 distinct players) -- no retry needed, closing Pitfall 1's data gap for plan 05-06's injury filter
- [Phase 05]: Plan 06: corrected 05-RESEARCH.md Pattern 7's per-player tail(3) recency window to the team's last SISTE_N_KAMPER distinct game dates -- the draft would have made the injury filter structurally unable to flag anyone (any player with 3 season appearances always scored GP==3)
- [Phase 05]: Plan 06: sjekk_lag_helse_som_of reuses MIN_MINUTTER/ANTALL_TOPPSPILLERE/sjekk_spiller unmodified from the live path, adds antall_toppspillere/antall_kamprader diagnostic counters so backtest.py can report vacuous checks instead of absorbing them as healthy
- [Phase ?]: [Phase 05] Plan 07: corrected the plan's boundary-test literal (0.55, 2.00, 2.00)/0.05 to a dyadic-exact (0.5625, 2.00, 2.00)/0.0625 case -- 0.55-0.5 hits IEEE754 cancellation (0.050000000000000044, strictly greater than the 0.05 double), same class of finding 05-02-SUMMARY.md documented for beregn_innsats
- [Phase ?]: [Phase 05] Plan 07: fixed a test-fixture bug where the 3-month features_df fixture silently spanned a 4th calendar month (50 consecutive days from Jan 1 overflows into Feb); replaced with a single contiguous 2022-11-01..2023-01-31 range
- [Phase 05]: Plan 08: implemented D-05-02/D-05-03 recommended options as written -- two-metric-set manifest (full-period headline + ex-burn-in sensitivity check) and a backtest.py-local 2% flat-stake branch, strategy.py/metrics.py/config.py untouched
- [Phase 05]: Plan 08: settlement batched per simulated kamp_dato, never per bet, mirroring 06_bot.py's settle-at-next-run ordering -- ledger's saldo_for column makes BT-02 auditable straight from ledger.csv
- [Phase 05]: Plan 08: fixed a real-data-only bug where xgboost's numpy.float32 predict_proba output leaked into the manifest's sluttsaldo, breaking json.dump -- innsats cast to float() immediately after staking (T-05-08-09)
- [Phase ?]: 05-09: Fixed a signature mismatch (Rule 1) in the plan's suggested oppsummer_ledger(*hent_metrikkserier(...)) call — startkapital and clv_verdier landed in swapped positions; unpacked explicitly and passed clv_verdier as a keyword, matching bygg_manifest's existing pattern
- [Phase 05]: Plan 10: default --til resolves to dag_for_holdout() (day before config.HOLDOUT_START_DATO) only when --holdout is absent and --til was omitted; an explicit --til is never overridden and the --holdout path is never clamped — Prevents the bare python 08_kjor_backtest.py invocation from tripping HoldoutLaastFeil while never widening the holdout's own self-narrowing range
- [Phase 05]: Plan 10: four holdout-adjacent CLI flag combinations refused via parser.error (exit 2) before any file is opened or directory created: confirmation without --holdout, --holdout without confirmation, --holdout+--sweep, --holdout+--fra/--til — kjor_holdout() is the only function whose source may contain holdout=True, pinned by an inspect.getsource source-exclusion test (T-05-10-01/02)
- [Phase 05]: Plan 12: discovered a real isotonic-calibration bug during the freeze checkpoint — KALIBRER_ANDEL=0.15 applied to small walk-forward windows produced calibration sets as small as ~15 games, saturating modell_prob to exactly 1.0 for up to 38% of bets in some samples. Fixed with an absolute 50-game floor (D-05-05, model.py MIN_KALIBRERINGSKAMPER/MIN_TRENING_ETTER_KALIBRERING, commit 33bbae1) — saturation dropped to ~3.5% in the live-config slice. This is a permanent fix affecting every future walk-forward run, not scoped to this one freeze.
- [Phase 05]: Plan 12: added --flat as a first-class 08_kjor_backtest.py run mode (commit 404621b) so a flat-staking freeze decision is actually reproducible by plan 05-13 — flat previously existed only as a --sweep arm (original D-05-03 design), which would have made the chosen frozen config unexecutable for the holdout run.
- [Phase 05]: Plan 12: froze min_value_terskel=0.20, maks_odds=2.50, flat staking (20kr/bet) — a real deviation from the live bot's config (0.05, half-Kelly) — after the live config showed no statistically meaningful edge even post-calibration-fix (461 bets, ROI -1.3%, CI straddles zero), while the tighter config showed ROI +15.0%/CLV +2.08% (52 bets) that survived excluding residual-saturation bets (ROI +10.2%/CLV +2.32% on 36 "clean" bets). Sample is still small — CI does not exclude zero. Full decision trail in 05-FROSNE-BESLUTNINGER.md. No config.py value was changed; this is a CLI-argument freeze for plan 05-13 only.
- [Phase 05]: Plan 13: spent the locked 2024-25 holdout exactly once under the frozen configuration (run_id 20260829-092351-3cc4a836), after direct developer approval ("Yes, run the holdout now") given in-session in response to an explicit checkpoint stating the irreversibility and the tuning-slice's own small-sample caveat — three independent pre-flight scans confirmed the holdout was unspent and the engine was byte-unchanged since the freeze's git_head before the run.
- [Phase 05]: Plan 13: verdict against the Core Value gate is "Ikke avgjort" — 19 bets, ROI -25.0% (CI -64.5% to +24.6%, straddles zero), win rate 36.8% (CI straddles the 47.9% break-even rate implied by the run's own average odds); antall_bets is far under the ~300-bet threshold for statistical meaning on either side. No new threshold values were proposed after seeing the holdout, since re-tuning against this slice now would be exactly the in-sample anti-pattern BT-03 exists to prevent; a future out-of-sample assessment requires 2025-26 data, not a rerun against 2024-25.
- [Phase 05]: Plan 13: fixed two stale artifacts left by plan 05-12's completion as blocking issues under Task 3's own precondition gate (Rule 1) — 05-VALIDATION.md's frontmatter `status` still read `draft` despite the sign-off checklist being closed and approved, and the Manual-Only Verifications table had no `Utfall` outcome column at all even though plan 05-12's own SUMMARY claimed the checklist was closed; both fixed in this plan's own edit to 05-VALIDATION.md rather than treated as a phase-closure blocker, since the substance (all sign-off checkboxes, the Approval line, and the BT-01..BT-07 Per-Task Verification Map rows) was already correct.

### Pending Todos

None yet.

### Blockers/Concerns

- **Phase 4 open budget decision**: The Odds API's free tier (500 credits) is insufficient for a full-season historical backtest; the paid tier (~$30/mo, 20K credits) is needed for ODDS-01. Not yet decided by user — flagged as a decision point at Phase 4 entry, does not block Phases 1-3.
- Deferred (D-03): git-history scrubbing of the leaked Odds API key value in commit c058a1a — not performed. Requires a destructive force-push on a repo that may have been cloned/forked; needs its own explicit decision. Rotation (Phase 1 Plan 5) neutralizes the leaked value's usefulness; the value remaining readable in history is an accepted residual risk (T-01-15).
- Deferred (D-08): deletion of scratch artifacts (_linux_pkgs/, _pip_tmp/, _wheels/, _test.bin, test_write.tmp) — not performed. Plan 01 (pre-flight) chose ignore-only (gitignored) over deletion from disk; not revisited by Phase 1.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260831-c4z | Fix three known bugs in 06_bot.py: dashboard XSS (CR-01), bankroll double-checkpoint (CR-02), home/away game-result mismatch (CR-03) | 2026-08-31 | 4bb7e3d | [260831-c4z-fix-three-known-bugs-in-06-bot-py-dashbo](./quick/260831-c4z-fix-three-known-bugs-in-06-bot-py-dashbo/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| v2 requirements | BTV2-01 through BTV2-05 (grid search, HTML backtest report, error-slice breakdown, retrain-cadence experiments, paper-trading reconciliation) | Deferred to v2 | Requirements definition, 2026-08-19 |

## Session Continuity

Last session: 2026-08-29T07:35:34.966Z
Stopped at: Completed 05-13-PLAN.md
Resume file: None

## Operator Next Steps

- Start the next milestone with /gsd-new-milestone
