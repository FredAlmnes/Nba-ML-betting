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

NÅR BACKTEST-MOTOREN BYGGES I FASE 5, MÅ FØLGENDE LEGGES TIL: en test som
kjører backtest-repriseringen og live-veien side om side for én fast
historisk dato og kamp, og asserter at de to veiene produserer nøyaktig
samme bet-beslutning (samme flagg, samme value, samme EV, samme
innsats). Denne testfilen dekker kun halvparten av CORE-04s bokstavelige
krav — den andre halvparten er instruksjonen i dette avsnittet.

Alt i denne filen er deterministisk: ingen tilfeldig tallgenerator, ingen
lesing av systemklokken noe sted. as_of-verdien kommer utelukkende fra
as_of_dato-fixturen i tests/conftest.py, aldri fra klokken — en test som
leser klokken er ikke en determinismetest.
"""

import pandas as pd
import pytest

import config
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
