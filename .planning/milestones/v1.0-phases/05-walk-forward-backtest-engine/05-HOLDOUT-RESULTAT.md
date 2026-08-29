---
phase: 5
slug: "walk-forward-backtest-engine"
type: "holdout-resultat"
holdout_brukt: true
holdout_dato: 2026-08-29
run_id: "20260829-092351-3cc4a836"
kjoringskatalog: "backtests/20260829-092351-3cc4a836"
manifest_fil: "backtests/20260829-092351-3cc4a836/manifest.json"
ledger_fil: "backtests/20260829-092351-3cc4a836/ledger.csv"
frys_run_id: "20260828-095233-3cc4a836"
frys_git_head: "33bbae11d63b06522f35d3fc55a22283b75379a1"
git_head: "36b43bc9affba39d24f6598c229b789ac15d8a0f"
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

Den frosne kommandolinjen, kjørt fra repo-roten med `venv` aktiv, ordrett, ingen flagg lagt til
eller fjernet:

```bash
./venv/bin/python3 08_kjor_backtest.py --holdout --bekreft-holdout --min-value-terskel 0.20 --maks-odds 2.50 --flat
```

- **run_id:** `20260829-092351-3cc4a836`
- **Kjøringskatalog:** `backtests/20260829-092351-3cc4a836/`
- **git_head (repo-tilstand da kjøringen ble startet):** `36b43bc9affba39d24f6598c229b789ac15d8a0f`
  (oppgave 1s commit — inneholder kun `05-HOLDOUT-RESULTAT.md` seksjon 1, ingen produksjonsfil)
- **manifest["type"]:** `"holdout"`
- **opprettet:** `2026-08-29T09:23:51.926435`
- **Kjøretid (klokketid):** cirka 3 sekunder (startet 07:23:49 UTC, manifest skrevet umiddelbart
  etter siste retrening — dette stemmer med `05-FROSNE-BESLUTNINGER.md`s estimat på sekunder, ikke
  minutter, for 7 retreninger over 1 225 kamper)

**periode-blokken:**

| Nøkkel | Verdi |
|---|---|
| fra_dato | 2024-10-22 |
| til_dato | 2025-04-13 |
| datoer_totalt | 162 |
| datoer_behandlet | 162 |
| kamper_totalt | 1225 |

`periode["fra_dato"]` = `"2024-10-22"` er strengt større enn `config.HOLDOUT_START_DATO` =
`"2024-10-01"` — det verifiserbare beviset, i denne filen, på at ingen tuning-dato kom inn i
kjøringen. `datoer_totalt` leser 162, ikke 480 — narrowingen i `kjor_endelig_holdout_backtest`
fant sted som forventet.

**Tellersammenligning (forventet fra `05-13-PLAN.md`s `verified_data_facts` vs. observert i
manifestet):**

| Teller | Forventet | Observert | Match? |
|---|---|---|---|
| periode.datoer_totalt | 162 | 162 | ja |
| periode.datoer_behandlet | 162 | 162 | ja |
| periode.kamper_totalt | 1225 | 1225 | ja |
| datakvalitet.retreninger | 7 | 7 | ja |
| datakvalitet.datoer_hoppet_over_for_lite_treningsgrunnlag | 0 | 0 | ja |
| periode.fra_dato | "2024-10-22" | "2024-10-22" | ja |
| periode.til_dato | "2025-04-13" | "2025-04-13" | ja |
| datakvalitet.kamper_uten_closing_snapshot | 0 eller 1 | 0 | ja |

Alle åtte tellere stemmer. Ingen avvik å eskalere.

## 3. Konfigurasjonen som ble evaluert

Én rad per nøkkel i `manifest["konfig"]`, i manifestets egen rekkefølge, sammenlignet mot den
frosne `F-05-NN`-tabellen i `05-FROSNE-BESLUTNINGER.md`:

