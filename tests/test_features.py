"""
Tester for features.py sin feature-kolonnekontrakt og as_of-grense.

Dette beskytter feature-kolonnekontrakten som deles mellom trening og
live-scoring: en mismatch her mater modellen et skjema den ikke er
trent på (train/serve skew), og en as_of-grense-feil (<= i stedet for <)
lekker fremtidig informasjon inn i en rullende gjennomsnittsverdi.
"""

import pandas as pd
import pytest

from features import beregn_lag_form, snitt_fra_kamplogg, bygg_feature_rad, STATS_KOLONNER, DIFF_STATS


def test_beregn_lag_form_gir_to_rader_per_kamp(kamper_df):
    resultat = beregn_lag_form(kamper_df)
    assert len(resultat) == 2 * len(kamper_df)
    assert resultat["ER_HJEMME"].sum() == len(kamper_df)


def test_rull_kolonner_finnes_for_alle_stats(kamper_df):
    resultat = beregn_lag_form(kamper_df)
    rull_kolonner = {k for k in resultat.columns if k.startswith("RULL_")}
    forventede = {f"RULL_{stat}" for stat in STATS_KOLONNER}
    assert rull_kolonner == forventede


def test_shift_gjor_forste_kamp_nan(kamper_df):
    resultat = beregn_lag_form(kamper_df)
    lag_id = resultat["TEAM_ID"].iloc[0]
    lag_rader = resultat[resultat["TEAM_ID"] == lag_id].sort_values("DATO")
    forste_rad = lag_rader.iloc[0]
    assert pd.isna(forste_rad["RULL_PTS"])


def test_as_of_filtrerer_bort_kampen_selv(fremtidige_kamper_df, as_of_dato):
    resultat = beregn_lag_form(fremtidige_kamper_df, as_of=as_of_dato)
    # Kampen datert nøyaktig 2024-12-01 skal EKSKLUDERES av < as_of (Pitfall 3),
    # kampen datert 2024-12-04 er strengt i fremtiden og skal også være borte.
    assert "0022400010" not in set(resultat["GAME_ID"])
    assert "0022400011" not in set(resultat["GAME_ID"])
    assert len(resultat) == 0


def test_as_of_none_beholder_alle_rader(kamper_df):
    uten_as_of = beregn_lag_form(kamper_df)
    med_as_of_none = beregn_lag_form(kamper_df, as_of=None)
    assert len(uten_as_of) == len(med_as_of_none)
    # Default er opt-out, ikke opt-in: siste kamp må være med i begge.
    assert uten_as_of["DATO"].max() == med_as_of_none["DATO"].max()


def test_snitt_fra_kamplogg_bruker_stats_kolonner():
    df_logg = pd.DataFrame({
        "PTS": [100, 110, 90, 100],
        "FG_PCT": [0.45, 0.46, 0.44, 0.45],
        "FT_PCT": [0.80, 0.79, 0.78, 0.80],
        "FG3_PCT": [0.35, 0.36, 0.34, 0.35],
        "REB": [40, 42, 38, 40],
        "AST": [22, 23, 21, 22],
        "TOV": [12, 13, 11, 12],
        "PLUS_MINUS": [5, 6, -4, 3],
        "WL": ["W", "W", "L", "W"],
    })
    resultat = snitt_fra_kamplogg(df_logg)
    assert set(resultat.keys()) == set(STATS_KOLONNER)
    assert resultat["VANT"] == 0.75
    assert resultat["PTS"] == 100.0


def test_bygg_feature_rad_kolonnenavn():
    hjemme_stats = {k: 1.0 for k in STATS_KOLONNER}
    borte_stats = {k: 0.5 for k in STATS_KOLONNER}
    feature_rad = bygg_feature_rad(hjemme_stats, borte_stats)

    assert len(feature_rad) == 27
    for stat in STATS_KOLONNER:
        assert f"HJEMME_RULL_{stat}" in feature_rad
        assert f"BORTE_RULL_{stat}" in feature_rad
        assert f"DIFF_{stat}" in feature_rad
        assert feature_rad[f"DIFF_{stat}"] == (
            feature_rad[f"HJEMME_RULL_{stat}"] - feature_rad[f"BORTE_RULL_{stat}"]
        )
