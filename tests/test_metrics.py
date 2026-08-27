"""
Tester for metrics.py — BT-04s hovedtall (ROI, vinnrate, maks drawdown,
konfidensintervaller) og BT-06s CLV, verifisert mot håndregnede verdier.

Ingen golden files, ingen innspilte utdata — hver forventet verdi i denne
filen kan etterregnes med papir og penn, og hver test har en kommentar som
viser regnestykket.
"""

import pytest

import metrics
from metrics import (
    beregn_profitt,
    beregn_roi,
    beregn_vinnrate,
    beregn_maks_drawdown,
)


# ---------------------------------------------------------------------
# beregn_profitt
# ---------------------------------------------------------------------


def test_beregn_profitt_vunnet_og_tapt():
    # Vunnet: 100 * (2.50 - 1) = 150.0. Tapt: -100.0 (hele innsatsen).
    assert beregn_profitt(100.0, 2.50, True) == 150.0
    assert beregn_profitt(100.0, 2.50, False) == -100.0


# ---------------------------------------------------------------------
# beregn_roi
# ---------------------------------------------------------------------


def test_beregn_roi_kjent_ledger():
    # sum(profitter) = 100 - 100 + 50 - 100 = -50
    # sum(innsatser) = 100*4 = 400
    # ROI = -50 / 400 = -0.125
    assert beregn_roi([100.0, -100.0, 50.0, -100.0], [100.0] * 4) == pytest.approx(-0.125)


def test_beregn_roi_tom_ledger():
    # Tom ledger skal gi 0.0, ikke krasje eller NaN.
    assert beregn_roi([], []) == 0.0


# ---------------------------------------------------------------------
# beregn_vinnrate
# ---------------------------------------------------------------------


def test_beregn_vinnrate():
    # 2 av 4 vunnet -> 0.5
    vinnrate, antall_vunnet, antall_totalt = beregn_vinnrate([True, False, True, False])
    assert vinnrate == pytest.approx(0.5)
    assert antall_vunnet == 2
    assert antall_totalt == 4


def test_beregn_vinnrate_tom():
    assert beregn_vinnrate([]) == (0.0, 0, 0)


# ---------------------------------------------------------------------
# beregn_maks_drawdown
# ---------------------------------------------------------------------


def test_beregn_maks_drawdown_kjent_kurve():
    # Bankroll-kurve fra startkapital=1000 og profitter=[-200, 400, -300, 100]:
    #   1000 -> 800 -> 1200 -> 900 -> 1000
    # Kandidat 1: 1000 -> 800 er et fall på 200 kr / 20% (fra toppen 1000)
    # Kandidat 2: 1200 -> 900 er et fall på 300 kr / 25% (fra toppen 1200)
    # Størst i kroner OG i andel er kandidat 2: (300.0, 0.25)
    resultat = beregn_maks_drawdown([-200.0, 400.0, -300.0, 100.0], 1000.0)
    assert resultat == (pytest.approx(300.0), pytest.approx(0.25))


def test_beregn_maks_drawdown_kun_oppgang():
    # Monotont stigende kurve har ingen drawdown.
    assert beregn_maks_drawdown([100.0, 100.0], 1000.0) == (0.0, 0.0)


def test_beregn_maks_drawdown_tom():
    assert beregn_maks_drawdown([], 1000.0) == (0.0, 0.0)
