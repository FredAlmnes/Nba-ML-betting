---
phase: 2
slug: shared-core-extraction-test-foundation
status: complete
nyquist_compliant: true
wave_0_complete: true
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
| 02-04-02 | 02-04 | 4 | CORE-01 | T-02-09 | `teams.finn_lag()` resolves every known team-name variant (full_name, nickname, abbreviation, substring) to the correct team | unit | `pytest tests/test_teams.py -v` | ✅ | ✅ green |
| 02-05-02 | 02-05 | 5 | CORE-01 | T-02-14 | `features.beregn_lag_form()` produces the same output shape/values as the current `02_feature_engineering.py` implementation on a fixed fixture — no silent behavior change during extraction | unit | `pytest tests/test_features.py -v` | ✅ | ✅ green |
| 02-03-02 | 02-03 | 3 | CORE-01 | — | `strategy.fjern_vigorish()`/`beregn_value_og_ev()` reproduce the exact current `04_value_detector.py` math on known inputs | unit | `pytest tests/test_strategy.py -v` | ✅ | ✅ green |
| 02-02-03 | 02-02 | 2 | CORE-02 | T-02-05 | `config.py` constants match the exact current values (0.05 / 1.50 / 4.00 / 0.5 / 150.0 / 20.0 / 1000.0) — no drift during extraction | unit | `pytest tests/test_strategy.py::test_config_values -v` | ✅ | ✅ green |
| 02-03-02 | 02-03 | 3 | CORE-03 | T-02-06 | `beregn_innsats` — negative edge → 0.0; min/max stake clamping; half-Kelly fraction applied correctly | unit | `pytest tests/test_strategy.py -k innsats -v` | ✅ | ✅ green |
| 02-03-02 | 02-03 | 3 | CORE-03 | T-02-07 | Bet dedup key logic — exact duplicate detected; stale-row near-duplicate scenario covered | unit | `pytest tests/test_strategy.py -k dedup -v` | ✅ | ✅ green |
| 02-06-01 | 02-06 | 6 | CORE-04 | T-02-14 | `features.beregn_lag_form(..., as_of=D)` is deterministic and unaffected by rows with `game_date >= D` appended to input (determinism/leakage regression, scoped per CONTEXT.md D-12) | unit | `pytest tests/test_parity.py -v` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. All seven rows above were flipped to ✅ green in plan 02-06 Task 2 after personally running each row's exact Automated Command in this task and observing the stated pass count (see 02-06-SUMMARY.md "Named-command verification" for the raw output of each run). The `teams.finn_lag()` row also carries T-02-09 (broadened substring-fallback resolution safety, proven by the 90-assertion sweep in `test_teams.py`); the `config.py` row carries T-02-05 (silent threshold drift); the `beregn_innsats` row carries T-02-06 (call-site parameter-order regression); the dedup row carries T-02-07 (the 2026-08-19 stale-row bug shape); the `as_of` rows (`features.beregn_lag_form`, both CORE-01 and CORE-04) carry T-02-14 (leakage via `<=` instead of `<`), consistent with the dedup-drift audit in T-02-07.*

## De-duplication audit (ROADMAP Phase 2 success criterion 1)

Ran in plan 02-06 Task 2. All four commands below exclude `venv/`; two of the four
(`get_teams()` and the money-math `def` grep) also needed a `tests/`/path-prefix
correction versus the plan's literal command, because this repo's `grep -r .`
(BSD grep on macOS) prints matched paths WITHOUT a leading `./` for files directly
under the search root (`teams.py:8:...`, not `./teams.py:8:...`), so a filter written
as `grep -v "^./venv/"` is a silent no-op on this platform. The corrected commands
below are semantically identical to the plan's intent, adjusted only for that path-
prefix difference; raw command output is in `02-06-SUMMARY.md`.

