---
phase: "5"
slug: "walk-forward-backtest-engine"
type: "frosne-beslutninger"
run_id: "20260828-095233-3cc4a836"
kjoringskatalog: "backtests/20260828-095233-3cc4a836"
manifest_fil: "backtests/20260828-095233-3cc4a836/manifest.json"
ledger_fil: "backtests/20260828-095233-3cc4a836/ledger.csv"
sweep_fil: "backtests/20260828-095233-3cc4a836/kelly_sweep.json"
git_head: "33bbae133de71c47a95170a3a2f8a2e97b30d8dc"
frosset: true
frosset_dato: 2026-08-28
godkjent_av: "Utvikleren, via to eksplisitte AskUserQuestion-runder i økten: (1) 'Freeze tight threshold (0.20/2.50) + flat staking (Recommended)' etter kalibreringsfiksen, (2) tidligere 'Fix calibration methodology first (Recommended)' da metningsfunnet ble presentert. Direkte utvikler-svar, ikke agent-relayed."
created: 2026-08-28
---

## Sammendrag av hele frysings-prosessen

Denne fasen gikk gjennom flere runder, ikke én enkelt kjøring. Rekkefølgen,
i sin helhet, fordi den er selve begrunnelsen for hvilken konfigurasjon som
til slutt ble frosset:

1. **Kjøring 1** (`20260828-092713-6fd9654f`): full trening/kalibrering-slice
   med live-konfigurasjonen (`min_value_terskel=0.05`, halv Kelly). 458 bets,
   ROI 1.7 % (KI −10.1 % til 12.7 %) — statistisk ikke skilt fra null.
2. Utvikleren ba om et forsøk med strammere terskel før frysing.
3. **Kjøring 2** (`min-value-terskel=0.20`, `maks-odds=2.50`, halv Kelly):
   kun 18 bets, ROI −38.6 %. For lite utvalg til å bety noe alene.
4. Samme terskel med **flat stake** (én arm i `--sweep`): 60 bets, ROI 3.9 %,
   CLV +1.2 % — det mest lovende funnet så langt, men uten egen
   ledger (flat fantes da kun som sweep-arm, ikke egen kjøremodus).
5. Utvikleren ba om at flat-staking skulle gjøres til en egen kjørbar modus
   (for at 05-13 faktisk skal kunne gjenskape den frosne konfigurasjonen).
   `--flat`-flagget ble lagt til `08_kjor_backtest.py` (commit `404621b`).
6. **Et alvorlig datakvalitetsfunn** dukket opp ved inspeksjon av
   ledger.csv fra kjøring 4: 23 av 60 bets (38 %) hadde `modell_prob`
   nøyaktig `1.0` — umulig ekte modellsikkerhet. Rotårsak: `KALIBRER_ANDEL=0.15`
   ga kalibreringssett så små som ~15 kamper ved `MIN_TRENINGSKAMPER=100`,
   godt under selv Fase 3s ENGANGS-kalibreringssett på 172 kamper (som
   Fase 3 selv allerede flagget som under sklearns ~1000-anbefaling).
   Isotonic regression metter til 0/1 med så få kalibreringspunkter.
7. Utvikleren ba om at kalibreringsmetodikken ble fikset før videre arbeid.
   Et absolutt gulv (`MIN_KALIBRERINGSKAMPER=50`,
   `MIN_TRENING_ETTER_KALIBRERING=50`) ble lagt til `model.py::del_for_trening`
   (commit `33bbae1`), verifisert mot 15 nye/endrede tester.
8. **Kjøring 5** (samme live-config som kjøring 1, ETTER fiksen): metning
   falt fra ~38 % til ~3.5 % i denne slicen; ROI-bildet endret seg lite
   (−1.3 %, fortsatt ikke skilt fra null) — live-konfigurasjonen var
   aldri det lovende funnet.
9. **Kjøring 6 — DEN FROSNE KJØRINGEN** (`20260828-095233-3cc4a836`): samme
   stramme terskel (0.20/2.50) + flat stake, ETTER kalibreringsfiksen.
   52 bets, ROI **15.0 %** (KI −11.9 % til 42.9 %), CLV **+2.08 %**,
   maks drawdown 7.8 %. Metning falt til 16/52 (30.8 %) — fortsatt
   til stede men lavere. Et manuelt sjekk mot kun de 36 "rene" (ikke-mettede)
   bets-ene i denne kjøringen viste ROI 10.2 %, CLV 2.32 % — signalet
   overlever å fjerne de gjenværende mettede bets-ene.
10. Utvikleren valgte, direkte, å fryse på kjøring 6s konfigurasjon.

