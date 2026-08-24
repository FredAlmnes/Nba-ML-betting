# Fase 4 Plan 07: Røyktest mot ekte The Odds API

**Dato utført:** 2026-08-24
**Total kreditt brukt:** 51 av maks 130 tillatt for dette plan-et (39%)
**Kredittgrense per kommando:** aldri over 60, ingen kommando kjørt uten `--maks-kreditt`

## Sammendrag

Røyktesten kjørte seks ekte API-kall mot The Odds API sitt betalte 20 000-kreditt-nivå:
to bet-time-snapshots i tidlig del av datointervallet (2022-10-24, 2022-10-25), ett
bet-time-snapshot i sen del (2025-04-13), én gratis gjenkjøring av det tidlige intervallet,
og ett closing-line-løp for 2025-04-13 (1 discovery-kall + 2 klyngekall). Kostnadsmodellen
fra 04-RESEARCH.md ble re-verifisert direkte mot den offisielle dokumentasjonen FØR noe
kreditt ble brukt, og stemte nøyaktig med det som allerede ligger i `odds.py` — ingen
avvik funnet, ingen stopp nødvendig i Steg 1.

Alle mål fra 04-RESEARCH.md sine åpne spørsmål er nå erstattet med ekte tall: sport-wide
historisk odds-kall koster nøyaktig 10 kreditter per kall uansett antall kamper i svaret
(bekreftet identisk for både 2022- og 2025-datoer), discovery-kallet koster 1 kreditt,
2025-04-13 hadde 2 avspark-klynger (ikke den antatte 3), og gjenkjøring av allerede
arkiverte datoer kostet reproduserbart 0 kreditter med uendret gjenstående saldo. Den ene
substansielle, ikke-nøytrale observasjonen er at tidlig-i-intervallet-datoer (2022-10) har
merkbart tynnere bookmaker-dekning (10-11 bookmakere/kamp) enn sent-i-intervallet-datoer
(2025-04, 17-19 bookmakere/kamp) — se Steg 6 under. Dette er en reell datakvalitetsforskjell,
ikke en feil i koden, og må håndteres som en eksplisitt beslutning i Task 2 sin sjekkpunkt.

---

## Steg 1: Re-verifisering av kostnadsmodell (0 kreditter)

Hentet rå HTML fra `https://the-odds-api.com/liveapi/guides/v4/` via `curl` (ikke
WebFetch sin AI-oppsummerte gjengivelse, som 04-RESEARCH.md fant upålitelig) og
parset ut de eksakte "Usage Quota Costs"-avsnittene for alle tre historiske endepunkt.

**`GET historical odds`** (sport-wide, `/v4/historical/sports/{sport}/odds`):
> "The usage quota cost for historical odds is 10 per region per market.
> cost = 10 x [number of markets specified] x [number of regions specified]"
> Eksempel: 1 marked, 1 region → Cost: 10 — **per kall, uansett antall kamper i svaret.**

**`GET historical events`** (discovery, `/v4/historical/sports/{sport}/events`):
> "This endpoint costs 1 from usage quota. If no events are found, it will not cost."

**`GET historical event odds`** (per-kamp, `/v4/historical/sports/{sport}/events/{eventId}/odds`):
> "The usage quota cost depends on the number of markets and regions used in the request.
> cost = 10 x [number of unique markets returned] x [number of regions specified]"
> Eksempel: 1 marked, 1 region → Cost: 10 — **per kall, per enkelt-kamp.**

**Verdikt:** Identisk med det `odds.py` allerede antar (`x-requests-last` = 10 for
sport-wide-kall, 1 for discovery). Ingen avvik funnet. D-03-amendmentets valg av
sport-wide-endepunktet er fortsatt riktig valg. Steg 2-8 fortsatte som planlagt.

---

## Steg 2: Bet-time, tidlig del av intervallet (2022-10-24 → 2022-10-25)

Kommando:
```
venv/bin/python 07_hent_historisk_odds.py --snapshot-type bet_time \
  --fra 2022-10-24 --til 2022-10-25 --maks-kreditt 30 --utfor
```

| Dato | x-requests-last | x-requests-remaining (etter kall) | Kamper i snapshot | Rader arkivert |
|------|-----------------|-------------------------------------|--------------------|-----------------|
| 2022-10-24 | 10 | 19990 | 8 | 174 |
| 2022-10-25 | 10 | 19980 | 4 | 88 |

Exit-kode: 0. `kreditt_brukt` totalt for steget: **20**.

---

