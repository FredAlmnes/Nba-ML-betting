"""
STEG 2: Feature Engineering
=============================
Her gjør vi rådata om til nyttige "features" – variabler som
modellen faktisk kan lære noe av.

Tanken er: hva VET vi FØR en kamp spilles?
  - Lagets form de siste N kampene
  - Gjennomsnittsstatistikk (poeng, rebounds, assists...)
  - Hjemmebanefordel
  - Vinnprosent denne sesongen

Vi bruker et "rullende vindu" – f.eks. siste 10 kamper –
for å beregne form. Dette er mer realistisk enn sesongsnitt.
"""

import pandas as pd
import numpy as np

# -------------------------------------------------------
# 1. Les inn rådata
# -------------------------------------------------------
print("Leser inn rådata...")
df = pd.read_csv("nba_kamper_raw.csv", parse_dates=["GAME_DATE_HJEMME"])
df = df.sort_values("GAME_DATE_HJEMME").reset_index(drop=True)

print(f"Antall kamper: {len(df)}")

# -------------------------------------------------------
# 2. Beregn rullende statistikk PER LAG
# -------------------------------------------------------
# Vi trenger ett datasett med én rad per lag per kamp (som rådata har),
# og beregner statistikk BAKOVER i tid (vi kan ikke bruke fremtidig info!)

def beregn_lag_form(df_raw, vindu=10):
    """
    Beregner rullende gjennomsnitt for hvert lag.

    'vindu' = antall tidligere kamper å se på.
    Vi bruker shift(1) for å sikre at vi aldri bruker
    informasjon fra den kampen vi prøver å spå.
    """
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

    hjemme_df = df[list(kolonne_map.keys())].rename(columns=kolonne_map).copy()
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

    borte_df = df[list(kolonne_map_borte.keys())].rename(columns=kolonne_map_borte).copy()
    borte_df["VANT"] = 1 - df["HJEMME_VANT"].values  # Bortelaget vant det motsatte
    borte_df["ER_HJEMME"] = 0

    # Slå sammen til én tabell
    alle = pd.concat([hjemme_df, borte_df], ignore_index=True)
    alle = alle.sort_values(["TEAM_ID", "DATO"]).reset_index(drop=True)

    # Beregn rullende statistikk per lag
    stats_kolonner = ["PTS", "FG_PCT", "FT_PCT", "FG3_PCT", "REB", "AST", "TOV", "PLUS_MINUS", "VANT"]

    for kol in stats_kolonner:
        # shift(1) betyr "bruk forrige kamps verdi" – ikke dagens
        # Dette er avgjørende for å unngå "data leakage"!
        alle[f"RULL_{kol}"] = (
            alle.groupby("TEAM_ID")[kol]
            .transform(lambda x: x.shift(1).rolling(window=vindu, min_periods=3).mean())
        )

    return alle

print("Beregner rullende lagstatistikk (siste 10 kamper)...")
lag_stats = beregn_lag_form(df, vindu=10)

# -------------------------------------------------------
# 3. Koble lagstatistikk tilbake til kampene
# -------------------------------------------------------
print("Kobler statistikk til kampene...")

hjemme_stats = lag_stats[lag_stats["ER_HJEMME"] == 1].copy()
borte_stats  = lag_stats[lag_stats["ER_HJEMME"] == 0].copy()

# Rename kolonner så vi vet hvem som er hvem
rull_kolonner = [k for k in hjemme_stats.columns if k.startswith("RULL_")]

hjemme_features = hjemme_stats[["GAME_ID"] + rull_kolonner].rename(
    columns={k: f"HJEMME_{k}" for k in rull_kolonner}
)
borte_features = borte_stats[["GAME_ID"] + rull_kolonner].rename(
    columns={k: f"BORTE_{k}" for k in rull_kolonner}
)

# Merge med kamp-tabellen
features_df = df[["GAME_ID", "GAME_DATE_HJEMME", "TEAM_ABBREVIATION_HJEMME",
                   "TEAM_ABBREVIATION_BORTE", "HJEMME_VANT"]].copy()
features_df = features_df.merge(hjemme_features, on="GAME_ID")
features_df = features_df.merge(borte_features, on="GAME_ID")

# -------------------------------------------------------
# 4. Legg til differanse-features
# -------------------------------------------------------
# Modeller liker ofte "differansen mellom lagene" som feature
# F.eks.: hjemmelagets snittpoeng MINUS bortelagets snittpoeng

for stat in ["PTS", "FG_PCT", "REB", "AST", "TOV", "PLUS_MINUS", "VANT"]:
    hjemme_kol = f"HJEMME_RULL_{stat}"
    borte_kol  = f"BORTE_RULL_{stat}"
    if hjemme_kol in features_df.columns and borte_kol in features_df.columns:
        features_df[f"DIFF_{stat}"] = features_df[hjemme_kol] - features_df[borte_kol]

# -------------------------------------------------------
# 5. Fjern rader med manglende verdier
# -------------------------------------------------------
# De første kampene i sesongen har ikke nok historikk
antall_for = len(features_df)
features_df = features_df.dropna()
antall_etter = len(features_df)

print(f"Fjernet {antall_for - antall_etter} rader pga. manglende historikk")
print(f"Gjenstående kamper til modellering: {antall_etter}")

# -------------------------------------------------------
# 6. Lagre
# -------------------------------------------------------
features_df.to_csv("nba_features.csv", index=False)
print(f"\nFeatures lagret til 'nba_features.csv'")
print("\nEksempel på features:")
diff_kol = [k for k in features_df.columns if k.startswith("DIFF_")]
print(features_df[["TEAM_ABBREVIATION_HJEMME", "TEAM_ABBREVIATION_BORTE",
                    "HJEMME_VANT"] + diff_kol[:4]].head())

print("\nKjør nå 03_tren_modell.py!")
