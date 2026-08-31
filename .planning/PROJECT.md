# NBA Value Betting Bot

## What This Is

A personal, paper-trading NBA moneyline value-betting system: it trains a calibrated XGBoost model on historical NBA team stats, compares model-implied win probabilities against live bookmaker odds to flag "value" bets, filters out bets where a key player is injured, and tracks a virtual bankroll with half-Kelly stake sizing. It also now includes a walk-forward backtest engine that replays the full decision pipeline chronologically against archived historical odds, gated by a one-shot holdout. No real money is at risk yet — it's a single-user research/validation project run manually or via a daily script.

## Core Value

The bot must demonstrate a **positive, validated ROI over a proper historical backtest** before it's trusted with anything beyond paper trading. Win rate or model accuracy alone don't matter if the actual betting strategy (value threshold + staking + filters) doesn't make money against real historical odds.

## Requirements

### Validated

<!-- Existing technical capabilities — confirmed to run, NOT confirmed to be profitable. -->

- ✓ Historical data ingestion from `nba_api` (game-level box scores, reshaped home/away) — existing (`01_hent_data.py`)
- ✓ Leakage-safe rolling-window feature engineering (10-game rolling averages, `shift(1)`) — existing (`02_feature_engineering.py`)
- ✓ XGBoost classifier training with isotonic calibration, time-series train/test split — existing (`03_tren_modell.py`, `modell_utils.py`)
- ✓ Live odds retrieval (The Odds API) and value/EV scoring against the calibrated model — existing (`04_value_detector.py`)
- ✓ Injury-risk filtering based on top-3 minutes players' recent availability — existing (`05_skadefilter.py`)
- ✓ Daily orchestration: settles pending bets, runs the pipeline, sizes stakes via half-Kelly, persists bankroll/bet ledger as JSON, renders a static HTML dashboard — existing (`06_bot.py`)
- ✓ Odds API key loaded from an environment variable (not hardcoded), exposed key rotated — Phase 1
- ✓ `modell_utils.py` tracked in git so a fresh clone can unpickle `nba_modell.pkl` — Phase 1
- ✓ `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` marked superseded/never-deployed, no longer silently implying their proposed thresholds are live — Phase 1
- ✓ `features.py`/`strategy.py`/`teams.py` extracted as shared, tested modules — single implementation of feature engineering, value/EV/Kelly math, and team-name resolution, replacing 2-4 independent duplicates each — Phase 2
- ✓ `config.py` single source-of-truth for the 7 strategy constants, imported by both live scripts — Phase 2
- ✓ First automated test suite in this repo (pytest, 37 tests, grown to 349 by end of milestone) covering stake-sizing, dedup, and a determinism/leakage-safety proof for the shared core — Phase 2
- ✓ Isotonic calibration fit and evaluated on disjoint train/calibrate/test slices, closing a confirmed same-slice leakage bug — Phase 3
- ✓ Historical odds (bet-time and closing) for the full backtest window fetched once and archived permanently in SQLite (480 dates, 187,376 rows) — Phase 4
- ✓ Live bot (`06_bot.py`) calls the shared core in-process instead of shelling out to `04_value_detector.py`/`05_skadefilter.py` — Phase 4
- ✓ A walk-forward backtesting framework (`backtest.py`, `08_kjor_backtest.py`) that replays the value-betting strategy (model + value threshold + odds range + injury filter + Kelly staking) chronologically against archived historical odds, with a structurally single-entry holdout guard, and reports ROI/win-rate/drawdown/CLV with bootstrap and Wilson confidence intervals — Phase 5
- ✓ The one-shot 2024-25 holdout evaluation, spent exactly once under a frozen configuration — Phase 5 (result: inconclusive, see Context)

### Active

<!-- Current scope. Building toward these. -->

