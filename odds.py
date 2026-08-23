"""
Delt Odds API-modul for både live-veien og Fase 5-backtesten (D-07).

Dette er den eneste modulen som skal snakke med The Odds API sitt v4-endepunkt
og med det permanente SQLite-arkivet — 04_value_detector.py sitt live-oddskall
og en fremtidig historisk-backfill-driver importerer begge herfra, slik at de
aldri kan ende opp med to forskjellige rad-skjemaer for samme data (samme
drift-risiko som feature-engineering og lag-navn-oppslag hadde før Fase 2).

SQLite-arkivet (`odds_arkiv`-tabellen) er permanent og append-only, uten TTL —
historiske odds for et allerede passert tidspunkt endrer seg aldri (D-04), så
det finnes ingen cache-utløpslogikk her. Det som faktisk sparer API-kreditter
er IKKE "INSERT OR IGNORE" (den er bare et sikkerhetsnett mot dobbel-insert) —
det er `er_allerede_arkivert()`, som MÅ kalles FØR et nettverkskall gjøres, slik
at en allerede arkivert (kamp_dato, snapshot_type)-kombinasjon aldri fører til
et nytt, betalt API-kall.

Dette plan-et (04-01) legger kun persistenslaget — ingen nettverkskode her ennå.
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from teams import finn_lag_id


ARKIV_FIL = "odds_arkiv.db"

SPORT = "basketball_nba"
MARKED = "h2h"          # Moneyline er hele v1-scopet — ikke legg til spread/totals
REGION = "eu"            # Matcher 04_value_detector.py sin nåværende live-region,
                          # slik at backtest og live ser de samme bookmakerne

BASIS_URL = "https://api.the-odds-api.com/v4"   # Eneste sted vertsnavnet star -
                                                  # alle URL-er i denne modulen
                                                  # bygges herfra (T-04-17).

RETRYBARE_STATUSER = (429, 500, 502, 503, 504)   # Transiente feil - trygt a
                                                  # prove igjen midt i et
                                                  # betalt backfill-lop.

# NBA-kampdatoer folger hjemmearenaens lokale kalenderdag (US Eastern), ikke
# UTC — en 19:30 ET-avspark er allerede neste UTC-dogn, men horer fortsatt
# til samme kveld pa hjemmearenaens kalender. En rå UTC-dato-slice ville gitt
# feil kampdato for enhver kamp som starter etter ca. kl. 19:00-20:00 UTC
# (Pitfall 2, 04-RESEARCH.md).
NBA_TIDSSONE = ZoneInfo("America/New_York")

MORGEN_UTC_TIME = 13   # 13:00 UTC = 08:00 EST / 09:00 EDT — "morgenen av kampdag"
                        # i arenaens tidssone, uansett sommertid. Dette ER
                        # operasjonaliseringen av D-01 (den historiske arkiveringen
                        # ma sporre om samme klokkeslett som live-boten faktisk kjorer
                        # pa); endrer live-botens kjoreplan seg, ma dette tallet
                        # oppdateres samtidig, ellers bryter hele backtest-premisset
                        # (antagelse A3 i 04-RESEARCH.md).


SKJEMA = """
CREATE TABLE IF NOT EXISTS odds_arkiv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sport TEXT NOT NULL,
    event_id TEXT NOT NULL,
    kamp_dato TEXT NOT NULL,                 -- join-nøkkel mot nba_features.csv sin
                                              -- GAME_DATE_HJEMME (rene YYYY-MM-DD-strenger, verifisert)
    hjemmelag TEXT NOT NULL,
    bortelag TEXT NOT NULL,
    hjemme_lag_id INTEGER,
    borte_lag_id INTEGER,
    commence_time TEXT NOT NULL,
    snapshot_type TEXT NOT NULL CHECK (snapshot_type IN ('bet_time', 'closing')),
    snapshot_timestamp TEXT NOT NULL,        -- API-ets FAKTISK returnerte "timestamp" —
                                              -- kan avvike fra forespurt dato; skal ALDRI
                                              -- overskrives med forespurt verdi (Pitfall 4)
    bookmaker TEXT NOT NULL,
    marked TEXT NOT NULL,
    utfall_navn TEXT NOT NULL,
    odds REAL NOT NULL,
    hentet_tidspunkt TEXT NOT NULL,
    UNIQUE(event_id, snapshot_type, bookmaker, marked, utfall_navn)
);

