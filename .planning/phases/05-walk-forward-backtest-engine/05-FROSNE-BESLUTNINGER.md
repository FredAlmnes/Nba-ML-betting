---
phase: "5"
slug: "walk-forward-backtest-engine"
type: "frosne-beslutninger"
run_id: "20260828-092713-6fd9654f"
kjoringskatalog: "backtests/20260828-092713-6fd9654f"
manifest_fil: "backtests/20260828-092713-6fd9654f/manifest.json"
ledger_fil: "backtests/20260828-092713-6fd9654f/ledger.csv"
sweep_fil: "backtests/20260828-092713-6fd9654f/kelly_sweep.json"
git_head: "a44b40804d9cb1294509183ddea24195b5e78db7"
frosset: false
frosset_dato: null
godkjent_av: null
created: 2026-08-28
---

## Kjøringen

Full invokasjon (kjørt fra repo-roten, med `venv` aktiv):

```bash
./venv/bin/python3 08_kjor_backtest.py --fra 2022-10-24 --til 2024-09-30 --sweep
```

- **run_id:** `20260828-092713-6fd9654f`
- **Kjøringskatalog:** `backtests/20260828-092713-6fd9654f/`
- **git_head:** `a44b40804d9cb1294509183ddea24195b5e78db7`
- **manifest["type"]:** `"tuning"`
- **opprettet:** `2026-08-28T09:27:13.874208`
- **Varighet:** ca. 44 sekunder (første XGBoost-advarsel logget `09:26:37`, manifestet fikk `opprettet: 09:27:13`; hele CLI-invokasjonen, inkludert Python-oppstart og pytest-preflighten som gikk rett før, ble fullført godt under ett minutt — i tråd med `<verified_data_facts>`s estimat om at 13 retreninger koster sekunder og hele prediksjonspasset 10-15 s)

`manifest["periode"]["til_dato"]` er `"2024-04-14"` (siste faktisk behandlede kampdato innenfor vinduet), som er strengt mindre enn `config.HOLDOUT_START_DATO = "2024-10-01"`. Kjøringen har dermed aldri rørt den låste 2024-25-holdouten.

## Konfigurasjonen som produserte tallene

Én rad per nøkkel i `manifest["konfig"]`, i manifestets egen rekkefølge:

| Nøkkel | Verdi i kjøringen | Live-verdi i config.py |
|---|---|---|
| min_value_terskel | 0.05 | 0.05 |
| min_odds | 1.5 | 1.50 |
| maks_odds | 4.0 | 4.00 |
| kelly_fraksjon | 0.5 | 0.5 |
| flat_innsats | null | — |
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

## Trakten

Fra kamper til plasserte bets, med absolutt antall og andel av forrige steg:

| Steg | Antall | Andel av forrige steg |
|---|---|---|
| kamper_totalt | 2 302 | 100,0 % (utgangspunkt) |
| kandidater_flagget | 1 205 | 52,3 % av kamper_totalt |
| minus kandidater_blokkert_av_skadefilter (747) | 458 | 38,0 % av kandidater_flagget |
| minus kandidater_uten_kelly_edge (0) | 458 | 100,0 % |
| minus bets_hoppet_over_duplikat (0) | 458 | 100,0 % |
| minus bets_uten_utfall (0) | 458 | 100,0 % |
| metrikker["antall_bets"] | 458 | — |

`kandidater_flagget` (1 205) ligger **langt over** det ~185-345-kandidat-båndet `<verified_data_facts>` anslo for denne skiven (avledet fra en antatt 8-15 % flagg-rate over 2 302 kamper). Ingen tolkning av hva dette betyr for strategien gis her.

## Hovedtall

`manifest["headline"]` peker på `"metrikker"` (full periode). `innbrenning_maaneder` er `3`; `innbrenning_fra_dato` er `"2023-02-02"` (datoen `metrikker_uten_innbrenning` regnes fra, etter at de tre første distinkte behandlede kalendermånedene er droppet).

