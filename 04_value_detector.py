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

Nøkkelen leses fra miljøvariabelen ODDS_API_NOKKEL via en .env-fil.
Kopier .env.example til .env og fyll inn din egen nøkkel der.
"""

import os
import sys
import requests
import pickle
import pandas as pd
import numpy as np
from nba_api.stats.endpoints import leaguegamefinder, teamgamelogs
from modell_utils import KalibrertModell  # nødvendig for å laste pickle
from strategy import fjern_vigorish, beregn_value_og_ev
from teams import finn_lag_id
from config import MIN_VALUE_TERSKEL, MIN_ODDS, MAX_ODDS
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------------
# KONFIGURASJON – ENDRE DISSE
# -------------------------------------------------------
API_NØKKEL = os.environ.get("ODDS_API_NOKKEL")
if not API_NØKKEL:
    print("FEIL: Miljøvariabelen ODDS_API_NOKKEL er ikke satt.")
    print("Kopier .env.example til .env og fyll inn din egen nøkkel:")
    print("  ODDS_API_NOKKEL=din-nøkkel-her")
    print("Hent en gratis nøkkel fra https://the-odds-api.com")
    sys.exit(1)  # NB: bare exit() gir exitkode 0 (=suksess) og gjemmer feilen for 06_bot.py
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
    import sys
    sys.exit(1)  # NB: bare exit() gir exitkode 0 (=suksess) og gjemmer feilen for 06_bot.py

kamper = respons.json()
print(f"Fant {len(kamper)} NBA-kamper med odds")

# Vis hvor mange API-kall vi har igjen
print(f"Gjenstående API-kall denne måneden: {respons.headers.get('x-requests-remaining', 'ukjent')}")

# -------------------------------------------------------
# 3. Hent fersk lagstatistikk for å lage features
# -------------------------------------------------------
print("\nHenter fersk lagstatistikk fra NBA...")

def gjeldende_sesong():
    """Returnerer NBA-sesongen for inneværende dato, f.eks. '2025-26'."""
    år = datetime.now().year
    måned = datetime.now().month
    # NBA-sesongen starter i oktober – hvis vi er før oktober er vi i fjorårets sesong
    if måned >= 10:
        return f"{år}-{str(år + 1)[-2:]}"
    else:
        return f"{år - 1}-{str(år)[-2:]}"

def hent_siste_lagstats(team_id, antall_kamper=10):
    """Henter siste N kamper for et lag og beregner snittet."""
    sesong = gjeldende_sesong()
    logs = teamgamelogs.TeamGameLogs(
        team_id_nullable=team_id,
        season_nullable=sesong,
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

    # Finn lag-IDs. NB: resolusjonsrekkefølgen endres bevisst her — den gamle
    # heuristikken prøvde kallenavn (siste ord) først og hele navnet som
    # fallback; teams.finn_lag() prøver eksakt match (alle tre nøkkeltyper)
    # først og substreng-fallback etterpå. Begge løser de samme navnene
    # (bevist av test_odds_api_navn_loses i tests/test_teams.py), men
    # REKKEFØLGEN de prøver ting i er ulik — se 02-04-SUMMARY.md.
    hjemme_id = finn_lag_id(hjemme_navn)
    borte_id  = finn_lag_id(borte_navn)

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

    # Vig-fri normalisering og value/EV-beregning bor nå i strategy.py, slik
    # at Phase 5-backtesten regner disse identisk med live-veien.
    impl_sann_hjemme, impl_sann_borte = fjern_vigorish(beste_hjemme_odds, beste_borte_odds)
    value_hjemme, ev_hjemme = beregn_value_og_ev(modell_sann_hjemme, beste_hjemme_odds, impl_sann_hjemme)
    value_borte,  ev_borte  = beregn_value_og_ev(modell_sann_borte,  beste_borte_odds,  impl_sann_borte)

    print(f"\n{hjemme_navn} vs {borte_navn}")
    print(f"  Modell:     Hjemme {modell_sann_hjemme:.1%}  |  Borte {modell_sann_borte:.1%}")
    print(f"  Bookmaker:  Hjemme {impl_sann_hjemme:.1%}  |  Borte {impl_sann_borte:.1%}")
    print(f"  Beste odds: Hjemme {beste_hjemme_odds} ({beste_hjemme_book}) | Borte {beste_borte_odds} ({beste_borte_book})")
    print(f"  Value:      Hjemme {value_hjemme:+.1%}  |  Borte {value_borte:+.1%}")
    print(f"  Forv. EV:   Hjemme {ev_hjemme:+.1%}  |  Borte {ev_borte:+.1%}")

    # Trekk ut faktisk kampdato fra Odds API (UTC → dato-streng)
    kamp_dato_str = kamp_tid[:10] if kamp_tid else str(datetime.now().date())

    # Flagg value bets
    if value_hjemme > MIN_VALUE_TERSKEL and MIN_ODDS <= beste_hjemme_odds <= MAX_ODDS:
        value_bets.append({
            "Kamp":         f"{hjemme_navn} vs {borte_navn}",
            "KampDato":     kamp_dato_str,
            "Bet":          f"Hjemme ({hjemme_navn})",
            "Odds":         beste_hjemme_odds,
            "Bookmaker":    beste_hjemme_book,
            "Modell_prob":  round(modell_sann_hjemme, 4),   # rå float til Kelly
            "Modell %":     f"{modell_sann_hjemme:.1%}",
            "Bookmaker %":  f"{impl_sann_hjemme:.1%}",
            "Value":        f"{value_hjemme:+.1%}",
            "Forv. EV":     f"{ev_hjemme:+.1%}"
        })

    if value_borte > MIN_VALUE_TERSKEL and MIN_ODDS <= beste_borte_odds <= MAX_ODDS:
        value_bets.append({
            "Kamp":         f"{hjemme_navn} vs {borte_navn}",
            "KampDato":     kamp_dato_str,
            "Bet":          f"Borte ({borte_navn})",
            "Odds":         beste_borte_odds,
            "Bookmaker":    beste_borte_book,
            "Modell_prob":  round(modell_sann_borte, 4),    # rå float til Kelly
            "Modell %":     f"{modell_sann_borte:.1%}",
            "Bookmaker %":  f"{impl_sann_borte:.1%}",
            "Value":        f"{value_borte:+.1%}",
            "Forv. EV":     f"{ev_borte:+.1%}"
        })

# -------------------------------------------------------
# 5. Vis oppsummering av value bets
# -------------------------------------------------------
print("\n" + "="*60)
print("OPPSUMMERING: VALUE BETS I DAG")
print("="*60)

# VIKTIG: skriv alltid til value_bets_idag.csv, også når vi ikke fant noen
# value bets (f.eks. NBA-sommerpause). Ellers ligger gårsdagens (eller forrige
# måneds!) fil igjen urørt, og 05/06 vil stille-gjenbruke gamle, allerede
# spilte kamper som om de var dagens anbefalinger.
KOLONNER = ["Kamp", "KampDato", "Bet", "Odds", "Bookmaker", "Modell_prob",
            "Modell %", "Bookmaker %", "Value", "Forv. EV"]

if value_bets:
    value_df = pd.DataFrame(value_bets)
    print(value_df.to_string(index=False))
    value_df.to_csv("value_bets_idag.csv", index=False)
    print(f"\n{len(value_bets)} value bet(s) funnet og lagret til 'value_bets_idag.csv'")
else:
    print("Ingen value bets funnet i dag med gjeldende terskelverdier.")
    print(f"(Terskel: {MIN_VALUE_TERSKEL:.0%} value, odds mellom {MIN_ODDS}–{MAX_ODDS})")
    pd.DataFrame(columns=KOLONNER).to_csv("value_bets_idag.csv", index=False)
    print("'value_bets_idag.csv' tømt/oppdatert (ingen anbefalinger i dag).")

print("\n⚠️  ADVARSEL: Bruk dette som læringsverktøy, ikke som garanti for profitt.")
print("   Spill alltid ansvarlig og ikke bett mer enn du har råd til å tape.")