CREATE INDEX IF NOT EXISTS idx_odds_arkiv_dato_type
    ON odds_arkiv(kamp_dato, snapshot_type);

CREATE TABLE IF NOT EXISTS kreditt_logg (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tidspunkt TEXT NOT NULL,
    endepunkt TEXT NOT NULL,
    forespurt_dato TEXT,
    kreditt_brukt INTEGER,
    kreditt_igjen INTEGER,
    antall_rader INTEGER
);
"""


def apne_arkiv(sti=ARKIV_FIL):
    """Åpner (og oppretter ved behov) SQLite-arkivet. Returnerer sqlite3.Connection."""
    con = sqlite3.connect(sti)
    con.executescript(SKJEMA)
    con.commit()
    return con


def er_allerede_arkivert(con, kamp_dato, snapshot_type):
    """
    True hvis arkivet allerede har minst én rad for (kamp_dato, snapshot_type).

    Dette kalles FØR nettverkskallet gjøres — det er selve kredittsparings-
    mekanismen (D-04), ikke "INSERT OR IGNORE" i arkiver_odds_rader().
    """
    rad = con.execute(
        "SELECT 1 FROM odds_arkiv WHERE kamp_dato = ? AND snapshot_type = ? LIMIT 1",
        (kamp_dato, snapshot_type),
    ).fetchone()
    return rad is not None


def arkiver_odds_rader(con, rader):
    """
    INSERT OR IGNORE + commit. Returnerer antall NYE rader som faktisk ble lagt inn.

    Commit skjer umiddelbart per kall — dette ER gjenopptagbarheten: et avbrutt
    løp skal beholde alt som allerede er betalt for (se T-04-05).
    """
    if not rader:
        return 0

    antall_for = con.total_changes
    con.executemany(
        """
        INSERT OR IGNORE INTO odds_arkiv (
            sport, event_id, kamp_dato, hjemmelag, bortelag,
            hjemme_lag_id, borte_lag_id, commence_time, snapshot_type,
            snapshot_timestamp, bookmaker, marked, utfall_navn, odds,
            hentet_tidspunkt
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        rader,
    )
    con.commit()
    return con.total_changes - antall_for


def logg_kreditt(con, endepunkt, forespurt_dato, headers, antall_rader):
    """Logger faktisk kredittforbruk fra x-requests-last/x-requests-remaining."""

    def _til_int(verdi):
        try:
            return int(verdi)
        except (TypeError, ValueError):
            return None

    kreditt_brukt = _til_int(headers.get("x-requests-last"))
    kreditt_igjen = _til_int(headers.get("x-requests-remaining"))

    con.execute(
        """
        INSERT INTO kreditt_logg (
            tidspunkt, endepunkt, forespurt_dato, kreditt_brukt,
            kreditt_igjen, antall_rader
        ) VALUES (?,?,?,?,?,?)
        """,
        (
            datetime.now().isoformat(timespec="seconds"),
            endepunkt,
            forespurt_dato,
            kreditt_brukt,
            kreditt_igjen,
            antall_rader,
        ),
    )
    con.commit()


# ---------------------------------------------------------------------------
# HTTP-laget (plan 04-04)
#
# _utfor_kall er det ENESTE stedet i denne modulen som gjor et faktisk
# requests.get-kall - bade hent_live_odds og de to historiske funksjonene
# lenger ned gar via den, slik at retry-policy, feilhandtering og at
# API-nokkelen aldri havner i print/exception-tekst kun matte implementeres
# ett sted (T-04-15, T-04-16, T-04-18).
#
# Betalt-tier-grensen er 30 kall/sekund. Backfillens sekvensielle lokke (en
# dato om gangen, ett kall per dato) kommer aldri i naerheten av det, sa det
# trengs ingen egen klient-side rate-throttling her.
# ---------------------------------------------------------------------------


