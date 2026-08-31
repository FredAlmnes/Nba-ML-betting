---
phase: quick-260831-hij
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - run_daglig.sh
  - .gitignore
  - KOMME_I_GANG.md
autonomous: false
requirements: [QUICK-260831-hij]

must_haves:
  truths:
    - "run_daglig.sh runs 06_bot.py successfully from any working directory (launchd's minimal environment included)"
    - "Each run appends a timestamped block to a log file instead of overwriting the previous run's output"
    - "The script's exit code equals 06_bot.py's exit code, so launchd sees real failures"
    - "The log file is git-ignored and never committed"
    - "KOMME_I_GANG.md explains what run_daglig.sh is and that launchd invokes it"
  artifacts:
    - path: "run_daglig.sh"
      provides: "launchd-safe wrapper - cd to repo root, venv interpreter, append-with-timestamp logging, exit-code propagation"
      contains: "set -euo pipefail"
      executable: true
    - path: ".gitignore"
      provides: "logs/ ignore entry under a Norwegian section comment matching existing style"
      contains: "logs/"
    - path: "KOMME_I_GANG.md"
      provides: "Short Norwegian usage note for the scheduled daily run"
      contains: "run_daglig.sh"
  key_links:
    - from: "run_daglig.sh"
      to: "./venv/bin/python3"
      via: "explicit relative interpreter path after cd to repo root"
      pattern: "venv/bin/python3"
    - from: "run_daglig.sh"
      to: "logs/run_daglig.log"
      via: "append redirect of both stdout and stderr"
      pattern: ">>.*LOGGFIL"
    - from: "run_daglig.sh"
      to: "06_bot.py"
      via: "direct invocation, exit status captured and re-raised"
      pattern: "exit .*STATUS"
---

<objective>
Create `run_daglig.sh` - a launchd-safe wrapper around `06_bot.py` - plus its
`.gitignore` entry and a short usage note in `KOMME_I_GANG.md`.

Purpose: launchd runs jobs headless, with a minimal environment, no sourced shell
profile, and an unpredictable working directory. `06_bot.py` and every module it
imports (`odds.py`, `config.py`, `skadefilter.py`, ...) use bare relative filenames
for all file I/O (`bankroll.json`, `bets.json`, `dashboard.html`, `nba_features.csv`,
`nba_modell.pkl`, `odds_arkiv.db`). That is a documented architectural constraint of
this project, not something this plan fixes - so the wrapper must guarantee the
correct working directory, the correct interpreter, and a durable log of each run.

Output: `run_daglig.sh` (executable, tracked in git), a `logs/` ignore entry, and a
short Norwegian section in `KOMME_I_GANG.md`.

Explicitly out of scope: any edit to `06_bot.py`; creating the launchd plist; running
any `launchctl` command. The plist is a system-level file outside the repo and is
handled separately by the orchestrating session.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@CLAUDE.md
@KOMME_I_GANG.md
@.gitignore

<interfaces>
Facts already extracted from the codebase. Do not re-derive them by exploring.

Absolute repo root (contains spaces AND non-ASCII - quote every expansion):
  /Users/fredr/Documents/lære seg ting/Maskinlæring/nba_betting

Interpreter that has the project's dependencies installed:
  ./venv/bin/python3   (symlink to python3.14; system python3 lacks xgboost/pandas/nba_api)

Entry point being wrapped, 06_bot.py line 1096:
  if __name__ == "__main__": main()

06_bot.py has NO webbrowser/open call - it only prints the Norwegian hint
"Apne dashboard.html i nettleseren for full oversikt!". Safe to run headless.

Local shell is GNU bash 3.2.57 (macOS system bash at /bin/bash). `set -euo pipefail`
and `${BASH_SOURCE[0]}` are both supported. Do not use bash-4-only constructs.

Existing .gitignore section-comment style (Norwegian, comment + dash explanation):
  # Bankroll og bet-historikk - personlig data
  # Dashboard (genereres automatisk)
  # Lokale build/pip-scratch-artefakter (ikke del av prosjektet)

Paths already ignored (a new log path must NOT collide with any of these):
  venv/ __pycache__/ *.pyc *.pyo *.egg-info/ .env
  nba_kamper_raw.csv nba_features.csv nba_modell.pkl
  value_bets_idag.csv value_bets_med_skadefilter.csv odds_arkiv.db
  bankroll.json bets.json bankroll.json.bak bets.json.bak
  backtests/ nba_spillerlogg_raw.csv dashboard.html dashboard_tom.html
  .DS_Store _linux_pkgs/ _pip_tmp/ _pip_home/ _wheels/ _test.bin test_write.tmp

