"""
Debug: Finn Minnesota vs Denver resultatet manuelt
"""
from nba_api.stats.endpoints import leaguegamefinder
from teams import finn_lag
from datetime import datetime, timedelta
import time

KAMP_DATO  = "2026-05-27"
HJEMME_LAG = "Oklahoma City Thunder"
BORTE_LAG  = "San Antonio Spurs"

hjemme_info = finn_lag(HJEMME_LAG)
borte_info  = finn_lag(BORTE_LAG)

print(f"Hjemme: {hjemme_info['full_name']} (ID: {hjemme_info['id']}, abbr: {hjemme_info['abbreviation']})")
print(f"Borte:  {borte_info['full_name']} (ID: {borte_info['id']}, abbr: {borte_info['abbreviation']})")

# Prøv ±2 dager rundt kampdatoen
fra = (datetime.strptime(KAMP_DATO, "%Y-%m-%d") - timedelta(days=1)).strftime("%m/%d/%Y")
til = (datetime.strptime(KAMP_DATO, "%Y-%m-%d") + timedelta(days=2)).strftime("%m/%d/%Y")

print(f"\nSøker fra {fra} til {til}...\n")

# Søk med Minnesota sin ID
finder = leaguegamefinder.LeagueGameFinder(
    team_id_nullable=hjemme_info["id"],
    date_from_nullable=fra,
    date_to_nullable=til,
    league_id_nullable="00"
)
df = finder.get_data_frames()[0]
time.sleep(0.6)

if df.empty:
    print("❌ Ingen kamper funnet for Minnesota i denne perioden")
else:
    print(f"Fant {len(df)} kamp(er) for Minnesota:")
    print(df[["GAME_DATE", "MATCHUP", "WL", "PTS"]].to_string(index=False))

# Søk med Denver sin ID også
print()
finder2 = leaguegamefinder.LeagueGameFinder(
    team_id_nullable=borte_info["id"],
    date_from_nullable=fra,
    date_to_nullable=til,
    league_id_nullable="00"
)
df2 = finder2.get_data_frames()[0]
time.sleep(0.6)

if df2.empty:
    print("❌ Ingen kamper funnet for Denver i denne perioden")
else:
    print(f"Fant {len(df2)} kamp(er) for Denver:")
    print(df2[["GAME_DATE", "MATCHUP", "WL", "PTS"]].to_string(index=False))
