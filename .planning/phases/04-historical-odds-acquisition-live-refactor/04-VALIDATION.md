---
phase: 4
slug: historical-odds-acquisition-live-refactor
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-23
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 (`venv/bin/python -m pytest --version`) |
| **Config file** | `pytest.ini` (`pythonpath = .`, `testpaths = tests`) |
| **Quick run command** | `venv/bin/python -m pytest tests/test_odds.py -x -q` |
| **Full suite command** | `venv/bin/python -m pytest -q` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** `venv/bin/python -m pytest tests/test_odds.py tests/test_verdi_deteksjon.py tests/test_bot.py -x -q`
- **After every plan wave:** `venv/bin/python -m pytest -q` (full suite — includes existing `test_features.py`, `test_strategy.py`, `test_teams.py`, `test_parity.py`, `test_calibrering_split.py`)
- **Before `/gsd:verify-work`:** Full suite green, PLUS a manual smoke-test run of the historical fetch script against a tiny date range (1-2 dates) to confirm real API behavior — this is NOT automatable in pytest since it spends real credits. The full 480-date backfill must not run until the smoke test confirms the response schema and credit cost match expectations.
- **Max feedback latency:** 5 seconds (excluding the manual smoke test)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 0 | ODDS-01 | Pre-fetch existence check prevents a second network call/credit spend for an already-archived `(kamp_dato, snapshot_type)` | unit (mock HTTP, in-memory SQLite) | `pytest tests/test_odds.py::test_er_allerede_arkivert_hindrer_dobbelt_kall -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 0 | ODDS-01 | Sport-wide snapshot `data[]` rows correctly map to `nba_features.csv` games via `teams.py`'s resolver | unit (fixture JSON) | `pytest tests/test_odds.py::test_snapshot_matcher_bruker_teams_py -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 0 | ODDS-01 | SQLite `UNIQUE` constraint on the composite key prevents double-insert on re-run | unit (real tempfile SQLite) | `pytest tests/test_odds.py::test_dobbel_insert_er_idempotent -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 1 | ODDS-02 | `04_value_detector.py`'s extracted function returns the same value/EV output shape as before extraction | unit/regression (fixture input) | `pytest tests/test_verdi_deteksjon.py::test_finn_value_bets_uendret_output -x` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 1 | ODDS-02 | `06_bot.py`'s direct-call path degrades gracefully on an injected exception, matching the old subprocess-failure behavior | unit (monkeypatched raise) | `pytest tests/test_bot.py::test_pipeline_feil_degraderer_grasiost -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_odds.py` — pre-fetch existence check, snapshot-to-game matching, SQLite idempotency (ODDS-01)
- [ ] `tests/test_verdi_deteksjon.py` (name TBD by planner, matching whatever function name is extracted from `04_value_detector.py`) — regression proving extraction preserved output (ODDS-02)
- [ ] `tests/test_bot.py` — graceful-degradation behavior post-refactor (ODDS-02, Pitfall 5: subprocess boundary was providing implicit exception-swallowing that must be explicitly replicated)
- [ ] No new fixture infrastructure needed beyond `tests/conftest.py` — odds-specific fixtures (sample sport-wide JSON response) added as static fixtures/inline dicts, never live API calls

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real historical fetch against The Odds API succeeds, costs credits matching the estimate, and archives correctly | ODDS-01 | Spends real, already-paid-for credits; cannot be mocked without losing the point of the check | Run the fetch script against a tiny range (1-2 dates) first, inspect `x-requests-last`/`x-requests-remaining` response headers to confirm actual cost matches the ~10 credits/date estimate, inspect the SQLite archive contents, THEN run the full 480-date backfill |
| `06_bot.py` end-to-end run after the refactor produces the same dashboard/bankroll behavior as before | ODDS-02 | Full daily-pipeline behavior (dashboard generation, bankroll state) isn't unit-testable in isolation | Run `venv/bin/python3 06_bot.py` once after the refactor, compare console output and `dashboard.html` against a pre-refactor run for the same day's data |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
