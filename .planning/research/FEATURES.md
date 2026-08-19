# Feature Research

**Domain:** Sports value-betting strategy backtesting & validation (NBA moneyline)
**Researched:** 2026-08-19
**Confidence:** MEDIUM-HIGH (domain concepts are well-established quant/betting theory, verified against multiple independent sources; specifics of this codebase's implementation are HIGH from direct file review)

## Feature Landscape

### Table Stakes (A Backtest Is Not Trustworthy Without These)

These aren't "nice to have" — without them the backtest number is meaningless or actively misleading, which is exactly the failure mode that produced the current unvalidated `MIN_VALUE_TERSKEL`/`MAX_ODDS` values.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Chronological, walk-forward replay of the full decision pipeline (model → value threshold → odds filter → injury filter → Kelly stake) against historical odds | A backtest that only scores model accuracy (as `03_tren_modell.py` does today) never tests the actual betting decision. The strategy = model + threshold + filters + staking, and all of it must be replayed together, in date order, using only information available before tip-off | HIGH | This is the core missing piece per PROJECT.md. Must reuse (not reimplement) the exact feature-engineering and value-scoring logic currently duplicated between `02_feature_engineering.py` and `04_value_detector.py` — backtesting on a third, slightly-different copy of that logic would invalidate the result |
| Point-in-time / leakage-safe data assembly | The rolling-window features already use `shift(1)` correctly (`02_feature_engineering.py:89-95`), but a backtest introduces new leakage surfaces: pulling injury status "as of" a date, pulling odds "as of" a date (not the closing/final line), and pulling season-to-date roster/rotation data that didn't exist yet | HIGH | Any field pulled for backtest day D must be filterable to "known as of D," not "known today." This is the single most common way sports-betting backtests silently cheat |
| Historical odds at the time of the (would-be) bet, not just final/closing odds | The Odds API's historical endpoint returns odds snapshots; the backtest must bet against the snapshot closest to when the live bot would actually have placed the bet (e.g., morning-of), not the closing line, or ROI will be inflated/deflated in an unrealistic direction | MEDIUM | Confirms PROJECT.md's plan to use The Odds API historical endpoint. Snapshot timing choice must be documented and consistent with how `06_bot.py` actually runs (once daily) |
| Walk-forward (rolling-origin) train/calibrate/test splits — never a single static train/test split reused for both model selection and strategy validation | A model retrained naively on all history before backtesting looks great in-sample but was never actually "future-blind" at each decision point; single fixed splits also can't catch season-to-season drift (roster turnover, rule changes) | HIGH | Directly fixes the CONCERNS.md leakage bug where the isotonic calibrator is fit and evaluated on the same slice (`03_tren_modell.py:143-147`). Needs a proper 3-way split (train / calibrate / test) repeated across multiple rolling windows, not one holdout |
| Held-out final validation set that is *never* touched during threshold/parameter selection | This is the direct fix for the root problem described in PROJECT.md: `MIN_VALUE_TERSKEL`, `MAX_ODDS`, and Kelly fraction were "guessed/hand-tuned" with no separation between the data used to pick them and the data used to report results | HIGH | Requires discipline as much as code: e.g. last N months (or last full season) locked away, touched exactly once, after all threshold/parameter decisions are frozen |
| Realistic execution assumptions (vig-removed implied probability already exists; also need bet-not-filled/line-moved handling, and no assumption of getting the best line across books) | `04_value_detector.py` already normalizes for vig — a backtest must also acknowledge that historical "available" odds may not represent what would have actually been bettable (limits, market moves between decision and bet placement) | MEDIUM | Even a simple, clearly-stated assumption ("we always get the snapshot odds") is fine as long as it's explicit and consistent, not silently optimistic |
| ROI / profit-and-loss reporting on the flagged bet subset only (not all games) | The strategy only ever bets when the value threshold fires; reporting must reflect P&L on actual bets placed under the strategy, sized with the real staking rule (half-Kelly), not a flat-stake proxy that hides sizing risk | LOW-MEDIUM | Should mirror `06_bot.py`'s existing bankroll/bet-ledger data structures so the backtest and live paper-trading numbers are directly comparable |
| Closing Line Value (CLV) tracking | Positive CLV (bets consistently beating where the market closed) is widely regarded as the most reliable *leading* indicator of a genuine edge, because it converges on statistical significance far faster than raw ROI, which needs a large sample to separate skill from variance | MEDIUM | Requires storing the closing-line odds per historical game (from the same historical odds endpoint) alongside the bet-time odds. Should be reported per-bet and in aggregate |
| Calibration curves / reliability diagrams evaluated out-of-sample | The model's whole edge depends on `P(win)` estimates being trustworthy at the exact probability ranges being bet (e.g., 55-65%); a reliability diagram fit and shown on the same data it was calibrated on (current bug per CONCERNS.md) is not evidence of anything | MEDIUM | Bucket predicted probability into bins (e.g. deciles) and plot/report actual win rate per bin against a disjoint holdout; a systematic over/under-confidence pattern directly explains why "value" bets lose |
| Drawdown and variance analysis (not just final ROI) | A single ending-bankroll number hides whether the path was a smooth compounding curve or one huge swing; max drawdown and the shape of the equity curve are what tell you if a strategy is survivable with real money and real psychology | MEDIUM | Report max drawdown %, time-to-recovery, and the equity curve, not just terminal ROI. An unusually smooth curve is itself a red flag for overfitting, not a good sign |
| Sample-size / statistical-significance framing on every headline number | A 60% win rate over 20 bets and over 2,000 bets mean completely different things; reporting "N bets, X% CI" prevents both false confidence and false failure conclusions from a single season of NBA data (~1,230 games/season, and only a subset will clear the value threshold) | LOW-MEDIUM | Simple: report bet count alongside every ROI/win-rate figure and a basic confidence interval (e.g., Wilson interval on win rate, or bootstrap CI on ROI) |
| Bet-sizing sensitivity analysis (Kelly fraction sweep) | Kelly sizing is extremely sensitive to probability-estimation error — a model that's off by a few points on true win probability can cause full Kelly to over-bet by ~80%; the project already uses half-Kelly, but that choice has never been validated against the backtest | MEDIUM | Backtest the same bet sequence at multiple stake schemes (flat stake, quarter/half/full Kelly, capped Kelly) to show how sensitive the reported ROI is to the sizing assumption — a strategy that's only profitable at unrealistically aggressive sizing is not a real edge |
| Reproducible, versioned backtest runs | To compare "before fix" vs "after fix" (explicitly required by PROJECT.md: "clear before/after evidence... that the rebuilt/fixed system beats the current losing baseline"), each backtest run needs a recorded config snapshot (threshold values, odds range, Kelly fraction, model version, date range) alongside its output | LOW-MEDIUM | Doesn't need a full experiment-tracking platform — a JSON/CSV run manifest per backtest is enough given this is a single-user project, consistent with the existing JSON-ledger pattern in `06_bot.py` |

### Differentiators (Valuable, Not Required to Trust the Backtest)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Backtest report as a static HTML page (equity curve, calibration plot, CLV chart) | The project already generates a self-contained `dashboard.html` (`06_bot.py::generer_dashboard`) — extending that pattern to a backtest report keeps tooling consistent and gives an at-a-glance validation artifact instead of only console text | LOW-MEDIUM | Reuse existing charting approach in `06_bot.py` rather than adding a new visualization dependency |
| Feature-importance / error-slice breakdown (e.g., ROI by odds bucket, by home/away, by rest days, by back-to-backs) | Helps the "root-cause investigation" PROJECT.md explicitly asks for — distinguishes "the model is fine but the threshold is wrong" from "the model has no edge in a specific game context" | MEDIUM | Natural extension once the backtest ledger exists — just group-by on the same output data, no new pipeline needed |
| Walk-forward re-training cadence experiment (e.g., retrain monthly vs. once per season) | NBA rosters/form drift within a season (trades, injuries accumulating, tanking at season end); testing retrain frequency could reveal the static, train-once model is stale by backtest time | MEDIUM-HIGH | Only worth doing after the basic walk-forward backtest exists and shows a stable-vs-unstable edge over time |
| Multiple-threshold / multiple-strategy comparison in one backtest run (e.g., sweep `MIN_VALUE_TERSKEL` and `MAX_ODDS` and show a heatmap of ROI) | Turns "guessed/hand-tuned" threshold selection (the exact problem flagged in PROJECT.md) into a data-driven grid search — as long as the *final* number is validated on the untouched holdout, not the sweep itself | MEDIUM | Must be paired with the "no in-sample threshold tuning" anti-feature discipline below, or this becomes the overfitting trap it's meant to prevent |
| Automated "before vs after" comparison report | Directly satisfies PROJECT.md's requirement for "clear before/after evidence" — a small script/report that diffs two backtest run manifests and their headline metrics | LOW | Cheap once the run-manifest table stake exists |
| Paper-trading vs. backtest reconciliation check | Compares the bot's live paper-trading ledger (`bets.json`) against what the backtest would have predicted for the same dates/games, to catch drift between "what the backtest simulates" and "what the live pipeline actually does" (e.g., the exact kind of code/doc drift CONCERNS.md already found once) | MEDIUM | High value given this project's history of live code silently diverging from documented intent |

### Anti-Features (Things to Deliberately NOT Build/Do)

| Feature/Practice | Why It's Tempting | Why It's Problematic | Alternative |
|---|---|---|---|
| In-sample threshold/parameter tuning ("try `MIN_VALUE_TERSKEL` values until ROI looks good on the full historical set") | Fast, and it's exactly how the current thresholds were arrived at (per PROJECT.md, "guessed/hand-tuned") | This is textbook overfitting to noise — a threshold picked because it happened to work on 2-3 seasons of specific games will not generalize; it's the most common single cause of live-vs-backtest performance gaps | Pick thresholds via walk-forward cross-validation on a train/calibrate slice, then confirm ONCE on a locked, never-before-touched holdout. If the holdout disagrees, the answer is "no validated edge yet," not "try another threshold" |
| Optimizing to a single hero backtest number without out-of-sample confirmation | A great final ROI is satisfying and easy to report | An "unusually smooth equity curve" or suspiciously high ROI is itself evidence of overfitting, not a good sign — real edges in efficient sports-betting markets are typically thin | Always report the holdout-only result as the headline number, with the exploratory/tuning-set result labeled explicitly as such and never treated as validation |
| Using closing-line odds (or any post-decision-time data) for the odds side of the backtest | Closing lines are often more efficient/accurate than what's available at bet time, and are trivially available in a single historical fetch | This lets the model "beat" prices that were never actually available to bet against, silently inflating ROI — classic lookahead bias | Snapshot odds at (or just before) the same time-of-day the live bot actually runs, and only use closing-line data for the CLV *comparison* metric, never as the bet price itself |
| Backtesting only game outcomes / classification accuracy and calling it a "strategy backtest" | It's what already exists (`03_tren_modell.py`'s accuracy/log-loss/Brier on a holdout) and feels like validation | Model accuracy and betting profitability are different questions — a well-calibrated 55% model can still lose money against a threshold/staking rule that's wrong, and a slightly miscalibrated model can still be profitable at the right threshold. PROJECT.md explicitly calls this out as the current gap | Always backtest the full pipeline (model + threshold + filters + Kelly stake) end-to-end, using price and stake, not just win/loss classification |
| Treating a short backtest window (e.g., one season, or the ~30 bets currently in `bets.json`) as statistically conclusive proof of an edge or its absence | It's the only data available right now, and it's tempting to declare victory or failure quickly | With small samples, win-rate swings of many points are just noise; a "77.6% drawdown" or a "30% ROI" over a few dozen bets says almost nothing on its own about the true long-run edge | Always pair headline metrics with sample size and a confidence interval; treat small-sample backtest results as "directional, needs more data" rather than final verdicts. Multi-season backtests (2022-23 through 2024-25 data already exists per `01_hent_data.py`) should be the norm, not a single recent window |
| Full-Kelly (or aggressive) staking chosen because it maximizes backtest theoretical growth | Kelly-optimal sizing is mathematically "correct" if probabilities are exactly right, and it produces the best-looking backtest equity curve | Kelly sizing is extremely sensitive to probability-estimation error (an edge overestimated by a few points can mean betting ~2x too large), and real models are never perfectly calibrated — this directly risks real money later even if the backtest says otherwise | Backtest a Kelly-fraction sensitivity sweep (quarter/half/full) and prefer the more conservative fraction unless there's strong out-of-sample evidence the model's probabilities are trustworthy; quarter-Kelly is the common practitioner default for exactly this reason |
| Re-fitting the calibrator (isotonic regression) on the same data used to evaluate it | Simpler to code, and it's the existing bug flagged in CONCERNS.md | Produces optimistically biased calibration metrics that don't reflect real-world behavior — directly undermines trust in the "value" signal the whole strategy depends on | Three-way split: train model → fit calibrator on a disjoint calibration slice → evaluate both on a further disjoint test slice, repeated across walk-forward windows |
| Building a generalized, multi-market, multi-sport, or web-hosted backtesting framework in this milestone | Feels like the "proper" way to build reusable infrastructure | Directly conflicts with PROJECT.md's explicit scope (moneyline-only NBA, single-user, no hosted service) and would delay validating the one strategy currently at stake | Build the backtest scoped to the exact pipeline that exists today (moneyline, NBA, this model); generalize later only if/when spreads/totals are actually added |
| Declaring the strategy "validated" the moment the backtest shows positive ROI, then immediately deploying real money | Backtest passing feels like the finish line | PROJECT.md's own gate requires backtest AND sustained paper-trading evidence — a backtest alone doesn't catch live-execution issues (line movement, filled odds, injury-data lag, API failures) that only paper trading surfaces | Treat backtest-positive as necessary but not sufficient: require a subsequent live/paper-trading period (see below) confirming the backtest's predicted edge shows up in real conditions before any real-money discussion |

