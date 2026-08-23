# Roadmap: NBA Value Betting Bot

## Overview

This milestone turns an already-running (and currently losing) paper-trading bot into a system whose strategy has been validated against a proper historical backtest. The journey is remediation-first, backtest-second: fix the repo hygiene issues and confirmed bugs that would otherwise poison any backtest result (Phase 1, Phase 3), extract the feature/team/strategy logic into a single shared core so the backtest and the live bot can never drift apart again (Phase 2), acquire and permanently archive historical odds while refactoring the live bot onto the shared core (Phase 4), and finally build the walk-forward backtest engine that is this project's actual Core Value deliverable — chronological, leakage-safe, holdout-gated, with ROI/drawdown/CLV reporting (Phase 5). Every phase after Phase 1 exists because it removes a specific, already-confirmed risk that would otherwise make the final backtest numbers untrustworthy.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Repo Hygiene & Config Remediation** - Fresh clone works, no leaked secrets, docs match running config (completed 2026-08-20)
- [x] **Phase 2: Shared Core Extraction & Test Foundation** - Feature/team/strategy logic lives in one place with tests, no more silent drift (completed 2026-08-21)
- [x] **Phase 3: Calibration Remediation** - Isotonic calibrator fit/evaluated on properly separated data, closing a confirmed leak (completed 2026-08-23)
- [ ] **Phase 4: Historical Odds Acquisition & Live Refactor** - Historical odds permanently archived; live bot runs on the shared core
- [ ] **Phase 5: Walk-Forward Backtest Engine** - Full strategy replayed chronologically against history with holdout-gated, versioned ROI/drawdown/CLV results

## Phase Details

### Phase 1: Repo Hygiene & Config Remediation

**Goal**: A fresh clone of this repo can be configured and run without exposing secrets or breaking on a missing file, and the strategy config actually running in production is known to match (or explicitly supersede) what's documented.
**Depends on**: Nothing (first phase)
**Requirements**: HYG-01, HYG-02, HYG-03
**Success Criteria** (what must be TRUE):

  1. A fresh `git clone` + `pip install` can load `nba_modell.pkl` without an `ImportError`, because `modell_utils.py` is tracked in git
  2. No Odds API key is hardcoded in source; `04_value_detector.py` reads it from an environment variable, and the previously-exposed key has been rotated so the old value is dead
  3. The claims in `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` are reconciled with the running code — either applied so code matches docs, or the docs are explicitly marked superseded — so there is exactly one source of truth for "what config is actually live"

**Plans**: 5 plans

Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Pre-flight safety gate: working-tree disposition, scratch-artifact decision, python-dotenv legitimacy approval (checkpoints only)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — HYG-02: harden .gitignore against scratch artifacts, track modell_utils.py, prove fresh-clone import

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — HYG-01 (code): fail-fast ODDS_API_NOKKEL env-var load via python-dotenv, .env.example, corrected setup guide

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 01-04-PLAN.md — HYG-03: mark KALIBRERING_RAPPORT.md and ENDRINGER_SUMMARY.txt as superseded/never-deployed and commit them

**Wave 5** *(blocked on Wave 4 completion)*

- [x] 01-05-PLAN.md — HYG-01 (human): rotate the exposed key, then run the full 01-VALIDATION.md phase gate (checkpoints + battery)

Plans are strictly sequential (waves 1-5): every plan commits against one shared git index, and the working tree holds a ~100MB scratch file plus ~1200 lines of unrelated uncommitted work, so concurrent staging is unsafe.

### Phase 2: Shared Core Extraction & Test Foundation

**Goal**: Feature engineering, team-name resolution, and value/stake strategy logic exist in exactly one place, imported identically by the live path and the (future) backtest path, with automated tests protecting the money-math functions.
**Depends on**: Phase 1
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04
**Success Criteria** (what must be TRUE):

  1. `features.py`, `strategy.py`, and `teams.py` exist as shared modules, and no duplicate reimplementation of their logic remains in `02_feature_engineering.py`, `04_value_detector.py`, `05_skadefilter.py`, or `06_bot.py`
  2. `MIN_VALUE_TERSKEL`, `MAX_ODDS`, and the Kelly fraction live in a single config module that both the live path and the backtest path import — there is no second place these values could be set
  3. A `pytest` suite covers the stake-sizing function (`beregn_innsats`) and the bet-dedup logic, and passes
  4. A parity/leakage regression test proves the live path and the backtest path produce an identical bet decision for the same historical date/game

**Plans**: 6 plans

Plans:
**Wave 1**

- [x] 02-01-PLAN.md — Pre-flight safety gate: working-tree WIP disposition, debug_kamp.py tracking decision (checkpoints only)

**Wave 2** *(blocked on Wave 1)*

- [x] 02-02-PLAN.md — CORE-02/CORE-03: pytest harness (pytest.ini, requirements-dev.txt, tests/) and config.py single source of truth

**Wave 3** *(blocked on Wave 2)*

