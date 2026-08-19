# Project Research Summary

**Project:** NBA Betting — value-betting strategy backtesting & validation
**Domain:** Sports-betting / quant-style value-detection system (NBA moneyline, Python/pandas/XGBoost, historical backtesting)
**Researched:** 2026-08-19
**Confidence:** MEDIUM-HIGH

## Executive Summary

This project is a solo-maintained Python system that predicts NBA moneyline outcomes with a calibrated XGBoost model, flags "value" bets against bookmaker odds, and stakes them with half-Kelly sizing. It currently has no historical backtesting framework, no automated tests, and has already lost most of its virtual bankroll (1000 kr to 74.88 kr) running an unvalidated, hand-tuned threshold configuration. Experts building this kind of system converge on a well-established pattern from quant/algo-trading tooling (NautilusTrader, QuantConnect LEAN, Freqtrade): one shared decision core (features to model to strategy), two thin adapters — a backtest engine that replays it walk-forward over history with simulated odds/bankroll, and a live orchestrator that runs it once a day for real. The two paths must literally import the same functions, not maintain parallel reimplementations, because this codebase has already suffered duplicated-logic drift twice (feature engineering, team-name lookup) and a documented remediation report that was never actually deployed.

The recommended approach is: (1) fix repo hygiene and extract the shared core (teams.py, features.py with an as_of parameter, strategy.py as pure functions) before writing a single line of backtest code, since building a backtest against duplicated logic just creates a third drift point; (2) acquire historical odds cheaply via The Odds API's per-event historical endpoint (10x cheaper than the sport-wide snapshot endpoint) and archive every response permanently in SQLite, since historical odds never change; (3) build a custom pandas/numpy walk-forward backtest loop — no off-the-shelf backtesting framework (backtrader, vectorbt, zipline-reloaded) fits discrete single-settlement fixed-odds wagers, they're all built for continuous OHLCV price series; and (4) enforce a strict tune/validate/holdout data split with walk-forward retraining, since a single model trained once on the whole date range and then "backtested" across that same range would leak future information into every prediction, invalidating the result.

The dominant risk is overfitting the backtest itself — this project already lived through one round of this (a threshold change never even deployed, based on in-sample analysis alone). Closely related risks are already-present, verified bugs: the isotonic calibrator is fit and evaluated on the same data slice (produces optimistically biased "value" signals), a leaked/hardcoded API key sits in a public repo, a runtime-critical file (modell_utils.py) is untracked in git, and there is zero test coverage on the money-math functions that directly control stakes. None of these are backtesting-framework problems per se, but a backtest built on top of them would validate a broken foundation. The research strongly implies a remediation-first, backtest-second phase order, with the backtest itself built to structurally prevent the overfitting pattern that already happened once.

## Key Findings

### Recommended Stack

No new heavyweight dependencies are needed. The backtest engine itself should be a new, custom pandas/numpy module — generic trading backtest frameworks are a paradigm mismatch for single fixed-odds wagers that settle once. The single highest-value stack finding is a cost optimization: The Odds API's per-event historical endpoint is 10x cheaper than its sport-wide snapshot endpoint for building a season-long dataset, and results should be archived permanently in SQLite (not a TTL cache) since historical odds for a past timestamp never change.

**Core technologies:**
- Custom event-driven backtest loop (pandas/numpy, new module) — replays model to threshold to filters to Kelly stake chronologically against historical odds; no existing library fits this discrete-bet paradigm
- The Odds API per-event historical odds endpoint (/v4/historical/sports/{sport}/events/{eventId}/odds) — 1 credit/event vs. 10 credits/event for the sport-wide snapshot endpoint; budget for the $30/mo 20K-credit tier for the initial full-season backfill
- SQLite (stdlib) — permanent local archive of every historical odds/event API response ever fetched, so backtests are replayable offline at zero further cost
- scikit-learn TimeSeriesSplit (already installed) — walk-forward CV for model hyperparameter tuning specifically, not for the single train/test backtest split
- python-dotenv + tenacity — fix the hardcoded API key immediately (independent of backtesting) and add retry/backoff around the long sequential historical-odds fetch loop
- pytest — first automated tests in this repo, scoped to the new backtest module's correctness-critical logic (walk-forward split boundaries, Kelly formula, ROI/drawdown arithmetic, odds-archive dedup)

