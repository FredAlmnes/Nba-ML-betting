"""
Walk-forward-motoren for Fase 5s historiske backtest.

Denne modulen eier den kronologiske replay-en: den komponerer model.py
(trening/kalibrering), odds.py (arkiv-lesing), skadefilter.py (as-of
helsesjekk) og strategy.py (value/EV-regelen) uten å reimplementere noen
av dem. Importørene er 08_kjor_backtest.py (plan 05-10, CLI-inngangen) og
tests/test_parity.py (plan 05-11, live-vs-backtest-paritetstesten).

Modulen splittes bevisst i to pass: et PREDICT-pass (denne planen,
05-07) som produserer cachede prediksjonsrader, og et SIMULATE-pass
(plan 05-08) som re-staker de cachede radene. Splitten finnes slik at
plan 05-09s Kelly-sweep kan prøve flere stake-strategier på samme
prediksjoner uten å kjøre gjenopptrenings-løkken på nytt for hver av dem
— gjenoppetrening er den dyre delen av et løp, staking er billig.

Ingen nettverkskall skjer ved import av denne modulen, og ingen
modul-nivå I/O gjøres — all fil-/database-lesing skjer inne i
klargjor_backtestdata(), kalt eksplisitt av kalleren.
"""

import pandas as pd

import config
import model
import odds
import skadefilter
import spillerlogg
import teams
from strategy import beregn_value_og_ev, fjern_vigorish


DATO_KOLONNE = "GAME_DATE_HJEMME"    # Samme kolonne model.py/features.py bruker for kronologisk sortering
MAAL_KOLONNE = "HJEMME_VANT"          # Det binære utfallet — vurder_kamp skal ALDRI se denne
MODELL_ETIKETT = "walk-forward"       # Skiller backtestens prediksjonsrader fra en fremtidig live-modell-etikett
MIN_TRENINGSKAMPER = 100              # Varm-opp-gulv — se kjor_backtest sin docstring for begrunnelsen


class HoldoutLaastFeil(Exception):
    """
    Reist når noe forsøker å evaluere en dato i den låste 2024-25-holdouten
    (config.HOLDOUT_START_DATO) utenfor kjor_endelig_holdout_backtest.

    Dette er IKKE en advarsel — løpet skal stoppe. Ingen løkke-nivå
    `except Exception` noe sted i denne modulen skal noensinne fange og
    svelge denne (se banner-kommentaren over datoløkken i kjor_backtest).
    """


def _sikre_ikke_holdout(dato, tillat_holdout=False):
    """
    Kaster HoldoutLaastFeil hvis `dato` >= config.HOLDOUT_START_DATO og
    `tillat_holdout` er falsy.

    ISO-datoer ("YYYY-MM-DD") sorterer leksikografisk riktig, så ingen
    datetime-parsing trengs her — samme resonnement odds.hent_unike_kampdatoer
    allerede dokumenterer for sin fra/til-filtrering. Sammenligningen er >=,
    ikke >, fordi grensedatoen SELV hører til holdouten (D-05-01).

    kjor_endelig_holdout_backtest er den ENESTE funksjonen i denne modulen
    som noensinne har lov til å åpne vinduet ved å sende inn
    tillat_holdout=True.
    """
    if not tillat_holdout and dato >= config.HOLDOUT_START_DATO:
        raise HoldoutLaastFeil(
            f"Dato {dato!r} ligger i den låste holdouten (>= "
            f"config.HOLDOUT_START_DATO={config.HOLDOUT_START_DATO!r}). "
            "Kun kjor_endelig_holdout_backtest har lov til å evaluere denne datoen."
        )


def trenger_retrening(as_of_dato, siste_retrent_maaned):
    """
    Ren predikat: sant når `siste_retrent_maaned` er None (aller første
    behandlede dato) eller når `as_of_dato`s kalendermåned ("YYYY-MM")
    skiller seg fra den.

    Ankeret er måneden til forrige PROSESSERTE dato, aldri en forhåndsberegnet
    liste med kalender-1.-datoer (Pitfall 5, 05-RESEARCH.md): NBA-sesongen
    hopper over den 1. i hver måned, All-Star-pausen og hele sommeren, og
    odds.hent_unike_kampdatoer gir kun datoer som faktisk har kamper. Et anker
    på kalenderen ville trengt et spesialtilfelle for hvert slikt hull; et
    anker på forrige prosesserte måned trenger ingen — en sommerpause fra april
    til oktober utløser nøyaktig ett gjenopptrenings-flagg, ikke fem.
    """
    if siste_retrent_maaned is None:
        return True
    return as_of_dato[:7] != siste_retrent_maaned


def vurder_kamp(modell_prob_hjemme, odds_hjemme, odds_borte,
                 min_value_terskel=config.MIN_VALUE_TERSKEL,
                 min_odds=config.MIN_ODDS,
                 maks_odds=config.MAX_ODDS):
    """
    Den rene beslutningskjernen: modell-sannsynlighet + bet-time-priser inn,
    en liste kandidat-dicter ut (hjemme først, deretter borte — samme
    rekkefølge som verdi_deteksjon.py:172-198 legger til).

    Terskler er PARAMETRE med config-standardverdier, ikke direkte
    config-lesninger, slik at plan 05-09s Kelly-sweep og en fremtidig
    terskel-studie kan overstyre dem per kjøring uten å røre de levende
    verdiene i config.py.

    Denne funksjonen mottar bevisst verken kamputfallet eller prisen fra
    ETTER beslutningsøyeblikket — det er det som gjør BT-02s påstand
    sjekkbar ved å lese femten linjer i stedet for hele løkken.
    """
    modell_prob_borte = 1 - modell_prob_hjemme
    impl_prob_hjemme, impl_prob_borte = fjern_vigorish(odds_hjemme, odds_borte)

    value_hjemme, ev_hjemme = beregn_value_og_ev(modell_prob_hjemme, odds_hjemme, impl_prob_hjemme)
    value_borte, ev_borte = beregn_value_og_ev(modell_prob_borte, odds_borte, impl_prob_borte)

    kandidater = []

    if value_hjemme > min_value_terskel and min_odds <= odds_hjemme <= maks_odds:
        kandidater.append({
            "side": "hjemme",
            "odds": odds_hjemme,
            "modell_prob": modell_prob_hjemme,
            "impl_prob": impl_prob_hjemme,
            "value": value_hjemme,
            "ev": ev_hjemme,
        })

    if value_borte > min_value_terskel and min_odds <= odds_borte <= maks_odds:
        kandidater.append({
            "side": "borte",
            "odds": odds_borte,
            "modell_prob": modell_prob_borte,
            "impl_prob": impl_prob_borte,
            "value": value_borte,
            "ev": ev_borte,
        })

    return kandidater


def _lag_id_og_navn(forkortelse):
    """
    Løser en TEAM_ABBREVIATION_*-verdi gjennom teams.finn_lag() til
    (lag_id, full_name), eller (None, None) hvis navnet er ukjent.

    Alle 30 forkortelser i nba_features.csv løser på et EKSAKT
    LAG_OPPSLAG-treff (verifisert under planlegging) — (None, None)-grenen
    vokter derfor mot en fremtidig regenerert fil, ikke en sti dagens data
    faktisk treffer. Den returnerte full_name-en er det som gjør
    ledger-ens `kamp`-streng identisk i form med live-botens
    f"{hjemme_navn} vs {borte_navn}".
    """
    lag = teams.finn_lag(forkortelse)
    if lag is None:
        return None, None
    return lag["id"], lag["full_name"]
