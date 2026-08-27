"""
Tester for spillerlogg.py — historisk spiller-kamplogg-innhenting og
normalisering (plan 05-05).

Alle tester her gjør null nettverkskall. Enhver nba_api-respons injiseres
som en syntetisk DataFrame via hent_spillerlogg sitt hent_fn-keyword.
Filen finnes for å bevise de tre egenskapene plan 05-06 avhenger av:
korrekt kolonneskjema, at GAME_DATE er brukbar som en strengbasert
as-of-nøkkel, og skip-and-log (i stedet for krasj) på en feilet sesong.
"""

import importlib

import pandas as pd
import pytest

import spillerlogg
from spillerlogg import (
    KILDEKOLONNER,
    KOLONNER,
    hent_spillerlogg,
    lagre_spillerlogg,
    les_spillerlogg,
    normaliser_spillerlogg,
)


def _raa_sesong(sesong, antall=3, team_id=1610612748):
    """Bygger en syntetisk rå nba_api-formet DataFrame for én sesong.

    Inneholder alle KILDEKOLONNER pluss to ekstra kolonner (MATCHUP, WL)
    for å bevise at ekstra kolonner droppes. Datoer er deterministiske og
    innenfor gitt sesong.
    """
    datoer_per_sesong = {
        "2022-23": ["2022-10-24", "2022-10-26", "2022-10-28"],
        "2023-24": ["2023-10-24", "2023-10-26", "2023-10-28"],
        "2024-25": ["2024-10-24", "2024-10-26", "2024-10-28"],
    }
    datoer = datoer_per_sesong.get(sesong, ["2022-10-24", "2022-10-26", "2022-10-28"])[:antall]

    rader = []
    for i, dato in enumerate(datoer):
        rader.append({
            "PLAYER_ID": 100 + i,
            "PLAYER_NAME": f"Spiller {i}",
            "TEAM_ID": team_id,
            "GAME_ID": f"002220{i:04d}",
            "GAME_DATE": dato,
            "MIN": 30.0 + i,
            "MATCHUP": "MIA vs. TOR",
            "WL": "W",
        })
    return pd.DataFrame(rader)


def test_import_spillerlogg_gjor_ingen_nettverkskall(monkeypatch):
    """
    Reloader spillerlogg med LeagueGameLog erstattet av en funksjon som
    kaster AssertionError hvis den kalles. Modulen skal lastes uten feil.
    """
    from nba_api.stats.endpoints import leaguegamelog

    def _sprengt(*args, **kwargs):
        raise AssertionError("LeagueGameLog skal IKKE kalles ved import")

    monkeypatch.setattr(leaguegamelog, "LeagueGameLog", _sprengt)

    modul = importlib.reload(spillerlogg)
    assert modul is not None


def test_normaliser_gir_eksakt_kolonneskjema():
    rå = _raa_sesong("2022-23")
    n = normaliser_spillerlogg(rå, "2022-23")

    assert list(n.columns) == KOLONNER
    assert "MATCHUP" not in n.columns
    assert "WL" not in n.columns
    assert (n["SESONG"] == "2022-23").all()


def test_normaliser_gir_iso_dato_streng_uansett_inndatatype():
    rå_streng = _raa_sesong("2022-23")

    rå_tidsstempel = rå_streng.copy()
    rå_tidsstempel["GAME_DATE"] = pd.to_datetime(rå_tidsstempel["GAME_DATE"])

    n_streng = normaliser_spillerlogg(rå_streng, "2022-23")
    n_tidsstempel = normaliser_spillerlogg(rå_tidsstempel, "2022-23")

    assert list(n_streng["GAME_DATE"]) == list(n_tidsstempel["GAME_DATE"])
    assert all(isinstance(v, str) for v in n_streng["GAME_DATE"])
    assert all(isinstance(v, str) for v in n_tidsstempel["GAME_DATE"])