## Feature Dependencies

```
[Point-in-time leakage-safe data assembly]
    └──requires──> [Walk-forward train/calibrate/test splits]
                       └──requires──> [Held-out final validation set]

[Chronological full-pipeline replay]
    └──requires──> [Point-in-time leakage-safe data assembly]
    └──requires──> [Historical odds at bet-time]
                       └──enables──> [Closing Line Value tracking]

[Chronological full-pipeline replay]
    └──enables──> [ROI/P&L reporting on flagged bets]
                       └──enables──> [Drawdown/variance analysis]
                       └──enables──> [Sample-size/CI framing]
                       └──enables──> [Bet-sizing sensitivity sweep]

[Held-out final validation set]
    └──enables──> [Trustworthy calibration curves / reliability diagrams]
    └──gates────> [Multiple-threshold sweep] (sweep must run on train/calibrate data,
                    final number confirmed once on holdout — NOT the reverse)

[Reproducible/versioned backtest runs]
    └──enables──> [Before/after comparison report]
    └──enables──> [Paper-trading vs. backtest reconciliation]

[Backtest showing positive, validated ROI]
    └──requires──> [Sustained subsequent paper-trading period confirming the edge]
                       └──gates──> [Any real-money discussion] (out of scope this milestone regardless)
```

### Dependency Notes

