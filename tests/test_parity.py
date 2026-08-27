"""
CORE-04-tester: determinisme- og leakage-regresjonstest for den delte kjernen.

CORE-04s bokstavelige krav ber om en live-vs-backtest paritetstest som
bekrefter at live-veien og backtest-veien produserer en identisk
beslutning for samme historiske dato/kamp. Ingen backtest-motor finnes
før Fase 5 — det andre kallstedet en slik paritetstest egentlig skulle
sammenlignet mot, eksisterer rett og slett ikke ennå.

Per CONTEXT.md D-12 skaleres derfor dette kravet ned til: en
determinisme- og leakage-regresjonstest på den delte kjernen
(features.py/strategy.py), som beviser at funksjonene er trygge å kalle
identisk fra to ulike kallsteder — uten at det andre kallstedet
(backtesten) trenger å eksistere ennå. Det er nøyaktig den egenskapen
som gjør det trygt å legge til en ny kaller senere uten å endre
funksjonene selv.

OPPFYLT I FASE 5 PLAN 05-11: test_identisk_bet_beslutning_live_og_backtest
lenger ned i denne filen kjører backtest-repriseringen
(backtest.kjor_backtest + backtest.simuler_bets) og live-veien
(verdi_deteksjon.finn_value_bets) side om side for én fast historisk dato
og kamp, og bekrefter at de to veiene produserer nøyaktig samme
bet-beslutning (samme flagg, samme value, samme EV, samme innsats).
Sammenligningen dekker prisvalg (odds.velg_beste_pris_per_utfall),
vig-fjerning, value/EV-beregningen, terskel- og odds-grensene,
bet-streng-formateringen og innsatsen — med modell-objektet holdt
IDENTISK på begge sider med vilje, slik at ingen del av et avvik kan
skjules bak en modell-scoring-forskjell. Den dekker IKKE modelltrening
(det er tests/test_model.py sin jobb) eller feature-engineering (det er
denne filens egne fire determinisme-/leakage-tester rett under sin jobb).
Den kjører bevisst backtest-siden med skadefilteret slått av
(bruk_skadefilter=False), fordi verdi_deteksjon.finn_value_bets —
live-funksjonen under sammenligning — sitter FØR skadefilteret i
live-pipelinen; skadefilteret (skadefilter.filtrer_bets_for_skader)
påføres først av 06_bot.py, etter at finn_value_bets allerede har
returnert.

Alt i denne filen er deterministisk: ingen tilfeldig tallgenerator, ingen
lesing av systemklokken noe sted. as_of-verdien kommer utelukkende fra
as_of_dato-fixturen i tests/conftest.py, aldri fra klokken — en test som
leser klokken er ikke en determinismetest.
"""

import numpy as np
import pandas as pd
import pytest

import backtest
import config
import features
import model
import odds
import teams
import verdi_deteksjon
from features import beregn_lag_form
from strategy import fjern_vigorish, beregn_value_og_ev, beregn_innsats


# ---------------------------------------------------------------------
# features.py — determinisme og leakage-regresjon (CORE-04, skopet som beskrevet over)
# ---------------------------------------------------------------------


def test_beregn_lag_form_er_deterministisk(kamper_df, as_of_dato):
    # To kall med samme input og samme as_of skal gi bit-for-bit identiske
    # rammer — referanse-transparens, egenskapen som gjør det trygt for to
    # ulike kallsteder å dele funksjonen.
    a = beregn_lag_form(kamper_df, as_of=as_of_dato)
    b = beregn_lag_form(kamper_df, as_of=as_of_dato)
    pd.testing.assert_frame_equal(a, b)


def test_fremtidige_rader_endrer_ikke_tidligere_features(
    kamper_df, fremtidige_kamper_df, as_of_dato
):
    # Fase 5s walk-forward-løkke vil sende inn hele fler-sesong-rammen på
    # hver iterasjon. Denne testen bekrefter at det er trygt: å legge til
    # kamper datert på eller etter skjæringsdatoen kan ikke endre noen
    # feature-verdi beregnet FØR skjæringsdatoen.
    before = beregn_lag_form(kamper_df, as_of=as_of_dato)
    after = beregn_lag_form(
        pd.concat([kamper_df, fremtidige_kamper_df], ignore_index=True),
        as_of=as_of_dato,
    )
    pd.testing.assert_frame_equal(before, after)