def test_normaliser_dato_stotter_streng_sammenligning_som_as_of():
    """
    Beviser strengt-<-som-as-of-grense-egenskapen plan 05-06 avhenger av —
    mirrorer tests/test_parity.py::test_grenserad_paa_as_of_er_ekskludert.
    """
    rå = _raa_sesong("2022-23")  # datoer: 2022-10-24, 2022-10-26, 2022-10-28
    n = normaliser_spillerlogg(rå, "2022-23")

    assert (n["GAME_DATE"] < "2022-10-26").sum() == 1
    assert (n["GAME_DATE"] < "2022-10-24").sum() == 0


def test_normaliser_manglende_kolonne_reiser_valueerror():
    rå = _raa_sesong("2022-23").drop(columns=["PLAYER_ID"])

    with pytest.raises(ValueError) as excinfo:
        normaliser_spillerlogg(rå, "2022-23")

    assert "PLAYER_ID" in str(excinfo.value)


def test_normaliser_null_minutter_blir_null_float():
    """
    0.0 er den konservative retningen — det gjør at den nedstrøms sjekken
    behandler spilleren som utilgjengelig i stedet for å skape falsk
    trygghet.
    """
    rå = _raa_sesong("2022-23", antall=2)
    rå["MIN"] = rå["MIN"].astype(object)
    rå.loc[0, "MIN"] = None
    rå.loc[1, "MIN"] = "ikke-tall"

    n = normaliser_spillerlogg(rå, "2022-23")

    assert n.loc[0, "MIN"] == 0.0
    assert n.loc[1, "MIN"] == 0.0
    assert n["MIN"].dtype == float


def test_hent_spillerlogg_hopper_over_feilet_sesong():
    def hent_fn(sesong):
        if sesong == "2023-24":
            return pd.DataFrame()
        return _raa_sesong(sesong)

    df, resultat = hent_spillerlogg(hent_fn=hent_fn)

    assert resultat["hoppet_over"] == ["2023-24"]
    assert resultat["sesonger_hentet"] == 2
    assert set(df["SESONG"].unique()) == {"2022-23", "2024-25"}


def test_hent_spillerlogg_hopper_over_allerede_hentede_sesonger():
    eksisterende_df = normaliser_spillerlogg(_raa_sesong("2022-23"), "2022-23")

    forespurte_sesonger = []

    def hent_fn(sesong):
        forespurte_sesonger.append(sesong)
        return _raa_sesong(sesong)

    df, resultat = hent_spillerlogg(hent_fn=hent_fn, eksisterende_df=eksisterende_df)

    assert forespurte_sesonger == ["2023-24", "2024-25"]
    assert resultat["allerede_hentet"] == 1
    assert set(df["SESONG"].unique()) == {"2022-23", "2023-24", "2024-25"}


def test_hent_spillerlogg_alle_sesonger_feiler_gir_tom_ramme():
    def hent_fn(sesong):
        return pd.DataFrame()

    df, resultat = hent_spillerlogg(hent_fn=hent_fn)

    assert df.empty
    assert resultat["hoppet_over"] == ["2022-23", "2023-24", "2024-25"]


def test_lagre_og_les_bevarer_dato_som_streng(tmp_path):
    n = normaliser_spillerlogg(_raa_sesong("2022-23"), "2022-23")
    for_antall = (n["GAME_DATE"] < "2022-10-26").sum()

    sti = tmp_path / "spillerlogg.csv"
    lagre_spillerlogg(n, filnavn=str(sti))
    lest = les_spillerlogg(filnavn=str(sti))

    assert all(isinstance(v, str) for v in lest["GAME_DATE"])
    assert list(lest["GAME_DATE"]) == list(n["GAME_DATE"])
    assert (lest["GAME_DATE"] < "2022-10-26").sum() == for_antall


def test_les_spillerlogg_manglende_fil_gir_forklarende_feil(tmp_path):
    sti = tmp_path / "finnes_ikke.csv"

    with pytest.raises(FileNotFoundError) as excinfo:
        les_spillerlogg(filnavn=str(sti))

    assert "spillerlogg.py" in str(excinfo.value)