| Nøkkel | Verdi i holdout-kjøringen | Frosset verdi (F-05-NN) | Lik frysen? |
|---|---|---|---|
| min_value_terskel | 0.2 | 0.20 (F-05-01) | ja |
| min_odds | 1.5 | 1.5 (F-05-02) | ja |
| maks_odds | 2.5 | 2.5 (F-05-03) | ja |
| kelly_fraksjon | null (flat stake) | flat, ikke Kelly (F-05-04, "staking-regel") | ja |
| flat_innsats | 20.0 | 20.0 kr (F-05-05) | ja |
| startkapital | 1000.0 | 1000.0 (F-05-06) | ja |
| min_innsats | 20.0 | 20.0 (F-05-07) | ja |
| maks_innsats | 150.0 | 150.0 (F-05-08) | ja |
| min_treningskamper | 100 | 100 (F-05-09) | ja |
| kalibrer_andel | 0.15 | 0.15 (F-05-10) | ja |
| retrenings_kadens | "maanedlig" | "maanedlig" (F-05-11) | ja |
| holdout_start_dato | "2024-10-01" | "2024-10-01" (F-05-12) | ja |
| skadefilter_aktiv | true | true (F-05-13) | ja |
| bootstrap_seed | 42 | 42 (F-05-14) | ja |
| bootstrap_n_resamples | 1000 | 1000 (F-05-15) | ja |

Alle femten rader leser `ja`. Ingen `config.py`-verdi ble endret av denne planen eller av plan
05-12 — den frosne konfigurasjonen ble uttrykt utelukkende som CLI-argumenter til
`08_kjor_backtest.py`. Live `config.py` kjører fortsatt `MIN_VALUE_TERSKEL=0.05`,
`MIN_ODDS=1.50`, `MAX_ODDS=4.00`, `KELLY_FRAKSJON=0.5` — uendret, verifisert i seksjon 6.

## 4. Hovedtall på holdout

`manifest["headline"]` peker på `"metrikker"` (full periode). D-05-02 låste to-metrikksett-
policyen (full periode som hovedtall, pluss et ekskludert-innbrenning sensitivitetssjekk) — begge
kolonner er derfor reelle, ingen er tapt.

`innbrenning_maaneder`: 3. `innbrenning_fra_dato`: `"2025-01-02"` (de tre første kalendermånedene
av holdout-perioden, 2024-10 til 2024-12, er ekskludert i høyre kolonne).

| Nøkkel | metrikker (full periode) | metrikker_uten_innbrenning (fra 2025-01-02) |
|---|---|---|
| antall_bets | 19 | 5 |
| antall_vunnet | 7 | 1 |
| roi | -25.0% | -53.4% |
| roi_ci_nedre | -64.5% | -100.0% |
| roi_ci_oevre | 24.6% | 39.8% |
| vinnrate | 36.8% | 20.0% |
| vinnrate_ci_nedre | 19.1% | 3.6% |
| vinnrate_ci_oevre | 59.0% | 62.4% |
| maks_drawdown_kroner | 101.0 kr | 53.4 kr |
| maks_drawdown_andel | 10.0% | 5.3% |
| sum_innsats | 380.0 kr | 100.0 kr |
| sum_profitt | -95.0 kr | -53.4 kr |
| clv_snitt | 0.8% | -1.1% |
| antall_med_clv | 19 | 5 |
| antall_uten_clv | 0 | 0 |
| andel_slo_closing | 57.9% | 40.0% |
| bootstrap_seed | 42 | 42 |
| bootstrap_n_resamples | 1000 | 1000 |

`datakvalitet["sluttsaldo"]`: **905,0 kr**, mot `konfig["startkapital"]`: **1 000,0 kr** —
en endring på **-95,0 kr (-9,5 %)** over hele holdout-perioden (dette er ROI på innsats, ikke på
kapital; -9,5 % kapitalendring vs. -25,0 % ROI på de 380 kr som faktisk ble satset, fordi kun
19 av 1 225 kamper noensinne ble en plassert bet).

## 5. Datakvalitet og hopp

Alle fjorten `datakvalitet`-nøkler, ingen utelatt eller oppsummert:

| Teller | Verdi |
|---|---|
| datoer_hoppet_over_for_lite_treningsgrunnlag | 0 |
| kamper_hoppet_over_manglende_odds | 0 |
| kamper_hoppet_over_ukjent_lag | 0 |
| kamper_uten_closing_snapshot | 0 |
| kandidater_flagget | 46 |
| kandidater_blokkert_av_skadefilter | 27 |
| skadesjekk_uten_datagrunnlag | 2 |
| kandidater_uten_kelly_edge | 0 |
| bets_hoppet_over_duplikat | 0 |
| bets_uten_utfall | 0 |
| datoer_stoppet_lav_bankroll | 0 |
| bets_uten_clv | 0 |
| retreninger | 7 |
| sluttsaldo | 905.0 |

