"""
STEG 1: Hent historiske NBA-data
=================================
Dette scriptet henter kampresultater og lagstatistikk fra NBA
ved hjelp av nba_api-biblioteket (gratis, ingen API-nøkkel nødvendig).

Kjør dette scriptet først for å laste ned data lokalt.
Det lagrer en CSV-fil som de andre scriptene bruker.
"""

import pandas as pd
import time
from nba_api.stats.endpoints import leaguegamefinder, teamgamelogs
from nba_api.stats.static import teams

# -------------------------------------------------------
# 1. Hent liste over alle NBA-lag
# -------------------------------------------------------
print("Henter liste over alle NBA-lag...")
alle_lag = teams.get_teams()
print(f"Fant {len(alle_lag)} lag")

# Lag en rask oppslagsbok: team_id -> navn
lag_navn = {lag["id"]: lag["full_name"] for lag in alle_lag}

# -------------------------------------------------------
# 2. Hent kampresultater for de siste sesongene
# -------------------------------------------------------
sesonger = ["2022-23", "2023-24", "2024-25"]
alle_kamper = []

for sesong in sesonger:
    print(f"\nHenter kamper for sesong {sesong}...")

    # LeagueGameFinder gir oss alle kampresultater i en sesong
    gamefinder = leaguegamefinder.LeagueGameFinder(
        season_nullable=sesong,
        league_id_nullable="00",          # 00 = NBA
        season_type_nullable="Regular Season"
    )

    kamper_df = gamefinder.get_data_frames()[0]
    alle_kamper.append(kamper_df)

    print(f"  Fant {len(kamper_df)} rader (en rad per lag per kamp)")

    # Viktig: nba_api har rate limiting, så vi venter litt mellom kall
    time.sleep(1)

# Slå sammen alle sesongene til én stor tabell
df = pd.concat(alle_kamper, ignore_index=True)

print(f"\nTotalt {len(df)} rader hentet")
print("\nKolonner tilgjengelig:")
print(df.columns.tolist())

# -------------------------------------------------------
# 3. Forstå datastrukturen
# -------------------------------------------------------
# nba_api gir én rad PER LAG PER KAMP.
# Det betyr at en kamp mellom Lakers og Celtics gir 2 rader:
#   - En for Lakers sin perspektiv
#   - En for Celtics sin perspektiv
#
# Kolonnen WL forteller om laget vant (W) eller tapte (L)
# MATCHUP ser slik ut:
#   "LAL vs. BOS"  -> hjemmekamp for LAL
#   "LAL @ BOS"    -> bortekamp for LAL

print("\nEksempel på data (første 5 rader):")
print(df[["GAME_DATE", "TEAM_ABBREVIATION", "MATCHUP", "WL",
          "PTS", "FG_PCT", "REB", "AST"]].head())

# -------------------------------------------------------
# 4. Gjør om til én rad per kamp (hjemme vs borte)
# -------------------------------------------------------
print("\nOmformer til én rad per kamp...")

# Skill ut hjemmekamper og bortekamper
hjemme = df[df["MATCHUP"].str.contains("vs.")].copy()
borte  = df[df["MATCHUP"].str.contains("@")].copy()

# Merge på GAME_ID så vi får hjemme- og bortelag på samme rad
kamp_df = hjemme.merge(
    borte,
    on="GAME_ID",
    suffixes=("_HJEMME", "_BORTE")
)

# Lag en enkel vinner-kolonne (1 = hjemmelaget vant, 0 = bortelaget vant)
kamp_df["HJEMME_VANT"] = (kamp_df["WL_HJEMME"] == "W").astype(int)

print(f"Antall kamper (en rad per kamp): {len(kamp_df)}")
print(f"\nHjemmelaget vant: {kamp_df['HJEMME_VANT'].mean():.1%} av kampene")
print("(Typisk er hjemmefordelen rundt 58-60% i NBA)")

# -------------------------------------------------------
# 5. Lagre til CSV
# -------------------------------------------------------
filnavn = "nba_kamper_raw.csv"
kamp_df.to_csv(filnavn, index=False)
print(f"\nData lagret til '{filnavn}'")
print("Kjør nå 02_feature_engineering.py for neste steg!")
