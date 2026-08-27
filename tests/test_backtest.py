"""
Tester for backtest.py — Fase 5s walk-forward-motor (plan 05-07).

Hver test i denne filen er deterministisk — ingen systemklokke, ingen
nettverk, ingen `random` — og (bortsett fra de tre eksplisitt
skip-vaktede ekte-data-testene plan 05-07 Task 3 legger til) ingen
avhengighet av den ekte `odds_arkiv.db` eller `nba_features.csv`, som
speiler `tests/test_parity.py` sin egen docstring-disiplin.
"""

import inspect

import pytest

import backtest
import config


# --- 1. Holdout-vakt / gjenopptrenings-planlegger / ren beslutning ---


def test_holdout_guard_reiser_feil():
    with pytest.raises(backtest.HoldoutLaastFeil):
        backtest._sikre_ikke_holdout(config.HOLDOUT_START_DATO)

    with pytest.raises(backtest.HoldoutLaastFeil) as exc_info:
        backtest._sikre_ikke_holdout("2025-01-15")

    melding = str(exc_info.value)
    assert "2025-01-15" in melding
    assert config.HOLDOUT_START_DATO in melding


def test_holdout_guard_slipper_gjennom_tuning_datoer():
    dagen_for = "2024-09-30"
    assert backtest._sikre_ikke_holdout(dagen_for) is None
    assert backtest._sikre_ikke_holdout("2022-10-24") is None


def test_holdout_guard_kan_apnes_eksplisitt():
    assert backtest._sikre_ikke_holdout(config.HOLDOUT_START_DATO, tillat_holdout=True) is None


def test_holdout_grensedatoen_selv_er_last():
    with pytest.raises(backtest.HoldoutLaastFeil):
        backtest._sikre_ikke_holdout(config.HOLDOUT_START_DATO)


def test_trenger_retrening_forste_dato():
    assert backtest.trenger_retrening("2022-11-09", None) is True


def test_trenger_retrening_ved_manedsskifte():
    assert backtest.trenger_retrening("2022-12-01", "2022-11") is True
    assert backtest.trenger_retrening("2022-11-30", "2022-11") is False
    assert backtest.trenger_retrening("2023-01-02", "2022-12") is True


def test_trenger_retrening_bruker_forrige_behandlede_maned_ikke_kalenderen():
    # Sommerpausen: forrige behandlede dato var i april, neste behandlede
    # dato er i oktober — skal utløse akkurat ETT gjenopptrenings-flagg,
    # ikke ett per hoppet-over kalendermåned.
    assert backtest.trenger_retrening("2023-10-24", "2023-04") is True


def test_vurder_kamp_flagger_hjemme_ved_value():
    kandidater = backtest.vurder_kamp(0.70, 2.00, 2.00)
    assert len(kandidater) == 1
    k = kandidater[0]
    assert k["side"] == "hjemme"
    assert k["odds"] == pytest.approx(2.00)
    assert k["impl_prob"] == pytest.approx(0.5)
    assert k["value"] == pytest.approx(0.20)
    assert k["ev"] == pytest.approx(0.40)


def test_vurder_kamp_flagger_borte_ved_value():
    kandidater = backtest.vurder_kamp(0.30, 2.00, 2.00)
    assert len(kandidater) == 1
    k = kandidater[0]
    assert k["side"] == "borte"
    assert k["modell_prob"] == pytest.approx(0.70)


def test_vurder_kamp_kan_aldri_flagge_begge_sider():
    priser = [(2.00, 2.00), (1.60, 3.50), (3.00, 1.60), (4.00, 1.50), (1.50, 4.00)]
    for modell_prob_hjemme in [x / 100 for x in range(5, 96, 5)]:
        for odds_hjemme, odds_borte in priser:
            kandidater = backtest.vurder_kamp(modell_prob_hjemme, odds_hjemme, odds_borte)
            assert len(kandidater) != 2


def test_vurder_kamp_respekterer_odds_grensene():
    assert backtest.vurder_kamp(0.90, 1.49, 1.49) == []
    assert len(backtest.vurder_kamp(0.90, 1.50, 1.50)) == 1
    assert len(backtest.vurder_kamp(0.90, 4.00, 4.00)) == 1
    assert backtest.vurder_kamp(0.90, 4.01, 4.01) == []


def test_vurder_kamp_terskelen_er_strengt_storre_enn():
    # impl_prob 0.5, modell_prob 0.55 -> value akkurat 0.05, som er terskelen selv
    assert backtest.vurder_kamp(0.55, 2.00, 2.00) == []


def test_vurder_kamp_bruker_strategy_funksjonene(monkeypatch):
    def _sprakk(*args, **kwargs):
        raise AssertionError("vig-fjerning skal aldri reimplementeres lokalt")

    monkeypatch.setattr(backtest, "fjern_vigorish", _sprakk)
    with pytest.raises(AssertionError):
        backtest.vurder_kamp(0.70, 2.00, 2.00)


def test_vurder_kamp_ser_verken_utfall_eller_closing():
    kilde = inspect.getsource(backtest.vurder_kamp)
    assert "HJEMME_VANT" not in kilde
    assert "hjemme_vant" not in kilde
    assert "hent_closing_pris" not in kilde
    assert "closing" not in kilde


def test_lag_id_og_navn_loser_forkortelser():
    lag_id, navn = backtest._lag_id_og_navn("LAL")
    assert lag_id == 1610612747
    assert navn == "Los Angeles Lakers"

    assert backtest._lag_id_og_navn("ZZZ") == (None, None)
