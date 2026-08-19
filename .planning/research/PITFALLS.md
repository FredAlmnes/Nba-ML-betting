# Pitfalls Research

**Domain:** Sports-betting / quant-style value-betting system (NBA moneyline, Python, XGBoost + isotonic calibration, half-Kelly staking, single-user paper trading)
**Researched:** 2026-08-19
**Confidence:** MEDIUM-HIGH (backtesting/Kelly/CLV/calibration pitfalls verified against multiple independent sources; project-specific pitfalls verified directly against this codebase's `.planning/codebase/CONCERNS.md` and `ARCHITECTURE.md`, several of which are not hypothetical — they already happened)

## Critical Pitfalls

### Pitfall 1: In-sample threshold tuning that curve-fits the backtest

**What goes wrong:**
Strategy parameters (`MIN_VALUE_TERSKEL`, `MAX_ODDS`, `MIN_ODDS`, `KELLY_FRAKSJON`) get adjusted repeatedly against the *same* historical odds/results dataset until the backtest ROI curve looks good, then those exact values get shipped to production. The backtest ROI is no longer measuring "does this strategy have edge" — it's measuring "how well did I fit noise in this specific historical window." This is the single most common way quant/betting projects go from "backtested +15% ROI" to "live -60% ROI."
This project is at elevated risk because it already lived through one iteration of exactly this pattern without even knowing it: `KALIBRERING_RAPPORT.md` describes a backtest-driven threshold change (`MIN_VALUE_TERSKEL` 0.05→0.20, `MAX_ODDS` 4.00→2.50) that was never even deployed, meaning the *only* evidence of "this fixes the problem" was an in-sample analysis that was never validated live.

**Why it happens:**
There's no walk-forward or held-out validation step separating "tune the threshold" from "confirm the threshold works." A single historical dataset gets reused for both discovery and confirmation, and with NBA moneyline data (~1,230 games/season, and a much smaller subset that clears any value threshold), it's very easy to find a value threshold, odds range, and Kelly fraction combination that happens to look profitable by chance — the "garden of forking paths" problem gets worse the more parameter combinations get tried.

**How to avoid:**
- Split historical odds/results data into three chronologically ordered slices: **tune** (find candidate thresholds), **validate** (confirm the winning combination out-of-sample, untouched during tuning), **final holdout** (touched exactly once, at the very end, to report the number that goes in the roadmap doc). Never move backward — a threshold rejected by validate cannot be re-tried against final holdout.
- Prefer walk-forward (rolling-origin) backtesting over a single train/test split: retrain/re-threshold on data up to date T, evaluate on T+1..T+k, roll forward. This mimics how the bot actually operates (constantly betting into the future) far better than one static split.
- Log every threshold combination tried during tuning, not just the winner — if 40 combinations were tried and 1 looked good, that's a strong overfitting signal even if the backtest report only shows the winner.
- Require a minimum sample size before trusting a backtest result: treat anything under ~300-500 *placed bets* (not games — bets that actually cleared the value filter) as statistically inconclusive, and say so explicitly in the backtest report rather than presenting a percentage as if it were reliable.
- Treat the backtest ROI number as an upper bound on real expected performance, not an estimate of it — live execution will always be somewhat worse (slippage, stale odds, filter gaps).

**Warning signs:**
- Backtest ROI looks "too good" (e.g., >20-30% per season) — real, sustained edges in a market as liquid as NBA moneyline are typically in the low single digits.
- The chosen threshold sits at a sharp local optimum (e.g., ROI at `MIN_VALUE_TERSKEL=0.20` is great but drops sharply at 0.18 or 0.22) rather than a broad plateau — sharp optima are a classic overfitting signature.
- The backtest report doesn't mention how many other threshold combinations were tried before landing on the reported one.
- Bet count behind the headline ROI number is small (tens, not hundreds).

**Phase to address:**
Backtesting framework phase — the tune/validate/holdout split and walk-forward structure must be built into the framework itself, not bolted on after a naive single-split backtest already exists.

---

### Pitfall 2: Look-ahead bias from historical odds data (backtesting against a line the bot could never have actually bet)

**What goes wrong:**
The Odds API's historical endpoint returns snapshots of odds at specific timestamps. If the backtest uses odds *closer to game time* than what a daily-run bot would realistically have captured (the bot runs once per day, likely well before tip-off), or uses a blended/best-available price across multiple snapshots, the backtest is pricing bets the bot could never have actually placed. Similarly, if the backtest doesn't filter out games/markets where liquidity or line availability was thin, it can "bet" into odds that were never really biddable.

**Why it happens:**
It's tempting to grab the most complete/accurate historical odds snapshot available (often the closing line, since it's the most information-rich) rather than reconstructing the exact snapshot timing that matches the bot's real daily cadence. The historical endpoint charges per request/snapshot, which also creates pressure to pull fewer, more convenient snapshots rather than the ones that are actually timing-accurate.

