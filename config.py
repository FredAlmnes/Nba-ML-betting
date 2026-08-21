"""
Enkelt sannhets-kilde for strategiparametre.

Importeres av live-boten i dag (04_value_detector.py, 06_bot.py) og av
Phase 5-backtesten senere. Endrer man en verdi her, endrer man hva en
fremtidig backtest faktisk validerer.

Odds-API-nøkkelen ligger IKKE her med vilje – den forblir en
miljøvariabel-innlesning i 04_value_detector.py, fordi config.py
commitres til git og hemmeligheter skal ikke det.
"""

MIN_VALUE_TERSKEL = 0.05            # Flagg bets der vi er 5%+ over bookmaker
MIN_ODDS = 1.50                     # Ikke bett på favoritter med veldig lave odds
MAX_ODDS = 4.00                     # Ikke bett på store outsidere (over 4x = for usikkert)

KELLY_FRAKSJON = 0.5      # Halvt Kelly (konservativt – reduserer varians)
MAX_INNSATS = 150.0    # Aldri mer enn 150 kr på ett bet
MIN_INNSATS = 20.0     # Aldri mindre enn 20 kr
STARTKAPITAL = 1000.0   # kr