| Nøkkel | metrikker (full periode) | metrikker_uten_innbrenning |
|---|---|---|
| antall_bets | 458 | 315 |
| antall_vunnet | 191 | 125 |
| roi | 1.7% | -2.1% |
| roi_ci_nedre | -10.1% | -15.8% |
| roi_ci_oevre | 12.7% | 12.2% |
| vinnrate | 41.7% | 39.7% |
| vinnrate_ci_nedre | 37.3% | 34.4% |
| vinnrate_ci_oevre | 46.3% | 45.2% |
| maks_drawdown_kroner | 3027.0 | 3027.0 |
| maks_drawdown_andel | 67.8% | 126.5% |
| sum_innsats | 64654.3 | 45452.2 |
| sum_profitt | 1110.9 | -960.9 |
| clv_snitt | 0.0001002 | -0.0010591 |
| antall_med_clv | 458 | 315 |
| antall_uten_clv | 0 | 0 |
| andel_slo_closing | 49.8% | 50.8% |
| bootstrap_seed | 42 | 42 |
| bootstrap_n_resamples | 1000 | 1000 |

`datakvalitet["sluttsaldo"]`: **2110.9** kr, mot `konfig["startkapital"]`: **1000.0** kr.

## Datakvalitet og hopp

Alle fjorten `datakvalitet`-tellere, ingen oppsummert eller utelatt:

| Teller | Verdi |
|---|---|
| datoer_hoppet_over_for_lite_treningsgrunnlag | 15 |
| kamper_hoppet_over_manglende_odds | 0 |
| kamper_hoppet_over_ukjent_lag | 0 |
| kamper_uten_closing_snapshot | 0 |
| kandidater_flagget | 1 205 |
| kandidater_blokkert_av_skadefilter | 747 |
| skadesjekk_uten_datagrunnlag | 20 |
| kandidater_uten_kelly_edge | 0 |
| bets_hoppet_over_duplikat | 0 |
| bets_uten_utfall | 0 |
| datoer_stoppet_lav_bankroll | 0 |
| bets_uten_clv | 0 |
| retreninger | 13 |
| sluttsaldo | 2110.9 |

Varm-opp-hoppet (15 datoer / 111 kamper, alle i oktober/tidlig november 2022) er forventet — ikke et datahull. Det skyldes at `min_treningskamper=100` krever et treningsgrunnlag som ikke finnes før arkivets første kamper er spilt; se `05-07-SUMMARY.md`.

Den tynnere eu-region-bookmaker-dekningen tidlig i 2022-23 (målt til 10-11 bookmakere/kamp tidlig, mot 17-19 senere i Fase 4, akseptert av utvikleren som en dokumentert avgrensning) gjelder også denne kjøringen, men er ikke separat målbar fra denne kjøringens egne tellere — den er en egenskap ved det arkiverte datagrunnlaget, ikke ved denne backtesten.

`kamper_uten_closing_snapshot` er `0` i denne kjøringen — det ene kjente gap-spillet (`2023-03-11` PHX mot SAC) traff altså ikke denne slicens faktisk behandlede kamper (eller ble ikke flagget som kandidat), og `bets_uten_clv` er også `0`, konsistent med det.

`skadesjekk_uten_datagrunnlag` er `20` (vakuøse skadesjekk-passeringer, dvs. lag uten toppspillerdata på den datoen) — disse ble IKKE blokkert av skadefilteret (skadefilteret blokkerer bare når helsevurderingen faktisk mangler for et lag som har toppspillere å vurdere; se `05-06-SUMMARY.md`), så de påvirker ikke `kandidater_blokkert_av_skadefilter`-telleren direkte, men betyr at 20 kandidat-vurderinger manglet et fullstendig datagrunnlag for skadesjekken. `datoer_stoppet_lav_bankroll` er `0` — banken ble aldri for lav til å plassere et bet i denne kjøringen.

## Kelly-sweep

Én rad per arm, i `kelly_sweep.json`s låste rekkefølge. `basis_arm` er `"halv"`, markert under.

| Arm | kelly_fraksjon | flat_innsats | antall_bets | ROI | ROI 95 % KI | maks drawdown | kandidater_uten_kelly_edge |
|---|---|---|---|---|---|---|---|
| flat | null | 20.0 | 458 | 2.0% | -9.7% – 13.2% | 27.9% | 0 |
| kvart | 0.25 | null | 458 | -1.2% | -13.7% – 11.6% | 82.9% | 0 |
| **halv (basis_arm)** | 0.5 | null | 458 | 1.7% | -10.1% – 12.7% | 67.8% | 0 |
| full | 1.0 | null | 458 | 1.8% | -10.0% – 12.7% | 68.3% | 0 |

