"""
Tester for 06_bot.py sin kjør_pipeline()-funksjon etter at subprocess-kallene
mot 04_value_detector.py/05_skadefilter.py ble erstattet med direkte importer
av odds.py/verdi_deteksjon.py/skadefilter.py (plan 04-08).

Disse testene tar ALDRI kontakt med nettverket, den ekte modell-pickle-filen
eller de ekte JSON-tilstandsfilene (bankroll.json/bets.json) — 06_bot.py
lastes via importlib (siden filnavnet starter med et siffer og ikke kan
importeres normalt), og odds-/verdi_deteksjon-/skadefilter-modulattributtene
på den lastede bot-modulen erstattes med injiserte stubber via monkeypatch.
"""

import importlib.util
import json
from datetime import date, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest


def _last_bot():
    spec = importlib.util.spec_from_file_location("bot", "06_bot.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture
def bot():
    return _last_bot()


def _ok_bet(kamp="Miami Heat vs Toronto Raptors"):
    return {
        "Kamp": kamp,
        "KampDato": "2026-01-15",
        "Bet": "Hjemme (Miami Heat)",
        "Odds": 1.85,
        "Bookmaker": "TestBook",
        "Modell_prob": 0.58,
        "Modell %": "58.0%",
        "Bookmaker %": "54.0%",
        "Value": "+4.0%",
        "Forv. EV": "+2.3%",
    }


def _skadefilter_df(status_liste):
    """Bygger en resultat-DataFrame slik filtrer_bets_for_skader ville returnert,
    én rad per status i status_liste (de ekte emoji-strengene fra skadefilter.py)."""
    rader = []
    for status in status_liste:
        rad = _ok_bet()
        rad["Skadestatus"] = status
        rad["Skadeinfo"] = (
            "Alle nøkkelspillere spilte siste 3 kamper" if "OK" in status else "Testspiller mangler"
        )
        rader.append(rad)
    return pd.DataFrame(rader)


def _stub_moduler(
    monkeypatch,
    bot,
    *,
    api_nokkel_feiler=False,
    value_bets_feiler=False,
    skadefilter_feiler=False,
    value_bets=None,
    skadestatuser=("✅ OK",),
):
    """Erstatter bot.odds/bot.verdi_deteksjon/bot.skadefilter med stubbede
    moduler slik at kjør_pipeline aldri tar kontakt med nettverket eller disk."""
    if value_bets is None:
        value_bets = [_ok_bet()]

    def hent_api_nokkel():
        if api_nokkel_feiler:
            raise SystemExit(1)
        return "test-nøkkel"

    fake_odds = SimpleNamespace(hent_api_nokkel=hent_api_nokkel)

    def last_modell(sti="nba_modell.pkl"):
        return ("fake-modell", ["kol1", "kol2"])

    def finn_value_bets(modell, feature_kolonner, kamper=None, api_nokkel=None, hent_lagstats=None):
        if value_bets_feiler:
            raise RuntimeError("simulert feil i value-pipelinen")
        return value_bets

    def skriv_value_bets_csv(bets, sti="value_bets_idag.csv"):
        pass  # aldri skriv til disk i tester

    fake_verdi = SimpleNamespace(
        last_modell=last_modell,
        finn_value_bets=finn_value_bets,
        skriv_value_bets_csv=skriv_value_bets_csv,
    )

    def filtrer_bets_for_skader(value_df, siste3=None, sesong_snitt=None):
        if skadefilter_feiler:
            raise ValueError("simulert feil i skadefilter")
        return _skadefilter_df(skadestatuser)

    def skriv_skadefilter_csv(resultat_df, sti="value_bets_med_skadefilter.csv"):
        pass  # aldri skriv til disk i tester

    fake_skadefilter = SimpleNamespace(
        filtrer_bets_for_skader=filtrer_bets_for_skader,
        skriv_skadefilter_csv=skriv_skadefilter_csv,
    )

    monkeypatch.setattr(bot, "odds", fake_odds)
    monkeypatch.setattr(bot, "verdi_deteksjon", fake_verdi)
    monkeypatch.setattr(bot, "skadefilter", fake_skadefilter)


def test_pipeline_returner_kun_ok_rader_ved_suksess(monkeypatch, bot):
    _stub_moduler(monkeypatch, bot, skadestatuser=("✅ OK", "⚠️  USIKKER"))
    resultat = bot.kjør_pipeline()
    assert resultat is not None
    assert len(resultat) == 1
    assert resultat.iloc[0]["Skadestatus"] == "✅ OK"


def test_pipeline_feil_degraderer_grasiost(monkeypatch, bot):
    """kjør_pipeline skal returnere None (ikke la unntaket forplante seg) når
    verdi_deteksjon.finn_value_bets kaster RuntimeError."""
    _stub_moduler(monkeypatch, bot, value_bets_feiler=True)
    resultat = bot.kjør_pipeline()
    assert resultat is None


def test_pipeline_returnerer_none_ved_systemexit_fra_api_nokkel(monkeypatch, bot):
    """odds.hent_api_nokkel() kaller sys.exit(1) ved manglende nøkkel — dette
    kaster SystemExit, som ARVER FRA BaseException, ikke Exception. En bare
    'except Exception' ville IKKE fanget dette og boten ville krasjet midt i
    kjøringen, før bankroll/bets ble lagret. Krasjbarrieren MÅ derfor være
    'except (Exception, SystemExit)'."""
    _stub_moduler(monkeypatch, bot, api_nokkel_feiler=True)
    resultat = bot.kjør_pipeline()
    assert resultat is None


def test_pipeline_returnerer_none_ved_feil_i_skadefilter(monkeypatch, bot):
    _stub_moduler(monkeypatch, bot, skadefilter_feiler=True)
    resultat = bot.kjør_pipeline()
    assert resultat is None


def test_pipeline_returnerer_none_ved_tom_value_bets_liste(monkeypatch, bot):
    _stub_moduler(monkeypatch, bot, value_bets=[])
    resultat = bot.kjør_pipeline()
    assert resultat is None


def test_pipeline_returnerer_none_naar_alle_er_usikker(monkeypatch, bot):
    _stub_moduler(monkeypatch, bot, skadestatuser=("⚠️  USIKKER", "⚠️  USIKKER"))
    resultat = bot.kjør_pipeline()
    assert resultat is None


def test_import_bot_gjor_ingen_nettverkskall(monkeypatch):
    """Å laste 06_bot.py (importlib, siden filnavnet starter med et siffer)
    skal ikke gjøre noe nba_api-kall — beviser at det ikke finnes kode på
    modul-nivå som tar kontakt med nettverket."""
    from nba_api.stats.endpoints import leaguegamefinder

    def _sprengt(*args, **kwargs):
        raise AssertionError("LeagueGameFinder skal IKKE kalles ved import av 06_bot.py")

    monkeypatch.setattr(leaguegamefinder, "LeagueGameFinder", _sprengt)

    modul = _last_bot()
    assert modul is not None


def test_bot_kildekode_har_ingen_subprocess_eller_python310_referanse():
    """D-05/D-06: subprocess-kallene og den hardkodede python3.10-PYTHONPATH-en
    skal være fjernet fra 06_bot.py sin kildekode."""
    with open("06_bot.py", "r", encoding="utf-8") as f:
        kildekode = f.read()
    assert "subprocess" not in kildekode
    assert "python3.10" not in kildekode
    assert "PYTHONPATH" not in kildekode


# ---------------------------------------------------------------------------
# CR-01: stored XSS via lagnavn fra The Odds API i dashboard.html
# ---------------------------------------------------------------------------


def _ok_dashboard_bet(kamp="Miami Heat vs Toronto Raptors", value="+4.0%"):
    return {
        "dato": "2026-01-15",
        "kamp_dato": "2026-01-15",
        "kamp": kamp,
        "bet": "Hjemme (Miami Heat)",
        "odds": 1.85,
        "innsats": 50.0,
        "modell": "58.0%",
        "modell_prob": 0.58,
        "value": value,
        "ev": "+2.3%",
        "status": "venter",
        "gevinst": None,
    }


def _ok_bankroll_data(saldo=1000.0):
    return {"saldo": saldo, "historikk": [{"dato": "2026-01-15", "saldo": saldo}]}


def test_json_til_script_fjerner_alle_mindre_enn_tegn_uten_aa_endre_dataene(bot):
    data = [{"kamp": "</script><script>alert(1)</script>"}]
    resultat = bot._json_til_script(data)
    assert "<" not in resultat
    assert json.loads(resultat) == data


def test_generer_dashboard_escaper_ondsinnet_lagnavn_og_value(monkeypatch, bot, tmp_path):
    dashboard_fil = tmp_path / "dashboard.html"
    monkeypatch.setattr(bot, "DASHBOARD_FIL", str(dashboard_fil))

    ondsinnet_bet = _ok_dashboard_bet(
        kamp="<img src=x onerror=alert(1)> vs </script><script>alert(2)</script>",
        value="<svg onload=alert(3)>",
    )
    bot.generer_dashboard([ondsinnet_bet], _ok_bankroll_data())

    html = dashboard_fil.read_text(encoding="utf-8")
    assert html.count("</script>") == 2
    assert "<img src=x onerror=" not in html
    assert "<svg onload=" not in html
    assert "\\u003c" in html


def test_generer_dashboard_normalt_bet_uendret(monkeypatch, bot, tmp_path):
    dashboard_fil = tmp_path / "dashboard.html"
    monkeypatch.setattr(bot, "DASHBOARD_FIL", str(dashboard_fil))

    bot.generer_dashboard([_ok_dashboard_bet()], _ok_bankroll_data())

    html = dashboard_fil.read_text(encoding="utf-8")
    assert "Miami Heat" in html
    assert '<tbody id="bet-body">' in html
    assert "const bets" in html


# ---------------------------------------------------------------------------
# CR-02: ett historikkpunkt per dag, skrevet etter oppgjør OG plassering
# ---------------------------------------------------------------------------


def _venter_bet(kamp_dato, kamp="Miami Heat vs Toronto Raptors", bet="Hjemme (Miami Heat)",
                 odds=2.0, innsats=100.0):
    return {
        "dato": kamp_dato,
        "kamp_dato": kamp_dato,
        "kamp": kamp,
        "bet": bet,
        "odds": odds,
        "innsats": innsats,
        "modell": "60.0%",
        "modell_prob": 0.6,
        "value": "+5.0%",
        "ev": "+20.0%",
        "status": "venter",
        "gevinst": None,
    }


def test_sjekk_resultater_ruhrer_ikke_historikk(monkeypatch, bot):
    i_gaar = str(date.today() - timedelta(days=1))
    bets = [_venter_bet(i_gaar)]
    historikk_original = [{"dato": "2020-01-01", "saldo": 500.0}]
    bankroll_data = {"saldo": 1000.0, "historikk": list(historikk_original)}

    monkeypatch.setattr(bot, "hent_kampresultat", lambda *a, **k: "hjemme")
    bets, bankroll_data = bot.sjekk_resultater(bets, bankroll_data)

    assert bankroll_data["saldo"] == 1100.0
    assert bankroll_data["historikk"] == historikk_original


def test_oppdater_dagens_historikk_oppdaterer_eksisterende_punkt(bot):
    i_dag = str(date.today())
    bankroll_data = {"saldo": 850.0, "historikk": [{"dato": i_dag, "saldo": 1000.0}]}

    bankroll_data = bot.oppdater_dagens_historikk(bankroll_data)

    assert len(bankroll_data["historikk"]) == 1
    assert bankroll_data["historikk"][0]["saldo"] == 850.0


def test_oppdater_dagens_historikk_legger_til_nytt_punkt(bot):
    i_gaar = str(date.today() - timedelta(days=1))
    i_dag = str(date.today())
    bankroll_data = {"saldo": 1120.0, "historikk": [{"dato": i_gaar, "saldo": 1000.0}]}

    bankroll_data = bot.oppdater_dagens_historikk(bankroll_data)

    assert len(bankroll_data["historikk"]) == 2
    assert bankroll_data["historikk"][-1] == {"dato": i_dag, "saldo": 1120.0}


def test_sekvens_oppgjor_og_plassering_samme_dag_gir_korrekt_historikkpunkt(monkeypatch, bot):
    """Reproduserer CR-02-buggen: dagens historikkpunkt skal reflektere saldoen
    ETTER både oppgjør av gamle bets OG plassering av nye, ikke bare oppgjøret."""
    i_dag  = str(date.today())
    i_gaar = str(date.today() - timedelta(days=1))

    bets = [_venter_bet(i_gaar)]
    bankroll_data = {"saldo": 1000.0, "historikk": [{"dato": i_dag, "saldo": 1000.0}]}

    monkeypatch.setattr(bot, "hent_kampresultat", lambda *a, **k: "hjemme")
    bets, bankroll_data = bot.sjekk_resultater(bets, bankroll_data)

    value_bets_df = pd.DataFrame([{
        "Kamp": "Boston Celtics vs New York Knicks",
        "KampDato": i_dag,
        "Bet": "Hjemme (Boston Celtics)",
        "Odds": 1.7,
        "Modell_prob": 0.65,
        "Modell %": "65.0%",
        "Value": "+10.0%",
        "Forv. EV": "+10.5%",
    }])
    bets, bankroll_data, nye = bot.plasser_bets(value_bets_df, bets, bankroll_data)
    assert nye == 1  # sikrer at innsatsen faktisk ble trukket, ellers tester vi ingenting

    bankroll_data = bot.oppdater_dagens_historikk(bankroll_data)

    dagens_punkt = next(h for h in bankroll_data["historikk"] if h["dato"] == i_dag)
    assert dagens_punkt["saldo"] == bankroll_data["saldo"]