(None yet — v1.0's active requirements were fully delivered. Next milestone requirements TBD via `/gsd:new-milestone`.)

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Real-money betting / live wagering integration — not until paper-trading + backtest show sustained positive ROI (still true: v1.0's holdout result was inconclusive, not positive)
- Spread and totals markets — starting moneyline-only for v1; may be added later once the moneyline strategy is validated
- Multi-user / hosted service — this is a single-user personal tool, not a product
- Re-running the spent 2024-25 holdout — BT-03 permits exactly one out-of-sample check per milestone; a new evaluation requires new data (2025-26 season), not a rerun against 2024-25

## Context

**Current State (as of v1.0 ship, 2026-08-29):**

- **v1.0's actual deliverable — a trustworthy walk-forward backtest engine — is built and works.** It replays the full decision pipeline (model → value threshold → odds filter → injury filter → Kelly stake) chronologically against 187,376 rows of archived historical odds, with a structurally-enforced single-entry holdout guard (not just convention).
- **The Core Value question ("is this strategy profitable?") came back inconclusive, not positive.** The one-shot 2024-25 holdout (spent under a frozen config: 0.20 value threshold, 2.50 max odds, flat staking) produced ROI -25.0%, 95% CI [-64.5%, +24.6%], on only 19 bets — the sample is far too small to conclude either way. The tuning-slice signal that motivated freezing that config (ROI +15.0%, 52 bets) did not survive out-of-sample testing. This is an honest result from a working instrument, not a bug.
- **The one-shot holdout is now spent for 2024-25 data.** Re-testing requires the 2025-26 season's data, not a rerun against 2024-25 — this is enforced in code (`HoldoutLaastFeil`), not just policy.
- **A real, previously-hidden bug was found and fixed along the way:** isotonic calibration on small walk-forward windows (as few as ~15 games) was saturating predicted probabilities to exactly 1.0 for up to 38% of bets in some samples. Fixed with an absolute 50-game floor (`model.py`). This is a permanent fix, not scoped to one run — any future code that fits a calibrator on a small dynamically-sized slice should be checked against this pattern.
- **The codebase evolved from a flat, duplicated batch pipeline into a shared-core architecture during this milestone.** Feature engineering, team-name resolution, value/EV/Kelly math, and odds-fetching logic each now live in exactly one tested module (`features.py`, `strategy.py`, `teams.py`, `odds.py`, `config.py`, `model.py`, `metrics.py`, `skadefilter.py`, `verdi_deteksjon.py`, `backtest.py`) instead of 2-4 independent copies. 349 automated tests exist where there were none at milestone start.
- **3 minor, non-blocking tech-debt items remain** (see `.planning/milestones/v1.0-MILESTONE-AUDIT.md`): a burn-in filter edge case in `backtest.py`, redundant CSV I/O in `klargjor_backtestdata`, and a long-standing `gjeldende_sesong()` duplication between `verdi_deteksjon.py` and `skadefilter.py`. None affect the holdout result's validity.
- **The next decision is a product decision, not a technical one:** what to do with an inconclusive result — gather more data (2025-26 season), try a different model/feature approach, or accept the strategy isn't validated and stop here. The user has not yet decided.
- **Deferred from Phase 1, still outstanding:** git-history scrubbing of the old leaked API key value (destructive, needs separate approval) and deletion of ~471MB of local scratch artifacts (gitignored only, not deleted from disk).

## Constraints

- **Scope**: Moneyline only for v1 — spread/totals explicitly deferred, not because they're hard but to keep validation focused on one strategy at a time.
- **Risk**: No real-money betting until backtested + paper-traded evidence of positive ROI exists — this is a hard gate, not a suggestion.
- **Data**: Historical odds backtesting depends on The Odds API's historical endpoint (rate limits / API cost apply — same key that needs rotating).
- **Language/style**: Existing codebase uses Norwegian identifiers and comments throughout; new/modified code should stay consistent with this unless a decision is made to deviate.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Backtest the full strategy against historical odds before further threshold tuning | Current losses trace to unvalidated threshold changes and a fix that was written but never deployed; guessing again would repeat the same mistake | ✓ Good — Phase 5, engine built and holdout spent; result inconclusive |
| Start with moneyline only, defer spread/totals | Keeps validation focused; can expand once moneyline strategy is proven | ✓ Good — held for the whole milestone, still the right scope |
| Fix leaked API key, untracked `modell_utils.py`, and doc/code drift as part of this milestone | Flagged as critical during codebase mapping; leaked key is on a public repo and untracked file breaks fresh clones | ✓ Good — Phase 1 |
| Defer git-history scrubbing and scratch-artifact deletion rather than doing them autonomously | Both are destructive/irreversible; rotating the key neutralizes the practical risk without a force-push, and scratch deletion needs explicit confirmation | — Pending (user decision, still deferred at v1.0 close) |
| Stay open to architectural changes if backtesting points to a deeper issue (model/features/data), not just thresholds | User explicitly does not want to just re-tune the same broken structure if that's not where the problem is | — Pending — holdout result is inconclusive, not diagnostic; next milestone decides |
| Extract shared core as flat modules at repo root, not a full `nba_betting/` package | Matches existing convention; full package restructure only becomes load-bearing once backtest/live paths must coexist (Phase 4/5) | ✓ Good — Phase 2, held through Phase 5 without needing a package restructure |
| Scope CORE-04's parity test down to a determinism/leakage proof, not a live-vs-backtest integration test | The backtest engine doesn't exist until Phase 5 — the requirement text slightly outran what's buildable yet | ✓ Good — Phase 2; Phase 5's `tests/test_parity.py` added the real live-vs-backtest integration proof |
| Fix 3 critical bugs found in `06_bot.py`/`05_skadefilter.py` during Phase 2 code review | Dashboard XSS, bankroll double-checkpoint, home/away mismatch risk — pre-existing in the developer's own WIP, not introduced by Phase 2 | ✓ Good — fixed 2026-08-31 via quick task 260831-c4z (13 new regression tests, 349→362 passing) |
| Fix isotonic calibration degeneracy on small walk-forward windows with an absolute 50-game floor (D-05-05) | Small calibration slices (~15 games) were saturating `modell_prob` to 1.0 for up to 38% of bets — a real, previously-hidden bug found mid-Phase-5 | ✓ Good — Phase 5, permanent fix in `model.py` |
| Freeze tuning-slice config (0.20 threshold, 2.50 max odds, flat staking) for the one-shot holdout, rather than the live bot's default (0.05, half-Kelly) | Live config showed no edge even post-calibration-fix; the tighter config showed a small-sample positive signal that survived a sensitivity check | ⚠️ Revisit — the signal did not survive the holdout (ROI -25.0%, CI straddles zero) |
| Spend the one-shot 2024-25 holdout under the frozen config, with direct developer authorization | BT-03 permits exactly one out-of-sample check; further in-sample tuning would repeat the original mistake this milestone exists to fix | ✓ Good — process followed correctly; result itself is inconclusive (small sample) not favorable |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-08-29 after v1.0 milestone completion*