### Expected Features

A sports-betting backtest is not trustworthy without a specific set of table-stakes features — without them the ROI number is meaningless or actively misleading, which is precisely the failure mode that already produced this project's unvalidated thresholds.

**Must have (table stakes):**
- Chronological walk-forward replay of the full pipeline (model to value threshold to odds filter to injury filter to Kelly stake) against historical odds — not just model accuracy, which is what exists today
- Point-in-time / leakage-safe data assembly (odds, injuries, rolling stats all filtered to "known as of date D")
- Walk-forward train/calibrate/test three-way split, repeated across rolling windows — fixes the existing same-slice calibration leakage bug
- A locked, never-touched final holdout slice, checked exactly once
- ROI, win rate, max drawdown reported on the flagged-bet subset only, with bet count and a confidence interval attached to every headline number
- Out-of-sample calibration curves / reliability diagrams
- Reproducible, versioned run manifests (config + date range + metrics) for before/after comparison

**Should have (differentiators):**
- Closing Line Value (CLV) tracking per bet — faster-converging signal of genuine edge than raw ROI
- Kelly-fraction sensitivity sweep (flat/quarter/half/full)
- Threshold/odds-range grid search — but structurally gated so it can never touch the holdout
- Static HTML backtest report reusing the existing dashboard pattern
- Error-slice breakdown (ROI by odds bucket, home/away, rest days)

**Defer (v2+):**
- Retrain-cadence experiments (monthly vs. seasonal)
- Automated paper-trading vs. backtest reconciliation tooling
- Any real-money execution, spreads/totals markets, multi-sport/multi-user tooling — explicitly out of scope this milestone

### Architecture Approach

The recommended structure converts the current flat-script repo into an importable package (nba_betting/) with one shared decision core (features.py, model.py, strategy.py, teams.py) imported identically by a new backtest/ engine and a refactored live/ orchestrator. Backtest and live must never share state (separate state/ vs. backtests/<run_id>/ directories) even though they share code. No database, service layer, or async is warranted — this remains a single-user, once-a-day system; SQLite is only justified as an odds-quota archive and, later, if the bet ledger needs richer querying.

**Major components:**
1. data/ adapters (games.py, odds.py, injuries.py, teams.py) — normalize live and historical sources into an identical schema so the decision core never needs to know which source it received
2. features.py/model.py/strategy.py (shared core) — pure, as_of-aware functions computing point-in-time-safe features, calibrated predictions, and bet/stake decisions; imported directly (no subprocess) by both paths
3. backtest/engine.py + backtest/metrics.py — walk-forward replay loop with as-of-aware retraining, simulated bankroll, ROI/drawdown/CLV computation
4. live/bot.py — daily orchestration, refactored to import the shared core instead of shelling out to separate scripts

### Critical Pitfalls

1. **In-sample threshold tuning that curve-fits the backtest** — this already happened once (an undeployed threshold change based on in-sample analysis alone). Avoid with a strict chronological tune/validate/holdout split; never move backward from holdout to validate.
2. **Look-ahead bias from historical odds timing** — using closing-line or best-available snapshots instead of the odds actually available when the live bot runs inflates backtest ROI unrealistically. Pin snapshot retrieval to the live bot's actual daily cadence; track CLV as a separate, distinct metric from entry-price ROI.
3. **Calibration metrics leak (already present bug)** — 03_tren_modell.py fits and evaluates the isotonic calibrator on the same data slice, producing optimistically biased "value" signals for every downstream bet decision. Requires a proper train/calibrate/test three-way split before backtest results can be trusted at all.
4. **Kelly staking amplifies edge-estimation error into ruin** — this is the likely direct mechanism behind the 1000 to 74.88 kr bankroll collapse. Requires drawdown reporting (not just ROI) in the backtest, a circuit breaker in live operation, and unit tests on the stake-sizing function.
5. **Config/doc drift and untracked runtime files (both already happened)** — a documented remediation was never actually deployed to code, and a file the pickled model depends on (modell_utils.py) is untracked in git. Both must be fixed before backtest results can be considered representative of what's actually running live.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Repo Hygiene & Config Remediation
**Rationale:** Cheapest, highest-priority fixes; backtest results are meaningless if they validate a config that isn't what's actually running, or if the environment can't reproducibly load the model at all.
**Delivers:** API key moved to .env/rotated, modell_utils.py committed, stale/undeployed markdown reports reconciled with actual running config or archived, a single source-of-truth strategy-config file.
**Addresses:** Pitfalls 6 (config drift) and 7 (untracked file) from PITFALLS.md.
**Avoids:** Building anything on top of a config nobody can verify is actually deployed.

