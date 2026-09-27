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
# Etter boten deployes public/ (dashboardet) til Vercel, se README.md.
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

# Deploy dashboardet (public/) til Vercel. Hoppes over hvis Vercel CLI mangler
# eller public/ ikke er koblet til et Vercel-prosjekt ennå (se README.md).
# launchd har ingen PATH fra shell-profilen, så Homebrew/npm-stiene legges til
# eksplisitt. En feilet deploy logges, men endrer ikke botens exit-kode.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
if [ -f "public/index.html" ] && [ -d "public/.vercel" ] && command -v vercel >/dev/null 2>&1; then
    echo "-- deployer public/ til Vercel --" >> "$LOGGFIL"
    set +e
    (cd public && vercel deploy --prod --yes) >> "$LOGGFIL" 2>&1
    echo "-- vercel exit-kode $? --" >> "$LOGGFIL"
    set -e
else
    echo "-- hopper over Vercel-deploy (mangler vercel CLI eller public/.vercel) --" >> "$LOGGFIL"
fi

echo "==== slutt (exit-kode $STATUS) ====" >> "$LOGGFIL"

exit "$STATUS"
