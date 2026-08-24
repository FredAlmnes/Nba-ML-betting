"""
Tester for verdi_deteksjon.py — value-deteksjon-beslutningslogikken flyttet ut
av 04_value_detector.py som importerbare funksjoner (plan 04-06).

Beviser to ting: (1) at å importere modulen ikke lenger laster pickle-modellen,
gjør nettverkskall eller skriver CSV slik den gamle 04_value_detector.py gjorde
ved import, og (2) at beslutningsreglene (finn_value_bets) oppfører seg
identisk med før, gitt injiserte kamper/lagstats/modell — ingen nettverkskall.

test_finn_value_bets_uendret_output er navngitt eksplisitt av 04-VALIDATION.md
og regner ut forventet bet-dict for hånd (ikke ved å kjøre koden under test på
nytt), akkurat slik plan-instruksen krever.
"""

import importlib

import pandas as pd

import verdi_deteksjon
from features import STATS_KOLONNER, bygg_feature_rad
from verdi_deteksjon import KOLONNER, finn_value_bets, skriv_value_bets_csv

# Ekte NBA-lag-navn, resolverbare via teams.finn_lag_id.
HEAT = "Miami Heat"
RAPTORS = "Toronto Raptors"


class _StubModell:
    """Stub-modell med et fast predict_proba-svar, uavhengig av X sitt innhold."""

    def __init__(self, prob_hjemme):
        self._prob_hjemme = prob_hjemme

    def predict_proba(self, X):
        return [[1 - self._prob_hjemme, self._prob_hjemme]]


def _stub_lagstats(team_id):
    """Fast lagstats-dict som dekker alle STATS_KOLONNER-nøklene bygg_feature_rad forventer."""
    return {
        "PTS": 110.0, "FG_PCT": 0.47, "FT_PCT": 0.78, "FG3_PCT": 0.36,
        "REB": 44.0, "AST": 25.0, "TOV": 13.0, "PLUS_MINUS": 2.0, "VANT": 0.55,
    }


def _feature_kolonner():
    """Bygger en gyldig feature_kolonner-liste fra de samme stats-nøklene stub-modellen bruker."""
    rad = bygg_feature_rad(_stub_lagstats(0), _stub_lagstats(0))
    return list(rad.keys())


def _kamp(hjemme=HEAT, borte=RAPTORS, commence_time="2026-01-15T00:30:00Z", bookmakere=None):
    if bookmakere is None:
        bookmakere = [{
            "title": "Unibet",
            "markets": [{
                "key": "h2h",
                "outcomes": [
                    {"name": hjemme, "price": 2.10},
                    {"name": borte, "price": 1.80},
                ],
            }],
        }]
    return {
        "home_team": hjemme,
        "away_team": borte,
        "commence_time": commence_time,
        "bookmakers": bookmakere,
    }


def test_import_verdi_deteksjon_gjor_ingen_nettverkskall(monkeypatch):
    """
    Reloader verdi_deteksjon med TeamGameLogs erstattet av en funksjon som
    kaster AssertionError hvis den kalles. Modulen skal lastes uten feil —
    det beviser at ingen kode på modul-nivå gjør nba_api-kall, laster pickle-
    modellen eller skriver CSV (i motsetning til gamle 04_value_detector.py).
    """
    from nba_api.stats.endpoints import teamgamelogs

    def _sprengt(*args, **kwargs):
        raise AssertionError("TeamGameLogs skal IKKE kalles ved import")

    monkeypatch.setattr(teamgamelogs, "TeamGameLogs", _sprengt)

    modul = importlib.reload(verdi_deteksjon)
    assert modul is not None


def test_finn_value_bets_uendret_output():
    """
    Regnet ut for hånd (ikke rekomputert via koden under test):
    impl_hjemme = 6/13 = 0.461538..., impl_borte = 7/13 = 0.538461...
    value_hjemme = 0.65 - 0.461538... = 0.188461... (> MIN_VALUE_TERSKEL, innenfor MIN_ODDS..MAX_ODDS -> flagges)
    value_borte  = 0.35 - 0.538461... = -0.188461... (negativ -> flagges ikke)
    """
    modell = _StubModell(prob_hjemme=0.65)
    kamper = [_kamp()]

    value_bets = finn_value_bets(
        modell, _feature_kolonner(), kamper=kamper, hent_lagstats=_stub_lagstats
    )

    assert len(value_bets) == 1
    assert value_bets[0] == {
        "Kamp": "Miami Heat vs Toronto Raptors",
        "KampDato": "2026-01-15",
        "Bet": "Hjemme (Miami Heat)",
        "Odds": 2.10,
        "Bookmaker": "Unibet",
        "Modell_prob": 0.65,
        "Modell %": "65.0%",
        "Bookmaker %": "46.2%",
        "Value": "+18.8%",
        "Forv. EV": "+36.5%",
    }