**Viktig ærlighet om utvalgsstørrelsen:** 52 bets (eller 36 "rene") er et
lite utvalg. Konfidensintervallet [−11.9 %, 42.9 %] utelukker IKKE null ved
95 % konfidens. Dette er det mest lovende funnet i hele utforskningen —
det er ikke et statistisk bevist funn. Holdout-kjøringen (plan 05-13) er
den ENESTE gjenværende testen som kan bekrefte eller avkrefte det.

## Kalibreringsfiksen (D-05-05) — hvorfor den er en reell korreksjon, ikke tuning

Dette er IKKE en terskel-justering på trening/kalibrering-skiven (som ville
vært i tråd med REQUIREMENTS.md sin advarsel mot "in-sample threshold/parameter
tuning without a locked holdout") — det er en korreksjon av en metodefeil i
HVORDAN modellen kalibreres, oppdaget og fikset FØR frysing, på samme skive
frysingen selv bruker. Fiksen endrer ikke noen strategi-parameter
(`min_value_terskel`, `maks_odds`, Kelly-fraksjon) — den endrer kun hvor mange
kamper som går til `IsotonicRegression.fit()` per retrening. Se
`model.py`-commit `33bbae1` for full begrunnelse og `tests/test_model.py`
for de 4 nye/endrede testene som låser oppførselen.

## Kjøringen som ble frosset

Full invokasjon (kjørt fra repo-roten, med `venv` aktiv, ETTER
kalibreringsfiksen i commit `33bbae1`):

```bash
./venv/bin/python3 08_kjor_backtest.py --min-value-terskel 0.20 --maks-odds 2.50 --flat --sweep --stille
```

- **run_id:** `20260828-095233-3cc4a836`
- **Kjøringskatalog:** `backtests/20260828-095233-3cc4a836/`
- **git_head (denne kjøringen ble produsert etter):** `33bbae133de71c47a95170a3a2f8a2e97b30d8dc`
- **manifest["type"]:** `"tuning"`
- **opprettet:** `2026-08-28T09:52:33.457226`

`manifest["periode"]["til_dato"]` er `"2024-04-14"`, strengt mindre enn
`config.HOLDOUT_START_DATO = "2024-10-01"`. Kjøringen har aldri rørt den
låste 2024-25-holdouten.

## Konfigurasjonen som produserte tallene

Én rad per nøkkel i `manifest["konfig"]`, i manifestets egen rekkefølge:

| Nøkkel | Verdi i kjøringen | Live-verdi i config.py |
|---|---|---|
| min_value_terskel | 0.20 | 0.05 |
| min_odds | 1.5 | 1.50 |
| maks_odds | 2.5 | 4.00 |
| kelly_fraksjon | null (flat) | 0.5 |
| flat_innsats | 20.0 | — |
| startkapital | 1000.0 | 1000.0 |
| min_innsats | 20.0 | 20.0 |
| maks_innsats | 150.0 | 150.0 |
| min_treningskamper | 100 | — |
| kalibrer_andel | 0.15 | — |
| retrenings_kadens | "maanedlig" | — |
| holdout_start_dato | "2024-10-01" | "2024-10-01" |
| skadefilter_aktiv | true | — |
| bootstrap_seed | 42 | — |
| bootstrap_n_resamples | 1000 | — |

**To verdier avviker fra live-konfigurasjonen** (`min_value_terskel`,
`maks_odds`) pluss staking-regelen (flat i stedet for halv Kelly) — dette
er nettopp resultatet av frysings-prosessen: live-konfigurasjonen viste
intet reelt signal selv etter kalibreringsfiksen (se kjøring 5/8 over),
mens denne strammere konfigurasjonen gjorde det.

## Trakten

| Steg | Antall | Andel av forrige steg |
|---|---|---|
| kamper_totalt | 2 302 | 100,0 % |
| kandidater_flagget | 127 | 5,5 % av kamper_totalt |
| minus kandidater_blokkert_av_skadefilter (75) | 52 | 40,9 % av kandidater_flagget |
| minus kandidater_uten_kelly_edge (0) | 52 | 100,0 % (flat stake har ingen Kelly-edge-terskel) |
| minus bets_hoppet_over_duplikat (0) | 52 | 100,0 % |
| minus bets_uten_utfall (0) | 52 | 100,0 % |
| metrikker["antall_bets"] | 52 | — |

## Hovedtall

`manifest["headline"]` peker på `"metrikker"` (full periode).
`innbrenning_maaneder`: 3. `innbrenning_fra_dato`: `"2023-03-18"`.

| Nøkkel | metrikker (full periode) | metrikker_uten_innbrenning |
|---|---|---|
| antall_bets | 52 | 21 |
| antall_vunnet | 30 | 12 |
| roi | 15.0% | 17.9% |
| roi_ci_nedre | -11.9% | -24.1% |
| roi_ci_oevre | 42.9% | 60.3% |
| vinnrate | 57.7% | 57.1% |
| vinnrate_ci_nedre | 44.2% | 36.5% |
| vinnrate_ci_oevre | 70.1% | 75.5% |
| maks_drawdown_kroner | 80.0 | 80.0 |
| maks_drawdown_andel | 7.8% | 7.1% |
| sum_innsats | 1040.0 | 420.0 |
| sum_profitt | 156.2 | 75.2 |
| clv_snitt | 2.075% | 1.745% |
| antall_med_clv | 52 | 21 |
| antall_uten_clv | 0 | 0 |
| andel_slo_closing | 76.9% | 90.5% |
| bootstrap_seed | 42 | 42 |
| bootstrap_n_resamples | 1000 | 1000 |

`sluttsaldo`: **1156.2** kr, mot `startkapital`: **1000.0** kr.

**Manuell sjekk mot residual-metning (ikke i manifestet, beregnet separat
fra ledger.csv med `metrics.py` sine egne funksjoner):** av de 52 bets-ene
hadde 16 (30.8 %) fortsatt `modell_prob == 1.0` selv etter kalibreringsfiksen.
De 36 gjenværende "rene" bets-ene ga ROI 10.2 % (KI −27.8 % til 43.6 %),
vinnrate 52.8 %, drawdown 7.1 %, CLV 2.32 % — signalet svekkes noe men
forsvinner ikke.

## Datakvalitet og hopp

| Teller | Verdi |
|---|---|
| datoer_hoppet_over_for_lite_treningsgrunnlag | 15 |
| kamper_hoppet_over_manglende_odds | 0 |
| kamper_hoppet_over_ukjent_lag | 0 |
| kamper_uten_closing_snapshot | 0 |
| kandidater_flagget | 127 |
| kandidater_blokkert_av_skadefilter | 75 |
| skadesjekk_uten_datagrunnlag | 4 |
| kandidater_uten_kelly_edge | 0 |
| bets_hoppet_over_duplikat | 0 |
| bets_uten_utfall | 0 |
| datoer_stoppet_lav_bankroll | 0 |
| bets_uten_clv | 0 |
| retreninger | 13 |
| sluttsaldo | 1156.2 |

Varm-opp-hoppet (15 datoer / samme som alle andre kjøringer denne fasen)
er forventet, ikke et datahull — se `05-07-SUMMARY.md`.
`skadesjekk_uten_datagrunnlag` (4) er lavere enn i den løse-terskel-kjøringen
(20) fordi denne slicen har færre kandidater totalt å sjekke.

## Kelly-sweep (kjørt ved siden av, samme kjøring)

| Arm | kelly_fraksjon | flat_innsats | antall_bets | ROI | ROI 95 % KI | maks drawdown | CLV |
|---|---|---|---|---|---|---|---|
| **flat (hovedregelen som ble frosset)** | null | 20.0 | 52 | 15.0% | -11.9% – 42.9% | 7.8% | 2.075% |
| kvart | 0.25 | null | 52 | 15.8% | -11.8% – 43.1% | 47.1% | 2.075% |
| halv | 0.5 | null | 52 | 15.0% | -11.9% – 42.9% | 49.2% | 2.075% |
| full | 1.0 | null | 52 | 15.0% | -11.9% – 42.9% | 49.2% | 2.075% |

Alle fire armer plasserte de samme 52 bets (`kandidater_uten_kelly_edge`
er 0 for alle) — forskjellen mellom armene er kun stake-størrelse, ikke
hvilke bets som ble tatt. ROI er nesten identisk på tvers av armer
(CLV er identisk, siden CLV er stake-uavhengig), men **maks drawdown er
dramatisk lavere for flat (7.8 %) enn for noen Kelly-fraksjon (47-49 %)** —
dette er selve grunnen til at flat ble valgt over halv Kelly: samme
forventede avkastning, langt lavere risiko på dette lille utvalget.

## Frosne beslutninger

| ID | Parameter | Frosset verdi | Kilde | Slik overstyres den i 05-13 |
|---|---|---|---|---|
| F-05-01 | min_value_terskel | 0.20 | manifest.json konfig | `--min-value-terskel 0.20` |
| F-05-02 | min_odds | 1.5 | manifest.json konfig | `--min-odds 1.5` |
| F-05-03 | maks_odds | 2.5 | manifest.json konfig | `--maks-odds 2.5` |
| F-05-04 | staking-regel | flat (ikke Kelly) | manifest.json konfig + kjøring 4/6s sammenligning | `--flat` |
| F-05-05 | flat_innsats | 20.0 kr (2% av startkapital) | manifest.json konfig (backtest.flat_innsats_belop) | Beregnes automatisk fra `--startkapital` når `--flat` er satt, ingen egen flagg |
| F-05-06 | startkapital | 1000.0 | manifest.json konfig | `--startkapital 1000.0` (standardverdi, kan utelates) |
| F-05-07 | min_innsats | 20.0 | manifest.json konfig | — (ingen flagg; standardverdi fra config.py) |
| F-05-08 | maks_innsats | 150.0 | manifest.json konfig | — (ingen flagg; standardverdi fra config.py) |
| F-05-09 | min_treningskamper | 100 | manifest.json konfig | — (ingen flagg; standardverdi) |
| F-05-10 | kalibrer_andel | 0.15 (med D-05-05s gulv på 50 kamper) | manifest.json konfig + model.py commit 33bbae1 | — (ingen flagg; kildekode-endring, ikke en per-kjøring-parameter) |
| F-05-11 | retrenings_kadens | "maanedlig" | manifest.json konfig | — (ingen flagg) |
| F-05-12 | holdout_start_dato | "2024-10-01" | manifest.json konfig + config.py | — (ingen flagg; config.py-konstant) |
| F-05-13 | skadefilter_aktiv | true | manifest.json konfig | — (ingen flagg; PÅ er standard, `--uten-skadefilter` ville slått den av) |
| F-05-14 | bootstrap_seed | 42 | manifest.json konfig | — (ingen flagg; metrics.py-konstant) |
| F-05-15 | bootstrap_n_resamples | 1000 | manifest.json konfig | — (ingen flagg; metrics.py-konstant) |

**Ingen `config.py`-verdi ble endret.** Den frosne konfigurasjonen er
uttrykt som CLI-argumenter for plan 05-13, ikke som en endring av den
kjørende live-boten. Hvorvidt live-konfigurasjonen (`04_value_detector.py`,
`06_bot.py`) skal oppdateres til å matche, er en SEPARAT, senere beslutning
som avhenger av hva holdout-kjøringen (plan 05-13) faktisk viser.

## Hva 05-13 skal kjøre

Den EKSAKTE kommandolinjen, ordrett, som plan 05-13 skal kjøre for å bruke
opp den låste 2024-25-holdouten:

```bash
./venv/bin/python3 08_kjor_backtest.py --holdout --bekreft-holdout --min-value-terskel 0.20 --maks-odds 2.50 --flat
```

Merk: **INGEN `--sweep`** (kan ikke kombineres med `--holdout` — sweepen
finnes for å VELGE en konfigurasjon, ikke for å teste flere på holdouten).
`--fra`/`--til` utelates bevisst (holdout-veien begrenser selv sitt eget
datoområde). `--startkapital`, `--min-innsats`, `--maks-innsats`,
`--min-treningskamper` utelates fordi de allerede står på sine
frosne standardverdier (F-05-06/07/08/09) — 05-13s pre-flight skal
verifisere dette eksplisitt før kjøring, ikke anta det.

## Rå terminalutskrift (den frosne kjøringen)

```
============================================================
WALK-FORWARD BACKTEST
============================================================
Modus:                tuning
Fra:                  (tidligste dato i nba_features.csv)
Til:                  2024-09-30 (standard: dagen før holdout)
Sweep:                True
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
============================================================
BACKTEST-OPPSUMMERING
run_id:               20260828-095233-3cc4a836
type:                 tuning
katalog:              backtests/20260828-095233-3cc4a836
fra_dato:             2022-10-24
til_dato:             2024-04-14
datoer_behandlet:     303
kamper_totalt:        2302
kamper_hoppet_over_manglende_odds:  0
kandidater_flagget:                 127
kandidater_blokkert_av_skadefilter:  75
retreninger:                         13
antall_bets:          52
roi:                  15.0% (KI -11.9% – 42.9%)
vinnrate:             57.7%
maks_drawdown:        7.8%
clv_snitt:            0.020750397633784536
============================================================
manifest.json skrevet til: backtests/20260828-095233-3cc4a836/manifest.json
kelly_sweep.json skrevet til: backtests/20260828-095233-3cc4a836/kelly_sweep.json
```

## Tidligere kjøringer i denne prosessen (arkivert for sporbarhet)

Alle skrevet til `backtests/` (gitignored) i løpet av utforskningen, ingen
av dem er `type: "holdout"`:

- `20260828-092713-6fd9654f` — kjøring 1 (live-config, FØR kalibreringsfiksen)
- `20260828-093206-9fd2dcbd` — kjøring 2/3 (0.20/2.50, halv Kelly, FØR fiksen)
- `20260828-093815-3cc4a836` — kjøring 4 (0.20/2.50, flat, FØR fiksen, første `--flat`-kjøring)
- `20260828-095206-6fd9654f` — kjøring 5/8 (live-config, ETTER fiksen)
- `20260828-095233-3cc4a836` — **kjøring 6, DEN FROSNE KJØRINGEN** (0.20/2.50, flat, ETTER fiksen)
