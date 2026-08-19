---
phase: 1
slug: repo-hygiene-config-remediation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-08-19
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None installed — no `pytest`/test config anywhere in repo. Not warranted for this phase (no testable business logic added; config-loading, git-tracking, and doc edits only). |
| **Config file** | none |
| **Quick run command** | `grep -n 'API_NØKKEL = "' 04_value_detector.py` (expect no match) |
| **Full suite command** | Run all 4 manual/smoke checks in the Per-Task Verification Map below |
| **Estimated runtime** | ~10 seconds (all checks are grep/exit-code/manual-read, no live API calls) |

---

## Sampling Rate

- **After every task commit:** Run the relevant smoke check for that task (grep for removed literal, or missing-env-var exit-code check)
- **After every plan wave:** Re-run all 4 checks below — this phase is a single wave
- **Before `/gsd:verify-work`:** All 4 checks must pass
- **Max feedback latency:** ~10 seconds (no build/compile step)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | HYG-01 | Info Disclosure (hardcoded secret) | Missing `ODDS_API_NØKKEL` env var causes fatal error, not silent failure | smoke | `unset ODDS_API_NØKKEL; python 04_value_detector.py; echo $?` → expect FEIL message + exit code 1 | N/A | ⬜ pending |
| 01-01-02 | 01 | 1 | HYG-01 | Info Disclosure (hardcoded secret) | No hardcoded key literal remains in source | static check | `grep -n 'API_NØKKEL = "' 04_value_detector.py` → expect no match | N/A | ⬜ pending |
| 01-02-01 | 01 | 1 | HYG-02 | — | Fresh clone can import `modell_utils` without `ModuleNotFoundError` | smoke | `git ls-files \| grep modell_utils.py` (tracked) + fresh-clone `python -c "from modell_utils import KalibrertModell"` | N/A | ⬜ pending |
| 01-03-01 | 01 | 1 | HYG-03 | — | Docs no longer silently imply undeployed values are live | manual review | Read added header note on `KALIBRERING_RAPPORT.md`/`ENDRINGER_SUMMARY.txt`; confirm it states values were never deployed and names actual running values | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements — no test framework install warranted (per RESEARCH.md: no testable business logic added; automated test-framework setup is explicitly scoped to Phase 2/CORE-03).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Key rotation completed on the-odds-api.com | HYG-01 | Requires human login to an external account — not executable by an agent | User manually rotates the key at the-odds-api.com and places the new value in a local `.env` (not committed) |
| Doc "superseded" note is unambiguous | HYG-03 | Requires human judgment of clarity, not a checkable assertion | Read the note; confirm it states plainly (not hedged) that the proposed values were never deployed |

---

## Validation Sign-Off

- [x] All tasks have automated/smoke verify or Wave 0 dependencies (N/A — no Wave 0 gaps)
- [x] Sampling continuity: no 3 consecutive tasks without verify (all 4 tasks have a check)
- [x] Wave 0 covers all MISSING references (none missing — single wave, no framework needed)
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-08-19 (auto mode — recommended verification approach from RESEARCH.md adopted as-is)