- [x] 02-03-PLAN.md — CORE-01/CORE-03: strategy.py (vig, value/EV, half-Kelly, dedup key) + money-math unit tests; 04 and 06 rewired

**Wave 4** *(blocked on Wave 3)*

- [x] 02-04-PLAN.md — CORE-01: teams.py canonical resolver replacing four duplicates; 04, 05, 06 (+ debug_kamp.py per decision) rewired

**Wave 5** *(blocked on Wave 4)*

- [x] 02-05-PLAN.md — CORE-01: features.py with as_of-aware rolling-window computation and single stat list; 02 and 04 rewired, golden-file regression

**Wave 6** *(blocked on Wave 5)*

- [x] 02-06-PLAN.md — CORE-04: determinism/leakage regression test (scoped per D-12) + repo-wide de-duplication audit and VALIDATION.md close-out

Plans are strictly sequential (waves 1-6): every plan commits against one shared git index, and `05_skadefilter.py`/`06_bot.py` carry ~1100 lines of the developer's uncommitted work, so concurrent staging is unsafe. Plans 03, 04 and 05 additionally all edit `04_value_detector.py`, which forces sequencing on file ownership alone.

### Phase 3: Calibration Remediation

**Goal**: The model's probability calibration is fit and validated on data it never touched during fitting, closing a confirmed same-slice leakage bug that has been producing optimistically biased "value" signals.
**Depends on**: Phase 2
**Requirements**: CALIB-01, CALIB-02
**Success Criteria** (what must be TRUE):

  1. The isotonic calibrator is fit on a calibration split that is disjoint from both the training data and the final evaluation/test data — a proper three-way train/calibrate/test split is visible in the training code
  2. An out-of-sample calibration curve / reliability diagram is generated and reported using only the held-out test slice the calibrator never saw during fitting

**Plans**: TBD

### Phase 4: Historical Odds Acquisition & Live Refactor

**Goal**: Historical odds needed for backtesting are fetched once and archived permanently so further backtest iteration costs no additional API credits, and the live bot runs on the exact same shared core the backtest will use.

**Decision point (phase entry):** The Odds API's free tier (500 credits) is not enough for a full-season historical backtest; the paid tier (~$30/mo for 20K credits) is needed. This has not been decided yet. Confirm the budget decision before starting the historical-odds-fetch work in this phase — it does not block starting the live-refactor half of this phase (ODDS-02), which has no API-cost dependency.

**Depends on**: Phase 3
**Requirements**: ODDS-01, ODDS-02
**Success Criteria** (what must be TRUE):

  1. Historical odds for the target date range are fetched via The Odds API's per-event historical endpoint and persisted permanently in SQLite; re-running the fetch for an already-archived date/event consumes zero additional API credits
  2. `06_bot.py` calls into the shared core (`features.py`/`strategy.py`/`teams.py`) directly instead of invoking `04_value_detector.py`/`05_skadefilter.py` as subprocesses
  3. The SQLite archive can be queried to reconstruct "odds as known on date D" for any archived event, independent of the live API

**Plans**: TBD

### Phase 5: Walk-Forward Backtest Engine

**Goal**: The full betting decision pipeline (model score → value threshold → odds filter → injury filter → half-Kelly stake) can be replayed chronologically against archived historical odds, producing reproducible, leakage-safe ROI/drawdown/CLV evidence gated by a locked holdout — the project's actual Core Value deliverable.
**Depends on**: Phase 4
**Requirements**: BT-01, BT-02, BT-03, BT-04, BT-05, BT-06, BT-07
**Success Criteria** (what must be TRUE):

  1. A walk-forward backtest run replays model score → value threshold → odds filter → injury filter → half-Kelly stake chronologically across the existing 2022-23 through 2024-25 data using archived historical odds
  2. Every data point pulled into the replay (odds, injury status, rolling stats) is provably filtered to "known as of date D" — the code structurally prevents post-decision-time information from entering the loop
  3. A locked, never-touched final holdout slice is checked exactly once, after all threshold/parameter decisions are frozen on the train/calibrate data — enforced by the code, not just convention
  4. A backtest run produces a reproducible, versioned run manifest (config + date range + ROI + win rate + max drawdown + bet count + confidence interval), enabling a clear before/after comparison against the current losing live configuration
  5. Closing Line Value (CLV) is reported per bet and in aggregate, and a Kelly-fraction sensitivity sweep (flat/quarter/half/full) shows how sensitive reported ROI is to the staking assumption

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Repo Hygiene & Config Remediation | 5/5 | Complete    | 2026-08-20 |
| 2. Shared Core Extraction & Test Foundation | 6/6 | Complete    | 2026-08-21 |
| 3. Calibration Remediation | 2/2 | Complete   | 2026-08-23 |
| 4. Historical Odds Acquisition & Live Refactor | 0/TBD | Not started | - |
| 5. Walk-Forward Backtest Engine | 0/TBD | Not started | - |