`datoer_hoppet_over_for_lite_treningsgrunnlag` er 0 her, mot 15 i tuning-kjøringen, fordi
treningsvinduet er ekspanderende fra 2022-10-24: hver eneste holdout-dato har allerede minst
2 413 kamper strengt før seg — langt over `min_treningskamper` (100). Et positivt tall i denne
telleren ville betydd at det ekspanderende vinduet ikke ekspanderte, en defekt og ikke en
grensebetingelse; 0 er nettopp det forventede resultatet.

Den ene kjente closing-snapshot-hullkampen i denne slicen, `2025-01-09` DAL(1610612742) vs
POR(1610612757), er den eneste mulige kilden til en manglende CLV i hele holdout-perioden. Den
kampen ble aldri en plassert bet (ingen rad i `ledger.csv` er datert 2025-01-09), så den påvirker
verken `kamper_uten_closing_snapshot` (0) eller `bets_uten_clv` (0) i denne kjøringen — hullet
eksisterer, men ble aldri satset på.

Fase 4s tynne eu-region-bookmaker-dekning (10-11 bookmakere/kamp tidlig i 2022-23, mot 17-19
senere) gjelder tuning-skiven og ikke i vesentlig grad 2024-25, som ligger i den godt dekkede sene
perioden — `andel_slo_closing` (57,9 %) og `clv_snitt` (0,8 %) i denne kjøringen bekrefter at
prisdataene for holdout-perioden er av god kvalitet, ikke systematisk skjeve av tynn dekning.

`skadesjekk_uten_datagrunnlag` er 2 (ikke null): to av de 46 flaggede kandidatene kunne ikke
sjekkes mot skadefilteret fordi spillerloggdataene manglet grunnlag for den kampdatoen. Disse to
kandidatene ble IKKE automatisk blokkert (skadefilteret feiler åpent, ikke lukket, når det mangler
data) — de gikk videre til simuleringspasset som om skadefilteret ikke fant noe å blokkere på. Med
kun 46 kandidater totalt er 2 en liten, men ikke neglisjerbar, andel av grunnlaget for ROI-tallet
over; det er ikke stort nok til å endre konklusjonen i seksjon 8, men leseren skal vite at ikke
alle 46 kandidatene fikk en fullverdig skadesjekk.

## 6. Før/etter mot dagens tapende live-oppsett

Dette er milepælens faktiske betalingspunkt.

| Dimensjon | Før (dagens live-oppsett) | Etter (holdout-evaluering) | Kilde |
|---|---|---|---|
| Bevisgrunnlag | Manuell daglig paper-trading via `06_bot.py`, ingen formell logg utover `bankroll.json`s sluttsaldo | Én låst walk-forward-holdout-simulering, kjørt én gang | `.planning/PROJECT.md` §Context / denne filen §2 |
| Periode | ukjent (ikke registrert noe sted på disk — `bankroll.json.historikk` er tom) | 2024-10-22 til 2025-04-13 (162 datoer, 7 kalendermåneder) | `.planning/codebase/CONCERNS.md`; manifest.json `periode` |
| Bankroll (start → slutt) | 1 000,00 kr → **74,88 kr** (≈ -92,5 %) | 1 000,00 kr → 905,00 kr (-9,5 %) | `.planning/PROJECT.md` §Context ("fell from 1000 kr to 74.88 kr"); manifest.json `datakvalitet.sluttsaldo` |
| ROI med 95 % KI | ukjent | -25,0 % (KI -64,5 % – 24,6 %) | manifest.json `metrikker.roi` / `roi_ci_*` |
| Vinnrate med KI | ukjent | 36,8 % (KI 19,1 % – 59,0 %) | manifest.json `metrikker.vinnrate` / `vinnrate_ci_*` |
| Maks drawdown | ukjent | 10,0 % (101,0 kr) | manifest.json `metrikker.maks_drawdown_andel/_kroner` |
| Antall bets | ukjent | 19 (av 46 flaggede kandidater, av 1 225 kamper) | manifest.json `metrikker.antall_bets` |
| CLV | ukjent | +0,8 % snitt, 19/19 bets med CLV, 57,9 % slo closing-linjen | manifest.json `metrikker.clv_snitt/antall_med_clv/andel_slo_closing` |
| Terskler (min_value_terskel / min_odds / maks_odds) | 0,05 / 1,50 / 4,00 (`config.py`, uendret) | 0,20 / 1,5 / 2,5 (frosset, kun CLI for denne kjøringen) | `04_value_detector.py:31-33`; manifest.json `konfig` |
| Kelly-fraksjon | 0,5 (halv Kelly) | flat stake (ingen Kelly-fraksjon), 20 kr/bet | `config.py` `KELLY_FRAKSJON`; manifest.json `konfig.kelly_fraksjon` |
| Hvordan verdiene ble valgt | Manuell justering for hånd, aldri validert mot en backtest | Frosset FØR denne kjøringen, etter en egen tuning-/kalibreringsprosess på en atskilt skive som aldri rørte 2024-25 | `.planning/PROJECT.md` §Context; `05-FROSNE-BESLUTNINGER.md` |

