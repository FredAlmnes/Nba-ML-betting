---
phase: 04-historical-odds-acquisition-live-refactor
plan: 04
subsystem: api
tags: [odds-api, tenacity, requests, retry-backoff, http-client, tdd]

# Dependency graph
requires:
  - phase: 04-historical-odds-acquisition-live-refactor (04-01)
    provides: odds.py's SQLite archive layer (apne_arkiv/er_allerede_arkivert/arkiver_odds_rader/logg_kreditt)
  - phase: 04-historical-odds-acquisition-live-refactor (04-03)
    provides: DST-aware timestamp logic (morgen_tidspunkt/lukketidspunkt/grupper_commence_tider) and parse_snapshot_til_rader, which the historical fetch functions in this plan feed
provides:
  - "hent_api_nokkel() — .env-backed ODDS_API_NOKKEL read, fail-loud on missing key, no import-time side effect"
  - "_utfor_kall() — single retrying, fail-loud, key-safe HTTP choke point for every call this module makes"
  - "hent_live_odds() — live moneyline odds fetch, moved out of 04_value_detector.py's inline HTTP (D-07), not yet wired back in"
  - "hent_historisk_odds_snapshot() / hent_historiske_events() — the two historical endpoints the backfill driver (04-05+) will call"
affects: [04-05, 04-06, 04-07, 04-09]

# Tech tracking
tech-stack:
  added: ["tenacity>=9.1.4 (retry/backoff decorator, approved via blocking package-legitimacy checkpoint)"]
  patterns:
    - "Single HTTP choke point (_utfor_kall) that every fetch function in odds.py goes through, so retry policy / fail-loud / key-never-logged only had to be implemented once"
    - "Retryable-status allowlist (429/500/502/503/504) converted to requests.exceptions.HTTPError via raise_for_status() so tenacity's retry_if_exception_type can distinguish transient failures from fail-loud ones (401/422/etc, which sys.exit(1) immediately, no retry)"
    - "Historical fetch functions return (body, headers) tuples and never write to the archive or raise on a missing 'timestamp' — that stays parse_snapshot_til_rader's job, keeping the fetch layer and the parsing layer independently testable"

key-files:
  created: []
  modified: [odds.py, tests/test_odds.py, requirements.txt, .planning/REQUIREMENTS.md]

key-decisions:
  - "tenacity approved (godkjent) by the user after the blocking-human package-legitimacy checkpoint — see Pakkelegitimitet section below"
  - "_utfor_kall's non-retryable branch (sys.exit(1)) never prints params (which contains apiKey) — only the status code and response body text, verified by a dedicated test asserting the key string never appears in captured stdout"
  - "04_value_detector.py was intentionally NOT modified — this plan's files_modified scope is odds.py/tests/test_odds.py/requirements.txt only; the live-bot rewire (D-07's other half) is a later plan's job"

requirements-completed: []  # ODDS-01 not fully realized yet — HTTP client now exists but the paid backfill driver and 04_value_detector.py rewire still land in 04-05 through 04-09

# Metrics
duration: ~4min (coding) + checkpoint wait for tenacity approval
completed: 2026-08-23
---

# Phase 4 Plan 4: Live Odds Fetch, Historical Endpoints & Retry Caller Summary

**`odds.py` gets its HTTP layer — `hent_live_odds` (moved out of `04_value_detector.py`), `hent_historisk_odds_snapshot`/`hent_historiske_events` for the backfill, and a single tenacity-backed `_utfor_kall` choke point that retries transient errors and fails loud on everything else — all tested against mocked `requests.get`, zero real API credits spent.**

## Performance

- **Duration:** ~4 min of coding across 2 TDD cycles (RED/GREEN commits at 17:57–18:00); preceded by a blocking-human checkpoint (package-legitimacy for `tenacity`) that paused execution until the user responded
- **Started:** 2026-08-23T17:57:30+02:00 (first RED commit)
- **Completed:** 2026-08-23T18:00:32+02:00 (last GREEN commit)
- **Tasks:** 3 (1 checkpoint + 2 TDD implementation tasks)
- **Files modified:** 4 (`odds.py`, `tests/test_odds.py`, `requirements.txt`, `.planning/REQUIREMENTS.md`)

## Pakkelegitimitet

**Task 1's blocking-human checkpoint result: `tenacity` APPROVED.**

The user reviewed the checkpoint's verification steps (PyPI project page, GitHub repo, release history) and responded `"godkjent: tenacity"`. Per the checkpoint's own acceptance criteria, this is recorded verbatim here rather than assumed or auto-approved — the checkpoint was never bypassed, and no `pip install` ran before the explicit answer arrived.

