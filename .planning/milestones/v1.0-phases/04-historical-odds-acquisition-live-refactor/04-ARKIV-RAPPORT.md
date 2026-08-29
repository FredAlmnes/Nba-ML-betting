# Fase 4 Plan 9: Historisk odds-arkiv — dekning, kostnad og hull

*Skrevet: 2026-08-24. Alle tall under er hentet direkte fra `odds_arkiv.db` og `kreditt_logg` via de spørringene som star ved siden av hvert resultat — ingen tall er anslatt eller interpolert.*

## 1. Sammendrag

Arkivet dekker nå **alle 480 unike kampdatoer** (2022-10-24 til 2025-04-13) for **begge** snapshot-typer: `bet_time` (odds klokken 13:00 UTC kampdagens morgen) og `closing` (odds ~15 minutter før avspark, gruppert per avspark-klynge). Totalt er **17 710 kreditter** brukt denne fasen (smoke-test + full backfill), og **2 289 kreditter** står igjen på kontoen. **ODDS-01 er fullt oppfylt** — begge de to sannhetene kravet stiller ("bet-time odds arkivert for datoene budsjettet dekker" og "closing-line odds arkivert for datoene budsjettet dekker") er nå 480/480, ikke delvis.

Underveis i denne kjøringen ble to reelle avvik funnet og håndtert eksplisitt, begge dokumentert i detalj i `04-09-SUMMARY.md`:

