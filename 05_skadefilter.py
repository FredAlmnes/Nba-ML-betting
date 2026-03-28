"""
STEG 5: Skadefilter (optimalisert versjon)
===========================================
Bruker LeagueDashPlayerStats med last_n_games=3 – bare ÉN API-forespørsel
for alle spillere i hele NBA på én gang. Mye raskere og færre timeouts.

Logikk:
  1. Hent alle spilleres snitt siste 3 kamper (1 kall)
  2. Hent alle spilleres sesongsnitt (1 kall) for å finne toppspillere
  3. Sammenlign – er toppspilleren borte fra siste 3 kamper? -> flagg betten
"""

import pandas as pd
import time
from nba_api.stats.endpoints import leaguedashplayerstats
from nba_api.stats.static import teams

# -------------------------------------------------------
# Konfigurasjon
# -------------------------------------------------------
ANTALL_TOPPSPILLERE = 3     # Sjekk de N viktigste spillerne per lag
MIN_MINUTTER        = 20    # Ignorer spillere med under 20 min/kamp (sesongsnitt)
SESONG              = "2024-25"

# -------------------------------------------------------
# 1. Hent alle spilleres stats – bare 2 API-kall totalt!
# -------------------------------------------------------
print("Henter spillerstatistikk fra NBA (siste 3 kamper)...")
siste3 = leaguedashplayerstats.LeagueDashPlayerStats(
    season=SESONG,
    season_type_all_star="Regular Season",
    last_n_games=3
).get_data_frames()[0]
print(f"  Hentet data for {len(siste3)} spillere")

time.sleep(1.5)

print("Henter sesongsnitt (for å identifisere toppspillere)...")
sesong_snitt = leaguedashplayerstats.LeagueDashPlayerStats(
    season=SESONG,
    season_type_all_star="Regular Season",
    last_n_games=0   # 0 = hele sesongen
).get_data_frames()[0]
print(f"  Hentet data for {len(sesong_snitt)} spillere\n")

# -------------------------------------------------------
# 2. Finn toppspillere per lag (etter sesongsnitt minutter)
# -------------------------------------------------------
def hent_toppspillere_for_lag(team_id, antall=3):
    lag_spillere = sesong_snitt[
        (sesong_snitt["TEAM_ID"] == team_id) &
        (sesong_snitt["MIN"] >= MIN_MINUTTER)
    ].sort_values("MIN", ascending=False).head(antall)
    return lag_spillere[["PLAYER_ID", "PLAYER_NAME", "MIN"]].to_dict("records")

# -------------------------------------------------------
# 3. Sjekk om toppspillere er med i siste 3 kamper
# -------------------------------------------------------
def sjekk_spiller(spiller_id, spiller_navn, sesong_min):
    """
    Sjekker om spilleren er i siste-3-kamper-datasettet med
    et fornuftig antall minutter.
    """
    siste = siste3[siste3["PLAYER_ID"] == spiller_id]

    if siste.empty or siste["GP"].iloc[0] == 0:
        return False, f"{spiller_navn} ({sesong_min:.0f} min/kamp) – 0 kamper siste 3"

    gp  = siste["GP"].iloc[0]
    min_snitt = siste["MIN"].iloc[0]

    if gp < 2 or min_snitt < 10:
        return False, f"{spiller_navn} ({sesong_min:.0f} min/kamp) – kun {gp} kamp(er), {min_snitt:.0f} min"

    return True, f"{spiller_navn} ({sesong_min:.0f} min/kamp) – {gp} kamper, {min_snitt:.0f} min"


def sjekk_lag_helse(team_id, lagnavn):
    toppspillere = hent_toppspillere_for_lag(team_id, ANTALL_TOPPSPILLERE)

    resultat = {
        "lagnavn":      lagnavn,
        "tilgjengelig": True,
        "advarsler":    []
    }

    print(f"  {lagnavn}:")
    for sp in toppspillere:
        ok, melding = sjekk_spiller(sp["PLAYER_ID"], sp["PLAYER_NAME"], sp["MIN"])
        ikon = "✅" if ok else "⚠️ "
        print(f"    {ikon} {melding}")
        if not ok:
            resultat["tilgjengelig"] = False
            resultat["advarsler"].append(melding)

    if not toppspillere:
        print(f"    (Ingen spillere med >{MIN_MINUTTER} min/kamp funnet)")

    return resultat