def test_finn_value_bets_hopper_over_uresolverbart_lagnavn(monkeypatch):
    """Et lagnavn finn_lag_id() ikke klarer å løse skal hoppes over uten å kaste."""
    monkeypatch.setattr(verdi_deteksjon, "finn_lag_id", lambda navn: None)

    modell = _StubModell(prob_hjemme=0.65)
    kamper = [_kamp()]

    value_bets = finn_value_bets(
        modell, _feature_kolonner(), kamper=kamper, hent_lagstats=_stub_lagstats
    )

    assert value_bets == []


def test_finn_value_bets_hopper_over_manglende_lagstats():
    """Hvis hent_lagstats returnerer None for en av lagene, hoppes kampen over."""
    modell = _StubModell(prob_hjemme=0.65)
    kamper = [_kamp()]

    def _delvis_manglende(team_id):
        heat_id = 1610612748
        if team_id == heat_id:
            return None
        return _stub_lagstats(team_id)

    value_bets = finn_value_bets(
        modell, _feature_kolonner(), kamper=kamper, hent_lagstats=_delvis_manglende
    )

    assert value_bets == []


def test_finn_value_bets_hopper_over_kamp_uten_h2h_odds():
    """En kamp uten h2h-utfall (beste odds forblir 0) skal hoppes over."""
    modell = _StubModell(prob_hjemme=0.65)
    kamp = _kamp(bookmakere=[{
        "title": "Unibet",
        "markets": [{"key": "spreads", "outcomes": []}],
    }])

    value_bets = finn_value_bets(
        modell, _feature_kolonner(), kamper=[kamp], hent_lagstats=_stub_lagstats
    )

    assert value_bets == []


def test_finn_value_bets_under_terskel_flagges_ikke():
    """Value akkurat på/under MIN_VALUE_TERSKEL skal ikke flagges."""
    # Odds 2.0 -> vig-fri implisitt sannsynlighet nær 50% for begge sider når
    # oddsene er symmetriske (samme margin), modell satt til akkurat 50%.
    modell = _StubModell(prob_hjemme=0.50)
    kamp = _kamp(bookmakere=[{
        "title": "Unibet",
        "markets": [{
            "key": "h2h",
            "outcomes": [
                {"name": HEAT, "price": 2.00},
                {"name": RAPTORS, "price": 2.00},
            ],
        }],
    }])

    value_bets = finn_value_bets(
        modell, _feature_kolonner(), kamper=[kamp], hent_lagstats=_stub_lagstats
    )

    assert value_bets == []


def test_finn_value_bets_odds_utenfor_range_flagges_ikke():
    """Value som klarer terskelen, men med odds over MAX_ODDS, skal ikke flagges."""
    modell = _StubModell(prob_hjemme=0.80)
    kamp = _kamp(bookmakere=[{
        "title": "Unibet",
        "markets": [{
            "key": "h2h",
            "outcomes": [
                {"name": HEAT, "price": 5.00},   # over MAX_ODDS (4.00)
                {"name": RAPTORS, "price": 1.30},  # under MIN_ODDS (1.50)
            ],
        }],
    }])

    value_bets = finn_value_bets(
        modell, _feature_kolonner(), kamper=[kamp], hent_lagstats=_stub_lagstats
    )

    assert value_bets == []


def test_finn_value_bets_velger_beste_odds_pa_tvers_av_bookmakers():
    """De beste oddsene per side skal være maksimum på tvers av alle bookmakere."""
    modell = _StubModell(prob_hjemme=0.65)
    kamp = _kamp(bookmakere=[
        {
            "title": "DårligBook",
            "markets": [{
                "key": "h2h",
                "outcomes": [
                    {"name": HEAT, "price": 1.90},
                    {"name": RAPTORS, "price": 1.70},
                ],
            }],
        },
        {
            "title": "BestBook",
            "markets": [{
                "key": "h2h",
                "outcomes": [
                    {"name": HEAT, "price": 2.10},
                    {"name": RAPTORS, "price": 1.80},
                ],
            }],
        },
    ])

    value_bets = finn_value_bets(
        modell, _feature_kolonner(), kamper=[kamp], hent_lagstats=_stub_lagstats
    )

    assert len(value_bets) == 1
    assert value_bets[0]["Odds"] == 2.10
    assert value_bets[0]["Bookmaker"] == "BestBook"


def test_skriv_value_bets_csv_tom_liste_skriver_kun_header(tmp_path):
    """skriv_value_bets_csv([]) skal skrive en CSV med kun KOLONNER-headeren og ingen datarader."""
    sti = tmp_path / "value_bets_idag.csv"

    skriv_value_bets_csv([], sti=str(sti))

    df = pd.read_csv(sti)
    assert list(df.columns) == KOLONNER
    assert len(df) == 0
