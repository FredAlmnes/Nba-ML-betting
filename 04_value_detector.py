"""
STEG 4: Value Detector – finn gode bets
=========================================
Dette er hjertet av systemet!

Vi henter dagens NBA-odds fra The Odds API, bruker modellen
vår til å beregne "riktige" sannsynligheter, og flagger
kamper der bookmakerens implisitte sannsynlighet divergerer
fra vår modell.

Du trenger en gratis API-nøkkel fra:
https://the-odds-api.com (500 kall/måned gratis)

Sett inn din nøkkel i API_NØKKEL-variabelen under.
"""

import requests
import pickle
import pandas as pd
import numpy as np
from nba_api.stats.endpoints import leaguegamefinder, teamgamelogs
from nba_api.stats.static import teams
import time
from datetime import datetime, timedelta

# -------------------------------------------------------
# KONFIGURASJON – ENDRE DISSE
# -------------------------------------------------------
API_NØKKEL = "afc4f647c551e760f59f837769f5a3a1"  # the-odds-api.com
MIN_VALUE_TERSKEL = 0.05            # Flagg bets der vi er 5%+ over bookmaker
MIN_ODDS = 1.50                     # Ikke bett på favoritter med veldig lave odds
# -------------------------------------------------------

# -------------------------------------------------------
# 1. Last inn modellen
# -------------------------------------------------------
print("Laster inn trent modell...")
with open("nba_modell.pkl", "rb") as f:
    data = pickle.load(f)

modell = data["modell"]
feature_kolonner = data["feature_kolonner"]
print("Modell lastet!")

# -------------------------------------------------------
# 2. Hent dagens NBA-odds fra The Odds API
# -------------------------------------------------------
print("\nHenter dagens NBA-odds...")

url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/"
params = {
    "apiKey": API_NØKKEL,
    "regions": "eu",           # Europeiske bookmakers
    "markets": "h2h",          # Head-to-head (moneyline) odds
    "oddsFormat": "decimal",   # Desimalodds (f.eks. 2.10)
    "dateFormat": "iso"
}

respons = requests.get(url, params=params)

if respons.status_code != 200:
    print(f"Feil ved henting av odds: {respons.status_code}")
    print(respons.text)
    exit()

kamper = respons.json()
print(f"Fant {len(kamper)} NBA-kamper med odds")

# Vis hvor mange API-kall vi har igjen
print(f"Gjenstående API-kall denne måneden: {respons.headers.get('x-requests-remaining', 'ukjent')}")

# -------------------------------------------------------
# 3. Hent fersk lagstatistikk for å lage features
# -------------------------------------------------------
print("\nHenter fersk lagstatistikk fra NBA...")

def hent_siste_lagstats(team_id, antall_kamper=10):
    """Henter siste N kamper for et lag og beregner snittet."""
    logs = teamgamelogs.TeamGameLogs(
        team_id_nullable=team_id,
        season_nullable="2024-25",
        season_type_nullable="Regular Season"
    )
    df = logs.get_data_frames()[0].head(antall_kamper)
    time.sleep(0.5)  # Rate limiting

    if len(df) < 3:
        return None

    return {
        "PTS":        df["PTS"].mean(),
        "FG_PCT":     df["FG_PCT"].mean(),
        "FT_PCT":     df["FT_PCT"].mean(),
        "FG3_PCT":    df["FG3_PCT"].mean(),
        "REB":        df["REB"].mean(),
        "AST":        df["AST"].mean(),
        "TOV":        df["TOV"].mean(),
        "PLUS_MINUS": df["PLUS_MINUS"].mean(),
        "VANT":       (df["WL"] == "W").mean()
    }

# Lag oppslagstabell: lagnavn -> team_id
alle_lag = teams.get_teams()
lag_oppslag = {}
for lag in alle_lag:
    lag_oppslag[lag["full_name"].lower()] = lag["id"]
    lag_oppslag[lag["abbreviation"].lower()] = lag["id"]
    # Legg til korte navn (f.eks. "lakers" -> Lakers ID)
    lag_oppslag[lag["nickname"].lower()] = lag["id"]

# -------------------------------------------------------
# 4. Beregn modellens sannsynligheter og finn value
# -------------------------------------------------------
print("\n" + "="*60)
print("VALUE BETS FOR DAGENS NBA-KAMPER")
print("="*60)

value_bets = []

