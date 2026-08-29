# Phase 4: Historical Odds Acquisition & Live Refactor - Research

**Researched:** 2026-08-23
**Domain:** The Odds API v4 historical endpoints (credit-cost model, request/response shape), SQLite append-only archival patterns, Python subprocess-to-import refactor
**Confidence:** MEDIUM-HIGH overall — HIGH on the verified API cost model (this is the phase's single highest-stakes finding and it is sourced from the raw official docs HTML, not a summary), HIGH on the refactor pattern (precedent already exists in this repo), MEDIUM on exact credit budget (depends on commence-time clustering not yet measured against real data)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Odds snapshot timing**
- **D-01:** The live bot runs once daily, in the morning of game day (locked in this discussion). The historical fetch must pin the same offset: snapshot odds at the closest available reading to morning-of-game-day for each event, not the closing line.

**Fetch scope (credit budget)**
- **D-02:** Fetch both the morning-of bet-time snapshot AND the closing-line snapshot for every archived event, in this same paid month — not bet-time only. Original math assumed ~2 credits/event (1 discovery + 1 fetch) for bet-time-only ≈ 7,300 credits, bet-time+closing ≈ 10,900 credits, for ~3,638 games. **⚠️ See "CRITICAL FINDING" below — this math was built on a per-event cost assumption that this research found to be incorrect against the current official docs. The credit totals below must be re-derived before any fetch runs.**
- **D-03:** Use the per-event historical odds endpoint (`/v4/historical/sports/{sport}/events/{eventId}/odds`), never the sport-wide snapshot endpoint (`/v4/historical/sports/{sport}/odds`) — stated as a hard requirement based on a claimed 10x cost difference favoring per-event. **⚠️ See "CRITICAL FINDING" below — official docs show the opposite cost relationship for this project's use case (many events, featured h2h market). This decision's stated rationale does not hold and needs to be revisited by the user/planner before execution.**
- **D-04:** SQLite archive is genuinely permanent/append-only — no cache-expiry/TTL logic. Before spending any credit, the fetch must check "do I already have this event+snapshot-type archived?" and skip if so.

**06_bot.py refactor shape (ODDS-02)**
- **D-05:** `04_value_detector.py` and `05_skadefilter.py` each get their core logic extracted into importable functions, while remaining standalone-runnable via an `if __name__ == "__main__":` guard that calls those same functions — mirroring the pattern already established for `features.py`/`strategy.py`/`teams.py` in Phase 2. `06_bot.py` imports and calls these functions directly, replacing the two `subprocess.run(...)` calls.
- **D-06:** This refactor removes the hardcoded `venv/lib/python3.10/site-packages` `PYTHONPATH` construction entirely.
- **D-07:** The odds-fetching logic (both live "today's odds" and the new historical archive fetch) lives in one new module, `odds.py`, at repo root — not split across two files. `04_value_detector.py` should import its live-odds fetch from `odds.py` rather than keep its own inline HTTP call.

**Package structure**
- **D-08:** Stay with flat modules at repo root this phase (`odds.py` joins `features.py`/`strategy.py`/`teams.py`/`config.py`) — do NOT introduce the full `nba_betting/` package yet.

### Claude's Discretion
- Exact SQLite filename/location (e.g. `odds_arkiv.db` at repo root) and exact table/column names beyond the composite key `(sport, event_id, market, snapshot_timestamp)`.
- Whether the historical bulk-fetch runs as a new numbered pipeline script (e.g. `07_hent_historisk_odds.py`) or a function invoked from elsewhere — planner's call, but it must be resumable/idempotent per D-04.
- Exact function names extracted from `04_value_detector.py`/`05_skadefilter.py` (Norwegian, snake_case, per established convention).

### Deferred Ideas (OUT OF SCOPE)
- Full `nba_betting/` package restructure (`data/`, `backtest/`, `live/`) — deferred to Phase 5 (D-08).
- Any change to `MIN_VALUE_TERSKEL`, `MAX_ODDS`, or Kelly fraction values — explicitly Phase 5, backtest-gated.
- Grid search / threshold tuning (BTV2-01) and HTML backtest report (BTV2-02) — v2, untouched by this phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ODDS-01 | Historical odds are fetched via The Odds API's per-event historical endpoint and archived permanently in SQLite, so re-running/iterating on the backtest costs no further API credits | See "CRITICAL FINDING" — the verified official cost model means the *endpoint choice* named in ODDS-01's own wording ("per-event") should be revisited with the user before implementation; the "archived permanently in SQLite, re-run costs nothing" part is unaffected and is covered in full by "Architecture Patterns" (SQLite schema + idempotent pre-fetch check) and "Code Examples" below. |
| ODDS-02 | `06_bot.py` imports the shared core directly instead of invoking `04_value_detector.py`/`05_skadefilter.py` as subprocesses | Covered in full by "Architecture Patterns" (extraction pattern, precedent from `features.py`/`strategy.py`/`teams.py`) and "Common Pitfalls" (error-visibility contract change, PYTHONPATH removal validation). |
</phase_requirements>

---

## CRITICAL FINDING: The cost-model premise behind D-02/D-03 does not match current official docs

**This is the single most important finding of this research task, given the user has already spent real money ($30, one month of the 20K-credit tier) on the premise these decisions encode. Do not proceed to the fetch implementation without the user explicitly re-confirming the endpoint choice.**

### What was assumed (per CONTEXT.md / `.planning/research/STACK.md`)
- Per-event historical odds endpoint (`/v4/historical/sports/{sport}/events/{eventId}/odds`) costs **1 × markets × regions** per event.
- Sport-wide historical odds endpoint (`/v4/historical/sports/{sport}/odds`) costs **10 × markets × regions** per call — a flat 10x penalty vs. per-event.
- Conclusion drawn: always use per-event, "confirmed 10x cost difference," treated as a hard requirement (D-03).
- Budget model: ~2 credits/event (1 discovery + 1 fetch) × 3,638 games × 2 snapshot types (bet-time + closing) ≈ 10,900 credits, comfortably under the 20,000-credit budget.

### What the current official docs actually say `[VERIFIED: the-odds-api.com/liveapi/guides/v4/]`

I fetched and parsed the raw HTML of `https://the-odds-api.com/liveapi/guides/v4/` directly (not just an AI-summarized rendering) to get the verbatim "Usage Quota Costs" text for each historical endpoint, since the first two summarized fetches disagreed with each other and with the milestone research. The raw HTML resolves the disagreement unambiguously:

**`GET historical odds`** (sport-wide snapshot, `/v4/historical/sports/{sport}/odds`) — returns *every game* live/upcoming at the requested timestamp in one response:
> "The usage quota cost depends on the number of markets and regions used in the request. `cost = 10 x [number of unique markets returned] x [number of regions specified]`"
> Example: 1 market, 1 region → Cost: 10 — **for the whole snapshot, all games included.**

**`GET historical event odds`** (per-event, `/v4/historical/sports/{sport}/events/{eventId}/odds`) — returns *one game* per call:
> "The usage quota cost depends on the number of markets and regions used in the request. `cost = 10 x [number of unique markets returned] x [number of regions specified]`"
> Example: 1 market, 1 region → Cost: 10 — **per event, per call.**

**Both endpoints use the identical formula (`10 × markets × regions`).** There is no 10x discount for the per-event endpoint — the "10x" in the sport-wide endpoint's example numbers is the *same* 10x multiplier that also applies to the per-event endpoint, not a comparison between the two. The milestone research's STACK.md conflated "cost per call" with "cost per event covered," which is the opposite of what matters when you need many events.

The official docs go further and say so explicitly, in a "Tip" callout directly inside the `GET historical event odds` section:
> "**Tip** When querying historical odds for featured markets, the historical odds endpoint is simpler to implement and more cost-effective."

`h2h` (moneyline — this project's entire v1 scope) is a **featured market**. The docs are telling operators building exactly this project's use case (moneyline, many games) to use the sport-wide endpoint, not the per-event one.

### Why this flips the cost comparison for this project
- **Per-event endpoint:** 10 credits × 1 market × 1 region, **charged once per event queried**. For 3,638 games × 2 snapshot types (bet-time + closing) = 7,276 calls × 10 credits = **~72,760 credits** — over 3.6x the entire 20,000-credit budget. This would fail outright, not just be suboptimal.
- **Sport-wide endpoint:** 10 credits × 1 market × 1 region, **charged once per snapshot call regardless of how many games that call returns**. `nba_features.csv` (2022-10-24 → 2025-04-13) has **480 unique game dates** across 3,638 games (verified by direct computation, `[VERIFIED: nba_features.csv]`, avg 7.6 games/date). One sport-wide call per unique date, at a "morning of game day" timestamp, captures every game that date's odds in a single 10-credit call:
  - Bet-time snapshots: 480 dates × 10 credits = **4,800 credits**
  - Closing-line snapshots: depends on how many distinct commence-time clusters exist per date (see "Open Questions" — not yet measured against real data), but even a conservative 3 clusters/date average = 480 × 3 × 10 = **14,400 credits**
  - Optional discovery pass (`GET historical events`, 1 credit/call, used to learn each date's exact commence times *before* spending odds credits, so the closing-line snapshot can be timed precisely instead of guessed): 480 × 1 = **480 credits**
  - **Total: ~19,680 credits worst-case, ~9,600–14,000 credits realistic** — inside budget, and this is the same total order of magnitude the user already believed they'd spend, just via the correct endpoint.

### Why this matters beyond just cost
D-03 frames per-event as "a hard requirement, not just a cost optimization... using the sport-wide endpoint would blow through the entire month's budget on a fraction of the games." Per the verified numbers above, **this statement has the endpoints' roles reversed**: it is the *per-event* endpoint that would blow through the budget (3.6x over) on this project's full game list, while the sport-wide endpoint is the one that fits.

### Recommendation
This is a factual/technical correction to a locked decision's stated rationale, not a preference the planner should silently override, and not something this research agent should silently "fix" either. Recommend routing back through `/gsd:discuss-phase` (or an explicit `checkpoint:human-verify` early in Phase 4's plan, before any credit-spending call is made) so the user can decide, now armed with the verified numbers:
1. Switch to the sport-wide endpoint (`/v4/historical/sports/{sport}/odds`) as the primary fetch mechanism, keeping the per-event endpoint only as a fallback for markets not covered by the sport-wide response (D-03 would need to be amended).
2. Or, if there's a reason to keep per-event specifically (e.g., wanting per-game deterministic API calls independent of what else is scheduled that day), accept the ~72,760-credit cost, which requires either a much smaller date range, bet-time-only (still ~36,380 credits — still over budget), or purchasing more credits.
3. A hybrid is also possible: sport-wide for the h2h archive (this phase's actual need), per-event reserved for any future non-featured-market work (not in v1 scope).

Option 1 is the only one that fits the existing $30/20K-credit budget the user already spent money on, and is what the official docs themselves recommend for this exact use case. This research does not have the authority to overrule a locked user decision — flagging it here, with full verified evidence, so the planner surfaces it as a blocking pre-flight question rather than silently building against a budget-breaking premise.

---

## Summary

This phase has two independent halves. **ODDS-02** (the `06_bot.py` subprocess-to-import refactor) is low-risk and has a direct precedent already in this codebase: Phase 2 already extracted `features.py`/`strategy.py`/`teams.py`/`config.py` as importable, pure-function, Norwegian-snake_case modules with the exact shape `04_value_detector.py`/`05_skadefilter.py` need to follow. **ODDS-01** (historical odds acquisition) is higher-risk because it spends real, already-paid-for money, and this research found that the locked decision's stated cost-model premise (D-02/D-03) does not match the current official API docs — see the CRITICAL FINDING above, which must be resolved before any fetch script runs.

Beyond the cost model, the mechanics of the fetch are straightforward: The Odds API v4's historical endpoints return a well-defined JSON schema (`timestamp`/`previous_timestamp`/`next_timestamp` wrapper around a `data` payload), report exact credit cost via the `x-requests-last` response header (so the fetch script can log real spend per call, not estimate it), and the whole historical-odds surface is rate-limited to 30 requests/second on paid plans. SQLite's stdlib `sqlite3` module, combined with a `UNIQUE` constraint and a pre-fetch existence check (per D-04), gives a resumable, idempotent archive with no new dependencies. The one place a new (small) dependency is worth adding is `tenacity` for retry/backoff around transient network/429 failures during a long-running, multi-session backfill — `tqdm` for a progress bar is a nice-to-have, not required.

**Primary recommendation:** Route the CRITICAL FINDING back to the user (via `checkpoint:human-verify` or a fresh `/gsd:discuss-phase` pass) before writing any credit-spending code, then build `odds.py` as the single module absorbing both the live fetch (moved out of `04_value_detector.py`) and the historical fetch/archive (backed by SQLite with a pre-fetch existence check), and extract `04_value_detector.py`/`05_skadefilter.py` into importable functions following the exact `features.py`/`strategy.py`/`teams.py` precedent so `06_bot.py` can import and call them directly.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Live odds fetch (today's NBA odds) | Data/API layer (`odds.py`) | — | Pure HTTP client + normalization; no business logic |
| Historical odds fetch + archive | Data/API layer (`odds.py`) + Storage (SQLite) | — | Fetch is I/O; archive is persistence — both belong in `odds.py`'s data-layer responsibility, mirroring the existing `nba_api` wrapper pattern in `01_hent_data.py` |
| Value/EV detection | Decision core (`strategy.py`, already shared) | Orchestration (`04_value_detector.py` as thin caller) | Already correctly placed per Phase 2; this phase only changes how `04_value_detector.py`'s odds *input* is obtained, not the decision logic itself |
| Injury/availability filter | Decision core (extracted function in `05_skadefilter.py`) | Data layer (`nba_api` player-stats fetch, stays inline) | D-05 extracts the decision logic into an importable function; the `nba_api` I/O stays where it is (no new module mandated by CONTEXT.md for this) |
| Daily orchestration (settle, fetch, filter, stake, persist, dashboard) | Orchestration (`06_bot.py`) | — | Owns process sequencing and state; after this phase, calls into `odds.py`/`04_value_detector.py`/`05_skadefilter.py` as in-process function calls instead of subprocesses |
| Bankroll/bet ledger state | Storage (`bankroll.json`/`bets.json`) | — | Unchanged by this phase |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `requests` | already installed (`>=2.31.0` in requirements.txt) | HTTP client for The Odds API — both live and historical calls | Already the project's only HTTP client; `odds.py` should reuse the exact same status-code-check + `sys.exit(1)`-on-failure pattern already established in `04_value_detector.py:75-79` `[CITED: 04_value_detector.py]` |
| `sqlite3` (stdlib) | bundled — verified 3.51.2 on this machine's Python 3.14.3 `[VERIFIED: python3 -c "import sqlite3; print(sqlite3.sqlite_version)"]` | Permanent, queryable, append-only archive for fetched historical odds | Zero new dependency; supports the exact "check before spend" pattern D-04 requires via a single indexed `SELECT` before each API call |
| `python-dotenv` | already installed (`>=1.2.3`, confirmed 1.2.3 present) | Loads `ODDS_API_NOKKEL` — already wired up in `04_value_detector.py` since Phase 1 | No new secret-handling needed; `odds.py`'s historical fetch reuses the same `os.environ.get("ODDS_API_NOKKEL")` + `sys.exit(1)`-if-unset pattern |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tenacity` | 9.1.4 (verified current on PyPI `[VERIFIED: pip index versions tenacity]`) | Retry-with-backoff decorator around each historical-odds HTTP call | A multi-hundred-call resumable backfill (D-04 explicitly anticipates interruption/resume across sessions) should not let one transient 5xx/429 kill an in-progress batch; wrap the single-call function, not the whole loop, so a failed call retries in place before the loop's own "already archived?" check moves on |
| `tqdm` | 4.70.0 (verified current on PyPI `[VERIFIED: pip index versions tqdm]`) | Progress bar for the historical-fetch loop | Optional UX nicety for a script that may run for tens of minutes across ~500-1,500 calls; not required for correctness |

Both `tenacity` and `tqdm` package **names** originate from the milestone `STACK.md` (WebSearch/training-derived), not from Context7 or official docs — per the package-name-provenance rule, both are tagged `[ASSUMED]` below despite passing a PyPI registry existence check. See "Package Legitimacy Audit."

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Sport-wide historical odds endpoint (recommended pending user confirmation, see CRITICAL FINDING) | Per-event historical odds endpoint (as currently locked by D-03) | Per-event costs ~10x more overall for this project's full game list under the verified cost model, but *is* the right choice if the phase later needs non-featured markets (player props) that the sport-wide snapshot doesn't reliably surface — not in v1 scope |
| SQLite stdlib archive | `requests-cache` | Wrong mental model for permanent archival data (TTL/ETag caching assumes data can change on refetch); already rejected in milestone STACK.md for the same reason, this research concurs |
| `sqlite3` stdlib | A tiny flat-file/JSON-lines archive (append-only `.jsonl`) | Would also satisfy "permanent, append-only" but loses the indexed "have I already fetched this?" existence check without loading the whole file into memory every run — SQLite's `UNIQUE` constraint + indexed `SELECT` is strictly better for the resumability requirement (D-04) at effectively zero extra cost (stdlib) |

**Installation:**
```bash
pip install tenacity tqdm
```

**Version verification:** `pip index versions tenacity` → `9.1.4` (current); `pip index versions tqdm` → `4.70.0` (current). Both confirmed against the PyPI registry directly during this research session (2026-08-23).

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `tenacity` | PyPI | ~10 years (first released 2016) — well-established, actively maintained | Very high (widely used retry library; tens of millions/month per PyPI ecosystem-wide usage patterns) | `github.com/jd/tenacity` | Not run — see note below | Approved, tagged `[ASSUMED]` |
| `tqdm` | PyPI | ~11 years (first released 2015) — extremely well-established | Very high (one of the most-downloaded PyPI packages) | `github.com/tqdm/tqdm` | Not run — see note below | Approved, tagged `[ASSUMED]` |

**Note on slopcheck:** `slopcheck` (v. installed via Homebrew, confirmed present at `/opt/homebrew/bin/slopcheck`) was available in this environment, but its only interface (`slopcheck install <pkg>`) performs a live `pip install` into the active environment as part of its check-then-install flow. This research session deliberately did not run it, to avoid mutating the project's git-committed `venv/` directory as a side effect of a research task. Package existence and currency were instead confirmed via `pip index versions` directly against the PyPI registry (see Standard Stack table). Per the package-legitimacy protocol's package-name-provenance rule, both packages remain tagged `[ASSUMED]` (not `[VERIFIED]`) because the package *names* originated from WebSearch/training knowledge (via the milestone STACK.md), not Context7 or official docs — registry existence alone doesn't upgrade that tag. **The planner should gate the actual `pip install tenacity tqdm` behind a `checkpoint:human-verify` task**, at which point running `slopcheck install tenacity tqdm` for real (accepting that it will install) is a fast, cheap confirmation immediately before use.

**Packages removed due to slopcheck `[SLOP]` verdict:** none (slopcheck not run this session — see note above).
**Packages flagged as suspicious `[SUS]`:** none.

## Architecture Patterns

### System Architecture Diagram

```text
┌──────────────────────────────────────────────────────────────────────┐
│  ONE-TIME / PERIODIC: Historical Odds Backfill (ODDS-01)              │
│                                                                          │
│  nba_features.csv (480 unique game dates, 3,638 games)                 │
│         │                                                               │
│         ▼                                                               │
│  for each unique game_date D not yet fully archived:                   │
│    ┌─────────────────────────────────────────────────────────────┐    │
│    │ 1. odds.py::hent_historisk_odds_snapshot(sport, D, "eu",      │    │
│    │    "h2h", morgen_tidspunkt(D))                                │    │
│    │      → check SQLite: already have bet_time rows for D? skip   │    │
│    │      → else: GET /v4/historical/sports/{sport}/odds            │    │
│    │        (sport-wide, pending CRITICAL FINDING resolution)       │    │
│    │      → parse data[] array (every game live/upcoming at D's     │    │
│    │        morning), match to nba_features.csv rows via teams.py   │    │
│    │      → INSERT OR IGNORE into odds_arkiv, tag snapshot_type=    │    │
│    │        'bet_time', log x-requests-last header                 │    │
│    └─────────────────────────────────────────────────────────────┘    │
│    ┌─────────────────────────────────────────────────────────────┐    │
│    │ 2. Repeat for snapshot_type='closing', timed near each        │    │
│    │    distinct commence_time cluster discovered in step 1         │    │
│    └─────────────────────────────────────────────────────────────┘    │
│         │                                                               │
│         ▼                                                               │
│  odds_arkiv.db (SQLite, permanent, append-only)                        │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  DAILY: Live Bot Run (ODDS-02, post-refactor)                          │
│                                                                          │
│  06_bot.py::main()                                                      │
│    → sjekk_resultater(bets, bankroll)          [unchanged]              │
│    → verdi_deteksjon.finn_value_bets()          ← was subprocess to     │
│      (imported from 04_value_detector.py)          04_value_detector.py │
│        → odds.py::hent_live_odds()              ← moved out of         │
│          (GET /v4/sports/{sport}/odds, unchanged live behavior)          │
│        → features.py / strategy.py / teams.py  [already shared]         │
│    → skadefilter.filtrer_bets()                 ← was subprocess to     │
│      (imported from 05_skadefilter.py)             05_skadefilter.py    │
│    → plasser_bets(), lagre_json(), generer_dashboard()  [unchanged]     │
└──────────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure

```
nba_betting/  (repo root — stays flat per D-08)
├── odds.py                    # NEW — unified live + historical Odds API client (D-07)
│   ├── hent_live_odds()           # replaces inline HTTP call in 04_value_detector.py
│   ├── hent_historisk_odds_snapshot()   # sport-wide (or per-event, pending resolution) fetch
│   ├── er_allerede_arkivert()     # pre-fetch existence check against SQLite (D-04)
│   └── arkiver_odds_rader()       # INSERT OR IGNORE into odds_arkiv.db
├── 04_value_detector.py       # MODIFIED — logic extracted into finn_value_bets(), imports odds.hent_live_odds()
├── 05_skadefilter.py          # MODIFIED — logic extracted into filtrer_bets_for_skader()
├── 06_bot.py                  # MODIFIED — imports 04/05 functions directly, no subprocess, no PYTHONPATH hack
├── odds_arkiv.db               # NEW, gitignored — SQLite permanent odds archive
├── (optional) 07_hent_historisk_odds.py   # NEW — thin CLI entry point for the backfill (planner's discretion)
└── tests/
    ├── test_odds.py            # NEW — unit tests for odds.py's pure/parsing functions
    └── test_arkiv.py           # NEW (or folded into test_odds.py) — idempotency/resumability tests
```

### Pattern 1: Extraction into importable function + `__main__` guard (precedent already in this repo)

**What:** Wrap a script's top-level logic in a function with a clear return contract, keep the `if __name__ == "__main__":` block for standalone use, and have the caller (`06_bot.py`) import and call the function directly.

**When to use:** Exactly what D-05 asks for `04_value_detector.py` and `05_skadefilter.py`. Phase 2 already established this exact shape for `features.py`/`strategy.py`/`teams.py` — those modules have **zero** top-level side effects except `teams.py`'s intentionally-safe, no-network `LAG_OPPSLAG = bygg_lag_oppslag()` (documented in its own docstring as safe because it reads a packaged static list, not the network). `04_value_detector.py`/`05_skadefilter.py` currently do the opposite — the entire file body executes top-to-bottom, including network calls, at import time. This is the concrete thing D-05's extraction must fix: wrapping the network-calling logic in a function so `import 04_value_detector` (well, its post-rename importable form) doesn't itself trigger HTTP calls.

**Example (this repo's own precedent, `teams.py`):**
```python
# Source: teams.py:23-40 (this repo, Phase 2)
def bygg_lag_oppslag():
    """... ingen nettverkskall (se docstring over)."""
    alle_lag = nba_teams.get_teams()
    oppslag = {}
    for lag in alle_lag:
        oppslag[lag["full_name"].lower()] = lag
        ...
    return oppslag

# Bygges én gang ved import — ingen nettverkskall (se docstring over).
LAG_OPPSLAG = bygg_lag_oppslag()
```
The pattern to replicate for `04_value_detector.py`: everything from "hent dagens odds" through "bygg value_bets-listen" becomes a function like `finn_value_bets(modell, feature_kolonner, api_nokkel)` returning the `value_df`/list, called both by the file's own `if __name__ == "__main__":` block (which then does the existing `print`/CSV-write side effects) and by `06_bot.py` directly.

### Pattern 2: SQLite idempotent "insert if not exists" for a resumable, interruptible fetch

**What:** A composite `UNIQUE` constraint plus `INSERT OR IGNORE` guarantees a re-run never creates duplicate archive rows, but that alone does **not** save API credits on a re-run — the credit-saving mechanism (D-04's actual requirement) is a `SELECT` existence check performed **before** the network call, not just before the insert.

**When to use:** Every iteration of the historical-fetch loop, for every `(event/date, snapshot_type)` unit the loop is about to spend a credit on.

**Example:**
```python
# odds.py — sketch, not final API
import sqlite3

SKJEMA = """
CREATE TABLE IF NOT EXISTS odds_arkiv (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    sport              TEXT NOT NULL,
    event_id           TEXT NOT NULL,
    kamp_dato          TEXT NOT NULL,   -- game date, joins to nba_features.csv GAME_DATE_HJEMME
    hjemmelag          TEXT NOT NULL,
    bortelag            TEXT NOT NULL,
    commence_time       TEXT NOT NULL,
    snapshot_type       TEXT NOT NULL CHECK (snapshot_type IN ('bet_time', 'closing')),
    snapshot_timestamp  TEXT NOT NULL,  -- the API's actual returned "timestamp", not the requested date
    bookmaker           TEXT NOT NULL,
    marked               TEXT NOT NULL,
    utfall_navn          TEXT NOT NULL, -- outcome name (team name)
    odds                 REAL NOT NULL,
    hentet_tidspunkt      TEXT NOT NULL, -- when this row was archived, audit trail
    UNIQUE(event_id, snapshot_type, bookmaker, marked, utfall_navn)
);
CREATE INDEX IF NOT EXISTS idx_odds_arkiv_dato_type
    ON odds_arkiv(kamp_dato, snapshot_type);
"""

def er_allerede_arkivert(con, kamp_dato, snapshot_type):
    """Sjekk FØR nettverkskall — dette er selve krediten-sparende sjekken (D-04)."""
    rad = con.execute(
        "SELECT 1 FROM odds_arkiv WHERE kamp_dato = ? AND snapshot_type = ? LIMIT 1",
        (kamp_dato, snapshot_type),
    ).fetchone()
    return rad is not None

def arkiver_snapshot(con, rader):
    """Batch-insert; commit umiddelbart slik at et avbrutt løp (Ctrl+C, strømbrudd,
    ny økt neste dag) beholder alt som allerede er hentet og betalt for."""
    con.executemany(
        """INSERT OR IGNORE INTO odds_arkiv
           (sport, event_id, kamp_dato, hjemmelag, bortelag, commence_time,
            snapshot_type, snapshot_timestamp, bookmaker, marked, utfall_navn,
            odds, hentet_tidspunkt)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rader,
    )
    con.commit()  # commit per snapshot, not once at the end — this IS the resumability
```

**Trade-offs:** Committing after every snapshot (rather than batching all commits at the end) is slightly slower but is what actually makes the fetch safely interruptible — a `KeyboardInterrupt` or crash mid-run loses at most the one in-flight snapshot's credit, never previously-archived data. Python 3.12+'s `sqlite3.Connection` legacy transaction behavior (implicit `BEGIN` before DML, explicit `commit()` required) is what this repo's Python 3.14.3 uses by default (no `autocommit=True` set anywhere) — this pattern works correctly under that default without any special configuration `[CITED: docs.python.org/3/library/sqlite3.html]`.

### Anti-Patterns to Avoid

- **Checking "have I archived this?" only via `INSERT OR IGNORE`'s silent no-op:** this still burns the credit for the network call that produced the row before discovering it was a duplicate. The `SELECT`-before-fetch check in Pattern 2 is what actually satisfies D-04 ("before spending any credit, the fetch must check...").
- **Committing only once at the very end of a multi-hundred-call loop:** defeats the entire point of D-04's resumability requirement — an interruption at call #400 of 480 would lose all 400 already-paid-for archived snapshots.
- **Treating a missing snapshot as "substitute the nearest one you have":** `.planning/research/ARCHITECTURE.md`'s Pitfall #6 applies directly here — if The Odds API's historical endpoint has no data at the requested morning-of-game-day timestamp for some early-2022-23-season game (bookmaker coverage may not extend that far back for every region — see Open Questions), skip that game/snapshot honestly rather than silently reusing a different timestamp's odds.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry-with-backoff on transient 429/5xx during the long backfill loop | A manual `for attempt in range(3): try/except/time.sleep(2**attempt)` loop | `tenacity`'s `@retry` decorator | The manual version is ~15 lines that already exist as a battle-tested, well-known one-line decorator; hand-rolling it for a real-money-relevant, multi-hour-across-sessions fetch script risks subtly wrong backoff/jitter behavior that wastes credits on a mis-timed retry storm |
| SQLite "already fetched?" existence check + resumability | A separate JSON/CSV "progress log" file tracking which dates have been processed | SQLite `SELECT` against the archive table itself (Pattern 2) | A separate progress file can drift from the actual archive contents (e.g. if a row insert failed after the progress file was updated); querying the archive table directly for the ground truth ("do rows for this date+snapshot_type actually exist") can never drift from itself |
| Team name resolution between Odds API team-name strings and `nba_features.csv`/`nba_api` team IDs, for matching sport-wide snapshot response rows to specific games | A new lookup dict inside `odds.py`, duplicating the pattern this project has already fixed twice | `teams.py::finn_lag_id()` (already shared, already tested per `tests/test_teams.py`) | This is precisely the drift risk `teams.py` was built to close in Phase 2 — `odds.py` must import it, not reinvent it |

**Key insight:** Every "don't hand-roll" item above traces back to the same root cause this project has already been bitten by twice (duplicated feature logic, duplicated team lookup) — a new module written under real-money time pressure is exactly where a third instance of that drift would happen if `odds.py` doesn't deliberately import `teams.py` and lean on well-known libraries for the parts that are genuinely commodity problems (retry/backoff).

## Common Pitfalls

### Pitfall 1: Cost-model premise mismatch (see CRITICAL FINDING)
**What goes wrong:** Building the fetch script against D-03's per-event-only requirement burns ~72,760 credits for the full `nba_features.csv` game list — 3.6x the paid budget — likely failing partway through with an exhausted-quota error, having already spent real money on an incomplete, unusable partial archive.
**Why it happens:** The milestone research's cost-formula finding, while HIGH-confidence-labeled at the time, inverted which endpoint's formula included the "10x" multiplier.
**How to avoid:** Resolve the CRITICAL FINDING with the user before writing the fetch script. If the sport-wide endpoint is approved as the primary mechanism, D-03 needs to be explicitly amended (not silently reinterpreted) since it's currently phrased as a hard requirement.
**Warning signs:** Any credit estimate for this phase that comes out near or under the naive "1 credit/event" assumption should be treated as suspect and re-derived from the verified `10 × markets × regions` formula.

### Pitfall 2: "Morning of game day" timezone ambiguity
**What goes wrong:** `nba_features.csv`'s `GAME_DATE_HJEMME` is a calendar date with no explicit timezone documented in this codebase, while The Odds API's `commence_time` and `date` query parameter are UTC ISO8601. A naive `f"{game_date}T08:00:00Z"` conversion can land on the wrong side of a game's actual local morning if `GAME_DATE_HJEMME` reflects US Eastern/home-arena local date and the game's own `commence_time` crosses the UTC day boundary (e.g., a 7pm ET tip-off is already the next UTC calendar day).
**Why it happens:** NBA schedule dates conventionally follow the home team's local calendar day, not UTC; this project's existing code (`04_value_detector.py:196`, `06_bot.py`) already works entirely in date strings without timezone-aware datetime objects, so there's no existing convention to inherit.
**How to avoid:** Pick one explicit timezone convention (e.g., always compute "morning of game day" as `{GAME_DATE_HJEMME} 13:00 UTC`, which is 8-9am US Eastern year-round accounting for DST) and document it once in `odds.py`, rather than re-deriving it ad hoc per call site.
**Warning signs:** A bet-time snapshot whose returned `commence_time` is more than ~18 hours from the requested date is a sign the timezone math picked the wrong calendar day.

### Pitfall 3: Historical odds returning stale/missing markets for early-in-range dates
**What goes wrong:** The official docs state "Bookmakers, sports and markets will only be available in the historical odds API from the time that they were added to the current odds API" — a specific EU bookmaker used by the live bot today may not have historical coverage back to `nba_features.csv`'s earliest date (2022-10-24), silently producing thinner/different bookmaker coverage for early-season archived games than for later ones.
**Why it happens:** The Odds API's historical archive only contains what its live scraping infrastructure was actually capturing at that point in time; bookmaker/region coverage has grown over the product's life.
**How to avoid:** Run a small spot-check (2-3 dates near the start of the range, 2-3 near the end) before committing to the full 480-date backfill, comparing bookmaker count/coverage; if early-range coverage under the `eu` region is meaningfully thinner, consider falling back to `us` region for those dates or documenting the coverage gap explicitly rather than treating all 480 dates as equally reliable.
**Warning signs:** A sport-wide snapshot response for an early-2022-23-season date returning zero or one bookmaker per game, versus several for late-2024-25 dates.

### Pitfall 4: Closing-line snapshot capturing post-tipoff or withdrawn markets
**What goes wrong:** If a "closing line" snapshot call is timed even slightly after a game's actual `commence_time` (e.g., because multiple games share a date but tip off hours apart, and one blanket end-of-day timestamp is used for all of them), the historical odds endpoint may return in-play odds, a withdrawn/suspended market, or simply the pregame line frozen at whatever the last update was before kickoff — not a clean "closing line" in the backtest sense.
**Why it happens:** `.planning/research/ARCHITECTURE.md`'s Anti-Pattern 3 flags this generally; this phase's specific manifestation is that NBA slates commonly span a 3+ hour tip-off window (e.g., 7pm and 10pm ET games same date), so a single per-date closing snapshot cannot be simultaneously "just before tipoff" for both games.
**How to avoid:** Cluster games by distinct `commence_time` per date (discoverable cheaply via the 1-credit `GET historical events` endpoint before spending any odds credits) and issue one closing-line odds call per cluster, timed 10-15 minutes before that cluster's earliest commence_time, snapped to the API's 5-minute snapshot grid.
**Warning signs:** A "closing" row whose `snapshot_timestamp` (the API's actual returned timestamp, which may differ from the requested `date`) is later than that game's `commence_time`.

### Pitfall 5: `06_bot.py`'s error-visibility contract silently changes shape after the subprocess removal
**What goes wrong:** Today, `kjør_pipeline()` treats `04_value_detector.py`/`05_skadefilter.py` failures as "non-zero exit code + captured stderr text," and `06_bot.py` prints the last 500 chars of stderr and returns `None` (`06_bot.py:201-202, 208-209`). After D-05/D-06's refactor to direct function calls, a failure inside `finn_value_bets()` raises a Python exception in-process instead — if nothing catches it, `06_bot.py` crashes instead of gracefully degrading to "no value bets today" the way the subprocess boundary currently allows.
**Why it happens:** The subprocess boundary was accidentally providing a de facto try/except-Exception-and-continue safety net (any crash inside `04`/`05` just becomes a captured stderr string); removing the boundary removes that implicit safety net unless it's explicitly replaced.
**How to avoid:** Wrap the new direct calls in `06_bot.py` with the same broad `try/except Exception` + print + `return None`/continue pattern already used elsewhere in this codebase (e.g. `06_bot.py`'s `hent_kampresultat`'s `except Exception: return None`), so the observable behavior (bot degrades gracefully on a bad day rather than crashing) is preserved, not just the happy path.
**Warning signs:** A live bot run that used to print "Feil i 04_value_detector.py: ..." and continue now instead exits with an unhandled traceback.

### Pitfall 6: PYTHONPATH removal (D-06) validated only by "it still imports," not by a clean environment
**What goes wrong:** `06_bot.py:196-198`'s hardcoded `python3.10` site-packages path exists because of the documented three-Python-version site-packages inconsistency in the committed `venv/` (per CLAUDE.md's own "Inconsistency" note). Simply deleting that `PYTHONPATH` construction and confirming `06_bot.py` still runs *in the current shell* doesn't prove the hack was actually load-bearing for something the current shell's active `python3.14` venv happens to already have.
**Why it happens:** Direct in-process imports (this phase's whole point) mean `06_bot.py` now runs under whatever interpreter invoked it — if that's reliably the 3.14 venv (which owns `nba_api`, `requests`, etc. per `venv/lib/python3.14/site-packages`), the hack genuinely becomes unnecessary, but this should be verified by actually running `06_bot.py` end-to-end post-refactor, not just by the code compiling.
**How to avoid:** After D-06's removal, run `06_bot.py` (or at minimum import all its new direct-call targets) using the exact invocation the daily-run instructions describe, and confirm no `ModuleNotFoundError` — this closes the loop D-06 opens rather than assuming it.
**Warning signs:** `ModuleNotFoundError: No module named 'nba_api'` (or similar) after the PYTHONPATH line is removed, when previously it worked — would indicate the hack actually was covering a real gap for some invocation path.

## Code Examples

### The Odds API — sport-wide historical odds request (pending CRITICAL FINDING resolution)
```python
# Source: https://the-odds-api.com/liveapi/guides/v4/ (GET historical odds section, verified via raw HTML)
import requests

url = f"https://api.the-odds-api.com/v4/historical/sports/basketball_nba/odds"
params = {
    "apiKey": api_nokkel,
    "regions": "eu",          # match live bot's existing region choice for consistency
    "markets": "h2h",
    "oddsFormat": "decimal",
    "dateFormat": "iso",
    "date": "2023-01-15T13:00:00Z",   # ISO8601 — API returns closest snapshot <= this
}
respons = requests.get(url, params=params)
print(f"Kreditt brukt på dette kallet: {respons.headers.get('x-requests-last', 'ukjent')}")
print(f"Gjenstående: {respons.headers.get('x-requests-remaining', 'ukjent')}")
data = respons.json()
# data["timestamp"] = the actual snapshot timestamp returned (may differ from requested date)
# data["data"] = list of ALL games with odds active at that timestamp
```

### The Odds API — historical events discovery (1 credit, for precise closing-line timing)
```python
# Source: https://the-odds-api.com/liveapi/guides/v4/ (GET historical events section)
url = "https://api.the-odds-api.com/v4/historical/sports/basketball_nba/events"
params = {
    "apiKey": api_nokkel,
    "date": "2023-01-15T13:00:00Z",
    "commenceTimeFrom": "2023-01-15T00:00:00Z",
    "commenceTimeTo": "2023-01-16T00:00:00Z",
}
respons = requests.get(url, params=params)
# respons.json()["data"] = list of {id, home_team, away_team, commence_time} — NO odds, NO cost
# beyond the flat 1 credit (0 if empty) — use this to plan closing-line snapshot timing
# before spending any 10-credit odds call.
```

### The Odds API — per-event historical odds request (fallback / non-featured-market use only)
```python
# Source: https://the-odds-api.com/liveapi/guides/v4/ (GET historical event odds section)
url = f"https://api.the-odds-api.com/v4/historical/sports/basketball_nba/events/{event_id}/odds"
params = {
    "apiKey": api_nokkel,
    "regions": "eu",
    "markets": "h2h",
    "date": "2023-01-15T23:50:00Z",
}
# cost = 10 x markets x regions, PER CALL — i.e. per single event, not per snapshot.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `06_bot.py` invokes `04_value_detector.py`/`05_skadefilter.py` via `subprocess.run` with a hand-rolled `PYTHONPATH` | Direct in-process function imports (this phase) | This phase (ODDS-02) | Removes the process-boundary coupling anti-pattern flagged in `.planning/research/ARCHITECTURE.md`'s Integration Points table; removes the documented three-Python-version venv inconsistency's most visible symptom |
| `04_value_detector.py`'s inline live-odds HTTP call | `odds.py::hent_live_odds()`, imported by `04_value_detector.py` | This phase (D-07) | Establishes the single point where live and historical odds share a normalized output schema, matching `.planning/research/ARCHITECTURE.md`'s Pattern 3 (ports-and-adapters, minimal form) |

**Deprecated/outdated:** The milestone `STACK.md`'s per-event-vs-sport-wide cost comparison (2026-08-19) is superseded by this phase's direct verification against the raw official docs HTML (2026-08-23) — see CRITICAL FINDING. `STACK.md` itself should be corrected once the user resolves the open question, to prevent the same stale premise resurfacing in Phase 5's planning.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `tenacity` and `tqdm` are legitimate, safe-to-install packages (package *names* sourced from milestone STACK.md/training knowledge, not Context7/official docs; existence+version confirmed via PyPI registry only, slopcheck not run) | Standard Stack, Package Legitimacy Audit | Low — both are extremely well-known, long-lived packages; risk is near-zero but the provenance rule requires the tag regardless |
| A2 | 3 distinct commence-time clusters/date is a reasonable planning estimate for closing-line snapshot cost | CRITICAL FINDING (credit budget), Pitfall 4 | Medium — if real NBA slates cluster into more than 3 distinct tip-off times on a meaningful fraction of the 480 dates, closing-line costs could exceed the conservative 14,400-credit estimate; should be measured directly (e.g. from the discovery pass's actual `commence_time` values) before committing the full backfill, not assumed |
| A3 | "Morning of game day" = 13:00 UTC (~8-9am US Eastern) is an acceptable operationalization of D-01's "morning of game day" for the historical fetch | Pitfall 2 | Medium — if the live bot's actual daily cron/manual run time differs meaningfully from this assumption once it's scheduled, the archived "bet-time" snapshots won't match what the live bot actually sees, undermining the entire premise of D-01 (backtest must reflect a timing the live bot could realistically achieve) |
| A4 | `eu` region (matching `04_value_detector.py`'s current live-fetch region) is the right region for the historical archive too, for backtest/live consistency | Code Examples, Pitfall 3 | Medium — if `eu` bookmaker historical coverage is meaningfully thinner than `us` for part of the 2022-2025 range, archive quality could vary by date range in a way that quietly biases early-vs-late backtest results |

**If this table is empty:** N/A — see rows above.

## Open Questions (RESOLVED)

1. **RESOLVED: Does the user want to switch D-03 from per-event to sport-wide, given the verified cost reversal?** — Yes; user confirmed the switch after seeing the verified numbers. D-03 amended in 04-CONTEXT.md (2026-08-23); every fetch-touching plan (04-01, 04-03, 04-04, 04-05, 04-07, 04-09) uses the sport-wide endpoint exclusively, with 04-04 asserting the per-event path is absent via grep.
   - What we know: Sport-wide fits the paid budget (~9,600-19,680 credits); per-event does not (~72,760 credits for the full game list).
   - What's unclear: Whether there's a non-cost reason (not captured in CONTEXT.md) for preferring per-event that would survive knowing the real cost.
   - Recommendation: Block on this before implementation — see CRITICAL FINDING.

2. **RESOLVED-BY-DESIGN: How many distinct commence-time clusters exist per game date, in the real `nba_features.csv` data?** — Deliberately not pre-computed; plan 04-07's smoke test runs the 1-credit discovery pass against real dates and measures this empirically before the full backfill is sized, per the recommendation below.
   - What we know: 480 unique dates, avg 7.6 games/date; NBA slates typically run 2-4 distinct tip-off windows per day in the current era.
   - What's unclear: The actual distribution for this specific 2022-10-24→2025-04-13 range hasn't been computed (would require either the 1-credit discovery endpoint or an nba_api boxscore-time cross-reference, since `nba_features.csv` doesn't carry the original game start time).
   - Recommendation: Run the discovery pass (`GET historical events`, 1 credit/date) first and let its output drive the exact number of closing-line odds calls needed, rather than guessing upfront.

3. **RESOLVED-BY-DESIGN: Is `eu` region's historical coverage complete back to 2022-10-24, or should the archive fall back to `us` for older dates?** — Deliberately not pre-verified; plan 04-07's smoke test spot-checks early-range dates before the full backfill, per the recommendation below.
   - What we know: Official docs state bookmaker/region historical coverage only exists "from the time they were added to the current odds API" — no specific date given for `eu`.
   - What's unclear: Whether this creates a meaningful coverage gap for this project's specific 2.5-season range.
   - Recommendation: Spot-check 2-3 early-range dates before committing to the full backfill (see Pitfall 3).

4. **Exact SQLite filename/table names** — CONTEXT.md leaves this to planner discretion; `odds_arkiv.db` / `odds_arkiv` table (used throughout this document) is a suggestion following the project's Norwegian-domain-noun convention, not a locked choice.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python `sqlite3` (stdlib) | Odds archive (ODDS-01) | ✓ | 3.51.2 (bundled) `[VERIFIED]` | — |
| `requests` | Live + historical odds fetch | ✓ | already in requirements.txt (`>=2.31.0`) | — |
| `python-dotenv` | `ODDS_API_NOKKEL` loading | ✓ | 1.2.3 installed `[VERIFIED: pip show]` | — |
| `tenacity` | Retry/backoff around historical fetch loop | ✗ (not yet installed) `[VERIFIED: pip show → "Package(s) not found"]` | 9.1.4 available on PyPI | Manual `try/except` + `time.sleep()` loop (existing pattern elsewhere in repo, e.g. `01_hent_data.py`'s rate-limit sleeps) — acceptable fallback if the checkpoint-gated install is declined |
| `tqdm` | Progress bar for backfill | ✗ (not yet installed) | 4.70.0 available on PyPI | Plain `print(f"{i}/{total}")` progress line — trivial fallback, not a blocker |
| The Odds API paid tier (20K credits/month) | ODDS-01 entirely | ✓ (user already paid) | — | None — this is the phase's hard external dependency, already satisfied per CONTEXT.md's domain note |
| Network access to `api.the-odds-api.com` | ODDS-01, ODDS-02's live-odds path | Not tested this session (would consume credits/rate limit for no research value) | — | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `tenacity`, `tqdm` — both have low-cost fallbacks; recommend installing them (checkpoint-gated per Package Legitimacy Audit) rather than hand-rolling, per "Don't Hand-Roll."

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 `[VERIFIED: venv/bin/python -m pytest --version]` |
| Config file | `pytest.ini` (`pythonpath = .`, `testpaths = tests`) |
| Quick run command | `venv/bin/python -m pytest tests/test_odds.py -x -q` |
| Full suite command | `venv/bin/python -m pytest -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ODDS-01 | Pre-fetch existence check prevents a second network call / credit spend for an already-archived `(kamp_dato, snapshot_type)` | unit (mock HTTP, real in-memory SQLite) | `pytest tests/test_odds.py::test_er_allerede_arkivert_hindrer_dobbelt_kall -x` | ❌ Wave 0 |
| ODDS-01 | `odds.py`'s response parser correctly maps sport-wide snapshot `data[]` rows to `nba_features.csv` games via `teams.finn_lag_id()` | unit (fixture JSON response) | `pytest tests/test_odds.py::test_snapshot_matcher_bruker_teams_py -x` | ❌ Wave 0 |
| ODDS-01 | SQLite schema enforces the composite `UNIQUE` constraint so a re-run never double-inserts | unit (real in-memory/tempfile SQLite, insert twice) | `pytest tests/test_odds.py::test_dobbel_insert_er_idempotent -x` | ❌ Wave 0 |
| ODDS-02 | `04_value_detector.py`'s extracted function returns the same value/EV output shape it printed before extraction, for a fixed fixture input | unit/regression | `pytest tests/test_verdi_deteksjon.py::test_finn_value_bets_uendret_output -x` | ❌ Wave 0 |
| ODDS-02 | `06_bot.py`'s direct-call path degrades gracefully (returns `None`/continues) on an injected exception, mirroring the old subprocess-failure behavior (Pitfall 5) | unit (monkeypatched function raising) | `pytest tests/test_bot.py::test_pipeline_feil_degraderer_grasiost -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `venv/bin/python -m pytest tests/test_odds.py tests/test_verdi_deteksjon.py tests/test_bot.py -x -q`
- **Per wave merge:** `venv/bin/python -m pytest -q` (full suite, including existing `tests/test_features.py`, `tests/test_strategy.py`, `tests/test_teams.py`, `tests/test_parity.py`, `tests/test_calibrering_split.py`)
- **Phase gate:** Full suite green before `/gsd:verify-work`, plus a manual smoke-test run of the historical fetch script against a tiny date range (1-2 dates) to confirm real API behavior before the full 480-date backfill is triggered — this is not automatable in pytest since it spends real credits.

### Wave 0 Gaps
- [ ] `tests/test_odds.py` — covers the pre-fetch existence check, snapshot-to-game matching, and SQLite idempotency (ODDS-01)
- [ ] `tests/test_verdi_deteksjon.py` (or similarly named after the planner picks `04_value_detector.py`'s extracted function name) — regression test proving extraction didn't change output (ODDS-02)
- [ ] `tests/test_bot.py` — covers `06_bot.py`'s graceful-degradation behavior post-refactor (ODDS-02, Pitfall 5)
- [ ] No new fixture data needed beyond what `tests/conftest.py` already provides for feature/parity tests; odds-specific fixtures (sample sport-wide JSON response) should be added as static fixture files or inline dicts, not live API calls

## Project Constraints (from CLAUDE.md)

- **Norwegian identifiers/comments throughout** — `odds.py`'s function/variable names, docstrings, and print output must follow the existing convention (`hent_live_odds`, `hent_historisk_odds_snapshot`, `er_allerede_arkivert`, etc.), matching `features.py`/`strategy.py`/`teams.py`'s established style.
- **`snake_case` throughout, no type hints, no linter/formatter config** — new code in `odds.py` and the extracted `04`/`05` functions should match this; do not introduce type hints or a linter as part of this phase.
- **Moneyline only for v1** — the historical archive should fetch `markets=h2h` only; do not add `spreads`/`totals` even though they're available, per the project's explicit v1 scope boundary.
- **No real-money betting until backtest + paper-trading show positive ROI** — this phase does not place real bets; it only prepares data. No action in this phase should touch that gate.
- **`.env`/`python-dotenv` already the established secret pattern** (this is a correction to CLAUDE.md's own stale "No `.env` file usage in code" note, which predates Phase 1's HYG-01 fix — `04_value_detector.py` has used `python-dotenv` + `ODDS_API_NOKKEL` since Phase 1, and this phase's historical fetch should reuse that exact pattern, not reintroduce a hardcoded key or a different secret mechanism).
- **Existing error-handling convention: broad `try/except Exception` around external API calls, `sys.exit(1)` (not bare `exit()`) for fatal top-level failures** — `odds.py` and the extracted functions should follow this, especially given Pitfall 5's finding that the subprocess boundary was providing implicit exception-swallowing that must be explicitly replicated in the new direct-call path.
- **GSD workflow enforcement** — per this project's CLAUDE.md, file-changing work must go through a GSD command (`/gsd:plan-phase` → `/gsd:execute-phase`, or equivalent); this research output feeds that workflow rather than being applied directly.

## Sources

### Primary (HIGH confidence)
- `https://the-odds-api.com/liveapi/guides/v4/` — raw HTML fetched directly via `curl` and parsed with Python (not the AI-summarized WebFetch rendering, which was internally inconsistent across three separate fetch attempts) — verified verbatim "Usage Quota Costs" text for `GET historical odds`, `GET historical events`, and `GET historical event odds`; verified request/response schema for all three; verified `x-requests-remaining`/`x-requests-used`/`x-requests-last` response headers.
- `https://the-odds-api.com/guide/rate-limit.html` — verified "30 requests per second on paid usage plans."
- `nba_features.csv` (this repo) — verified 3,638 rows, 480 unique `GAME_DATE_HJEMME` values, 2022-10-24 → 2025-04-13, via direct `pandas` computation this session.
- `python3 -c "import sqlite3; print(sqlite3.sqlite_version)"` — verified 3.51.2 bundled with this machine's Python 3.14.3.
- `pip index versions tenacity` / `pip index versions tqdm` — verified 9.1.4 / 4.70.0 current on PyPI.
- This repo: `04_value_detector.py`, `05_skadefilter.py`, `06_bot.py`, `features.py`, `strategy.py`, `teams.py`, `config.py`, `tests/conftest.py`, `pytest.ini`, `requirements.txt` — read directly this session.

### Secondary (MEDIUM confidence)
- WebSearch cross-checks of the per-event vs. sport-wide cost distinction (multiple independent queries converged on "per-event costs 10×markets×regions per event," consistent with the raw-HTML primary source above, after two earlier WebFetch summarization passes gave inconsistent/wrong answers that were discarded).
- `.planning/research/ARCHITECTURE.md` (milestone research, 2026-08-19) — the shared-core/unified-adapter architecture pattern is still sound and used directly in this document's recommendations; only its cost-model input from `STACK.md` is superseded.

### Tertiary (LOW confidence)
- Exact NBA commence-time clustering per date (Open Question 2) — not verified against real data this session, flagged for planning-time or execution-time measurement via the 1-credit discovery endpoint before the closing-line backfill is sized.
- `eu` region's exact historical coverage start date (Open Question 3) — not verified; recommend spot-check before full backfill.

## Metadata

**Confidence breakdown:**
- Standard stack (SQLite, requests, tenacity/tqdm): HIGH — stdlib + already-installed + PyPI-registry-verified current versions
- Historical API cost model: HIGH (verified via raw official docs HTML, cross-checked against WebSearch) — but this HIGH confidence directly *contradicts* a locked user decision, which is why it's surfaced as a blocking finding rather than silently applied
- 06_bot.py refactor pattern (ODDS-02): HIGH — direct precedent already exists and works in this exact codebase (Phase 2)
- Exact credit budget for closing-line snapshots: MEDIUM — depends on real commence-time clustering not yet measured
- eu region historical coverage completeness: LOW — not verified, flagged as open question

**Research date:** 2026-08-23
**Valid until:** The Odds API's pricing/endpoint-cost model should be treated as valid for ~30 days but re-verified immediately before the fetch script actually runs, given this research already found the milestone research's version (4 days old) to be incorrect — pricing/endpoint pages on third-party APIs are not guaranteed stable and the cost of re-checking (one more WebFetch) is far lower than the cost of a wrong assumption at execution time.

---
*Phase: 4-Historical Odds Acquisition & Live Refactor*
*Research completed: 2026-08-23*
