---
phase: 5
slug: "walk-forward-backtest-engine"
type: "holdout-resultat"
holdout_brukt: false
holdout_dato: null
run_id: null
kjoringskatalog: null
manifest_fil: null
ledger_fil: null
frys_run_id: "20260828-095233-3cc4a836"
frys_git_head: "33bbae11d63b06522f35d3fc55a22283b75379a1"
git_head: "f8de4655f206426ac8e9ac868814e88ae3390b6a"
godkjent_av: "Utvikleren, direkte i denne økten, via en eksplisitt AskUserQuestion som la frem irreversibiliteten, den frosne konfigurasjonen og den ærlige advarselen om lite utvalg fra tuning-skivens funn før svaret ble gitt. Svar: 'Yes, run the holdout now.'"
godkjent_dato: 2026-08-29
created: 2026-08-29
---

## 1. Forhåndssjekk og godkjenning

**Pytest-sammendrag (kjørt fra repo-roten, `./venv/bin/python3 -m pytest tests/ -q`):**

```
346 passed, 45 warnings in 29.90s
```

**Skann A (filsystem — `type`-feltet i hvert `backtests/*/manifest.json`):**

Alle ti eksisterende manifester i `backtests/` ble lest. Verdier funnet: `tuning` (×10).
Ingen `holdout`.

```
20260827-134920-6fd9654f  tuning  2022-10-24 -> 2022-12-31
20260827-140650-6fd9654f  tuning  2022-10-24 -> 2022-12-31
20260827-225526-6fd9654f  tuning  2022-11-15 -> 2022-11-30
20260827-225535-6fd9654f  tuning  2022-11-15 -> 2022-11-30
20260827-225602-6fd9654f  tuning  2024-04-10 -> 2024-04-14
20260828-092713-6fd9654f  tuning  2022-10-24 -> 2024-04-14
20260828-093206-9fd2dcbd  tuning  2022-10-24 -> 2024-04-14
20260828-093815-3cc4a836  tuning  2022-10-24 -> 2024-04-14
20260828-095206-6fd9654f  tuning  2022-10-24 -> 2024-04-14
20260828-095233-3cc4a836  tuning  2022-10-24 -> 2024-04-14 (dette er frys-kjøringen)
```

**Skann B (git-sporet register — `.planning/STATE.md`):** `grep -c "HOLDOUT BRUKT" .planning/STATE.md`
→ `0`. Dette er den lastbærende skanningen: `backtests/` er gitignored, så skann A alene ville
returnert rent på en fersk klone eller en ryddet arbeidskatalog selv om holdouten var brukt for
måneder siden. Utvikleren skal forstå at det er dette skannet — ikke skann A — hele kontrollen
faktisk hviler på.

**Skann C (planleggingsartefakter):** `grep -rn 'type": "holdout"\|HOLDOUT BRUKT\|05-HOLDOUT-RESULTAT' .planning/ --include="*.md"`
utenfor `05-13-PLAN.md` → ingen treff. Ingen tidligere forsøk har kommet lenger enn dette.

**Kodeintegritet siden frysen:** `git diff --name-only 33bbae11d63b06522f35d3fc55a22283b75379a1..HEAD`
over de elleve produksjonsfilene (`config.py strategy.py backtest.py metrics.py model.py odds.py
skadefilter.py features.py spillerlogg.py modell_utils.py 08_kjor_backtest.py`) → tom output.
`git status --porcelain` over de samme filene → tom output (ingen uforpliktede endringer). Motoren
er byte-uendret siden frysen. (`HEAD` selv har beveget seg til `f8de465` — en `docs`-commit som
rettet et korrupt `git_head`-hash i `05-FROSNE-BESLUTNINGER.md`s frontmatter; den commiten rørte
ingen av de elleve filene, kun planleggingsdokumentasjon, og er derfor forventet å avvike fra
frysens `git_head` uten at motoren har endret seg.)

**Datagrunnlag:** `nba_features.csv` → 3 638 rader, 480 unike `GAME_DATE_HJEMME`-verdier,
spennende `2022-10-24` .. `2025-04-13`. Uendret siden frysen. `odds_arkiv.db` (67 309 568 bytes)
og `nba_spillerlogg_raw.csv` (5 337 368 bytes) finnes begge på disk.

**Ignore-sjekk:** `git check-ignore -q backtests` → suksess (exit 0). `backtests/` er gitignored;
kjørekatalogen denne planen er i ferd med å opprette kan ikke bli committet.

**Frysens proveniens:** `frys_run_id` = `20260828-095233-3cc4a836`, `frosset_dato` = `2026-08-28`,
`godkjent_av` (fra `05-FROSNE-BESLUTNINGER.md`) = *"Utvikleren, via to eksplisitte
AskUserQuestion-runder i økten: (1) 'Freeze tight threshold (0.20/2.50) + flat staking
(Recommended)' etter kalibreringsfiksen, (2) tidligere 'Fix calibration methodology first
(Recommended)' da metningsfunnet ble presentert. Direkte utvikler-svar, ikke agent-relayed."*

**Kommandoen som er i ferd med å kjøre**, ordrett fra `05-FROSNE-BESLUTNINGER.md`s
`## Hva 05-13 skal kjøre`:

```bash
./venv/bin/python3 08_kjor_backtest.py --holdout --bekreft-holdout --min-value-terskel 0.20 --maks-odds 2.50 --flat
```

**Utviklerens svar på denne sjekkpunktet, ordrett:** *"Yes, run the holdout now"* — gitt direkte
i denne økten som svar på en eksplisitt AskUserQuestion som la frem, før spørsmålet ble stilt: at
handlingen er irreversibel, at den frosne konfigurasjonen (0.20/2.50/flat) er hva som evalueres,
og den ærlige advarselen om at 52 (eller 36 "rene") bets på tuning-skiven er et lite utvalg hvis
konfidensintervall ikke utelukker null. Godkjent 2026-08-29.

Ingen holdout-kjøring eksisterte i det øyeblikket denne godkjenningen ble gitt — dette er bevist
av de tre uavhengige skanningene A, B og C over, samtlige rene.

## 2. Kjøringen

Ikke kjørt ennå — fylles av oppgave 2.

## 3. Konfigurasjonen som ble evaluert

Ikke kjørt ennå — fylles av oppgave 2.

## 4. Hovedtall på holdout

Ikke kjørt ennå — fylles av oppgave 2.

## 5. Datakvalitet og hopp

Ikke kjørt ennå — fylles av oppgave 2.

## 6. Før/etter mot dagens tapende live-oppsett

Ikke kjørt ennå — fylles av oppgave 2.

## 7. Hvor mye vekt tallene tåler

Ikke kjørt ennå — fylles av oppgave 2.

## 8. Konklusjon mot Core Value-porten

Ikke kjørt ennå — fylles av oppgave 2.

## 9. Rå terminalutskrift

Ikke kjørt ennå — fylles av oppgave 2.