def hent_api_nokkel():
    """
    Leser ODDS_API_NOKKEL fra miljoet (via .env). sys.exit(1) hvis den mangler.

    .env-innlastingen skjer her inne, IKKE pa modulniva - odds.py importeres
    bade av tester og av 06_bot.py, og import-tidspunkt-sideeffekter er
    nettopp det denne fasen fjerner fra 04_value_detector.py (D-07).
    """
    load_dotenv()
    api_nokkel = os.environ.get("ODDS_API_NOKKEL")
    if not api_nokkel:
        print("FEIL: Miljøvariabelen ODDS_API_NOKKEL er ikke satt.")
        print("Kopier .env.example til .env og fyll inn din egen nøkkel:")
        print("  ODDS_API_NOKKEL=din-nøkkel-her")
        print("Hent en gratis nøkkel fra https://the-odds-api.com")
        sys.exit(1)  # NB: bare exit() gir exitkode 0 (=suksess) og gjemmer feilen
    return api_nokkel


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(requests.exceptions.HTTPError),
    reraise=True,
)
def _utfor_kall(url, params):
    """
    Eneste sted i modulen som kaller requests.get. Kaster aldri params videre
    til print/logg - kun url-en, siden params inneholder apiKey.

    - Status 200: returner responsen uendret.
    - Status i RETRYBARE_STATUSER (429/5xx): raise_for_status() gjor dette om
      til en requests.exceptions.HTTPError, som tenacity-dekoratoren over
      fanger opp og prover pa nytt med eksponentiell backoff (maks 4 forsok,
      2-30 sekund). Etter siste mislykkede forsok kastes feilen videre
      (reraise=True) - den skal ALDRI sluke seg selv midt i et betalt lop.
    - Alle andre statuser (401 feil nokkel, 422 ugyldige parametre, 404 osv.)
      er ikke-forbigaende - a prove pa nytt vil aldri lykkes og sloser kun
      bort tid midt i backfillen. Feiler hoyt med sys.exit(1) i stedet for a
      returnere tomt, som er umulig a skille fra "ingen kamper i dag" (T-04-18).
    """
    respons = requests.get(url, params=params)

    if respons.status_code == 200:
        return respons

    if respons.status_code in RETRYBARE_STATUSER:
        respons.raise_for_status()

    print(f"Feil fra The Odds API: {respons.status_code}")
    print(respons.text)
    sys.exit(1)  # NB: bare exit() gir exitkode 0 (=suksess) og gjemmer feilen


def hent_live_odds(api_nokkel=None, regions=REGION, markets=MARKED, sport=SPORT):
    """
    Henter dagens NBA-odds fra live-endepunktet - flyttet ut av
    04_value_detector.py (D-07), samme URL/params/konsoll-output som for.

    Region/marked/oddsformat/datoformat ma ALDRI endres uavhengig av
    hent_historisk_odds_snapshot - arkivet og live-boten ma se de samme
    bokmakerne for at backtesten skal vaere aerlig (antagelse A4).
    """
    if api_nokkel is None:
        api_nokkel = hent_api_nokkel()

    url = f"{BASIS_URL}/sports/{sport}/odds/"
    params = {
        "apiKey": api_nokkel,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
    }

    respons = _utfor_kall(url, params)
    kamper = respons.json()
    print(f"Fant {len(kamper)} NBA-kamper med odds")
    print(f"Gjenstående API-kall denne måneden: {respons.headers.get('x-requests-remaining', 'ukjent')}")
    return kamper


# Kredittmodell for de to historiske endepunktene under (04-RESEARCH.md sin
# CRITICAL FINDING, D-03-amendmentet): sport-wide odds-snapshotet koster
# 10 x markets x regions PER KALL uansett hvor mange kamper som kommer
# tilbake, sa ett kall per kampdato dekker en hel slate - derfor brukes
# ALDRI per-kamp-oddsendepunktet (10 kreditter PER KAMP, ville kostet
# ~72 760 kreditter for dette prosjektets 3 638 kamper, 3.6x budsjettet).
# Discovery-endepunktet (hent_historiske_events) koster kun 1 kreditt per
# kall (0 hvis tomt) og gir ingen odds, bare hvilke kamper som fantes og
# nar de startet - den billige forhandsvisningen som gjor at lukketidspunkt
# kan tidfestes presist (grupper_commence_tider) i stedet for a gjettes
# (Pitfall 4 / Open Question 2).


