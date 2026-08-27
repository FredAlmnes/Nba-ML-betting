"""
Tester for model.py — den as_of-bevisste tren/kalibrer/lagre/last-modulen.

Denne modulen eier NÅ alle .fit()-kall i kodebasen (XGBoost + isotonic
regression). Testene her vokter tre ting samtidig:

1. Engangs-splitten (as_of=None) skal være IDENTISK med den allerede
   testede kalibrering.del_kronologisk_3veis — fase 3s CALIB-01-fiks
   (disjunkt tren/kalibrer/test) må overleve flyttingen uendret.
2. as_of-splitten (walk-forward) skal aldri lekke en rad datert PÅ eller
   ETTER as_of inn i noen av bolkene — strengt <, samme disiplin som
   features.py::beregn_lag_form allerede håndhever (BT-02).
3. De to kildekode-vokterne som tidligere lå i
   tests/test_calibrering_split.py og pekte på 03_tren_modell.py, pekes nå
   mot model.py — modulen som faktisk eier fittingen etter denne planen.

Fixturen under bruker en LOKAL, syntetisk feature-formet tabell (ikke
tests/conftest.py sin kamper_df, som er RÅ per-kamp-rader uten
HJEMME_RULL_/BORTE_RULL_/DIFF_-kolonner). Ingen random, ingen
datetime.now() — 100 fortløpende dagsdatoer med et deterministisk mål.
"""

import pickle
import re
from pathlib import Path

import pandas as pd
import pytest

import model
from kalibrering import del_kronologisk_3veis
from modell_utils import KalibrertModell


@pytest.fixture
def features_df():
    """100 fortløpende dagsdatoer fra 2023-01-01 med feature-formede kolonner."""
    n = 100
    datoer = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "GAME_DATE_HJEMME": datoer,
        "HJEMME_VANT":      [i % 2 for i in range(n)],
        "DIFF_PTS":         [float(i % 2) * 2 - 1 for i in range(n)],
        "DIFF_REB":         [float((i + 1) % 2) * 2 - 1 for i in range(n)],
        "HJEMME_RULL_PTS":  [100.0 + (i % 5) for i in range(n)],
        "HJEMME_RULL_REB":  [40.0 + (i % 3) for i in range(n)],
        "BORTE_RULL_PTS":   [95.0 + (i % 4) for i in range(n)],
        "BORTE_RULL_REB":   [38.0 + (i % 2) for i in range(n)],
    })


# ---------------------------------------------------------------------------
# velg_feature_kolonner
# ---------------------------------------------------------------------------

def test_velg_feature_kolonner_finner_alle_tre_prefikser(features_df):
    kolonner = model.velg_feature_kolonner(features_df)
    forventet = [
        k for k in features_df.columns
        if k.startswith("DIFF_") or k.startswith("HJEMME_RULL_") or k.startswith("BORTE_RULL_")
    ]
    assert kolonner == forventet
    assert "GAME_DATE_HJEMME" not in kolonner
    assert "HJEMME_VANT" not in kolonner


# ---------------------------------------------------------------------------
# del_for_trening — engangs-splitten (as_of=None)
# ---------------------------------------------------------------------------

def test_engangs_split_er_identisk_med_del_kronologisk_3veis(features_df):
    tren_mask, kalibrer_mask, test_mask = model.del_for_trening(features_df)
    tren_forventet, kalibrer_forventet, test_forventet = del_kronologisk_3veis(features_df)
    assert tren_mask.equals(tren_forventet)
    assert kalibrer_mask.equals(kalibrer_forventet)
    assert test_mask.equals(test_forventet)


def test_engangs_split_maskene_overlapper_aldri_og_dekker_alt(features_df):
    tren_mask, kalibrer_mask, test_mask = model.del_for_trening(features_df)
    assert not (tren_mask & kalibrer_mask).any()
    assert not (kalibrer_mask & test_mask).any()
    assert not (tren_mask & test_mask).any()
    assert (tren_mask | kalibrer_mask | test_mask).all()


# ---------------------------------------------------------------------------
# del_for_trening — as_of-splitten (walk-forward)
# ---------------------------------------------------------------------------

def test_as_of_split_ekskluderer_grenseraden(features_df):
    grense_dato = features_df["GAME_DATE_HJEMME"].iloc[80]
    tren_mask, kalibrer_mask, test_mask = model.del_for_trening(features_df, as_of=grense_dato)
    grense_indeks = features_df.index[features_df["GAME_DATE_HJEMME"] == grense_dato][0]
    assert not tren_mask.loc[grense_indeks]
    assert not kalibrer_mask.loc[grense_indeks]
    assert not test_mask.loc[grense_indeks]


def test_as_of_split_gir_tomt_testsett(features_df):
    as_of = features_df["GAME_DATE_HJEMME"].iloc[80]
    _, _, test_mask = model.del_for_trening(features_df, as_of=as_of)
    assert test_mask.sum() == 0


