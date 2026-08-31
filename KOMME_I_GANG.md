# NBA Betting Model – Komme i gang

## Hva er dette?

Et maskinlæringsprosjekt som:
1. Henter historiske NBA-kampdata
2. Trener en XGBoost-modell til å spå vinnersannsynlighet
3. Sammenligner modellens odds med bookmaker-odds
4. Flagger "value bets" – kamper der modellen mener bookmaker tar feil

---

## Installasjon

Åpne terminal i denne mappen og kjør:

```bash
pip install -r requirements.txt
```

---

## Kjør i rekkefølge

### Steg 1: Hent data (tar 3–5 min)
```bash
python 01_hent_data.py
```
Lager filen `nba_kamper_raw.csv`

### Steg 2: Lag features
```bash
python 02_feature_engineering.py
```
Lager filen `nba_features.csv`

### Steg 3: Tren modellen
```bash
python 03_tren_modell.py
```
Lager filen `nba_modell.pkl`

### Steg 4: Finn value bets
Gå til https://the-odds-api.com og lag en gratis konto.
Kopier `.env.example` til `.env` og legg nøkkelen din i `ODDS_API_NOKKEL`-linjen:

```
ODDS_API_NOKKEL=din-nøkkel-her
```

`.env` er git-ignorert og må aldri committes.

```bash
python 04_value_detector.py
```
Lager filen `value_bets_idag.csv`

### Steg 8: Kjør backtesten

**Forutsetninger:** `08_kjor_backtest.py` leser tre filer: `nba_features.csv` (steg 2),
`odds_arkiv.db` (`07_hent_historisk_odds.py`) og `nba_spillerlogg_raw.csv`
(`spillerlogg.py`). Stegene 5-7 (odds-arkivering, spillerlogg-henting,
skadefilter-integrasjon) er ikke skrevet opp i denne guiden ennå — mangler du
en av de tre filene er det et hull i denne dokumentasjonen, ikke en ødelagt
installasjon.

```bash
python 08_kjor_backtest.py
```
Lager filen `backtests/<run_id>/manifest.json` og `backtests/<run_id>/ledger.csv`.
Uten `--fra`/`--til` kjører den hele train/calibrate-slicen — fra første dato
i `nba_features.csv` til og med **dagen før** holdout-sesongen starter — og
den rører derfor aldri 2024-25-sesongen. Det fulle løpet tar noen minutter
fordi modellen gjenoppretrenes én gang per måned; bruk det avgrensede vinduet
under for billig iterasjon mens du prøver en endring.

```bash
python 08_kjor_backtest.py --sweep
```
Kjører det samme, og skriver i tillegg `kelly_sweep.json` med flat/kvart/halv/
full-Kelly-sammenligningen fra samme predict-pass.

```bash
python 08_kjor_backtest.py --fra 2022-11-15 --til 2022-11-30
```
Dette er den billige måten å prøve en endring på før du forplikter deg til
det fulle train/calibrate-løpet over.

⚠️ **Advarsel om holdouten**: 2024-25-sesongen er en LÅST holdout. Den
sjekkes **nøyaktig én gang** for hele prosjektet, etter at hver terskel- og
Kelly-beslutning allerede er frosset. Den nås kun ved å gi både `--holdout`
og bekreftelsesflagget som heter bekreft-holdout. Det finnes ingen måte å
bruke den opp på nytt — en andre kjøring ville ikke lenger vært en ærlig
out-of-sample-test. `run_id`-en fra den kjøringen må skrives inn i
`.planning/STATE.md` slik at en senere økt ser at holdouten er brukt.

---

## Daglig kjøring (launchd)

`run_daglig.sh` er wrapper-skriptet som kjører boten daglig. Det bytter til
prosjektmappen, bruker `./venv/bin/python3` (ikke system-Python), kjører
`06_bot.py`, og logger hver kjøring til `logs/run_daglig.log` med et
tidsstempel per kjøring.

Skriptet er ment å startes automatisk av en launchd-jobb i
`~/Library/LaunchAgents/` kl. 14:00 lokal tid — dette er den normale måten å
bruke boten på, ikke å kjøre `06_bot.py` for hånd hver dag. Du kan likevel
kjøre `./run_daglig.sh` manuelt når som helst for å teste oppsettet.

`logs/` er git-ignorert.

---

## Hva betyr resultatene?

- **Modell %** – vår modells estimerte sannsynlighet for seier
- **Bookmaker %** – bookmakerens implisitte sannsynlighet (utregnet fra odds)
- **Value** – differansen. Positivt = vi tror det er mer sannsynlig enn bookmaker
- **Forv. EV** – forventet verdi per krone. Positivt = lønnsomt bet på sikt (i teorien)

---

## Viktige konsepter å forstå

**Data leakage** – Vi bruker `shift(1)` i feature engineering for å sikre at
modellen aldri ser informasjon fra kampen den prøver å spå.

**Tidsserie-split** – Vi tester alltid på nyere data enn treningsdataene.
Aldri bland fremtid og fortid!

**Value betting** – Handler ikke om å vinne flest bets, men om å finne bets
der odds er høyere enn "riktig" sannsynlighet tilsier. Over mange bets
vil positiv forventet verdi gi profitt.

---

## Neste steg for å forbedre modellen

- Legg til skadedata (spillere som mangler)
- Legg til "back-to-back"-faktor (spiller de kamp 2 dager på rad?)
- Legg til hviledag-statistikk
- Bruk Kelly Criterion for å beregne optimal innsatsstørrelse
- Backtesting – implementert, se Steg 8 over

---

⚠️ **Advarsel**: Dette er et læringsprosjekt. Ingen garanti for profitt.
Spill alltid ansvarlig.