- **Chronological full-pipeline replay requires point-in-time data assembly:** without leakage-safe "as of date D" data (odds, injuries, rolling stats), the replay isn't actually simulating what the live bot would have known — it becomes a leakage exercise, not a backtest.
- **Held-out final validation set requires walk-forward splits to exist first:** the whole point of the holdout is that it's never touched during threshold/parameter search; the walk-forward train/calibrate loop is where all tuning happens, and the holdout is checked exactly once at the end.
- **Multiple-threshold sweep gates on the holdout, not the reverse:** this is the single most important ordering constraint in this milestone — building the sweep tool before the train/calibrate/holdout split exists would recreate the exact overfitting trap PROJECT.md is trying to fix.
- **CLV tracking requires historical bet-time odds AND a closing-line snapshot:** both must be pulled from The Odds API's historical endpoint; CLV is a diagnostic layered on top of the core replay, not a separate pipeline.
- **Positive backtest ROI does not, by itself, satisfy the "confident to risk small real money" bar:** per PROJECT.md's explicit gate, a subsequent live paper-trading confirmation period is still required — backtests can't capture live-only failure modes (API outages, odds not actually available, injury data lag).

## MVP Definition

### Launch With (v1 — minimum to make the backtest trustworthy)

- [ ] Walk-forward chronological replay of the full strategy (model score → value threshold → odds filter → injury filter → half-Kelly stake) against historical odds, using existing 2022-23 through 2024-25 data plus historical odds endpoint
- [ ] Point-in-time-safe feature/injury/odds assembly (no post-decision-time data anywhere in the loop)
- [ ] Train/calibrate/test three-way split (fixes the current same-data calibration leakage bug), repeated walk-forward across seasons
- [ ] A locked, never-touched final holdout slice for the one-time confirming run
- [ ] ROI, win rate, and max drawdown reported on the flagged-bet subset, with bet count and a basic confidence interval attached to every headline number
- [ ] Out-of-sample calibration curve / reliability diagram on the holdout
- [ ] Reproducible run manifest (config + date range + metrics) per backtest execution, enabling a before/after comparison against the current losing live configuration