**How to avoid:**
- Pin backtest odds retrieval to the same time-of-day the live bot actually runs (e.g., "odds as of the daily cron run," not "odds 5 minutes before tip-off").
- Explicitly separate two different questions in the backtest report: (1) "would this strategy have beaten the closing line" (a CLV/edge-quality check, useful even with closing-line data) vs. (2) "would this strategy have made money placing bets at the time the bot actually runs" (the number that matters for going live). Don't conflate them.
- Record and report **closing-line value (CLV)** for every backtested bet in addition to raw ROI — CLV (vig-removed) is a much lower-variance signal of genuine edge than win/loss ROI over a short backtest window, and a strategy that's consistently entering at worse-than-average prices vs. the eventual close is unlikely to have real edge even if the ROI number happens to be positive.

**Warning signs:**
- Backtest ROI is strong but average CLV is flat or negative — a sign the ROI is a lucky sample, not real edge.
- Backtest and live pipelines pull odds through different code paths (they will inevitably drift in timing/snapshot semantics unless deliberately unified).

**Phase to address:**
Backtesting framework phase — snapshot timing and CLV tracking should be a first-class output of the backtest, not an afterthought bolted on after ROI is already being reported.

---

### Pitfall 3: Calibration metrics leak — evaluating the calibrator on the data it was fit on

**What goes wrong:**
This has **already happened in this codebase**: `03_tren_modell.py` fits the isotonic regressor with `kalibrerer.fit(y_rå, y_test)` and then evaluates it with `kalibrerer.predict(y_rå)` against the same `y_test` it was just fit on (`03_tren_modell.py:143-161`, per `CONCERNS.md`). The printed calibration log-loss/Brier scores and the calibration-bucket diagnostic table are therefore measuring how well the calibrator memorized its own fitting data, not how well-calibrated the model actually is out-of-sample. Every "value" signal downstream depends on this calibration being trustworthy — value = model-implied probability minus vig-free market probability — so an over-optimistic calibrator directly inflates the number of bets that look like value when they aren't.

**Why it happens:**
Isotonic regression is a nonparametric, highly flexible fit (a monotonic step function) — with a small holdout set (this project uses a 2-month time-based test slice), it's easy to fit and evaluate on the same slice without noticing, because the code "runs fine" and produces plausible-looking numbers. The failure mode is silent: no error, no crash, just optimistically biased metrics.

**How to avoid:**
- Use a proper three-way split: **train** (fit XGBoost) / **calibrate** (fit isotonic regressor, disjoint from train) / **test** (final, single-use evaluation of the calibrated model, disjoint from both). This matches sklearn's own recommendation that `CalibratedClassifierCV`-style calibration should always use cross-validation or a held-out calibration set distinct from the evaluation set.
- Isotonic regression needs a reasonably large calibration set (rule of thumb: >1,000 samples) to avoid overfitting to noise in the calibration slice; with less, prefer Platt scaling (logistic/sigmoid calibration) which has far fewer degrees of freedom and degrades more gracefully on small data. NBA has ~1,230 games/season, so a multi-season pooled calibration set is needed to safely use isotonic regression at all — a single-season slice is likely too small.
- Add a reliability diagram / calibration-bucket check computed on the *final held-out test set*, not the calibration set, and treat this as a required backtest output.

**Warning signs:**
- Calibration diagnostic numbers look "suspiciously perfect" (near-zero calibration error).
- Same variable name/dataframe used as both the argument passed to `.fit()` and to `.predict()`/`.transform()` for evaluation — this is exactly the bug already present at `03_tren_modell.py:143-147`.
- Model looks well-calibrated in training logs but the live "value" signal rate (fraction of games flagged as value bets) is much higher or lower than expected once deployed.

