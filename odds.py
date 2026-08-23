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

import sqlite3
from datetime import datetime


ARKIV_FIL = "odds_arkiv.db"

SPORT = "basketball_nba"
MARKED = "h2h"          # Moneyline er hele v1-scopet — ikke legg til spread/totals
REGION = "eu"            # Matcher 04_value_detector.py sin nåværende live-region,
                          # slik at backtest og live ser de samme bookmakerne


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
