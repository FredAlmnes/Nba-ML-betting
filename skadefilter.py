"""
Delt modul for skadefilter-beslutningslogikk.

Erstatter den gamle 05_skadefilter.py, som utførte alt — inkludert fire
nba_api-nettverkskall og en `print(f"Bruker sesong: {SESONG}")` — på
modul-nivå ved import. Det gjorde filen umulig å importere trygt fra
06_bot.py (som derfor måtte kjøre den som en subprocess i stedet).

Denne modulen gjør ingen nettverkskall bare ved `import skadefilter` — alle
nba_api-kall skjer inne i funksjoner, og kalles først når noen faktisk ber
om ferske data (hent_spillerstatistikk / filtrer_bets_for_skader uten
injiserte DataFrames). Dette gjør beslutningslogikken testbar uten nettverk
og importerbar i prosess av 06_bot.py (plan 04-08).

05_skadefilter.py er nå en tynn CLI-wrapper som importerer herfra.
"""

import time
from datetime import datetime as _dt

import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats

from teams import finn_lag_id

# -------------------------------------------------------
# Konfigurasjon
# -------------------------------------------------------
ANTALL_TOPPSPILLERE = 3     # Sjekk de N viktigste spillerne per lag
MIN_MINUTTER = 20           # Ignorer spillere med under 20 min/kamp (sesongsnitt)


def gjeldende_sesong():
    """
    Beregner NBA-sesong dynamisk, f.eks. '2025-26'.

    NB: denne funksjonen og gjeldende_sesong() i verdi_deteksjon.py (plan
    04-06, tidligere 04_value_detector.py) er samme NBA-sesong-utledning,
    duplisert i to filer. Begge ekstraheres i denne fasen, men
    04-CONTEXT.md skoper ikke en delt sesong-modul, og dette var aldri ett
    av Phase 2 D-03s fire oppførte duplikater — det er derfor ikke fikset
    her. Flagget som et konsolideringspunkt for Phase 5, samme behandling
    som DIFF_-kolonne-divergensen fikk i 02-05-SUMMARY.md.
    """
    år = _dt.now().year
    måned = _dt.now().month
    if måned >= 10:
        return f"{år}-{str(år + 1)[-2:]}"
    else:
        return f"{år - 1}-{str(år)[-2:]}"


def hent_spillerdata(season_type, sesong, last_n=0):
    """Henter spillerdata for gitt season_type/sesong. Returnerer tom DataFrame ved feil."""
    try:
        df = leaguedashplayerstats.LeagueDashPlayerStats(
            season=sesong,
            season_type_all_star=season_type,
            last_n_games=last_n
        ).get_data_frames()[0]
        time.sleep(1.0)  # Rate limiting
        return df
    except Exception as e:
        print(f"  (Kunne ikke hente {season_type} data: {e})")
        return pd.DataFrame()


def hent_spillerstatistikk(sesong=None):
    """
    Henter spillerstatistikk for hele NBA: siste 3 kamper og sesongsnitt,
    for Regular Season og Playoffs. Gjør de fire nba_api-kallene.

    'sesong' er None som standard, som betyr "bruk gjeldende_sesong()".
    Dette keyword-injeksjonspunktet er hele grunnen til at
    filtrer_bets_for_skader er testbar uten nettverk.

    Returnerer (siste3, sesong_snitt).
    """
    if sesong is None:
        sesong = gjeldende_sesong()

    print("Henter spillerstatistikk fra NBA (siste 3 kamper – Regular Season)...")
    siste3_reg = hent_spillerdata("Regular Season", sesong, last_n=3)
    print(f"  Hentet data for {len(siste3_reg)} spillere (Regular Season)")

    print("Henter spillerstatistikk fra NBA (siste 3 kamper – Playoffs)...")
    siste3_play = hent_spillerdata("Playoffs", sesong, last_n=3)
    print(f"  Hentet data for {len(siste3_play)} spillere (Playoffs)")

    # Slå sammen: behold Playoffs-data der det finnes, ellers Regular Season
    if not siste3_play.empty and not siste3_reg.empty:
        siste3 = pd.concat([siste3_play, siste3_reg]).drop_duplicates(
            subset=["PLAYER_ID"], keep="first"
        ).reset_index(drop=True)
    elif not siste3_play.empty:
        siste3 = siste3_play
    else:
        siste3 = siste3_reg
    print(f"  Totalt {len(siste3)} unike spillere etter sammenslåing\n")

    print("Henter sesongsnitt (for å identifisere toppspillere – Regular Season)...")
    sesong_reg = hent_spillerdata("Regular Season", sesong, last_n=0)
    print("Henter sesongsnitt (Playoffs)...")
    sesong_play = hent_spillerdata("Playoffs", sesong, last_n=0)

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

    return siste3, sesong_snitt