### Phase 2: Shared Core Extraction & Test Foundation
**Rationale:** Building a backtest against duplicated feature/team-lookup/strategy logic creates a third drift point (this codebase already has two). Must happen before backtest code is written.
**Delivers:** features.py (with as_of parameter), strategy.py (pure functions: implied prob, value/EV, Kelly stake), teams.py (single resolver), plus unit tests for beregn_innsats/dedup logic and a leakage-regression parity test.
**Addresses:** Table-stakes "point-in-time leakage-safe data assembly" from FEATURES.md.
**Avoids:** Pitfalls 8 (train/serve feature skew) and 9 (no test coverage on money-math) from PITFALLS.md.

### Phase 3: Model/Calibration Remediation
**Rationale:** A biased calibrator poisons every downstream backtest run; must be fixed before backtest numbers are trusted, and is independent of the backtest engine itself.
**Delivers:** Proper train/calibrate/test three-way split for the isotonic regressor, calibration curve validated on a disjoint slice.
**Addresses:** Table-stakes "out-of-sample calibration curve" from FEATURES.md.
**Avoids:** Pitfall 3 (calibration metrics leak) from PITFALLS.md — this is an already-confirmed, live bug.

### Phase 4: Historical Odds Acquisition & Live Path Refactor
**Rationale:** The historical-odds fetch is a hard, rate-limited/costly dependency for the backtest engine and should be built/cached early; refactoring the live path to import the shared core (instead of subprocessing) should happen alongside or before the backtest so both paths are provably running identical logic.
**Delivers:** data/odds.py::fetch_historical_odds() using the per-event endpoint, SQLite permanent archive; live/bot.py importing shared core directly.
**Uses:** The Odds API per-event historical endpoint + SQLite archive from STACK.md.
**Implements:** Ports-and-adapters data layer from ARCHITECTURE.md (Pattern 3).

### Phase 5: Walk-Forward Backtest Engine
**Rationale:** This is the actual deliverable the project's Core Value statement depends on — but only valid once Phases 1-4 have removed the known leakage/drift/untested-math risks underneath it.
**Delivers:** backtest/engine.py (walk-forward replay with as-of-aware retraining), backtest/metrics.py (ROI, max drawdown, CLV, confidence intervals), reproducible run manifests, tune/validate/holdout-gated threshold sweep.
**Addresses:** Nearly all P1 features from FEATURES.md (chronological full-pipeline replay, locked holdout, ROI/drawdown/CI reporting).
**Avoids:** Pitfalls 1, 2, 4, 5 (overfitting, look-ahead bias, vig-removal errors, Kelly amplification) from PITFALLS.md — these are structural risks the engine's design must prevent by construction, not bolt on afterward.

### Phase Ordering Rationale

- Remediation-first, backtest-second: nearly every pitfall identified is an already-confirmed bug in the existing code (calibration leak, config drift, untracked file, untested money-math), not a hypothetical risk of the new backtest work — fixing these after the backtest exists would mean re-running and re-trusting the backtest anyway.
- Shared-core extraction must precede the backtest engine specifically because this project has already drifted twice (features, team lookup) from having parallel implementations — a third parallel implementation (the backtest) would compound rather than fix that pattern.
- The backtest engine is deliberately the last phase because its entire value proposition — "trustworthy evidence of edge" — depends on everything underneath it (config, calibration, shared logic, odds data) being correct first; an early backtest built on the current foundation would just produce a more elaborate wrong number.

### Research Flags

