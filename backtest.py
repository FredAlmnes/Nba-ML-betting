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
