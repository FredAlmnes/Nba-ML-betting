"""
Tester for skadefilter.py — skadefilter-beslutningslogikken flyttet ut av
05_skadefilter.py som importerbare funksjoner (plan 04-02).

Beviser to ting: (1) at å importere modulen ikke lenger gjør fire nba_api-
kall slik den gamle 05_skadefilter.py gjorde ved import (SESONG/print-
blokken kjørte på modul-nivå), og (2) at beslutningsreglene (sjekk_spiller,
hent_toppspillere_for_lag, filtrer_bets_for_skader) oppfører seg identisk
med før, gitt injiserte DataFrames — ingen nettverkskall.

Denne filen dekker nå også as-of-varianten lagt til for Fase 5s
walk-forward-backtest (plan 05-06): sesong_grenser_for_dato,
hent_sesonglogg_som_of, hent_toppspillere_som_of, bygg_siste3_som_of og
sjekk_lag_helse_som_of. Negativ-kontroll-testen
(test_sjekk_lag_helse_som_of_negativ_kontroll_etter_as_of_rader_ignoreres)
er skadefilterets halvdel av BT-02s lekkasjebevis — den andre halvdelen er
tests/test_parity.py::test_grenserad_paa_as_of_er_ekskludert på feature-siden.
"""

import importlib

import pandas as pd
import pytest

import skadefilter
from skadefilter import (
    ANTALL_TOPPSPILLERE,
    MIN_MINUTTER,
    SISTE_N_KAMPER,
    bygg_siste3_som_of,
    filtrer_bets_for_skader,
    hent_sesonglogg_som_of,
    hent_toppspillere_for_lag,
    hent_toppspillere_som_of,
    sesong_grenser_for_dato,
    sjekk_lag_helse,
    sjekk_lag_helse_som_of,
    sjekk_spiller,
)

# Ekte NBA-lag-IDer, resolverbare via teams.finn_lag_id (Miami Heat / Toronto Raptors).
HEAT_ID = 1610612748
RAPTORS_ID = 1610612761


def test_import_skadefilter_gjor_ingen_nettverkskall(monkeypatch):
    """
    Reloader skadefilter med LeagueDashPlayerStats erstattet av en funksjon
    som kaster AssertionError hvis den kalles. Modulen skal lastes uten
    feil — det beviser at ingen kode på modul-nivå gjør nba_api-kall (i
    motsetning til gamle 05_skadefilter.py, som hentet spillerdata og
    printet "Bruker sesong: ..." ved import).
    """
    from nba_api.stats.endpoints import leaguedashplayerstats

    def _sprengt(*args, **kwargs):
        raise AssertionError("LeagueDashPlayerStats skal IKKE kalles ved import")

    monkeypatch.setattr(leaguedashplayerstats, "LeagueDashPlayerStats", _sprengt)

    modul = importlib.reload(skadefilter)
    assert modul is not None


