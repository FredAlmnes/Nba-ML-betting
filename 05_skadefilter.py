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
from teams import finn_lag_id

# -------------------------------------------------------
# Konfigurasjon
# -------------------------------------------------------
ANTALL_TOPPSPILLERE = 3     # Sjekk de N viktigste spillerne per lag
MIN_MINUTTER        = 20    # Ignorer spillere med under 20 min/kamp (sesongsnitt)

from datetime import datetime as _dt
def _gjeldende_sesong():
    """Beregner NBA-sesong dynamisk, f.eks. '2025-26'."""
    år = _dt.now().year
    måned = _dt.now().month
    if måned >= 10:
        return f"{år}-{str(år + 1)[-2:]}"
    else:
        return f"{år - 1}-{str(år)[-2:]}"

SESONG = _gjeldende_sesong()
print(f"Bruker sesong: {SESONG}")

# -------------------------------------------------------
# 1. Hent alle spilleres stats – sjekker Regular Season + Playoffs
# -------------------------------------------------------

def _hent_spillerdata(season_type, last_n=0):
    """Henter spillerdata for gitt season_type. Returnerer tom DataFrame ved feil."""
    try:
        df = leaguedashplayerstats.LeagueDashPlayerStats(
            season=SESONG,
            season_type_all_star=season_type,
            last_n_games=last_n
        ).get_data_frames()[0]
        time.sleep(1.0)
        return df
    except Exception as e:
        print(f"  (Kunne ikke hente {season_type} data: {e})")
        return pd.DataFrame()

print("Henter spillerstatistikk fra NBA (siste 3 kamper – Regular Season)...")
siste3_reg = _hent_spillerdata("Regular Season", last_n=3)
print(f"  Hentet data for {len(siste3_reg)} spillere (Regular Season)")

print("Henter spillerstatistikk fra NBA (siste 3 kamper – Playoffs)...")
siste3_play = _hent_spillerdata("Playoffs", last_n=3)
print(f"  Hentet data for {len(siste3_play)} spillere (Playoffs)")

# Slå sammen: behold Playoffs-data der det finnes, ellers Regular Season
if not siste3_play.empty and not siste3_reg.empty:
    siste3 = pd.concat([siste3_play, siste3_reg]).drop_duplicates(subset=["PLAYER_ID"], keep="first").reset_index(drop=True)
elif not siste3_play.empty:
    siste3 = siste3_play
else:
    siste3 = siste3_reg
print(f"  Totalt {len(siste3)} unike spillere etter sammenslåing\n")

print("Henter sesongsnitt (for å identifisere toppspillere – Regular Season)...")
sesong_reg = _hent_spillerdata("Regular Season", last_n=0)
print("Henter sesongsnitt (Playoffs)...")
sesong_play = _hent_spillerdata("Playoffs", last_n=0)

# For sesongsnitt: summer minutter fra begge (Regular + Playoffs)
if not sesong_play.empty and not sesong_reg.empty:
    sesong_snitt = pd.concat([sesong_play, sesong_reg]).groupby("PLAYER_ID", as_index=False).agg(
        PLAYER_NAME=("PLAYER_NAME", "first"),
        TEAM_ID=("TEAM_ID", "first"),
        MIN=("MIN", "sum")
    )
elif not sesong_play.empty:
    sesong_snitt = sesong_play
else:
    sesong_snitt = sesong_reg
print(f"  Totalt {len(sesong_snitt)} unike spillere i sesongsnitt\n")

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

if value_df.empty:
    print("Ingen value bets å sjekke – skriver tom fil og avslutter.")
    pd.DataFrame(columns=list(value_df.columns) + ["Skadestatus", "Skadeinfo"]).to_csv(
        "value_bets_med_skadefilter.csv", index=False)
    exit()

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
            # NB: teams.finn_lag_id() matcher også på forkortelse (abbreviation),
            # noe denne filens gamle full_name/nickname-only-oppslag ikke gjorde.
            # Dette utvider treffoverflaten (flere navn matcher), det snevrer
            # den aldri inn — en bevisst, dokumentert forening, ikke en
            # regresjon. Se 02-04-SUMMARY.md.
            team_id = finn_lag_id(lagnavn)

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
