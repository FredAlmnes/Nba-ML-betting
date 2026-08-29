# Phase 2: Shared Core Extraction & Test Foundation - Research

**Researched:** 2026-08-20
**Domain:** Python code extraction/de-duplication (flat-script → shared pure-function modules) + first-ever pytest test suite for a zero-test-infrastructure repo
**Confidence:** HIGH (extraction design — directly grounded in this codebase's own source, not hypothetical); HIGH (pytest discovery/config — verified against official pytest docs + registry); MEDIUM (exact `as_of` mechanical shape for `features.py`, since it requires reasoned synthesis beyond what CONTEXT.md locked — flagged below)

## Summary

This phase has no external-library discovery risk — the "stack" is one dev dependency (`pytest`) and the real work is a disciplined, mechanical extraction of code that already exists in four files into three new flat modules (`teams.py`, `features.py`, `strategy.py`) plus a `config.py` single source of truth, followed by the repo's first-ever automated tests. All four duplication sites (team lookup in `04_value_detector.py`/`05_skadefilter.py`/`06_bot.py`/`debug_kamp.py`; feature stat-list/window duplication between `02_feature_engineering.py` and `04_value_detector.py`) were re-confirmed directly against current source this session, with exact line numbers below.

The one genuinely open design question — how `features.py` should accept an `as_of` cutoff given the existing `shift(1)`-based rolling-window code — has a concrete, conservative answer grounded in the actual mechanics of the current code (see Pattern 2 below): the batch rolling-window function is already leakage-safe *per row* today; `as_of` should be added as a defense-in-depth **pre-filter** on the input DataFrame, not a redesign of the rolling logic itself. Full unification of the live (`nba_api` fetch-last-N-games) and batch (rolling-window-over-full-history) *data-fetching* mechanics is explicitly out of scope for this phase (that's the `data/games.py` adapter work ARCHITECTURE.md assigns to Phase 4/5) — only the **stat list and window-size constants** need to become single-sourced now to close the actual drift risk (Pitfall 8).

**Primary recommendation:** Extract mechanically, changing zero behavior/values; add `pytest` (already verified clean via slopcheck, `pip index versions pytest` confirms `9.1.1` current on PyPI); create a single `pytest.ini` with `pythonpath = .` so the new `tests/` directory can `import teams`, `import features`, `import strategy` from repo root without adding `__init__.py` files anywhere — this preserves the project's flat-script convention while making imports work.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CORE-01 | Feature engineering, team-name resolution, and value/stake strategy logic are extracted into shared modules (`features.py`, `strategy.py`, `teams.py`) imported identically by both the live path and the backtest path — no duplicate implementations | Exact duplication sites confirmed with line numbers (see Don't Hand-Roll / Architecture Patterns); canonical function designs proposed per module below |
| CORE-02 | Strategy parameters (`MIN_VALUE_TERSKEL`, `MAX_ODDS`, Kelly fraction) live in a single source-of-truth config imported by both live and backtest | `config.py` design proposed (module-level `UPPER_SNAKE_CASE` constants, matching existing convention); exact current values enumerated below to copy verbatim |
| CORE-03 | Unit tests cover the stake-sizing function (`beregn_innsats`) and bet-dedup logic — first automated tests in this repo | `pytest` install/config verified; test cases derived directly from existing `beregn_innsats` logic and `plasser_bets` dedup key construction (06_bot.py:264-274) |
| CORE-04 | A parity/leakage regression test confirms the live path and backtest path produce an identical decision for the same historical date/game | Scoping validated (see Open Questions) — since no backtest engine exists yet, this becomes a determinism/referential-transparency test on the extracted pure functions, per `.planning/research/ARCHITECTURE.md` Pattern 2 |

</phase_requirements>

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Package structure**
- **D-01:** Create `features.py`, `strategy.py`, `teams.py` as **flat modules at the repo root**, matching the existing flat-script convention (no new `nba_betting/` package directory yet). Milestone-level research (`.planning/research/ARCHITECTURE.md`) recommends a full `nba_betting/` package eventually, but that restructure is only actually load-bearing once `backtest/` and `live/` need to coexist as separate execution paths — that's Phase 4/5. Introducing a full package now would be premature scope for what CORE-01 through CORE-04 actually require.
- **D-02:** `modell_utils.py` (the `KalibrertModell` calibration wrapper) is NOT touched or renamed in this phase — it already serves as the "model" concern and calibration fixes are explicitly Phase 3's job (CALIB-01/02).

**Team-name resolution (`teams.py`)**
- **D-03:** Confirmed via direct grep this session: team lookup is independently reimplemented in exactly 4 places — `04_value_detector.py:129-135` (lowercase full_name/abbreviation/nickname keys, substring fallback), `05_skadefilter.py:168-172` (full_name/nickname keys only, no abbreviation), `06_bot.py:76-89` (full_name/nickname/abbreviation, `finn_lag()` closure with substring fallback), `debug_kamp.py:13-19` (same three keys, dict comprehension style). `teams.py` should provide a single canonical resolver function that supersedes all four.
- **D-04:** `debug_kamp.py` is currently **untracked** (never committed to git at all, confirmed via `git status`). Whether it gets tracked as part of this phase's `teams.py` migration, or left untracked/untouched (its own separate, lower-priority hygiene item), is a planner/research judgement call — it's an intentional manual debug utility per `.planning/codebase/ARCHITECTURE.md`, not part of the production pipeline.

**Feature engineering (`features.py`)**
- **D-05:** Confirmed duplication is between `02_feature_engineering.py` (historical/batch, rolling 10-game averages with `shift(1)`) and the inline feature-building block in `04_value_detector.py` (live/online) — per `.planning/codebase/ARCHITECTURE.md`. `features.py` should be the single implementation both import, ideally parameterized by an `as_of`-style cutoff so the same function is safe for a future walk-forward backtest (Phase 5) without modification — per `.planning/research/ARCHITECTURE.md`'s recommended pattern. Do not change the actual feature set/columns in this phase — this is an extraction, not a feature redesign.

**Value/stake strategy (`strategy.py`)**
- **D-06:** Extract the value/EV calculation and vig-removal logic currently in `04_value_detector.py`, plus the half-Kelly stake-sizing function `beregn_innsats` currently in `06_bot.py`, into `strategy.py` as pure functions (inputs in, decision out — no I/O, no global state). This is what CORE-03's unit tests will exercise directly.
- **D-07:** Per Phase 1's D-05/D-07 (still binding): do NOT change `MIN_VALUE_TERSKEL`, `MAX_ODDS`, or the Kelly fraction values themselves while extracting them — CORE-02's single source-of-truth config module is in scope for this phase (it's explicitly a Phase 2 requirement), but the *values* stay exactly what they are today (0.05 / 4.00 / half-Kelly) until Phase 5's backtest validates different ones.

**Pre-existing uncommitted work in files this phase touches**
- **D-08:** Confirmed via `git status` this session: `05_skadefilter.py` and `06_bot.py` still carry the user's own pre-existing uncommitted changes (88 and 1009 lines respectively, per Phase 1's pre-flight inspection) — these are the exact files `teams.py`/`strategy.py` extraction must edit. Following the precedent set in Phase 1 (Plan 01-01), the planner should build an equivalent pre-flight checkpoint plan that inspects current `git diff` on these files and asks the developer whether to include the pre-existing WIP in this phase's commits, before any extraction work stages them. Do not assume "include" by default this time — ask fresh, since the WIP has had more time to diverge since Phase 1's decision.
- **D-09:** `03_tren_modell.py` also has pre-existing uncommitted changes but is NOT touched by this phase (no team lookup, no duplicated feature/strategy logic identified in it) — leave it untouched, same as Phase 1.

**Testing (CORE-03, CORE-04)**
- **D-10:** `pytest` is the test framework (per `.planning/research/SUMMARY.md` and Phase 2's own `.planning/research/SUMMARY.md` phase table) — this is the first automated test suite in the repo. Tests live in a `tests/` directory at repo root.
- **D-11:** CORE-03 unit tests must cover `beregn_innsats` (stake sizing) and the bet-dedup logic (`(kamp, bet, kamp_dato)` key matching in `06_bot.py::plasser_bets`) directly, now that they're extracted into testable pure functions.
- **D-12:** CORE-04's "parity/leakage regression test" cannot yet be a true live-vs-backtest integration test — the backtest engine doesn't exist until Phase 5. Per `.planning/research/ARCHITECTURE.md`'s guidance ("add a parity/regression test that asserts both paths produce identical decisions for a fixed historical date"), scope this down to: a determinism/referential-transparency test proving `features.py`/`strategy.py` functions given the same inputs (including a fixed `as_of` date) always produce the same output — i.e., proving the shared functions are safe to call identically from two different call sites, without needing the actual second call site (the backtest) to exist yet. Flag this scoping interpretation explicitly to the phase researcher/planner rather than silently deciding it — it's the one place this phase's requirement slightly outruns what's buildable yet.

### Claude's Discretion
- Exact function signatures/names within `features.py`/`strategy.py`/`teams.py` (e.g., `hent_lag_oppslag()` vs `finn_lag()` — `.planning/codebase/ARCHITECTURE.md` suggested `hent_lag_oppslag()`/`finn_lag()` as an example naming, not a locked requirement)
- Exact shape of the CORE-02 single source-of-truth config module (a `config.py` with module-level constants vs. a small dataclass) — either is fine as long as both live and (future) backtest import the same values from one place
- Whether `debug_kamp.py` gets tracked in git as part of this phase (D-04)

### Deferred Ideas (OUT OF SCOPE)
- Full `nba_betting/` package restructure (data/, backtest/, live/ subdirectories) — deferred to Phase 4/5 when backtest/live separation actually requires it (D-01)
- Refactoring `06_bot.py` to import the shared core directly instead of subprocessing — explicitly Phase 4 (ODDS-02)
- Any change to feature set, thresholds, or Kelly fraction values — explicitly Phase 5, backtest-gated
</user_constraints>

## Project Constraints (from CLAUDE.md)

- **Norwegian identifiers throughout** — all new function/variable names in `features.py`/`strategy.py`/`teams.py`/`config.py` and all test file docstrings/comments must follow the established Norwegian convention (`snake_case`, verbs/nouns like `beregn_innsats`, `finn_lag`). Test *function* names may stay in English per pytest convention (`test_*`) but assertions/comments explaining *why* should stay Norwegian to match the rest of the codebase, per CLAUDE.md's Comments section ("comments explain why, not what").
- **No type hints anywhere in the codebase** — new shared modules should NOT introduce type hints; this would be an inconsistent style deviation not requested by this phase.
- **No linter/formatter config exists** — do not introduce Black/Ruff config as part of this phase; out of scope.
- **`snake_case` throughout, `PascalCase` only for the one existing class (`KalibrertModell`)** — any new class (unlikely to be needed for pure-function `strategy.py`/`features.py`/`teams.py`) should follow this if introduced.
- **Constant-like config values are `UPPER_SNAKE_CASE` at module top** — directly informs the recommended `config.py` shape (see Architecture Patterns).
- **`sys.exit(1)` with explanatory comment for fatal errors** — if any new shared module needs a fatal-error path (unlikely for pure functions), follow this pattern, not bare `exit()`.
- **Broad `try/except Exception` around external API calls; pure-logic functions currently have no error handling conventions to preserve** since none exist yet — the newly extracted pure functions in `strategy.py`/`features.py`/`teams.py` should have NO I/O and thus need no exception handling; keep error handling in the (unextracted) calling scripts.
- **`requirements.txt` is reserved for runtime dependencies only** (per `.planning/codebase/TESTING.md`'s explicit recommendation, consistent with CLAUDE.md's "Configuration" section noting `requirements.txt` is the only build/config artifact) — `pytest` must go in a new `requirements-dev.txt`, not `requirements.txt`.
- **GSD Workflow Enforcement clause** — this file is a research artifact consumed by `/gsd:plan-phase`; actual code changes must flow through the GSD phase-execution workflow, not ad hoc edits.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Team-name string resolution (API response → canonical team ID/info) | Shared core (pure function module) | — | Called identically by data-ingestion layer (live) and future backtest replay; must not know which caller invoked it |
| Feature engineering (rolling-window team-form stats) | Shared core (pure function module) | — | Same computation must run in training/batch context and live/backtest scoring context — this is precisely the capability that already drifted twice |
| Value/EV calculation + vig removal | Shared core (pure function module) | — | Pure math over `(model_prob, odds)` — no I/O, must be identical for live detection and backtest replay |
| Kelly stake sizing (`beregn_innsats`) | Shared core (pure function module) | — | Pure math over `(bankroll, prob, odds)` — directly money-critical (Pitfall 5/9), must be single-sourced and tested |
| Bet dedup / staleness guard (`plasser_bets`'s key logic) | Shared core (pure function, extracted) or orchestration layer | Orchestration (`06_bot.py`) | The *decision rule* ("is this key already bet?") is pure and testable; the *loop that applies it to a DataFrame and mutates bankroll* stays in `06_bot.py` (orchestration), which is explicitly not refactored this phase (ODDS-02 is Phase 4) |
| Strategy parameter values (thresholds, Kelly fraction) | Shared core (config module) | — | Single source of truth so a future backtest validates exactly what's deployed (Pitfall 6 — this already happened once with `KALIBRERING_RAPPORT.md`) |
| Test framework/harness | New cross-cutting layer (`tests/`) | — | Not owned by any pipeline stage; verifies the shared core in isolation |
| Live orchestration (subprocess calls to 04/05, bankroll I/O, dashboard render) | Orchestration (`06_bot.py`) | — | Explicitly untouched this phase (D-08 covers pre-existing WIP only, not a refactor of the subprocess boundary — that's ODDS-02/Phase 4) |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pytest` | 9.1.1 (current on PyPI, confirmed via `pip index versions pytest` this session) | Test runner/framework — first automated tests in this repo | Locked by CONTEXT.md D-10 and milestone research SUMMARY.md; de facto standard Python test framework, zero-config for simple pure-function tests, supports the `pythonpath` ini option needed for this repo's flat-module layout (added in pytest 7.0, present in 9.1.1) `[VERIFIED: pypi registry via pip index versions, cross-checked against slopcheck]` |

**Version verification:**
```bash
pip index versions pytest
# pytest (9.1.1)
# Available versions: 9.1.1, 9.1.0, 9.0.3, ...
```
Ran this session (2026-08-20) against the live PyPI index — confirmed current.

### Supporting

None required. `beregn_innsats` and dedup-key tests are pure-function tests over plain floats/tuples — no mocking library, no fixtures library, no coverage tool needed to satisfy CORE-03/CORE-04 as scoped. `unittest.mock`/`responses` become relevant only once tests target the network-calling functions (`hent_siste_lagstats`, `hent_kampresultat`) — out of scope for this phase per D-11/D-12 (those functions are not on CORE-03's required list, and CORE-04 is a determinism test on pure functions only).

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pytest` | `unittest` (stdlib, zero install) | No install-risk at all, but locked out by CONTEXT.md D-10 (explicit user/milestone-research decision); `pytest`'s plain-`assert` style and `pythonpath` ini option are a better fit for a from-scratch suite than `unittest`'s class-based boilerplate |

**Installation:**
```bash
echo "pytest" > requirements-dev.txt
pip install -r requirements-dev.txt
```

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `pytest` | PyPI | ~20 yrs (originally `py.test`, first pytest releases ~2010s) | Hundreds of millions/month (de facto standard Python test runner) | github.com/pytest-dev/pytest | [OK] (ran `slopcheck install pytest` this session — reported `[OK] pytest (pypi)`) | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

slopcheck was available and ran successfully this session (`/opt/homebrew/bin/slopcheck`, invoked as `slopcheck install pytest`). It reported `[OK]` before attempting an actual `pip install` (which failed in the research sandbox only because the sandbox's `pip` binary isn't on PATH as a bare command — irrelevant to the verdict itself; the planner's actual install step should use `pip install -r requirements-dev.txt` or `python -m pip install pytest`, not bare `pip`).

## Architecture Patterns

### System Architecture Diagram

```text
                    ┌─────────────────────────────────────────┐
                    │         SHARED CORE (new, this phase)     │
                    │                                             │
   02_feature_─────▶│  features.py                                │
   engineering.py   │   beregn_lag_form(games_df, vindu=10,       │
   (batch, calls)   │                    as_of=None)              │
                     │   STATS_KOLONNER (single list)             │
   04_value_─────────▶│                                            │
   detector.py       │  teams.py                                  │
   (live, calls)     │   LAG_OPPSLAG (built once)                 │
                      │   finn_lag(navn) -> dict|None              │
   05_skadefilter.py─▶│                                            │
   (live, calls)      │  strategy.py                               │
                       │   fjern_vigorish(odds_hjemme, odds_borte) │
   06_bot.py──────────▶│   beregn_value_og_ev(modell_p, odds)      │
   (live, calls)       │   beregn_innsats(saldo, modell_p, odds)   │
                        │   finn_bet_nokkel(kamp, bet, kamp_dato)  │
   debug_kamp.py───────▶│   er_duplikat(nokkel, historikk)         │
   (optional, calls)    │                                          │
                         │  config.py                              │
                         │   MIN_VALUE_TERSKEL, MIN_ODDS, MAX_ODDS,│
                         │   KELLY_FRAKSJON, MIN/MAX_INNSATS       │
                         └─────────────────┬───────────────────────┘
                                            │
                                            ▼
                          ┌─────────────────────────────────┐
                          │   tests/ (new, this phase)        │
                          │   test_strategy.py  (CORE-03)     │
                          │   test_teams.py                   │
                          │   test_features.py                │
                          │   test_parity.py     (CORE-04,     │
                          │     determinism-scoped per D-12)  │
                          └─────────────────────────────────┘

Not touched this phase: subprocess boundary between 06_bot.py and 04/05
(that's ODDS-02, Phase 4) — 06_bot.py still shells out, but the functions
it eventually imports directly are already the tested, single-sourced
ones by the time that refactor happens.
```

### Recommended Project Structure

```
nba_betting/                       (repo root — unchanged, flat)
├── teams.py                        # NEW — canonical team-name resolver
├── features.py                     # NEW — shared rolling-window feature computation
├── strategy.py                     # NEW — pure value/EV/Kelly/dedup-key functions
├── config.py                       # NEW — single source of truth for strategy constants
├── modell_utils.py                 # UNCHANGED (D-02)
├── 01_hent_data.py                 # UNCHANGED
├── 02_feature_engineering.py       # MODIFIED — imports features.beregn_lag_form instead of its own copy
├── 03_tren_modell.py               # UNCHANGED (D-09 — has pre-existing WIP, not touched)
├── 04_value_detector.py            # MODIFIED — imports teams.finn_lag, features.*, strategy.*, config.*
├── 05_skadefilter.py               # MODIFIED — imports teams.finn_lag
├── 06_bot.py                       # MODIFIED — imports teams.finn_lag, strategy.beregn_innsats, strategy dedup helpers, config.*
├── debug_kamp.py                   # OPTIONALLY MODIFIED + tracked (D-04, planner's call) — imports teams.finn_lag
├── requirements.txt                 # UNCHANGED — runtime deps only
├── requirements-dev.txt            # NEW — pytest
├── pytest.ini                      # NEW — pythonpath = . ; testpaths = tests
└── tests/                          # NEW
    ├── test_teams.py
    ├── test_features.py
    ├── test_strategy.py
    └── test_parity.py
```

### Pattern 1: Canonical team resolver (`teams.py`)

**What:** One dict built once at import time (`LAG_OPPSLAG`), keyed by lowercased `full_name`, `nickname`, and `abbreviation`, plus one lookup function with the same exact-match-then-substring-fallback logic `06_bot.py`'s existing `finn_lag()` closure already implements (the most complete of the four existing implementations — it's the only one with all three key types AND substring fallback).

**When to use:** Every place that currently builds its own `lag_oppslag` dict (`04_value_detector.py:128-135`, `05_skadefilter.py:168-172`, `06_bot.py:76-92`, `debug_kamp.py:13-16`).

**Example (design, not yet in codebase — synthesized from `06_bot.py:76-92`, the most complete existing implementation):**
```python
# teams.py
"""
Delt modul for lag-navn-oppslag.
Erstatter fire uavhengige implementasjoner i 04/05/06/debug_kamp.
"""
from nba_api.stats.static import teams

def bygg_lag_oppslag():
    """Bygger oppslagstabell: navn/kallenavn/forkortelse (lowercase) -> full lag-info."""
    alle_lag = teams.get_teams()
    oppslag = {}
    for lag in alle_lag:
        oppslag[lag["full_name"].lower()]   = lag
        oppslag[lag["nickname"].lower()]     = lag
        oppslag[lag["abbreviation"].lower()] = lag
    return oppslag

LAG_OPPSLAG = bygg_lag_oppslag()  # bygges én gang ved import

def finn_lag(navn):
    """
    Slår opp lag-info fra et navn (full_name, nickname, eller abbreviation).
    Faller tilbake til substreng-match hvis eksakt match ikke finnes.
    Returnerer lag-dict (id, full_name, abbreviation, nickname, ...) eller None.
    """
    navn = navn.lower()
    if navn in LAG_OPPSLAG:
        return LAG_OPPSLAG[navn]
    for nøkkel, info in LAG_OPPSLAG.items():
        if nøkkel in navn or navn in nøkkel:
            return info
    return None
```
Callers extract what they need: `04_value_detector.py` wants `.["id"]`, `06_bot.py` wants `.["abbreviation"]` too — `finn_lag()` returning the full dict is a superset that satisfies every current caller without loss of information (`05_skadefilter.py` currently uses only full_name/nickname as keys with no abbreviation — switching it to `finn_lag()` slightly *broadens* its match surface; this is intentional unification, not a behavior regression, since abbreviation-based matching only adds match cases, never removes them).

### Pattern 2: `as_of`-aware feature computation (`features.py`) — scoping recommendation

**What:** `02_feature_engineering.py::beregn_lag_form(df_raw, vindu=10)` (lines 35-97) is **already leakage-safe per row** today: it computes `alle.groupby("TEAM_ID")[kol].transform(lambda x: x.shift(1).rolling(window=vindu, min_periods=3).mean())` over the full historical DataFrame sorted by date — `shift(1).rolling(...)` at row *i* only ever reads rows strictly before *i* for that team, so appending future rows to the input DataFrame cannot change any already-computed row's value (rolling windows only look backward). This means the *mechanical* leakage-safety ARCHITECTURE.md's Pattern 2 worries about is not actually broken in the current code — the risk is **duplication of the stat list and window size**, not a rolling-window bug.

**Recommended shape for `features.py` this phase (MEDIUM confidence — reasoned synthesis, not a locked CONTEXT.md decision; flag for planner confirmation):**
```python
# features.py
STATS_KOLONNER = ["PTS", "FG_PCT", "FT_PCT", "FG3_PCT", "REB", "AST", "TOV", "PLUS_MINUS", "VANT"]
RULLENDE_VINDU = 10

def beregn_lag_form(df_raw, vindu=RULLENDE_VINDU, as_of=None):
    """
    Beregner rullende gjennomsnitt for hvert lag (identisk logikk som
    tidligere 02_feature_engineering.py::beregn_lag_form).

    'as_of', hvis satt, filtrerer df_raw til rader med
    GAME_DATE_HJEMME < as_of FØR rullende-vindu-beregningen kjøres.
    Dette er et forsvar-i-dybden-filter: shift(1)-logikken er allerede
    leakage-safe per rad, men et eksplisitt as_of-filter gjør funksjonen
    trygg å kalle med en full, flersesong DataFrame som inkluderer rader
    etter skjæringsdatoen (fremtidig backtest-bruk, se Phase 5).
    """
    if as_of is not None:
        df_raw = df_raw[df_raw["GAME_DATE_HJEMME"] < as_of]
    # ... resten identisk med eksisterende beregn_lag_form ...
```
This satisfies D-05's "ideally parameterized by an `as_of`-style cutoff... without modification" while explicitly NOT redesigning the rolling-window mechanics (per D-05's "do not change the actual feature set/columns... this is an extraction, not a feature redesign").

**What is explicitly out of scope this phase:** Unifying this batch function with the live path's `hent_siste_lagstats()` (`04_value_detector.py:102-126`), which fetches the last N games via a live `nba_api` call and computes a flat `.mean()` (no `shift`/`rolling` needed — the fetched rows are inherently "already played, before today"). These two functions solve the same *goal* ("last 10 games' average stats per team") via different *mechanics* because their data sources differ (full historical CSV vs. live API response). Full unification into one data-source-agnostic function is `ARCHITECTURE.md`'s `data/games.py` adapter work, assigned to Phase 4/5's build order (item 4), not this phase. **What this phase must still do to close Pitfall 8's actual risk:** make `hent_siste_lagstats()` import `STATS_KOLONNER` from `features.py` instead of hardcoding its own `stats = ["PTS", "FG_PCT", ...]` list (`04_value_detector.py:173`) — this is the cheap, load-bearing fix that prevents the stat list itself from silently diverging, even though the two *mechanics* remain temporarily separate.

**Recommend the planner explicitly confirm this scoping split (as_of pre-filter + single stat-list constant now; full data-source unification deferred) rather than attempting full mechanical unification in Phase 2** — attempting the latter would pull `data/games.py`-shaped work (an nba_api adapter redesign) into a phase whose CONTEXT.md explicitly scopes it as "extraction, not a feature redesign."

### Pattern 3: Pure-function `strategy.py`

**What:** Extract vig removal, value/EV calculation (`04_value_detector.py:207-225`), and Kelly stake sizing (`06_bot.py::beregn_innsats`, lines 202-222) as pure functions — no I/O, no global state, deterministic given inputs.

**Example (synthesized directly from existing code, values/logic unchanged per D-07):**
```python
# strategy.py
def fjern_vigorish(odds_hjemme, odds_borte):
    """Normaliserer implisitte sannsynligheter fra odds til å summere 100% (fjerner bookmakerens margin)."""
    impl_hjemme = 1 / odds_hjemme
    impl_borte  = 1 / odds_borte
    total = impl_hjemme + impl_borte
    return impl_hjemme / total, impl_borte / total

def beregn_value_og_ev(modell_prob, odds, impl_prob):
    """VALUE = modellens sannsynlighet minus bookmakerens (vig-frie) implisitte. EV = (modell_prob * odds) - 1."""
    value = modell_prob - impl_prob
    ev    = (modell_prob * odds) - 1
    return value, ev

def beregn_innsats(saldo, modell_prob, odds, kelly_fraksjon, min_innsats, max_innsats):
    """Halvt Kelly-kriteriet — identisk logikk som eksisterende 06_bot.py::beregn_innsats,
    men med konfigverdier som parametre i stedet for globale konstanter, slik at
    strategy.py forblir en ren funksjon uten avhengighet til config.py."""
    b = odds - 1.0
    p = modell_prob
    q = 1.0 - p
    kelly = (b * p - q) / b
    if kelly <= 0:
        return 0.0
    innsats = saldo * kelly * kelly_fraksjon
    return round(max(min_innsats, min(max_innsats, innsats)), 2)

def finn_bet_nokkel(kamp, bet, kamp_dato):
    """Bygger dedup-nøkkelen brukt til å hindre dobbel-betting på samme fysiske kamp."""
    return (kamp, bet, kamp_dato)

def er_duplikat(nokkel, eksisterende_nokler):
    """Ren prediker-funksjon over dedup-settet — testbar uten DataFrame/I/O."""
    return nokkel in eksisterende_nokler
```
Note the `beregn_innsats` signature takes `kelly_fraksjon`/`min_innsats`/`max_innsats` as parameters rather than importing `config.py`'s constants directly inside `strategy.py` — this keeps `strategy.py` a zero-dependency pure-function module (importable and testable without any other project module), while `06_bot.py` and the future backtest both pass in `config.KELLY_FRAKSJON` etc. at the call site. This is a design choice for the planner to confirm or override (Claude's Discretion per CONTEXT.md) — the alternative (importing `config` directly inside `strategy.py`) is also valid and slightly less boilerplate at every call site; either satisfies CORE-02/CORE-03.

### Pattern 4: `config.py` single source of truth

**What:** Module-level `UPPER_SNAKE_CASE` constants (matches CLAUDE.md's established convention), copied verbatim from current values — no changes per D-07.

**Example:**
```python
# config.py
"""Enkelt sannhets-kilde for strategiparametre. Importeres av live-bot og fremtidig backtest."""
MIN_VALUE_TERSKEL = 0.05    # Flagg bets der vi er 5%+ over bookmaker (fra 04_value_detector.py)
MIN_ODDS          = 1.50    # Ikke bett på favoritter med veldig lave odds
MAX_ODDS          = 4.00    # Ikke bett på store outsidere (over 4x = for usikkert)
KELLY_FRAKSJON    = 0.5     # Halvt Kelly (konservativt – reduserer varians) (fra 06_bot.py)
MAX_INNSATS       = 150.0   # Aldri mer enn 150 kr på ett bet
MIN_INNSATS       = 20.0    # Aldri mindre enn 20 kr
STARTKAPITAL      = 1000.0  # kr
```
Exact current values confirmed by direct read this session: `04_value_detector.py:43-45` (`MIN_VALUE_TERSKEL=0.05`, `MIN_ODDS=1.50`, `MAX_ODDS=4.00`) and `06_bot.py:33-38` (`KELLY_FRAKSJON=0.5`, `MAX_INNSATS=150.0`, `MIN_INNSATS=20.0`, `STARTKAPITAL=1000.0`).

### Pattern 5: pytest discovery for a flat, package-less repo

**What:** With zero `__init__.py` files anywhere (confirmed — no packages exist in this repo), pytest's default "prepend" import mode adds only the **test file's own directory** (`tests/`) to `sys.path` when collecting — NOT the repo root. Without configuration, `tests/test_strategy.py` doing `from strategy import beregn_innsats` would raise `ModuleNotFoundError` because `strategy.py` lives at repo root, not in `tests/`.

**The fix — `pythonpath` ini option (built into pytest since 7.0.0, confirmed compatible with the verified-current `9.1.1`):**
```ini
# pytest.ini (repo root)
[pytest]
pythonpath = .
testpaths = tests
```
This explicitly adds the repo root to `sys.path` for the duration of the test session, independent of import mode (`prepend`/`importlib`) and independent of whether tests are invoked as `pytest` or `python -m pytest`. This is the officially documented, config-file-based solution — cleaner than relying on `python -m pytest`'s incidental cwd-insertion behavior (which only works if invoked exactly that way) or a root `conftest.py`'s side-effect `sys.path` insertion (works, but less explicit/discoverable).

`[CITED: docs.pytest.org/en/stable/reference/customize.html, docs.pytest.org/en/stable/explanation/pythonpath.html]` — confirmed via WebSearch this session that `pythonpath` was added as a built-in pytest 7.0.0 feature (replacing the separate `pytest-pythonpath` plugin), syntax `[pytest]\npythonpath = .` in `pytest.ini`. Exact online docs page for `pythonpath` returned partial content via WebFetch (page structure didn't surface the full syntax table), so this is **MEDIUM-HIGH** confidence (multiple independent search results corroborate the syntax and version; not a direct single-page doc quote).

**Recommend `pytest.ini` over a `pyproject.toml` `[tool.pytest.ini_options]` section:** the repo has zero `pyproject.toml` today (confirmed — `ls` shows none) and no packaging/build-system need is in scope for this phase (D-01 explicitly defers the `nba_betting/` package). Introducing a `pyproject.toml` now would imply a packaging intent this phase doesn't have. A bare `pytest.ini` is the minimal, purpose-scoped config file. `conftest.py`-only (no ini file) was considered and rejected as primary mechanism — it works but is a less explicit/documented mechanism than the ini option and doesn't self-document `testpaths`.

### Anti-Patterns to Avoid

- **Writing a fourth team-lookup implementation "just for tests"** — test fixtures should call the real `teams.finn_lag()`, not reimplement lookup logic inline in `test_teams.py`.
- **Skipping the `as_of` parameter "because the backtest doesn't exist yet"** — D-05 explicitly wants this added now so Phase 5 doesn't need to modify `features.py`'s signature later, which would re-touch (and risk re-diverging) both call sites.
- **Importing `config.py` constants directly into `strategy.py` function *bodies* as module-level globals instead of parameters** — makes `strategy.py` functions harder to unit test with edge-case values (e.g., testing `beregn_innsats` with a different Kelly fraction than the live config) and creates an import-order coupling. Prefer passing config values as parameters (Pattern 3) or, if importing directly, at minimum keep `config.py` as `strategy.py`'s *only* import so the coupling is single and obvious.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Team-name string matching | A fifth ad hoc lookup dict/substring-match implementation | The canonical `teams.finn_lag()` (Pattern 1) | Already reimplemented 4 times with subtly different key sets — a 5th copy (even a test-only one) reintroduces the exact drift risk this phase exists to close |
| Vig-free probability normalization | A different vig-removal formula in the backtest later | The single `strategy.fjern_vigorish()` this phase creates | Pitfall 4 (PITFALLS.md) — vig-removal errors are one of the most common ways "value" gets manufactured out of bookmaker margin rather than genuine model edge; must be single-sourced now, before a backtest exists to duplicate it a third way |
| Kelly stake sizing | A backtest-only reimplementation of `beregn_innsats` | The extracted `strategy.beregn_innsats()` | Pitfall 5/9 — money-math functions are exactly where untested, duplicated logic has already caused a real bug in this project (bankroll drawdown, dedup bug) |
| pytest path/import configuration | A custom `sys.path.insert(...)` hack at the top of every test file | `pytest.ini`'s `pythonpath = .` (Pattern 5) | One central, documented config beats N per-file hacks; also survives future test files without needing the same boilerplate copy-pasted |

**Key insight:** Every "don't hand-roll" item in this phase is really the same insight repeated: this codebase's core recurring failure mode is *not* "used the wrong library" — it's "reimplemented the same small function in a second/third/fourth place." The fix in every case is one canonical function, not a smarter algorithm.

## Common Pitfalls

### Pitfall 1: Extracting logic while accidentally changing a value or edge case

**What goes wrong:** During extraction, a "cleanup" temptation appears — e.g., "while I'm here, let me also fix the substring-match order" or "let me round differently." This silently changes behavior in a phase whose entire premise is behavior-preserving extraction (D-07 explicitly locks the threshold values; the same discipline applies to every extracted function's exact logic).
**Why it happens:** Refactoring and improving get mentally bundled, especially when the "obviously better" version is right there.
**How to avoid:** Extract by literal copy first, then only change import statements at call sites. Any behavior change (even a seemingly-obviously-correct one, like unifying `05_skadefilter.py`'s narrower key set with `teams.py`'s broader one) should be called out explicitly as an intentional behavior change in the plan/commit message, not silently bundled into "extraction."
**Warning signs:** A diff on `04_value_detector.py`/`05_skadefilter.py`/`06_bot.py` that changes more than import statements + the deleted duplicated function body + the call-site update to use the imported name.

### Pitfall 2: `pytest` collected but nothing actually runs (silent 0-test pass)

**What goes wrong:** Without `testpaths` set and without following `test_*.py` naming, `pytest` can exit 0 having collected zero tests — which looks like "tests pass" in a shell script or human glance at exit code, masking a config mistake.
**Why it happens:** This is the *first* test suite in the repo — there's no existing CI/precedent to catch a misconfigured `pytest.ini` or a test file that doesn't match `test_*.py`/`*_test.py` naming.
**How to avoid:** After writing `pytest.ini` and the first test file, run `pytest -v` (not just `pytest`) and manually confirm the printed test count is > 0, not just that the exit code is 0. Add this as an explicit verification step in the plan (not just "tests exist" but "tests are collected and executed").
**Warning signs:** `pytest` output showing "no tests ran" or "0 collected" — easy to miss if only checking `$?`.

### Pitfall 3: `as_of` filter uses the wrong column or comparison direction

**What goes wrong:** `features.py`'s new `as_of` parameter needs to filter on `GAME_DATE_HJEMME < as_of` (strictly before). An off-by-one (`<=` instead of `<`) would let the game being predicted leak its own row into its own rolling-average computation for a future backtest — exactly the leakage class this phase's CORE-04 test is supposed to catch.
**Why it happens:** `<` vs `<=` boundary errors are a classic leakage bug and easy to get backwards under time pressure.
**How to avoid:** The determinism test (CORE-04, Pattern per D-12) should explicitly include a case that appends a *same-day* future row and asserts it does NOT change the `as_of`-filtered feature output for that day — not just an arbitrary "different date" case.
**Warning signs:** A CORE-04 test that only checks two *different* `as_of` dates rather than testing the boundary condition directly.

### Pitfall 4: Dedup-key test passes but doesn't test the real risk (stale-row bug precedent)

**What goes wrong:** `06_bot.py`'s existing code comment (line 260-263) references an already-fixed 2026-08-19 stale-row bug where already-processed bets got re-bet. A shallow dedup test ("same tuple twice → detected as duplicate") doesn't actually cover that historical bug's shape (a row with a *different* `kamp_dato` field due to a pipeline staleness issue slipping past the dedup key).
**Why it happens:** It's easy to write the "obvious" happy-path dedup test and consider CORE-03 satisfied without covering the specific historical failure mode the comment documents.
**How to avoid:** Include at least one test case modeling the documented stale-row scenario: a bet record that would be a "new" bet under a naive `(kamp, bet)` key but should be caught as a duplicate once `kamp_dato` is included in the key (or vice versa — confirm the key design actually distinguishes the two dates that caused the original bug).
**Warning signs:** `test_strategy.py`'s dedup tests only exercise exact-duplicate and clearly-different cases, no near-duplicate/stale-date case.

## Runtime State Inventory

> This phase is a code extraction/refactor (moving functions between files), not a rename/rebrand/data-migration. Applying the canonical question ("after every file is updated, what runtime systems still have the old thing cached/stored/registered?") explicitly:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `bankroll.json`/`bets.json` store bet *records* (dicts with `kamp`/`bet`/`odds`/etc. keys), not references to which Python file/function computed them. Moving `beregn_innsats` from `06_bot.py` to `strategy.py` does not change any persisted JSON shape. | None |
| Live service config | None — no external service (n8n, Datadog, etc.) references these file/function names. | None |
| OS-registered state | None — confirmed in STATE.md/CLAUDE.md that no cron/Task Scheduler entry exists for this project; `06_bot.py` is invoked manually. | None |
| Secrets/env vars | None — `ODDS_API_NOKKEL` (Phase 1) is unaffected; no secret references a function/module name being moved. | None |
| Build artifacts / installed packages | None — none of `teams.py`/`features.py`/`strategy.py`/`config.py` become an installed package this phase (D-01 explicitly keeps them flat, not a `pip install -e .`-able package); no `.egg-info` or compiled artifact exists to go stale. | None |

**Nothing found in any category** — this phase's only "runtime state" risk is the already-covered case of `nba_modell.pkl`'s pickle depending on an importable class name (`KalibrertModell` in `modell_utils.py`), and D-02 explicitly confirms `modell_utils.py` is untouched this phase, so that risk does not apply here either.

## Code Examples

### pytest.ini (repo root)
```ini
# Source: pytest official docs — pythonpath ini option (pytest >= 7.0)
[pytest]
pythonpath = .
testpaths = tests
```

### Example unit test shape for CORE-03 (`beregn_innsats`)
```python
# tests/test_strategy.py
from strategy import beregn_innsats

def test_beregn_innsats_negativ_edge_gir_null():
    # Modellsannsynlighet lik markedets implisitte -> ingen edge -> 0 kr innsats
    innsats = beregn_innsats(saldo=1000.0, modell_prob=0.40, odds=2.50,
                              kelly_fraksjon=0.5, min_innsats=20.0, max_innsats=150.0)
    assert innsats == 0.0

def test_beregn_innsats_respekterer_maks_innsats():
    innsats = beregn_innsats(saldo=100000.0, modell_prob=0.90, odds=1.60,
                              kelly_fraksjon=0.5, min_innsats=20.0, max_innsats=150.0)
    assert innsats == 150.0
```

### Example determinism test shape for CORE-04 (per D-12 scoping)
```python
# tests/test_parity.py
from features import beregn_lag_form

def test_as_of_filter_er_deterministisk_og_leakage_safe(fixture_games_df):
    # Samme input, samme as_of -> identisk output (referential transparency)
    a = beregn_lag_form(fixture_games_df, as_of="2024-12-01")
    b = beregn_lag_form(fixture_games_df, as_of="2024-12-01")
    pd.testing.assert_frame_equal(a, b)

def test_fremtidige_rader_pavirker_ikke_tidligere_features(fixture_games_df, fixture_future_row):
    before = beregn_lag_form(fixture_games_df, as_of="2024-12-01")
    after  = beregn_lag_form(pd.concat([fixture_games_df, fixture_future_row]), as_of="2024-12-01")
    pd.testing.assert_frame_equal(before, after)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| N/A — no prior test framework existed to migrate from | `pytest` (this phase) | This phase, 2026-08-20 | First automated regression safety net in the repo's history |

**Deprecated/outdated:** Nothing in this phase deprecates prior project code beyond the duplicated implementations it directly replaces.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | `features.py`'s `as_of` parameter should be a pre-filter on the input DataFrame's date column rather than a mechanical redesign of the rolling-window computation, and full data-source unification between batch and live feature computation is out of scope for this phase | Architecture Patterns, Pattern 2 | If the planner/user actually wants full mechanical unification now (pulling in `nba_api` adapter work), the phase's task list would need `data/games.py`-shaped work this research explicitly scoped out — could under-scope Phase 2 or misalign with Phase 4/5's later build order |
| A2 | `strategy.py`'s functions should take config values as parameters rather than importing `config.py` directly | Architecture Patterns, Pattern 3 | Low risk — explicitly flagged as Claude's Discretion in CONTEXT.md; either design satisfies CORE-02/CORE-03, this is a style recommendation only |
| A3 | pytest 7.0's `pythonpath` ini option works correctly with pytest 9.1.1 and is the right primary fix (vs. relying on `python -m pytest` invocation or a root `conftest.py`) | Architecture Patterns, Pattern 5 | If somehow incompatible, tests would fail to import shared modules; low risk since this is a long-stable, non-deprecated pytest core feature, but the exact docs page content could not be fully confirmed via WebFetch this session (partial page returns) — cross-verified via multiple independent WebSearch results instead |
| A4 | `05_skadefilter.py` switching from its narrower (full_name/nickname-only) lookup to the canonical `teams.finn_lag()` (which also matches on abbreviation) is a safe behavior *broadening*, not a regression | Pattern 1 | If some abbreviation string collides ambiguously with an unrelated substring match, `05_skadefilter.py` could resolve a different team than before for an edge-case name — low probability (NBA team abbreviations are short and distinct) but worth a planner verification step, e.g. a `test_teams.py` case asserting every known Odds-API/nba_api team string resolves to the expected team |

**If this table is empty:** N/A — see entries above; all are MEDIUM risk at most, none block planning.

## Open Questions

1. **Should `debug_kamp.py` be tracked in git and migrated to `teams.py` this phase, or left as a separate untracked hygiene item?**
   - What we know: It's currently untracked (confirmed via `git status` this session), duplicates the team-lookup pattern (`debug_kamp.py:13-16`), and CONTEXT.md D-04 explicitly defers this exact decision to "planner/research judgement call."
   - What's unclear: Whether tracking it now (small, cheap — 62 lines, no dependencies beyond what's already imported elsewhere) is worth bundling into this phase's scope vs. keeping the phase strictly focused on the 4 already-tracked pipeline files.
   - Recommendation: Track it and migrate it to `teams.finn_lag()` in this phase — it's a trivial, zero-risk addition (one file, no runtime dependents, already confirmed to duplicate the exact pattern this phase exists to fix) and leaving a 4th untracked duplicate of the pattern feels inconsistent with the phase's stated goal ("no more silent drift"). But this is explicitly flagged as the planner's call per D-04, not a locked decision from this research.

2. **Should the dedup-key pure functions (`finn_bet_nokkel`/`er_duplikat`) live in `strategy.py` or stay inline in `06_bot.py::plasser_bets` with only the *test* importing them via a refactor?**
   - What we know: D-11 requires the dedup logic be "extracted into testable pure functions" — it doesn't specify which module.
   - What's unclear: `strategy.py` is the closest fit conceptually (decision logic, not orchestration), but it's also plausible the planner wants a dedicated small module or to keep it in `06_bot.py` as a private-but-testable function (`_finn_bet_nokkel`).
   - Recommendation: Put it in `strategy.py` alongside `beregn_innsats` (both are "given inputs, decide something" pure functions) — this is Claude's Discretion territory per CONTEXT.md, not a blocking question, but flagged since D-11's wording is genuinely silent on module placement.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|----------|
| Python 3 | All shared modules, tests | ✓ | 3.14.3 (both system `python3` and repo `venv/bin/python`) | — |
| `pytest` | CORE-03, CORE-04 test execution | ✗ (not installed in venv or system — confirmed via `./venv/bin/python -m pytest --version` and `pip3 show pytest`, both report not found) | Latest on PyPI: 9.1.1 | Install via `pip install -r requirements-dev.txt` — no fallback needed, this is a first-time install, not a version mismatch |
| `pandas`, `numpy` | `features.py` tests (DataFrame fixtures) | ✓ (already a runtime dependency, present in `venv/`) | pandas 3.0.1, numpy 2.4.3 (per CLAUDE.md's documented `venv/` inventory) | — |
| `slopcheck` | Package legitimacy verification (research-time only, not a phase runtime dependency) | ✓ (installed at `/opt/homebrew/bin/slopcheck` this session) | — | — |

**Missing dependencies with no fallback:**
- `pytest` — must be installed as part of this phase's first task (add to `requirements-dev.txt`, `pip install`). Not a blocker, just an explicit first step.

**Missing dependencies with fallback:** none.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 (to be installed this phase — currently absent) |
| Config file | `pytest.ini` (new, this phase) — `[pytest]\npythonpath = .\ntestpaths = tests` |
| Quick run command | `pytest -v` |
| Full suite command | `pytest -v` (suite is small enough that "quick" and "full" are identical this phase — no slow/integration tests are in scope) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| CORE-01 | `teams.finn_lag()` resolves every known team-name variant (full_name, nickname, abbreviation, substring) to the correct team | unit | `pytest tests/test_teams.py -v` | ❌ Wave 0 |
| CORE-01 | `features.beregn_lag_form()` produces the same output shape/values as the current `02_feature_engineering.py::beregn_lag_form()` on a fixed fixture (no silent behavior change during extraction) | unit | `pytest tests/test_features.py -v` | ❌ Wave 0 |
| CORE-01 | `strategy.fjern_vigorish()`/`beregn_value_og_ev()` reproduce the exact current `04_value_detector.py` math on known inputs | unit | `pytest tests/test_strategy.py -v` | ❌ Wave 0 |
| CORE-02 | `config.py` constants match the exact current values (0.05 / 1.50 / 4.00 / 0.5 / 150.0 / 20.0 / 1000.0) — no drift during extraction | unit | `pytest tests/test_strategy.py::test_config_values -v` (or equivalent) | ❌ Wave 0 |
| CORE-03 | `beregn_innsats` — negative edge → 0.0; min/max stake clamping; half-Kelly fraction applied correctly | unit | `pytest tests/test_strategy.py -k innsats -v` | ❌ Wave 0 |
| CORE-03 | Bet dedup key logic — exact duplicate detected; stale-row-shaped near-duplicate scenario (Pitfall 4) covered | unit | `pytest tests/test_strategy.py -k dedup -v` | ❌ Wave 0 |
| CORE-04 | `features.beregn_lag_form(..., as_of=D)` is deterministic and unaffected by rows with `game_date >= D` appended to input | unit (determinism/leakage regression, scoped per D-12) | `pytest tests/test_parity.py -v` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest -v` (full suite — small enough to run every time, no need for a separate "quick" subset this phase)
- **Per wave merge:** `pytest -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `pytest.ini` — framework config, enables `import teams`/`import features`/`import strategy` from `tests/`
- [ ] `requirements-dev.txt` — pytest install
- [ ] `tests/` directory + all 4 test files listed above — none exist yet, this phase creates the entire suite from scratch
- [ ] `tests/conftest.py` — shared fixtures (a small synthetic games DataFrame fixture is needed by both `test_features.py` and `test_parity.py`; consider a single `fixture_games_df` fixture here to avoid duplicating fixture-construction logic between the two test files — the same "don't duplicate" discipline this phase is enforcing on production code should apply to its own tests)

## Security Domain

This phase's scope (pure-function extraction + first test suite, no new external inputs, no new network calls, no new persisted data shape) has minimal security surface. Evaluated against ASVS categories for completeness:

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|-----------------|---------|---------------------|
| V2 Authentication | No | No auth surface exists or is touched this phase |
| V3 Session Management | No | Single-user, no sessions |
| V4 Access Control | No | Single-user local tool |
| V5 Input Validation | Yes (lightweight, pre-existing) | `teams.finn_lag()` handles untrusted external strings (Odds-API team names) — the existing pattern (return `None` on no match, caller skips/logs) is already the correct approach and should be preserved unchanged in the extraction, not tightened or loosened |
| V6 Cryptography | No | No crypto in scope; the pre-existing `pickle`-based model serialization (flagged in PITFALLS.md's Security Mistakes table) is `modell_utils.py`/`03_tren_modell.py` territory, explicitly untouched this phase (D-02/D-09) |

### Known Threat Patterns for this stack

Not meaningfully applicable this phase — no new external attack surface is introduced (no new network endpoint, no new user input, no new persisted secret). The one pre-existing item worth carrying forward as a note (not a Phase 2 action item): `nba_modell.pkl`'s `pickle`-based serialization is a known low-but-nonzero risk (arbitrary code execution if ever loaded from an untrusted source) per PITFALLS.md's Security Mistakes table — out of scope for this phase since `modell_utils.py` is untouched (D-02).

## Sources

### Primary (HIGH confidence)
- Direct source read this session: `02_feature_engineering.py`, `04_value_detector.py`, `05_skadefilter.py`, `06_bot.py`, `debug_kamp.py`, `modell_utils.py` — all line numbers and current constant values cited above are from this session's direct reads, not recalled from prior research
- `pip index versions pytest` (run this session, 2026-08-20) — confirmed `9.1.1` current on PyPI
- `slopcheck install pytest` (run this session) — confirmed `[OK]` verdict
- `.planning/phases/02-shared-core-extraction-test-foundation/02-CONTEXT.md` — locked decisions, copied verbatim into User Constraints
- `.planning/codebase/TESTING.md` — prior codebase-level testing audit, directly informed Standard Stack and Validation Architecture recommendations

### Secondary (MEDIUM confidence)
- [pytest — Configuration](https://docs.pytest.org/en/stable/reference/customize.html) — confirmed rootdir does NOT modify sys.path (WebFetch this session, partial page content)
- [pytest — import mechanisms and sys.path/PYTHONPATH](https://docs.pytest.org/en/stable/explanation/pythonpath.html) — confirmed flat-module-without-`__init__.py` behavior and `pythonpath` ini option existence (WebFetch this session, partial page content — corroborated by WebSearch results below)
- [pytest 7.0.0 discussion — pythonpath ini option](https://github.com/pytest-dev/pytest/discussions/9635) and [pytest-dev/pytest#9636](https://github.com/pytest-dev/pytest/issues/9636) — confirmed `pythonpath` was added as a built-in pytest 7.0.0 feature (WebSearch this session)
- `.planning/research/ARCHITECTURE.md` (milestone-level research, 2026-08-19) — `as_of`-aware `features.py` pattern, Pattern 2 (leakage regression test), shared-core architectural principle — HIGH confidence per that document's own sourcing (NautilusTrader/QuantConnect/Freqtrade precedent)
- `.planning/research/PITFALLS.md` (milestone-level research, 2026-08-19) — Pitfall 8 (train/serve feature skew) and Pitfall 9 (no test coverage on money-math) directly addressed by this phase

### Tertiary (LOW confidence)
- None — all claims in this document are either directly grounded in this session's source reads/tool runs, or cited against official pytest documentation/milestone research with cross-verification.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — single dependency (`pytest`), verified against live PyPI registry and slopcheck this session
- Architecture (extraction design): HIGH for `teams.py`/`strategy.py`/`config.py` (directly derived from existing, read source code); MEDIUM for `features.py`'s exact `as_of` mechanical shape (reasoned synthesis, flagged as Assumption A1 for planner confirmation)
- Pitfalls: HIGH — all four pitfalls above are either directly observable in the current code (stale-row comment, no test infra) or standard extraction/pytest-config failure modes, not speculative
- Testing/pytest config: HIGH — cross-verified via multiple independent WebSearch results and partial WebFetch confirmation of official docs, plus confirmed compatible with the exact pytest version (9.1.1) that will be installed

**Research date:** 2026-08-20
**Valid until:** 30 days (stable domain — no fast-moving external dependency; the only expiring fact is the `pytest` version pin, which the planner should re-verify with `pip index versions pytest` if this research is consumed more than a few weeks after the date above)

---
*Phase: 2-Shared Core Extraction & Test Foundation*
*Research completed: 2026-08-20*