def test_sjekk_spiller_fraverende_spiller_gir_false():
    siste3 = pd.DataFrame(columns=["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "MIN", "GP"])
    ok, melding = sjekk_spiller(siste3, 999, "Testspiller", 25.0)
    assert ok is False
    assert "Testspiller" in melding
    assert "0 kamper siste 3" in melding


def test_sjekk_spiller_lavt_gp_gir_false():
    siste3 = pd.DataFrame([
        {"PLAYER_ID": 1, "PLAYER_NAME": "Spiller A", "TEAM_ID": HEAT_ID, "MIN": 15.0, "GP": 1},
    ])
    ok, _ = sjekk_spiller(siste3, 1, "Spiller A", 30.0)
    assert ok is False


def test_sjekk_spiller_lave_minutter_gir_false():
    siste3 = pd.DataFrame([
        {"PLAYER_ID": 1, "PLAYER_NAME": "Spiller A", "TEAM_ID": HEAT_ID, "MIN": 8.0, "GP": 3},
    ])
    ok, _ = sjekk_spiller(siste3, 1, "Spiller A", 30.0)
    assert ok is False


def test_sjekk_spiller_ok_gir_true():
    siste3 = pd.DataFrame([
        {"PLAYER_ID": 1, "PLAYER_NAME": "Spiller A", "TEAM_ID": HEAT_ID, "MIN": 32.0, "GP": 3},
    ])
    ok, melding = sjekk_spiller(siste3, 1, "Spiller A", 30.0)
    assert ok is True
    assert "Spiller A" in melding


def test_hent_toppspillere_for_lag_respekterer_grense_og_sortering():
    sesong_snitt = pd.DataFrame([
        {"PLAYER_ID": 1, "PLAYER_NAME": "A", "TEAM_ID": HEAT_ID, "MIN": 30.0},
        {"PLAYER_ID": 2, "PLAYER_NAME": "B", "TEAM_ID": HEAT_ID, "MIN": 25.0},
        {"PLAYER_ID": 3, "PLAYER_NAME": "C", "TEAM_ID": HEAT_ID, "MIN": 22.0},
        {"PLAYER_ID": 4, "PLAYER_NAME": "D", "TEAM_ID": HEAT_ID, "MIN": 21.0},
        {"PLAYER_ID": 5, "PLAYER_NAME": "E", "TEAM_ID": HEAT_ID, "MIN": 15.0},  # under MIN_MINUTTER
    ])
    topp = hent_toppspillere_for_lag(sesong_snitt, HEAT_ID)
    assert len(topp) == ANTALL_TOPPSPILLERE
    minutter = [sp["MIN"] for sp in topp]
    assert minutter == sorted(minutter, reverse=True)
    assert all(sp["MIN"] >= MIN_MINUTTER for sp in topp)


def _value_df(kamp="Miami Heat vs Toronto Raptors"):
    return pd.DataFrame([{
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
    }])


def _sesong_snitt_topp3(team_id, min_verdi=30.0):
    return pd.DataFrame([
        {"PLAYER_ID": team_id * 10 + i, "PLAYER_NAME": f"Spiller {i}", "TEAM_ID": team_id, "MIN": min_verdi - i}
        for i in range(ANTALL_TOPPSPILLERE)
    ])


def test_filtrer_bets_for_skader_ingen_nettverkskall_og_bevarer_radantall(monkeypatch):
    """Med siste3/sesong_snitt injisert skal ingen nba_api-kall skje, og radantallet bevares."""
    from nba_api.stats.endpoints import leaguedashplayerstats

    def _sprengt(*args, **kwargs):
        raise AssertionError("Skal ikke kalle nba_api når siste3/sesong_snitt er injisert")

    monkeypatch.setattr(leaguedashplayerstats, "LeagueDashPlayerStats", _sprengt)

    sesong_snitt = pd.concat([
        _sesong_snitt_topp3(HEAT_ID),
        _sesong_snitt_topp3(RAPTORS_ID),
    ], ignore_index=True)

    siste3 = pd.DataFrame([
        {"PLAYER_ID": rad["PLAYER_ID"], "PLAYER_NAME": rad["PLAYER_NAME"],
         "TEAM_ID": rad["TEAM_ID"], "MIN": rad["MIN"], "GP": 3}
        for _, rad in sesong_snitt.iterrows()
    ])

    value_df = _value_df()
    resultat = filtrer_bets_for_skader(value_df, siste3=siste3, sesong_snitt=sesong_snitt)

    assert len(resultat) == len(value_df)
    assert resultat.iloc[0]["Skadestatus"] == "✅ OK"
    assert resultat.iloc[0]["Skadeinfo"] == "Alle nøkkelspillere spilte siste 3 kamper"


def test_filtrer_bets_for_skader_flagger_usikker_ved_fravaerende_toppspiller():
    sesong_snitt = pd.concat([
        _sesong_snitt_topp3(HEAT_ID),
        _sesong_snitt_topp3(RAPTORS_ID),
    ], ignore_index=True)

    # Heat sin beste spiller (høyest MIN) mangler helt fra siste3-datasettet -> 0 kamper siste 3.
    heat_topp_id = (
        sesong_snitt[sesong_snitt["TEAM_ID"] == HEAT_ID]
        .sort_values("MIN", ascending=False)
        .iloc[0]["PLAYER_ID"]
    )
    siste3_rader = []
    for _, rad in sesong_snitt.iterrows():
        if rad["PLAYER_ID"] == heat_topp_id:
            continue
        siste3_rader.append({
            "PLAYER_ID": rad["PLAYER_ID"], "PLAYER_NAME": rad["PLAYER_NAME"],
            "TEAM_ID": rad["TEAM_ID"], "MIN": rad["MIN"], "GP": 3,
        })
    siste3 = pd.DataFrame(siste3_rader)

    value_df = _value_df()
    resultat = filtrer_bets_for_skader(value_df, siste3=siste3, sesong_snitt=sesong_snitt)

    assert len(resultat) == len(value_df)
    assert resultat.iloc[0]["Skadestatus"] == "⚠️  USIKKER"
    assert resultat.iloc[0]["Skadeinfo"] != ""


def test_filtrer_bets_for_skader_hopper_over_uresolverbart_lagnavn(monkeypatch):
    """Et lagnavn finn_lag_id() ikke klarer å løse skal hoppes over uten å kaste (dagens continue-oppførsel)."""
    monkeypatch.setattr(skadefilter, "finn_lag_id", lambda navn: None)

    value_df = _value_df()
    sesong_snitt = pd.DataFrame(columns=["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "MIN"])
    siste3 = pd.DataFrame(columns=["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "MIN", "GP"])

    resultat = filtrer_bets_for_skader(value_df, siste3=siste3, sesong_snitt=sesong_snitt)

    assert len(resultat) == len(value_df)
    assert resultat.iloc[0]["Skadestatus"] == "✅ OK"


# ---------------------------------------------------------------------
# As-of-vei (plan 05-06, Fase 5s walk-forward-backtest)
#
# Alle datoer under er hardkodet inne i 2022-23-sesongen. Ingen
# tilfeldig tallgenerator, ingen lesing av systemklokken noe sted.
# ---------------------------------------------------------------------


def _spillerlogg(rader):
    """Bygger en syntetisk spillerlogg-DataFrame fra en liste med
    (player_id, navn, team_id, dato, minutter)-tupler."""
    return pd.DataFrame([
        {"PLAYER_ID": pid, "PLAYER_NAME": navn, "TEAM_ID": team_id, "GAME_DATE": dato, "MIN": minutter}
        for pid, navn, team_id, dato, minutter in rader
    ])


def _lagkamper(team_id, datoer, spillere):
    """Emitterer én rad per spiller per dato, slik at den vanlige 'tre
    friske startere over N kampdatoer'-fixturen blir én linje. 'spillere'
    er en liste med (player_id, navn, minutter)-tupler."""
    rader = [
        (pid, navn, team_id, dato, minutter)
        for dato in datoer
        for pid, navn, minutter in spillere
    ]
    return _spillerlogg(rader)


def test_sesong_grenser_for_dato_deler_paa_oktober():
    assert sesong_grenser_for_dato("2022-10-24") == ("2022-10-01", "2023-10-01")
    assert sesong_grenser_for_dato("2023-04-13") == ("2022-10-01", "2023-10-01")
    assert sesong_grenser_for_dato("2024-10-01") == ("2024-10-01", "2025-10-01")
    assert sesong_grenser_for_dato("2023-09-30") == ("2022-10-01", "2023-10-01")
    assert sesong_grenser_for_dato(pd.Timestamp("2023-04-13")) == sesong_grenser_for_dato("2023-04-13")


def test_sesong_grenser_for_dato_leser_ikke_klokken(monkeypatch):
    """Kjernebeviset for as-of-fiksen. skadefilter._dt erstattes med en
    stubbe hvis now() kaster -- sesong_grenser_for_dato skal likevel svare
    korrekt, mens gjeldende_sesong() (den uendrede live-funksjonen) skal
    kaste. Den andre halvdelen er kontrollen på kontrollen: den beviser at
    stubben faktisk er koblet inn og at den første assert-en er meningsfull."""

    class _Klokkestopp:
        @staticmethod
        def now():
            raise AssertionError("skadefilter._dt.now() skal IKKE kalles av as-of-veien")

    monkeypatch.setattr(skadefilter, "_dt", _Klokkestopp)

    assert sesong_grenser_for_dato("2023-01-15") == ("2022-10-01", "2023-10-01")

    with pytest.raises(AssertionError):
        skadefilter.gjeldende_sesong()


def test_hent_sesonglogg_som_of_ekskluderer_grenseraden():
    """Strengt <-kontrakten -- feature-sidens tvilling er
    tests/test_parity.py::test_grenserad_paa_as_of_er_ekskludert."""
    datoer = ["2023-01-02", "2023-01-04", "2023-01-06", "2023-01-08", "2023-01-10"]
    logg = _lagkamper(HEAT_ID, datoer, [(1, "Spiller A", 30.0)])

    resultat = hent_sesonglogg_som_of(logg, HEAT_ID, "2023-01-06")

    assert len(resultat) == 2
    assert "2023-01-06" not in resultat["GAME_DATE"].values


def test_hent_sesonglogg_som_of_ekskluderer_forrige_sesong():
    """Minutter fra en tidligere sesong skal ikke kunne gjøre en spiller
    til en nåværende toppspiller."""
    logg = _spillerlogg([
        (1, "Spiller A", HEAT_ID, "2022-03-15", 30.0),  # 2021-22-sesongen
        (1, "Spiller A", HEAT_ID, "2023-01-02", 30.0),
        (1, "Spiller A", HEAT_ID, "2023-01-04", 30.0),
    ])

    resultat = hent_sesonglogg_som_of(logg, HEAT_ID, "2023-01-06")

    assert "2022-03-15" not in resultat["GAME_DATE"].values
    assert len(resultat) == 2


def test_hent_toppspillere_som_of_bruker_sesong_til_dato_snitt():
    datoer = ["2023-01-02", "2023-01-04", "2023-01-06", "2023-01-08", "2023-01-10"]
    spillere = [
        (1, "A", 32.0),
        (2, "B", 28.0),
        (3, "C", 24.0),
        (4, "D", 15.0),  # under MIN_MINUTTER
        (5, "E", 10.0),  # under MIN_MINUTTER
    ]
    logg = _lagkamper(HEAT_ID, datoer, spillere)
    sesong_logg = hent_sesonglogg_som_of(logg, HEAT_ID, "2023-01-12")

    topp = hent_toppspillere_som_of(sesong_logg)

    assert len(topp) == ANTALL_TOPPSPILLERE
    minutter = [sp["MIN"] for sp in topp]
    assert minutter == sorted(minutter, reverse=True)
    assert all(sp["MIN"] >= MIN_MINUTTER for sp in topp)
    assert set(topp[0].keys()) == {"PLAYER_ID", "PLAYER_NAME", "MIN"}


def test_bygg_siste3_som_of_bruker_lagets_kampdatoer_ikke_spillerens():
    """Den korrigerte Pattern 7-vinduet. Det naive per-spiller-tail(3)-
    alternativet ville rapportert GP == 2 her, og gjort filteret
    strukturelt ute av stand til å flagge en skadet spiller."""
    rader = [
        (1, "Toppspiller", HEAT_ID, "2023-01-02", 32.0),
        (1, "Toppspiller", HEAT_ID, "2023-01-04", 32.0),
        # Fraværende fra lagets tre siste datoer (01-06, 01-08, 01-10).
        (2, "B", HEAT_ID, "2023-01-06", 28.0),
        (2, "B", HEAT_ID, "2023-01-08", 28.0),
        (2, "B", HEAT_ID, "2023-01-10", 28.0),
    ]
    logg = _spillerlogg(rader)
    sesong_logg = hent_sesonglogg_som_of(logg, HEAT_ID, "2023-01-12")

    siste3 = bygg_siste3_som_of(sesong_logg)

    assert 1 not in siste3["PLAYER_ID"].values


def test_sjekk_lag_helse_som_of_alle_tilgjengelige_gir_ok():
    datoer = ["2023-01-02", "2023-01-04", "2023-01-06", "2023-01-08", "2023-01-10"]
    spillere = [(1, "A", 30.0), (2, "B", 30.0), (3, "C", 30.0)]
    logg = _lagkamper(HEAT_ID, datoer, spillere)

    resultat = sjekk_lag_helse_som_of(logg, HEAT_ID, "Miami Heat", "2023-01-12")

    assert resultat["tilgjengelig"] is True
    assert resultat["advarsler"] == []
    assert resultat["antall_toppspillere"] == ANTALL_TOPPSPILLERE
    assert resultat["antall_kamprader"] > 0


def _fravaerende_toppspiller_rader():
    return [
        (1, "Stjerne", HEAT_ID, "2023-01-02", 35.0),
        (1, "Stjerne", HEAT_ID, "2023-01-04", 35.0),
        # Stjerne fraværende fra lagets tre siste datoer (01-06/08/10).
        (2, "B", HEAT_ID, "2023-01-02", 28.0), (2, "B", HEAT_ID, "2023-01-04", 28.0),
        (2, "B", HEAT_ID, "2023-01-06", 28.0), (2, "B", HEAT_ID, "2023-01-08", 28.0),
        (2, "B", HEAT_ID, "2023-01-10", 28.0),
        (3, "C", HEAT_ID, "2023-01-02", 26.0), (3, "C", HEAT_ID, "2023-01-04", 26.0),
        (3, "C", HEAT_ID, "2023-01-06", 26.0), (3, "C", HEAT_ID, "2023-01-08", 26.0),
        (3, "C", HEAT_ID, "2023-01-10", 26.0),
    ]


def test_sjekk_lag_helse_som_of_flagger_fravaerende_toppspiller():
    logg = _spillerlogg(_fravaerende_toppspiller_rader())

    resultat = sjekk_lag_helse_som_of(logg, HEAT_ID, "Miami Heat", "2023-01-12")

    assert resultat["tilgjengelig"] is False
    assert len(resultat["advarsler"]) == 1
    assert "Stjerne" in resultat["advarsler"][0]


def test_sjekk_lag_helse_som_of_negativ_kontroll_etter_as_of_rader_ignoreres():
    """THE lekkasjebeviset, og grunnen til at denne planen finnes. Dette
    er BT-02s skadesiden av lekkasjebeviset -- enten en <=-sammenligning
    eller en klokke-utledet sesonggrense ville fått denne til å feile.

    Logg A inneholder kun rader strengt før as_of_dato, der toppspilleren
    er fraværende fra lagets tre siste datoer -> tilgjengelig=False. Logg
    B er A pluss rader datert PÅ og ETTER as_of_dato der samme spiller
    returnerer og spiller 35 min i tre påfølgende kamper -- data som,
    hvis den lekket inn, ville snudd verdikten til frisk."""
    as_of = "2023-01-12"
    rader_a = _fravaerende_toppspiller_rader()
    logg_a = _spillerlogg(rader_a)

    rader_b = rader_a + [
        (1, "Stjerne", HEAT_ID, "2023-01-12", 35.0),
        (1, "Stjerne", HEAT_ID, "2023-01-14", 35.0),
        (1, "Stjerne", HEAT_ID, "2023-01-16", 35.0),
    ]
    logg_b = _spillerlogg(rader_b)

    resultat_a = sjekk_lag_helse_som_of(logg_a, HEAT_ID, "Miami Heat", as_of)
    resultat_b = sjekk_lag_helse_som_of(logg_b, HEAT_ID, "Miami Heat", as_of)

    assert resultat_a["tilgjengelig"] is False  # kontroll på kontrollen: testen kan ikke bestå vacuously
    assert resultat_a == resultat_b


def test_sjekk_lag_helse_som_of_samme_terskler_som_live():
    """Pinner as-of-veien til MIN_MINUTTER/ANTALL_TOPPSPILLERE/sjekk_spiller
    i stedet for en re-utledet kopi av regelen -- kjører både frisk- og
    flagget-scenario gjennom begge veier fra ekvivalente data."""
    datoer = ["2023-01-02", "2023-01-04", "2023-01-06", "2023-01-08", "2023-01-10"]

    # Frisk scenario: alle tre toppspillere spilte lagets tre siste kamper.
    spillere_ok = [(1, "A", 30.0), (2, "B", 28.0), (3, "C", 26.0)]
    logg_ok = _lagkamper(HEAT_ID, datoer, spillere_ok)
    as_of_resultat_ok = sjekk_lag_helse_som_of(logg_ok, HEAT_ID, "Miami Heat", "2023-01-12")

    siste3_ok = pd.DataFrame([
        {"PLAYER_ID": pid, "PLAYER_NAME": navn, "TEAM_ID": HEAT_ID, "MIN": minutter, "GP": 3}
        for pid, navn, minutter in spillere_ok
    ])
    sesong_snitt_ok = pd.DataFrame([
        {"PLAYER_ID": pid, "PLAYER_NAME": navn, "TEAM_ID": HEAT_ID, "MIN": minutter}
        for pid, navn, minutter in spillere_ok
    ])
    live_resultat_ok = sjekk_lag_helse(siste3_ok, sesong_snitt_ok, HEAT_ID, "Miami Heat")

    assert as_of_resultat_ok["tilgjengelig"] == live_resultat_ok["tilgjengelig"] == True
    assert list(as_of_resultat_ok)[:3] == list(live_resultat_ok)[:3]

    # Flagget scenario: toppspilleren fraværende fra lagets tre siste kamper.
    logg_flagg = _spillerlogg(_fravaerende_toppspiller_rader())
    as_of_resultat_flagg = sjekk_lag_helse_som_of(logg_flagg, HEAT_ID, "Miami Heat", "2023-01-12")

    siste3_flagg = pd.DataFrame([
        {"PLAYER_ID": 2, "PLAYER_NAME": "B", "TEAM_ID": HEAT_ID, "MIN": 28.0, "GP": 3},
        {"PLAYER_ID": 3, "PLAYER_NAME": "C", "TEAM_ID": HEAT_ID, "MIN": 26.0, "GP": 3},
    ])
    sesong_snitt_flagg = pd.DataFrame([
        {"PLAYER_ID": 1, "PLAYER_NAME": "Stjerne", "TEAM_ID": HEAT_ID, "MIN": 35.0},
        {"PLAYER_ID": 2, "PLAYER_NAME": "B", "TEAM_ID": HEAT_ID, "MIN": 28.0},
        {"PLAYER_ID": 3, "PLAYER_NAME": "C", "TEAM_ID": HEAT_ID, "MIN": 26.0},
    ])
    live_resultat_flagg = sjekk_lag_helse(siste3_flagg, sesong_snitt_flagg, HEAT_ID, "Miami Heat")

    assert as_of_resultat_flagg["tilgjengelig"] == live_resultat_flagg["tilgjengelig"] == False
    assert list(as_of_resultat_flagg)[:3] == list(live_resultat_flagg)[:3]


def test_sjekk_lag_helse_som_of_manglende_kolonne_reiser_valueerror():
    logg = pd.DataFrame([
        {"PLAYER_ID": 1, "PLAYER_NAME": "A", "TEAM_ID": HEAT_ID, "GAME_DATE": "2023-01-02"}
    ])

    with pytest.raises(ValueError) as excinfo:
        sjekk_lag_helse_som_of(logg, HEAT_ID, "Miami Heat", "2023-01-06")

    assert "MIN" in str(excinfo.value)


def test_sjekk_lag_helse_som_of_datetimekolonne_reiser_valueerror():
    logg = _spillerlogg([(1, "A", HEAT_ID, "2023-01-02", 30.0)])
    logg["GAME_DATE"] = pd.to_datetime(logg["GAME_DATE"])

    with pytest.raises(ValueError) as excinfo:
        sjekk_lag_helse_som_of(logg, HEAT_ID, "Miami Heat", "2023-01-06")

    assert "les_spillerlogg" in str(excinfo.value)


def test_sjekk_lag_helse_som_of_uten_dekning_rapporterer_tomt_datagrunnlag(monkeypatch):
    """Beviser to ting: (1) ingen nettverkskall skjer -- trygt inne i en
    ~960-iterasjons walk-forward-løkke -- og (2) et vacuous pass
    rapporteres via tellerne fremfor å være umulig å skille fra et
    genuint friskt lag."""
    from nba_api.stats.endpoints import leaguedashplayerstats

    def _sprengt(*args, **kwargs):
        raise AssertionError("LeagueDashPlayerStats skal IKKE kalles av as-of-veien")

    monkeypatch.setattr(leaguedashplayerstats, "LeagueDashPlayerStats", _sprengt)

    tom_logg = pd.DataFrame(columns=["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "GAME_DATE", "MIN"])
    resultat = sjekk_lag_helse_som_of(tom_logg, HEAT_ID, "Miami Heat", "2023-01-12")

    assert resultat["tilgjengelig"] is True
    assert resultat["antall_toppspillere"] == 0
    assert resultat["antall_kamprader"] == 0
