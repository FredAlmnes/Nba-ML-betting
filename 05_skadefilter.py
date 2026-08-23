"""
STEG 5: Skadefilter (optimalisert versjon)
===========================================
Bruker LeagueDashPlayerStats med last_n_games=3 – bare ÉN API-forespørsel
for alle spillere i hele NBA på én gang. Mye raskere og færre timeouts.

Logikk:
  1. Hent alle spilleres snitt siste 3 kamper (1 kall)
  2. Hent alle spilleres sesongsnitt (1 kall) for å finne toppspillere
  3. Sammenlign – er toppspilleren borte fra siste 3 kamper? -> flagg betten

All beslutningslogikk (over) er flyttet til skadefilter.py, som kan
importeres uten å utløse noen nettverkskall mot NBA sin statistikk-API.
Denne filen er nå bare den frittstående CLI-inngangen — kjør
`python 05_skadefilter.py` for å lese value_bets_idag.csv og skrive
value_bets_med_skadefilter.csv, akkurat som før.
"""

import sys

import pandas as pd

import skadefilter


def main():
    sesong = skadefilter.gjeldende_sesong()
    print(f"Bruker sesong: {sesong}")

    print("=" * 60)
    print("SKADEFILTER FOR DAGENS VALUE BETS")
    print("=" * 60)

    try:
        value_df = pd.read_csv("value_bets_idag.csv")
    except FileNotFoundError:
        print("Finner ikke 'value_bets_idag.csv' – kjør 04_value_detector.py først!")
        sys.exit(1)  # NB: bare exit() gir exitkode 0 (=suksess) og gjemmer feilen for 06_bot.py

    print(f"Sjekker {len(value_df)} value bets\n")

    if value_df.empty:
        print("Ingen value bets å sjekke – skriver tom fil og avslutter.")
        pd.DataFrame(columns=list(value_df.columns) + ["Skadestatus", "Skadeinfo"]).to_csv(
            "value_bets_med_skadefilter.csv", index=False)
        return

    resultat_df = skadefilter.filtrer_bets_for_skader(value_df)

    # -------------------------------------------------------
    # Oppsummering
    # -------------------------------------------------------
    print("\n" + "=" * 60)
    print("ENDELIG OPPSUMMERING ETTER SKADEFILTER")
    print("=" * 60)

    ok_bets = resultat_df[resultat_df["Skadestatus"].str.contains("OK")]
    usikre_bets = resultat_df[resultat_df["Skadestatus"].str.contains("USIKKER")]

    if not ok_bets.empty:
        print(f"\n✅ ANBEFALTE BETS ({len(ok_bets)} stk):")
        print(ok_bets[["Kamp", "Bet", "Odds", "Modell %", "Value", "Forv. EV"]].to_string(index=False))

    if not usikre_bets.empty:
        print(f"\n⚠️  USIKRE BETS – MULIGE SKADER ({len(usikre_bets)} stk):")
        print(usikre_bets[["Kamp", "Bet", "Odds", "Skadeinfo"]].to_string(index=False))

    if ok_bets.empty and usikre_bets.empty:
        print("Ingen bets å vise.")

    skadefilter.skriv_skadefilter_csv(resultat_df)
    print("\n⚠️  Husk: Spill alltid ansvarlig.")


if __name__ == "__main__":
    main()