Fire punkter, alle påkrevd:

1. **Asymmetrien er reell, ikke slurv.** `bankroll.json` leser i dag `saldo: 1000.0` med en tom
   `historikk`, og `bets.json` er en tom liste (verifisert 2026-08-26). Begge er gitignored, så
   den tapende kjøringens ledger finnes ikke lenger noe sted og kan ikke rekonstrueres. 74,88
   kr-sluttpunktet er et dokumentert historisk faktum, ikke et tall som kan regnes om. De to
   sidene er derfor ikke sammenlignbare bet-for-bet, og `ukjent`-cellene over er ærlige, ikke late.
2. **Periodene og bet-universene er forskjellige.** Før-siden er live paper trading under
   live-konfigurasjonen over en ikke-registrert tidsperiode; etter-siden er en simulert
   gjenspilling av 2024-25-sesongen alene. Ulike sesonger, ulike kamper, ulike utvalgsstørrelser.
   Dette er en sammenligning av hvilket bevis som finnes på hver side, ikke en kontrollert A/B-test,
   og skal ikke leses som en.
3. **Er den frosne konfigurasjonen identisk med live `config.py`? Nei — og det er nettopp
   frysings-prosessens poeng.** `min_value_terskel` (0,05 live vs. 0,20 frosset), `maks_odds`
   (4,00 live vs. 2,50 frosset) og staking-regelen (halv Kelly live vs. flat frosset) er alle
   forskjellige. Med andre ord: holdout-kjøringen evaluerte IKKE den samme konfigurasjonen som
   tapte penger live — den evaluerte en STRAMMERE konfigurasjon som tuning-skiven (etter
   kalibreringsfiksen) viste et lovende, men lite, signal for. `05-FROSNE-BESLUTNINGER.md`
   dokumenterer (kjøring 5/8) at live-konfigurasjonen selv, evaluert på samme tuning-skive etter
   kalibreringsfiksen, ga ROI -1,3 % — fortsatt ikke skilt fra null. Denne 05-13-holdouten testet
   derfor ikke live-konfigurasjonen på nytt; den testet frysings-kandidaten. En uendret
   konfigurasjon skal aldri fremstilles som en forbedring — og her er konfigurasjonen ikke
   uendret, men resultatet (-25,0 % ROI på holdouten) er heller ingen forbedring av den frosne
   kandidatens egen tuning-tall (+15,0 % ROI). Se seksjon 7 for hva den forskjellen betyr.
4. **`KALIBRERING_RAPPORT.md` / `ENDRINGER_SUMMARY.txt`s påstand om 17 % vinnrate og -67 % ROI
   brukes IKKE som baseline her.** Fase 1 merket begge dokumentene SUPERSEDED og aldri utrullet,
   og tallene deres er aldri reprodusert av noe i dette repoet. De navngis her, én gang, som en
   supersedert historisk påstand — de får ingen egen rad i tabellen over.