- **Decision:** Install `tenacity` (not the hand-rolled `try/except` + `time.sleep(2 ** forsøk)` fallback).
- **Installed:** `venv/bin/pip install tenacity` → `tenacity-9.1.4` (verified via `importlib.metadata.version("tenacity")`, since 9.1.4 does not expose a `__version__` attribute directly).
- **requirements.txt:** `tenacity>=9.1.4` added as the 8th line, following the file's existing `>=`-bounded style, with a Norwegian trailing comment naming its purpose.
- **Retry implementation used in Tasks 2/3:** `@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30), retry=retry_if_exception_type(requests.exceptions.HTTPError), reraise=True)` decorating `_utfor_kall`, exactly as specified in the plan's tenacity path.

## Accomplishments
- `hent_api_nokkel()` added: reads `ODDS_API_NOKKEL` via `.env` (loaded inside the function body, not at module import — `odds.py` is imported by tests and `06_bot.py`), `sys.exit(1)` with the same Phase 1 guidance lines on missing key
- `_utfor_kall(url, params)` added: the sole `requests.get` choke point in the module — 429/5xx retry with exponential backoff (4 attempts, 2–30s) via tenacity; 401/422/404/etc fail loud with `sys.exit(1)` instead of ever returning empty data; `params` (containing the API key) is never printed or logged, only the URL and status code
- `hent_live_odds()` added: identical URL, params, and console output to the code it replaces (`04_value_detector.py:64-85`), built from the new `BASIS_URL` constant
- `hent_historisk_odds_snapshot()` added: sport-wide historical snapshot fetch, returns `(snapshot, headers)`, docstring names the D-03 amendment's verified cost (10 x markets x regions per call, once per snapshot regardless of games returned)
- `hent_historiske_events()` added: 1-credit discovery endpoint, returns `(svar, headers)`, no `regions`/`markets` params (the endpoint doesn't take them)
- Per-event odds endpoint (10 credits/game, ~3.6x the purchased budget for this project) deliberately not implemented — verified via `grep -c "events/{" odds.py` returning 0, backed by a dedicated test
- Full TDD gate followed for both tasks: RED commit (failing tests, functions didn't exist) → GREEN commit (implementation, all tests pass, no regressions)
- Test suite grew from 79 (pre-plan baseline) to 95 tests, all green, zero real network calls (`grep -c "requests.get(" tests/test_odds.py` returns 0 — every call goes through `unittest.mock.patch("odds.requests.get")`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Legitimitetsgodkjenning av tenacity** — no commit (checkpoint only; user approval recorded above, install/requirements.txt change folded into Task 2's GREEN commit per the plan's own action instructions)
2. **Task 2 (RED): Failing tests for hent_api_nokkel/_utfor_kall/hent_live_odds** - `189cfcc` (test)
2. **Task 2 (GREEN): Implement hent_api_nokkel/_utfor_kall/hent_live_odds + tenacity dependency** - `c8c3b54` (feat)
3. **Task 3 (RED): Failing tests for the two historical endpoints** - `4b9b441` (test)
3. **Task 3 (GREEN): Implement hent_historisk_odds_snapshot/hent_historiske_events** - `cb822a8` (feat)

**Plan metadata:** _pending_ (docs: complete plan — added after this summary is committed)

## Files Created/Modified
- `odds.py` - added `BASIS_URL`/`RETRYBARE_STATUSER` module constants, `import os`/`sys`/`requests`, `from dotenv import load_dotenv`, `from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential`, and 5 functions: `hent_api_nokkel`, `_utfor_kall`, `hent_live_odds`, `hent_historisk_odds_snapshot`, `hent_historiske_events`
- `tests/test_odds.py` - 16 new tests: `SvarMock` response stand-in (mirrors `requests.Response`'s `status_code`/`json()`/`text`/`headers`/`raise_for_status()`), 8 tests for `hent_api_nokkel`/`_utfor_kall`/`hent_live_odds` (key read/fail-fast, correct URL/params, 401 fail-loud, 429 retry-then-succeed, 503 exhaust-and-raise, 401/422 no-retry, key-never-printed), 6 tests for the two historical endpoints (URL/params, `(body, headers)` return contract, missing-timestamp pass-through, per-event-endpoint-absence check)
- `requirements.txt` - added `tenacity>=9.1.4`
- `.planning/REQUIREMENTS.md` - ODDS-01 traceability note updated to 3/9 plans (persistence + timestamp/parsing + HTTP client, backfill driver/live-bot rewire still pending)

## Decisions Made
- `tenacity` approved by the user — see Pakkelegitimitet section
- `time.sleep` patched to a no-op in the two retry-path tests (`test_utfor_kall_retryer_pa_429_og_lykkes`, `test_utfor_kall_gir_opp_etter_4_forsok_pa_503`) so the test suite doesn't actually wait through tenacity's real exponential backoff (which would otherwise add ~14s of real sleep to the 503-exhaustion test alone); production behavior (the real backoff timing) is unaffected — only the test process's `time.sleep` is patched
- `04_value_detector.py` intentionally untouched — this plan's `files_modified` scope (per its own frontmatter) is `odds.py`/`tests/test_odds.py`/`requirements.txt` only; wiring the live bot to call `hent_live_odds` instead of its inline HTTP block is a later plan's job (consistent with `must_haves.truths`' "single shared function" claim being a phase-level, not plan-level, guarantee)

## Deviations from Plan

**Observations (not deviations — mechanical grep-count checks that only fully resolve once both tasks land, consistent with 04-03-SUMMARY.md's precedent for this repo's plans):**

1. Task 2's own acceptance criteria lists `grep -c "BASIS_URL" odds.py` returning "at least 3" — after Task 2 alone this was 2 (the constant's definition plus its one use in `hent_live_odds`). It reaches 4 once Task 3 adds its own two usages (`hent_historisk_odds_snapshot`, `hent_historiske_events`), which is the state the module is in now. No code defect; the check is naturally satisfied only after both tasks in this plan are done.
2. The plan's `<verification>` section checks `grep -vc '^#' odds.py` stays under 400 non-comment lines, flagging the SUMMARY to report if it's larger. It is: 471 lines by that literal count (500 total lines in the file). This matches the codebase's established heavy pedagogical-documentation convention (long Norwegian docstrings on every new function explaining the credit model, retry policy, and threat mitigations, consistent with `CONVENTIONS.md`'s "Comments explain *why*, not *what*" and "Function docstrings are short... and explain purpose + return contract" guidance, though these particular docstrings run longer than "short" given how much undocumented API behavior they had to pin down). Not a structural code smell — no duplicated logic, no dead code — but flagged per the plan's own instruction as a module-size signal worth naming rather than silently exceeding.

**Auto-fixed issue:**

**1. [Rule 1 - Bug] `hent_api_nokkel`'s docstring accidentally duplicated the literal string being grep-checked**
- **Found during:** Task 2, immediately after implementation, while running the plan's own acceptance-criteria greps
- **Issue:** The first docstring draft explained `load_dotenv()`'s placement using the literal text `load_dotenv() kalles her inne...`, which made `grep -c "load_dotenv()" odds.py` return 2 (docstring + actual call) instead of the acceptance criterion's required exactly 1
- **Fix:** Reworded the docstring to describe the same behavior ("`.env`-innlastingen skjer her inne...") without repeating the literal `load_dotenv()` call-syntax string
- **Files modified:** `odds.py`
- **Verification:** `grep -c "load_dotenv()" odds.py` returns 1; full suite still green (89/89 at that point)
- **Committed in:** `c8c3b54` (part of Task 2's GREEN commit — caught before commit, not a follow-up fix)

---

**Total deviations:** 1 auto-fixed (Rule 1, caught pre-commit), 2 observations (both explained by the plan's own multi-task-check design, not defects)
**Impact on plan:** None on scope or behavior — both are documentation/reporting nuances, not functional gaps.

## Issues Encountered
None.

## User Setup Required

None beyond the checkpoint decision already recorded above. `ODDS_API_NOKKEL` continues to be read from the same git-ignored `.env` established in Phase 1 — no new environment variable introduced by this plan.

## TDD Gate Compliance

RED gate: `189cfcc` (Task 2), `4b9b441` (Task 3) — both confirmed failing (`AttributeError: module 'odds' has no attribute ...`) before implementation existed.
GREEN gate: `c8c3b54` (Task 2), `cb822a8` (Task 3) — all tests pass after each implementation; full 95-test suite green with no regressions.
No REFACTOR commits needed — one docstring wording fix was folded into the GREEN commit itself (caught before commit, see Deviations).

## Next Phase Readiness
- `odds.py` now exposes a complete, tested HTTP surface (`hent_live_odds`, `hent_historisk_odds_snapshot`, `hent_historiske_events`, `_utfor_kall`) that the backfill driver (04-05+) can call directly, with credit accounting (`(body, headers)` returns) already wired to feed `logg_kreditt` (04-01)
- `parse_snapshot_til_rader` (04-03) is ready to receive real `hent_historisk_odds_snapshot` responses — both were built and tested independently but share the exact snapshot-body shape
- Zero real API credits spent by this plan — verified via `grep -c "requests.get(" tests/test_odds.py` returning 0 both before and after, and the full test suite running in 0.17s (no real network latency)
- `04_value_detector.py` still has its own inline live-odds HTTP block — that rewire (the second half of D-07) is still open for a later plan, most naturally alongside the `04_value_detector.py`/`05_skadefilter.py` duplication cleanup already flagged in `STATE.md` (Phase 4 Plan 02 decision re: `gjeldende_sesong()`)
- No blockers.

---
*Phase: 04-historical-odds-acquisition-live-refactor*
*Completed: 2026-08-23*

## Self-Check: PASSED

- FOUND: odds.py
- FOUND: tests/test_odds.py
- FOUND: .planning/phases/04-historical-odds-acquisition-live-refactor/04-04-SUMMARY.md
- FOUND: 189cfcc (test RED, Task 2)
- FOUND: c8c3b54 (feat GREEN, Task 2)
- FOUND: 4b9b441 (test RED, Task 3)
- FOUND: cb822a8 (feat GREEN, Task 3)
