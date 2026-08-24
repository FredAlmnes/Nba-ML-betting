"""
STEG 4: Value Detector – finn gode bets
=========================================
Dette er hjertet av systemet!

Vi henter dagens NBA-odds fra The Odds API, bruker modellen
vår til å beregne "riktige" sannsynligheter, og flagger
kamper der bookmakerens implisitte sannsynlighet divergerer
fra vår modell.

All beslutningslogikk (modell-lasting, value/EV-beregning, CSV-skriving) er
flyttet til verdi_deteksjon.py, og selve odds-hentingen til odds.py — denne
filen er nå bare den frittstående CLI-inngangen som orkestrerer de to.

Du trenger en gratis API-nøkkel fra:
https://the-odds-api.com (500 kall/måned gratis)

Nøkkelen leses fra miljøvariabelen ODDS_API_NOKKEL via en .env-fil.
Kopier .env.example til .env og fyll inn din egen nøkkel der.
"""

import sys

import odds
import verdi_deteksjon


def main():
    api_nokkel = odds.hent_api_nokkel()

    print("Laster inn trent modell...")
    try:
        modell, feature_kolonner = verdi_deteksjon.last_modell()
    except FileNotFoundError:
        print("Finner ikke 'nba_modell.pkl' – kjør 03_tren_modell.py først!")
        sys.exit(1)  # NB: bare exit() gir exitkode 0 (=suksess) og gjemmer feilen for 06_bot.py
    print("Modell lastet!")

    print("\nHenter dagens NBA-odds...")
    print("\nHenter fersk lagstatistikk fra NBA...")

    print("\n" + "=" * 60)
    print("VALUE BETS FOR DAGENS NBA-KAMPER")
    print("=" * 60)

    value_bets = verdi_deteksjon.finn_value_bets(modell, feature_kolonner, api_nokkel=api_nokkel)

    print("\n" + "=" * 60)
    print("OPPSUMMERING: VALUE BETS I DAG")
    print("=" * 60)

    verdi_deteksjon.skriv_value_bets_csv(value_bets)

    print("\n⚠️  ADVARSEL: Bruk dette som læringsverktøy, ikke som garanti for profitt.")
    print("   Spill alltid ansvarlig og ikke bett mer enn du har råd til å tape.")


if __name__ == "__main__":
    main()