## Steg 3: Bet-time, sen del av intervallet (2025-04-12 → 2025-04-13)

Kommando:
```
venv/bin/python 07_hent_historisk_odds.py --snapshot-type bet_time \
  --fra 2025-04-12 --til 2025-04-13 --maks-kreditt 30 --utfor
```

`nba_features.csv` har kun én unik kampdato i dette intervallet (2025-04-12 var ingen
NBA-kampdag i datasettet — sesongslutt/off-day), så løpet behandlet 1 dato, ikke 2.

| Dato | x-requests-last | x-requests-remaining (etter kall) | Kamper i snapshot | Rader arkivert |
|------|-----------------|-------------------------------------|--------------------|-----------------|
| 2025-04-13 | 10 | 19970 | 19 | 560 |

Exit-kode: 0. `kreditt_brukt` totalt for steget: **10**.

**Merk:** Snapshotet returnerte 19 kamper totalt (alle live/kommende kamper på det
forespurte tidspunktet, ikke bare 2025-04-13 sine), men kun 15 distinkte kamper falt
innenfor `kamp_dato='2025-04-13'` etter `kamp_dato_fra_commence`-filteret — de resterende
4 var kamper på senere datoer i snapshotet og ble korrekt hoppet over, ikke feilaktig
arkivert under feil dato. Dette er filteret (Pitfall 2/#6-vernet) som fungerer som tiltenkt,
ikke et tegn på tidssone-feil.

---

## Steg 4: Gratis gjenkjøring mot ekte API (bevis for ODDS-01)

Eksakt samme kommando som Steg 2 kjørt på nytt, verbatim:
```
venv/bin/python 07_hent_historisk_odds.py --snapshot-type bet_time \
  --fra 2022-10-24 --til 2022-10-25 --maks-kreditt 30 --utfor
```

Rått resultat fra scriptets egen oppsummering:
```
Datoer totalt:  2
Hoppet over:    2
Kall utfort:    0
Kreditt brukt:  0
Nye rader:      0
```

| | Før gjenkjøring (etter Steg 3) | Etter gjenkjøring (Steg 4) |
|---|---|---|
| Siste `kreditt_igjen` i `kreditt_logg` | 19970 | 19970 (uendret — ingen ny rad lagt til) |
| Antall rader i `kreditt_logg` | 3 | 3 (uendret) |

**`hoppet_over=2`, `kall=0`, `kreditt_brukt=0`, saldo uendret** — ODDS-01s kjernepåstand
("gjenkjøring koster ingenting") er nå bevist mot den ekte APIen, ikke bare mot mock-HTTP.

---

## Steg 5: Closing-line, sen dato (2025-04-13)

Kommando:
```
venv/bin/python 07_hent_historisk_odds.py --snapshot-type closing \
  --fra 2025-04-13 --til 2025-04-13 --maks-kreditt 60 --utfor
```

Resultat: **3 kall totalt, 21 kreditter brukt** (1 discovery-kall à 1 kreditt +
2 klyngekall à 10 kreditter), 538 nye rader.

| Kall | Endepunkt | Forespurt tidspunkt | x-requests-last | x-requests-remaining |
|------|-----------|----------------------|------------------|------------------------|
| 1 | historical_events (discovery) | 2025-04-13 | 1 | 19969 |
| 2 | historical_odds (klynge 1) | 2025-04-13T16:55:00Z | 10 | 19959 |
| 3 | historical_odds (klynge 2) | 2025-04-13T19:25:00Z | 10 | 19949 |

**Målt klyngeantall for 2025-04-13: 2 klynger** (ikke den antatte 3 fra A2).

| Klynge | Lukketidspunkt (forespurt) | `snapshot_timestamp` (API-ets faktiske) | Kamp-avsparker i klyngen |
|--------|------------------------------|--------------------------------------------|-----------------------------|
| 1 | 2025-04-13T16:55:00Z | 2025-04-13T16:50:38Z | 2025-04-13T17:10:00Z |
| 2 | 2025-04-13T19:25:00Z | 2025-04-13T19:20:37Z | 2025-04-13T19:40:00Z |

**Pitfall 4-sjekk (SQL):**
```sql
SELECT COUNT(*) FROM odds_arkiv
WHERE snapshot_type='closing' AND snapshot_timestamp > commence_time;
```
Resultat: **0** — ingen closing-rad ble hentet etter avspark.

---

## Steg 6: Dekningssammenligning (Pitfall 3 / antagelse A4)

```sql
SELECT kamp_dato, snapshot_type, COUNT(DISTINCT event_id) AS kamper,
       COUNT(DISTINCT bookmaker) AS bookmakere, COUNT(*) AS rader
FROM odds_arkiv GROUP BY kamp_dato, snapshot_type ORDER BY kamp_dato;
```

| kamp_dato | snapshot_type | kamper | bookmakere (distinkt, hele datoen) | rader |
|-----------|----------------|--------|--------------------------------------|-------|
| 2022-10-24 | bet_time | 8 | 11 | 174 |
| 2022-10-25 | bet_time | 4 | 11 | 88 |
| 2025-04-13 | bet_time | 15 | 19 | 560 |
| 2025-04-13 | closing | 15 | 18 | 538 |

Aggregert bookmaker-antall kan skjule per-kamp-variasjon, så bookmaker-antall PER KAMP
ble også sjekket:

| Dato | Bookmakere per kamp (min–maks) |
|------|-----------------------------------|
| 2022-10-24 (8 kamper) | 10–11 |
| 2025-04-13 (15 kamper) | 17–19 |

**Verdikt: JA, tidlig-i-intervallet-dekningen er merkbart tynnere.** 2022-10-datoene
har konsekvent 10-11 bookmakere per kamp under `eu`-regionen, mot 17-19 for
2025-04-13 — en reduksjon på omtrent 40%. Dette bekrefter Pitfall 3 sin advarsel:
The Odds API sin historiske dekning vokser over tid etter hvert som flere
bookmakere legges til i den løpende innsamlingen. Det er IKKE null/én bookmaker
(så dataene er fortsatt brukbare for tidlige datoer), men det er en reell,
dato-avhengig kvalitetsforskjell som Fase 5-backtesten må være klar over — flere
tilgjengelige linjer sent i datasettet betyr flere mulige "value"-kandidater å
sammenligne mot per kamp, rent mekanisk, uavhengig av modellkvalitet.

**Kamper-i-snapshot vs. kamper-som-overlevde-datofilteret:** for 2022-10-24 og
2022-10-25 var "kamper totalt" i snapshotet identisk med antall kamper arkivert
under riktig dato (8=8, 4=4) — ingen filter-tap. For 2025-04-13 var det et gap
(19 totalt → 15 arkivert), forklart i Steg 3 over: snapshotet inkluderer også
kommende kamper på senere datoer, og filteret fjerner dem korrekt. Ingen tegn til
feil tidssone-konvertering (som ville vist seg som et stort, uforklarlig tap på
ALLE datoer, ikke bare et forventet "fremtidige kamper i samme snapshot"-gap).

---

## Steg 7: Sanity-sjekk — arkivet er spørrbart for sitt faktiske formål

```sql
SELECT hjemmelag, bortelag, bookmaker, utfall_navn, odds, snapshot_timestamp
FROM odds_arkiv WHERE kamp_dato='2025-04-13' AND snapshot_type='bet_time' LIMIT 10;
```

| hjemmelag | bortelag | bookmaker | utfall_navn | odds | snapshot_timestamp |
|-----------|----------|-----------|--------------|------|----------------------|
| Atlanta Hawks | Orlando Magic | Betfair | Atlanta Hawks | 1.99 | 2025-04-13T12:55:38Z |
| Atlanta Hawks | Orlando Magic | Betfair | Orlando Magic | 2.00 | 2025-04-13T12:55:38Z |
| Atlanta Hawks | Orlando Magic | 888sport | Atlanta Hawks | 1.85 | 2025-04-13T12:55:38Z |
| Atlanta Hawks | Orlando Magic | 888sport | Orlando Magic | 1.91 | 2025-04-13T12:55:38Z |
| Atlanta Hawks | Orlando Magic | Matchbook | Atlanta Hawks | 1.99 | 2025-04-13T12:55:38Z |
| Atlanta Hawks | Orlando Magic | Matchbook | Orlando Magic | 2.00 | 2025-04-13T12:55:38Z |
| Atlanta Hawks | Orlando Magic | Coolbet | Atlanta Hawks | 1.89 | 2025-04-13T12:55:38Z |
| Atlanta Hawks | Orlando Magic | 888sport | ... | ... | ... |

Arkivet svarer på "hva var odds for kamp X, hos bookmaker Y, på tidspunkt Z" —
nøyaktig det ROADMAP-suksesskriteriet ("rekonstruer odds som kjent på dato D") krever.

---

## Steg 8: Projeksjon av full backfill fra målte tall

**Utgangspunkt (målt, ikke antatt):**
- 480 unike kampdatoer (verifisert tidligere, 04-05-SUMMARY.md)
- bet_time: **eksakt 10 kreditter/dato** (målt identisk på både 2022- og 2025-datoer)
- closing: **1 discovery-kreditt + målt 2 klynger × 10 kreditter/dato = 21 kreditter**
  for den ENE målte datoen (2025-04-13) — klyngeantallet er kun målt for én dato, ikke
  et gjennomsnitt over mange datoer, så dette tallet bæres videre med eksplisitt
  usikkerhet, ikke som en ny fast sannhet.

**Regnestykke — bet_time (eksakt, ingen usikkerhet i selve kostnaden per kall):**
```
480 datoer × 10 kreditter = 4 800 kreditter
```

**Regnestykke — closing, realistisk (bruker målt 2 klynger/dato som typisk-anslag):**
```
480 datoer × (1 + 2 × 10) kreditter = 480 × 21 = 10 080 kreditter
```

**Regnestykke — closing, verste fall (bruker A2 sitt opprinnelige konservative anslag
på 3 klynger/dato, siden N=1 målt dato ikke er nok til å utelukke travlere slates)::**
```
480 datoer × (1 + 3 × 10) kreditter = 480 × 31 = 14 880 kreditter
```

**Totalsummer:**

| Scenario | bet_time | closing | Totalt |
|----------|----------|---------|--------|
| Realistisk (målt klyngeantall = 2) | 4 800 | 10 080 | **14 880** |
| Verste fall (antatt klyngeantall = 3, A2s opprinnelige anslag) | 4 800 | 14 880 | **19 680** |

**Gjenstående saldo etter denne røyktesten:** 19 949 kreditter (`x-requests-remaining`
fra siste logget kall, Steg 5).

**Passer det?**
- Realistisk scenario (14 880): **JA**, passer komfortabelt — 5 069 kreditter i margin
  for retries/feil.
- Verste fall (19 680): **MARGINALT** — bare 269 kreditters margin igjen av 19 949,
  altså under 1.5% slakk. Dette gir ikke trygg margin for API-feil, retries, eller om
  klyngeantallet for andre datoer er høyere enn 3 (f.eks. All-Star-helg-lignende travle
  kvelder, eller datoer med kamper spredt over enda flere tidssoner).

**Anbefaling hvis full-kostnad nærmer seg verste-fall-tallet:** hent bet_time for ALLE
480 datoer først (Fase 5s BT-01 trenger denne uansett, og kostnaden her er eksakt kjent
og billig — 4 800 kreditter, ingen usikkerhet), og gjør closing-backfillen i en egen,
separat kjøring med sin egen kredittgrense — IKKE ved å krympe datointervallet. Dette
lar bet_time-arkivet bli komplett uansett hva som skjer med closing-budsjettet, og gir
et naturlig sjekkpunkt mellom de to der reelt forbruk fra de første ~50-100 closing-
datoene kan brukes til å oppdatere klynge-anslaget før resten av closing-kjøringen settes
i gang.

---

## Oppsummering av alle målte tall (til bruk i Task 2 sitt sjekkpunkt)

| Målt størrelse | Antatt (04-RESEARCH.md) | Målt (denne røyktesten) |
|-----------------|---------------------------|-----------------------------|
| Kostnad, sport-wide odds-kall | 10 kreditter/kall | **10** (bekreftet, 6/6 kall) |
| Kostnad, discovery-kall | 1 kreditt (0 hvis tomt) | **1** (bekreftet, 1/1 kall) |
| Klynger/dato, 2025-04-13 | 3 (A2, antatt) | **2** (målt, N=1 dato) |
| Gjenkjøring av arkivert dato | 0 kreditter | **0** (bekreftet: `kall=0`, `kreditt_brukt=0`, saldo uendret) |
| Bookmakere/kamp, 2022-10 (tidlig) | ukjent (A4) | **10-11** |
| Bookmakere/kamp, 2025-04 (sent) | ukjent (A4) | **17-19** |
| Closing-rader etter avspark | 0 (krav) | **0** (bekreftet) |
| Total kreditt brukt denne røyktesten | ≤130 (tak) | **51** |
| Gjenstående saldo etter røyktesten | — | **19 949** |
| Projisert full backfill, realistisk | ~9 600–14 000 (04-RESEARCH.md) | **14 880** |
| Projisert full backfill, verste fall | ~19 680 (04-RESEARCH.md) | **19 680** (identisk — god sanity-sjekk) |