def test_as_of_split_er_disjunkt_og_kronologisk(features_df):
    as_of = features_df["GAME_DATE_HJEMME"].iloc[80]
    tren_mask, kalibrer_mask, _ = model.del_for_trening(features_df, as_of=as_of)
    assert not (tren_mask & kalibrer_mask).any()
    datoer = features_df["GAME_DATE_HJEMME"]
    assert datoer[tren_mask].max() < datoer[kalibrer_mask].min()


def test_kalibrer_andel_styrer_stoerrelsen(features_df):
    as_of = features_df["GAME_DATE_HJEMME"].iloc[-1] + pd.Timedelta(days=1)

    tren_mask, kalibrer_mask, _ = model.del_for_trening(features_df, as_of=as_of, kalibrer_andel=0.15)
    assert tren_mask.sum() == 85
    assert kalibrer_mask.sum() == 15

    tren_mask2, kalibrer_mask2, _ = model.del_for_trening(features_df, as_of=as_of, kalibrer_andel=0.30)
    assert tren_mask2.sum() == 70
    assert kalibrer_mask2.sum() == 30


def test_for_lite_vindu_gir_verdifeil(features_df):
    as_of = features_df["GAME_DATE_HJEMME"].iloc[1]
    with pytest.raises(ValueError):
        model.del_for_trening(features_df, as_of=as_of)


def test_ugyldig_kalibrer_andel_gir_verdifeil(features_df):
    as_of = features_df["GAME_DATE_HJEMME"].iloc[-1] + pd.Timedelta(days=1)
    with pytest.raises(ValueError):
        model.del_for_trening(features_df, as_of=as_of, kalibrer_andel=0)
    with pytest.raises(ValueError):
        model.del_for_trening(features_df, as_of=as_of, kalibrer_andel=1.0)


# ---------------------------------------------------------------------------
# tren / lagre / last
# ---------------------------------------------------------------------------

def test_tren_returnerer_kalibrert_modell(features_df):
    resultat = model.tren(features_df)
    assert isinstance(resultat["modell"], KalibrertModell)

    X = features_df[model.velg_feature_kolonner(features_df)]
    sannsynligheter = resultat["modell"].predict_proba(X)
    assert sannsynligheter.shape == (len(X), 2)
    assert sannsynligheter.sum(axis=1) == pytest.approx(1.0)
    assert (sannsynligheter >= 0).all() and (sannsynligheter <= 1).all()


def test_lagre_og_last_bevarer_pickle_kontrakten(tmp_path, features_df):
    resultat = model.tren(features_df)
    sti = tmp_path / "test_modell.pkl"

    model.lagre(resultat["modell"], resultat["feature_kolonner"], sti=str(sti))
    modell_lastet, feature_kolonner_lastet = model.last(sti=str(sti))

    assert isinstance(modell_lastet, KalibrertModell)
    assert feature_kolonner_lastet == resultat["feature_kolonner"]

    with open(sti, "rb") as f:
        raapickle = pickle.load(f)
    assert sorted(raapickle.keys()) == ["feature_kolonner", "modell"]


# ---------------------------------------------------------------------------
# Kildekode-vokterester — FLYTTET fra tests/test_calibrering_split.py, nå
# rettet mot model.py (modulen som faktisk eier fittingen etter Plan 05-02)
# ---------------------------------------------------------------------------

def _modellmodul_kode():
    """
    Leser model.py som tekst og fjerner kommentarlinjer, samme mønster som
    tests/test_calibrering_split.py sin _treningsskript_kode().

    Filtreringen er obligatorisk: model.py inneholder med vilje norske
    kommentarer som nevner y_test/X_test (forklarer HVORFOR de aldri skal
    fittes på), så et ufiltrert søk ville vært selvmotsigende og gitt
    falske positiver.
    """
    sti = Path(__file__).resolve().parents[1] / "model.py"
    tekst = sti.read_text(encoding="utf-8")
    linjer = [
        linje for linje in tekst.splitlines()
        if not linje.strip().startswith("#")
    ]
    return "\n".join(linjer)


def test_kalibrator_fittes_kun_pa_kalibreringssettet():
    """CALIB-01 — selve lekkasjebugen fase 3 lukket, nå voktet i model.py."""
    kode = _modellmodul_kode()
    assert re.search(
        r"kalibrerer\.fit\(\s*y_rå_kalibrer\s*,\s*y_kalibrer\s*\)", kode
    )
    assert re.search(r"kalibrerer\.fit\([^)]*y_test", kode) is None
    assert re.search(
        r'IsotonicRegression\(\s*out_of_bounds\s*=\s*"clip"\s*\)', kode
    )


def test_early_stopping_bruker_aldri_testsettet():
    """D-04 — testsettet skal aldri styre hvor mange trær som bygges."""
    kode = _modellmodul_kode()
    assert re.search(
        r"eval_set\s*=\s*\[\(\s*X_kalibrer\s*,\s*y_kalibrer\s*\)\]", kode
    )
    assert re.search(r"eval_set\s*=\s*\[\(\s*X_test", kode) is None
    # model.py skal aldri drifte bort fra den testede del_kronologisk_3veis
    # for engangs-splitten.
    assert "from kalibrering import del_kronologisk_3veis" in kode
