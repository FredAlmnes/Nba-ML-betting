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

import hashlib
import json
import os
import re
from datetime import datetime

import pandas as pd

import config
import model
import odds
import skadefilter
import spillerlogg
import teams
from strategy import beregn_value_og_ev, fjern_vigorish, beregn_innsats, er_duplikat, finn_bet_nokkel
# metrics.py importerer kun numpy og strategy.fjern_vigorish, så denne
# importen åpner ingen sirkel tilbake til backtest.py.
from metrics import beregn_clv, beregn_profitt, oppsummer_ledger

# datetime.now() leses KUN ett sted i denne modulen — bygg_run_id sin
# standardverdi-håndtering. Hver test injiserer et fast tidspunkt i stedet,
# slik at modulen forblir deterministisk under test.


DATO_KOLONNE = "GAME_DATE_HJEMME"    # Samme kolonne model.py/features.py bruker for kronologisk sortering
MAAL_KOLONNE = "HJEMME_VANT"          # Det binære utfallet — vurder_kamp skal ALDRI se denne
MODELL_ETIKETT = "walk-forward"       # Skiller backtestens prediksjonsrader fra en fremtidig live-modell-etikett
MIN_TRENINGSKAMPER = 100              # Varm-opp-gulv — se kjor_backtest sin docstring for begrunnelsen


