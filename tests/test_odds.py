"""
Tester for odds.py sitt SQLite-arkivlag (plan 04-01) og HTTP-laget (plan 04-04).

Dekker skjema-oppretting, eksistenssjekk før nettverkskall (D-04's faktiske
kredittsparende mekanisme), idempotent innsetting, og kredittlogg-lagring.

Fra og med plan 04-04 dekkes ogsa hent_api_nokkel/_utfor_kall/hent_live_odds/
hent_historisk_odds_snapshot/hent_historiske_events — ALLTID mot en mocket
requests.get (unittest.mock.patch("odds.requests.get")). Ingen test i denne
filen gjor et ekte nettverkskall til the-odds-api.com — det er forbeholdt
plan 04-07 sin eksplisitt godkjente smoke-test.
"""

import sqlite3
from unittest.mock import patch

import pytest
import requests

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


# ---------------------------------------------------------------------------
# Plan 04-04: HTTP-laget (hent_api_nokkel, _utfor_kall, hent_live_odds)
#
# SvarMock star inn for requests.Response uten a bygge en ekte HTTP-forbindelse.
# raise_for_status() etterligner requests sin virkemate: kaster HTTPError for
# enhver status >= 400, som er nettopp hva _utfor_kall sin tenacity-retry
# lytter etter (retry_if_exception_type(requests.exceptions.HTTPError)).
# ---------------------------------------------------------------------------


class SvarMock:
    def __init__(self, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else []
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} feil", response=self)


def test_hent_api_nokkel_returnerer_verdi(monkeypatch):
    monkeypatch.setattr(odds, "load_dotenv", lambda: None)
    monkeypatch.setenv("ODDS_API_NOKKEL", "hemmelig-test-nokkel")
    assert odds.hent_api_nokkel() == "hemmelig-test-nokkel"


