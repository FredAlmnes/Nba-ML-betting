"""
Tester for kalibrering.py sin kronologiske 3-veis splitt.

Denne testen vokter CALIB-01 — hvis tren/kalibrer/test-slicene noensinne
overlapper, blir isotonic-kalibratoren fittet på data den senere
evalueres på, som er nøyaktig lekkasjebugen fase 3 fikser.
"""

import re
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
# Kildekode-vokterester for 03_tren_modell.py (Plan 03-02)
#
# 03_tren_modell.py kan ikke importeres av en test (modulnavn starter med
# et siffer, og den kjører en full XGBoost-treningsrunde ved import). Disse
# testene leser derfor skriptet som tekst og sjekker at CALIB-01-lekkasje-
# bugen (kalibratoren fittet på testsettet den senere evalueres på) ikke
# kan smyge seg tilbake inn i koden ubemerket.
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


def test_early_stopping_bruker_aldri_testsettet():
    """D-04 — testsettet skal aldri styre hvor mange trær som bygges."""
    kode = _treningsskript_kode()
    assert re.search(
        r"eval_set\s*=\s*\[\(\s*X_kalibrer\s*,\s*y_kalibrer\s*\)\]", kode
    )
    assert re.search(r"eval_set\s*=\s*\[\(\s*X_test", kode) is None
    # Skriptet skal aldri drifte tilbake til en inline 2-veis splitt som
    # forbikjører den testede del_kronologisk_3veis-funksjonen.
    assert "from kalibrering import del_kronologisk_3veis" in kode


def test_kalibrator_fittes_kun_pa_kalibreringssettet():
    """CALIB-01 — dette er selve lekkasjebugen fase 3 lukker."""
    kode = _treningsskript_kode()
    assert re.search(
        r"kalibrerer\.fit\(\s*y_rå_kalibrer\s*,\s*y_kalibrer\s*\)", kode
    )
    assert re.search(r"kalibrerer\.fit\([^)]*y_test", kode) is None


def test_isotonic_klipper_utenfor_omraade():
    """Pitfall 3 — sklearn-standarden "nan" ville stille korrumpert reliabilitetstabellen."""
    kode = _treningsskript_kode()
    assert re.search(
        r'IsotonicRegression\(\s*out_of_bounds\s*=\s*"clip"\s*\)', kode
    )
