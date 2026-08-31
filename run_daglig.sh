#!/bin/bash
set -euo pipefail

# Daglig kjøre-wrapper rundt 06_bot.py, ment å startes av en launchd-jobb.
#
# launchd gir jobben et minimalt miljø: ingen shell-profil er kilde, ingen
# garantert working directory, og ingen PATH man kan stole på. Derfor finner
# dette skriptet prosjektroten fra sin egen filplassering, bytter dit
# eksplisitt, og kjører 06_bot.py med prosjektets egen venv-interpreter i
# stedet for en interpreter funnet via PATH.
#
# Kan også kjøres manuelt (./run_daglig.sh) for å teste at oppsettet virker.

REPO_ROT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROT"

LOGG_KATALOG="$REPO_ROT/logs"
LOGGFIL="$LOGG_KATALOG/run_daglig.log"
mkdir -p "$LOGG_KATALOG"

echo "==== $(date '+%Y-%m-%d %H:%M:%S') ====" >> "$LOGGFIL"

set +e
"./venv/bin/python3" 06_bot.py >> "$LOGGFIL" 2>&1
STATUS=$?
set -e

echo "==== slutt (exit-kode $STATUS) ====" >> "$LOGGFIL"

exit "$STATUS"
