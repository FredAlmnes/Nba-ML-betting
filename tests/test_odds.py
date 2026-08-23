"""
Tester for odds.py sitt SQLite-arkivlag (plan 04-01).

Dekker skjema-oppretting, eksistenssjekk før nettverkskall (D-04's faktiske
kredittsparende mekanisme), idempotent innsetting, og kredittlogg-lagring.
Ingen nettverkskall her — dette plan-et bygger kun persistenslaget.
"""

import sqlite3

import pytest

import odds


def _rad(event_id="evt-1", snapshot_type="bet_time", bookmaker="pinnacle", utfall_navn="Boston Celtics"):
    """Bygger én odds_arkiv-rad (15 felt, samme rekkefølge som SKJEMA)."""
    return (
        "basketball_nba",           # sport
        event_id,                   # event_id
        "2023-01-15",                # kamp_dato
        "Boston Celtics",           # hjemmelag
        "Miami Heat",                # bortelag
        1610612738,                  # hjemme_lag_id
        1610612748,                  # borte_lag_id
        "2023-01-15T18:00:00Z",     # commence_time
        snapshot_type,                # snapshot_type
        "2023-01-15T14:03:00Z",     # snapshot_timestamp
        bookmaker,                   # bookmaker
        "h2h",                        # marked
        utfall_navn,                  # utfall_navn
        1.85,                         # odds
        "2026-08-23T10:00:00",       # hentet_tidspunkt
    )


@pytest.fixture
def con():
    return odds.apne_arkiv(":memory:")


def test_apne_arkiv_oppretter_tabellen():
    c = odds.apne_arkiv(":memory:")
    navn = sorted(
        rad[0] for rad in c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    )
    assert "odds_arkiv" in navn
    assert "kreditt_logg" in navn


def test_er_allerede_arkivert_false_pa_tomt_arkiv(con):
    assert odds.er_allerede_arkivert(con, "2023-01-15", "bet_time") is False


def test_er_allerede_arkivert_true_etter_arkivering(con):
    odds.arkiver_odds_rader(con, [_rad()])
    assert odds.er_allerede_arkivert(con, "2023-01-15", "bet_time") is True


def test_snapshot_typer_spores_uavhengig(con):
    odds.arkiver_odds_rader(con, [_rad(snapshot_type="bet_time")])
    assert odds.er_allerede_arkivert(con, "2023-01-15", "closing") is False


def test_dobbel_insert_er_idempotent(con):
    rader = [
        _rad(event_id="evt-1", bookmaker="pinnacle", utfall_navn="Boston Celtics"),
        _rad(event_id="evt-1", bookmaker="pinnacle", utfall_navn="Miami Heat"),
    ]
    antall_forste = odds.arkiver_odds_rader(con, rader)
    antall_andre = odds.arkiver_odds_rader(con, rader)

    assert antall_forste == 2
    assert antall_andre == 0
    assert con.execute("SELECT COUNT(*) FROM odds_arkiv").fetchone()[0] == 2


def test_ugyldig_snapshot_type_gir_integrity_error(con):
    ugyldig_rad = _rad(snapshot_type="ugyldig")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            """
            INSERT INTO odds_arkiv (
                sport, event_id, kamp_dato, hjemmelag, bortelag,
                hjemme_lag_id, borte_lag_id, commence_time, snapshot_type,
                snapshot_timestamp, bookmaker, marked, utfall_navn, odds,
                hentet_tidspunkt
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            ugyldig_rad,
        )


def test_logg_kreditt_lagrer_headers_som_int(con):
    headers = {"x-requests-last": "10", "x-requests-remaining": "19990"}
    odds.logg_kreditt(con, "/v4/historical/sports/basketball_nba/odds", "2023-01-15", headers, 8)

    rad = con.execute(
        "SELECT kreditt_brukt, kreditt_igjen, antall_rader FROM kreditt_logg"
    ).fetchone()
    assert rad == (10, 19990, 8)


def test_logg_kreditt_tolererer_manglende_headers(con):
    odds.logg_kreditt(con, "/v4/historical/sports/basketball_nba/odds", "2023-01-15", {}, 0)

    rad = con.execute(
        "SELECT kreditt_brukt, kreditt_igjen FROM kreditt_logg"
    ).fetchone()
    assert rad == (None, None)
