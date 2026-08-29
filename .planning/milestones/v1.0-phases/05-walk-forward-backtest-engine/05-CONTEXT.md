# Phase 5: Walk-Forward Backtest Engine - Context

**Gathered:** 2026-08-24
**Status:** Ready for planning
**Mode:** Autonomous (smart discuss — recommended answers accepted per user's "just go through it" instruction; no per-area interactive round)

<domain>
## Phase Boundary

This phase builds the backtest engine that is the project's actual Core Value deliverable: it replays the full betting decision pipeline (model score → value threshold → odds filter → injury filter → half-Kelly stake) chronologically against the historical odds already archived in `odds_arkiv.db` (Phase 4), using walk-forward (as-of-aware, periodically retrained) model scoring so no prediction ever sees data from its own future. It produces a reproducible, versioned run manifest with ROI/win-rate/max-drawdown/CLV and a confidence interval, gated by a final holdout slice that is checked exactly once after all threshold/parameter decisions are frozen. It does NOT change `MIN_VALUE_TERSKEL`/`MAX_ODDS`/`KELLY_FRAKSJON` in `config.py` as a side effect of building the engine — those are validated/updated only as a *result* the backtest produces evidence for, not a precondition. It does NOT build the v2 grid-search/HTML-report/error-slice tooling (BTV2-01 through BTV2-05, deferred).

</domain>

<decisions>
## Implementation Decisions

### Package & Module Structure
- Backtest code lives as flat modules at repo root — `backtest.py` (walk-forward loop) and `metrics.py` (ROI/drawdown/CLV/CI) — matching the existing `features.py`/`strategy.py`/`teams.py`/`odds.py`/`config.py` pattern established in Phases 2 and 4. The full `nba_betting/` package sketched in early research is explicitly NOT adopted this phase — D-08 (Phase 4) left this undecided and nothing in BT-01–07 requires the restructure.
- A new numbered entry script, `08_kjor_backtest.py`, matches the existing `0N_verb_ting.py` convention (01–07 already exist) and calls `backtest.py`'s functions — mirrors the importable-function-plus-`if __name__` pattern established in Phase 4's D-05.
- Model training/retraining logic is extracted into a new shared `model.py` module (train/calibrate/persist/load, `as_of`-aware), reusing the existing `modell_utils.KalibrertModell` wrapper, so both `03_tren_modell.py` (one-shot) and the backtest's walk-forward retrain loop call the same function — closes the last duplicated-logic gap the research flagged (Anti-Pattern 2).
- Backtest run outputs (manifests, ledgers) go in a new gitignored `backtests/` directory at repo root, one subfolder per run — kept structurally separate from `bankroll.json`/`bets.json` so simulated backtest state can never mix with or be mistaken for real paper-trading history (per `.planning/research/ARCHITECTURE.md`'s explicit warning on this exact failure mode).

### Walk-Forward Retraining & Holdout Definition
- Retraining cadence is monthly: the model is refit at the start of each simulated calendar month using only data strictly before that date. This follows `.planning/research/ARCHITECTURE.md` Pattern 1's suggested cadence and avoids ~30x the model fits of daily retraining for negligible accuracy gain at this data volume (3,638 games).
- Training window is expanding (all data from 2022-10-24 up to the retrain cutoff), not rolling — the total data volume (~2.5 seasons) is modest enough that discarding older games via a rolling window would needlessly throw away signal.
- The locked final holdout is the full 2024-25 season (2024-10 through 2025-04-13, the most recent complete season in the archived data). All threshold/parameter/Kelly-fraction decisions are tuned only on 2022-23 + 2023-24 data; the 2024-25 slice is checked exactly once, after those decisions are frozen — satisfies BT-03.
- The holdout lock is enforced in code, not just convention: a `HOLDOUT_START_DATO` constant in `config.py`, plus a structural guard so the tuning/sweep code path raises if asked to evaluate dates on or after that constant. Only a separate, explicit "final holdout run" entry point may read past it. BT-03 explicitly requires enforcement "by the code, not just convention."

### Run Manifest & Reporting Output
- Each run writes `backtests/<run_id>/manifest.json` containing: the config snapshot (thresholds, odds range, Kelly fraction, retrain cadence), date range, and headline metrics (ROI, win rate, max drawdown, bet count, confidence interval) — matches `.planning/research/ARCHITECTURE.md`'s sketched `backtests/<run_id>/report + ledger` layout and BT-05's "reproducible, versioned run manifest" requirement.
- Each run also writes `backtests/<run_id>/ledger.csv`, one row per simulated bet — CSV rather than JSON since backtest ledgers are write-once/read-many per run (unlike `bets.json`, which is repeatedly mutated by the live bot).
- Confidence intervals: bootstrap resampling (1,000 resamples) of the bet ledger for the ROI CI; Wilson score interval for the win-rate CI. Bootstrap handles the non-normal, small-sample nature of a flagged-bet subset better than a naive normal approximation.
- `run_id` is timestamp-based (`YYYYMMDD-HHMMSS`) with a short config-hash suffix, so runs sort chronologically and identical-config reruns remain distinguishable.

### CLV & Kelly Sweep Mechanics
- CLV per bet is computed as the vig-free implied probability at the **closing** snapshot minus the vig-free implied probability at the **bet-time** snapshot (both already archived in `odds_arkiv.db` as `snapshot_type` `bet_time`/`closing`), reusing `strategy.fjern_vigorish()` on both — mirrors the vig-removal reasoning already applied to the value calculation, so bookmaker margin never leaks into the CLV signal (BT-06). **Sign convention (corrected 2026-08-24 — an earlier draft of this decision had the operands reversed, which inverted the sign):** `closing − bet_time`, so a **positive** CLV means the bettor's price was better than the closing line implied (the market moved toward the bettor's side after the bet was placed) — matching the standard sports-betting convention where positive CLV signals genuine edge, and matching BT-06's own framing of CLV as "a faster-converging signal of genuine edge." A bet at longer odds than the eventual close (lower bet-time implied probability than closing implied probability) now correctly reads as a positive number.
- The Kelly-fraction sweep (flat/quarter/half/full, BT-07) is split into a predict pass (walk-forward model scoring + odds/injury filtering, run once and cached) and a simulate pass (re-running `strategy.beregn_innsats` at each Kelly fraction against the cached predictions) — per `.planning/research/ARCHITECTURE.md`'s explicit predict/simulate split, avoiding a ~4x-slower full re-run of the retrain loop per fraction.
- The sweep runs only on the train/calibrate slice (2022-23 + 2023-24) — never on the locked holdout, consistent with BT-03's "checked exactly once, after all parameter decisions are frozen" (read together with BT-07).
- Sweep output is `backtests/<run_id>/kelly_sweep.json` (one entry per Kelly fraction: ROI, max drawdown, bet count), written alongside the main manifest as a diagnostic sub-output of the same run rather than a separate decoupled script.

### Claude's Discretion
- Exact internal function names and module-level organization within `backtest.py`, `metrics.py`, and `model.py` (Norwegian, snake_case, per established convention).
- Exact bootstrap implementation details (resample count beyond the 1,000 default, RNG seeding for reproducibility — should be seeded so re-running the same manifest config reproduces the same CI).
- Whether `08_kjor_backtest.py` takes CLI flags for date range / Kelly fraction overrides, or is edited-and-rerun like the other numbered scripts — planner's call, but must remain resumable/cheap to iterate on the train/calibrate slice per the "predict once, simulate many" cost-management guidance in `.planning/research/ARCHITECTURE.md`.

### Post-Research Resolution (2026-08-24 — resolved autonomously, see 05-RESEARCH.md)

`05-RESEARCH.md` found this phase's original injury-filter assumption was wrong and raised 3 open questions. Resolved here so the planner does not need to re-litigate:

1. **Injury-filter backtest IS in scope.** Research confirmed `nba_kamper_raw.csv`/`nba_features.csv` are team-level only (no player IDs/minutes), so `05_skadefilter.py`'s live "top-3 minutes players present in last 3 games" logic cannot be made as-of-aware from existing data alone — it needs a new `nba_spillerlogg_raw.csv` (player-game-log) data source. Research verified live that `nba_api`'s `leaguegamelog.LeagueGameLog(player_or_team_abbreviation='P', season=...)` returns a full season of player-game-log rows in one free call (same pattern `01_hent_data.py` already uses for team logs; no Odds-API credit cost). **Decision: build this data acquisition + an as-of-aware `skadefilter.py` adaptation as part of this phase**, rather than disabling the injury filter in the backtest — BT-01 explicitly lists the injury filter as part of the replayed decision pipeline, and this project's Core Value is validating the *actual* live strategy, not a stripped-down approximation of it. Disabling it would silently bias every backtest ROI number in an unknown direction (games where a key player was actually out would be scored as if they weren't).
2. **`HOLDOUT_START_DATO = "2024-10-01"`** — confirmed as the exact constant value (matches the "full 2024-25 season" holdout definition above; research independently verified 1,225 games fall on/after this date in `nba_features.csv`).
3. **Early walk-forward months (small sample) are included, not excluded**, with the bootstrap/Wilson CIs communicating the uncertainty rather than dropping data — avoids any appearance of cherry-picking the backtest window, and `features.py`'s existing `min_periods=3` already naturally limits how few games contribute to an early rolling-average anyway.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — BT-01 through BT-07 (locked acceptance criteria for this phase)

