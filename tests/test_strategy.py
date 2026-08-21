"""
Tester for config.py og strategy.py.

Denne filen dekker config.py-verdiene (CORE-02) og strategy.py sine rene
value/EV/Kelly/dedup-funksjoner (CORE-03) — pengemattematikken som CORE-03
finnes for å beskytte, og der utestet, duplisert logikk allerede har
kostet dette prosjektet ekte (papir-)penger.
"""

import pathlib

import pytest

import config
from strategy import (
    fjern_vigorish,
    beregn_value_og_ev,
    beregn_innsats,
    finn_bet_nokkel,
    bygg_bet_nokler,
    er_duplikat,
)


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


# ---------------------------------------------------------------------
# strategy.py — vig-fjerning og value/EV (CORE-01/CORE-03)
# ---------------------------------------------------------------------


def test_fjern_vigorish_summerer_til_en():
    # Rå 1/1.90 + 1/1.90 = 1.0526 (bookmakerens margin) skal normaliseres
    # bort slik at de to sannsynlighetene summerer til nøyaktig 100%.
    impl_hjemme, impl_borte = fjern_vigorish(1.90, 1.90)
    assert impl_hjemme == pytest.approx(0.5)
    assert impl_borte == pytest.approx(0.5)
    assert impl_hjemme + impl_borte == pytest.approx(1.0)


def test_fjern_vigorish_bevarer_rekkefolge():
    # Favoritten (lavest odds) skal få høyest implisitt sannsynlighet,
    # ikke motsatt — en regresjon her ville reversert hvem som er favoritt.
    impl_hjemme, impl_borte = fjern_vigorish(1.50, 3.00)
    assert impl_hjemme == pytest.approx(2 / 3, abs=1e-9)
    assert impl_borte == pytest.approx(1 / 3, abs=1e-9)


def test_beregn_value_og_ev():
    value, ev = beregn_value_og_ev(0.60, 2.00, 0.50)
    assert value == pytest.approx(0.10)
    assert ev == pytest.approx(0.20)


def test_beregn_value_og_ev_negativ_edge():
    # Negativ value og negativ EV skal rapporteres rått, ikke klemmes til 0 —
    # dette er signalet som forteller boten at det IKKE er en value bet.
    value, ev = beregn_value_og_ev(0.45, 2.00, 0.50)
    assert value == pytest.approx(-0.05)
    assert ev == pytest.approx(-0.10)


# ---------------------------------------------------------------------
# strategy.py — beregn_innsats / halvt Kelly (CORE-03)
# ---------------------------------------------------------------------


def test_beregn_innsats_halv_kelly():
    # Full Kelly ville gitt 0.20 av bankroll (200 kr); halvt Kelly skal
    # være nøyaktig halvparten av det.
    assert beregn_innsats(1000.0, 0.60, 2.00, 0.5, 20.0, 150.0) == 100.0


def test_beregn_innsats_null_edge_gir_null():
    # Modellsannsynlighet = 0.50 og odds = 2.00 gir eksakt kelly = 0.0
    # (1.0*0.5 - 0.5 = 0.0 uten flyttallsstøy) -> "<= 0"-grenen slår til.
    # NB: paret (0.40, 2.50) fra planens interfaces-eksempel gir IKKE
    # eksakt 0.0 her pga. flyttallsunøyaktighet i 1.5*0.4 (se SUMMARY,
    # avvik-seksjonen) — samme oppførsel som før ekstraksjonen, ikke en
    # regresjon. Denne testen bruker derfor et flyttall-trygt par som
    # faktisk isolerer "<= 0"-grenen.
    assert beregn_innsats(1000.0, 0.50, 2.00, 0.5, 20.0, 150.0) == 0.0


def test_beregn_innsats_negativ_edge_gir_null():
    assert beregn_innsats(1000.0, 0.30, 2.50, 0.5, 20.0, 150.0) == 0.0


def test_beregn_innsats_klemmer_mot_maks():
    assert beregn_innsats(100000.0, 0.90, 1.60, 0.5, 20.0, 150.0) == 150.0


def test_beregn_innsats_klemmer_opp_til_min():
    # Rå halv-Kelly-innsats er 5.00 kr, min-klemmingen løfter den til 20.00 —
    # en reell 4x innsatsøkning på en tynn edge, pinnet bevisst slik at
    # oppførselen ikke kan endre seg umerket.
    assert beregn_innsats(100.0, 0.55, 2.00, 0.5, 20.0, 150.0) == 20.0


# ---------------------------------------------------------------------
# strategy.py — bet-dedup-nøkkel (CORE-03, D-11)
# ---------------------------------------------------------------------


def test_bygg_bet_nokler_bruker_kamp_dato():
    # Når kamp_dato finnes skal nøkkelen bygges på den, ikke botens
    # kjøredato (dato).
    records = [{"kamp": "Lakers vs Celtics", "bet": "Hjemme", "dato": "2026-08-20", "kamp_dato": "2026-08-22"}]
    nokler = bygg_bet_nokler(records)
    assert ("Lakers vs Celtics", "Hjemme", "2026-08-22") in nokler
    assert ("Lakers vs Celtics", "Hjemme", "2026-08-20") not in nokler


def test_bygg_bet_nokler_faller_tilbake_til_dato():
    # Legacy-records skrevet før 2026-08-19-fiksen mangler kamp_dato helt —
    # de skal fortsatt delta i dedup via fallback til dato.
    records = [{"kamp": "Lakers vs Celtics", "bet": "Hjemme", "dato": "2026-08-18"}]
    nokler = bygg_bet_nokler(records)
    assert ("Lakers vs Celtics", "Hjemme", "2026-08-18") in nokler


def test_dedup_fanger_samme_kamp_paa_ulik_kjoredato():
    # Den eksakte formen på 2026-08-19-bugen: to records for samme kamp med
    # samme kamp_dato men ulik dato (botens kjøredato) skal kollapse til ÉN
    # nøkkel, slik at andre kjørings bet oppdages som duplikat.
    r1 = {"kamp": "Lakers vs Celtics", "bet": "Hjemme", "dato": "2026-08-20", "kamp_dato": "2026-08-22"}
    r2 = {"kamp": "Lakers vs Celtics", "bet": "Hjemme", "dato": "2026-08-21", "kamp_dato": "2026-08-22"}
    assert len(bygg_bet_nokler([r1, r2])) == 1


def test_dedup_slipper_gjennom_ulik_kamp_dato():
    # Samme kamp og bet men ulik kamp_dato er IKKE en duplikat — et
    # revansjeoppgjør mellom samme to lag er et legitimt nytt bet.
    r1 = {"kamp": "Lakers vs Celtics", "bet": "Hjemme", "dato": "2026-08-20", "kamp_dato": "2026-08-22"}
    r2 = {"kamp": "Lakers vs Celtics", "bet": "Hjemme", "dato": "2026-09-10", "kamp_dato": "2026-09-12"}
    nokler = bygg_bet_nokler([r1])
    nokkel_r2 = finn_bet_nokkel(r2["kamp"], r2["bet"], r2["kamp_dato"])
    assert not er_duplikat(nokkel_r2, nokler)


def test_dedup_tom_historikk():
    nokkel = finn_bet_nokkel("Lakers vs Celtics", "Hjemme", "2026-08-22")
    assert er_duplikat(nokkel, bygg_bet_nokler([])) is False
