"""
Tester for skadefilter.py — skadefilter-beslutningslogikken flyttet ut av
05_skadefilter.py som importerbare funksjoner (plan 04-02).

Beviser to ting: (1) at å importere modulen ikke lenger gjør fire nba_api-
kall slik den gamle 05_skadefilter.py gjorde ved import (SESONG/print-
blokken kjørte på modul-nivå), og (2) at beslutningsreglene (sjekk_spiller,
hent_toppspillere_for_lag, filtrer_bets_for_skader) oppfører seg identisk
med før, gitt injiserte DataFrames — ingen nettverkskall.
"""

import importlib

import pandas as pd

import skadefilter
from skadefilter import (
    ANTALL_TOPPSPILLERE,
    MIN_MINUTTER,
    filtrer_bets_for_skader,
    hent_toppspillere_for_lag,
    sjekk_spiller,
)

# Ekte NBA-lag-IDer, resolverbare via teams.finn_lag_id (Miami Heat / Toronto Raptors).
HEAT_ID = 1610612748
RAPTORS_ID = 1610612761


def test_import_skadefilter_gjor_ingen_nettverkskall(monkeypatch):
    """
    Reloader skadefilter med LeagueDashPlayerStats erstattet av en funksjon
    som kaster AssertionError hvis den kalles. Modulen skal lastes uten
    feil — det beviser at ingen kode på modul-nivå gjør nba_api-kall (i
    motsetning til gamle 05_skadefilter.py, som hentet spillerdata og
    printet "Bruker sesong: ..." ved import).
    """
    from nba_api.stats.endpoints import leaguedashplayerstats

    def _sprengt(*args, **kwargs):
        raise AssertionError("LeagueDashPlayerStats skal IKKE kalles ved import")

    monkeypatch.setattr(leaguedashplayerstats, "LeagueDashPlayerStats", _sprengt)

    modul = importlib.reload(skadefilter)
    assert modul is not None