**Phase to address:**
Model/calibration remediation phase (root-cause investigation into why the current config underperforms) — this must be fixed before backtest results are trusted, since a biased calibrator will bias every backtest run downstream of it.

---

### Pitfall 4: Vig removal errors that manufacture fake "value"

**What goes wrong:**
"Value" is defined as model probability exceeding the market's *true* (vig-free) implied probability. If vig removal is done incorrectly — e.g., comparing the model probability directly against the raw implied probability (which sums to >100% because of the bookmaker's margin) instead of the normalized, vig-free probability — every bet looks artificially more valuable than it is, because part of the "edge" is just the bookmaker's margin being counted as free money. The simplest (and most commonly misapplied) vig-removal method is the equal-margin method (dividing each side's implied probability by the sum of both sides); this is a reasonable default but is known to be biased for favorites/longshots, and more accurate methods exist (odds-ratio, Shin's method, logarithmic method) that better reflect the true longshot bias baked into bookmaker pricing.

**Why it happens:**
Vig removal looks trivial (divide by the sum), so it's easy to implement once and never revisit, without checking it against a more accurate method or validating it against realized outcomes. It's also easy to accidentally skip vig removal at one point in the pipeline (e.g., the live scoring path) while applying it correctly in another (e.g., a backtest script written separately) — exactly the kind of duplicated-logic drift this codebase already has a documented pattern of (team-name lookup logic, feature engineering logic, both independently reimplemented in multiple files per `ARCHITECTURE.md`).

**How to avoid:**
- Implement vig removal exactly once, in a shared module, imported by both the live detector and the backtest framework — never reimplemented per-script (this project already has the pattern to avoid: `04_value_detector.py`, `05_skadefilter.py`, `06_bot.py` each independently reimplement team-lookup logic; don't repeat that mistake for vig removal).
- Default to the equal-margin method for simplicity, but validate it: compute vig-free CLV using the same method and confirm the sign/magnitude of "value" bets roughly correlates with positive CLV over the backtest period. If value bets systematically show negative CLV, the vig-removal method (or the model) is the problem, not just the threshold.
- For NBA moneyline specifically, watch for longshot bias — heavy favorites/underdogs are where equal-margin vig removal is least accurate, and this project's `MAX_ODDS`/`MIN_ODDS` range directly controls exposure to that region.

**Warning signs:**
- A disproportionate share of flagged "value" bets cluster at extreme odds (very heavy favorites or big underdogs) — a sign vig-removal bias rather than genuine model edge is driving the signal.
- Backtest ROI is positive but CLV is negative or flat (see Pitfall 2) — value is being manufactured by the vig calculation, not found by the model.

**Phase to address:**
Backtesting framework phase (shared vig-removal module) and model/calibration remediation phase (validating value-signal quality via CLV).

---

### Pitfall 5: Kelly staking errors amplify small edge-estimation mistakes into bankroll ruin

**What goes wrong:**
Kelly sizing is a direct function of the *estimated* edge, and edge estimates from a backtested/calibrated model are always somewhat noisy. Because Kelly stake size scales with the edge, a modest overestimate of true win probability (e.g., believing the model is 58% accurate on value bets when it's really 53%) produces a *much* larger overbet than the error in probability would suggest — this is the exact mechanism that turned this project's bankroll from 1000 kr to 74.88 kr under an unvalidated threshold config. Half-Kelly (already used here) roughly halves this risk but does not eliminate it: with a true edge close to zero (or negative, as apparently happened), even half-Kelly stakes compound losses fast, since Kelly-style position sizing bets *more* after wins and *proportionally* after losses, which is fine when the edge is real but accelerates ruin when it isn't.

**Why it happens:**
Kelly formulas are typically implemented once using whatever probability estimate is available at decision time, with no discount applied for estimation uncertainty in that probability, and no circuit breaker that reduces or halts staking when realized results diverge from what the model/backtest predicted.

**How to avoid:**
- Keep (or go further than) half-Kelly — consider quarter-Kelly during the initial live-validation period after backtesting, tightening to half-Kelly only once live results track backtest predictions for a meaningful sample.
- Cap maximum single-bet stake as a hard percentage of bankroll regardless of what Kelly math outputs (this project already has `MAX_INNSATS`/`MIN_INNSATS` caps — verify they're tight enough relative to the *validated* bankroll size, not left at values chosen under the old, unvalidated threshold config).
- Add a bankroll-drawdown circuit breaker: if the tracked bankroll drops below a defined threshold (e.g., -25% from the post-backtest starting point) within a rolling window, pause betting and require manual review rather than continuing to stake automatically — the current bot has no such circuit breaker, which is how it was allowed to run all the way down to 74.88 kr unnoticed.
- Unit test `beregn_innsats` (the Kelly stake-sizing function) directly: known probability/odds/bankroll inputs → known expected stake outputs, including edge cases (probability at or below the market-implied probability should never produce a positive stake).
- Backtest the Kelly staking layer itself, not just the value-detection layer — report max drawdown and time-to-recover from the backtest, not just final ROI, since a strategy can have positive final ROI while passing through a drawdown deep enough to have exhausted a real (or virtual) bankroll along the way.

**Warning signs:**
- Backtest report shows final ROI/bankroll but no drawdown curve or max-drawdown statistic.
- Live bankroll trajectory shows a small number of oversized bets responsible for a disproportionate share of losses.
- No automated stop-loss/circuit breaker exists between the staking function and the persisted bankroll state.

**Phase to address:**
Backtesting framework phase (report drawdown, not just ROI) and staking/config remediation phase (circuit breaker, stake caps validated against backtest-derived bankroll assumptions, unit tests on `beregn_innsats`).

---

### Pitfall 6: Documented fixes silently never deployed ("config drift" between docs and running code)

**What goes wrong:**
This has **already happened**: `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt` describe a specific remediation (raise `MIN_VALUE_TERSKEL` to 0.20, lower `MAX_ODDS` to 2.50, add `MIN_SIKKERHET`/`KALIBRERING_FAKTOR`) that was never applied to `04_value_detector.py`, which still runs the old, pre-fix values. Nobody caught this because there is no automated test asserting "the running config matches the documented/intended config," and no CI check comparing intended vs. actual threshold values. The user was not aware the fix had never shipped — the bot kept running the losing configuration for an unknown period while everyone believed the fix was live.

**Why it happens:**
In a project with no tests, no CI, and no code review step, a documented decision and the code that's supposed to implement it are two independent artifacts with nothing forcing them to stay in sync. Markdown reports describing "what should change" are easy to write and easy to leave uncommitted/unapplied, especially in a single-person, low-ceremony workflow where "I'll apply this later" silently becomes "never."

**How to avoid:**
- Treat strategy parameters (`MIN_VALUE_TERSKEL`, `MAX_ODDS`, `MIN_ODDS`, Kelly fraction, calibration factor) as version-controlled, single-source-of-truth config (e.g., a `strategy_config.py`/`.json`/`.yaml` file that's imported, not copy-pasted, into both the live detector and the backtest framework) rather than inline constants duplicated across scripts and described separately in prose reports.
- Add a lightweight automated check (even just a unit test) that asserts the live config matches whatever the most recent backtest validated — e.g., a test that loads the config and fails if it doesn't match a recorded "last validated" snapshot, forcing any config change to be a deliberate, visible diff.
- When a remediation report/plan is written, either apply it in the same commit or explicitly mark it as a proposal (not a completed change) with a checkbox/status field — don't leave "this was fixed" implied by a report's mere existence.
- Delete or archive stale reports once superseded (this project currently has two markdown reports describing a plan that doesn't match what's actually running — a trap for future readers, including future AI sessions, that will misattribute current behavior to a fix that was never applied).

**Warning signs:**
- A markdown/doc file describing a fix exists but is untracked in git (as with `ENDRINGER_SUMMARY.txt`/`KALIBRERING_RAPPORT.md` here) — untracked docs describing code changes are a strong signal the change itself may also be untracked/unapplied.
- Config values are defined as bare module-level constants with no single source of truth and no test asserting their values.
- Bankroll/results are trending in the direction a "known" fix should have prevented.

**Phase to address:**
Config/drift remediation phase — should be one of the first things fixed, before backtesting even begins, since backtest results are meaningless if they validate a config that isn't actually what's running live.

---

### Pitfall 7: Untracked runtime-critical files break reproducibility (already happened: `modell_utils.py`)

**What goes wrong:**
`modell_utils.py` — which defines `KalibrertModell`, required to unpickle `nba_modell.pkl` — is currently untracked in git. A fresh clone (or a scheduled/cron runner on a different machine, or a backtest framework that checks out the repo fresh) gets an immediate `ModuleNotFoundError` the moment it tries to load the model. This is exactly the kind of "works on my machine only" gap that silently breaks any attempt to run the backtest framework in a clean environment, or to reproduce past results.

**Why it happens:**
The file was likely created during iterative local development and never explicitly `git add`ed, and because the local machine always has it present, nothing ever surfaces the gap — it's invisible until a second environment (fresh clone, CI, another machine) is involved.

**How to avoid:**
- `git add modell_utils.py` and commit it now — this is a one-line, zero-risk fix already flagged as the single highest-priority non-security fix in `CONCERNS.md`.
- Add a basic "fresh clone smoke test" (can be as simple as a documented manual step, or a CI job) that clones the repo to a clean directory and confirms the model can be loaded and a value-detection pass runs — this would have caught this issue immediately.
- Audit for other untracked-but-imported files the same way (`git status` review before considering the repo "reproducible").

**Warning signs:**
- `git status` shows `??` (untracked) next to any file that's `import`ed by a tracked file.
- Pickle/joblib files that depend on custom classes defined outside the standard library.

**Phase to address:**
Config/repo-hygiene remediation phase — trivial to fix, should be done immediately, ideally before the backtesting framework is built (the backtest framework will also need to unpickle the model).

---

### Pitfall 8: Train/serve skew from duplicated feature-engineering logic

**What goes wrong:**
The feature set (rolling-window stats, `DIFF_*` differential columns) is implemented twice: once in `02_feature_engineering.py` (offline/historical, used to build the training data) and once inline in `04_value_detector.py` (live/online, used to score today's games). If these two implementations ever diverge — a stat added, a rolling window changed, a column renamed — the model silently receives a differently-shaped or differently-computed feature vector at inference time than it was trained on. `XGBoost`/`sklearn` won't necessarily error (a `KeyError` might surface for missing columns, but subtly different values — e.g., a rolling window off by one game — will not error at all, just quietly produce wrong predictions). This directly threatens the validity of a backtesting framework too: if the backtest reuses `02`'s feature logic but live scoring uses `04`'s inline copy, the backtest is validating a strategy that isn't exactly the strategy running live.

**Why it happens:**
Splitting historical (batch, vectorized pandas) and live (per-game, small dataframe) feature computation into separate code paths feels natural because the data shapes are different (a whole historical CSV vs. one day's games), but the actual transformation logic (which stats, which window, which shift) should be identical and is not naturally forced to be.

**How to avoid:**
- Extract the feature-computation logic (stat list, rolling window size, shift/lag logic, `DIFF_*` construction) into a single shared function/module that both `02_feature_engineering.py` and `04_value_detector.py` — and the new backtest framework — import and call, parameterized by whether the input is a historical batch or a single day's slate.
- Add a regression test that runs both paths against a small shared fixture (a few known games) and asserts identical output feature vectors.
- When building the backtest framework, deliberately reuse the *live* scoring code path (not a third, separate backtest-only implementation) so the backtest is validating exactly what runs in production — a backtest framework that reimplements feature engineering a third time compounds this pitfall rather than fixing it.

**Warning signs:**
- Any change to `stats`/rolling-window/`DIFF_*` logic touches only one of `02_feature_engineering.py` / `04_value_detector.py`.
- Backtest results and live results diverge even when using the "same" model and thresholds — a sign the feature vectors going into the model aren't actually the same between the two paths.

**Phase to address:**
Backtesting framework phase (the framework should force this unification by reusing live scoring code) and general remediation phase (extract shared module).

---

### Pitfall 9: No test coverage on the money-math functions that directly control stakes and settlement

**What goes wrong:**
`beregn_innsats` (Kelly stake sizing), `plasser_bets` (bet dedup/staleness guard), and `sjekk_resultater` (win/loss grading) directly determine how much virtual money is risked and how it's tracked — and none of them have any automated test coverage. `06_bot.py` already has a documented instance of exactly this class of bug reaching production undetected: a stale-row bug in the pipeline caused already-processed bets to be re-bet, patched after the fact with a comment-only dedup guard (`06_bot.py:262-263`) rather than a fix at the source. A backtesting framework built on top of this same, untested money-math logic inherits the same risk — a subtle bug in stake sizing or settlement will silently corrupt backtest ROI numbers exactly as it silently corrupted the live bankroll.

**Why it happens:**
The scripts were written pedagogically/iteratively without a test framework ever being introduced (no `pytest`, no `test_*.py` anywhere in the repo), and bugs in pure financial math are easy to miss by eye because the code "looks right" — the failure mode is a wrong number, not a crash.

**How to avoid:**
- Before or alongside building the backtest framework, add unit tests for `beregn_innsats` with known probability/odds/bankroll-fraction inputs and hand-verified expected stakes, including edge cases (zero/negative edge → zero stake; probability capped correctly; stake caps enforced).
- Add unit tests for dedup/staleness logic in `plasser_bets` using synthetic bet records, specifically covering the stale-row scenario that already caused a bug once.
- Since the backtest framework will replay historical bets through this same staking/settlement logic at scale, treat test coverage on these functions as a **prerequisite** for trusting any backtest output, not a nice-to-have afterthought.

**Warning signs:**
- Any change to `beregn_innsats`, `plasser_bets`, or `sjekk_resultater` ships without a corresponding test run.
- Backtest bankroll/bet-count numbers look implausible (e.g., duplicate bets on the same game, stakes that don't match expected Kelly fractions) but pass silently because nothing asserts otherwise.

**Phase to address:**
Should be addressed early — ideally as a prerequisite to or first deliverable within the backtesting framework phase, since the framework will reuse (or should reuse) this exact logic at scale.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|------------------|
| Hand-tuning thresholds against one backtest run instead of tune/validate/holdout split | Fast, simple, "looks done" quickly | Ships an overfit config with no real evidence of edge (already happened once) | Never for anything that risks real money later — acceptable only for throwaway exploratory scripts explicitly labeled as such |
| Reimplementing feature engineering / team lookup inline per script instead of a shared module | Faster to write a standalone script | Train/serve skew, silent divergence, bugs fixed in one place don't propagate (already happened) | Never past the prototype stage — extract shared modules before adding a third consumer (the backtest framework) |
| Writing a remediation plan as a markdown report instead of applying it in code | Documents intent quickly, feels like progress | Report and code silently diverge, misleads future readers about what's actually running (already happened) | Acceptable only if the report is applied in the same commit/session, or explicitly marked "proposal, not applied" |
| Skipping a three-way train/calibrate/test split in favor of train/test only | One less split to manage, simpler code | Calibration metrics are optimistically biased, value signal is untrustworthy (already happened) | Never once the calibrated probabilities feed a real staking decision |
| No automated tests on staking/settlement math | Ships faster with fewer files | Silent financial-math bugs directly mis-size bets (already happened once, dedup bug) | Acceptable only while stakes are simulated/trivial and no backtest depends on the same code path |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|-----------------|-------------------|
| The Odds API (historical endpoint) | Pulling closing-line or best-available snapshots for backtest odds instead of the snapshot timing that matches when the live bot actually runs, producing an unrealistically favorable backtest | Pin backtest snapshot retrieval to match the live bot's daily run cadence; separately track CLV using the true closing line as a distinct metric, not as the entry price |
| The Odds API (rate limits / cost) | Burning through historical-endpoint request quota re-running backtests naively per threshold combination tried | Cache raw historical odds pulls to local disk once, then iterate on thresholds/parameters against the cached data — don't re-hit the API per parameter sweep |
| The Odds API (auth) | Hardcoding the API key directly in source (already done — `04_value_detector.py:30`, exposed on a public GitHub repo) | Load from an environment variable / git-ignored `.env` via `python-dotenv`; rotate the currently-exposed key immediately; scrub git history since it's been public since the first commit |
| `nba_api` (result settlement) | Treating any exception from the results lookup the same as "game not played yet" (already done — `06_bot.py:135-136` bare `except Exception: return None`), silently masking real API/schema failures as pending bets | Distinguish "not yet played" (expected, no result found for a future/in-progress game) from actual errors (log them, don't silently swallow); track consecutive failures per bet |
| `nba_api` / The Odds API team-name matching | Independently reimplementing fuzzy team-name resolution in multiple files with different heuristics (already done — 3-4 separate implementations per `ARCHITECTURE.md`) | One shared `finn_lag()`/lookup helper, imported everywhere; add a test that asserts every team name from both APIs resolves correctly, especially around season team-name/relocation changes |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Sequential per-game/per-bet API calls with hardcoded `time.sleep()` (already present throughout the pipeline) | A backtest over a full season (~1,230 games) or multiple seasons takes hours instead of minutes if it reuses the same per-call sleep pattern | Batch historical odds/results retrieval (date-range queries instead of per-game calls); cache aggressively since historical data doesn't change | Becomes painful once the backtest window spans a full season or multiple seasons rather than a handful of recent days |
| Re-fetching static reference data (e.g., `teams.get_teams()`) on every single bet/game check instead of once per run | Backtest runtime scales unnecessarily with bet count instead of staying flat | Fetch static/reference data once per run and pass it through, not re-fetch per item | Noticeable once backtest bet counts reach the hundreds needed for statistical validity (Pitfall 1) |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Hardcoded live API key committed to a public repo (already done) | Key is scrapable by anyone/any bot right now; potential quota abuse or account compromise | Rotate immediately, move to env var/`.env`, scrub git history, update setup docs to not instruct users to paste keys into source |
| `pickle`-based model serialization (already used) | Arbitrary code execution if `nba_modell.pkl` is ever shared/downloaded from an untrusted source | Low risk today (self-generated, gitignored) but switch to `joblib` with a documented schema or export raw model + calibrator parameters as JSON/arrays if the model is ever distributed |

## "Looks Done But Isn't" Checklist

- [ ] **Backtest framework:** Often missing an out-of-sample validation/holdout split — verify the reported ROI number comes from data never used to choose thresholds, not the same window used for tuning
- [ ] **Backtest framework:** Often missing a drawdown/max-drawdown report — verify final ROI is reported alongside max drawdown and bet count, not ROI alone
- [ ] **Calibration:** Often evaluated on the same data it was fit on — verify calibration metrics come from a disjoint slice from the one the isotonic/Platt calibrator was `.fit()` on
- [ ] **"Value" signal:** Often built on unvalidated vig-removal — verify the vig-removal method is applied consistently across live and backtest paths and its output correlates with positive CLV, not just positive raw ROI
- [ ] **Config/thresholds:** Often documented as "fixed" without the fix being deployed (already happened) — verify the running code's constants match what the latest validated backtest/report actually recommends, with a test enforcing it
- [ ] **Reproducibility:** Often broken by an untracked file the model depends on (already happened — `modell_utils.py`) — verify a fresh `git clone` + fresh venv can load the model and run one full pipeline cycle end to end
- [ ] **Staking safety:** Often missing a circuit breaker — verify there's an automated stop (not just human vigilance) if drawdown exceeds a defined threshold
- [ ] **Feature parity:** Often silently diverges between training and live scoring (already happened) — verify a shared feature-computation function is used by training, live scoring, and the backtest framework, with a test asserting identical output on shared fixtures

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|----------------|------------------|
| Overfit backtest thresholds already shipped to production | MEDIUM | Re-run backtest with proper tune/validate/holdout split; discard the old threshold-selection process's authority; re-paper-trade the newly validated config for a meaningful sample before trusting it |
| Calibration metrics found to be leaked/biased | LOW-MEDIUM | Re-split data (train/calibrate/test three-way), refit calibrator on the calibrate slice only, re-report metrics on the disjoint test slice; re-run any backtest that depended on the old calibrated model |
| Config drift discovered again in the future (doc says X, code runs Y) | LOW | Diff the documented/intended config against the running config constant-by-constant; apply the correct values in one commit; delete/archive the stale report; add the config-matches-backtest test described in Pitfall 6 |
| Bankroll drawdown beyond acceptable threshold during paper trading | LOW (virtual money) | Pause the bot, run the backtest framework against the exact live config to see if the drawdown was predictable/expected variance vs. a sign of a real bug or an invalid edge; do not resume without a specific root cause identified |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|--------------------|----------------|
| In-sample threshold overfitting (Pitfall 1) | Backtesting framework phase | Backtest report shows separate tune/validate/holdout results and bet counts per slice; final number comes from holdout only |
| Look-ahead bias in historical odds (Pitfall 2) | Backtesting framework phase | Backtest odds-snapshot timing documented and matched to live bot cadence; CLV reported alongside ROI |
| Calibration evaluated on its own fit data (Pitfall 3) | Model/calibration remediation phase | Three-way train/calibrate/test split confirmed in code review; calibration diagnostic computed on disjoint test slice |
| Vig-removal errors manufacturing fake value (Pitfall 4) | Backtesting framework phase (shared module) + model remediation phase (CLV validation) | Single shared vig-removal function used by both live and backtest paths; value bets show positive average CLV over backtest period |
| Kelly staking amplifying edge-estimation error (Pitfall 5) | Backtesting framework phase (drawdown reporting) + staking remediation phase (circuit breaker) | Backtest reports max drawdown, not just ROI; live bot has an automated stop tied to a drawdown threshold; `beregn_innsats` has unit tests |
| Documented fixes never deployed / config drift (Pitfall 6) | Config remediation phase (should precede backtesting) | Single source-of-truth config file imported by both live and backtest code; test asserts live config matches last-validated backtest config |
| Untracked runtime-critical file (Pitfall 7) | Config/repo-hygiene remediation phase (immediate) | `git status` clean of untracked-but-imported files; fresh-clone smoke test passes |
| Train/serve feature skew (Pitfall 8) | Backtesting framework phase (forces reuse of live scoring path) + remediation phase (extract shared module) | Backtest framework calls the same feature-computation function as live scoring; regression test confirms identical output on shared fixtures |
| No test coverage on staking/settlement math (Pitfall 9) | Prerequisite to backtesting framework phase | Unit tests exist for `beregn_innsats`, `plasser_bets` dedup, and `sjekk_resultater` before the backtest framework is built on top of them |

## Sources

- [How to Backtest a Sports Betting Strategy Without Overfitting - Great Bets](https://www.greatbets.co.uk/how-to-backtest-a-sports-betting-strategy-without-overfitting/)
- [7 Mistakes You're Making with Overfitting Betting Models - Predictology](https://www.predictology.co/blog/7-mistakes-youre-making-with-overfitting-betting-models-and-how-to-fix-them/)
- [Mastering Cross-Validation Techniques for Betting Models - oddsonnet.com](https://oddsonnet.com/news/mastering-cross-validation-techniques-for-betting-models-avoid-overfitting-and-boost-profits)
- [Backtesting a Sports Betting Strategy - Estèphe, Systematic Sports (Medium)](https://medium.com/systematic-sports/backtesting-a-sports-betting-strategy-283833a5eca3)
- [What is the Kelly Criterion and How Does it Apply to Sports Betting? - betstamp](https://www.betstamp.com/education/kelly-criterion)
- [Reasons to Ignore the Kelly Criterion in Sports Betting - analytics.bet](https://analytics.bet/articles/reasons-to-ignore-the-kelly-criterion/)
- [Kelly Criterion Formula Explained - Quant Matter](https://quantmatter.com/kelly-criterion-formula/)
- [How to Track Closing Line Value (CLV) in Sports Betting - Pikkit](https://pikkit.com/blog/how-to-track-closing-line-value-clv-in-sports-betting)
- [Closing Line Value (CLV) demystified by expert Joseph Buchdahl - Pinnacle Odds Dropper](https://www.pinnacleoddsdropper.com/blog/closing-line-value--clv-demystified-by-expert-joseph-buchdahl)
- [What is Closing Line Value in Sports Betting? - OddsJam](https://oddsjam.com/betting-education/closing-line-value)
- [Probability calibration — scikit-learn documentation](https://scikit-learn.org/stable/modules/calibration.html)
- [How and When to Use a Calibrated Classification Model with scikit-learn - MachineLearningMastery.com](https://machinelearningmastery.com/calibrated-classification-model-in-scikit-learn/)
- [Model Drift in Streaming: When ML Models Degrade in Real-Time - Conduktor](https://www.conduktor.io/glossary/model-drift-in-streaming)
- [Model Version Drift in Production Systems - Interwebicly](https://interwebicly.com/blog/model-version-drift-production-systems)
- Project-specific findings verified directly against this repository: `.planning/codebase/CONCERNS.md` and `.planning/codebase/ARCHITECTURE.md` (2026-08-19 codebase audit) — leaked API key, untracked `modell_utils.py`, calibration-metric leakage in `03_tren_modell.py`, documented-but-undeployed threshold fix, duplicated feature-engineering and team-lookup logic, zero test coverage, existing stale-row dedup bug in `06_bot.py`

---
*Pitfalls research for: Sports-betting value-detection system with historical backtesting framework*
*Researched: 2026-08-19*
