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
Lim inn API-nøkkelen din i `04_value_detector.py` (linje med `API_NØKKEL = ...`)

```bash
python 04_value_detector.py
```
Lager filen `value_bets_idag.csv`

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
- Backtesting – test modellen historisk for å se lønnsomhet

---

⚠️ **Advarsel**: Dette er et læringsprosjekt. Ingen garanti for profitt.
Spill alltid ansvarlig.