for kamp in kamper:
    hjemme_navn = kamp["home_team"]
    borte_navn  = kamp["away_team"]
    kamp_tid    = kamp["commence_time"]

    # Finn lag-IDs
    hjemme_id = lag_oppslag.get(hjemme_navn.lower().split()[-1])  # Prøv kallenavn
    borte_id  = lag_oppslag.get(borte_navn.lower().split()[-1])

    if not hjemme_id or not borte_id:
        # Prøv hele navnet
        hjemme_id = lag_oppslag.get(hjemme_navn.lower())
        borte_id  = lag_oppslag.get(borte_navn.lower())

    if not hjemme_id or not borte_id:
        print(f"  Kunne ikke finne lag-ID for: {hjemme_navn} vs {borte_navn}")
        continue

    # Hent statistikk
    hjemme_stats = hent_siste_lagstats(hjemme_id)
    borte_stats  = hent_siste_lagstats(borte_id)

    if not hjemme_stats or not borte_stats:
        continue

    # Bygg feature-rad for modellen
    feature_rad = {}
    stats = ["PTS", "FG_PCT", "FT_PCT", "FG3_PCT", "REB", "AST", "TOV", "PLUS_MINUS", "VANT"]

    for stat in stats:
        feature_rad[f"HJEMME_RULL_{stat}"] = hjemme_stats[stat]
        feature_rad[f"BORTE_RULL_{stat}"]  = borte_stats[stat]
        feature_rad[f"DIFF_{stat}"]        = hjemme_stats[stat] - borte_stats[stat]

    # Filtrer til bare de feature-kolonnene modellen forventer
    X = pd.DataFrame([feature_rad])[feature_kolonner]

    # Modellens sannsynlighet for at hjemmelaget vinner
    modell_sann_hjemme = modell.predict_proba(X)[0][1]
    modell_sann_borte  = 1 - modell_sann_hjemme

    # Finn beste odds fra bookmakers
    beste_hjemme_odds = 0
    beste_borte_odds  = 0
    beste_hjemme_book = ""
    beste_borte_book  = ""

    for bookmaker in kamp.get("bookmakers", []):
        for market in bookmaker.get("markets", []):
            if market["key"] == "h2h":
                for outcome in market["outcomes"]:
                    if outcome["name"] == hjemme_navn and outcome["price"] > beste_hjemme_odds:
                        beste_hjemme_odds = outcome["price"]
                        beste_hjemme_book = bookmaker["title"]
                    elif outcome["name"] == borte_navn and outcome["price"] > beste_borte_odds:
                        beste_borte_odds = outcome["price"]
                        beste_borte_book = bookmaker["title"]

    if beste_hjemme_odds == 0 or beste_borte_odds == 0:
        continue

    # Beregn implisitt sannsynlighet fra bookmaker-odds
    # (odds 2.00 -> 1/2.00 = 50% implisitt sannsynlighet)
    # NB: summen er >100% pga. bookmakerens margin ("vigorish")
    impl_sann_hjemme = 1 / beste_hjemme_odds
    impl_sann_borte  = 1 / beste_borte_odds

    # Normaliser så de summerer til 100%
    total = impl_sann_hjemme + impl_sann_borte
    impl_sann_hjemme /= total
    impl_sann_borte  /= total

    # VALUE = modellens sannsynlighet minus bookmakerens implisitte
    value_hjemme = modell_sann_hjemme - impl_sann_hjemme
    value_borte  = modell_sann_borte  - impl_sann_borte

    # Forventet verdi = (modell_sann * odds) - 1
    # Positivt EV betyr lønnsomt bet på sikt
    ev_hjemme = (modell_sann_hjemme * beste_hjemme_odds) - 1
    ev_borte  = (modell_sann_borte  * beste_borte_odds)  - 1

    print(f"\n{hjemme_navn} vs {borte_navn}")
    print(f"  Modell:     Hjemme {modell_sann_hjemme:.1%}  |  Borte {modell_sann_borte:.1%}")
    print(f"  Bookmaker:  Hjemme {impl_sann_hjemme:.1%}  |  Borte {impl_sann_borte:.1%}")
    print(f"  Beste odds: Hjemme {beste_hjemme_odds} ({beste_hjemme_book}) | Borte {beste_borte_odds} ({beste_borte_book})")
    print(f"  Value:      Hjemme {value_hjemme:+.1%}  |  Borte {value_borte:+.1%}")
    print(f"  Forv. EV:   Hjemme {ev_hjemme:+.1%}  |  Borte {ev_borte:+.1%}")

    # Flagg value bets
    if value_hjemme > MIN_VALUE_TERSKEL and beste_hjemme_odds >= MIN_ODDS:
        value_bets.append({
            "Kamp": f"{hjemme_navn} vs {borte_navn}",
            "Bet": f"Hjemme ({hjemme_navn})",
            "Odds": beste_hjemme_odds,
            "Bookmaker": beste_hjemme_book,
            "Modell %": f"{modell_sann_hjemme:.1%}",
            "Bookmaker %": f"{impl_sann_hjemme:.1%}",
            "Value": f"{value_hjemme:+.1%}",
            "Forv. EV": f"{ev_hjemme:+.1%}"
        })

    if value_borte > MIN_VALUE_TERSKEL and beste_borte_odds >= MIN_ODDS:
        value_bets.append({
            "Kamp": f"{hjemme_navn} vs {borte_navn}",
            "Bet": f"Borte ({borte_navn})",
            "Odds": beste_borte_odds,
            "Bookmaker": beste_borte_book,
            "Modell %": f"{modell_sann_borte:.1%}",
            "Bookmaker %": f"{impl_sann_borte:.1%}",
            "Value": f"{value_borte:+.1%}",
            "Forv. EV": f"{ev_borte:+.1%}"
        })

# -------------------------------------------------------
# 5. Vis oppsummering av value bets
# -------------------------------------------------------
print("\n" + "="*60)
print("OPPSUMMERING: VALUE BETS I DAG")
print("="*60)

if value_bets:
    value_df = pd.DataFrame(value_bets)
    print(value_df.to_string(index=False))
    value_df.to_csv("value_bets_idag.csv", index=False)
    print(f"\n{len(value_bets)} value bet(s) funnet og lagret til 'value_bets_idag.csv'")
else:
    print("Ingen value bets funnet i dag med gjeldende terskelverdier.")
    print(f"(Terskel: {MIN_VALUE_TERSKEL:.0%} value, min odds {MIN_ODDS})")

print("\n⚠️  ADVARSEL: Bruk dette som læringsverktøy, ikke som garanti for profitt.")
print("   Spill alltid ansvarlig og ikke bett mer enn du har råd til å tape.")