def hent_toppspillere_for_lag(sesong_snitt, team_id, antall=ANTALL_TOPPSPILLERE):
    """Finner de 'antall' spillerne med høyest sesongsnitt-minutter for et gitt lag."""
    lag_spillere = sesong_snitt[
        (sesong_snitt["TEAM_ID"] == team_id) &
        (sesong_snitt["MIN"] >= MIN_MINUTTER)
    ].sort_values("MIN", ascending=False).head(antall)
    return lag_spillere[["PLAYER_ID", "PLAYER_NAME", "MIN"]].to_dict("records")


def sjekk_spiller(siste3, spiller_id, spiller_navn, sesong_min):
    """
    Sjekker om spilleren er i siste-3-kamper-datasettet med
    et fornuftig antall minutter.
    """
    siste = siste3[siste3["PLAYER_ID"] == spiller_id]

    if siste.empty or siste["GP"].iloc[0] == 0:
        return False, f"{spiller_navn} ({sesong_min:.0f} min/kamp) – 0 kamper siste 3"

    gp = siste["GP"].iloc[0]
    min_snitt = siste["MIN"].iloc[0]

    if gp < 2 or min_snitt < 10:
        return False, f"{spiller_navn} ({sesong_min:.0f} min/kamp) – kun {gp} kamp(er), {min_snitt:.0f} min"

    return True, f"{spiller_navn} ({sesong_min:.0f} min/kamp) – {gp} kamper, {min_snitt:.0f} min"


def sjekk_lag_helse(siste3, sesong_snitt, team_id, lagnavn):
    """Sjekker et lags topp-N-spillere mot siste3-datasettet og returnerer en helsestatus-dict."""
    toppspillere = hent_toppspillere_for_lag(sesong_snitt, team_id, ANTALL_TOPPSPILLERE)

    resultat = {
        "lagnavn": lagnavn,
        "tilgjengelig": True,
        "advarsler": []
    }

    print(f"  {lagnavn}:")
    for sp in toppspillere:
        ok, melding = sjekk_spiller(siste3, sp["PLAYER_ID"], sp["PLAYER_NAME"], sp["MIN"])
        ikon = "✅" if ok else "⚠️ "
        print(f"    {ikon} {melding}")
        if not ok:
            resultat["tilgjengelig"] = False
            resultat["advarsler"].append(melding)

    if not toppspillere:
        print(f"    (Ingen spillere med >{MIN_MINUTTER} min/kamp funnet)")

    return resultat


def filtrer_bets_for_skader(value_df, siste3=None, sesong_snitt=None):
    """
    Kjører skadefilteret over value_df og returnerer en DataFrame med
    Skadestatus/Skadeinfo-kolonner lagt til.

    Injiser siste3/sesong_snitt (f.eks. fra tester) for å unngå
    nettverkskall; hvis enten er None hentes begge ferskt via
    hent_spillerstatistikk().
    """
    if siste3 is None or sesong_snitt is None:
        siste3, sesong_snitt = hent_spillerstatistikk()

    cache = {}
    filtrerte_bets = []

    for _, rad in value_df.iterrows():
        kamp = rad["Kamp"]
        bet = rad["Bet"]

        deler = kamp.split(" vs ")
        hjemme_navn = deler[0].strip()
        borte_navn = deler[1].strip()

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

                status = sjekk_lag_helse(siste3, sesong_snitt, team_id, lagnavn)
                cache[lagnavn] = status

            for advarsel in status["advarsler"]:
                advarsler.append(f"{lagnavn}: {advarsel}")

        bet_rad = rad.to_dict()
        if advarsler:
            bet_rad["Skadestatus"] = "⚠️  USIKKER"
            bet_rad["Skadeinfo"] = " | ".join(advarsler)
            print(f"  → BET FLAGGET SOM USIKKER")
            for a in advarsler:
                print(f"     ⚠️  {a}")
        else:
            bet_rad["Skadestatus"] = "✅ OK"
            bet_rad["Skadeinfo"] = "Alle nøkkelspillere spilte siste 3 kamper"
            print(f"  → ✅ Alle nøkkelspillere tilgjengelige")

        filtrerte_bets.append(bet_rad)

    return pd.DataFrame(filtrerte_bets)


def skriv_skadefilter_csv(resultat_df, sti="value_bets_med_skadefilter.csv"):
    """Skriver skadefilter-resultatet til CSV og bekrefter med en print."""
    resultat_df.to_csv(sti, index=False)
    print(f"\nResultat lagret til '{sti}'")
