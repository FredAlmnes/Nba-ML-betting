"""
Delt modul for rullende-vindu lagform-beregning.

Dette er den ENESTE implementasjonen av rullende-vindu-beregningen som i dag
finnes to steder: som lokal funksjon i 02_feature_engineering.py (batch,
trener modellen) og som en inline-blokk i 04_value_detector.py (live,
scorer modellen). Endres et navn eller en stat-liste her, endres det for
begge veiene samtidig — det er nettopp den drift-risikoen denne fasen
finnes for å stenge.

Importeres i dag av 02_feature_engineering.py (batch) og skal senere
importeres identisk av Phase 5s backtest via as_of-parameteren, uten at
signaturen trenger å endres videre.
"""

import pandas as pd

STATS_KOLONNER = ["PTS", "FG_PCT", "FT_PCT", "FG3_PCT", "REB", "AST", "TOV", "PLUS_MINUS", "VANT"]

RULLENDE_VINDU = 10

# Batch-veien (02_feature_engineering.py) bygger DIFF_-kolonner kun for disse
# syv statene. Live-veien (bygg_feature_rad under) bygger DIFF_ for alle ni.
# Dette er en FØR-EKSISTERENDE divergens, ikke noe denne fasen normaliserer:
# de to ekstra live-kolonnene (DIFF_FT_PCT, DIFF_FG3_PCT) er i dag harmløse
# fordi 04_value_detector.py filtrerer med [feature_kolonner] før predict.
# Å endre hvilke DIFF-kolonner som finnes ville endre modellens trente
# feature-sett, noe D-05 eksplisitt forbyr. Se 02-05-SUMMARY.md "Findings
# for Phase 5" for videre vurdering.
DIFF_STATS = ["PTS", "FG_PCT", "REB", "AST", "TOV", "PLUS_MINUS", "VANT"]


def beregn_lag_form(df_raw, vindu=RULLENDE_VINDU, as_of=None):
    """
    Beregner rullende gjennomsnitt for hvert lag.

    'vindu' = antall tidligere kamper å se på.
    Vi bruker shift(1) for å sikre at vi aldri bruker
    informasjon fra den kampen vi prøver å spå.

    'as_of', hvis satt, filtrerer df_raw til rader med GAME_DATE_HJEMME
    STRENGT FØR as_of, FØR selve rullende-vindu-beregningen kjøres. Dette
    er et forsvar-i-dybden-filter: shift(1).rolling(...) er allerede
    leakage-safe per rad (radene er sortert på dato, og shift(1) leser
    kun bakover), men as_of gjør funksjonen trygg å kalle med en full,
    flersesong DataFrame som inkluderer rader etter skjæringsdatoen —
    nøyaktig det en fremtidig walk-forward-backtest (Phase 5) trenger.
    Strengt < er avgjørende her: <= ville latt kampen vi prøver å spå
    bidra til sin egen rullende gjennomsnittsverdi.
    """
    if as_of is not None:
        df_raw = df_raw[df_raw["GAME_DATE_HJEMME"] < as_of]

    # Bruk de originale per-lag-per-kamp radene
    # (henter fra hjemme-kolonnene siden vi har dem)

    kolonne_map = {
        "GAME_ID": "GAME_ID",
        "GAME_DATE_HJEMME": "DATO",
        "TEAM_ID_HJEMME": "TEAM_ID",
        "PTS_HJEMME": "PTS",
        "FG_PCT_HJEMME": "FG_PCT",
        "FT_PCT_HJEMME": "FT_PCT",
        "FG3_PCT_HJEMME": "FG3_PCT",
        "REB_HJEMME": "REB",
        "AST_HJEMME": "AST",
        "TOV_HJEMME": "TOV",
        "PLUS_MINUS_HJEMME": "PLUS_MINUS",
        "HJEMME_VANT": "VANT"
    }

    hjemme_df = df_raw[list(kolonne_map.keys())].rename(columns=kolonne_map).copy()
    hjemme_df["ER_HJEMME"] = 1

    kolonne_map_borte = {
        "GAME_ID": "GAME_ID",
        "GAME_DATE_HJEMME": "DATO",
        "TEAM_ID_BORTE": "TEAM_ID",
        "PTS_BORTE": "PTS",
        "FG_PCT_BORTE": "FG_PCT",
        "FT_PCT_BORTE": "FT_PCT",
        "FG3_PCT_BORTE": "FG3_PCT",
        "REB_BORTE": "REB",
        "AST_BORTE": "AST",
        "TOV_BORTE": "TOV",
        "PLUS_MINUS_BORTE": "PLUS_MINUS",
    }

    borte_df = df_raw[list(kolonne_map_borte.keys())].rename(columns=kolonne_map_borte).copy()
    borte_df["VANT"] = 1 - df_raw["HJEMME_VANT"].values  # Bortelaget vant det motsatte
    borte_df["ER_HJEMME"] = 0

    # Slå sammen til én tabell
    alle = pd.concat([hjemme_df, borte_df], ignore_index=True)
    alle = alle.sort_values(["TEAM_ID", "DATO"]).reset_index(drop=True)

    # Beregn rullende statistikk per lag
    for kol in STATS_KOLONNER:
        # shift(1) betyr "bruk forrige kamps verdi" – ikke dagens
        # Dette er avgjørende for å unngå "data leakage"!
        alle[f"RULL_{kol}"] = (
            alle.groupby("TEAM_ID")[kol]
            .transform(lambda x: x.shift(1).rolling(window=vindu, min_periods=3).mean())
        )

    return alle


def snitt_fra_kamplogg(df_logg):
    """
    Beregner snitt-statistikk for et lag fra en nba_api-kamplogg-DataFrame.

    Samme verdier og nøkkelnavn som tidligere hardkodet inline i
    04_value_detector.py::hent_siste_lagstats. Gjør IKKE len(df) < 3-
    sjekken, API-kallet eller time.sleep() — de blir værende i
    04_value_detector.py som orkestrering (I/O hører ikke hjemme her).
    """
    return {
        "PTS":        df_logg["PTS"].mean(),
        "FG_PCT":     df_logg["FG_PCT"].mean(),
        "FT_PCT":     df_logg["FT_PCT"].mean(),
        "FG3_PCT":    df_logg["FG3_PCT"].mean(),
        "REB":        df_logg["REB"].mean(),
        "AST":        df_logg["AST"].mean(),
        "TOV":        df_logg["TOV"].mean(),
        "PLUS_MINUS": df_logg["PLUS_MINUS"].mean(),
        "VANT":       (df_logg["WL"] == "W").mean()
    }


def bygg_feature_rad(hjemme_stats, borte_stats):
    """
    Bygger den flate feature-raden modellen forventer, fra hjemme- og
    bortelagets snitt-statistikk-dicts. Samme HJEMME_RULL_/BORTE_RULL_/
    DIFF_-navngiving som tidligere inline i 04_value_detector.py, for
    alle ni statene i STATS_KOLONNER.
    """
    feature_rad = {}
    for stat in STATS_KOLONNER:
        feature_rad[f"HJEMME_RULL_{stat}"] = hjemme_stats[stat]
        feature_rad[f"BORTE_RULL_{stat}"] = borte_stats[stat]
        feature_rad[f"DIFF_{stat}"] = hjemme_stats[stat] - borte_stats[stat]
    return feature_rad