`logs/` does not exist on disk and is not currently ignored - it is free to use.
</interfaces>

<known_limitation>
`06_bot.py::kjør_pipeline` (line 217) wraps the whole value-detection pipeline in
`except (Exception, SystemExit)` (line 251), prints the error, and returns None.
`main()` never calls `sys.exit`. Consequence: a network/API failure inside the
pipeline still exits 0. The wrapper propagates whatever exit code Python returns -
it does not, and must not, try to second-guess it. Exit code 0 therefore means
"the bot ran to completion", not "the bot found bets". That crash barrier is
deliberate (the day's bankroll/bets still get saved) and is recorded in STATE.md as
a Phase 4 Plan 08 decision. Do NOT modify 06_bot.py to change this.
</known_limitation>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create run_daglig.sh and ignore its log directory</name>
  <files>run_daglig.sh, .gitignore</files>
  <action>
Create `run_daglig.sh` at the repo root. First line shebang `#!/bin/bash`, second line
`set -euo pipefail`. Follow with a short Norwegian comment block matching the tone of the
numbered Python scripts' docstrings: state that this is the daily wrapper launchd calls,
that it exists because launchd supplies no working directory and no shell profile, and
that it can also be run manually to test the setup.

Script behaviour, in order:

1. Resolve the repo root from the script's own location rather than hardcoding a path.
   Assign REPO_ROT using `$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)` and then
   `cd "$REPO_ROT"`. Every expansion of REPO_ROT, LOGG_KATALOG and LOGGFIL must be
   double-quoted - the real repo path contains both spaces and Norwegian characters, so
   an unquoted expansion breaks silently under launchd.
2. Assign LOGG_KATALOG to "$REPO_ROT/logs" and LOGGFIL to "$LOGG_KATALOG/run_daglig.log",
   then `mkdir -p "$LOGG_KATALOG"` so the first run works on a fresh clone.
3. Append a timestamp header line to the log before running anything, in exactly the form
   `==== 2026-08-31 14:00:01 ====`, produced with `date '+%Y-%m-%d %H:%M:%S'`. Use `>>`,
   never `>`, so multiple days accumulate in one readable file.
4. Run the bot with the project's own interpreter: `./venv/bin/python3 06_bot.py`,
   appending both streams to the log with `>> "$LOGGFIL" 2>&1`. Because `set -e` would
   abort before the footer is written, disable errexit around this single call: `set +e`,
   run, capture STATUS from `$?` on the very next line, then `set -e`.
5. Append a footer line recording the outcome, in the form `==== slutt (exit-kode $STATUS) ====`,
   so a reader scanning the log can tell a clean day from a failed one without parsing
   Python output.
6. End with `exit "$STATUS"` so launchd's exit-status tracking reflects the real result.
   Do not translate, clamp, or swallow the code.

Do NOT add a `python3`/`python` fallback branch. A silent fall back to system Python
would fail on missing xgboost/pandas in a way that is far harder to diagnose than a loud
"no such file" from an absent venv path.

Then make the script executable with `chmod +x run_daglig.sh`.

Finally, append a new section to `.gitignore`, placed immediately after the existing
`# Dashboard (genereres automatisk)` block and before the `# macOS` block, matching the
file's established Norwegian comment style: a comment line explaining that this is the
run log from the launchd job (local driftsdata, same category as bankroll/dashboard
output), followed by the entry `logs/`.
  </action>
  <verify>
    <automated>cd "/Users/fredr/Documents/lære seg ting/Maskinlæring/nba_betting" && bash -n run_daglig.sh && test -x run_daglig.sh && grep -q 'set -euo pipefail' run_daglig.sh && grep -q 'venv/bin/python3' run_daglig.sh && ! grep -qE '(^|[^/])python3? 06_bot\.py' run_daglig.sh && grep -q 'exit .*STATUS' run_daglig.sh && grep -q '>>' run_daglig.sh && grep -vE '^[[:space:]]*#' .gitignore | grep -qx 'logs/' && git check-ignore -q logs/run_daglig.log && echo OK</automated>
  </verify>
  <done>
`bash -n` parses the script clean; the file is executable; it uses `set -euo pipefail`;
it invokes `./venv/bin/python3` and never a bare `python3`/`python`; it exits with the
captured STATUS; `.gitignore` contains a non-comment `logs/` line and `git check-ignore`
confirms `logs/run_daglig.log` is ignored.
  </done>
</task>

<task type="auto">
  <name>Task 2: Prove exit-code propagation offline, then document the daily run</name>
  <files>KOMME_I_GANG.md</files>
  <action>
Part A - offline behavioural test. No API credits spent, no bankroll mutation, and
neither `06_bot.py` nor the real log is touched. Use throwaway files only:

1. Write a scratch file `_feilkode_test.py` at the repo root whose entire body is
   `import sys` then `sys.exit(3)`.
2. Copy `run_daglig.sh` to `_run_daglig_test.sh`. In the copy, replace `06_bot.py` with
   `_feilkode_test.py` and the log filename `run_daglig.log` with `_run_daglig_test.log`.
   Keep everything else byte-identical so the test exercises the real control flow
   (the same set -e handling, the same redirects, the same exit line).
3. Run `bash _run_daglig_test.sh` twice in a row, capturing the exit code each time.
4. Assert three things: both runs exit 3 (propagation survives `set -e`, the append
   redirect, and the footer line); `logs/_run_daglig_test.log` contains exactly 2 lines
   matching `^==== [0-9]` (header appended once per run, so run two did not truncate run
   one); and the log contains a footer line mentioning exit-kode 3.
5. Prove cd-independence, which is the actual launchd condition and the single most
   likely production failure mode: in one shell command, `cd /` and then invoke the test
   copy by its absolute path. Assert it still exits 3 and that the log now has 3 headers.
6. Delete all scratch artifacts: `_feilkode_test.py`, `_run_daglig_test.sh`, and
   `logs/_run_daglig_test.log`. Confirm `git status` shows none of them.

Part B - documentation. Add a short Norwegian section to `KOMME_I_GANG.md`, inserted
after the Steg 8 backtest block's closing `---` separator and before the
`## Hva betyr resultatene?` heading. Heading text: `## Daglig kjøring (launchd)`.
Keep it to a few lines in the guide's existing voice, covering: what `run_daglig.sh`
does (bytter til prosjektmappen, bruker `./venv/bin/python3`, kjører `06_bot.py`,
logger til `logs/run_daglig.log` med tidsstempel per kjøring); that it is meant to be
started automatically by a launchd-jobb in `~/Library/LaunchAgents/` kl. 14:00 lokal
tid rather than run by hand as the normal way to use the bot; that it can still be run
manually with `./run_daglig.sh` to test the setup; and that `logs/` er git-ignorert.
Do not paste the plist into the guide - the plist lives outside the repo and is not
part of this change.
  </action>
  <verify>
    <automated>cd "/Users/fredr/Documents/lære seg ting/Maskinlæring/nba_betting" && grep -q '^## Daglig kjøring (launchd)' KOMME_I_GANG.md && grep -q 'run_daglig.sh' KOMME_I_GANG.md && grep -q 'logs/run_daglig.log' KOMME_I_GANG.md && ! test -e _feilkode_test.py && ! test -e _run_daglig_test.sh && ! test -e logs/_run_daglig_test.log && echo OK</automated>
  </verify>
  <done>
The test copy exited 3 on all three invocations (twice from the repo root, once from `/`
via absolute path), the test log accumulated one header per run rather than being
truncated, and the footer recorded exit-kode 3. All scratch files are deleted.
`KOMME_I_GANG.md` has a `## Daglig kjøring (launchd)` section naming `run_daglig.sh`,
`logs/run_daglig.log`, the 14:00 launchd schedule, and the manual-test invocation.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Approve and perform one real end-to-end run</name>
  <action>
Present the cost disclosure below to the developer and WAIT for an explicit answer.
Do not run `run_daglig.sh` against the live bot before that answer arrives - this is
the only step in the plan with irreversible real-world side effects (Odds API credits,
bankroll/bets ledger mutation). If the answer is "hopp over", record the skip in the
SUMMARY and close the plan on the offline evidence from Task 2; the wrapper is already
fully covered there. If the answer is "kjor ekte", perform the four steps listed in
how-to-verify and record the exit code plus the log grep results in the SUMMARY.
  </action>
  <what-built>
`run_daglig.sh` (verified offline: syntax, executability, venv interpreter, append-only
logging, exit-code propagation from any working directory), a `logs/` entry in
`.gitignore`, and a `## Daglig kjøring (launchd)` note in `KOMME_I_GANG.md`.

Everything verifiable without side effects is already verified. What remains is one
real end-to-end run - and it is NOT free.
  </what-built>
  <how-to-verify>
STOP. Read the cost before approving. Running `./run_daglig.sh` for real executes one
full day of the live bot, with real-world side effects that cannot be undone by deleting
a file:

  - It calls The Odds API and SPENDS API CREDITS from the paid quota
    (STATE.md records 2,289 credits remaining after the Phase 4 backfill).
  - It calls nba_api for live team/player stats.
  - It SETTLES pending bets and MUTATES `bankroll.json` and `bets.json` - the real
    paper-trading ledger.
  - It may PLACE one or more new paper bets, appending them to that ledger with today's
    date, and rewrites `dashboard.html`.
  - `bankroll.json.bak` / `bets.json.bak` exist as the project's own backup convention;
    confirm you are comfortable with today's state being written before proceeding.

There is no cheaper substitute for this specific check: everything about the wrapper
itself has already been proven with the fake-failure harness in Task 2. The only thing a
real run adds is proof that the venv interpreter actually satisfies `06_bot.py`'s imports
under a minimal environment. If you would rather skip it, say so - the wrapper is
already covered by the offline tests, and the first scheduled 14:00 launchd run will
serve as the real-world proof instead.

If you approve, the executor will:
  1. Run, from a different working directory to mimic launchd:
     `cd / && "/Users/fredr/Documents/lære seg ting/Maskinlæring/nba_betting/run_daglig.sh"`
     and record the exit code.
  2. Confirm `logs/run_daglig.log` gained a new `====` timestamp header plus a footer
     line, and that the bot's own Norwegian OPPSUMMERING block is present in the log.
  3. Grep the log for the Odds API key value to confirm no secret leaked into a plaintext
     log file (mitigation for T-QUICK-01 below).
  4. Confirm `git status` shows no untracked log file (the `logs/` ignore rule holds).
  </how-to-verify>
  <resume-signal>
Reply "kjør ekte" to approve the one real run and its credit/ledger cost, or "hopp over"
to accept the offline evidence and let the first scheduled launchd run be the proof.
  </resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| launchd -> run_daglig.sh | Job starts with a minimal, non-interactive environment; no shell profile, no reliable PATH or cwd |
| 06_bot.py stdout/stderr -> logs/run_daglig.log | Everything the bot prints, including any error text, lands in a plaintext file on disk |
| repo -> git | A new log path could be committed if the ignore rule is wrong |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-QUICK-01 | Information disclosure | logs/run_daglig.log | mitigate | The Odds API key is read from `.env`; log is git-ignored via the `logs/` rule (Task 1) and grepped for the key value during the real-run checkpoint (Task 3) |
| T-QUICK-02 | Tampering | interpreter resolution in run_daglig.sh | mitigate | Interpreter is the explicit `./venv/bin/python3` after cd to the script's own resolved directory - no PATH lookup, so a hostile/stale PATH from launchd cannot substitute an interpreter; no `python3` fallback branch exists |
| T-QUICK-03 | Denial of service | unbounded log growth | accept | One append per day of a few KB; a rotation policy is not worth the complexity for a single-user local job. Revisit only if the file becomes unwieldy |
| T-QUICK-04 | Repudiation | silent failure invisible to launchd | mitigate | Exit code propagated verbatim via `exit "$STATUS"`, plus a footer line recording exit-kode per run. Residual risk documented in `<known_limitation>`: 06_bot.py's own crash barrier can still return 0 on a pipeline failure - out of scope here, 06_bot.py must not be modified |
| T-QUICK-SC | Tampering | package installs | n/a | This plan installs no packages. No npm/pip/cargo install task exists, so no legitimacy gate is required |
</threat_model>

<verification>
- `bash -n run_daglig.sh` parses clean and the file is executable.
- The wrapper's exit code equals the wrapped process's exit code, proven with a
  deliberate `sys.exit(3)` harness, including one invocation from `/` by absolute path.
- Repeated runs append to the log rather than truncate it (one `====` header per run).
- `git check-ignore -q logs/run_daglig.log` succeeds; `git status` stays clean of logs.
- `KOMME_I_GANG.md` documents the wrapper and its launchd role in Norwegian.
- `git diff --stat` touches only `run_daglig.sh`, `.gitignore`, `KOMME_I_GANG.md` -
  `06_bot.py` is unchanged. No plist created, no `launchctl` command run.
</verification>

<success_criteria>
- `run_daglig.sh` exists at the repo root, is executable and tracked in git, and runs
  `06_bot.py` under `./venv/bin/python3` from the repo root regardless of the caller's
  working directory.
- Every run appends a `==== YYYY-MM-DD HH:MM:SS ====` header, the bot's full
  stdout+stderr, and an exit-kode footer to `logs/run_daglig.log`.
- The script exits with `06_bot.py`'s exit code.
- `logs/` is git-ignored under a Norwegian section comment matching `.gitignore`'s style.
- `KOMME_I_GANG.md` has a brief `## Daglig kjøring (launchd)` section.
- `06_bot.py` is byte-unchanged; no launchd plist created; no `launchctl` invoked.
</success_criteria>

<output>
Create `.planning/quick/260831-hij-create-a-wrapper-shell-script-run-daglig/260831-hij-SUMMARY.md` when done.
</output>