Needs deeper research during planning:
- **Phase 5 (Walk-Forward Backtest Engine):** No single dominant off-the-shelf framework exists for discrete fixed-odds backtesting (confirmed as a MEDIUM-confidence architectural synthesis, not a citable standard) — expect to design walk-forward retraining cadence, snapshot-timing offsets, and metrics definitions largely from first principles during planning.
- **Phase 4 (Historical Odds Acquisition):** The Odds API's exact historical snapshot availability/granularity for NBA specifically (pre- vs. post-Sept-2022 interval changes) should be spot-checked against real API responses before committing to a snapshot-offset strategy.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Repo Hygiene):** Standard git/secrets/config hygiene, no domain research needed.
- **Phase 2 (Shared Core Extraction):** Well-established refactoring pattern (extract shared pure functions, add parity tests); already has a documented architecture blueprint in ARCHITECTURE.md.
- **Phase 3 (Calibration Remediation):** Standard scikit-learn calibration best practice (train/calibrate/test split), well-documented in official sklearn docs.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM-HIGH | Odds API cost/endpoint facts verified against official docs (HIGH); the "no dominant backtest framework exists for this domain" conclusion is a reasoned synthesis, not a single citable source (MEDIUM) |
| Features | MEDIUM-HIGH | Backtesting/CLV/calibration concepts cross-checked against multiple independent sources plus two academic preprints (HIGH); specific sample-size heuristics rest on lower-confidence single sources (LOW-MEDIUM) |
| Architecture | HIGH | Shared-core-between-backtest-and-live pattern is well-established in mature tooling (NautilusTrader, QuantConnect LEAN, Freqtrade) and directly verified against this project's own documented anti-patterns |
| Pitfalls | MEDIUM-HIGH | General backtesting/Kelly/calibration pitfalls verified against multiple independent sources; project-specific pitfalls (calibration leak, config drift, untracked file) verified directly against this codebase's own CONCERNS.md/ARCHITECTURE.md — several are not hypothetical, they already happened |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- No single authoritative "sports-betting backtest framework" reference exists — the custom-loop architecture is a reasoned synthesis across quant-trading and sports-betting sources, not a single verified industry-standard pattern. Validate the walk-forward loop design against the project's own data shape early in Phase 5 planning rather than assuming a textbook answer exists.
- Exact historical odds snapshot availability/timing for NBA on The Odds API (interval granularity, coverage gaps) needs direct API verification before finalizing the snapshot-offset strategy in Phase 4.
- Statistical sample-size heuristics (e.g., "~2,000+ bets for solid significance") rest on lower-confidence blog sources rather than rigorous derivation — treat as directional guidance for reporting confidence intervals, not a hard gate, and prefer bootstrap/Wilson-interval calculations over a fixed bet-count threshold.
- quantstats compatibility with the project's installed pandas 3.0.1 is unverified by the maintainers as of research date — smoke-test before relying on it if the optional HTML tear-sheet report is added.

## Sources

### Primary (HIGH confidence)
- The Odds API official v4 guide (the-odds-api.com/liveapi/guides/v4/) — historical endpoint cost formulas, snapshot intervals, data availability
- scikit-learn official docs — TimeSeriesSplit behavior, probability calibration best practices
- PyPI JSON API — verified current versions/maintenance status for all supporting libraries
- NautilusTrader, QuantConnect/LEAN, Freqtrade official docs — shared backtest/live engine architecture principle
- arXiv preprints: "Optimal sports betting strategies in practice" and "ML for sports betting: accuracy or calibration?" — academic support for calibration-over-accuracy and staking discipline
- Direct codebase review: .planning/PROJECT.md, .planning/codebase/ARCHITECTURE.md, .planning/codebase/CONCERNS.md, .planning/codebase/STACK.md, KALIBRERING_RAPPORT.md, ENDRINGER_SUMMARY.txt

### Secondary (MEDIUM confidence)
- Great Bets, Predictology, Systematic Sports (Medium), OddsPapi — backtesting-without-overfitting practices, cross-checked across multiple independent sources
- Pikkit, OddsJam, Pinnacle Odds Dropper — Closing Line Value methodology, consistent across sources
- Matthew Downey's fractional-Kelly simulation write-up — simulation-backed, consistent with established Kelly literature
- sports-betting PyPI package docs — football/soccer-only scope confirmed, used as pattern inspiration only

### Tertiary (LOW confidence)
- Sports Insights, SportBot AI — specific sample-size statistical-significance heuristics; treat as directional, not precise
- WebSearch synthesis on quant-trading reporting ecosystem (quantstats vs. empyrical vs. pyfolio) — cross-checked against PyPI release dates but not independently verified beyond that

---
*Research completed: 2026-08-19*
*Ready for roadmap: yes*