def hent_historisk_odds_snapshot(api_nokkel, dato_iso, regions=REGION, markets=MARKED, sport=SPORT):
    """
    Sport-wide historisk odds-snapshot for ett tidspunkt. Kost: 10 x markets
    x regions PER KALL, uavhengig av antall kamper i svaret (se kommentaren
    over - D-03-amendmentet og 04-RESEARCH.md sin CRITICAL FINDING).

    Returnerer (snapshot, headers) - snapshot er hele den dekodede JSON-
    kroppen (med egen 'timestamp'/'previous_timestamp'/'next_timestamp'/
    'data'), headers er responsens header-mapping. Skriver ikke til arkivet
    selv - kredittregnskap og arkivering eies av kalleren.

    En manglende 'timestamp' i body gis videre uendret her - det er
    parse_snapshot_til_rader (04-03) sitt ansvar a kaste ValueError, ikke
    hentelagets.
    """
    url = f"{BASIS_URL}/historical/sports/{sport}/odds"
    params = {
        "apiKey": api_nokkel,
        "regions": regions,
        "markets": markets,
        "oddsFormat": "decimal",
        "dateFormat": "iso",
        "date": dato_iso,
    }
    respons = _utfor_kall(url, params)
    return respons.json(), respons.headers


def hent_historiske_events(api_nokkel, dato_iso, commence_fra, commence_til, sport=SPORT):
    """
    Historisk event-discovery: hvilke kamper fantes pa et tidspunkt og nar de
    starter, uten odds. Kost: 1 kreditt per kall, 0 hvis svaret er tomt.

    Returnerer (svar, headers). Svaret er en liste av
    {id, home_team, away_team, commence_time} per kamp - ingen regions/
    markets-parametre, discovery-endepunktet tar ikke imot dem. commence_time
    -verdiene mates inn i grupper_commence_tider (04-03) for a tidfeste
    closing-snapshots presist i stedet for a gjette (Pitfall 4).
    """
    url = f"{BASIS_URL}/historical/sports/{sport}/events"
    params = {
        "apiKey": api_nokkel,
        "date": dato_iso,
        "commenceTimeFrom": commence_fra,
        "commenceTimeTo": commence_til,
    }
    respons = _utfor_kall(url, params)
    return respons.json(), respons.headers


def _parse_iso(tidspunkt):
    """
    Parser en ISO8601-streng med trailing 'Z' til en aware datetime.

    `datetime.fromisoformat` godtar 'Z' direkte fra Python 3.11, men vi
    normaliserer eksplisitt uansett — funksjonen skal ikke stille avhenge
    av hvilken tolkeversjon den kjores under.
    """
    if isinstance(tidspunkt, datetime):
        return tidspunkt
    return datetime.fromisoformat(tidspunkt.replace("Z", "+00:00"))


def kamp_dato_fra_commence(commence_time):
    """
    "2023-01-16T00:30:00Z" -> "2023-01-15".

    Konverterer API-ets UTC commence_time til NBA-kampdagens kalenderdato i
    US Eastern (se NBA_TIDSSONE-docstringen over) — ikke en rå UTC-dato-slice.
    """
    return _parse_iso(commence_time).astimezone(NBA_TIDSSONE).date().isoformat()


def morgen_tidspunkt(kamp_dato):
    """
    "2023-01-15" -> "2023-01-15T13:00:00Z".

    13:00 UTC er 08:00 EST / 09:00 EDT, altsa morgenen av kampdag i arenaens
    tidssone og for enhver NBA-avspark. Se MORGEN_UTC_TIME-docstringen over
    for hvorfor dette tallet ikke ma endres uten a sjekke live-botens
    faktiske kjoreplan.
    """
    return f"{kamp_dato}T{MORGEN_UTC_TIME:02d}:00:00Z"


