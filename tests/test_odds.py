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


# --- Tidsstempel-logikk (plan 04-03): morgen-of-game-day, Eastern kampdato, ---
# --- 5-minutters-rutenett og lukketidspunkt. Alt offline, ingen datetime.now(). ---


def test_morgen_tidspunkt_returnerer_1300_utc():
    assert odds.morgen_tidspunkt("2023-01-15") == "2023-01-15T13:00:00Z"


def test_kamp_dato_fra_commence_kveldskamp_krysser_utc_dogn():
    # 19:30 ET tipoff er allerede neste UTC-dogn, men horer til 15.'s NBA-slate
    assert odds.kamp_dato_fra_commence("2023-01-16T00:30:00Z") == "2023-01-15"


def test_kamp_dato_fra_commence_ettermiddagskamp_samme_utc_dogn():
    assert odds.kamp_dato_fra_commence("2023-01-15T20:00:00Z") == "2023-01-15"


def test_kamp_dato_fra_commence_handterer_sommertid_dst():
    # EDT (UTC-4) om sommeren, ikke en hardkodet -5-offset
    assert odds.kamp_dato_fra_commence("2023-07-04T23:00:00Z") == "2023-07-04"


def test_snap_til_5min_runder_ned_aldri_opp():
    assert odds.snap_til_5min("2023-01-16T00:17:43Z") == "2023-01-16T00:15:00Z"


def test_grupper_commence_tider_grupperer_naerliggende_tidspunkt():
    tider = [
        "2023-01-16T00:00:00Z",
        "2023-01-16T00:30:00Z",
        "2023-01-16T03:00:00Z",
    ]
    klynger = odds.grupper_commence_tider(tider)
    assert klynger == [
        ["2023-01-16T00:00:00Z", "2023-01-16T00:30:00Z"],
        ["2023-01-16T03:00:00Z"],
    ]


def test_grupper_commence_tider_tom_liste():
    assert odds.grupper_commence_tider([]) == []


def test_grupper_commence_tider_godtar_event_dicter():
    events = [
        {"commence_time": "2023-01-16T00:00:00Z"},
        {"commence_time": "2023-01-16T00:30:00Z"},
    ]
    klynger = odds.grupper_commence_tider(events)
    assert klynger == [["2023-01-16T00:00:00Z", "2023-01-16T00:30:00Z"]]


def test_lukketidspunkt_15min_for_tidligste_tipoff_paa_5min_rutenett():
    klynge = ["2023-01-16T00:30:00Z", "2023-01-16T01:00:00Z"]
    assert odds.lukketidspunkt(klynge) == "2023-01-16T00:15:00Z"


# --- parse_snapshot_til_rader (plan 04-03): sport-wide respons -> arkivrader ---
# --- via teams.finn_lag_id. Ingen live API-kall, alt bygges som inline fixtures. ---


def _snapshot(data, timestamp="2023-01-15T12:55:33Z"):
    return {
        "timestamp": timestamp,
        "previous_timestamp": "2023-01-15T12:50:31Z",
        "next_timestamp": "2023-01-15T13:00:34Z",
        "data": data,
    }


def _kamp(
    event_id="e912304de2b2ce35b473ce2ecd3d1502",
    commence_time="2023-01-16T00:30:00Z",
    home_team="Miami Heat",
    away_team="Toronto Raptors",
    bookmakers=None,
):
    if bookmakers is None:
        bookmakers = [
            {
                "key": "unibet",
                "title": "Unibet",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": home_team, "price": 1.75},
                            {"name": away_team, "price": 2.20},
                        ],
                    }
                ],
            }
        ]
    return {
        "id": event_id,
        "sport_key": "basketball_nba",
        "commence_time": commence_time,
        "home_team": home_team,
        "away_team": away_team,
        "bookmakers": bookmakers,
    }


def test_snapshot_matcher_bruker_teams_py():
    snapshot = _snapshot([_kamp()])
    rader = odds.parse_snapshot_til_rader(snapshot, "2023-01-15", "bet_time", hentet_tidspunkt="2026-08-23T12:00:00")

    assert len(rader) == 2
    for rad in rader:
        assert len(rad) == 15
    hjemme_lag_id_kolonne = 5
    borte_lag_id_kolonne = 6
    assert all(rad[hjemme_lag_id_kolonne] == 1610612748 for rad in rader)   # Miami Heat
    assert all(rad[borte_lag_id_kolonne] == 1610612761 for rad in rader)    # Toronto Raptors


