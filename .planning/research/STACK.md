# Stack Research

**Domain:** Sports-betting strategy backtesting (bet-sequence simulation, walk-forward validation, historical odds acquisition) added to an existing Python/pandas/xgboost NBA value-betting pipeline
**Researched:** 2026-08-19
**Confidence:** MEDIUM-HIGH (verified against official The Odds API docs and PyPI metadata; sports-betting-specific backtest tooling has no single dominant framework, so architectural recommendation is a synthesized best practice, not a single verified "everyone uses this" citation)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Custom event-driven backtest loop (pandas/numpy, new module) | n/a — write it, don't install it | Replays the full strategy (model prediction → value/EV threshold → odds-range filter → injury filter → Kelly stake) bet-by-bet in chronological order against historical odds, producing a bankroll time series | This is the actual standard practice for discrete-wager backtesting (moneyline/1X2 markets), not an off-the-shelf package. Generic trading backtest engines (`backtesting.py`, `vectorbt`, `zipline-reloaded`, `backtrader`) all model continuous OHLCV price series with open/hold/close positions — a paradigm mismatch for a single fixed-odds wager that resolves once. The sports-betting-specific tools that do exist (e.g. `sports-betting` on PyPI) implement exactly this pattern internally: a plain chronological loop over rows with a running cash/bankroll variable — there is no hidden trick to reverse-engineer. Confidence: MEDIUM (architectural synthesis, not a single citable "industry standard library" — see Sources). |
| The Odds API — per-event historical odds endpoint (`/v4/historical/sports/{sport}/events/{eventId}/odds`) | v4 (current) | Fetch odds for one game at (or just before) its actual tip-off time, at 1 credit per market × region | **SUPERSEDED 2026-08-23 by .planning/phases/04-historical-odds-acquisition-live-refactor/04-RESEARCH.md — both historical endpoints share the identical cost formula 10 x markets x regions; the per-event endpoint charges it per game queried, making it ~72,760 credits for this project's 3,638 games versus ~10-20K for sport-wide. Use the sport-wide endpoint.** ~~This is the single most important finding of this research.~~ ~~The sport-wide historical snapshot endpoint (`/v4/historical/sports/{sport}/odds`) costs `10 × markets × regions` per call, while the per-event endpoint costs `1 × markets × regions` — a **10x saving**. For h2h/us-only pulls that's 1 credit/event vs. 10 credits/event. Over a ~1,230-game NBA season this is the difference between ~1,230 credits and ~12,300 credits.~~ Confidence: HIGH (verified directly against official docs at the-odds-api.com/liveapi/guides/v4/) — **verification premise later found incorrect, see superseded marker above.** |
| The Odds API — historical events endpoint (`/v4/historical/sports/{sport}/events`) | v4 (current) | Cheaply discover event IDs + commence times for a given day/date range before spending odds credits | Costs 1 credit per call, **0 credits if no events are found** — use this to build the list of `eventId`s to backtest before calling the (per-event) odds endpoint on each one. Never guess event IDs or scrape them from another source. Confidence: HIGH (official docs). |
| `sqlite3` (Python stdlib) | 3.x (bundled with Python 3.14) | Permanent local archive of every historical odds/event API response ever fetched, keyed by `(sport, event_id, market, snapshot_timestamp)` | Historical odds for a past timestamp **never change** — this is an archival problem, not a caching problem. A generic HTTP cache (`requests-cache`) is the wrong tool because its cache-invalidation model (TTL/ETag) is designed for data that changes; you want "fetch once, keep forever, never re-request." SQLite needs zero new dependencies (stdlib), supports indexed joins against your existing game-log CSV, and easily answers "which events do I already have odds for" before spending any more credits. Confidence: HIGH (standard practice for append-only archival data; no new dependency risk). |
| `scikit-learn` `TimeSeriesSplit` (already installed, 1.8.0 in venv; 1.9.0 is current upstream) | already present | Walk-forward cross-validation for **model hyperparameter tuning** during backtesting iterations | Already a project dependency — no new install. `TimeSeriesSplit` gives an expanding-window walk-forward split out of the box and is the standard scikit-learn tool for this; it respects chronological order so later folds never see earlier folds' future data. Use it for model-selection CV; use the custom backtest loop above for the full strategy simulation (staking, thresholds, ROI) since `TimeSeriesSplit` only knows about row indices, not bets, stakes, or bankroll. Confidence: HIGH (official scikit-learn docs). |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `python-dotenv` | 1.2.3 | Load `THE_ODDS_API_KEY` (and any other secret) from a `.env` file into `os.environ` | Use immediately, independent of backtesting — this directly fixes the leaked hardcoded API key in `04_value_detector.py:30` that's flagged as a required fix in `PROJECT.md`. Add `.env` to `.gitignore` (already present pattern in repo) and read via `os.environ["THE_ODDS_API_KEY"]`. |
| `tenacity` | 9.1.4 | Retry-with-backoff decorator around the historical-odds fetch loop | A full-season historical pull is hundreds of sequential HTTP calls with rate-limit sleeps already in place (existing pattern in `01_hent_data.py`, `05_skadefilter.py`). A single transient network/5xx failure partway through a multi-hundred-call run shouldn't kill the whole fetch and waste already-spent credits on calls before the crash. Wrap the odds-fetch function in `@tenacity.retry(...)` with exponential backoff, capped attempts. |
| `numpy`/`pandas` (already installed) | already present | Compute ROI, yield, max drawdown, and a Sharpe-like ratio for the bet-sequence bankroll curve directly | For a hobby-scale bet log (hundreds to low-thousands of bets/season), these metrics are ~20 lines of pandas: `roi = pnl.sum() / stakes.sum()`, `drawdown = (equity.cummax() - equity) / equity.cummax()`, `sharpe_like = pnl.mean() / pnl.std() * sqrt(bets_per_year)`. This is the default recommendation — no new dependency, full control over exactly what "Sharpe-like" means for a bet sequence (returns aren't normally distributed the way trading returns loosely are, so a canned finance-library Sharpe can be misleading if applied uncritically). |
| `quantstats` | 0.0.81 | Optional: generate a polished HTML tear-sheet report (Sharpe, Sortino, Calmar, drawdown chart, rolling metrics) from a returns series | Only add this if you want a shareable/visual report beyond what a few pandas lines produce. Feed it a daily-resampled returns series derived from your bankroll curve (`quantstats.reports.html(returns, output="backtest_report.html")`). Note it pulls in `matplotlib`, `scipy`, `seaborn`, and `yfinance` as hard dependencies (the last one purely for optional benchmark comparison, e.g. vs. S&P 500 — irrelevant here, but installed regardless) — a meaningfully heavier footprint than the plain pandas approach above. Prefer the original `quantstats` (ranaroussi), actively maintained (last release Jan 2026) — **not** `quantstats-reloaded`, which is a community fork still at v0.1.0 (June 2025), too immature to trust for correctness-critical metrics. |
| `matplotlib` | 3.11.1 | Plot the bankroll/equity curve and drawdown chart | Needed if you want a chart at all (existing dashboard is a static HTML/JS string, not matplotlib-based) — either standalone for quick backtest-iteration plots, or pulled in transitively if you also add `quantstats`. |
| `tqdm` | 4.70.0 | Progress bar for the historical-odds backfill script | A full-season historical pull (1,000+ sequential rate-limited API calls) can run for many minutes; a progress bar with ETA is a meaningful UX improvement for a script you'll re-run repeatedly during development, and it's a one-line wrap (`for event in tqdm(events): ...`). |
| `pytest` | 9.1.1 | Unit tests for the new backtest engine's correctness-critical logic | The existing codebase has zero automated tests (documented gap in `.planning/codebase/STACK.md`). The backtest engine is exactly the kind of code where an off-by-one or leakage bug silently produces a wrong-but-plausible ROI number you'd never catch by eye — worth testing directly: walk-forward split boundaries (no row appears in both train and test), Kelly stake formula (matches hand-calculated values), ROI/drawdown arithmetic on a synthetic known bet sequence, and the odds-archive cache (same `(event_id, market)` never triggers a second paid API call). Scope tests to the new backtest module only — don't attempt to retrofit tests onto the existing flat scripts as part of this milestone unless the roadmap explicitly asks for it. |
| `pyarrow` | 25.0.1 | Optional: Parquet storage for the assembled backtest dataset (features + odds + outcomes joined) | Only worth adding if the joined backtest dataset becomes large/awkward as CSV (repeated re-reads during walk-forward iteration) or you want typed, indexed columns. Not needed at hobby scale (~1,230 rows/season) — CSV is fine to start; add this later only if iteration speed becomes a real problem. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pytest` | Test runner for the new backtest engine | See Supporting Libraries — first automated tests in this repo; keep scope tight to the new module. |
| `tenacity` | Retry decorator | See Supporting Libraries — used inside the historical-odds fetch script, not a dev-only tool but small enough to mention here as "resilience tooling." |

## Installation

```bash
# Core (all stdlib except scikit-learn, which is already a project dependency)
# No new install needed for the backtest engine itself — it's a new .py module using pandas/numpy/sqlite3.

# Supporting libraries for this milestone
pip install python-dotenv tenacity tqdm

# Reporting (optional — only if you want an HTML tear-sheet beyond pandas-computed metrics)
pip install quantstats matplotlib

# Dev dependencies
pip install pytest

# Optional, only if the joined backtest dataset outgrows CSV
pip install pyarrow
```

Pin these in `requirements.txt` with `==` (not `>=`) — the existing `requirements.txt` uses unpinned `>=` floors, which is flagged as a gap in `.planning/codebase/STACK.md`; don't repeat that pattern for the new dependencies, and ideally introduce a lockfile (`pip freeze > requirements-lock.txt` at minimum) as part of this milestone rather than deferring it further.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| Custom event-driven backtest loop (pandas/numpy) | `backtesting.py`, `vectorbt`, `zipline-reloaded`, `backtrader` | Never, for this project. All four are built around continuous price bars and position management (enter/hold/exit at a market price), which has no natural mapping to "place one fixed-odds moneyline bet, it settles once." Forcing a discrete-bet strategy into an OHLCV-bar engine (e.g. faking a "price" per game) adds real complexity for zero benefit over a plain pandas loop. Only reconsider if the project later expands into live-market/in-play odds movement trading, which is a genuinely different (continuous-series) problem. |
| Custom event-driven backtest loop | `sports-betting` (PyPI, scikit-learn-based bettor/backtest framework) | Reconsider if the project pivots to football/soccer (its actual domain — docs and examples are exclusively football, `football-data.co.uk`-sourced) or if you want its `TimeSeriesSplit`-based backtest CLI pattern as a design reference. It does not support NBA/basketball and is not a drop-in fit for The Odds API as a data source; worth reading its docs for pattern inspiration (scikit-learn `Bettor` wrapper around a classifier, `backtest()` returning ROI/yield per fold) rather than adopting as a dependency. |
| Plain pandas/numpy for ROI/drawdown/Sharpe-like metrics | `quantstats` | Use `quantstats` once you want a polished, shareable HTML report with drawdown charts, rolling metrics, and monthly/yearly breakdowns — the visual layer is genuinely good and saves plotting code. Don't use it as the primary metric source if you want full control over what "Sharpe-like" means for discrete non-normally-distributed bet returns. |
| Plain pandas/numpy or `quantstats` | `empyrical` / `empyrical-reloaded`, `pyfolio` | `empyrical` (original, Quantopian) is unmaintained since 2020 — don't use it. `empyrical-reloaded` (community fork, last release June 2025, v0.5.12) is maintained but is a narrower "just the numbers" library than `quantstats`; only reach for it if you specifically want to compose your own report/plots around raw metric functions rather than `quantstats`'s all-in-one tear sheet. `pyfolio` is effectively abandoned (built on old pandas, designed around `empyrical`) — avoid. |
| SQLite (stdlib) permanent odds archive | `requests-cache` | Use `requests-cache` only for the *live* odds endpoint during day-to-day bot operation (where TTL-based "don't refetch within N minutes" semantics genuinely apply), not for the historical backfill. For historical data, an HTTP-semantic cache with expiry is the wrong mental model — you want an explicit, queryable, permanent local archive you fully control, so you never accidentally re-spend credits. |
| Per-event historical odds endpoint (`/events/{eventId}/odds`) | Sport-wide historical snapshot endpoint (`/v4/historical/sports/{sport}/odds`) | Only use the sport-wide snapshot endpoint if you specifically need "what did the whole slate of games look like at exactly time T" (e.g. studying line movement across a whole day at once). For building a season-long backtest dataset of one odds reading per game (e.g. closing line), the per-event endpoint is 10x cheaper and is the correct default. |
| `scikit-learn TimeSeriesSplit` for model CV | Manual date-based season/month split (already used in `03_tren_modell.py`) | Keep using the existing manual date-cutoff split for the final train/test story used to report backtest results (it's easier to reason about "trained through end of 2023-24 season, tested on 2024-25 season" than fold indices) — reach for `TimeSeriesSplit` specifically when you need multiple folds for hyperparameter search (e.g. `GridSearchCV`/`RandomizedSearchCV` with `cv=TimeSeriesSplit(n_splits=5)`), not for the single train/test backtest split itself. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|--------------|
| `backtrader` | Last PyPI release April 2023 (`1.9.78.123`); effectively unmaintained, and even when maintained it targeted continuous-market trading, not discrete fixed-odds wagers. | Custom pandas/numpy backtest loop. |
| `zipline-reloaded` | Actively maintained (last release July 2025) but built for equities/portfolio simulation with a heavy dependency chain (`numba`, exchange calendars, bundle/ingest pipeline) — solving problems this project doesn't have, at real setup cost. | Custom pandas/numpy backtest loop. |
| `vectorbt` (even the newer 1.x line, released July 2026) | Still fundamentally an OHLCV/portfolio-order-simulation engine under the hood; adapting it to discrete single-settlement bets means fighting its core abstraction rather than using it. | Custom pandas/numpy backtest loop. |
| `empyrical` (original, Quantopian) | Unmaintained since ~2020; `pandas`/`numpy` version pins are stale and will conflict with the project's already-installed `pandas` 3.0.1 / `numpy` 2.4.3. | `empyrical-reloaded` if you want a metrics-only library, or plain pandas/numpy (recommended default). |
| `pyfolio` | Abandoned; built on old `pandas`/`empyrical` versions; overlaps entirely with `quantstats`, which is actively maintained and simpler to use. | `quantstats` (optional) or plain pandas/numpy. |
| Any dedicated "Kelly criterion" PyPI package (e.g. small niche `kelly-criterion` GitHub repos) | The formula is ~5 lines (`f* = (bp - q) / b`, already implemented as half-Kelly in `06_bot.py`'s `beregn_innsats()`); no package in this space has meaningful adoption/maintenance to justify a dependency for something this small. | Implement/extend the existing half-Kelly function directly; add a small pytest test for it. |
| The Odds API **sport-wide** historical odds endpoint (`/v4/historical/sports/{sport}/odds`) as the default method for building a full-season backtest dataset | Costs `10 × markets × regions` per snapshot call — building a season's worth of per-game closing lines this way is ~10x more expensive in credits than necessary and will blow through the free 500-credits/month tier almost immediately (≈50 calls/month at h2h+us). | Historical `/events` endpoint (1 credit, discovery) + per-event `/events/{eventId}/odds` endpoint (1 credit/event) — see Core Technologies. |
| Assuming the free "Starter" tier (500 credits/month) is enough to backtest a full NBA season | Even with the cheaper per-event endpoint, one full season (~1,230 games) needs roughly 1,230 events-discovery credits + 1,230 odds-fetch credits ≈ 2,460 credits for a single h2h/us-only pass — about 5x the free tier's monthly allowance. Re-runs (bug fixes, re-pulling after an interrupted fetch) add more. | Budget for the $30/month "20K" tier (20,000 credits/month) for the initial historical backfill; the SQLite permanent archive means you only pay this once — after the archive is built, iterating on strategy logic against cached data costs zero additional credits. Confirm current pricing before committing (verified 2026-08-19: Starter free/500 credits, 20K tier $30/mo — see Sources). |
| `requests-cache` for the historical backfill | TTL/ETag-based caching is designed for data that might change on refetch; historical odds for a past timestamp never change, so a generic HTTP cache adds indirection without the guarantee you actually want (an explicit, auditable "have I already paid for this event's odds?" record). | SQLite permanent archive (see Core Technologies). |

## Stack Patterns by Variant

**If you want the fastest path to a working backtest (recommended starting point):**
- Custom pandas/numpy backtest loop + plain pandas ROI/drawdown/Sharpe-like metrics + SQLite odds archive
- Because it adds zero new heavyweight dependencies, keeps every metric definition transparent and debuggable, and matches the project's existing "flat script, pandas everywhere" style

**If you later want a polished, shareable report (e.g. to show alongside the existing dashboard):**
- Add `quantstats` for an HTML tear-sheet, fed by a daily-resampled bankroll returns series
- Because building an equivalent chart set (rolling Sharpe, monthly heatmap, drawdown periods table) by hand is a lot of matplotlib code `quantstats` already provides well

**If a future milestone adds spread/totals or in-play odds:**
- Revisit the "no generic backtest engine" recommendation — in-play/line-movement strategies are closer to the continuous-series problem `vectorbt`/`zipline-reloaded` are built for
- Because the discrete-single-settlement assumption behind the custom-loop recommendation stops holding once you're reacting to odds movement within a game

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|------------------|-------|
| `quantstats` 0.0.81 | `pandas` >=1.5.0 (floor only, no upper pin) | Project's installed `pandas` is 3.0.1 — not explicitly tested by the `quantstats` maintainers against pandas 3.x as of this writing; verify with a smoke test (`quantstats.stats.sharpe(sample_series)`) before relying on it, since pandas 2.x→3.x had breaking changes in places. |
| `quantstats` 0.0.81 | `matplotlib` >=3.7.0, `scipy` >=1.11.0, `seaborn` >=0.13.0, `yfinance` >=0.2.40 | All hard dependencies, installed regardless of whether you use plotting/benchmark features. |
| `scikit-learn` 1.8.0 (installed) vs. 1.9.0 (current upstream) | `TimeSeriesSplit` API unchanged across this range | No need to upgrade scikit-learn for this milestone; `TimeSeriesSplit` behavior used here is stable across both versions. |
| `pytest` 9.1.1 | Python >=3.10 | Project runs Python 3.14 per `venv/pyvenv.cfg` — compatible. |
| `pyarrow` 25.0.1 | Python >=3.10 | Only relevant if you adopt Parquet later (optional, not needed at current data scale). |

## Sources

- The Odds API official v4 guide (`https://the-odds-api.com/liveapi/guides/v4/`) — verified: historical odds sport-wide endpoint cost formula (`10 × markets × regions`), per-event historical odds endpoint cost formula (`1 × markets × regions`), historical events endpoint cost (1 credit, 0 if empty), snapshot interval history (10-min pre-Sept-2022, 5-min after), data availability from June 6 2020. HIGH confidence.
- The Odds API pricing page (`https://the-odds-api.com/#pricing`) — verified: Starter/free tier = 500 credits/month, includes historical access in principle; paid tiers from $30/mo (20,000 credits). HIGH confidence.
- PyPI JSON API (`pypi.org/pypi/<package>/json`) — verified current versions/release dates for: `quantstats` 0.0.81 (2026-01-13), `quantstats-reloaded` 0.1.0 (2025-06-16), `empyrical-reloaded` 0.5.12 (2025-06-01), `scikit-learn` 1.9.0 (2026-06-02, project has 1.8.0 installed), `backtrader` 1.9.78.123 (2023-04-19, stale), `zipline-reloaded` 3.1.1 (2025-07-19), `vectorbt` 1.1.0 (2026-07-05), `python-dotenv` 1.2.3 (2026-08-16), `tenacity` 9.1.4 (2026-02-07), `pytest` 9.1.1 (2026-06-19), `pyarrow` 25.0.1 (2026-08-10), `matplotlib` 3.11.1 (2026-07-18), `tqdm` 4.70.0 (2026-07-27). HIGH confidence (PyPI is authoritative for version/date facts).
- `sports-betting` PyPI page (`pypi.org/project/sports-betting/`) — verified: football/soccer-only scope, scikit-learn-`Bettor` pattern, active maintenance (v0.15.1, 2026-07-28). MEDIUM confidence (WebFetch summary of docs, not hand-verified source code).
- scikit-learn `TimeSeriesSplit` official docs (`scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html`) — verified expanding-window walk-forward behavior. HIGH confidence.
- WebSearch synthesis on Python quant-trading reporting ecosystem (`quantstats` vs `empyrical` vs `pyfolio` maintenance status) — MEDIUM confidence, cross-checked against PyPI release dates directly.
- General backtesting-framework-for-discrete-bets architecture recommendation — MEDIUM confidence; this is a domain-reasoning synthesis (no single authoritative "here is THE standard sports-betting backtest library" source exists, which is itself a finding worth noting for the roadmap: expect to build this component largely from scratch).

---
*Stack research for: Python sports-betting backtesting framework (historical odds simulation, walk-forward validation, staking/bankroll simulation, result reporting)*
*Researched: 2026-08-19*