def test_grenserad_paa_as_of_er_ekskludert(kamper_df, fremtidige_kamper_df, as_of_dato):
    # Raden datert NØYAKTIG på as_of (2024-12-01) skal ikke bidra med noen
    # rad i output — strengt <, ikke <=. En <=-regresjon her ville latt
    # kampen vi prøver å spå lekke inn i sin egen rullende gjennomsnittsverdi.
    full_df = pd.concat([kamper_df, fremtidige_kamper_df], ignore_index=True)
    resultat = beregn_lag_form(full_df, as_of=as_of_dato)
    assert "0022400010" not in resultat["GAME_ID"].values
    # Den strengt fremtidige kampen (2024-12-04) skal naturligvis også
    # være ekskludert, siden den ligger enda lenger unna skjæringsdatoen.
    assert "0022400011" not in resultat["GAME_ID"].values


def test_rekkefolge_i_input_endrer_ikke_output(kamper_df, as_of_dato):
    # Et fremtidig backtest-oppsett vil mate inn rader i en annen
    # rekkefølge enn CSV-en gjør i dag. Funksjonen må ikke være avhengig
    # av innkommende rad-rekkefølge for å produsere samme svar.
    original = beregn_lag_form(kamper_df, as_of=as_of_dato)
    snudd = beregn_lag_form(kamper_df.iloc[::-1], as_of=as_of_dato)

    original_sortert = original.sort_values(["TEAM_ID", "DATO"]).reset_index(drop=True)
    snudd_sortert = snudd.sort_values(["TEAM_ID", "DATO"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(original_sortert, snudd_sortert)


# ---------------------------------------------------------------------
# strategy.py — determinisme (CORE-04, skopet som beskrevet over)
# ---------------------------------------------------------------------


def test_strategy_er_deterministisk():
    # fjern_vigorish, beregn_value_og_ev og beregn_innsats skal hver
    # returnere eksakt like verdier på tvers av to uavhengige kall med
    # identiske argumenter.
    a1 = fjern_vigorish(2.00, 2.00)
    a2 = fjern_vigorish(2.00, 2.00)
    assert a1 == a2

    b1 = beregn_value_og_ev(0.60, 2.00, 0.50)
    b2 = beregn_value_og_ev(0.60, 2.00, 0.50)
    assert b1 == b2

    c1 = beregn_innsats(1000.0, 0.60, 2.00, 0.5, 20.0, 150.0)
    c2 = beregn_innsats(1000.0, 0.60, 2.00, 0.5, 20.0, 150.0)
    assert c1 == c2


# ---------------------------------------------------------------------
# Full simulert bet-beslutning fra to uavhengige kallsteder (CORE-04)
# ---------------------------------------------------------------------


def simuler_bet_beslutning(modell_prob, odds_hjemme, odds_borte, saldo):
    """
    Kjeder vig-fjerning -> value/EV -> terskel-/odds-grense -> innsats,
    nøyaktig den beslutningskjeden 04_value_detector.py og 06_bot.py i
    dag utfører over en prosessgrense, og formen Fase 5s backtest skal
    utføre in-process. Terskler leses fra config her, ikke fra literaler
    gjentatt i testen, slik at en fremtidig terskelendring reflekteres
    automatisk i denne testen i stedet for å pinnes to steder.
    """
    impl_hjemme, _ = fjern_vigorish(odds_hjemme, odds_borte)
    value, ev = beregn_value_og_ev(modell_prob, odds_hjemme, impl_hjemme)

    over_terskel = value > config.MIN_VALUE_TERSKEL
    over_min_odds = odds_hjemme >= config.MIN_ODDS
    under_maks_odds = odds_hjemme <= config.MAX_ODDS
    bet_flagget = over_terskel and over_min_odds and under_maks_odds

    if bet_flagget:
        innsats = beregn_innsats(
            saldo, modell_prob, odds_hjemme,
            config.KELLY_FRAKSJON, config.MIN_INNSATS, config.MAX_INNSATS,
        )
    else:
        innsats = 0.0

    return bet_flagget, value, ev, innsats


def test_identisk_bet_beslutning_fra_to_kallsteder():
    # Tre input-sett: ett klart value-bet, ett under terskelen, og ett
    # over MAX_ODDS til tross for positiv value. To uavhengige kall med
    # identiske argumenter skal returnere identisk (bet_flagget, value,
    # ev, innsats) i alle tre tilfellene.

    # Klart value-bet: vig-fri implisitt 0.50, value +0.10 (over 0.05),
    # odds 2.00 innenfor [1.50, 4.00] -> flagget, innsats 100.0.
    klar = dict(modell_prob=0.60, odds_hjemme=2.00, odds_borte=2.00, saldo=1000.0)
    klar_1 = simuler_bet_beslutning(**klar)
    klar_2 = simuler_bet_beslutning(**klar)
    assert klar_1[0] is True
    assert klar_1[1] == pytest.approx(0.10)
    assert klar_1[2] == pytest.approx(0.20)
    assert klar_1[3] == 100.0
    assert klar_1[0] == klar_2[0]
    assert klar_1[1] == pytest.approx(klar_2[1])
    assert klar_1[2] == pytest.approx(klar_2[2])
    assert klar_1[3] == klar_2[3]

    # Under terskelen: value +0.02, under 0.05 -> ikke flagget.
    under = dict(modell_prob=0.52, odds_hjemme=2.00, odds_borte=2.00, saldo=1000.0)
    under_1 = simuler_bet_beslutning(**under)
    under_2 = simuler_bet_beslutning(**under)
    assert under_1[0] is False
    assert under_1[1] == pytest.approx(0.02)
    assert under_1[3] == 0.0
    assert under_1 == under_2

    # Over MAX_ODDS: value positiv, men odds 5.00 overstiger MAX_ODDS=4.00
    # -> ikke flagget selv om value alene ville tilsagt et bet.
    over_odds = dict(modell_prob=0.40, odds_hjemme=5.00, odds_borte=1.20, saldo=1000.0)
    over_1 = simuler_bet_beslutning(**over_odds)
    over_2 = simuler_bet_beslutning(**over_odds)
    assert over_1[0] is False
    assert over_1[1] > 0
    assert over_1[3] == 0.0
    assert over_1[0] == over_2[0]
    assert over_1[1] == pytest.approx(over_2[1])
    assert over_1[2] == pytest.approx(over_2[2])
    assert over_1[3] == over_2[3]


def test_bet_beslutning_respekterer_odds_grensene():
    # Odds-grensen er en del av den delte beslutningen, ikke et
    # tilfeldig ekstra filter et av kallstedene kunne glemme å bruke.
    bet_flagget, value, _ev, innsats = simuler_bet_beslutning(
        modell_prob=0.40, odds_hjemme=5.00, odds_borte=1.20, saldo=1000.0
    )
    assert value > 0
    assert bet_flagget is False
    assert innsats == 0.0


# ---------------------------------------------------------------------
# Live vs. backtest: samme beslutning for samme historiske kamp (CORE-04)
# ---------------------------------------------------------------------

# Fast fikstur-dato/kamp, løst gjennom teams.finn_lag() (aldri hardkodet
# navn/id direkte) slik at en fremtidig oppslags-endring feiler HER, ikke
# stille i en av testene under.
PARITET_DATO = "2023-01-15"
PARITET_HJEMME = "BOS"
PARITET_BORTE = "MIA"

_HJEMME_LAG = teams.finn_lag(PARITET_HJEMME)
_BORTE_LAG = teams.finn_lag(PARITET_BORTE)
PARITET_HJEMME_NAVN = _HJEMME_LAG["full_name"]
PARITET_BORTE_NAVN = _BORTE_LAG["full_name"]
PARITET_HJEMME_ID = _HJEMME_LAG["id"]
PARITET_BORTE_ID = _BORTE_LAG["id"]

# Batch-tabellens kolonneskjema (HJEMME_RULL_/BORTE_RULL_ for alle ni
# STATS_KOLONNER, DIFF_ kun for de syv DIFF_STATS), avledet fra
# features.py sine egne lister — aldri skrevet ut som en literal-liste,
# slik at denne fila følger batch-skjemaet automatisk om det endres.
FEATURE_KOLONNER = (
    [f"HJEMME_RULL_{s}" for s in features.STATS_KOLONNER]
    + [f"BORTE_RULL_{s}" for s in features.STATS_KOLONNER]
    + [f"DIFF_{s}" for s in features.DIFF_STATS]
)

BOOKMAKERE = ("Bookmaker A", "Bookmaker B", "Bookmaker C")

# Beste hjemme-pris (2.00) kommer fra Bookmaker A, beste borte-pris (1.95)
# fra Bookmaker B — ingen enkelt bookmaker er best på begge sider, slik at
# en "første bookmaker vinner begge sider"-regresjon i live- eller
# arkiv-veien ville feilet her.
PRISER_PARITET = [(2.00, 1.80), (1.90, 1.95), (1.85, 1.85)]
# Closing-priser, bevisst forskjellige fra bet_time-prisene over. CLV er
# IKKE en del av paritetssammenligningen (live-veien har ingen
# CLV-forestilling i det hele tatt) — denne fikstureren finnes kun for å
# bevise at et populert closing-snapshot ikke forstyrrer beslutningen.
PRISER_CLOSING = [(2.05, 1.90), (1.95, 2.00), (1.90, 1.85)]

# Negative kontroller (Task 1): value under terskelen, og value over
# terskelen men odds over MAX_ODDS.
PRISER_UNDER_TERSKEL = [(1.90, 2.10)]
PRISER_OVER_MAKS_ODDS = [(5.00, 1.20)]


class FastModell:
    """
    Stub-modell: predict_proba(X) returnerer en FAST sannsynlighet for
    hver rad i X, uavhengig av X sitt faktiske innhold. Godtar både
    live-veiens én-rads DataFrame og backtest-veiens fler-rads DataFrame.
    Én instans deles bevisst av begge veiene i hver test under, slik at
    en modell-scoring-forskjell aldri kan skjule en beslutningskjede-
    forskjell (se modul-docstringen).
    """

    def __init__(self, prob_hjemme):
        self.prob_hjemme = prob_hjemme

    def predict_proba(self, X):
        p = self.prob_hjemme
        return np.array([[1 - p, p] for _ in range(len(X))])


def _lag_stub_tren(modell, feature_kolonner=None):
    """
    Bygger en stub for model.tren som ALDRI kaller ekte XGBoost — den
    returnerer bare den delte modell-instansen og FEATURE_KOLONNER,
    uavhengig av innkommende features_df/as_of/kalibrer_andel. Dette er
    det som gjør modellobjektet backtest-veien scorer med og
    modellobjektet live-veien scorer med bit-for-bit samme Python-objekt
    (identity), ikke bare like verdier.
    """
    kolonner = list(feature_kolonner) if feature_kolonner is not None else list(FEATURE_KOLONNER)

    def stub(features_df, as_of=None, kalibrer_andel=model.KALIBRER_ANDEL, verbose=False):
        return {"modell": modell, "feature_kolonner": kolonner}

    return stub


def _stub_hent_lagstats(team_id):
    """
    Stub for hent_lagstats-injeksjonen i verdi_deteksjon.finn_value_bets.
    Returnerer faste, lag-spesifikke ni-nøkkel snitt-statistikk-dicts.
    Berører ALDRI nettverket — FastModell ignorerer verdiene uansett, men
    de må være til stede med alle ni STATS_KOLONNER-nøklene slik at
    features.bygg_feature_rad lykkes.
    """
    if team_id == PARITET_HJEMME_ID:
        return {"PTS": 110.0, "FG_PCT": 0.47, "FT_PCT": 0.80, "FG3_PCT": 0.36,
                "REB": 44.0, "AST": 25.0, "TOV": 13.0, "PLUS_MINUS": 3.0, "VANT": 0.6}
    if team_id == PARITET_BORTE_ID:
        return {"PTS": 105.0, "FG_PCT": 0.45, "FT_PCT": 0.78, "FG3_PCT": 0.34,
                "REB": 42.0, "AST": 23.0, "TOV": 14.0, "PLUS_MINUS": -1.0, "VANT": 0.4}
    raise ValueError(f"Ukjent lag-id i paritetsfikstur: {team_id!r}")


def lag_live_kamp(priser):
    """Bygger Odds-API-formatert kamp-dict for den faste fikstur-kampen,
    fra en liste av (hjemme_pris, borte_pris)-par, ett par per bookmaker."""
    bookmakers = []
    for (hjemme_pris, borte_pris), navn in zip(priser, BOOKMAKERE):
        bookmakers.append({
            "title": navn,
            "markets": [{
                "key": "h2h",
                "outcomes": [
                    {"name": PARITET_HJEMME_NAVN, "price": hjemme_pris},
                    {"name": PARITET_BORTE_NAVN, "price": borte_pris},
                ],
            }],
        })
    return {
        "home_team": PARITET_HJEMME_NAVN,
        "away_team": PARITET_BORTE_NAVN,
        "commence_time": f"{PARITET_DATO}T18:00:00Z",
        "bookmakers": bookmakers,
    }


def lag_arkivrader(priser, snapshot_type, event_id="evt-paritet"):
    """Bygger de matchende 15-felts odds_arkiv-radene for samme kamp og
    samme priser som lag_live_kamp — to encoding av ETT prissett."""
    rader = []
    for (hjemme_pris, borte_pris), navn in zip(priser, BOOKMAKERE):
        rader.append((
            "basketball_nba", event_id, PARITET_DATO, PARITET_HJEMME_NAVN, PARITET_BORTE_NAVN,
            PARITET_HJEMME_ID, PARITET_BORTE_ID, f"{PARITET_DATO}T18:00:00Z", snapshot_type,
            f"{PARITET_DATO}T13:00:00Z", navn, "h2h", PARITET_HJEMME_NAVN, hjemme_pris,
            "2026-08-27T10:00:00",
        ))
        rader.append((
            "basketball_nba", event_id, PARITET_DATO, PARITET_HJEMME_NAVN, PARITET_BORTE_NAVN,
            PARITET_HJEMME_ID, PARITET_BORTE_ID, f"{PARITET_DATO}T18:00:00Z", snapshot_type,
            f"{PARITET_DATO}T13:00:00Z", navn, "h2h", PARITET_BORTE_NAVN, borte_pris,
            "2026-08-27T10:00:00",
        ))
    return rader


def _lag_datoer_for(dato, antall):
    """`antall` fortløpende kalenderdager som ender dagen FØR `dato`."""
    slutt = pd.Timestamp(dato) - pd.Timedelta(days=1)
    start = slutt - pd.Timedelta(days=antall - 1)
    return [d.strftime("%Y-%m-%d") for d in pd.date_range(start=start, end=slutt, freq="D")]


def lag_features_df():
    """
    Bygger en feature-tabell med ti rader i de to ukene FØR PARITET_DATO
    (treningsgrunnlag) pluss NØYAKTIG én rad PÅ PARITET_DATO for den faste
    kampen. FEATURE_KOLONNER-verdiene er vilkårlig deterministisk
    aritmetikk avledet av radindeksen — FastModell leser dem aldri, men de
    må være til stede og ikke-null slik at
    trent["modell"].predict_proba(dagens[trent["feature_kolonner"]]) ikke
    feiler på en manglende kolonne. min_treningskamper=1 (satt av kalleren)
    er trygt HER kun fordi model.tren er stubbet — den ekte varm-opp-
    gulven på 100 (backtest.MIN_TRENINGSKAMPER) eksisterer fordi den ekte
    model.tren reiser ValueError på et så lite vindu; denne fikstureren
    sier ingenting om det gulvet. Mål-raden sin HJEMME_VANT settes til 1
    slik at simuler_bets kan gjøre opp betet; oppgjør er nedstrøms for
    innsatsen og kan derfor ikke påvirke den (plan 05-08s
    test_oppgjor_skjer_etter_at_dagens_bets_er_bestemt beviste dette
    allerede, uavhengig).
    """
    rader = []
    for i, dato in enumerate(_lag_datoer_for(PARITET_DATO, 10)):
        rad = {
            "GAME_ID": f"0022400{100 + i}",
            "GAME_DATE_HJEMME": dato,
            "TEAM_ABBREVIATION_HJEMME": PARITET_HJEMME,
            "TEAM_ABBREVIATION_BORTE": PARITET_BORTE,
            "HJEMME_VANT": i % 2,
        }
        for j, kol in enumerate(FEATURE_KOLONNER):
            rad[kol] = float(i + j) * 0.1
        rader.append(rad)

    maalrad = {
        "GAME_ID": "0022400999",
        "GAME_DATE_HJEMME": PARITET_DATO,
        "TEAM_ABBREVIATION_HJEMME": PARITET_HJEMME,
        "TEAM_ABBREVIATION_BORTE": PARITET_BORTE,
        "HJEMME_VANT": 1,
    }
    for j, kol in enumerate(FEATURE_KOLONNER):
        maalrad[kol] = float(100 + j) * 0.1
    rader.append(maalrad)

    return pd.DataFrame(rader)


def kjor_live(modell, kamp):
    """Kjører live-veien: verdi_deteksjon.finn_value_bets med kamper=[kamp]
    injisert (aldri et Odds API-kall) og hent_lagstats=_stub_hent_lagstats
    injisert (aldri et nba_api-kall)."""
    return verdi_deteksjon.finn_value_bets(
        modell, list(FEATURE_KOLONNER), kamper=[kamp], hent_lagstats=_stub_hent_lagstats,
    )


def kjor_backtest_veien(con, min_value_terskel=config.MIN_VALUE_TERSKEL,
                         min_odds=config.MIN_ODDS, maks_odds=config.MAX_ODDS):
    """
    Kjører backtest-veien over nøyaktig PARITET_DATO: klargjor_backtestdata
    (med features_df/con injisert og bruk_skadefilter=False) ->
    kjor_backtest -> simuler_bets. Kalleren må ha monkeypatchet
    backtest.model.tren (via _lag_stub_tren) FØR denne kalles.

    bruk_skadefilter=False fordi verdi_deteksjon.finn_value_bets — live-
    siden av denne sammenligningen — ikke anvender noe skadefilter i det
    hele tatt; det stadiet ligger i skadefilter.filtrer_bets_for_skader og
    påføres først av 06_bot.py, ETTER finn_value_bets. En backtest-side
    kjørt MED skadefilteret ville sammenlignet to ulikt lange pipeliner.
    """
    data = backtest.klargjor_backtestdata(
        features_df=lag_features_df(), con=con, bruk_skadefilter=False,
    )
    prediksjoner, resultat = backtest.kjor_backtest(
        data, datoer=[PARITET_DATO], min_treningskamper=1,
        min_value_terskel=min_value_terskel, min_odds=min_odds, maks_odds=maks_odds,
        bruk_skadefilter=False, skriv_ut=False,
    )
    ledger, resultat_sim = backtest.simuler_bets(prediksjoner, skriv_ut=False)
    return prediksjoner, resultat, ledger, resultat_sim


@pytest.fixture
def con():
    return odds.apne_arkiv(":memory:")


def test_paritetsfikstur_er_utenfor_holdout_og_bruker_samme_modell(monkeypatch):
    # Premiss 1: fikstur-datoen ligger strengt før holdout-grensen, så
    # backtest-siden av sammenligningen aldri kan treffe HoldoutLaastFeil.
    assert PARITET_DATO < config.HOLDOUT_START_DATO

    # Premiss 2: modellobjektet backtest.model.tren-stubben leverer ER det
    # samme Python-objektet som live-veien scorer med (identity, ikke bare
    # like verdier).
    modell = FastModell(0.60)
    stub = _lag_stub_tren(modell)
    levert = stub(pd.DataFrame(), as_of=PARITET_DATO)
    assert levert["modell"] is modell

    # Premiss 3: live-veiens round(modell_sann, 4) på Modell_prob er et
    # bevist no-op ved denne fikstureres sannsynlighet, ikke en uundersøkt
    # forskjell mellom veiene.
    assert round(0.60, 4) == 0.60


def test_beste_pris_er_identisk_live_og_backtest(con):
    kamp = lag_live_kamp(PRISER_PARITET)
    live_hjemme, live_borte, _, _ = odds.velg_beste_pris_per_utfall(
        odds.prisrader_fra_kamp(kamp), PARITET_HJEMME_NAVN, PARITET_BORTE_NAVN,
    )

    odds.arkiver_odds_rader(con, lag_arkivrader(PRISER_PARITET, "bet_time"))
    arkiv_hjemme, arkiv_borte = odds.hent_bet_time_pris(
        con, PARITET_DATO, PARITET_HJEMME_ID, PARITET_BORTE_ID,
    )

    assert (live_hjemme, live_borte) == (2.00, 1.95)
    assert (arkiv_hjemme, arkiv_borte) == (2.00, 1.95)


def test_identisk_bet_beslutning_live_og_backtest(con, monkeypatch):
    # Dette er testen tests/test_parity.py sin egen modul-docstring (Fase 2,
    # plan 02-06) instruerte en Fase 5-leser om å legge til.
    modell = FastModell(0.60)
    monkeypatch.setattr(backtest.model, "tren", _lag_stub_tren(modell))

    kamp = lag_live_kamp(PRISER_PARITET)
    odds.arkiver_odds_rader(con, lag_arkivrader(PRISER_PARITET, "bet_time"))
    odds.arkiver_odds_rader(con, lag_arkivrader(PRISER_CLOSING, "closing"))

    live = kjor_live(modell, kamp)
    _prediksjoner, _resultat, ledger, _resultat_sim = kjor_backtest_veien(con)

    # Strukturelt umulig å bestå på to tomme lister — lengden sjekkes FØR
    # innholdet sammenlignes (T-05-11-01).
    assert len(live) == 1
    assert len(ledger) == 1

    live_bet = live[0]
    ledger_rad = ledger[0]

    assert live_bet["Kamp"] == ledger_rad["kamp"]
    assert live_bet["KampDato"] == ledger_rad["kamp_dato"]
    assert live_bet["Bet"] == ledger_rad["bet"]
    assert ledger_rad["side"] == "hjemme"
    assert live_bet["Odds"] == ledger_rad["odds"]
    assert live_bet["Modell_prob"] == round(ledger_rad["modell_prob"], 4)
    assert live_bet["Value"] == f"{ledger_rad['value']:+.1%}"
    assert live_bet["Forv. EV"] == f"{ledger_rad['ev']:+.1%}"

    innsats_live = beregn_innsats(
        config.STARTKAPITAL, live_bet["Modell_prob"], live_bet["Odds"],
        config.KELLY_FRAKSJON, config.MIN_INNSATS, config.MAX_INNSATS,
    )
    assert innsats_live == ledger_rad["innsats"]
    assert innsats_live == 100.0

    assert ledger_rad["value"] == pytest.approx(0.106329, abs=1e-6)
    assert ledger_rad["ev"] == pytest.approx(0.20)


def test_ingen_av_veiene_flagger_under_terskelen(con, monkeypatch):
    modell = FastModell(0.55)
    monkeypatch.setattr(backtest.model, "tren", _lag_stub_tren(modell))

    kamp = lag_live_kamp(PRISER_UNDER_TERSKEL)
    odds.arkiver_odds_rader(con, lag_arkivrader(PRISER_UNDER_TERSKEL, "bet_time"))

    live = kjor_live(modell, kamp)
    _prediksjoner, _resultat, ledger, _resultat_sim = kjor_backtest_veien(con)

    assert live == []
    assert ledger == []
    # Bekrefter at årsaken er den DELTE terskelregelen, ikke et urelatert
    # hopp lenger nede i løkken.
    assert backtest.vurder_kamp(0.55, 1.90, 2.10) == []


def test_begge_veier_avviser_odds_over_maks(con, monkeypatch):
    modell = FastModell(0.30)
    monkeypatch.setattr(backtest.model, "tren", _lag_stub_tren(modell))

    kamp = lag_live_kamp(PRISER_OVER_MAKS_ODDS)
    odds.arkiver_odds_rader(con, lag_arkivrader(PRISER_OVER_MAKS_ODDS, "bet_time"))

    live = kjor_live(modell, kamp)
    _prediksjoner, _resultat, ledger, _resultat_sim = kjor_backtest_veien(con)

    assert live == []
    assert ledger == []
