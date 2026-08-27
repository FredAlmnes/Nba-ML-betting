"""
Tester for kalibrering.py sin kronologiske 3-veis splitt.

Denne testen vokter CALIB-01 — hvis tren/kalibrer/test-slicene noensinne
overlapper, blir isotonic-kalibratoren fittet på data den senere
evalueres på, som er nøyaktig lekkasjebugen fase 3 fikser.

Kildekode-voktertestene for selve fit-logikken (early stopping mot
kalibreringssettet, kalibratoren fittet kun på kalibreringssettet,
IsotonicRegression sin out_of_bounds="clip") flyttet til
tests/test_model.py i Plan 05-02, siden model.py nå eier alle .fit()-kall
i kodebasen. Denne filen vokter fortsatt selve splitten (over) pluss ETT
nytt guard-test: at 03_tren_modell.py delegerer til model.py i stedet for
å re-inline sin egen kopi av fit-logikken (se
test_treningsskript_delegerer_til_model under).
"""

from pathlib import Path

import pandas as pd
import pytest

from kalibrering import del_kronologisk_3veis


@pytest.fixture
def kamp_datoer_df():
    """150 deterministiske, fortløpende dagsdatoer fra 2024-10-01."""
    return pd.DataFrame({
        "GAME_DATE_HJEMME": pd.date_range("2024-10-01", periods=150, freq="D")
    })


def test_maskene_overlapper_aldri(kamp_datoer_df):
    tren_mask, kalibrer_mask, test_mask = del_kronologisk_3veis(kamp_datoer_df)
    assert not (tren_mask & kalibrer_mask).any()
    assert not (kalibrer_mask & test_mask).any()
    assert not (tren_mask & test_mask).any()


def test_maskene_dekker_alle_rader(kamp_datoer_df):
    tren_mask, kalibrer_mask, test_mask = del_kronologisk_3veis(kamp_datoer_df)
    assert (tren_mask | kalibrer_mask | test_mask).all()
    assert tren_mask.sum() + kalibrer_mask.sum() + test_mask.sum() == len(kamp_datoer_df)


def test_kronologisk_rekkefolge(kamp_datoer_df):
    tren_mask, kalibrer_mask, test_mask = del_kronologisk_3veis(kamp_datoer_df)
    datoer = kamp_datoer_df["GAME_DATE_HJEMME"]

    # Alle tre slicene må inneholde rader, ellers ville en fremtidig
    # off-by-one kunne tømme f.eks. kalibrer-vinduet stille.
    assert tren_mask.sum() > 0
    assert kalibrer_mask.sum() > 0
    assert test_mask.sum() > 0

    assert datoer[tren_mask].max() < datoer[kalibrer_mask].min()
    assert datoer[kalibrer_mask].max() < datoer[test_mask].min()


def test_ugyldig_kalibrer_cutoff_gir_verdifeil(kamp_datoer_df):
    with pytest.raises(ValueError):
        del_kronologisk_3veis(kamp_datoer_df, kalibrer_cutoff_mnd=2, tren_cutoff_mnd=2)


# ---------------------------------------------------------------------------
# Kildekode-voktertest for 03_tren_modell.py (Plan 05-02)
#
# 03_tren_modell.py kan ikke importeres av en test (modulnavn starter med
# et siffer, og den kjører en full XGBoost-treningsrunde ved import). Denne
# testen leser derfor skriptet som tekst og sjekker at fit-logikken forblir
# delegert til model.py — modulen som nå eier alle .fit()-kall — i stedet
# for å bli re-inlinet lokalt. Guardene for selve fit-DISIPLINEN (early
# stopping mot kalibreringssettet, kalibratoren fittet kun på
# kalibreringssettet, IsotonicRegression sin clip-oppførsel) lever nå i
# tests/test_model.py, rettet mot model.py.
# ---------------------------------------------------------------------------

def _treningsskript_kode():
    """
    Leser 03_tren_modell.py som tekst og fjerner kommentarlinjer.

    Filtreringen er obligatorisk: skriptet inneholder med vilje norske
    kommentarer som nevner X_test/eval_set (forklarer HVORFOR testsettet
    IKKE skal brukes til fitting), så et ufiltrert søk ville vært
    selvmotsigende og gi falske positiver.
    """
    sti = Path(__file__).resolve().parents[1] / "03_tren_modell.py"
    tekst = sti.read_text(encoding="utf-8")
    linjer = [
        linje for linje in tekst.splitlines()
        if not linje.strip().startswith("#")
    ]
    return "\n".join(linjer)


def test_treningsskript_delegerer_til_model():
    """
    Fit-logikken deles med walk-forward-løkken (Phase 5) kun så lenge
    ingen re-inliner en bekvem lokal kopi inn i treningsskriptet igjen —
    en re-inlinet kopi ville drevet bort fra CALIB-01-disiplinen usynlig,
    siden 03_tren_modell.py ikke kan importeres av en test for å sjekke
    dette direkte.
    """
    kode = _treningsskript_kode()
    assert "import model" in kode
    assert "XGBClassifier(" not in kode
    assert "IsotonicRegression(" not in kode
    assert ".fit(" not in kode
    assert "pickle.dump(" not in kode
