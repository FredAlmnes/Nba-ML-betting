---
phase: 3
slug: calibration-remediation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-21
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (bundled in `venv/`; `pytest.ini` present, `pythonpath = .`, `testpaths = tests`) |
| **Config file** | `pytest.ini` (repo root) |
| **Quick run command** | `venv/bin/python3 -m pytest tests/test_calibrering_split.py -q` (once created) |
| **Full suite command** | `venv/bin/python3 -m pytest -q` (37 tests today, all passing) |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** Run `venv/bin/python3 -m pytest -q`
- **After every plan wave:** Run the full suite, plus one manual run of `venv/bin/python3 03_tren_modell.py` to visually confirm the reliability table prints correctly and `nba_modell.pkl` regenerates without errors
- **Before `/gsd:verify-work`:** Full pytest suite green + one clean manual run of `03_tren_modell.py` producing a labeled, non-`NaN` reliability table
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 0 | CALIB-01 | — / N/A | `train`/`calibrate`/`test` date ranges are non-overlapping and chronologically ordered | unit | `venv/bin/python3 -m pytest tests/test_calibrering_split.py -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | CALIB-01 | — / N/A | Isotonic calibrator's `.fit()` call only ever receives `X_kalibrer`/`y_kalibrer`, never `X_test`/`y_test` | unit | `venv/bin/python3 -m pytest tests/test_calibrering_split.py -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | CALIB-02 | — / N/A | Reliability table computed and printed using only `test`-split predictions, labeled "kalibrert på X, evaluert på Y" | manual/smoke | `venv/bin/python3 03_tren_modell.py` (inspect stdout) | N/A — script, not test file | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_calibrering_split.py` — stubs covering CALIB-01 (non-overlap / chronological-order assertions on the split logic)
- [ ] Pure split-boundary function (e.g. `del_kronologisk_3veis`, extracted per RESEARCH.md Pattern 3 recommendation) — new, small, must exist before the test can import it, since `03_tren_modell.py` has no `main()` guard and can't be safely imported directly
- [ ] No new fixtures strictly required — reuse `tests/conftest.py`'s existing date-fixture style, or build a minimal inline synthetic DataFrame as `test_features.py` already does

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reliability table reflects true out-of-sample calibration quality | CALIB-02 | This repo has no convention for unit-testing the top-level numbered pipeline scripts (`03_tren_modell.py` trains a real model and writes `nba_modell.pkl`); verified by full-script run, not by test file | Run `venv/bin/python3 03_tren_modell.py`, inspect console output for a clearly labeled reliability table computed on the `test` split (not `calibrate`), with no `NaN` values (confirms `out_of_bounds="clip"` is doing its job per RESEARCH.md finding) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