Alle fire armer plasserte de samme 458 bets i denne kjøringen — `kandidater_uten_kelly_edge` er `0` for hver eneste arm, så ingen kandidat i denne slicen hadde en ikke-positiv Kelly-edge som fikk Kelly-armene til å hoppe over noe flat-armen tok med. Dette er en egenskap ved dataene i akkurat denne slicen, ikke ved mekanismen (se `05-09-SUMMARY.md` for det generelle tilfellet, bevist syntetisk).

`basis_arm`-radens (`"halv"`) `roi` (0.017182143883558525) og `antall_bets` (458) er **identiske** med `manifest["metrikker"]`s tilsvarende felt — verifisert ved direkte sammenligning av tallene, ikke bare stikkprøve. Sweepen og manifestet er altså enige om samme kjøring.

## Frosne beslutninger

| ID | Parameter | Frosset verdi | Kilde | Slik overstyres den i 05-13 |
|---|---|---|---|---|

Ikke frosset ennå — fylles av oppgave 2 etter utviklerens beslutning.

## Hva 05-13 skal kjøre

Ikke frosset ennå — fylles av oppgave 2 etter utviklerens beslutning.

## Rå terminalutskrift

```
============================================================
WALK-FORWARD BACKTEST
============================================================
Modus:                tuning
Fra:                  2022-10-24
Til:                  2024-09-30
Sweep:                True
Uten skadefilter:     False
Min value-terskel:    0.05
Min odds:             1.5
Maks odds:            4.0
Kelly-fraksjon:       0.5
Startkapital:         1000.0
Min treningskamper:   100
Features-fil:         nba_features.csv
Arkiv:                odds_arkiv.db
Katalog:              backtests
============================================================
============================================================
WALK-FORWARD PREDIKSJONSPASS
fra_dato: 2022-10-24
til_dato: 2024-04-14
datoer_totalt: 318
datoer_behandlet: 303
datoer_hoppet_over_for_lite_treningsgrunnlag: 15
kamper_totalt: 2302
kamper_hoppet_over_manglende_odds: 0
kamper_hoppet_over_ukjent_lag: 0
kamper_uten_closing_snapshot: 0
kandidater_flagget: 1205
kandidater_blokkert_av_skadefilter: 747
skadesjekk_uten_datagrunnlag: 20
retreninger: 13
prediksjoner: 458
min_treningskamper: 100
kalibrer_andel: 0.15
min_value_terskel: 0.05
min_odds: 1.5
maks_odds: 4.0
skadefilter_aktiv: True
============================================================
============================================================
SIMULERINGSPASS
startkapital: 1000.0
kelly_fraksjon: 0.5
flat_innsats: None
min_innsats: 20.0
maks_innsats: 150.0
kandidater_totalt: 458
bets_plassert: 458
kandidater_uten_kelly_edge: 0
bets_hoppet_over_duplikat: 0
bets_uten_utfall: 0
datoer_stoppet_lav_bankroll: 0
bets_uten_clv: 0
sluttsaldo: 2110.9000314331065
============================================================
============================================================
KELLY-SWEEP
flat: flat=20.0 bets=458 roi=2.0% maks_drawdown=27.9%
kvart: fraksjon=0.25 bets=458 roi=-1.2% maks_drawdown=82.9%
halv (basis): fraksjon=0.5 bets=458 roi=1.7% maks_drawdown=67.8%
full: fraksjon=1.0 bets=458 roi=1.8% maks_drawdown=68.3%
============================================================
============================================================
BACKTEST-OPPSUMMERING
run_id:               20260828-092713-6fd9654f
type:                 tuning
katalog:              backtests/20260828-092713-6fd9654f
fra_dato:             2022-10-24
til_dato:             2024-04-14
datoer_behandlet:     303
kamper_totalt:        2302
kamper_hoppet_over_manglende_odds:  0
kandidater_flagget:                 1205
kandidater_blokkert_av_skadefilter:  747
retreninger:                         13
antall_bets:          458
roi:                  1.7% (KI -10.1% – 12.7%)
vinnrate:             41.7%
maks_drawdown:        67.8%
clv_snitt:            0.00010023993953366159
============================================================
manifest.json skrevet til: backtests/20260828-092713-6fd9654f/manifest.json
kelly_sweep.json skrevet til: backtests/20260828-092713-6fd9654f/kelly_sweep.json
```
