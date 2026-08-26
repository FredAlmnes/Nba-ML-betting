"""
Enkelt sannhets-kilde for strategiparametre.

Importeres av live-boten i dag (04_value_detector.py, 06_bot.py) og av
Phase 5-backtesten senere. Endrer man en verdi her, endrer man hva en
fremtidig backtest faktisk validerer.

Odds-API-nøkkelen ligger IKKE her med vilje – den forblir en
miljøvariabel-innlesning i 04_value_detector.py, fordi config.py
commitres til git og hemmeligheter skal ikke det.

Denne filen eier nå også holdout-grensen, låst i 05-BESLUTNINGER.md D-05-01.
Å endre den etter at Plan 05-13 har brukt holdouten, opphever garantien om
at den er "sjekket nøyaktig én gang" for denne milepælen. De syv
strategiverdiene over den holder seg fryst helt til backtesten har gitt
bevis for noe annet (jf. 05-CONTEXT.md sine utsatte ideer).
"""

MIN_VALUE_TERSKEL = 0.05            # Flagg bets der vi er 5%+ over bookmaker
MIN_ODDS = 1.50                     # Ikke bett på favoritter med veldig lave odds
MAX_ODDS = 4.00                     # Ikke bett på store outsidere (over 4x = for usikkert)

KELLY_FRAKSJON = 0.5      # Halvt Kelly (konservativt – reduserer varians)
MAX_INNSATS = 150.0    # Aldri mer enn 150 kr på ett bet
MIN_INNSATS = 20.0     # Aldri mindre enn 20 kr
STARTKAPITAL = 1000.0   # kr

HOLDOUT_START_DATO = "2024-10-01"   # Datoer fra og med denne hører til den låste 2024-25-holdouten og skal kun evalueres via kjor_endelig_holdout_backtest() (BT-03)