# -------------------------------------------------------
# 4. Les inn value bets og kjør filteret
# -------------------------------------------------------
print("=" * 60)
print("SKADEFILTER FOR DAGENS VALUE BETS")
print("=" * 60)

try:
    value_df = pd.read_csv("value_bets_idag.csv")
except FileNotFoundError:
    print("Finner ikke 'value_bets_idag.csv' – kjør 04_value_detector.py først!")
    exit()

print(f"Sjekker {len(value_df)} value bets\n")

# Lag oppslagstabell: lagnavn -> team_id
alle_lag = teams.get_teams()
lag_oppslag = {}
for lag in alle_lag:
    lag_oppslag[lag["full_name"]] = lag["id"]
    lag_oppslag[lag["nickname"]]  = lag["id"]

cache          = {}
filtrerte_bets = []

for _, rad in value_df.iterrows():
    kamp = rad["Kamp"]
    bet  = rad["Bet"]

    deler       = kamp.split(" vs ")
    hjemme_navn = deler[0].strip()
    borte_navn  = deler[1].strip()

    print(f"\n{'─'*50}")
    print(f"Kamp: {kamp}")
    print(f"Bet:  {bet}")

    advarsler = []

    for lagnavn in [hjemme_navn, borte_navn]:
        if lagnavn in cache:
            status = cache[lagnavn]
        else:
            team_id = None
            for nøkkel, tid in lag_oppslag.items():
                if nøkkel.lower() in lagnavn.lower() or lagnavn.lower() in nøkkel.lower():
                    team_id = tid
                    break

            if not team_id:
                print(f"  ⚠️  Finner ikke team-ID for {lagnavn}")
                continue

            status = sjekk_lag_helse(team_id, lagnavn)
            cache[lagnavn] = status

        for advarsel in status["advarsler"]:
            advarsler.append(f"{lagnavn}: {advarsel}")

    bet_rad = rad.to_dict()
    if advarsler:
        bet_rad["Skadestatus"] = "⚠️  USIKKER"
        bet_rad["Skadeinfo"]   = " | ".join(advarsler)
        print(f"  → BET FLAGGET SOM USIKKER")
        for a in advarsler:
            print(f"     ⚠️  {a}")
    else:
        bet_rad["Skadestatus"] = "✅ OK"
        bet_rad["Skadeinfo"]   = "Alle nøkkelspillere spilte siste 3 kamper"
        print(f"  → ✅ Alle nøkkelspillere tilgjengelige")

    filtrerte_bets.append(bet_rad)

# -------------------------------------------------------
# 5. Oppsummering
# -------------------------------------------------------
print("\n" + "=" * 60)
print("ENDELIG OPPSUMMERING ETTER SKADEFILTER")
print("=" * 60)

resultat_df = pd.DataFrame(filtrerte_bets)

ok_bets     = resultat_df[resultat_df["Skadestatus"].str.contains("OK")]
usikre_bets = resultat_df[resultat_df["Skadestatus"].str.contains("USIKKER")]

if not ok_bets.empty:
    print(f"\n✅ ANBEFALTE BETS ({len(ok_bets)} stk):")
    print(ok_bets[["Kamp", "Bet", "Odds", "Modell %", "Value", "Forv. EV"]].to_string(index=False))

if not usikre_bets.empty:
    print(f"\n⚠️  USIKRE BETS – MULIGE SKADER ({len(usikre_bets)} stk):")
    print(usikre_bets[["Kamp", "Bet", "Odds", "Skadeinfo"]].to_string(index=False))

if ok_bets.empty and usikre_bets.empty:
    print("Ingen bets å vise.")

resultat_df.to_csv("value_bets_med_skadefilter.csv", index=False)
print(f"\nResultat lagret til 'value_bets_med_skadefilter.csv'")
print("\n⚠️  Husk: Spill alltid ansvarlig.")