### Roadmap
- `.planning/ROADMAP.md` §"Phase 5: Walk-Forward Backtest Engine" — goal and success criteria

### Milestone-level research
- `.planning/research/ARCHITECTURE.md` — Pattern 1 (walk-forward replay with as-of-aware retraining), Pattern 2 (unified live+historical data adapters), Common Pitfalls #1–6, Anti-Patterns 1–3, and the sketched `backtest/engine.py`/`metrics.py`/`backtests/<run_id>/` layout this phase's decisions are grounded in
- `.planning/research/STACK.md`, `.planning/research/FEATURES.md`, `.planning/research/PITFALLS.md` — supporting detail, cross-check during planning

### Prior phase decisions this phase depends on and resolves
- `.planning/phases/04-historical-odds-acquisition-live-refactor/04-CONTEXT.md` D-08 — deferred the full package-restructure decision to Phase 5's planner; resolved above (stay flat, no `nba_betting/` package)
- `.planning/phases/02-shared-core-extraction-test-foundation/02-CONTEXT.md` — CORE-04's parity test was scoped down to a determinism/leakage proof because the real live-vs-backtest integration test needed this phase's engine to exist (see `02-06-SUMMARY.md` "Findings for Phase 5") — planner should revisit whether a live-vs-backtest parity test now becomes buildable
- `features.py`'s `beregn_lag_form(..., as_of=...)` already implements the as-of filtering this phase's walk-forward loop needs — no rework required, just correct usage
- `strategy.py`'s pure functions (`fjern_vigorish`, `beregn_value_og_ev`, `beregn_innsats`, dedup helpers) are already backtest-ready (no I/O, no project imports) — reuse directly

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `features.py::beregn_lag_form(df_raw, vindu=10, as_of=None)` — already leakage-safe and as-of-aware; strict `<` comparison confirmed correct for backtest use.
- `strategy.py` — `fjern_vigorish()`, `beregn_value_og_ev()`, `beregn_innsats()` (half-Kelly), `finn_bet_nokkel()`/`bygg_bet_nokler()` (dedup) — all pure, parameter-driven, zero I/O. Directly importable by the backtest engine with no modification.
- `config.py` — single source of truth for `MIN_VALUE_TERSKEL`, `MIN_ODDS`, `MAX_ODDS`, `KELLY_FRAKSJON`, `MAX_INNSATS`, `MIN_INNSATS`, `STARTKAPITAL`. The backtest engine reads from here by default but must support overriding these per-run for the Kelly sweep and any future threshold sweeps.
- `odds_arkiv.db` (SQLite, `odds_arkiv` table, 187,376 rows) — both `bet_time` and `closing` snapshot types, keyed by `(sport, event_id, kamp_dato, snapshot_type, bookmaker, marked, utfall_navn)`, with `hjemme_lag_id`/`borte_lag_id` already resolved to nba_api team IDs. Full 2022-10-24 → 2025-04-13 coverage. `odds.py::apne_arkiv()` opens it.
- `odds.py::hent_unike_kampdatoer()` — already produces the canonical list of unique game dates from `nba_features.csv`, reusable for the walk-forward loop's date iteration.
- `modell_utils.KalibrertModell` — the isotonic-calibration wrapper; the new `model.py` should build on this rather than reimplementing calibration.