## 7. Hvor mye vekt tallene tåler

**Utvalgsstørrelse:** 19 bets. Prior-milepælens forskning (`.planning/research/PITFALLS.md`)
setter linjen for "statistisk ikke-avgjort" ved cirka 300-500 plasserte bets. 19 er dypt under den
linjen — mer enn en størrelsesorden mindre enn selv den nedre grensen. Et bredt konfidensintervall
ved dette utvalget er forventet og korrekt, ikke en defekt i beregningen.

**Straddler ROI-intervallet null?** Ja. `roi_ci_nedre` = -64,5 %, `roi_ci_oevre` = +24,6 % — null
ligger godt innenfor intervallet ved 95 % konfidens. Datasettet kan verken bekrefte eller avkrefte
et reelt positivt eller negativt signal på egen hånd.

**Straddler vinnrate-intervallet break-even-vinnraten implisert av kjøringens egne gjennomsnitts-
odds?** Gjennomsnittsodds over de 19 bets-ene er 2,13, som impliserer en break-even-vinnrate på
cirka 47,9 % (gjennomsnitt av 1/odds per bet). Observert vinnrate er 36,8 %, med KI [19,1 %,
59,0 %] — dette intervallet OMSLUTTER break-even-vinnraten (47,9 % ligger innenfor [19,1 %,
59,0 %]). Med andre ord: datasettet kan ikke skille denne kjøringens vinnrate fra
"akkurat god nok til å gå i null" ved 95 % konfidens, selv om punktestimatet (36,8 %) ligger under
break-even.

**Sammenligning mot tuning-kjøringens tall** (fra `05-12-SUMMARY.md` / `05-FROSNE-BESLUTNINGER.md`,
samme frosne konfigurasjon, atskilt skive):

| Metrikk | Tuning-skive (52 bets) | Holdout-skive (19 bets) |
|---|---|---|
| ROI | +15,0% (KI -11,9% – 42,9%) | -25,0% (KI -64,5% – 24,6%) |
| Vinnrate | 57,7% (KI 44,2% – 70,1%) | 36,8% (KI 19,1% – 59,0%) |
| Maks drawdown | 7,8% | 10,0% |
| CLV snitt | +2,075% | +0,8% |

Holdout-resultatet ligger klart under tuning-resultatet på alle fire metrikker — ROI snur fra
positivt til negativt, vinnraten faller nesten 21 prosentpoeng. Dette er den klassiske
in-sample-optimisme-signaturen: en konfigurasjon valgt fordi den så lovende ut på én skive,
evaluert på nytt på en atskilt skive, og signalet holder ikke. Punktestimatene peker i motsatt
retning av hverandre, men begge konfidensintervallene er brede nok til å overlappe hverandre
betydelig (tuning: -11,9% til 42,9%; holdout: -64,5% til 24,6% — et felles intervall på omtrent
-11,9% til 24,6%), så dette er ikke et statistisk bevist sprik heller — det er et datasett for
lite til å avgjøre om forskjellen er reell eller støy, i begge retninger.

Et bredt intervall ved denne utvalgsstørrelsen er forventet og korrekt, ikke en defekt.

## 8. Konklusjon mot Core Value-porten

**Ikke avgjort**

Begrunnelse i to setninger: `roi_ci_nedre` (-64,5 %) er negativ og `roi_ci_oevre` (+24,6 %) er
positiv — ROI-intervallet omslutter null, som alene er tilstrekkelig for `Ikke avgjort` uansett
utvalgsstørrelse; i tillegg er `antall_bets` (19) langt under 300, så porten forblir stengt på
begge de to uavhengige kriteriene samtidig. Punktestimatet er negativt (-25,0 % ROI, 36,8 %
vinnrate), men konfidensintervallet er for bredt til å skille dette resultatet statistisk fra
null ved 19 bets, og en holdout-run kan derfor verken bekrefte eller avkrefte den frosne
konfigurasjonens verdi alene.

Riktig neste steg er mer data eller en annen strategi — ikke en ny terskeljustering mot denne
skiven. Ingen nye terskelverdier foreslås i dette dokumentet: å foreslå dem nå, etter å ha sett
holdout-tallene, er nøyaktig det anti-mønsteret `.planning/REQUIREMENTS.md` navngir under
Out of Scope ("in-sample threshold/parameter tuning without a locked holdout") — å gjøre det på
holdout-skiven ville gjøre ethvert fremtidig tall fra denne skiven verdiløst som bevis.

