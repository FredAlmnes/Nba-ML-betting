# Phase 4: Historical Odds Acquisition & Live Refactor - Context

**Gathered:** 2026-08-23
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase has two halves. (1) ODDS-01: fetch historical NBA odds via The Odds API's per-event historical endpoint and archive them permanently in SQLite, so Phase 5's backtest never re-spends credits on repeated iteration. (2) ODDS-02: refactor `06_bot.py` to import the shared core (odds fetch, value detection, injury filter) directly instead of shelling out to `04_value_detector.py`/`05_skadefilter.py` via `subprocess.run`. It does NOT build the backtest engine itself (Phase 5), does NOT change the value threshold / odds range / Kelly fraction (Phase 5, backtest-gated), and does NOT do the full `nba_betting/` package restructure (deferred — see Package Structure below).

The user has already paid for one month of The Odds API's 20K-credit tier specifically to fund this phase's historical fetch.

</domain>

<decisions>
## Implementation Decisions

### Odds snapshot timing
- **D-01:** The live bot runs once daily, **in the morning of game day** (locked in this discussion — `06_bot.py`'s docstring says "kjør daglig" but never pinned a time; this phase is the first place that offset becomes load-bearing). The historical fetch must pin the same offset: snapshot odds at the closest available reading to morning-of-game-day for each event, not the closing line. Per `.planning/research/ARCHITECTURE.md`'s Pitfall #3 ("Simulate realistic bet-placement timing for odds, not closing lines"): using closing-line odds as the bet price would inflate/deflate backtest ROI in a direction the live bot could never actually realize.

### Fetch scope (credit budget)
- **D-02 (AMENDED 2026-08-23 — see D-03 below):** Fetch **both** the morning-of bet-time snapshot AND the closing-line snapshot for every archived date, in this same paid month — not bet-time only. Doing it now avoids a second paid month later when Phase 5's CLV requirement (BT-06) needs closing-line data anyway. Re-derived math (per D-03's amendment): `nba_features.csv` (2022-10-24 → 2025-04-13) has **480 unique game dates** across 3,638 games. One sport-wide call per date captures every game that date in a single 10-credit call. Bet-time (480 × 10 = 4,800 credits) + closing-line (≈3 commence-time clusters/date average × 480 × 10 ≈ 14,400 credits, conservative upper bound) + an optional cheap discovery pass (480 × 1 = 480 credits) ≈ **~19,680 credits worst-case, likely 9,600–14,000 realistic** — fits inside the 20,000-credit budget with headroom for retries.
- **D-03 (AMENDED 2026-08-23 — supersedes the original locked decision):** Use the **sport-wide** historical odds endpoint (`/v4/historical/sports/{sport}/odds`), one call per unique game date, NOT the per-event endpoint. **Original rationale reversed by verified research:** both endpoints share the identical `10 × markets × regions` cost formula, but per-event charges it *per game queried* while sport-wide charges it *once per snapshot call* (returning every game live at that timestamp). For this project's 3,638 games, per-event would cost ~72,760 credits (3.6x over budget — would fail outright), while sport-wide costs ~10-20K credits (fits). The official Odds API docs explicitly recommend the sport-wide endpoint for featured markets ("When querying historical odds for featured markets, the historical odds endpoint is simpler to implement and more cost-effective") — h2h/moneyline (this project's entire v1 scope) is a featured market. Verified independently twice against the raw official docs (`the-odds-api.com/liveapi/guides/v4/`) before amending; user confirmed the switch after seeing the verified numbers. The per-event endpoint remains available as a future fallback only if a non-featured market (e.g. player props) is ever needed — out of v1 scope.
- **D-04:** SQLite archive is genuinely permanent/append-only — historical odds for a past timestamp never change, so there is no cache-expiry/TTL logic. Before spending any credit, the fetch must check "do I already have this event+snapshot-type archived?" and skip if so (this is what makes re-running the fetch after an interruption free, per the phase's own success criteria).

### 06_bot.py refactor shape (ODDS-02)
- **D-05:** `04_value_detector.py` and `05_skadefilter.py` each get their core logic extracted into importable functions, while remaining standalone-runnable via an `if __name__ == "__main__":` guard that calls those same functions — mirroring the exact pattern already established for `features.py`/`strategy.py`/`teams.py` in Phase 2. `06_bot.py` imports and calls these functions directly, replacing the two `subprocess.run([sys.executable, "0X_....py"], ...)` calls (`06_bot.py:195-210`).
- **D-06:** This refactor removes the hardcoded `venv/lib/python3.10/site-packages` `PYTHONPATH` construction (`06_bot.py:196-198`) entirely — it only existed to make the subprocess's interpreter see the right packages, and direct in-process imports have no such problem. This is a natural side-effect cleanup of a documented tech-debt item (see CLAUDE.md's "Inconsistency" note on the venv), not new scope.
- **D-07:** The odds-fetching logic (both live "today's odds" and the new historical archive fetch) lives in **one new module, `odds.py`**, at repo root — not split across two files. Per `.planning/research/ARCHITECTURE.md`'s "unified live + historical Odds API client, same output schema" pattern: both the live path and Phase 5's backtest must receive odds rows in the identical shape, and a single module is the simplest way to guarantee that without a second duplication risk (the project has already drifted on duplicated logic twice — feature engineering and team-name resolution, both fixed in Phase 2). `04_value_detector.py` should import its live-odds fetch from `odds.py` rather than keep its own inline HTTP call.

