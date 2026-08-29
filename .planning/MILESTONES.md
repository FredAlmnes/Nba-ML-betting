# Milestones

## v1.0 NBA Value Betting Bot MVP (Shipped: 2026-08-29)

**Phases completed:** 5 phases, 35 plans, 88 tasks
**Timeline:** 2026-08-19 → 2026-08-29 (10 days), 202 commits, 163 files changed (+41,956 / −957 lines)
**Tests:** 349 passing (0 at milestone start)

**Key accomplishments:**

- **Phase 1 — Repo hygiene:** rotated a leaked Odds API key into a git-ignored `.env`, tracked the previously-untracked `modell_utils.py` so a fresh clone can unpickle the model, and reconciled a stale calibration report against the actually-running config.
- **Phase 2 — Shared core extraction:** consolidated feature engineering, team-name resolution, and value/stake math — each previously duplicated 2-4x across the pipeline — into single tested modules (`features.py`, `strategy.py`, `teams.py`, `config.py`), backed by the repo's first automated test suite.
- **Phase 3 — Calibration fix:** closed a confirmed same-slice leakage bug where the isotonic calibrator was fit and evaluated on the same data, by splitting train/calibrate/test into disjoint slices with regression-guard tests.
- **Phase 4 — Historical odds & live refactor:** archived all 480 NBA game dates (2022-10-24 to 2025-04-13) for both bet-time and closing odds — 187,376 rows, 17,710 API credits spent — and rewired `06_bot.py` off subprocess shell-outs onto the shared core in-process.
- **Phase 5 — Walk-forward backtest engine (the Core Value deliverable):** built a chronological, leakage-safe replay of the full betting decision pipeline with a structurally single-entry holdout guard; discovered and fixed a real isotonic-calibration degeneracy bug along the way (small walk-forward windows were saturating probabilities to 1.0 for up to 38% of bets).
- **The one-shot 2024-25 holdout was spent** under a frozen configuration (0.20 value threshold, 2.50 max odds, flat staking): **19 bets, ROI -25.0%, 95% CI [-64.5%, +24.6%]** — an honest result that does not validate a positive edge. Core Value gate verdict: **"Ikke avgjort" (undecided)**. This is a correct, working measurement instrument reporting an inconclusive answer, not a failed milestone.

---