def test_snapshot_timestamp_er_alltid_apiets_egen_verdi():
    snapshot = _snapshot([_kamp()], timestamp="2023-01-15T12:55:33Z")
    rader = odds.parse_snapshot_til_rader(snapshot, "2023-01-15", "bet_time", hentet_tidspunkt="2026-08-23T12:00:00")

    snapshot_timestamp_kolonne = 9
    assert all(rad[snapshot_timestamp_kolonne] == "2023-01-15T12:55:33Z" for rad in rader)


def test_kamp_utenfor_forespurt_dato_droppes_ikke_ombenevnes():
    riktig_dato_kamp = _kamp(event_id="evt-riktig", commence_time="2023-01-16T00:30:00Z")
    annen_dato_kamp = _kamp(
        event_id="evt-annen",
        commence_time="2023-01-18T20:00:00Z",
        home_team="Boston Celtics",
        away_team="Los Angeles Lakers",
    )
    snapshot = _snapshot([riktig_dato_kamp, annen_dato_kamp])
    rader = odds.parse_snapshot_til_rader(snapshot, "2023-01-15", "bet_time", hentet_tidspunkt="2026-08-23T12:00:00")

    event_id_kolonne = 1
    assert all(rad[event_id_kolonne] == "evt-riktig" for rad in rader)


def test_bookmaker_med_kun_spreads_gir_null_rader():
    kamp = _kamp(
        bookmakers=[
            {
                "key": "unibet",
                "title": "Unibet",
                "markets": [
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "Miami Heat", "price": 1.90, "point": -5.5},
                            {"name": "Toronto Raptors", "price": 1.90, "point": 5.5},
                        ],
                    }
                ],
            }
        ]
    )
    snapshot = _snapshot([kamp])
    rader = odds.parse_snapshot_til_rader(snapshot, "2023-01-15", "bet_time", hentet_tidspunkt="2026-08-23T12:00:00")

    assert rader == []


def test_ukjent_lagnavn_gir_none_men_beholder_raden():
    kamp = _kamp(home_team="Ukjent Ballklubb XYZ", away_team="Toronto Raptors")
    snapshot = _snapshot([kamp])
    rader = odds.parse_snapshot_til_rader(snapshot, "2023-01-15", "bet_time", hentet_tidspunkt="2026-08-23T12:00:00")

    hjemme_lag_id_kolonne = 5
    hjemmelag_kolonne = 3
    assert len(rader) == 2
    assert all(rad[hjemme_lag_id_kolonne] is None for rad in rader)
    assert all(rad[hjemmelag_kolonne] == "Ukjent Ballklubb XYZ" for rad in rader)


def test_tom_data_liste_gir_tom_rad_liste():
    snapshot = _snapshot([])
    rader = odds.parse_snapshot_til_rader(snapshot, "2023-01-15", "bet_time", hentet_tidspunkt="2026-08-23T12:00:00")
    assert rader == []


def test_manglende_snapshot_timestamp_gir_value_error():
    snapshot = {"data": [_kamp()]}
    with pytest.raises(ValueError):
        odds.parse_snapshot_til_rader(snapshot, "2023-01-15", "bet_time")


def test_hentet_tidspunkt_settes_eksplisitt_pa_hver_rad():
    snapshot = _snapshot([_kamp()])
    rader = odds.parse_snapshot_til_rader(snapshot, "2023-01-15", "bet_time", hentet_tidspunkt="2026-08-23T12:00:00")

    hentet_tidspunkt_kolonne = 14
    assert all(rad[hentet_tidspunkt_kolonne] == "2026-08-23T12:00:00" for rad in rader)


def test_parsede_rader_settes_inn_via_arkiver_odds_rader(con):
    snapshot = _snapshot([_kamp()])
    rader = odds.parse_snapshot_til_rader(snapshot, "2023-01-15", "bet_time", hentet_tidspunkt="2026-08-23T12:00:00")

    antall_innsatt = odds.arkiver_odds_rader(con, rader)
    assert antall_innsatt == 2
    assert con.execute("SELECT COUNT(*) FROM odds_arkiv").fetchone()[0] == 2
