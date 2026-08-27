"""
Tester for backtest.py — Fase 5s walk-forward-motor (plan 05-07).

Hver test i denne filen er deterministisk — ingen systemklokke, ingen
nettverk, ingen `random` — og (bortsett fra de tre eksplisitt
skip-vaktede ekte-data-testene plan 05-07 Task 3 legger til) ingen
avhengighet av den ekte `odds_arkiv.db` eller `nba_features.csv`, som
speiler `tests/test_parity.py` sin egen docstring-disiplin.
"""

import inspect
import os

import pandas as pd
import pytest

import backtest
import config
import model
import odds


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
    # impl_prob 0.5 (eksakt, 1/2.00 er en toer-potens), modell_prob 0.5625
    # (eksakt, 9/16) og terskel 0.0625 (eksakt, 1/16) — alle tre er dyadiske
    # flyttall, så subtraksjonen 0.5625 - 0.5 blir EKSAKT 0.0625 uten
    # avrundingsstøy (Sterbenz' lemma). Dette er en bevisst korrigert
    # boundary-verdi: 0.55/0.05 (plan-literalens forslag) rammer
    # kanselleringsstøy — 0.55 - 0.5 blir 0.050000000000000044 i IEEE754,
    # STØRRE enn 0.05, ikke lik den — se 05-07-SUMMARY.md sin
    # deviation-seksjon, samme klasse flyttallsfunn som 05-02-SUMMARY.md
    # allerede dokumenterte for beregn_innsats.
    assert backtest.vurder_kamp(0.5625, 2.00, 2.00, min_value_terskel=0.0625) == []


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


# --- 2. Walk-forward-løkke og de to inngangspunktene ---

LAG = {
    "BOS": (1610612738, "Boston Celtics"),
    "MIA": (1610612748, "Miami Heat"),
    "LAL": (1610612747, "Los Angeles Lakers"),
    "PHI": (1610612755, "Philadelphia 76ers"),
}

_PARRINGER = [("BOS", "MIA"), ("LAL", "PHI"), ("MIA", "LAL"), ("PHI", "BOS")]


def _feature_rad(i, dato):
    hjemme, borte = _PARRINGER[i % len(_PARRINGER)]
    return {
        "GAME_ID": f"00{22400000 + i}",
        "GAME_DATE_HJEMME": dato,
        "TEAM_ABBREVIATION_HJEMME": hjemme,
        "TEAM_ABBREVIATION_BORTE": borte,
        "HJEMME_VANT": i % 2,
        "DIFF_PTS": 1.0 + (i % 7),
        "DIFF_FG_PCT": 0.01 * (i % 5),
        "HJEMME_RULL_PTS": 100.0 + (i % 10),
        "BORTE_RULL_PTS": 98.0 + (i % 8),
    }


def _lag_datoer(fra, til):
    """Fortløpende kalenderdager fra og med `fra` til og med `til` (strenger "YYYY-MM-DD")."""
    rng = pd.date_range(start=fra, end=til, freq="D")
    return [d.strftime("%Y-%m-%d") for d in rng]


@pytest.fixture
def features_df():
    """92 rader, ett spill per dato, over EKSAKT tre kalendermåneder (2022-11-01..2023-01-31) —
    holdt innenfor månedsgrensene med vilje, slik at retreningstellingen blir eksakt 3."""
    datoer = _lag_datoer("2022-11-01", "2023-01-31")
    rader = [_feature_rad(i, dato) for i, dato in enumerate(datoer)]
    return pd.DataFrame(rader)


def _arkivrad(event_id, kamp_dato, hjemme, borte, snapshot_type="bet_time",
              bookmaker="pinnacle", hjemme_odds=2.00, borte_odds=2.00):
    """Bygger to odds_arkiv-rader (hjemme+borte) for én kamp, gitt fulle lagnavn."""
    hjemme_id, hjemme_navn = LAG[hjemme]
    borte_id, borte_navn = LAG[borte]
    return [
        (
            "basketball_nba", event_id, kamp_dato, hjemme_navn, borte_navn,
            hjemme_id, borte_id, f"{kamp_dato}T18:00:00Z", snapshot_type,
            f"{kamp_dato}T13:00:00Z", bookmaker, "h2h", hjemme_navn, hjemme_odds,
            "2026-08-27T10:00:00",
        ),
        (
            "basketball_nba", event_id, kamp_dato, hjemme_navn, borte_navn,
            hjemme_id, borte_id, f"{kamp_dato}T18:00:00Z", snapshot_type,
            f"{kamp_dato}T13:00:00Z", bookmaker, "h2h", borte_navn, borte_odds,
            "2026-08-27T10:00:00",
        ),
    ]


