> ⚠️ **SUPERSEDED — ALDRI DEPLOYERT TIL PRODUKSJON**
>
> De foreslåtte verdiene i dette dokumentet (`MIN_VALUE_TERSKEL` 0.05 → 0.20, `MAX_ODDS` 4.00 → 2.50, samt en kalibreringsfaktor og et minimum-sikkerhetsfilter) ble **aldri anvendt** på `04_value_detector.py`.
>
> Koden kjører fortsatt, og kjører fortsatt i dag, de opprinnelige verdiene: `MIN_VALUE_TERSKEL = 0.05` og `MAX_ODDS = 4.00`. Kalibreringsfaktoren og sikkerhetsfilteret finnes ikke i koden i det hele tatt.
>
> Validerte erstatningsverdier skal komme fra **Fase 5** sin walk-forward-backtest, ikke fra dette dokumentet. Ikke bruk tallene under på kjørende kode.
>
> Beholdt som historisk kontekst.

---

# 🔧 NBA Betting Bot - Kalibrerings Rapport

**Dato:** April 6, 2026
**Status:** IKKE DEPLOYERT — se merknaden øverst
**Formål:** Fikse overestimering i modellen basert på debug-analyse

---

## 📊 Problem Identifisert

### Symptomer:
- Modell predikerte 61.7% win rate i gjennomsnitt
- Faktisk win rate: 11.1% (1/9 bets)
- **Avvik: 50.6 prosentpoeng** ⚠️

### Root Cause:
Modellen **OVERESTIMERER** sannsynligheter systematisk.

**Spesifikke funn:**
- Høye odds (>3.0): 0% win rate (0/3)
- Lave odds (≤3.0): 17% win rate (1/6)
- **Konklusjon:** Modellen er dårlig på underdog-bets. Bookmakers prissetter risky bets bedre enn modellen.

---

## ✅ LØSNINGER IMPLEMENTERT

### 1. **Modell-Kalibrering (×0.60)**

**Hva:**
- Alle modell-prediksjoner multipliceres med 0.60
- Kalibreringsformel: `P_justert = 0.5 + (P_rå - 0.5) × 0.60`

**Eksempel:**
```
Hvis modellen sier: 80% (0.80)
Justert blir:       0.5 + (0.80 - 0.5) × 0.60 = 0.68 (68%)

Hvis modellen sier: 60% (0.60)
Justert blir:       0.5 + (0.60 - 0.5) × 0.60 = 0.56 (56%)
```

**Effekt:** Modellens sannsynligheter blir mer konservative uten å miste prediksjonsstyrke.

---

### 2. **Strengere Value-Filter**

**Før:** `MIN_VALUE_TERSKEL = 0.05` (5% value)
**Etter:** `MIN_VALUE_TERSKEL = 0.20` (20% value)

**Logikk:** Med 9 bets og 1 vinner, trenger vi langt større edge for å være trygge.

**Effekt:** Færre bets, men høyere sikkerhet. Klassisk "quality over quantity" approach.

---

### 3. **Favoritt-Focus (Odds-Filter)**

**Før:** `MIN_ODDS = 1.50, MAX_ODDS = 4.00`
**Etter:** `MIN_ODDS = 1.50, MAX_ODDS = 2.50`

**Logikk:** Debug-analyse viste at high-odds underdog-bets har 0% win rate.

**Effekt:**
- Bare bets på relativt favoritter (odds < 2.50)
- Unngår bookmakers "sharp-prising" på outsidere

---

### 4. **Minimum Sikkerhet-Filter**

**Ny:** `MIN_SIKKERHET = 0.65` (65% minimum)

**Logikk:** Aksepterer bare bets hvor modellen er relativt sikker (over 65%).

**Effekt:**
- Filtrer bort "borderline" bets der modellen er usikker
- Fokus på høy-konfidens-prediksjoner

---

## 📈 FORVENTET EFFEKT