Holdouten for milepæl v1.0 er nå brukt opp. En fremtidig ute-av-utvalg-evaluering krever nye data
(2025-26-sesongen), ikke en ny kjøring mot 2024-25.

`.planning/PROJECT.md`s begrensning krever uansett paper trading før ekte penger — dette punktet
er uendret av verdikten over: verken et positivt eller et ikke-avgjort holdout-resultat er noen
gang et grønt lys for innsats med ekte penger alene.

## 9. Rå terminalutskrift

```
============================================================
WALK-FORWARD BACKTEST
============================================================
Modus:                holdout
Fra:                  (tidligste dato i nba_features.csv)
Til:                  (ingen øvre grense — kun holdout-veien)
Sweep:                False
Uten skadefilter:     False
Min value-terskel:    0.2
Min odds:             1.5
Maks odds:            2.5
Kelly-fraksjon:       (flat stake, se under)
Flat innsats:         20.0 kr
Startkapital:         1000.0
Min treningskamper:   100
Features-fil:         nba_features.csv
Arkiv:                odds_arkiv.db
Katalog:              backtests
============================================================
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
ADVARSEL: Dette evaluerer den LÅSTE 2024-25-holdouten.
Den brukes opp NØYAKTIG ÉN GANG for hele prosjektet og kan IKKE
brukes opp på nytt etterpå.
Hver terskel- og Kelly-beslutning må allerede være FROSSET
(plan 05-12) FØR denne kjøringen — konfigurasjonen echoet over
må stemme med den frosne.
run_id-en fra denne kjøringen må skrives inn i
.planning/STATE.md etterpå (plan 05-13).
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
============================================================
WALK-FORWARD PREDIKSJONSPASS
fra_dato: 2024-10-22
til_dato: 2025-04-13
datoer_totalt: 162
datoer_behandlet: 162
datoer_hoppet_over_for_lite_treningsgrunnlag: 0
kamper_totalt: 1225
kamper_hoppet_over_manglende_odds: 0
kamper_hoppet_over_ukjent_lag: 0
kamper_uten_closing_snapshot: 0
kandidater_flagget: 46
kandidater_blokkert_av_skadefilter: 27
skadesjekk_uten_datagrunnlag: 2
retreninger: 7
prediksjoner: 19
min_treningskamper: 100
kalibrer_andel: 0.15
min_value_terskel: 0.2
min_odds: 1.5
maks_odds: 2.5
skadefilter_aktiv: True
============================================================
============================================================
SIMULERINGSPASS
startkapital: 1000.0
kelly_fraksjon: None
flat_innsats: 20.0
min_innsats: 20.0
maks_innsats: 150.0
kandidater_totalt: 19
bets_plassert: 19
kandidater_uten_kelly_edge: 0
bets_hoppet_over_duplikat: 0
bets_uten_utfall: 0
datoer_stoppet_lav_bankroll: 0
bets_uten_clv: 0
sluttsaldo: 905.0
============================================================
============================================================
BACKTEST-OPPSUMMERING
run_id:               20260829-092351-3cc4a836
type:                 holdout
katalog:              backtests/20260829-092351-3cc4a836
fra_dato:             2024-10-22
til_dato:             2025-04-13
datoer_behandlet:     162
kamper_totalt:        1225
kamper_hoppet_over_manglende_odds:  0
kandidater_flagget:                 46
kandidater_blokkert_av_skadefilter:  27
retreninger:                         7
antall_bets:          19
roi:                  -25.0% (KI -64.5% – 24.6%)
vinnrate:             36.8%
maks_drawdown:        10.0%
clv_snitt:            0.008481831807341031
============================================================
manifest.json skrevet til: backtests/20260829-092351-3cc4a836/manifest.json
```

(XGBoost `use_label_encoder`-advarsler fra hver av de 7 retreningene er utelatt over for lesbarhet
— de er uskadelige biblioteksadvarsler, ikke feil, og påvirker ikke tallene.)