1. Et forbigående DNS-utfall på maskinen stoppet den første `bet_time`-kjøringen etter 340 av 480 datoer (ingen kreditter gikk tapt — hver dato som feiler pga. nettverksfeil blir aldri fakturert, siden kallet aldri når fram). En identisk gjenkjøring hentet resten gratis for allerede-arkiverte datoer og betalt for de resterende 140.
2. Et ekte, sjeldent datakvalitetsproblem i selve `closing`-logikken: for 2 av 3 645 arkiverte kamper (0,055 %) returnerte The Odds API et snapshot hvis eget `timestamp`-felt lå ETTER kampens avspark — dvs. en pris tatt midt i (eller etter) kampen, ikke en ekte closing-linje. Dette ble oppdaget av denne plan-ens egen automatiserte sjekk (`snapshot_timestamp > commence_time` skal alltid være 0 rader), rettet i `odds.py` sin `parse_snapshot_til_rader` (dropper nå slike kamper istedenfor å arkivere dem — ARCHITECTURE.md Pitfall #6 / T-04-44), de 38 allerede-innsatte radene ble slettet fra arkivet, og de 2 kampene er navngitt eksplisitt som et hull i seksjon 4 under. Se `04-09-SUMMARY.md` for full rot-årsak-analyse og kode-diffen.

## 2. Dekning per snapshot-type

Spørring:
```sql
SELECT snapshot_type, COUNT(DISTINCT kamp_dato) AS datoer, COUNT(DISTINCT event_id) AS kamper, COUNT(*) AS rader
FROM odds_arkiv GROUP BY snapshot_type;
```

| snapshot_type | datoer (mål: 480) | kamper (mål: 3 638†) | rader |
|---|---|---|---|
| `bet_time` | **480** | 3 650 | 93 522 |
| `closing` | **480** | 3 643 | 93 854 |

† Målet på 3 638 kamper kommer fra `nba_features.csv` (02_feature_engineering.py sin box-score-baserte kamptelling). Arkivets egen `event_id`-telling (fra The Odds API sitt eget datasett) er noe høyere fordi Odds API-et sporer et par kamper `nba_features.csv` ikke har (se seksjon 4 for eksakt kryssreferanse mot `nba_features.csv`, som er den autoritative kilden for Fase 5).

Ingen manglende datoer for noen av de to snapshot-typene — se seksjon 3.

## 3. Manglende datoer

Spørring (kjørt for begge `snapshot_type`):
```python
import odds, sqlite3
con = sqlite3.connect("odds_arkiv.db")
maal = set(odds.hent_unike_kampdatoer())
arkivert = {r[0] for r in con.execute(
    "SELECT DISTINCT kamp_dato FROM odds_arkiv WHERE snapshot_type=?", (snapshot_type,)
)}
mangler = sorted(maal - arkivert)
```

**Resultat: 0 manglende datoer for `bet_time`. 0 manglende datoer for `closing`.**

Alle 480 datoer i `nba_features.csv` sin `GAME_DATE_HJEMME`-kolonne har minst én arkivert rad for begge snapshot-typer. Det finnes ingen dato Fase 5 må ekskludere på dato-nivå.

## 4. Kamper uten arkiverte odds

Kryssreferanse mellom `nba_features.csv` (3 638 kamper, med `TEAM_ABBREVIATION_HJEMME`/`_BORTE` løst til `hjemme_id`/`borte_id` via `teams.finn_lag_id`) og arkivets `(kamp_dato, hjemme_lag_id, borte_lag_id)`-nøkkel:

| snapshot_type | matchet mot arkiv | ingen matchende event_id | lag_id er NULL i arkivet |
|---|---|---|---|
| `bet_time` | **3 638 / 3 638** | 0 | 0 |
| `closing` | **3 636 / 3 638** | **2** | 0 |

**De to `closing`-hullene er navngitt eksplisitt** (samme to kamper nevnt i seksjon 1, punkt 2 — droppet av korrigeringen i `parse_snapshot_til_rader`, ikke stille manglet):

| Dato | Kamp | commence_time | Årsak |
|---|---|---|---|
| 2023-03-11 | Phoenix Suns @ Sacramento Kings | 2023-03-12T02:10:00Z | API returnerte closing-snapshot med egen timestamp 2023-03-12T02:50:38Z — 40 min ETTER avspark. Droppet per Pitfall #6 (aldri arkiver en erstatnings-pris som om den var closing). |
| 2025-01-09 | Dallas Mavericks @ Portland Trail Blazers | 2025-01-10T00:40:00Z | Samme mønster: snapshot-timestamp 2025-01-10T01:20:38Z, 40 min etter avspark. Droppet av samme grunn. |

Ingen `lag_id IS NULL`-tilfeller i noen av de to snapshot-typene — alle lagnavn The Odds API returnerte ble løst av `teams.finn_lag_id()` uten unntak, så det finnes ingen "ukjent lagnavn"-kategori å rapportere denne gangen (T-04-14 sin beskyttelse ble ikke utløst i praksis).

**Fase 5 sin backtest må derfor hoppe over closing-linjen (kun closing — bet_time og selve kampresultatet er upåvirket) for nøyaktig disse to kampene**, eller behandle dem som manglende CLV-datapunkt.

## 5. Bookmaker-dekning over tid

Spørring:
```sql
SELECT substr(kamp_dato,1,7) AS maaned, COUNT(DISTINCT bookmaker) AS bookmakere, COUNT(DISTINCT event_id) AS kamper
FROM odds_arkiv WHERE snapshot_type='bet_time' GROUP BY maaned ORDER BY maaned;
```

| Måned | Bookmakere | Kamper |
|---|---|---|
| 2022-10 | 11 | 59 |
| 2022-11 | 12 | 222 |
| 2022-12 | 11 | 222 |
| 2023-01 | 10 | 222 |
| 2023-02 | 11 | 164 |
| 2023-03 | 11 | 229 |
| 2023-04 | 11 | 70 |
| 2023-10 | 13 | 54 |
| 2023-11 | 13 | 219 |
| 2023-12 | 13 | 207 |
| 2024-01 | 13 | 232 |
| 2024-02 | 12 | 174 |
| 2024-03 | 12 | 230 |
| 2024-04 | 14 | 115 |
| 2024-10 | 18 | 71 |
| 2024-11 | 18 | 222 |
| 2024-12 | 18 | 189 |
| 2025-01 | 17 | 230 |
| 2025-02 | 20 | 176 |
| 2025-03 | 20 | 238 |
| 2025-04 | 19 | 105 |

**Verdikt: JA, tidligere-sesong-dekningen er systematisk tynnere.** 2022-10-sesongstart har 10-11 distinkte bookmakere per kamp under `eu`-regionen, som vokser jevnt til 17-20 bookmakere per kamp i 2024-25-sesongen — en nesten dobling. Dette bekrefter `04-SMOKETEST.md` sin målte observasjon (10-11 tidlig vs. 17-19 sent) over hele datosettet, ikke bare de to smoke-test-datoene. Dette er en ekte, dato-korrelert egenskap ved The Odds API sin egen historiske dekning (flere bookmakere ble sporet av API-et etter hvert som tiden gikk), IKKE en feil i denne backfillen — utviklerens beslutning fra plan 04-07 var å akseptere dette som et dokumentert forbehold, ikke legge til et `us`-region-fallback-kall.

## 6. Kredittregnskap

Spørring:
```sql
SELECT endepunkt, COUNT(*), SUM(kreditt_brukt) FROM kreditt_logg GROUP BY endepunkt;
```

| Endepunkt | Antall kall | Kreditter brukt |
|---|---|---|
| `historical_events` (discovery, closing-passets forhåndsvisning) | 480 | 480 |
| `historical_odds` (sport-wide odds-snapshot, begge typer) | 1 723 | 17 230 |
| **Totalt** | **2 203** | **17 710** |

`SELECT kreditt_igjen FROM kreditt_logg ORDER BY id DESC LIMIT 1` → **2 289 kreditter gjenstår** på kontoen ved slutten av denne fasen.

Fordelt på fase-aktivitet: 51 kreditter fra 04-07 sin smoke-test, 4 770 kreditter fra `bet_time`-hovedkjøringen (340+140 datoer fordelt over to prosess-kjøringer pga. DNS-utfallet), 12 889 kreditter fra `closing`-hovedkjøringen. Ingen kredittgrense (`avbrutt_grunn`) ble noensinne truffet — begge pass fullførte alle 480 datoer innenfor sine respektive godkjente tak (`bet_time` 5 500, `closing` 13 500).

## 7. Rekonstruksjonsbevis

Tilfeldig valgt arkivert dato: **2024-01-15**. Spørring, kjørt uten nettverkstilgang, kun mot den lokale SQLite-filen:

```sql
SELECT hjemmelag, bortelag, bookmaker, utfall_navn, odds, snapshot_timestamp
FROM odds_arkiv WHERE kamp_dato = '2024-01-15' AND snapshot_type = 'bet_time'
ORDER BY hjemmelag, bookmaker;
```

Faktisk output (utdrag, 278 rader totalt for denne datoen):

```
('Atlanta Hawks', 'San Antonio Spurs', '888sport', 'Atlanta Hawks', 1.3, '2024-01-15T12:55:39Z')
('Atlanta Hawks', 'San Antonio Spurs', '888sport', 'San Antonio Spurs', 3.55, '2024-01-15T12:55:39Z')
('Atlanta Hawks', 'San Antonio Spurs', 'BetOnline.ag', 'Atlanta Hawks', 1.32, '2024-01-15T12:55:39Z')
('Atlanta Hawks', 'San Antonio Spurs', 'BetOnline.ag', 'San Antonio Spurs', 3.65, '2024-01-15T12:55:39Z')
('Atlanta Hawks', 'San Antonio Spurs', 'Betfair', 'Atlanta Hawks', 1.35, '2024-01-15T12:55:39Z')
('Atlanta Hawks', 'San Antonio Spurs', 'Betfair', 'San Antonio Spurs', 3.7, '2024-01-15T12:55:39Z')
```

Alle 278 rader deler samme `snapshot_timestamp` (2024-01-15T12:55:39Z — ~5 minutter etter det forespurte 13:00 UTC-tidspunktet, API-ets nærmeste tilgjengelige snapshot), og er lest 100 % fra disk uten et eneste live API-kall. Dette er selve beviset ROADMAP-suksesskriterium 3 krever: Fase 5 kan spørre "hvilke odds var kjent morgenen av dato D" for enhver arkivert dato, helt offline.

## 8. Kjente forbehold for Fase 5

- **13:00 UTC-konvensjonen (D-01, A3):** `bet_time`-arkivet representerer odds slik de var klokken 13:00 UTC (08:00 EST / 09:00 EDT) samme kampdag. Dette MÅ matche det faktiske klokkeslettet live-boten kjører på (`06_bot.py`) for at backtesten skal være ærlig sammenlignbar med reell drift. Endrer live-botens kjøreplan seg, blir denne arkiverte antagelsen ugyldig og backtesten må re-arkiveres.
- **Dato-avhengig bookmaker-skjevhet (seksjon 5):** tidlig i datosettet (2022-10 til ~2023-04) er det systematisk færre bookmakere (10-13) enn sent i datosettet (2024-10 til 2025-04, 17-20). Enhver dato-korrelert mønster i backtestens resultater (f.eks. "strategien presterer bedre i april enn i oktober") må vurderes mot denne skjevheten før den tolkes som et reelt sesongmønster.
- **Manglende datoer:** ingen — 480/480 for begge snapshot-typer (seksjon 3).
- **Manglende closing-linjer for 2 spesifikke kamper** (seksjon 4): Phoenix Suns @ Sacramento Kings (2023-03-11) og Dallas Mavericks @ Portland Trail Blazers (2025-01-09) har `bet_time`-odds men INGEN `closing`-odds — API-et returnerte kun en post-avspark-pris for disse to, som ble bevisst forkastet. BT-06 sin CLV-beregning kan ikke kjøres for disse to kampene; alle andre 3 636 kamper har komplett closing-dekning.
- **eu-region-only, ikke us-fallback:** både `bet_time` og `closing` er hentet utelukkende fra `eu`-regionen (samme region som `04_value_detector.py` sitt live-kall), en bevisst beslutning fra plan 04-07 for å holde live og backtest konsistente — det finnes bookmakere i andre regioner (særlig `us`) som ikke er representert her.
- **`closing`-korreksjonens fåtallighet:** 2 av 3 645 opprinnelig arkiverte closing-kamper (0,055 %) ble forkastet av korrigeringen beskrevet i seksjon 1/4. Dette er lavt nok til at det ikke er en systemisk closing-tidsberegningsfeil, men Fase 5 bør vite at `parse_snapshot_til_rader` nå aktivt filtrerer bort closing-snapshots som viser seg å ha blitt tatt etter avspark, istedenfor å arkivere dem som om de var ekte closing-priser.
- **BT-06/CLV-datagrunnlaget er komplett** for praktiske formål: 480/480 datoer, 3 636/3 638 kamper har både bet_time og closing arkivert.