### Add After Validation (v1.x)

- [ ] Closing Line Value tracking per bet and in aggregate — add once the core replay is trustworthy, as a faster-converging confirmation signal than ROI alone
- [ ] Kelly-fraction sensitivity sweep (flat / quarter / half / full) — add once a baseline validated ROI exists to sweep around
- [ ] Threshold/odds-range grid search — add only after the train/calibrate vs. holdout split is enforced in tooling, so sweeps structurally cannot touch the holdout
- [ ] Static HTML backtest report (equity curve, calibration plot, CLV chart), reusing the existing dashboard pattern
- [ ] Error-slice breakdown (ROI by odds bucket, home/away, rest days) to support root-cause investigation

### Future Consideration (v2+)

- [ ] Retrain-cadence experiments (monthly vs. seasonal retraining) — defer until the basic backtest shows whether edge is stable or decaying over a season
- [ ] Automated paper-trading vs. backtest reconciliation tooling — defer until enough live paper-trading history accumulates post-fix to compare against
- [ ] Any real-money execution, spreads/totals markets, multi-user tooling — explicitly out of scope per PROJECT.md regardless of backtest results this milestone

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Chronological full-pipeline replay against historical odds | HIGH | HIGH | P1 |
| Point-in-time leakage-safe data assembly | HIGH | HIGH | P1 |
| Walk-forward train/calibrate/test splits | HIGH | HIGH | P1 |
| Locked final holdout validation | HIGH | LOW | P1 |
| ROI/drawdown/sample-size reporting | HIGH | MEDIUM | P1 |
| Out-of-sample calibration curves | HIGH | MEDIUM | P1 |
| Reproducible run manifests | MEDIUM | LOW | P1 |
| Closing Line Value tracking | MEDIUM | MEDIUM | P2 |
| Kelly-fraction sensitivity sweep | MEDIUM | MEDIUM | P2 |
| Threshold/odds-range grid search (holdout-gated) | MEDIUM | MEDIUM | P2 |
| Static HTML backtest report | LOW-MEDIUM | LOW | P2 |
| Error-slice breakdown | MEDIUM | LOW-MEDIUM | P2 |
| Retrain-cadence experiments | LOW-MEDIUM | HIGH | P3 |
| Paper-trading/backtest reconciliation | MEDIUM | MEDIUM | P3 |

