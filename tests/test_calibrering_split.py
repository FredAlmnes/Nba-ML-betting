"""
Tester for kalibrering.py sin kronologiske 3-veis splitt.

Denne testen vokter CALIB-01 — hvis tren/kalibrer/test-slicene noensinne
overlapper, blir isotonic-kalibratoren fittet på data den senere
evalueres på, som er nøyaktig lekkasjebugen fase 3 fikser.
"""

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
