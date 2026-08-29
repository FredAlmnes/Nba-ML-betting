# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — NBA Value Betting Bot MVP

**Shipped:** 2026-08-29
**Phases:** 5 | **Plans:** 35 | **Sessions:** several across 10 days (2026-08-19 → 2026-08-29), with Phase 5's execution + audit landing in one very long final session

### What Was Built
- Repo hygiene fixes: leaked API key rotated to env var, untracked model wrapper tracked, stale docs reconciled with running config (Phase 1)
- A shared, tested core (`features.py`, `strategy.py`, `teams.py`, `config.py`) replacing 2-4 independent duplicates each, plus the repo's first automated tests (Phase 2)
- A real same-slice calibration leakage bug fixed with a disjoint train/calibrate/test split (Phase 3)
- A permanent SQLite archive of historical odds (480 dates, 187,376 rows) and a live bot refactored onto the shared core in-process (Phase 4)
- A walk-forward backtest engine with a structurally-enforced one-shot holdout guard, CLV/ROI/drawdown reporting with bootstrap and Wilson confidence intervals, and a Kelly-fraction sensitivity sweep (Phase 5)
- The milestone's actual test of Core Value: the one-shot 2024-25 holdout, spent under a frozen configuration — result inconclusive (19 bets, ROI -25.0%, CI straddles zero)

### What Worked
- **Remediation-first phase ordering** (hygiene → shared core → calibration → odds/refactor → backtest) meant every phase before the backtest closed an already-confirmed risk that would otherwise have poisoned the final numbers. No rework was needed once Phase 5 started.
- **TDD extraction pattern** (write tests against the target module's intended interface, then extract logic out of the numbered scripts into it) was used consistently from Phase 2 through Phase 5 and caught several real pre-existing bugs during extraction, not after (e.g., the `df`→`df_raw` closure bug in `beregn_lag_form`, the isotonic calibration degeneracy).
- **Structural (code-enforced) guards over convention** for the holdout: `HoldoutLaastFeil` and a two-flag-plus-confirmation CLI path made the "check the holdout exactly once" rule something the code refuses to violate, not just a documented promise. This mattered — the guard was tested and held.
- **Blocking checkpoints at real decision points** (credit ceilings, freeze configuration, spending the holdout) kept irreversible/costly actions under explicit developer authorization rather than agent judgment calls.

### What Was Inefficient
- Several plans had to correct their own literal acceptance-criteria examples (floating-point edge cases in `beregn_innsats`, a GNU-vs-BSD grep path-prefix assumption, a stale per-event-endpoint doc reference) — the plan text was slightly wrong, not the code. Worth double-checking literal example values against actual float/platform behavior during planning, not just during execution.
- Phase 5 Plan 07's research document (`05-RESEARCH.md` Pattern 7) had a structural bug in its recency-window logic that would have made the injury filter incapable of ever flagging anyone; caught during execution, not research review.
- The final session ran Phase 5's full 13-plan/10-wave execution plus milestone-level code review, verification, and audit back-to-back without a natural pause point, requiring multiple context compactions and eventually a structured handoff (`HANDOFF.json` + `.continue-here.md`) to resume cleanly. A milestone-audit checkpoint offering an explicit "pause here" option after phase completion (before diving into audit) might have been a cleaner boundary.

### Patterns Established
- Shared core modules live as flat files at repo root (not a package), matching the existing Norwegian-identifier, numbered-script convention — validated as sufficient through all 5 phases without needing a restructure.
- `gjeldende_sesong()`-style small helper duplications get flagged in SUMMARY.md as "Phase N consolidation" candidates but are *not* auto-fixed unless a plan explicitly owns them — this kept plans scoped, but the duplication documented in Phase 2 was still unconsolidated by Phase 5's end (see tech debt below). Future milestones should assign an owning plan up front for flagged-but-deferred items, or accept they'll persist indefinitely.
- Dashboard/bankroll bugs found incidentally during code review (stored XSS, double-checkpoint bug, home/away mismatch risk) were logged as deferred follow-ups rather than scope-creeped into the current phase — correct call, but they remain unfixed at v1.0 close and should be explicitly triaged for the next milestone rather than left implicit.

### Key Lessons
1. A backtest engine that reports an honest "inconclusive" result is a successful outcome for a milestone whose actual goal was building a trustworthy measurement instrument — resist the urge to treat a non-positive result as something to "fix" by re-tuning against the same spent holdout.
2. Structural guards (code that refuses an action) are worth the extra implementation cost over convention/documentation for anything irreversible — the one-shot holdout guard is the clearest example in this milestone.
3. When a real bug is found mid-phase (e.g., the calibration degeneracy), fix it as a permanent, general fix at the source rather than special-casing the one run that surfaced it — the 50-game floor in `model.py` protects every future walk-forward run, not just the one that found the bug.

### Cost Observations
- Sessions: several short sessions for Phases 1-4, one very long session for all of Phase 5 plus milestone closeout
- Notable: real API costs were tightly managed via blocking credit-ceiling checkpoints — 17,710 of a ~20,000-credit paid tier spent on the full historical odds archive, with measured (not estimated) per-call costs informing the ceiling before the spend

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | ~6 | 5 | Established remediation-first ordering, TDD extraction pattern, and structural (code-enforced) guards for irreversible actions |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|---------------------|
| v1.0 | 349 | Not measured | `python-dotenv`, `tenacity` |

### Top Lessons (Verified Across Milestones)

1. Structural (code-enforced) guards beat convention for anything irreversible — established in v1.0, not yet cross-validated by a second milestone.