def test_sjekk_spiller_fraverende_spiller_gir_false():
    siste3 = pd.DataFrame(columns=["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "MIN", "GP"])
    ok, melding = sjekk_spiller(siste3, 999, "Testspiller", 25.0)
    assert ok is False
    assert "Testspiller" in melding
    assert "0 kamper siste 3" in melding


def test_sjekk_spiller_lavt_gp_gir_false():
    siste3 = pd.DataFrame([
        {"PLAYER_ID": 1, "PLAYER_NAME": "Spiller A", "TEAM_ID": HEAT_ID, "MIN": 15.0, "GP": 1},
    ])
    ok, _ = sjekk_spiller(siste3, 1, "Spiller A", 30.0)
    assert ok is False


def test_sjekk_spiller_lave_minutter_gir_false():
    siste3 = pd.DataFrame([
        {"PLAYER_ID": 1, "PLAYER_NAME": "Spiller A", "TEAM_ID": HEAT_ID, "MIN": 8.0, "GP": 3},
    ])
    ok, _ = sjekk_spiller(siste3, 1, "Spiller A", 30.0)
    assert ok is False


def test_sjekk_spiller_ok_gir_true():
    siste3 = pd.DataFrame([
        {"PLAYER_ID": 1, "PLAYER_NAME": "Spiller A", "TEAM_ID": HEAT_ID, "MIN": 32.0, "GP": 3},
    ])
    ok, melding = sjekk_spiller(siste3, 1, "Spiller A", 30.0)
    assert ok is True
    assert "Spiller A" in melding


def test_hent_toppspillere_for_lag_respekterer_grense_og_sortering():
    sesong_snitt = pd.DataFrame([
        {"PLAYER_ID": 1, "PLAYER_NAME": "A", "TEAM_ID": HEAT_ID, "MIN": 30.0},
        {"PLAYER_ID": 2, "PLAYER_NAME": "B", "TEAM_ID": HEAT_ID, "MIN": 25.0},
        {"PLAYER_ID": 3, "PLAYER_NAME": "C", "TEAM_ID": HEAT_ID, "MIN": 22.0},
        {"PLAYER_ID": 4, "PLAYER_NAME": "D", "TEAM_ID": HEAT_ID, "MIN": 21.0},
        {"PLAYER_ID": 5, "PLAYER_NAME": "E", "TEAM_ID": HEAT_ID, "MIN": 15.0},  # under MIN_MINUTTER
    ])
    topp = hent_toppspillere_for_lag(sesong_snitt, HEAT_ID)
    assert len(topp) == ANTALL_TOPPSPILLERE
    minutter = [sp["MIN"] for sp in topp]
    assert minutter == sorted(minutter, reverse=True)
    assert all(sp["MIN"] >= MIN_MINUTTER for sp in topp)


def _value_df(kamp="Miami Heat vs Toronto Raptors"):
    return pd.DataFrame([{
        "Kamp": kamp,
        "KampDato": "2026-01-15",
        "Bet": "Hjemme (Miami Heat)",
        "Odds": 1.85,
        "Bookmaker": "TestBook",
        "Modell_prob": 0.58,
        "Modell %": "58.0%",
        "Bookmaker %": "54.0%",
        "Value": "+4.0%",
        "Forv. EV": "+2.3%",
    }])


def _sesong_snitt_topp3(team_id, min_verdi=30.0):
    return pd.DataFrame([
        {"PLAYER_ID": team_id * 10 + i, "PLAYER_NAME": f"Spiller {i}", "TEAM_ID": team_id, "MIN": min_verdi - i}
        for i in range(ANTALL_TOPPSPILLERE)
    ])


def test_filtrer_bets_for_skader_ingen_nettverkskall_og_bevarer_radantall(monkeypatch):
    """Med siste3/sesong_snitt injisert skal ingen nba_api-kall skje, og radantallet bevares."""
    from nba_api.stats.endpoints import leaguedashplayerstats

    def _sprengt(*args, **kwargs):
        raise AssertionError("Skal ikke kalle nba_api når siste3/sesong_snitt er injisert")

    monkeypatch.setattr(leaguedashplayerstats, "LeagueDashPlayerStats", _sprengt)

    sesong_snitt = pd.concat([
        _sesong_snitt_topp3(HEAT_ID),
        _sesong_snitt_topp3(RAPTORS_ID),
    ], ignore_index=True)

    siste3 = pd.DataFrame([
        {"PLAYER_ID": rad["PLAYER_ID"], "PLAYER_NAME": rad["PLAYER_NAME"],
         "TEAM_ID": rad["TEAM_ID"], "MIN": rad["MIN"], "GP": 3}
        for _, rad in sesong_snitt.iterrows()
    ])

    value_df = _value_df()
    resultat = filtrer_bets_for_skader(value_df, siste3=siste3, sesong_snitt=sesong_snitt)

    assert len(resultat) == len(value_df)
    assert resultat.iloc[0]["Skadestatus"] == "✅ OK"
    assert resultat.iloc[0]["Skadeinfo"] == "Alle nøkkelspillere spilte siste 3 kamper"


def test_filtrer_bets_for_skader_flagger_usikker_ved_fravaerende_toppspiller():
    sesong_snitt = pd.concat([
        _sesong_snitt_topp3(HEAT_ID),
        _sesong_snitt_topp3(RAPTORS_ID),
    ], ignore_index=True)

    # Heat sin beste spiller (høyest MIN) mangler helt fra siste3-datasettet -> 0 kamper siste 3.
    heat_topp_id = (
        sesong_snitt[sesong_snitt["TEAM_ID"] == HEAT_ID]
        .sort_values("MIN", ascending=False)
        .iloc[0]["PLAYER_ID"]
    )
    siste3_rader = []
    for _, rad in sesong_snitt.iterrows():
        if rad["PLAYER_ID"] == heat_topp_id:
            continue
        siste3_rader.append({
            "PLAYER_ID": rad["PLAYER_ID"], "PLAYER_NAME": rad["PLAYER_NAME"],
            "TEAM_ID": rad["TEAM_ID"], "MIN": rad["MIN"], "GP": 3,
        })
    siste3 = pd.DataFrame(siste3_rader)

    value_df = _value_df()
    resultat = filtrer_bets_for_skader(value_df, siste3=siste3, sesong_snitt=sesong_snitt)

    assert len(resultat) == len(value_df)
    assert resultat.iloc[0]["Skadestatus"] == "⚠️  USIKKER"
    assert resultat.iloc[0]["Skadeinfo"] != ""


def test_filtrer_bets_for_skader_hopper_over_uresolverbart_lagnavn(monkeypatch):
    """Et lagnavn finn_lag_id() ikke klarer å løse skal hoppes over uten å kaste (dagens continue-oppførsel)."""
    monkeypatch.setattr(skadefilter, "finn_lag_id", lambda navn: None)

    value_df = _value_df()
    sesong_snitt = pd.DataFrame(columns=["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "MIN"])
    siste3 = pd.DataFrame(columns=["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "MIN", "GP"])

    resultat = filtrer_bets_for_skader(value_df, siste3=siste3, sesong_snitt=sesong_snitt)

    assert len(resultat) == len(value_df)
    assert resultat.iloc[0]["Skadestatus"] == "✅ OK"