def test_hent_api_nokkel_exitcode_1_uten_variabel(monkeypatch, capsys):
    monkeypatch.setattr(odds, "load_dotenv", lambda: None)
    monkeypatch.delenv("ODDS_API_NOKKEL", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        odds.hent_api_nokkel()
    assert exc_info.value.code == 1
    utdata = capsys.readouterr().out
    assert "ODDS_API_NOKKEL" in utdata


@patch("odds.requests.get")
def test_hent_live_odds_returnerer_json_uendret(mock_get):
    kamper = [{"id": "evt-1", "home_team": "Boston Celtics"}]
    mock_get.return_value = SvarMock(
        status_code=200, json_data=kamper, headers={"x-requests-remaining": "19990"}
    )
    resultat = odds.hent_live_odds(api_nokkel="test-nokkel")
    assert resultat == kamper


@patch("odds.requests.get")
def test_hent_live_odds_kaller_riktig_url_og_params(mock_get):
    mock_get.return_value = SvarMock(status_code=200, json_data=[])
    odds.hent_live_odds(api_nokkel="test-nokkel")

    kall_args, kall_kwargs = mock_get.call_args
    assert kall_args[0] == "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
    params = kall_kwargs["params"]
    assert params["apiKey"] == "test-nokkel"
    assert params["regions"] == "eu"
    assert params["markets"] == "h2h"
    assert params["oddsFormat"] == "decimal"
    assert params["dateFormat"] == "iso"


@patch("odds.requests.get")
def test_hent_live_odds_401_gir_systemexit_og_printer_body(mock_get, capsys):
    mock_get.return_value = SvarMock(status_code=401, text="Ugyldig API-nokkel")
    with pytest.raises(SystemExit) as exc_info:
        odds.hent_live_odds(api_nokkel="ugyldig-nokkel")
    assert exc_info.value.code == 1
    utdata = capsys.readouterr().out
    assert "Ugyldig API-nokkel" in utdata


@patch("time.sleep", lambda *a, **k: None)
@patch("odds.requests.get")
def test_utfor_kall_retryer_pa_429_og_lykkes(mock_get):
    mock_get.side_effect = [
        SvarMock(status_code=429, text="Rate limited"),
        SvarMock(status_code=200, json_data=[{"id": "evt-1"}]),
    ]
    respons = odds._utfor_kall(
        "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/", {"apiKey": "x"}
    )
    assert respons.status_code == 200
    assert mock_get.call_count == 2


@patch("time.sleep", lambda *a, **k: None)
@patch("odds.requests.get")
def test_utfor_kall_gir_opp_etter_4_forsok_pa_503(mock_get):
    mock_get.side_effect = [SvarMock(status_code=503, text="Server error")] * 4
    with pytest.raises(requests.exceptions.HTTPError):
        odds._utfor_kall(
            "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/", {"apiKey": "x"}
        )
    assert mock_get.call_count == 4


@patch("odds.requests.get")
def test_utfor_kall_retryer_ikke_401(mock_get):
    mock_get.return_value = SvarMock(status_code=401, text="Ugyldig nokkel")
    with pytest.raises(SystemExit):
        odds._utfor_kall(
            "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/", {"apiKey": "x"}
        )
    assert mock_get.call_count == 1


@patch("odds.requests.get")
def test_utfor_kall_retryer_ikke_422(mock_get):
    mock_get.return_value = SvarMock(status_code=422, text="Ugyldige parametre")
    with pytest.raises(SystemExit):
        odds._utfor_kall(
            "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/", {"apiKey": "x"}
        )
    assert mock_get.call_count == 1


@patch("odds.requests.get")
def test_api_nokkel_aldri_i_printet_output(mock_get, capsys):
    mock_get.return_value = SvarMock(status_code=401, text="Feil")
    hemmelig = "super-hemmelig-nokkel-123"
    with pytest.raises(SystemExit):
        odds.hent_live_odds(api_nokkel=hemmelig)
    utdata = capsys.readouterr().out
    assert hemmelig not in utdata


# ---------------------------------------------------------------------------
# Plan 04-04: de historiske endepunktene (hent_historisk_odds_snapshot,
# hent_historiske_events). Begge returnerer (body, headers) og lar kalleren
# eie kredittregnskapet - ingen av dem skriver til arkivet selv.
# ---------------------------------------------------------------------------


@patch("odds.requests.get")
def test_hent_historisk_odds_snapshot_kaller_riktig_url_og_params(mock_get):
    mock_get.return_value = SvarMock(
        status_code=200,
        json_data={"timestamp": "2023-01-15T13:00:00Z", "data": []},
        headers={"x-requests-last": "10"},
    )
    odds.hent_historisk_odds_snapshot("test-nokkel", "2023-01-15T13:00:00Z")

    kall_args, kall_kwargs = mock_get.call_args
    assert kall_args[0] == "https://api.the-odds-api.com/v4/historical/sports/basketball_nba/odds"
    params = kall_kwargs["params"]
    assert params["apiKey"] == "test-nokkel"
    assert params["regions"] == "eu"
    assert params["markets"] == "h2h"
    assert params["oddsFormat"] == "decimal"
    assert params["dateFormat"] == "iso"
    assert params["date"] == "2023-01-15T13:00:00Z"


@patch("odds.requests.get")
def test_hent_historisk_odds_snapshot_returnerer_body_og_headers(mock_get):
    body = {"timestamp": "2023-01-15T13:00:00Z", "data": [{"id": "evt-1"}]}
    headers = {"x-requests-last": "10", "x-requests-remaining": "19980"}
    mock_get.return_value = SvarMock(status_code=200, json_data=body, headers=headers)

    snapshot, mottatte_headers = odds.hent_historisk_odds_snapshot("test-nokkel", "2023-01-15T13:00:00Z")
    assert snapshot == body
    assert mottatte_headers == headers


@patch("odds.requests.get")
def test_hent_historisk_odds_snapshot_uten_timestamp_returneres_som_den_er(mock_get):
    body = {"data": []}
    mock_get.return_value = SvarMock(status_code=200, json_data=body)

    snapshot, _ = odds.hent_historisk_odds_snapshot("test-nokkel", "2023-01-15T13:00:00Z")
    assert snapshot == body


@patch("odds.requests.get")
def test_hent_historiske_events_kaller_riktig_url_og_params(mock_get):
    mock_get.return_value = SvarMock(status_code=200, json_data=[], headers={"x-requests-last": "1"})
    odds.hent_historiske_events(
        "test-nokkel", "2023-01-15T13:00:00Z", "2023-01-15T00:00:00Z", "2023-01-16T00:00:00Z"
    )

    kall_args, kall_kwargs = mock_get.call_args
    assert kall_args[0] == "https://api.the-odds-api.com/v4/historical/sports/basketball_nba/events"
    params = kall_kwargs["params"]
    assert params["apiKey"] == "test-nokkel"
    assert params["date"] == "2023-01-15T13:00:00Z"
    assert params["commenceTimeFrom"] == "2023-01-15T00:00:00Z"
    assert params["commenceTimeTo"] == "2023-01-16T00:00:00Z"
    assert "regions" not in params
    assert "markets" not in params


@patch("odds.requests.get")
def test_hent_historiske_events_returnerer_svar_og_headers(mock_get):
    events = [{"id": "evt-1", "home_team": "Boston Celtics", "away_team": "Miami Heat",
               "commence_time": "2023-01-15T18:00:00Z"}]
    headers = {"x-requests-last": "1", "x-requests-remaining": "19979"}
    mock_get.return_value = SvarMock(status_code=200, json_data=events, headers=headers)

    svar, mottatte_headers = odds.hent_historiske_events(
        "test-nokkel", "2023-01-15T13:00:00Z", "2023-01-15T00:00:00Z", "2023-01-16T00:00:00Z"
    )
    assert svar == events
    assert mottatte_headers == headers


def test_ingen_per_event_endepunkt_i_bruk():
    with open("odds.py") as f:
        innhold = f.read()
    assert "events/{" not in innhold
