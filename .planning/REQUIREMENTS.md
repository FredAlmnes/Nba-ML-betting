# Requirements: NBA Value Betting Bot

**Defined:** 2026-08-19
**Core Value:** The bot must demonstrate a positive, validated ROI over a proper historical backtest before it's trusted with anything beyond paper trading.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Hygiene (repo cleanup, blocks everything else)

- [x] **HYG-01**: The Odds API key is loaded from an environment variable (not hardcoded in source) and the previously-exposed key is rotated
- [x] **HYG-02**: `modell_utils.py` is tracked in git so a fresh clone can unpickle `nba_modell.pkl` without breaking
- [ ] **HYG-03**: The documented fix in `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` is reconciled with the running code — either applied, or explicitly superseded once backtest-validated values exist, so docs and running config never silently diverge again

### Shared Core (prevents a third instance of the drift that already happened twice)

- [ ] **CORE-01**: Feature engineering, team-name resolution, and value/stake strategy logic are extracted into shared modules (`features.py`, `strategy.py`, `teams.py`) imported identically by both the live path and the backtest path — no duplicate implementations
- [ ] **CORE-02**: Strategy parameters (`MIN_VALUE_TERSKEL`, `MAX_ODDS`, Kelly fraction) live in a single source-of-truth config imported by both live and backtest, so a backtest always validates what's actually deployed
- [ ] **CORE-03**: Unit tests cover the stake-sizing function (`beregn_innsats`) and bet-dedup logic — first automated tests in this repo
- [ ] **CORE-04**: A parity/leakage regression test confirms the live path and backtest path produce an identical decision for the same historical date/game

### Calibration Remediation (fixes a confirmed live bug)

- [ ] **CALIB-01**: The isotonic calibrator is fit and evaluated using a proper train/calibrate/test three-way split, not the same data slice for both fitting and evaluation
- [ ] **CALIB-02**: An out-of-sample calibration curve / reliability diagram is reported on held-out data the calibrator never saw

### Historical Odds & Live Refactor

- [ ] **ODDS-01**: Historical odds are fetched via The Odds API's per-event historical endpoint and archived permanently in SQLite, so re-running/iterating on the backtest costs no further API credits
- [ ] **ODDS-02**: `06_bot.py` imports the shared core directly instead of invoking `04_value_detector.py`/`05_skadefilter.py` as subprocesses

### Backtest Engine (the core deliverable)

- [ ] **BT-01**: A walk-forward, chronological replay simulates the full decision pipeline (model score → value threshold → odds filter → injury filter → half-Kelly stake) against historical odds, using existing 2022-23 through 2024-25 data plus the historical odds endpoint
- [ ] **BT-02**: All data pulled into the replay (odds, injury status, rolling stats) is filtered to "known as of date D" — no post-decision-time information anywhere in the loop
- [ ] **BT-03**: A locked, never-touched final holdout slice exists and is checked exactly once, after all threshold/parameter decisions are frozen on the train/calibrate data
- [ ] **BT-04**: ROI, win rate, and max drawdown are reported on the flagged-bet subset only, with bet count and a confidence interval attached to every headline number
- [ ] **BT-05**: Each backtest run produces a reproducible, versioned run manifest (config + date range + metrics), enabling a clear before/after comparison against the current losing live configuration
- [ ] **BT-06**: Closing Line Value (CLV) is tracked per bet and in aggregate, as a faster-converging signal of genuine edge than raw ROI
- [ ] **BT-07**: A Kelly-fraction sensitivity sweep (flat / quarter / half / full) shows how sensitive reported ROI is to the staking assumption, validating whether half-Kelly is actually the right choice

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Backtest Diagnostics

- **BTV2-01**: Threshold/odds-range grid search, structurally gated so it can never touch the locked holdout
- **BTV2-02**: Static HTML backtest report (equity curve, calibration plot, CLV chart) reusing the existing dashboard pattern
- **BTV2-03**: Error-slice breakdown (ROI by odds bucket, home/away, rest days) to support root-cause investigation
- **BTV2-04**: Retrain-cadence experiments (monthly vs. seasonal retraining)
- **BTV2-05**: Automated paper-trading vs. backtest reconciliation tooling

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Real-money betting / live wagering | Hard gate — not until backtest + sustained paper-trading show positive ROI with a statistically meaningful sample |
| Spread and totals markets | v1 stays moneyline-only to keep validation focused on one strategy at a time; can expand once moneyline is proven |
| Multi-user / hosted service | Single-user personal tool, not a product |
| Generalized multi-sport/multi-market backtesting framework | Would delay validating the one strategy actually at stake; build scoped to what exists today |
| In-sample threshold/parameter tuning without a locked holdout | Anti-pattern — this is exactly how the current losing thresholds were arrived at; the whole point of BT-03 is to prevent repeating it |

**Open budget decision:** A full-season historical backtest needs The Odds API's paid tier (~$30/mo for 20K credits) — the free 500-credit tier isn't enough. Not yet decided; flagged for a decision at the start of the Historical Odds Acquisition phase (see ODDS-01).

## Traceability

Populated during roadmap creation. See .planning/ROADMAP.md for phase details.

| Requirement | Phase | Status |
|-------------|-------|--------|
| HYG-01 | Phase 1 | Complete |
| HYG-02 | Phase 1 | Complete |
| HYG-03 | Phase 1 | Pending |
| CORE-01 | Phase 2 | Pending |
| CORE-02 | Phase 2 | Pending |
| CORE-03 | Phase 2 | Pending |
| CORE-04 | Phase 2 | Pending |
| CALIB-01 | Phase 3 | Pending |
| CALIB-02 | Phase 3 | Pending |
| ODDS-01 | Phase 4 | Pending |
| ODDS-02 | Phase 4 | Pending |
| BT-01 | Phase 5 | Pending |
| BT-02 | Phase 5 | Pending |
| BT-03 | Phase 5 | Pending |
| BT-04 | Phase 5 | Pending |
| BT-05 | Phase 5 | Pending |
| BT-06 | Phase 5 | Pending |
| BT-07 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 18 total
- Mapped to phases: 18/18
- Unmapped: 0 ✓

---
*Requirements defined: 2026-08-19*
*Last updated: 2026-08-19 after roadmap creation*
