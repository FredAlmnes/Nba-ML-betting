# Requirements: NBA Value Betting Bot

**Defined:** 2026-08-19
**Core Value:** The bot must demonstrate a positive, validated ROI over a proper historical backtest before it's trusted with anything beyond paper trading.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Hygiene (repo cleanup, blocks everything else)

- [x] **HYG-01**: The Odds API key is loaded from an environment variable (not hardcoded in source) and the previously-exposed key is rotated
- [x] **HYG-02**: `modell_utils.py` is tracked in git so a fresh clone can unpickle `nba_modell.pkl` without breaking
- [x] **HYG-03**: The documented fix in `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` is reconciled with the running code — either applied, or explicitly superseded once backtest-validated values exist, so docs and running config never silently diverge again

### Shared Core (prevents a third instance of the drift that already happened twice)

- [x] **CORE-01**: Feature engineering, team-name resolution, and value/stake strategy logic are extracted into shared modules (`features.py`, `strategy.py`, `teams.py`) imported identically by both the live path and the backtest path — no duplicate implementations
- [x] **CORE-02**: Strategy parameters (`MIN_VALUE_TERSKEL`, `MAX_ODDS`, Kelly fraction) live in a single source-of-truth config imported by both live and backtest, so a backtest always validates what's actually deployed
- [x] **CORE-03**: Unit tests cover the stake-sizing function (`beregn_innsats`) and bet-dedup logic — first automated tests in this repo
- [x] **CORE-04**: A parity/leakage regression test confirms the live path and backtest path produce an identical decision for the same historical date/game

### Calibration Remediation (fixes a confirmed live bug)

- [x] **CALIB-01**: The isotonic calibrator is fit and evaluated using a proper train/calibrate/test three-way split, not the same data slice for both fitting and evaluation
- [x] **CALIB-02**: An out-of-sample calibration curve / reliability diagram is reported on held-out data the calibrator never saw

### Historical Odds & Live Refactor

- [x] **ODDS-01**: Historical odds are fetched via The Odds API's sport-wide historical endpoint (`/v4/historical/sports/{sport}/odds`), one call per unique game date, and archived permanently in SQLite, so re-running/iterating on the backtest costs no further API credits (endpoint amended 2026-08-23 per Phase 4 D-03 — both endpoints cost 10 x markets x regions, but per-event charges per game queried; sport-wide charges once per snapshot). Persistence layer (`odds.py`'s SQLite archive) done in 04-01; timestamp/date logic and the offline snapshot-to-row parser (`parse_snapshot_til_rader`) done in 04-03; the HTTP client (`hent_live_odds`, `hent_historisk_odds_snapshot`, `hent_historiske_events`, retrying `_utfor_kall`, credit-safe by construction) done in 04-04; the resumable, credit-ceiling-enforced backfill driver (`kjor_backfill`) and its dry-run-by-default CLI (`07_hent_historisk_odds.py`) done in 04-05; the paid smoke test and human-approved credit ceilings done in 04-07; `04_value_detector.py`'s live-bot rewire done in 04-06/04-08. **Completed in 04-09:** full 480/480-date archive for both `bet_time` and `closing` snapshot types (17,710 credits spent, 2,289 remaining), documented in `04-ARKIV-RAPPORT.md` — a data-integrity bug found by the plan's own acceptance check (2 of 3,645 closing games had a post-tipoff snapshot mislabeled as a closing line) was fixed in `parse_snapshot_til_rader` and the corrupted rows removed; those 2 games remain a named closing-line gap.
- [x] **ODDS-02**: `06_bot.py` imports the shared core directly instead of invoking `04_value_detector.py`/`05_skadefilter.py` as subprocesses. Injury-filter half (`skadefilter.py`, importable with zero import-time network calls) done in 04-02; value-detector half (`verdi_deteksjon.py`, importable, live odds sourced from `odds.hent_live_odds`, zero import-time side effects) done in 04-06; `06_bot.py`'s in-process wiring (subprocess/`python3.10`-`PYTHONPATH` removal, explicit `except (Exception, SystemExit)` crash barrier) done in 04-08, proven safe by a real, developer-approved end-to-end daily run.

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

**Open budget decision:** RESOLVED 2026-08-23: A full-season historical backtest needs The Odds API's paid tier (~$30/mo for 20K credits) — the free 500-credit tier isn't enough. The user purchased one month of the 20,000-credit tier on 2026-08-23, unblocking ODDS-01 (originally flagged for a decision at the start of the Historical Odds Acquisition phase).

## Traceability

Populated during roadmap creation. See .planning/ROADMAP.md for phase details.

| Requirement | Phase | Status |
|-------------|-------|--------|
| HYG-01 | Phase 1 | Complete |
| HYG-02 | Phase 1 | Complete |
| HYG-03 | Phase 1 | Complete |
| CORE-01 | Phase 2 | Complete |
| CORE-02 | Phase 2 | Complete |
| CORE-03 | Phase 2 | Complete |
| CORE-04 | Phase 2 | Complete |
| CALIB-01 | Phase 3 | Complete |
| CALIB-02 | Phase 3 | Complete |
| ODDS-01 | Phase 4 | Complete (9/9 plans — full 480/480-date archive for bet_time and closing, 17,710 credits spent, see `04-ARKIV-RAPPORT.md`) |
| ODDS-02 | Phase 4 | Complete |
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
