"""
Delte pytest-fixtures for feature- og paritetstester (plan 06).

Bygger deterministiske syntetiske rå-kamp-DataFrames med samme
kolonneskjema som 02_feature_engineering.py forventer, slik at
features.py-/strategy.py-testene ikke trenger ekte NBA-data.
Ingen bruk av random eller datetime.now() – alt er reproduserbart.
"""

import pandas as pd
import pytest

LAG_IDER = [1610612737, 1610612738, 1610612739, 1610612740]

# Faste hjemme/borte-parringer per kampindeks – gir hvert lag akkurat 5 kamper
# blant de 10 syntetiske kampene, nok til at min_periods=3 gir ikke-NaN verdier
# etter shift(1).
_PARRINGER = [(0, 1), (2, 3), (1, 2), (3, 0), (0, 2), (1, 3), (0, 1), (2, 3), (1, 2), (3, 0)]


def _lag_stats(i, lag_indeks):
    """Deterministiske statistikkverdier for ett lag i én kamp, gitt kampindeks og lagindeks."""
    return {
        "PTS": 100 + i + 2 * lag_indeks,
        "FG_PCT": 0.44 + 0.01 * lag_indeks,
        "FT_PCT": 0.78 + 0.01 * lag_indeks,
        "FG3_PCT": 0.35 + 0.01 * lag_indeks,
        "REB": 40 + lag_indeks,
        "AST": 20 + i % 4,
        "TOV": 12 + lag_indeks,
        "PLUS_MINUS": i - 5 + lag_indeks,
    }


def _bygg_rad(game_id, dato, i, hjemme_idx, borte_idx):
    """Bygger én rad i rå-kamp-skjemaet (21 kolonner, samme som 02_feature_engineering.py)."""
    hjemme = _lag_stats(i, hjemme_idx)
    borte = _lag_stats(i, borte_idx)
    return {
        "GAME_ID": game_id,
        "GAME_DATE_HJEMME": dato,
        "HJEMME_VANT": i % 2,
        "TEAM_ID_HJEMME": LAG_IDER[hjemme_idx],
        "PTS_HJEMME": hjemme["PTS"],
        "FG_PCT_HJEMME": hjemme["FG_PCT"],
        "FT_PCT_HJEMME": hjemme["FT_PCT"],
        "FG3_PCT_HJEMME": hjemme["FG3_PCT"],
        "REB_HJEMME": hjemme["REB"],
        "AST_HJEMME": hjemme["AST"],
        "TOV_HJEMME": hjemme["TOV"],
        "PLUS_MINUS_HJEMME": hjemme["PLUS_MINUS"],
        "TEAM_ID_BORTE": LAG_IDER[borte_idx],
        "PTS_BORTE": borte["PTS"],
        "FG_PCT_BORTE": borte["FG_PCT"],
        "FT_PCT_BORTE": borte["FT_PCT"],
        "FG3_PCT_BORTE": borte["FG3_PCT"],
        "REB_BORTE": borte["REB"],
        "AST_BORTE": borte["AST"],
        "TOV_BORTE": borte["TOV"],
        "PLUS_MINUS_BORTE": borte["PLUS_MINUS"],
    }


@pytest.fixture
def kamper_df():
    """10 syntetiske rå-kamper (2024-11-01 til 2024-11-28), 5 kamper per lag."""
    rader = []
    for i in range(10):
        game_id = f"00{22400000 + i}"
        dato = pd.Timestamp("2024-11-01") + pd.Timedelta(days=3 * i)
        hjemme_idx, borte_idx = _PARRINGER[i]
        rader.append(_bygg_rad(game_id, dato, i, hjemme_idx, borte_idx))
    df = pd.DataFrame(rader)
    return df.sort_values("GAME_DATE_HJEMME").reset_index(drop=True)


@pytest.fixture
def fremtidige_kamper_df():
    """2 fremtidige kamper: én på as_of-grensen (2024-12-01, skal ekskluderes av < as_of),
    én strengt i fremtiden (2024-12-04)."""
    rader = [
        _bygg_rad("0022400010", pd.Timestamp("2024-12-01"), 10, 0, 1),
        _bygg_rad("0022400011", pd.Timestamp("2024-12-04"), 11, 2, 3),
    ]
    return pd.DataFrame(rader)


@pytest.fixture
def as_of_dato():
    """as_of-skjæringsdato brukt av features.py-testene."""
    return "2024-12-01"