def snap_til_5min(tidspunkt):
    """
    Runder NED til narmeste 5-minutters-rutenett, sekunder/mikrosekunder nullstilt.

    Runder aldri opp — a runde opp kan skyve et "closing"-snapshot forbi
    avspark, som er nettopp Pitfall 4 (04-RESEARCH.md).
    """
    dt = _parse_iso(tidspunkt)
    avrundet_minutt = (dt.minute // 5) * 5
    dt = dt.replace(minute=avrundet_minutt, second=0, microsecond=0)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def grupper_commence_tider(events, maks_gap_minutter=60):
    """
    Grupperer commence_time-tidspunkt i klynger av tett-i-tid avsparker.

    NBA-slates spenner ofte over 3+ timer med avsparker pa én dato, sa ett
    enkelt lukketidspunkt per dato kan ikke vare "rett for avspark" for alle
    kampene (Pitfall 4). Godtar bade en liste med commence_time-strenger og
    en liste med event-dicter (slik discovery-endepunktet returnerer dem).

    Returnerer en liste av lister med de originale ISO-strengene.
    """
    if not events:
        return []

    tider = [
        e["commence_time"] if isinstance(e, dict) else e
        for e in events
    ]
    unike_sorterte = sorted(set(tider), key=lambda t: _parse_iso(t))

    klynger = [[unike_sorterte[0]]]
    for tid in unike_sorterte[1:]:
        klynge_start = _parse_iso(klynger[-1][0])
        gap_minutter = (_parse_iso(tid) - klynge_start).total_seconds() / 60
        if gap_minutter > maks_gap_minutter:
            klynger.append([tid])
        else:
            klynger[-1].append(tid)
    return klynger


def lukketidspunkt(klynge, minutter_for=15):
    """
    Lukketidspunkt for en klynge avsparker: `minutter_for` minutter for den
    tidligste avsparken i klyngen, avrundet ned til 5-minutters-rutenettet.
    """
    tidligste = min(klynge, key=lambda t: _parse_iso(t))
    forskjøvet = _parse_iso(tidligste) - timedelta(minutes=minutter_for)
    return snap_til_5min(forskjøvet)


def parse_snapshot_til_rader(snapshot, kamp_dato, snapshot_type, hentet_tidspunkt=None):
    """
    Konverterer en sport-wide historisk odds-respons til en liste av
    arkivrader (samme 15-felts rekkefolge som SKJEMA/arkiver_odds_rader).

    `snapshot` er hele den dekodede JSON-kroppen (med `timestamp`/
    `previous_timestamp`/`next_timestamp`/`data`). `kamp_dato` er NBA-
    kampdatoen dette kallet ble gjort for. `snapshot_type` er "bet_time"
    eller "closing".

    Kamper hvis commence_time hoerer til en annen NBA-kampdato enn
    `kamp_dato` droppes helt — de blir ALDRI ombenevnt til forespurt dato
    (ARCHITECTURE.md Pitfall #6: et snapshot tatt for dato D er kun
    aerlig bevis om dato D sine kamper).

    Lag som teams.finn_lag_id() ikke kan lose beholder likevel raden sin,
    med None i *_lag_id-kolonnen og det rå navnet bevart — å droppe kampen
    stille ville skapt et usynlig hull i arkivet (T-04-14).
    """
    snapshot_timestamp = snapshot.get("timestamp")
    if not snapshot_timestamp:
        raise ValueError(
            "Snapshot mangler egen 'timestamp' — kan ikke arkiveres aerlig "
            "uten å vite hvilket tidspunkt oddsene faktisk gjelder for"
        )

    if hentet_tidspunkt is None:
        hentet_tidspunkt = datetime.now().isoformat(timespec="seconds")

    rader = []
    for kamp in snapshot.get("data", []):
        spill_dato = kamp_dato_fra_commence(kamp["commence_time"])
        if spill_dato != kamp_dato:
            continue

        hjemme_navn = kamp["home_team"]
        borte_navn = kamp["away_team"]
        hjemme_lag_id = finn_lag_id(hjemme_navn)
        borte_lag_id = finn_lag_id(borte_navn)

        for bookmaker in kamp.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market.get("key") != MARKED:
                    continue
                for outcome in market.get("outcomes", []):
                    rader.append((
                        SPORT,
                        kamp["id"],
                        kamp_dato,
                        hjemme_navn,
                        borte_navn,
                        hjemme_lag_id,
                        borte_lag_id,
                        kamp["commence_time"],
                        snapshot_type,
                        snapshot_timestamp,
                        bookmaker.get("title", bookmaker.get("key")),
                        MARKED,
                        outcome["name"],
                        float(outcome["price"]),
                        hentet_tidspunkt,
                    ))

    return rader