class HoldoutLaastFeil(Exception):
    """
    Reist når noe forsøker å evaluere en dato i den låste 2024-25-holdouten
    (config.HOLDOUT_START_DATO) utenfor kjor_endelig_holdout_backtest.

    Dette er IKKE en advarsel — løpet skal stoppe. Ingen bred unntaksfanger
    på løkke-nivå noe sted i denne modulen skal noensinne fange og svelge
    denne (se banner-kommentaren over datoløkken i kjor_backtest).
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
    som noensinne har lov til å åpne vinduet ved å sette allow-flagget sant.
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


# ---------------------------------------------------------------------------
# 2. Walk-forward-løkken og de to inngangspunktene (plan 05-07 Task 2)
# ---------------------------------------------------------------------------


def klargjor_backtestdata(features_fil="nba_features.csv", arkiv_fil="odds_arkiv.db",
                            fra=None, til=None, bruk_skadefilter=True,
                            features_df=None, spillerlogg_df=None, con=None):
    """
    Gjør ALL fil- og database-I/O for et løp, nøyaktig én gang, og returnerer
    en dict med `features_df`, `datoer`, `spillerlogg_df` (None når
    skadefilteret er slått av) og `con`.

    Grunnen til at dette kan gjøres én gang og filtreres mange ganger
    (Pattern 1, 05-RESEARCH.md): et lags rullende features avhenger
    utelukkende av det samme lagets EGNE tidligere kamper, så å legge til
    senere kamper i tabellen kan aldri endre en tidligere rad. Derfor kan
    hele tabellen bygges én gang, og hvert gjenopptreningspunkt i løkken
    under er bare en boolsk maske over denne ene rammen — aldri en ny
    filbygging.

    `features_df`/`spillerlogg_df`/`con` kan injiseres av kalleren (typisk
    en test) — dette er hele grunnen til at kjor_backtest sine tester kan
    kjøre helt uten nettverk eller den ekte, gitignorede filen/arkivet.
    Når `features_df` er injisert, utledes `datoer` fra dens egen
    dato-kolonne (sortert, deduplisert, fra/til-filtrert) i stedet for via
    odds.hent_unike_kampdatoer, siden den funksjonen selv leser fra disk.
    """
    if features_df is None:
        features_df = pd.read_csv(features_fil)
        datoer = odds.hent_unike_kampdatoer(features_fil, fra=fra, til=til)
    else:
        datoer_serie = features_df[DATO_KOLONNE].astype(str).str[:10]
        unike = sorted(set(datoer_serie))
        if fra is not None:
            unike = [d for d in unike if d >= fra]
        if til is not None:
            unike = [d for d in unike if d <= til]
        datoer = unike

    features_df = features_df.copy()
    features_df[DATO_KOLONNE] = features_df[DATO_KOLONNE].astype(str).str[:10]

    if con is None:
        con = odds.apne_arkiv(arkiv_fil)

    if bruk_skadefilter and spillerlogg_df is None:
        spillerlogg_df = spillerlogg.les_spillerlogg()

    return {
        "features_df": features_df,
        "datoer": datoer,
        "spillerlogg_df": spillerlogg_df,
        "con": con,
    }


def kjor_backtest(data, datoer=None, tillat_holdout=False,
                    min_value_terskel=config.MIN_VALUE_TERSKEL,
                    min_odds=config.MIN_ODDS,
                    maks_odds=config.MAX_ODDS,
                    min_treningskamper=MIN_TRENINGSKAMPER,
                    kalibrer_andel=model.KALIBRER_ANDEL,
                    bruk_skadefilter=True,
                    skriv_ut=True):
    """
    PREDICT-passet: løper kronologisk gjennom `datoer`, gjenoppretrener
    modellen én gang per kalendermåned av PROSESSERTE datoer, scorer hver
    dato mot en feature-tabell bygget nøyaktig én gang (av
    klargjor_backtestdata), og returnerer (prediksjoner, resultat) — samme
    (df, resultat)-konvensjon som spillerlogg.hent_spillerlogg (plan 05-05).

    `tillat_holdout` er IKKE ment å settes av vanlige kallere.
    kjor_endelig_holdout_backtest er den eneste funksjonen som noensinne
    setter tillat_holdout sann.

    Kaster HoldoutLaastFeil hvis en dato i `datoer` ligger i den låste
    2024-25-holdouten og tillat_holdout er falsk. Sjekken gjøres to steder
    med hensikt: FØRST som et pre-flight-pass over hele datolisten før noe
    annet arbeid skjer, slik at en feilaktig holdout-forespørsel feiler på
    millisekunder i stedet for etter et dusin modell-fits (05-RESEARCH.md
    Pattern 4 målte per-dato-sjekken som umålbart billig); DERETTER på nytt
    øverst i hver løkke-iterasjon, som er invarianten som overlever en
    fremtidig refaktorering av hvordan `datoer` produseres.
    """
    if datoer is None:
        datoer = data["datoer"]

    for dato in datoer:
        _sikre_ikke_holdout(dato, tillat_holdout)

    resultat = {
        "fra_dato": datoer[0] if datoer else None,
        "til_dato": datoer[-1] if datoer else None,
        "datoer_totalt": len(datoer),
        "datoer_behandlet": 0,
        "datoer_hoppet_over_for_lite_treningsgrunnlag": 0,
        "kamper_totalt": 0,
        "kamper_hoppet_over_manglende_odds": 0,
        "kamper_hoppet_over_ukjent_lag": 0,
        "kamper_uten_closing_snapshot": 0,
        "kandidater_flagget": 0,
        "kandidater_blokkert_av_skadefilter": 0,
        "skadesjekk_uten_datagrunnlag": 0,
        "retreninger": 0,
        "prediksjoner": 0,
        "min_treningskamper": min_treningskamper,
        "kalibrer_andel": kalibrer_andel,
        "min_value_terskel": min_value_terskel,
        "min_odds": min_odds,
        "maks_odds": maks_odds,
        "skadefilter_aktiv": bruk_skadefilter,
    }

    features_df = data["features_df"]
    con = data["con"]
    spillerlogg_df = data.get("spillerlogg_df")

    prediksjoner = []
    trent = None
    siste_retrent_maaned = None
    retrent_dato = None
    helse_cache = {}

    for dato in datoer:
        _sikre_ikke_holdout(dato, tillat_holdout)

        # Varm-opp-gulv: dette er IKKE D-05-02s burn-in-rapporteringspolicy
        # (som beholder alle PROSESSERTE måneder i ledgeren) — det er en
        # separat, hardere begrensning fra model.tren selv. Arkivets aller
        # første dato er 2022-10-24, der det strengt-tidligere vinduet har
        # null rader, og model.tren reiser ValueError på et slikt vindu.
        # 100 er valgt som det minste runde vinduet som lar den 15%-store
        # kalibreringsbolken beholde minst 15 rader; det koster 15 av 318
        # datoer og 111 av 2413 kamper i tren/kalibrer-bolken, alt innenfor
        # oktober og tidlig november 2022.
        antall_tidligere = int((features_df[DATO_KOLONNE] < dato).sum())
        if antall_tidligere < min_treningskamper:
            resultat["datoer_hoppet_over_for_lite_treningsgrunnlag"] += 1
            continue

        if trenger_retrening(dato, siste_retrent_maaned):
            trent = model.tren(
                features_df, as_of=dato, kalibrer_andel=kalibrer_andel, verbose=False
            )
            siste_retrent_maaned = dato[:7]
            retrent_dato = dato
            resultat["retreninger"] += 1

        resultat["datoer_behandlet"] += 1

        dagens = features_df[features_df[DATO_KOLONNE] == dato]
        if dagens.empty:
            continue

        X = dagens[trent["feature_kolonner"]]
        sannsynligheter = trent["modell"].predict_proba(X)[:, 1]

        for (_, rad), modell_prob_hjemme in zip(dagens.iterrows(), sannsynligheter):
            resultat["kamper_totalt"] += 1

            hjemme_lag_id, hjemme_navn = _lag_id_og_navn(rad["TEAM_ABBREVIATION_HJEMME"])
            borte_lag_id, borte_navn = _lag_id_og_navn(rad["TEAM_ABBREVIATION_BORTE"])
            if hjemme_lag_id is None or borte_lag_id is None:
                resultat["kamper_hoppet_over_ukjent_lag"] += 1
                continue

            odds_hjemme, odds_borte = odds.hent_bet_time_pris(
                con, dato, hjemme_lag_id, borte_lag_id
            )
            if odds_hjemme is None or odds_borte is None:
                resultat["kamper_hoppet_over_manglende_odds"] += 1
                continue

            kandidater = vurder_kamp(
                modell_prob_hjemme, odds_hjemme, odds_borte,
                min_value_terskel=min_value_terskel, min_odds=min_odds, maks_odds=maks_odds,
            )
            resultat["kandidater_flagget"] += len(kandidater)

            if not kandidater:
                continue

            if bruk_skadefilter:
                overlevende = []
                for kandidat in kandidater:
                    blokkert = False
                    for lag_id, lagnavn in ((hjemme_lag_id, hjemme_navn), (borte_lag_id, borte_navn)):
                        cache_nokkel = (dato, lag_id)
                        if cache_nokkel not in helse_cache:
                            helse_cache[cache_nokkel] = skadefilter.sjekk_lag_helse_som_of(
                                spillerlogg_df, lag_id, lagnavn, dato
                            )
                            if helse_cache[cache_nokkel]["antall_toppspillere"] == 0:
                                resultat["skadesjekk_uten_datagrunnlag"] += 1
                        if not helse_cache[cache_nokkel]["tilgjengelig"]:
                            blokkert = True
                    if blokkert:
                        resultat["kandidater_blokkert_av_skadefilter"] += 1
                    else:
                        overlevende.append(kandidat)
                kandidater = overlevende

            if not kandidater:
                continue

            closing_hjemme, closing_borte = odds.hent_closing_pris(
                con, dato, hjemme_lag_id, borte_lag_id
            )
            if closing_hjemme is None or closing_borte is None:
                resultat["kamper_uten_closing_snapshot"] += 1

            for kandidat in kandidater:
                if kandidat["side"] == "hjemme":
                    bet = f"Hjemme ({hjemme_navn})"
                else:
                    bet = f"Borte ({borte_navn})"

                prediksjoner.append({
                    "as_of_dato": dato,
                    "kamp_dato": dato,
                    "game_id": rad["GAME_ID"],
                    "kamp": f"{hjemme_navn} vs {borte_navn}",
                    "side": kandidat["side"],
                    "bet": bet,
                    "hjemme_lag_id": hjemme_lag_id,
                    "borte_lag_id": borte_lag_id,
                    "modell": MODELL_ETIKETT,
                    "retrent_dato": retrent_dato,
                    "modell_prob": kandidat["modell_prob"],
                    "modell_prob_hjemme": modell_prob_hjemme,
                    "odds": kandidat["odds"],
                    "impl_prob": kandidat["impl_prob"],
                    "value": kandidat["value"],
                    "ev": kandidat["ev"],
                    "odds_bet_time_hjemme": odds_hjemme,
                    "odds_bet_time_borte": odds_borte,
                    "odds_closing_hjemme": closing_hjemme,
                    "odds_closing_borte": closing_borte,
                    # hjemme_vant festes FØRST etter at vurder_kamp har returnert —
                    # ingen kode i denne modulen leser den, den bæres kun videre
                    # slik at plan 05-08 kan gjøre opp betten etter at beslutningen
                    # allerede er tatt og lagret.
                    "hjemme_vant": rad[MAAL_KOLONNE],
                })

    resultat["prediksjoner"] = len(prediksjoner)

    if skriv_ut:
        print("=" * 60)
        print("WALK-FORWARD PREDIKSJONSPASS")
        for nokkel, verdi in resultat.items():
            print(f"{nokkel}: {verdi}")
        print("=" * 60)

    return prediksjoner, resultat


def kjor_endelig_holdout_backtest(data, **kwargs):
    """
    Den ENESTE funksjonen som har lov til å åpne holdout-vinduet.

    Filtrerer `data["datoer"]` ned til datoer på eller etter
    config.HOLDOUT_START_DATO SELV, i stedet for å stole på kalleren — en
    fremtidig utilsiktet full-historikk-liste sendt inn her evaluerer
    likevel bare holdouten. To symmetriske egenskaper holder: tuning-kode
    kan aldri nå en holdout-dato (via kjor_backtest sin pre-flight-vakt),
    og denne funksjonen kan aldri nå en tuning-dato (via filtreringen her).

    ADVARSEL (plan 05-13): å kalle denne bruker opp holdouten. Resultatet
    er kun meningsfullt når hver terskel- og Kelly-beslutning allerede er
    frosset på tren/kalibrer-bolken, og kjøre-id-en må registreres i
    STATE.md etterpå.
    """
    holdout_datoer = [d for d in data["datoer"] if d >= config.HOLDOUT_START_DATO]
    if not holdout_datoer:
        raise ValueError(
            "Ingen datoer på eller etter config.HOLDOUT_START_DATO "
            f"({config.HOLDOUT_START_DATO!r}) funnet i data['datoer']"
        )

    return kjor_backtest(data, datoer=holdout_datoer, tillat_holdout=True, **kwargs)


# ---------------------------------------------------------------------------
# 4. Simuleringspass: innsats, ledger og oppgjør (plan 05-08 Task 1)
# ---------------------------------------------------------------------------


FLAT_INNSATS_ANDEL = 0.02   # D-05-03: 2% av config.STARTKAPITAL = 20.00 kr, sammenfaller med config.MIN_INNSATS

# De første tolv feltene er 06_bot.py:278-291s levende bet-dict, i SAMME
# rekkefølge, slik at et menneske kan diffe ledger.csv mot botens egen
# bet-historikk-fil kolonne for kolonne. `clv` er BT-06s per-bet-felt. De
# siste seks er rene backtest-provenance-/revisjonsfelt uten noe levende
# motstykke.
#
# To bevisste avvik fra den levende dict-en, nedtegnet her fordi begge
# ellers ville lest som bugs: `value` og `ev` er rå floats her, mens
# verdi_deteksjon.py:188/:202 formaterer dem som prosent-strenger for den
# levende CSV-overleveringen (ledgeren konsumeres av metrics.py, ikke av
# noen visningsflate). `modell` bærer den levende visningsstrengen
# f"{modell_prob:.1%}", mens prediksjonsradens EGET `modell`-felt
# (MODELL_ETIKETT) flyttes til `modell_etikett` — å gjenbruke navnet
# `modell` til to ulike ting på tvers av de to filene ville vært verre
# enn én ekstra kolonne.
LEDGER_KOLONNER = [
    "dato", "kamp_dato", "kamp", "bet", "odds", "innsats", "modell",
    "modell_prob", "value", "ev", "status", "gevinst",
    "clv", "game_id", "side", "retrent_dato", "modell_etikett",
    "saldo_for", "saldo_etter_dato",
]


def flat_innsats_belop(startkapital):
    """
    D-05-03s flate stake: `round(startkapital * FLAT_INNSATS_ANDEL, 2)`.

    Eksisterer som en navngitt funksjon utelukkende slik at plan 05-09s
    Kelly-sweep har ett sted å hente det flate beløpet fra, og slik at
    D-05-03s formel er grep-bar. `kelly_fraksjon` satt til null er IKKE en
    flat stake — strategy.beregn_innsats returnerer 0.0 for hvert bet ved
    den fraksjonen (05-RESEARCH.md Pitfall 6) — og det er derfor den flate
    armen er en `backtest.py`-lokal gren i stedet for en strategy.py-parameter.
    """
    return round(startkapital * FLAT_INNSATS_ANDEL, 2)


def bet_vant(side, hjemme_vant):
    """
    Sant når `side` er "hjemme" og hjemmelaget vant, eller `side` er
    "borte" og hjemmelaget IKKE vant. Kaster ValueError på en ukjent side
    i stedet for å stille anta et fortegn — en skrivefeil ville ellers
    gjort opp hvert eneste bet som et tap og stille halvert den rapporterte
    ROI-en.
    """
    if side == "hjemme":
        return bool(hjemme_vant)
    if side == "borte":
        return not bool(hjemme_vant)
    raise ValueError(f"Ukjent side {side!r} — forventet 'hjemme' eller 'borte'")


def beregn_innsats_for_kandidat(prediksjon, saldo, kelly_fraksjon, min_innsats,
                                  maks_innsats, flat_innsats=None):
    """
    Beregner innsatsen for én kandidat, uten å lese noe som først finnes
    ETTER at beslutningen er tatt: verken kampens utfall eller en senere
    markedspris. Dette er med hensikt den smaleste flaten der en slik
    senere verdi kunne lekket inn i en stake, så kildekoden kan sjekkes fri
    for de forbudte tokenene i femten linjer i stedet for hele
    simuleringsløkken.

    Returnerer `flat_innsats` uendret når den er satt (D-05-03s flate arm);
    ellers `beregn_innsats(saldo, prediksjon["modell_prob"], prediksjon["odds"],
    kelly_fraksjon, min_innsats, maks_innsats)`. Leser bevisst kun
    `modell_prob` og `odds` fra prediksjonsraden.
    """
    if flat_innsats is not None:
        return flat_innsats
    return beregn_innsats(
        saldo, prediksjon["modell_prob"], prediksjon["odds"],
        kelly_fraksjon, min_innsats, maks_innsats,
    )


def simuler_bets(prediksjoner, startkapital=config.STARTKAPITAL,
                   kelly_fraksjon=config.KELLY_FRAKSJON,
                   min_innsats=config.MIN_INNSATS,
                   maks_innsats=config.MAX_INNSATS,
                   flat_innsats=None,
                   skriv_ut=False):
    """
    SIMULATE-passet: re-staker cachede prediksjonsrader fra kjor_backtest
    gjennom halvt Kelly (eller D-05-03s flate gren), gjør opp hver dato sin
    bet-batch, fester CLV, og returnerer (ledger, resultat_sim) — samme
    (rader, resultat)-konvensjon som kjor_backtest.

    Sorteringen (kamp_dato, str(game_id), side) er defensiv, ikke
    korrigerende: kjor_backtest leverer allerede rader i datorekkefølge,
    men simuler_bets kalles også direkte av plan 05-09s sweep og av tester,
    og en bankroll-kurve som avhenger av inndata-rekkefølge ville gjort ROI
    ikke-reproduserbar — noe BT-05 forbyr.

    Oppgjør skjer BATCHET per simulerte dato, aldri per bet, fordi det er
    hva 06_bot.py faktisk gjør: sjekk_resultater kjører ved starten av NESTE
    daglige kjøring, ETTER at forrige dags bets allerede er plassert. Et bet
    plassert i dag kan derfor aldri finansieres av gevinsten fra en kamp
    spilt i dag. Å gjøre opp bet for bet i stedet ville lekket utfallet av
    dagens første kamp inn i innsatsen på dagens andre — et BT-02-brudd som
    ikke reiser noen feil og bare blåser opp ROI stille.

    CLV festes under oppgjøret, ikke ved rad-konstruksjon, av samme grunn:
    closing-prisen er data fra ETTER beslutningen, og å lese den i
    stake-stien er den andre veien denne planen kunne brutt BT-02 stille.

    `resultat_sim` sine nøkler dekker hver stake-knapp som endrer tallene
    (startkapital, kelly_fraksjon, flat_innsats, min_innsats, maks_innsats),
    slik at Task 2 kan kopiere dem rett inn i manifest.json uten at noe
    forblir implisitt.
    """
    rader_sortert = sorted(
        prediksjoner,
        key=lambda p: (p["kamp_dato"], str(p["game_id"]), p["side"]),
    )

    resultat_sim = {
        "startkapital": startkapital,
        "kelly_fraksjon": kelly_fraksjon,
        "flat_innsats": flat_innsats,
        "min_innsats": min_innsats,
        "maks_innsats": maks_innsats,
        "kandidater_totalt": len(prediksjoner),
        "bets_plassert": 0,
        "kandidater_uten_kelly_edge": 0,
        "bets_hoppet_over_duplikat": 0,
        "bets_uten_utfall": 0,
        "datoer_stoppet_lav_bankroll": 0,
        "bets_uten_clv": 0,
        "sluttsaldo": startkapital,
    }

    grupper = {}
    rekkefolge_datoer = []
    for p in rader_sortert:
        d = p["kamp_dato"]
        if d not in grupper:
            grupper[d] = []
            rekkefolge_datoer.append(d)
        grupper[d].append(p)

    ledger = []
    saldo = startkapital
    brukte_nokler = set()

    for dato in rekkefolge_datoer:
        dagens_rader = []   # liste av (rad, prediksjon)-par for denne datoen

        for p in grupper[dato]:
            # 1) Dedup FØRST — hindrer dobbel-betting på samme fysiske kamp.
            #    vurder_kamp kan aldri flagge begge sider av én kamp (plan
            #    05-07 beviste dette som en invariant), så denne vakten er
            #    parity med 06_bot.py:248-256, ikke en sti dagens data
            #    faktisk treffer.
            nokkel = finn_bet_nokkel(p["kamp"], p["bet"], p["kamp_dato"])
            if er_duplikat(nokkel, brukte_nokler):
                resultat_sim["bets_hoppet_over_duplikat"] += 1
                continue

            # 2) Uavgjorte kamper (fremdeles ukjent utfall) kan aldri telles
            #    som et tap — hopp over og tell separat.
            if pd.isna(p["hjemme_vant"]):
                resultat_sim["bets_uten_utfall"] += 1
                continue

            innsats = beregn_innsats_for_kandidat(
                p, saldo, kelly_fraksjon, min_innsats, maks_innsats, flat_innsats
            )
            if innsats == 0.0 and flat_innsats is None:
                resultat_sim["kandidater_uten_kelly_edge"] += 1
                continue

            if saldo - innsats < min_innsats * 2:
                # Stopper DENNE DATOEN, aldri hele løpet: 06_bot.py sin break
                # avslutter kun dagens plassering, og neste dag starter friskt.
                # Å avslutte hele backtesten her ville stille avkuttet ledgeren.
                resultat_sim["datoer_stoppet_lav_bankroll"] += 1
                break

            brukte_nokler.add(nokkel)

            saldo_for = saldo
            saldo -= innsats

            # Raden er komplett og uforanderlig som en BESLUTNING på dette
            # punktet — alt som legges til etterpå er oppgjørs-bokføring
            # etter beslutningen.
            rad = {
                "dato": p["as_of_dato"],
                "kamp_dato": p["kamp_dato"],
                "kamp": p["kamp"],
                "bet": p["bet"],
                "odds": p["odds"],
                "innsats": innsats,
                "modell": f"{p['modell_prob']:.1%}",
                "modell_prob": p["modell_prob"],
                "value": p["value"],
                "ev": p["ev"],
                "status": "venter",
                "gevinst": None,
                "clv": None,
                "game_id": p["game_id"],
                "side": p["side"],
                "retrent_dato": p["retrent_dato"],
                "modell_etikett": p["modell"],
                "saldo_for": saldo_for,
                "saldo_etter_dato": None,
            }
            ledger.append(rad)
            dagens_rader.append((rad, p))
            resultat_sim["bets_plassert"] += 1

        # Oppgjør skjer FØRST etter at hele dagens kandidatløkke er ferdig.
        for rad, p in dagens_rader:
            vant = bet_vant(p["side"], p["hjemme_vant"])
            rad["status"] = "vant" if vant else "tapte"
            rad["gevinst"] = beregn_profitt(rad["innsats"], rad["odds"], vant)
            if vant:
                # Innsatsen ble allerede trukket, så en vunnet bet legger
                # tilbake innsats pluss profitt.
                saldo += rad["innsats"] + rad["gevinst"]

            rad["clv"] = beregn_clv(
                p["odds_bet_time_hjemme"], p["odds_bet_time_borte"],
                p["odds_closing_hjemme"], p["odds_closing_borte"], p["side"],
            )
            if rad["clv"] is None:
                resultat_sim["bets_uten_clv"] += 1

        for rad, _ in dagens_rader:
            rad["saldo_etter_dato"] = saldo

    resultat_sim["sluttsaldo"] = saldo

    if skriv_ut:
        print("=" * 60)
        print("SIMULERINGSPASS")
        for nokkel, verdi in resultat_sim.items():
            print(f"{nokkel}: {verdi}")
        print("=" * 60)

    return ledger, resultat_sim


# ---------------------------------------------------------------------------
# 5. Kjøre-id, manifest og persistering (plan 05-08 Task 2)
# ---------------------------------------------------------------------------


BACKTEST_KATALOG = "backtests"          # Alt kjøre-output havner her, strukturelt adskilt fra botens egne tilstandsfiler
MANIFEST_FIL = "manifest.json"
LEDGER_FIL = "ledger.csv"
RETRENINGS_KADENS = "maanedlig"         # Speiler trenger_retrening sin faktiske kadens — nedtegnet eksplisitt i manifestet
INNBRENNING_MANEDER = 3                 # D-05-02: antall PROSESSERTE måneder ex-burn-in-settet dropper
BOOTSTRAP_SEED = 42                     # Matcher metrics.oppsummer_ledger sin egen standardverdi, restatt her med hensikt
BOOTSTRAP_N_RESAMPLES = 1000
RUN_ID_MONSTER = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{8}$")


def bygg_konfig_snapshot(resultat_predict, resultat_sim):
    """
    Bygger den flate konfig-dict-en manifestet lagrer — de femten
    strategi-/rapporterings-skalarene et fremtidig before/after-oppgjør
    trenger.

    Hver verdi leses fra de to teller-dict-ene løpet FAKTISK produserte,
    ALDRI fra config-modulen direkte, med unntak av `retrenings_kadens`
    (konstanten over), `holdout_start_dato` (lest fra config, siden den
    aldri overstyres per løp) og de to bootstrap-verdiene (denne modulens
    konstanter). Grunnen: tersklene kan overstyres per løp for plan 05-09s
    sweep, så å lese config her ville registrert modul-standarden mens
    løpet faktisk brukte noe annet — et manifest som lyver om sine egne
    input er verre enn intet manifest, og BT-05s "before/after-sammenligning
    mot dagens tapende live-konfigurasjon" avhenger helt av at denne
    dict-en er sann.
    """
    return {
        "min_value_terskel": resultat_predict["min_value_terskel"],
        "min_odds": resultat_predict["min_odds"],
        "maks_odds": resultat_predict["maks_odds"],
        "kelly_fraksjon": resultat_sim["kelly_fraksjon"],
        "flat_innsats": resultat_sim["flat_innsats"],
        "startkapital": resultat_sim["startkapital"],
        "min_innsats": resultat_sim["min_innsats"],
        "maks_innsats": resultat_sim["maks_innsats"],
        "min_treningskamper": resultat_predict["min_treningskamper"],
        "kalibrer_andel": resultat_predict["kalibrer_andel"],
        "retrenings_kadens": RETRENINGS_KADENS,
        "holdout_start_dato": config.HOLDOUT_START_DATO,
        "skadefilter_aktiv": resultat_predict["skadefilter_aktiv"],
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_n_resamples": BOOTSTRAP_N_RESAMPLES,
    }


def bygg_run_id(konfig, tidspunkt=None):
    """
    Bygger id-en som `strftime("%Y%m%d-%H%M%S")` av `tidspunkt`
    (standard `datetime.now()`), en bindestrek, og de første åtte
    heksadesimale tegnene av SHA-256 av
    `json.dumps(konfig, sort_keys=True, ensure_ascii=False)` kodet UTF-8.

    `sort_keys=True` er det som gjør at hashen avhenger av konfigens
    VERDIER, ikke av Pythons dict-innsettingsrekkefølge. Tidsstempel-
    prefikset gjør at kjøringer sorterer kronologisk i en katalogliste, og
    hash-suffikset holder to identisk-konfigurerte gjenkjøringer
    distinkte — begge kravene kommer rett fra 05-CONTEXT.md.

    Hashen er en endrings-detektor, ikke en sikkerhetskontroll: åtte
    heksadesimale tegn er for menneskelig diffing, og ingenting i dette
    prosjektet avhenger av at den er kollisjonssikker.
    """
    if tidspunkt is None:
        tidspunkt = datetime.now()
    tidsdel = tidspunkt.strftime("%Y%m%d-%H%M%S")
    digest = hashlib.sha256(
        json.dumps(konfig, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:8]
    return f"{tidsdel}-{digest}"


def _valider_run_id(run_id):
    """
    Kaster ValueError med mindre `run_id` matcher `RUN_ID_MONSTER` fullt ut.

    Dette er en sti-sikkerhetskontroll, ikke kosmetikk: `run_id` blir et
    katalognavn, og mønsteret tillater kun sifre, bindestreker og små
    heksadesimale bokstaver, så ingen verdi som består kan inneholde en
    stiseparator, en foreldre-referanse, et innledende punktum eller en
    null-byte. `bygg_run_id` kan kun produsere gyldige id-er, så denne
    vakten finnes for tilfellet der en fremtidig kaller — plan 05-10s CLI,
    mest sannsynlig — sender en inn utenfra.
    """
    if not isinstance(run_id, str) or not RUN_ID_MONSTER.fullmatch(run_id):
        raise ValueError(f"Ugyldig run_id: {run_id!r}")


def filtrer_ledger_etter_innbrenning(ledger, maaneder):
    """
    Samler det sorterte settet av distinkte `kamp_dato[:7]`-verdier som
    FINNES i ledgeren, dropper rader hvis måned er blant de første
    `maaneder` av dem, og returnerer resten.

    Vinduet er definert over måneder TIL STEDE i ledgeren, ikke over
    kalendermåneder siden startdatoen, av samme grunn plan 05-07 forankrer
    gjenoppretrening på forrige prosesserte måned: NBA-sesongen har en
    All-Star-pause og en fire måneder lang sommer, så kalenderaritmetikk
    ville stille droppet ulik mengde data avhengig av hvor et løps
    datoområde tilfeldigvis starter.

    Returnerer ledgeren uendret når `maaneder` er null eller falsy.
    """
    if not maaneder:
        return list(ledger)
    maneder_i_ledger = sorted({rad["kamp_dato"][:7] for rad in ledger})
    dropp = set(maneder_i_ledger[:maaneder])
    return [rad for rad in ledger if rad["kamp_dato"][:7] not in dropp]


def hent_metrikkserier(ledger):
    """
    Returnerer 4-tupelet `(profitter, innsatser, vant_flagg, clv_verdier)`
    trukket kolonnevis av ledger-radene, med `vant_flagg` utledet av
    `status == "vant"`.

    Finnes slik at bygg_manifest aldri inlinjer kolonne-uttrekk to ganger
    (én gang per rapportert vindu), og slik at "kun avgjorte bets når
    metrikkene" har ETT håndhevelsespunkt: en rad hvis `status` fremdeles
    er `"venter"` skal aldri nå hit, og simuler_bets garanterer at det
    ikke kan skje ved å hoppe over uavgjorte rader og telle dem som
    `bets_uten_utfall`.
    """
    profitter = [rad["gevinst"] for rad in ledger]
    innsatser = [rad["innsats"] for rad in ledger]
    vant_flagg = [rad["status"] == "vant" for rad in ledger]
    clv_verdier = [rad["clv"] for rad in ledger]
    return profitter, innsatser, vant_flagg, clv_verdier


def bygg_manifest(run_id, konfig, resultat_predict, resultat_sim, ledger,
                    type_kjoring="tuning", innbrenning_maaneder=INNBRENNING_MANEDER,
                    opprettet=None):
    """
    Setter sammen manifest-dict-en. Toppnivå-nøkler i denne rekkefølgen:
    `run_id`, `opprettet`, `type`, `headline`, `konfig`, `periode`,
    `datakvalitet`, `metrikker`, og — under D-05-02s låste alternativ a —
    `innbrenning_maaneder`, `innbrenning_fra_dato` og
    `metrikker_uten_innbrenning`.

    `datakvalitet` er den ærlige rapporterings-flaten for de to
    data-grensene 05-PLAN-OUTLINE.md flagget som aksepterte i stedet for
    undersøkte — tynn EU-region-bookmaker-dekning tidlig i 2022-23, og
    closing-linje-hullene — slik at en leser av manifest.json kan se dem
    uten å lese noen kode.

    `metrikker` er full-periode-settet og er HOVEDTALLET; `headline`-feltet
    finnes slik at ingen leser trenger å gjette hvilket sett som er hvilket.
    `metrikker_uten_innbrenning` er en SENSITIVITETSSJEKK over de samme
    radene minus de første `innbrenning_maaneder` PROSESSERTE månedene.
    Begge er billige fordi oppsummer_ledger er dato-uvitende og kan kalles
    på nytt over en filtrert delmengde av samme cachede ledger.
    """
    if opprettet is None:
        opprettet = datetime.now().isoformat()

    periode = {
        "fra_dato": resultat_predict["fra_dato"],
        "til_dato": resultat_predict["til_dato"],
        "datoer_totalt": resultat_predict["datoer_totalt"],
        "datoer_behandlet": resultat_predict["datoer_behandlet"],
        "kamper_totalt": resultat_predict["kamper_totalt"],
    }

    datakvalitet = {
        "datoer_hoppet_over_for_lite_treningsgrunnlag": resultat_predict["datoer_hoppet_over_for_lite_treningsgrunnlag"],
        "kamper_hoppet_over_manglende_odds": resultat_predict["kamper_hoppet_over_manglende_odds"],
        "kamper_hoppet_over_ukjent_lag": resultat_predict["kamper_hoppet_over_ukjent_lag"],
        "kamper_uten_closing_snapshot": resultat_predict["kamper_uten_closing_snapshot"],
        "kandidater_flagget": resultat_predict["kandidater_flagget"],
        "kandidater_blokkert_av_skadefilter": resultat_predict["kandidater_blokkert_av_skadefilter"],
        "skadesjekk_uten_datagrunnlag": resultat_predict["skadesjekk_uten_datagrunnlag"],
        "kandidater_uten_kelly_edge": resultat_sim["kandidater_uten_kelly_edge"],
        "bets_hoppet_over_duplikat": resultat_sim["bets_hoppet_over_duplikat"],
        "bets_uten_utfall": resultat_sim["bets_uten_utfall"],
        "datoer_stoppet_lav_bankroll": resultat_sim["datoer_stoppet_lav_bankroll"],
        "bets_uten_clv": resultat_sim["bets_uten_clv"],
        "retreninger": resultat_predict["retreninger"],
        "sluttsaldo": resultat_sim["sluttsaldo"],
    }

    profitter, innsatser, vant_flagg, clv_verdier = hent_metrikkserier(ledger)
    metrikker = oppsummer_ledger(
        profitter, innsatser, vant_flagg, konfig["startkapital"],
        clv_verdier=clv_verdier, n_resamples=BOOTSTRAP_N_RESAMPLES, seed=BOOTSTRAP_SEED,
    )

    manifest = {
        "run_id": run_id,
        "opprettet": opprettet,
        "type": type_kjoring,
        "headline": "metrikker",
        "konfig": konfig,
        "periode": periode,
        "datakvalitet": datakvalitet,
        "metrikker": metrikker,
    }

    if innbrenning_maaneder:
        ledger_uten_innbrenning = filtrer_ledger_etter_innbrenning(ledger, innbrenning_maaneder)
        manifest["innbrenning_maaneder"] = innbrenning_maaneder
        manifest["innbrenning_fra_dato"] = (
            min(rad["kamp_dato"] for rad in ledger_uten_innbrenning)
            if ledger_uten_innbrenning else None
        )
        p2, i2, v2, c2 = hent_metrikkserier(ledger_uten_innbrenning)
        manifest["metrikker_uten_innbrenning"] = oppsummer_ledger(
            p2, i2, v2, konfig["startkapital"],
            clv_verdier=c2, n_resamples=BOOTSTRAP_N_RESAMPLES, seed=BOOTSTRAP_SEED,
        )

    return manifest


def skriv_kjoring(run_id, manifest, ledger, katalog=BACKTEST_KATALOG):
    """
    Validerer `run_id`, oppretter `<katalog>/<run_id>/` og skriver
    `manifest.json` + `ledger.csv` inn i den.

    To garantier denne funksjonen finnes for å gi: `os.makedirs` UTEN
    `exist_ok` betyr at en eksisterende `run_id` kaster `FileExistsError`
    i stedet for å stille overskrive et tidligere løps bevis; og alt som
    skrives havner under `backtests/`, strukturelt adskilt fra botens
    egne tilstandsfiler for den ekte paper-trading-historikken, slik at
    simulerte penger aldri kan forveksles med den (05-CONTEXT.md sin
    eksplisitte advarsel, arvet fra .planning/research/ARCHITECTURE.md).
    """
    _valider_run_id(run_id)

    run_sti = os.path.join(katalog, run_id)
    katalog_abs = os.path.abspath(katalog)
    run_abs = os.path.abspath(run_sti)
    if not run_abs.startswith(katalog_abs + os.sep):
        raise ValueError(f"run_id løser til en sti utenfor {katalog!r}: {run_sti!r}")

    os.makedirs(run_sti)   # UTEN exist_ok — en eksisterende kjøring skal ALDRI overskrives

    manifest_sti = os.path.join(run_sti, MANIFEST_FIL)
    with open(manifest_sti, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    ledger_sti = os.path.join(run_sti, LEDGER_FIL)
    pd.DataFrame(ledger, columns=LEDGER_KOLONNER).to_csv(ledger_sti, index=False)

    return run_sti


def kjor_og_lagre(data, holdout=False, katalog=BACKTEST_KATALOG, tidspunkt=None,
                    min_value_terskel=config.MIN_VALUE_TERSKEL,
                    min_odds=config.MIN_ODDS,
                    maks_odds=config.MAX_ODDS,
                    min_treningskamper=MIN_TRENINGSKAMPER,
                    kalibrer_andel=model.KALIBRER_ANDEL,
                    bruk_skadefilter=True,
                    startkapital=config.STARTKAPITAL,
                    kelly_fraksjon=config.KELLY_FRAKSJON,
                    min_innsats=config.MIN_INNSATS,
                    maks_innsats=config.MAX_INNSATS,
                    flat_innsats=None,
                    innbrenning_maaneder=INNBRENNING_MANEDER,
                    skriv_ut=True):
    """
    Komponerer predict-passet, deretter simuleringspasset, bygger
    manifestet og skriver løpet — funksjonen plan 05-10s
    08_kjor_backtest.py kaller. Plan 05-09s Kelly-sweep kaller den BEVISST
    IKKE: sweepen gjenbruker ett cachet predict-pass og kaller simuler_bets
    per fraksjon i stedet.

    Når `holdout` er sann kalles den holdout-inngangen; når den er usann
    kalles kjor_backtest. Setter ALDRI det låste holdout-overstyrings-
    flagget sant noe sted i denne funksjonen — omtal alltid oppførselen i
    prosa som "holdout-inngangen", aldri som en direkte tilordning av flagget.

    Inneholder ingen forsøk-fangst-blokk: en HoldoutLaastFeil fra
    predict-passet må nå kalleren med INGEN kjøre-katalog opprettet, og det
    er derfor skrivingen skjer strengt ETTER at begge passene er ferdige i
    stedet for underveis.

    Manifestets `type`-felt settes fra `holdout`-argumentet, slik at et
    holdout-løp er identifiserbart fra sitt eget manifest uten å konsultere
    STATE.md.
    """
    felles_kwargs = dict(
        min_value_terskel=min_value_terskel, min_odds=min_odds, maks_odds=maks_odds,
        min_treningskamper=min_treningskamper, kalibrer_andel=kalibrer_andel,
        bruk_skadefilter=bruk_skadefilter, skriv_ut=skriv_ut,
    )
    if holdout:
        prediksjoner, resultat_predict = kjor_endelig_holdout_backtest(data, **felles_kwargs)
    else:
        prediksjoner, resultat_predict = kjor_backtest(data, **felles_kwargs)

    ledger, resultat_sim = simuler_bets(
        prediksjoner, startkapital=startkapital, kelly_fraksjon=kelly_fraksjon,
        min_innsats=min_innsats, maks_innsats=maks_innsats, flat_innsats=flat_innsats,
        skriv_ut=skriv_ut,
    )

    konfig = bygg_konfig_snapshot(resultat_predict, resultat_sim)
    run_id = bygg_run_id(konfig, tidspunkt=tidspunkt)
    type_kjoring = "holdout" if holdout else "tuning"
    manifest = bygg_manifest(
        run_id, konfig, resultat_predict, resultat_sim, ledger,
        type_kjoring=type_kjoring, innbrenning_maaneder=innbrenning_maaneder,
    )
    sti = skriv_kjoring(run_id, manifest, ledger, katalog=katalog)

    return sti, manifest, ledger