| # | What | Command (path-prefix corrected) | Result | Verdict |
|---|------|----------------------------------|--------|---------|
| a | Team lookup | `grep -rn "get_teams()" --include="*.py" . \| grep -v "^venv/" \| grep -v "^tests/"` | 4 lines: `teams.py` ×3 (1 code call + 2 prose/comment mentions), `01_hent_data.py` ×1 (code call) | ✅ zero surviving *resolver* duplicates. Isolating executable call sites only (`grep -E "= *(nba_teams\|teams)\.get_teams\(\)"`) narrows this to exactly 2 code call sites: `teams.py` (the canonical resolver) and `01_hent_data.py:20` (declared exception — full 30-team roster enumeration for historical fetch, never one of D-03's four resolver duplicates, confirmed out of scope in `02-04-SUMMARY.md`'s own audit). `04_value_detector.py`, `05_skadefilter.py`, `06_bot.py`, `debug_kamp.py` all resolve via `teams.finn_lag`/`finn_lag_id` — zero surviving copies. |
| b | Stat list | `grep -rn '"PTS", *"FG_PCT", *"FT_PCT"' --include="*.py" . \| grep -v "^venv/"` | 1 hit: `features.py:18` (`STATS_KOLONNER`) | ✅ exact match to expectation |
| c | Strategy constants | `grep -rn -E "^(MIN_VALUE_TERSKEL\|MIN_ODDS\|MAX_ODDS\|KELLY_FRAKSJON\|MAX_INNSATS\|MIN_INNSATS\|STARTKAPITAL) *=" --include="*.py" . \| grep -v "^venv/"` | 7 hits, all `config.py` | ✅ exact match to expectation |
| d | Money math | `grep -rn -E "^def (beregn_innsats\|beregn_lag_form\|finn_lag\|fjern_vigorish)" --include="*.py" . \| grep -v "^venv/"` | 5 lines: `features.py` (`beregn_lag_form`), `teams.py` ×2 (`finn_lag`, `finn_lag_id` — the latter is an unanchored-regex artifact: `finn_lag` matches the *prefix* of `finn_lag_id`, a distinct, legitimate helper, not a duplicate), `strategy.py` ×2 (`fjern_vigorish`, `beregn_innsats`) | ✅ 4 real function definitions, one each in the plan's declared modules; the strict acceptance-criteria pattern (excludes `finn_lag`, checks 0 hits outside `strategy.py`/`features.py`) confirms 0 excess |

**Verdict:** zero NEW surviving duplicate implementations found. Both discrepancies against
the plan's literal expected counts are pre-existing, already-documented states: (1)
`01_hent_data.py`'s unrelated `get_teams()` call, declared out of D-03's scope in
`02-04-SUMMARY.md`; (2) the money-math grep pattern's own prefix-matching imprecision
(`finn_lag` vs `finn_lag_id`), not a second implementation of `finn_lag` itself. Per this
task's own instruction ("do not adjust the expectation to match reality — the surviving
duplicate is the finding"), both are recorded here rather than silently absorbed — but
neither is a NEW finding requiring a plan change; both were already investigated and
justified in a prior plan (02-04) or are inherent to the grep pattern's own text-matching
imprecision (02-06, this task).

---

## Wave 0 Requirements

- [x] `pytest.ini` — framework config, enables `import teams`/`import features`/`import strategy` from `tests/` without package `__init__.py` files (present, confirmed via `ls`, plan 02-02)
- [x] `requirements-dev.txt` (or equivalent) — pytest install declaration (present, confirmed via `ls`, plan 02-02)
- [x] `tests/` directory + `test_teams.py`, `test_features.py`, `test_strategy.py`, `test_parity.py` — all four present, confirmed via `ls` (plans 02-04, 02-05, 02-03, 02-06 respectively)
- [x] `tests/conftest.py` — shared fixtures (present, confirmed via `ls`; consumed by both `test_features.py` and `test_parity.py`, per the same anti-duplication discipline this phase enforces on production code)

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — every Per-Task Verification Map row carries a concrete `pytest` command; all seven were run in plan 02-06 Task 2 and observed passing
- [x] Sampling continuity: no 3 consecutive tasks without automated verify — every row has an automated command, zero manual-only rows
- [x] Wave 0 covers all MISSING references — all four Wave 0 artifacts confirmed present via `ls` in plan 02-06 Task 2
- [x] No watch-mode flags — every command in this file is a one-shot `pytest -v`/`pytest -k`/`pytest tests/x.py::y` invocation, no `--watch`/`-f` present anywhere
- [x] Feedback latency < 10s — full suite (37 tests) completes in ~0.18s, individual file runs in ~0.02–0.12s, confirmed this session
- [x] `nyquist_compliant: true` set in frontmatter — set

**Approval:** approved 2026-08-21 (auto mode — recommended verification approach from RESEARCH.md adopted as-is)

**Closed:** 2026-08-21, plan 02-06 Task 2 — full suite green at 37/37, all four de-duplication greps evidenced above, frontmatter status flipped to closed-out and `wave_0_complete: true` set.