@pytest.fixture
def arkiv_con(features_df):
    """In-memory-arkiv med bet_time OG closing-rader for hver rad i features_df."""
    con = odds.apne_arkiv(":memory:")
    for i, rad in features_df.iterrows():
        hjemme, borte = rad["TEAM_ABBREVIATION_HJEMME"], rad["TEAM_ABBREVIATION_BORTE"]
        dato = rad["GAME_DATE_HJEMME"]
        # Alternér prisene slik at noen kamper havner innenfor value/odds-vinduet
        # og noen utenfor.
        hjemme_odds = 1.80 if i % 3 == 0 else 3.20
        borte_odds = 2.30 if i % 3 == 0 else 1.35
        rader = _arkivrad(f"evt-{i}", dato, hjemme, borte, "bet_time",
                           hjemme_odds=hjemme_odds, borte_odds=borte_odds)
        odds.arkiver_odds_rader(con, rader)
        rader_closing = _arkivrad(f"evt-{i}", dato, hjemme, borte, "closing",
                                   hjemme_odds=hjemme_odds + 0.05, borte_odds=borte_odds - 0.05)
        odds.arkiver_odds_rader(con, rader_closing)
    return con


@pytest.fixture
def spillerlogg_df():
    """Tom, men riktig kolonneskjema-rammet spillerlogg — vacuous-pass-banen."""
    return pd.DataFrame(columns=["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "GAME_DATE", "MIN"])


@pytest.fixture
def data(features_df, arkiv_con, spillerlogg_df):
    return {
        "features_df": features_df,
        "datoer": sorted(features_df["GAME_DATE_HJEMME"].unique()),
        "spillerlogg_df": spillerlogg_df,
        "con": arkiv_con,
    }


def test_kjor_backtest_produserer_ledger(data):
    prediksjoner, resultat = backtest.kjor_backtest(data, min_treningskamper=20, skriv_ut=False)
    assert len(prediksjoner) > 0
    assert resultat["prediksjoner"] == len(prediksjoner)

    forventede_nokler = {
        "as_of_dato", "kamp_dato", "game_id", "kamp", "side", "bet",
        "hjemme_lag_id", "borte_lag_id", "modell", "retrent_dato",
        "modell_prob", "modell_prob_hjemme", "odds", "impl_prob", "value", "ev",
        "odds_bet_time_hjemme", "odds_bet_time_borte",
        "odds_closing_hjemme", "odds_closing_borte", "hjemme_vant",
    }
    for rad in prediksjoner:
        assert forventede_nokler.issubset(rad.keys())


def test_kjor_backtest_returnerer_navngitte_tellere(data):
    _, resultat = backtest.kjor_backtest(data, min_treningskamper=20, skriv_ut=False)
    forventede_tellere = {
        "fra_dato", "til_dato", "datoer_totalt", "datoer_behandlet",
        "datoer_hoppet_over_for_lite_treningsgrunnlag", "kamper_totalt",
        "kamper_hoppet_over_manglende_odds", "kamper_hoppet_over_ukjent_lag",
        "kamper_uten_closing_snapshot", "kandidater_flagget",
        "kandidater_blokkert_av_skadefilter", "skadesjekk_uten_datagrunnlag",
        "retreninger", "prediksjoner", "min_treningskamper", "kalibrer_andel",
        "min_value_terskel", "min_odds", "maks_odds", "skadefilter_aktiv",
    }
    assert set(resultat.keys()) == forventede_tellere
    assert resultat["datoer_totalt"] == (
        resultat["datoer_behandlet"] + resultat["datoer_hoppet_over_for_lite_treningsgrunnlag"]
    )


def test_retrening_skjer_en_gang_per_maned(data):
    prediksjoner, resultat = backtest.kjor_backtest(data, min_treningskamper=20, skriv_ut=False)
    assert resultat["retreninger"] == 3

    # Innenfor hver kalendermåned skal ALLE prediksjonsrader dele samme
    # retrent_dato (nøyaktig én gjenoppretrening per måned), og den datoen
    # skal selv ligge i den samme måneden (ikke en tidligere måneds anker).
    retrent_dato_per_maned = {}
    for rad in prediksjoner:
        m = rad["as_of_dato"][:7]
        if m in retrent_dato_per_maned:
            assert rad["retrent_dato"] == retrent_dato_per_maned[m]
        else:
            retrent_dato_per_maned[m] = rad["retrent_dato"]
            assert rad["retrent_dato"][:7] == m


def test_modellen_trenes_bare_paa_data_for_datoen(data, monkeypatch):
    ekte_tren = model.tren
    kalt_med = []

    def spion(features_df, as_of=None, kalibrer_andel=model.KALIBRER_ANDEL, verbose=False):
        kalt_med.append(as_of)
        return ekte_tren(features_df, as_of=as_of, kalibrer_andel=kalibrer_andel, verbose=verbose)

    monkeypatch.setattr(backtest.model, "tren", spion)

    backtest.kjor_backtest(data, min_treningskamper=20, skriv_ut=False)
    assert len(kalt_med) == 3
    for as_of in kalt_med:
        assert as_of in data["datoer"]


def test_manglende_bet_time_hoppes_over_og_telles(data):
    forste_dato = data["datoer"][20]  # inne i det trenbare vinduet (>= 20 kamper for)
    data["con"].execute(
        "DELETE FROM odds_arkiv WHERE kamp_dato = ? AND snapshot_type = 'bet_time'",
        (forste_dato,),
    )
    data["con"].commit()

    prediksjoner, resultat = backtest.kjor_backtest(data, min_treningskamper=20, skriv_ut=False)
    assert all(rad["kamp_dato"] != forste_dato for rad in prediksjoner)
    assert resultat["kamper_hoppet_over_manglende_odds"] == 1


def test_manglende_closing_gir_none_ikke_hopp(data):
    dato = data["datoer"][20]
    data["con"].execute(
        "DELETE FROM odds_arkiv WHERE kamp_dato = ? AND snapshot_type = 'closing'",
        (dato,),
    )
    data["con"].commit()

    prediksjoner, resultat = backtest.kjor_backtest(data, min_treningskamper=20, skriv_ut=False)
    rader_for_dato = [r for r in prediksjoner if r["kamp_dato"] == dato]
    for rad in rader_for_dato:
        assert rad["odds_closing_hjemme"] is None
        assert rad["odds_closing_borte"] is None
    if rader_for_dato:
        assert resultat["kamper_uten_closing_snapshot"] >= 1


def test_closing_pris_hentes_aldri_for_beslutningen(data, monkeypatch):
    rekkefolge = []

    ekte_vurder_kamp = backtest.vurder_kamp

    def vurder_spion(*args, **kwargs):
        rekkefolge.append("vurder_kamp")
        return ekte_vurder_kamp(*args, **kwargs)

    ekte_hent_closing = odds.hent_closing_pris

    def closing_spion(*args, **kwargs):
        rekkefolge.append("hent_closing_pris")
        return ekte_hent_closing(*args, **kwargs)

    monkeypatch.setattr(backtest, "vurder_kamp", vurder_spion)
    monkeypatch.setattr(backtest.odds, "hent_closing_pris", closing_spion)

    backtest.kjor_backtest(data, min_treningskamper=20, skriv_ut=False)

    for idx, navn in enumerate(rekkefolge):
        if navn == "hent_closing_pris":
            # enhver closing-lookup må komme etter minst én foregående vurder_kamp
            assert "vurder_kamp" in rekkefolge[:idx]


def test_ukjent_lagforkortelse_hoppes_over_og_telles(data):
    df = data["features_df"].copy()
    df.loc[20, "TEAM_ABBREVIATION_BORTE"] = "ZZZ"
    data["features_df"] = df

    prediksjoner, resultat = backtest.kjor_backtest(data, min_treningskamper=20, skriv_ut=False)
    dato = df.loc[20, "GAME_DATE_HJEMME"]
    assert all(rad["kamp_dato"] != dato for rad in prediksjoner)
    assert resultat["kamper_hoppet_over_ukjent_lag"] == 1


def test_skadefilter_blokkerer_bet_naar_enten_lag_er_usikkert(data, monkeypatch):
    def falsk_sjekk(spillerlogg_df, team_id, lagnavn, as_of_dato, antall=3, skriv_ut=False):
        # Blokker Philadelphia 76ers (borte-laget i LAL/PHI-parringen)
        if lagnavn == "Philadelphia 76ers":
            return {"lagnavn": lagnavn, "tilgjengelig": False,
                     "advarsler": ["testspiller mangler"],
                     "antall_toppspillere": 3, "antall_kamprader": 10}
        return {"lagnavn": lagnavn, "tilgjengelig": True, "advarsler": [],
                "antall_toppspillere": 3, "antall_kamprader": 10}

    monkeypatch.setattr(backtest.skadefilter, "sjekk_lag_helse_som_of", falsk_sjekk)

    prediksjoner, resultat = backtest.kjor_backtest(data, min_treningskamper=20, skriv_ut=False)
    assert all(rad["hjemme_lag_id"] != LAG["LAL"][0] or rad["borte_lag_id"] != LAG["PHI"][0]
               for rad in prediksjoner)
    assert resultat["kandidater_blokkert_av_skadefilter"] >= 1


def test_skadefilter_teller_tomt_datagrunnlag(data):
    # spillerlogg_df er allerede tom (fixture) -> antall_toppspillere alltid 0
    prediksjoner, resultat = backtest.kjor_backtest(data, min_treningskamper=20, skriv_ut=False)
    assert resultat["skadesjekk_uten_datagrunnlag"] > 0
    # Vacuous pass: ingen kandidat skal være blokkert siden ingen toppspillere finnes
    assert resultat["kandidater_blokkert_av_skadefilter"] == 0


def test_skadefilter_kan_slaas_av(data, monkeypatch):
    def sprakk(*args, **kwargs):
        raise AssertionError("skadefilteret skal ikke kalles når det er slått av")

    monkeypatch.setattr(backtest.skadefilter, "sjekk_lag_helse_som_of", sprakk)
    _, resultat = backtest.kjor_backtest(data, min_treningskamper=20, bruk_skadefilter=False, skriv_ut=False)
    assert resultat["skadefilter_aktiv"] is False


def test_for_lite_treningsgrunnlag_hoppes_over(data, monkeypatch):
    def sprakk(*args, **kwargs):
        raise AssertionError("model.tren skal aldri kalles når vinduet er for lite")

    monkeypatch.setattr(backtest.model, "tren", sprakk)
    prediksjoner, resultat = backtest.kjor_backtest(
        data, min_treningskamper=10_000, skriv_ut=False
    )
    assert prediksjoner == []
    assert resultat["datoer_behandlet"] == 0


def test_tom_datoliste_gir_tomt_resultat(data):
    data["datoer"] = []
    prediksjoner, resultat = backtest.kjor_backtest(data, skriv_ut=False)
    assert prediksjoner == []
    assert resultat["datoer_totalt"] == 0
    assert resultat["datoer_behandlet"] == 0
    assert resultat["kamper_totalt"] == 0


def test_kjor_backtest_gjor_ingen_fil_io(data, monkeypatch):
    import features

    def sprakk(*args, **kwargs):
        raise AssertionError("ingen fil-I/O skal skje inne i kjor_backtest")

    monkeypatch.setattr(pd, "read_csv", sprakk)
    monkeypatch.setattr(features, "beregn_lag_form", sprakk)
    monkeypatch.setattr(odds, "apne_arkiv", sprakk)

    prediksjoner, resultat = backtest.kjor_backtest(data, min_treningskamper=20, skriv_ut=False)
    assert resultat["datoer_behandlet"] > 0


def test_klargjor_backtestdata_returnerer_alle_delene(features_df, arkiv_con, spillerlogg_df):
    d = backtest.klargjor_backtestdata(
        features_df=features_df, con=arkiv_con, spillerlogg_df=spillerlogg_df
    )
    assert set(["features_df", "datoer", "spillerlogg_df", "con"]).issubset(d.keys())
    assert d["datoer"] == sorted(set(d["datoer"]))
    assert len(d["datoer"]) == len(set(d["datoer"]))
    for dato in d["datoer"]:
        assert dato in set(features_df["GAME_DATE_HJEMME"])


def test_kjor_backtest_reiser_holdoutfeil_for_laste_datoer(data, monkeypatch):
    def sprakk(*args, **kwargs):
        raise AssertionError("model.tren skal aldri kalles når en dato er i holdouten")

    monkeypatch.setattr(backtest.model, "tren", sprakk)

    data["datoer"] = list(data["datoer"]) + [config.HOLDOUT_START_DATO]
    with pytest.raises(backtest.HoldoutLaastFeil):
        backtest.kjor_backtest(data, min_treningskamper=20, skriv_ut=False)


def test_holdoutkjoring_slipper_gjennom_og_filtrerer_selv(data):
    blandet = list(data["datoer"]) + [config.HOLDOUT_START_DATO]
    data["datoer"] = blandet
    prediksjoner, resultat = backtest.kjor_endelig_holdout_backtest(
        data, min_treningskamper=20, skriv_ut=False
    )
    for rad in prediksjoner:
        assert rad["as_of_dato"] >= config.HOLDOUT_START_DATO


def test_bare_holdout_inngangen_apner_vinduet():
    kildetekst = open("backtest.py", encoding="utf-8").read()
    holdout_kilde = inspect.getsource(backtest.kjor_endelig_holdout_backtest)
    rest = kildetekst.replace(holdout_kilde, "")
    rest_uten_kommentarer = "\n".join(
        line for line in rest.splitlines() if not line.strip().startswith("#")
    )
    assert "tillat_holdout=True" not in rest_uten_kommentarer


def test_ingen_bar_except_i_datolokken():
    kildetekst = open("backtest.py", encoding="utf-8").read()
    linjer_uten_kommentarer = [
        line for line in kildetekst.splitlines() if not line.strip().startswith("#")
    ]
    kildetekst_uten_kommentarer = "\n".join(linjer_uten_kommentarer)
    assert "except Exception" not in kildetekst_uten_kommentarer
    assert "except:" not in kildetekst_uten_kommentarer


# --- 3. Røyktest mot ekte arkiv, modell og spillerlogg (plan 05-07 Task 3) ---

_EKTE_FILER = ["nba_features.csv", "odds_arkiv.db", "nba_spillerlogg_raw.csv"]
_EKTE_DATA_TILGJENGELIG = all(os.path.exists(f) for f in _EKTE_FILER)
_HOPP_OVER_GRUNN = (
    "krever ekte nba_features.csv/odds_arkiv.db/nba_spillerlogg_raw.csv "
    "(alle tre er gitignored, fraværende i en fersk klone)"
)


@pytest.mark.skipif(not _EKTE_DATA_TILGJENGELIG, reason=_HOPP_OVER_GRUNN)
def test_prediksjoner_er_uendret_naar_fremtidig_utfall_snus():
    """
    Flipper HJEMME_VANT kun på siste behandlede dato i et kort ekte vindu, og
    sjekker at prediksjonene for den datoen er uendret bortsett fra selve
    hjemme_vant-feltet. model.del_for_trening filtrerer med strengt <, så
    ingen kamp på siste dato kan noensinne havne i noe treningsvindu i dette
    løpet — en uendret prediksjon er derfor den direkte observerbare
    konsekvensen av BT-02, ikke en tilfeldighet ved fixturen.
    """
    d1 = backtest.klargjor_backtestdata(fra="2022-10-24", til="2022-11-30")
    p1, r1 = backtest.kjor_backtest(d1, min_treningskamper=100, skriv_ut=False)

    siste_dato = d1["datoer"][-1]

    d2 = backtest.klargjor_backtestdata(fra="2022-10-24", til="2022-11-30")
    df2 = d2["features_df"].copy()
    maske = df2["GAME_DATE_HJEMME"].astype(str).str[:10] == siste_dato
    df2.loc[maske, "HJEMME_VANT"] = 1 - df2.loc[maske, "HJEMME_VANT"]
    d2["features_df"] = df2

    p2, r2 = backtest.kjor_backtest(d2, min_treningskamper=100, skriv_ut=False)

    rader1 = sorted((r for r in p1 if r["kamp_dato"] == siste_dato), key=lambda r: r["game_id"])
    rader2 = sorted((r for r in p2 if r["kamp_dato"] == siste_dato), key=lambda r: r["game_id"])
    assert len(rader1) == len(rader2)
    for a, b in zip(rader1, rader2):
        for nokkel in a:
            if nokkel == "hjemme_vant":
                continue
            assert a[nokkel] == b[nokkel], nokkel


@pytest.mark.skipif(not _EKTE_DATA_TILGJENGELIG, reason=_HOPP_OVER_GRUNN)
def test_holdout_er_utilgjengelig_fra_tuning_veien():
    d = backtest.klargjor_backtestdata(fra=config.HOLDOUT_START_DATO, til="2024-11-15")
    with pytest.raises(backtest.HoldoutLaastFeil):
        backtest.kjor_backtest(d, skriv_ut=False)

    d2 = backtest.klargjor_backtestdata(fra=config.HOLDOUT_START_DATO, til="2024-11-15")
    backtest.kjor_endelig_holdout_backtest(d2, skriv_ut=False)  # skal ikke reise


@pytest.mark.skipif(not _EKTE_DATA_TILGJENGELIG, reason=_HOPP_OVER_GRUNN)
def test_ekte_arkiv_gir_ingen_manglende_bet_time():
    d = backtest.klargjor_backtestdata(fra="2022-10-24", til="2022-11-30")
    _, resultat = backtest.kjor_backtest(d, min_treningskamper=100, skriv_ut=False)
    assert resultat["kamper_hoppet_over_manglende_odds"] == 0
    assert resultat["kamper_hoppet_over_ukjent_lag"] == 0
