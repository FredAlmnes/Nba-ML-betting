"""
Tester for config.py (og fra plan 03: strategy.py).

Denne filen dekker foreløpig kun config.py-verdiene. beregn_innsats-,
vig- og dedup-testene legges til i plan 03 når strategy.py finnes.
"""

import pathlib

import config


def test_config_values():
    # D-07 låser disse verdiene til Phase 5s backtest har validert alternativer.
    # KALIBRERING_RAPPORT.md er det historiske presedenset: en aldri utrullet
    # terskelendring (0.20/2.50) som forble udokumentert live i lang tid.
    # Denne testen er en bevisst snubletråd — en endring her må skje sammen
    # med en bevisst endring av testen, ikke som en stille sideeffekt.
    assert config.MIN_VALUE_TERSKEL == 0.05
    assert config.MIN_ODDS == 1.50
    assert config.MAX_ODDS == 4.00
    assert config.KELLY_FRAKSJON == 0.5
    assert config.MAX_INNSATS == 150.0
    assert config.MIN_INNSATS == 20.0
    assert config.STARTKAPITAL == 1000.0


def test_config_har_ingen_hemmeligheter():
    # config.py commitres til git, så filen skal aldri inneholde en API-nøkkel
    # eller lignende hemmelighet — Odds API-nøkkelen skal fortsatt kun leses
    # fra miljøvariabel i 04_value_detector.py.
    config_kilde = (pathlib.Path(__file__).resolve().parent.parent / "config.py").read_text(
        encoding="utf-8"
    )
    assert "ODDS_API" not in config_kilde
    assert "apiKey" not in config_kilde