### Established Patterns
- Norwegian snake_case naming, pure functions with docstrings explaining *why* (especially leakage/timing pitfalls), `if __name__ == "__main__":` guard for standalone-runnable scripts, `sys.exit(1)` with explanatory comment for fatal API/data errors — all established since Phase 1/2/4 and expected to continue.
- Existing bet-record dict shape (`dato`, `kamp_dato`, `kamp`, `bet`, `odds`, `innsats`, `modell`, `modell_prob`, `value`, `ev`, `status`, `gevinst`) from `06_bot.py` — the backtest ledger row shape should stay recognizably parallel to this for easy comparison, even though it's CSV not JSON.

### Integration Points
- `nba_features.csv` (3,638 rows) — raw game data the walk-forward loop iterates over; already the shared date/game source for both Phase 4's odds archive and this phase's replay.
- `05_skadefilter.py`/`skadefilter.py` — injury-filter logic needs an as-of-aware adaptation (currently keyed to live "today"); this phase's planner must decide the specific signature/data-source change needed to look at "3 games before the simulated date" using historical box-score data already in `nba_kamper_raw.csv`/`nba_features.csv` rather than a live `nba_api` call.
- `03_tren_modell.py` — current one-shot training script; logic should be extracted into the new `model.py` so both this script and the backtest's monthly retrain loop share one implementation (mirrors the Phase 2 extraction pattern for `features.py`/`strategy.py`/`teams.py`).