**Priority key:**
- P1: Must have — without these the backtest cannot be trusted at all
- P2: Should have — meaningfully strengthens confidence and diagnostic power once P1 exists
- P3: Nice to have — deferred until the core validated backtest is in place and stable

## "Confident to Risk Small Real Money" — What's Actually Expected

Synthesizing the research, the transition from paper trading to small real-money stakes in the sports-betting-model space generally expects **all** of the following, not any single one in isolation:

1. **A walk-forward backtest with a positive, statistically meaningful edge on a never-touched holdout** (not the tuning set) — this is the baseline evidence requirement, and it's exactly what PROJECT.md's Core Value statement demands ("positive, validated ROI over a proper historical backtest").
2. **A large enough sample to distinguish skill from variance.** Rough industry heuristic: dozens of bets prove nothing; hundreds start to be suggestive; ~2,000+ bets at a given edge size is where win-rate differences of a couple points become statistically solid. NBA moneyline volume is naturally slow (~1,230 games/season, only a fraction clearing a value threshold), so this likely means multiple backtested seasons, not one.
3. **Positive Closing Line Value, not just positive ROI.** CLV is treated in the community as the earliest reliable signal because it doesn't require waiting for ROI variance to average out — if the strategy doesn't beat the closing line, ROI positivity in a backtest is more likely noise.
4. **A subsequent live paper-trading period that reproduces the backtest's expected edge** under real operational conditions (real API latency, real injury-report timing, real odds availability at decision time) — the backtest cannot fully substitute for this, because it can't capture execution-only failure modes.
5. **Conservative, not maximal, stake sizing** (e.g., quarter- or half-Kelly, matching the project's already-implemented half-Kelly default) precisely because probability estimates are never perfectly calibrated, and over-sized stakes turn a small real edge into a real risk of ruin.
6. **A stable edge across time/robustness checks** — the edge shouldn't have appeared only in one season or one narrow filter combination; if a walk-forward or seasonal breakdown shows the edge is unstable or decaying, that's a signal to keep it in paper trading longer, not proceed.

None of this changes the milestone's own hard gate already stated in PROJECT.md (no real-money betting until backtested + paper-traded evidence of positive ROI exists) — it just specifies what "evidence" needs to look like to be credible in this domain, rather than being another round of the same guesswork that produced the current losing thresholds.

## Sources

- [How to Backtest a Sports Betting Strategy Without Overfitting - Great Bets](https://www.greatbets.co.uk/how-to-backtest-a-sports-betting-strategy-without-overfitting/) — MEDIUM confidence (single independent source, cross-checked against others below)
- [Closing Line Value (CLV) Guide: Validate AI Betting Models](https://www.sports-ai.dev/blog/closing-line-value-and-ai-model-performance) — MEDIUM confidence
- [How to Backtest a Betting Model with Free Historical Odds (Python Tutorial) - OddsPapi](https://oddspapi.io/blog/backtest-betting-model-free-historical-odds/) — MEDIUM confidence
- [7 Mistakes You're Making with Overfitting Betting Models - Predictology](https://www.predictology.co/blog/7-mistakes-youre-making-with-overfitting-betting-models-and-how-to-fix-them/) — MEDIUM confidence
- [How to Avoid the Biggest Backtesting Pitfalls in Football Betting - Predictology](https://www.predictology.co/blog/how-to-avoid-the-biggest-backtesting-pitfalls-in-football-betting/) — MEDIUM confidence
- [Backtesting a Sports Betting Strategy - Estèphe, Systematic Sports (Medium)](https://medium.com/systematic-sports/backtesting-a-sports-betting-strategy-283833a5eca3) — MEDIUM confidence
- [8.3 The Dangers of Backtesting - Portfolio Optimization Book](https://portfoliooptimizationbook.com/book/8.3-dangers-backtesting.html) — MEDIUM-HIGH confidence (quantitative finance reference text, principles transfer directly to sports betting backtesting)
- [Sports Investing Statistical Significance - Sports Insights](https://www.sportsinsights.com/sports-investing-statistical-significance/) — LOW-MEDIUM confidence (single source for the specific sample-size heuristics cited; treat as directional, not precise)
- [Sample Size Requirements for Evaluating Betting Performance - SportBot AI](https://www.sportbotai.com/blog/sample-size-requirements-for-evaluating-betting-performance-1777204957633) — LOW-MEDIUM confidence
- [Why fractional Kelly? Simulations of bet size with uncertainty - Matthew Downey](https://matthewdowney.github.io/uncertainty-kelly-criterion-optimal-bet-size.html) — MEDIUM-HIGH confidence (simulation-backed, consistent with established Kelly-criterion literature)
- [Kelly Criterion Sports Betting: Bankroll Sizing Guide - Prediction Engine](https://predictionengine.app/learn/kelly-criterion-sports-betting) — MEDIUM confidence
- [Optimal sports betting strategies in practice: an experimental review (arXiv)](https://arxiv.org/pdf/2107.08827) — HIGH confidence (peer-reviewed/academic preprint)
- [Machine learning for sports betting: should model selection be based on accuracy or calibration? (arXiv)](https://arxiv.org/pdf/2303.06021) — HIGH confidence (academic preprint, directly supports the calibration-vs-accuracy distinction used above)
- Codebase review: `.planning/PROJECT.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONCERNS.md` — HIGH confidence (direct source inspection)

---
*Feature research for: sports value-betting strategy backtesting & validation (NBA moneyline)*
*Researched: 2026-08-19*
