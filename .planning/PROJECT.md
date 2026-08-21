# NBA Value Betting Bot

## What This Is

A personal, paper-trading NBA moneyline value-betting system: it trains a calibrated XGBoost model on historical NBA team stats, compares model-implied win probabilities against live bookmaker odds to flag "value" bets, filters out bets where a key player is injured, and tracks a virtual bankroll with half-Kelly stake sizing. No real money is at risk yet — it's a single-user research/validation project run manually or via a daily script.

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
- ✓ First automated test suite in this repo (pytest, 37 tests) covering stake-sizing, dedup, and a determinism/leakage-safety proof for the shared core — Phase 2

### Active

<!-- Current scope. Building toward these. -->

- [ ] A historical backtesting framework that replays the value-betting strategy (model + value threshold + odds range + injury filter + Kelly staking) against historical odds data (The Odds API historical endpoint) and reports realistic ROI/drawdown — not just raw model classification metrics
- [ ] A validated, data-driven set of strategy parameters (value threshold, odds range, stake sizing) chosen because backtesting shows they work — not guessed/hand-tuned
- [ ] Root-cause investigation into why the current live config underperforms — model quality, feature set, calibration, threshold choice, or a combination — informed by the backtest rather than assumption
- [ ] Clear before/after evidence (paper-trading results, backtest results) that the rebuilt/fixed system beats the current losing baseline

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Real-money betting / live wagering integration — not until paper-trading + backtest show sustained positive ROI
- Spread and totals markets — starting moneyline-only for v1; may be added later once the moneyline strategy is validated
- Multi-user / hosted service — this is a single-user personal tool, not a product

## Context

- **Phase 2 complete (2026-08-21):** feature/team/strategy logic — previously duplicated 2-4x across the pipeline — now lives in single shared modules (`features.py`, `strategy.py`, `teams.py`) plus `config.py`, all imported by the live scripts. First automated tests landed (37 pytest tests). CORE-04's "parity test" was scoped down (per CONTEXT.md D-12) to a determinism/leakage-safety proof on the shared core, since the real live-vs-backtest integration test needs Phase 5's backtest engine to exist — the test file documents this and what Phase 5 must still add. Code review during this phase surfaced 3 pre-existing critical bugs in the developer's own uncommitted `06_bot.py`/`05_skadefilter.py` WIP (now committed per the developer's "include" decision) — none introduced by Phase 2's extraction work, all flagged as follow-up: a stored-XSS path in the dashboard (unescaped team names from The Odds API via `innerHTML`), a bankroll-history double-checkpoint bug that can understate same-day stakes, and a home/away game-result mismatch risk in `hent_kampresultat` when only a reverse fixture is found in the search window. Not yet fixed — most naturally addressed when Phase 4 touches `06_bot.py` again, or sooner if the user prioritizes it.
- **Phase 1 complete (2026-08-20):** repo hygiene fixed. Leaked Odds API key rotated and moved to env var (`ODDS_API_NOKKEL` via `python-dotenv`); `modell_utils.py` tracked; doc/code drift resolved by marking the never-deployed fix superseded rather than applying its unvalidated numbers. Running thresholds intentionally left unchanged (`MIN_VALUE_TERSKEL=0.05`, `MAX_ODDS=4.00`) — validated values still come from Phase 5's backtest, not from this cleanup. Two items deferred by explicit decision: git-history scrubbing of the old key (destructive, needs separate approval) and deletion of ~471MB of local scratch artifacts (gitignored only, not deleted).
- **Current state is losing money (in paper trading):** the tracked virtual bankroll fell from 1000 kr to 74.88 kr under the currently-running configuration.
- **A known fix was never applied:** `ENDRINGER_SUMMARY.txt` / `KALIBRERING_RAPPORT.md` describe raising `MIN_VALUE_TERSKEL` to 0.20, lowering `MAX_ODDS` to 2.50, and adding calibration/confidence filters — but `04_value_detector.py` still runs the old values (`MIN_VALUE_TERSKEL=0.05`, `MAX_ODDS=4.00`). The user was not aware this fix had never made it into the running code.
- **No strategy backtest exists today.** The model is only evaluated with classification metrics (accuracy/log-loss/Brier) on a 2-month holdout at training time. There has never been a backtest of the full betting decision pipeline (value detection + odds filtering + Kelly staking) against historical odds, which likely explains why threshold tuning has been guesswork.
- **Historical odds data is available** via The Odds API's historical endpoint, making a proper backtest feasible.
- **Codebase is a flat, numbered-script batch pipeline** (`01_` → `06_`), no package structure, Norwegian identifiers throughout, no automated tests, no lint/format tooling. Full details in `.planning/codebase/`.
- **Known code-quality issues** (from codebase mapping): feature-engineering logic duplicated between `02_feature_engineering.py` and `04_value_detector.py` (must be kept in sync manually); team-name lookup logic independently reimplemented in four different files; all pipeline scripts execute top-level code with no `main()` guard (untestable, unimportable).
- **User is open to rethinking the approach** — not committed to preserving the current architecture if backtesting reveals a more fundamental problem (model, features, or data) rather than just bad thresholds.

## Constraints

- **Scope**: Moneyline only for v1 — spread/totals explicitly deferred, not because they're hard but to keep validation focused on one strategy at a time.
- **Risk**: No real-money betting until backtested + paper-traded evidence of positive ROI exists — this is a hard gate, not a suggestion.
- **Data**: Historical odds backtesting depends on The Odds API's historical endpoint (rate limits / API cost apply — same key that needs rotating).
- **Language/style**: Existing codebase uses Norwegian identifiers and comments throughout; new/modified code should stay consistent with this unless a decision is made to deviate.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Backtest the full strategy against historical odds before further threshold tuning | Current losses trace to unvalidated threshold changes and a fix that was written but never deployed; guessing again would repeat the same mistake | — Pending |
| Start with moneyline only, defer spread/totals | Keeps validation focused; can expand once moneyline strategy is proven | — Pending |
| Fix leaked API key, untracked `modell_utils.py`, and doc/code drift as part of this milestone | Flagged as critical during codebase mapping; leaked key is on a public repo and untracked file breaks fresh clones | ✓ Good — Phase 1 |
| Defer git-history scrubbing and scratch-artifact deletion rather than doing them autonomously | Both are destructive/irreversible; rotating the key neutralizes the practical risk without a force-push, and scratch deletion needs explicit confirmation | — Pending (user decision) |
| Stay open to architectural changes if backtesting points to a deeper issue (model/features/data), not just thresholds | User explicitly does not want to just re-tune the same broken structure if that's not where the problem is | — Pending |
| Extract shared core as flat modules at repo root, not a full `nba_betting/` package | Matches existing convention; full package restructure only becomes load-bearing once backtest/live paths must coexist (Phase 4/5) | ✓ Good — Phase 2 |
| Scope CORE-04's parity test down to a determinism/leakage proof, not a live-vs-backtest integration test | The backtest engine doesn't exist until Phase 5 — the requirement text slightly outran what's buildable yet | ✓ Good — Phase 2, revisit in Phase 5 |
| Fix 3 critical bugs found in `06_bot.py`/`05_skadefilter.py` during Phase 2 code review | Dashboard XSS, bankroll double-checkpoint, home/away mismatch risk — pre-existing in the developer's own WIP, not introduced by Phase 2 | — Pending (deferred, most naturally Phase 4) |

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
*Last updated: 2026-08-21 after Phase 2 completion*