</code_context>

<specifics>
## Specific Ideas

No UI/visual requirements — this is a backend simulation/reporting phase. All specifics are the grounded technical decisions captured above (package layout, retraining cadence, holdout definition, manifest format, CLV/Kelly-sweep mechanics), derived from `.planning/research/ARCHITECTURE.md` and the existing shared-core code rather than from interactive user discussion, per the user's explicit "just go through it yourself" instruction for this phase.

</specifics>

<deferred>
## Deferred Ideas

- Full `nba_betting/` package restructure (`data/`, `backtest/`, `live/` subdirectories) — stays deferred; flat modules chosen instead for this phase (see Package & Module Structure above). Revisit only if a future phase's scope genuinely requires the separation.
- Threshold/odds-range grid search (BTV2-01), static HTML backtest report (BTV2-02), error-slice breakdown (BTV2-03), retrain-cadence experiments (BTV2-04), automated paper-trading-vs-backtest reconciliation (BTV2-05) — all already tracked as v2 requirements in `.planning/REQUIREMENTS.md`, untouched by this phase.
- Any change to the *live* `MIN_VALUE_TERSKEL`/`MAX_ODDS`/`KELLY_FRAKSJON` values in `config.py` — this phase builds the engine that will produce the evidence for such a change, but does not itself change the live-running values. That's a follow-on decision after this phase's results are in.

</deferred>

---

*Phase: 5-Walk-Forward Backtest Engine*
*Context gathered: 2026-08-24*