### Nye Parametre Oppsummert:

| Parameter | Før | Etter | Endring |
|-----------|-----|-------|---------|
| Value-terskel | 5% | 20% | +15pp |
| Max odds | 4.00 | 2.50 | -1.50 |
| Min sikkerhet | Ingen | 65% | Ny |
| Kalibrering | Ingen | ×0.60 | Ny |

### Predikert Påvirkning:

1. **Færre bets per dag**
   - Før: ~3-5 bets
   - Etter: ~0-2 bets
   - *Bedre kvalitet, mindre volum*

2. **Høyere win rate**
   - Hvis modellen er riktig kalibrert: ~50-55%
   - Hvis bookmakers er smarte: ~40-45%

3. **Bedre ROI**
   - Med 65% sikkerhet + 2.0 odds = EV: +30% per bet
   - Med 50% win rate + 2.0 odds = ROI: 0% (break-even)
   - Med 55% win rate + 2.0 odds = ROI: +10%

---

## 🧪 TEST-PLAN

### Phase 1: Monitor (7 dager)
- Kjør den nye konfigurasjonen
- Noter antall bets og win rate
- Sammenlign med gammelt format

### Phase 2: Evaluate (14 dager)
- Minimum 20-30 bets før evaluering
- Beregn faktisk ROI
- Juster kalibrerings-faktor hvis nødvendig

### Phase 3: Optimize (30+ dager)
- Hvis win rate < 45%: reduser MAX_ODDS ytterligere
- Hvis win rate > 60%: øk MIN_VALUE_TERSKEL litt
- Fine-tune kalibreringsfaktoren basert på empirisk data

---

## 📝 IMPLEMENTASJONSDETALJER

### Filer Endret:
- ✅ `04_value_detector.py`
  - Lagt til `KALIBRERING_FAKTOR = 0.60`
  - Endret `MIN_VALUE_TERSKEL` fra 0.05 til 0.20
  - Endret `MAX_ODDS` fra 4.00 til 2.50
  - Lagt til `MIN_SIKKERHET = 0.65`
  - Implementert kalibrering i prediksjons-logikk
  - Lagt til sikkerhet-filter i bet-valideringen

### Filer IKKE Endret:
- `06_bot.py` - Kjører 04_value_detector.py automatisk
- `01-03_*.py` - Retrening-pipeline uendret
- `bankroll.json`, `bets.json` - Data bevares

---

## ⚠️ VIKTIGE MERKNADER

1. **Kalibrerings-faktor (0.60) er empirisk estimat**
   - Basert på at modellen sier 61.7% men bare 11.1% vinner
   - Kan trenge justeres etter mer data

2. **Færre bets = lavere learning rate**
   - Med 0-2 bets per dag tar det lengre å samle data
   - Men høyere kvalitet bets

3. **Bookmakers er smarte**
   - Selv med optimalisering, å slå bookmakers-odds er vanskelig
   - +10% ROI på lang sikt skulle være realistisk mål

4. **Variasjon er normal**
   - 20 bets med 55% win rate kan lett se ut som 40% pga. randomness
   - Trenger 100+ bets for statistisk signifikans

---

## 🎯 NEXT STEPS

1. **Kjør bot hver dag** - Den vil nå bruke nye parametre
2. **Monitor resultater** - Noter win rate hver dag
3. **Kom tilbake 14 dager** - Analysér om endringer hjelp
4. **Fine-tune** - Juster kalibrerings-faktor basert på faktiske resultater

---

## 📞 SPØRSMÅL?

Hvis modellen fremdeles gjør det dårlig etter 30 bets, mulige årsaker:
1. Modellen trenger retrening (kjør 01-03 stegene)
2. Kalibrerings-faktor må justeres (prøv 0.50 eller 0.70)
3. Features er utdatert (sjekk datostempel i data)
4. Bookmakers er faktisk bedre enn modellen (aksepter defeat 😅)

**God lykke! 🚀**
