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


# ---------------------------------------------------------------------
# bootstrap_roi_ci og wilson_ci (BT-04 — konfidensintervaller)
# ---------------------------------------------------------------------


def test_bootstrap_roi_ci_kjente_verdier():
    # Degenerert ledger: alle 5 bets vunnet på odds 2.00, innsats 100 hver
    # -> profitt er +100.0 for hvert bet, altså profitt == innsats overalt.
    # Enhver resample (uansett hvilke indekser som trekkes) gir dermed
    # ratio sum(profitt)/sum(innsats) == 1.0 eksakt -> (1.0, 1.0, 1.0).
    resultat = metrics.bootstrap_roi_ci([100.0] * 5, [100.0] * 5)
    assert resultat == (1.0, 1.0, 1.0)

    # Symmetrisk to-bet-ledger: profitter [100, -100], innsatser [100, 100].
    # Med 2 uavhengige trekk fra {bet0, bet1} finnes det kun 4 like sannsynlige
    # resamples: (0,0) -> ratio +1.0, (1,1) -> ratio -1.0, (0,1) og (1,0)
    # -> ratio 0.0. Sannsynligheter: +1.0 med 0.25, -1.0 med 0.25,
    # 0.0 med 0.5 (to av fire kombinasjoner). Ved 1000 resamples er
    # 2.5- og 97.5-persentilen derfor strukturelt -1.0 og +1.0 — en
    # egenskap ved fordelingen, ikke et artefakt av seed 42.
    punkt, nedre, oevre = metrics.bootstrap_roi_ci([100.0, -100.0], [100.0, 100.0])
    assert punkt == pytest.approx(0.0)
    assert nedre == pytest.approx(-1.0)
    assert oevre == pytest.approx(1.0)


def test_bootstrap_roi_ci_er_reproduserbar():
    # Samme seed to ganger skal gi bit-identiske tupler.
    a = metrics.bootstrap_roi_ci([100.0, -100.0, 50.0], [100.0, 100.0, 100.0], seed=7)
    b = metrics.bootstrap_roi_ci([100.0, -100.0, 50.0], [100.0, 100.0, 100.0], seed=7)
    assert a == b

    # Ulik seed skal fortsatt gi samme punktestimat — punktestimatet
    # avhenger aldri av RNG-en, kun av den originale ledgeren.
    c = metrics.bootstrap_roi_ci([100.0, -100.0, 50.0], [100.0, 100.0, 100.0], seed=99)
    assert a[0] == c[0]


def test_bootstrap_roi_ci_returnerer_python_float():
    # json.dumps i manifest.json (plan 05-08) feiler på numpy.float64 —
    # denne testen pinner at alle tre returverdier er rene Python-floats.
    resultat = metrics.bootstrap_roi_ci([100.0, -100.0], [100.0, 100.0])
    assert all(type(x) is float for x in resultat)


def test_bootstrap_roi_ci_standardverdier_er_laast():
    # n_resamples og seed skrives inn i manifest.json for reproduserbarhet
    # (BT-05). En stille endring av standardverdiene ville gjort tidligere
    # kjøringer irreproduserbare uten at noen test feilet — denne testen
    # er den bevisste snubletråden som hindrer det, samme mønster som
    # tests/test_strategy.py::test_config_values.
    import inspect

    sig = inspect.signature(metrics.bootstrap_roi_ci)
    assert sig.parameters["n_resamples"].default == 1000
    assert sig.parameters["seed"].default == 42


def test_bootstrap_roi_ci_ulik_lengde_reiser_feil():
    with pytest.raises(ValueError):
        metrics.bootstrap_roi_ci([100.0, -100.0], [100.0])


def test_wilson_ci_kjente_verdier():
    # wilson_ci(50, 100): p = 0.5 er Wilson-senteret eksakt for p=0.5.
    p, nedre, oevre = metrics.wilson_ci(50, 100)
    assert p == pytest.approx(0.5)
    assert nedre == pytest.approx(0.40383, abs=1e-4)
    assert oevre == pytest.approx(0.59617, abs=1e-4)

    # wilson_ci(0, 10): naiv normal-approksimasjon ville kollapset til
    # 0.0 ± 0.0 og gitt et intervall uten informasjon. Wilson gir en
    # nedre grense klemt til eksakt 0.0, men en meningsfull øvre grense.
    p0, nedre0, oevre0 = metrics.wilson_ci(0, 10)
    assert p0 == pytest.approx(0.0)
    assert nedre0 == 0.0
    assert oevre0 == pytest.approx(0.27754, abs=1e-4)

    # wilson_ci(0, 0): ingen data -> (0.0, 0.0, 0.0).
    assert metrics.wilson_ci(0, 0) == (0.0, 0.0, 0.0)

    # Standard z er 1.96 (95%-intervall).
    import inspect

    sig = inspect.signature(metrics.wilson_ci)
    assert sig.parameters["z"].default == 1.96