### Package structure
- **D-08:** Stay with **flat modules at repo root** this phase (`odds.py` joins `features.py`/`strategy.py`/`teams.py`/`config.py`) — do NOT introduce the full `nba_betting/` package (`data/`, `backtest/`, `live/`) yet. Phase 2's D-01 explicitly deferred that restructure to "Phase 4/5 when backtest/live separation actually requires it" — but Phase 4 only touches the live path (odds archive + `06_bot.py` refactor); the backtest/live *separation* only becomes real in Phase 5 when `backtest/` needs to exist as a directory alongside `live/`. Restructuring now would be premature — Phase 5's planner should make the final call on package layout once the backtest engine's actual shape is known.

### Claude's Discretion
- Exact SQLite filename/location (e.g. `odds_arkiv.db` at repo root, matching the Norwegian-domain-noun naming convention used elsewhere) and exact table/column names beyond the composite key `(sport, event_id, market, snapshot_timestamp)` already specified in `.planning/research/STACK.md`.
- Whether the historical bulk-fetch runs as a new numbered pipeline script (e.g. `07_hent_historisk_odds.py`, matching the existing `0N_verb_ting.py` convention) or a function invoked from elsewhere — planner's call, but it must be resumable/idempotent per D-04.
- Exact function names extracted from `04_value_detector.py`/`05_skadefilter.py` (Norwegian, snake_case, per established convention).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` §"Historical Odds & Live Refactor" — ODDS-01, ODDS-02 (locked acceptance criteria)

### Roadmap
- `.planning/ROADMAP.md` §"Phase 4: Historical Odds Acquisition & Live Refactor" — goal, success criteria, and the phase-entry budget decision note (now resolved — see D-01 through D-04 above)

### Milestone-level research (already answers most "how" questions for this phase)
- `.planning/research/STACK.md` — SQLite archive rationale and confirmed pricing tiers (verified 2026-08-19) are still valid. **Its per-event-vs-sport-wide cost claim is superseded — see `04-RESEARCH.md`'s "CRITICAL FINDING" and D-03's amendment above; STACK.md itself is stale on this one point and should not be trusted for endpoint choice.**
- `.planning/research/ARCHITECTURE.md` §"Common Pitfalls" #3 and #6 — snapshot-timing pitfall (this phase's D-01) and "treat missing historical odds honestly" (skip, don't substitute a nearby snapshot) — both directly govern this phase's fetch logic
- `.planning/research/ARCHITECTURE.md` — the unified live+historical odds client pattern behind D-07 (`data/odds.py` in the research doc's sketched full-package layout — this phase keeps it flat as `odds.py` per D-08)
- `.planning/research/FEATURES.md` — confirms CLV tracking (BT-06, Phase 5) needs both bet-time and closing-line historical odds, informing D-02

### Prior phase decisions this phase depends on
- `.planning/phases/02-shared-core-extraction-test-foundation/02-CONTEXT.md` D-01 — the original deferral of package restructure to "Phase 4/5", resolved by D-08 above (still deferred, now explicitly to Phase 5)
- `.planning/phases/02-shared-core-extraction-test-foundation/02-CONTEXT.md` D-08/D-09 pattern — the pre-flight-checkpoint precedent for handling any pre-existing uncommitted WIP in files this phase touches (`06_bot.py`, `04_value_detector.py`, `05_skadefilter.py` should all be checked for uncommitted changes before this phase's plans start editing them)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `features.py`, `strategy.py`, `teams.py`, `config.py` (Phase 2) — the exact extraction pattern (pure functions, importable, Norwegian snake_case, `if __name__ == "__main__":` guard where standalone use matters) to replicate for `odds.py` and for extracting `04_value_detector.py`/`05_skadefilter.py`'s logic.
- `modell_utils.KalibrertModell` import pattern — the established "import from a plain-named root module" convention `odds.py` should follow too.

### Established Patterns
- `06_bot.py:195-210` — the exact subprocess block ODDS-02 removes (`subprocess.run([sys.executable, "04_value_detector.py"], ...)` then `05_skadefilter.py`), including the hardcoded `python3.10` `PYTHONPATH` hack this refactor incidentally cleans up.
- `sys.exit(1)` with explanatory comment for fatal errors (`04_value_detector.py:63-67`) — the existing pattern for HTTP-status-code failures against The Odds API; the new historical-fetch logic in `odds.py` should follow the same fail-loud convention, especially for credit-exhaustion responses.
- Existing `.env`/`python-dotenv` pattern (Phase 1, `04_value_detector.py:32-40`) — `ODDS_API_NOKKEL` is already loaded this way; the new historical fetch reuses the same env var, no new secret-handling needed.

### Integration Points
- `nba_features.csv` (3,638 rows, `GAME_DATE_HJEMME` 2022-10-24 → 2025-04-13) — the exact date range and game list the historical odds archive needs to cover, so Phase 5 can join odds to features by date+matchup.
- `04_value_detector.py`'s current inline live-odds HTTP call (`04_value_detector.py:61-67` area) is the thing `odds.py`'s live-fetch function replaces/absorbs (D-07).

</code_context>

<specifics>
## Specific Ideas

No UI/visual requirements — this is a backend data-acquisition and refactor phase. The user's specific input was procedural: they'd already paid for the Odds API upgrade before this discussion, confirming the budget decision from Phase 3's blocker is resolved, and picked "morning of game day" as the concrete run-time assumption needed to make the historical snapshot timing decision real rather than hypothetical.

</specifics>

<deferred>
## Deferred Ideas

- Full `nba_betting/` package restructure (`data/`, `backtest/`, `live/`) — deferred to Phase 5 (D-08), where the backtest/live separation actually becomes real.
- Any change to `MIN_VALUE_TERSKEL`, `MAX_ODDS`, or Kelly fraction values — explicitly Phase 5, backtest-gated (carried forward from Phase 1 D-05/D-07 and Phase 2 D-07, still binding).
- Grid search / threshold tuning (BTV2-01) and HTML backtest report (BTV2-02) — already deferred to v2 per `.planning/STATE.md`'s Deferred Items table, untouched by this phase.

None — discussion stayed within phase scope otherwise.

</deferred>

---

*Phase: 4-Historical Odds Acquisition & Live Refactor*
*Context gathered: 2026-08-23*
