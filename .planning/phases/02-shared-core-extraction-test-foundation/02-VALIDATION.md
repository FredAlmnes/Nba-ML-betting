---
phase: 2
slug: shared-core-extraction-test-foundation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-21
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 (to be installed this phase — currently absent from the repo) |
| **Config file** | `pytest.ini` (new, this phase) — `[pytest]` / `pythonpath = .` / `testpaths = tests` |
| **Quick run command** | `pytest -v` |
| **Full suite command** | `pytest -v` (suite is small enough that quick and full are identical this phase) |
| **Estimated runtime** | <10 seconds (pure unit tests, no I/O, no network, no fixtures larger than a small synthetic DataFrame) |

---

## Sampling Rate

- **After every task commit:** Run `pytest -v`
- **After every plan wave:** Run `pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** <10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-XX-XX | TBD | TBD | CORE-01 | — | `teams.finn_lag()` resolves every known team-name variant (full_name, nickname, abbreviation, substring) to the correct team | unit | `pytest tests/test_teams.py -v` | ❌ Wave 0 | ⬜ pending |
| 02-XX-XX | TBD | TBD | CORE-01 | — | `features.beregn_lag_form()` produces the same output shape/values as the current `02_feature_engineering.py` implementation on a fixed fixture — no silent behavior change during extraction | unit | `pytest tests/test_features.py -v` | ❌ Wave 0 | ⬜ pending |
| 02-XX-XX | TBD | TBD | CORE-01 | — | `strategy.fjern_vigorish()`/`beregn_value_og_ev()` reproduce the exact current `04_value_detector.py` math on known inputs | unit | `pytest tests/test_strategy.py -v` | ❌ Wave 0 | ⬜ pending |
| 02-XX-XX | TBD | TBD | CORE-02 | — | `config.py` constants match the exact current values (0.05 / 1.50 / 4.00 / 0.5 / 150.0 / 20.0 / 1000.0) — no drift during extraction | unit | `pytest tests/test_strategy.py::test_config_values -v` | ❌ Wave 0 | ⬜ pending |
| 02-XX-XX | TBD | TBD | CORE-03 | — | `beregn_innsats` — negative edge → 0.0; min/max stake clamping; half-Kelly fraction applied correctly | unit | `pytest tests/test_strategy.py -k innsats -v` | ❌ Wave 0 | ⬜ pending |
| 02-XX-XX | TBD | TBD | CORE-03 | — | Bet dedup key logic — exact duplicate detected; stale-row near-duplicate scenario covered | unit | `pytest tests/test_strategy.py -k dedup -v` | ❌ Wave 0 | ⬜ pending |
| 02-XX-XX | TBD | TBD | CORE-04 | — | `features.beregn_lag_form(..., as_of=D)` is deterministic and unaffected by rows with `game_date >= D` appended to input (determinism/leakage regression, scoped per CONTEXT.md D-12) | unit | `pytest tests/test_parity.py -v` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky — Plan/Wave/Task IDs filled in once the planner assigns them.*

---

## Wave 0 Requirements

- [ ] `pytest.ini` — framework config, enables `import teams`/`import features`/`import strategy` from `tests/` without package `__init__.py` files
- [ ] `requirements-dev.txt` (or equivalent) — pytest install declaration
- [ ] `tests/` directory + `test_teams.py`, `test_features.py`, `test_strategy.py`, `test_parity.py` — none exist yet; this phase creates the entire suite from scratch
- [ ] `tests/conftest.py` — shared fixtures (a small synthetic games DataFrame fixture needed by both `test_features.py` and `test_parity.py` — use one shared fixture rather than duplicating fixture construction, per the same anti-duplication discipline this phase enforces on production code)

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-08-21 (auto mode — recommended verification approach from RESEARCH.md adopted as-is)
