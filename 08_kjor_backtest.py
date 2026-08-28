"""
STEG 8: Walk-forward backtest
==============================================================
En tynn CLI-innpakning rundt `backtest.py` sin walk-forward-motor. Denne
filen inneholder INGEN backtest-logikk selv — all den finnes i `backtest.py`
(plan 05-07 til 05-09). Det denne filen eier er overflaten et menneske
faktisk trykker på: argument-parsing, dato-validering og de to inngangene
til de to løpstypene.

En kjøring UTEN moteflagg spiller kun av trening/kalibrering-bolken og
skriver `backtests/<run_id>/`. Kelly-sweepen er opt-in bak `--sweep`. Den
låste holdouten nås kun ved å gi BÅDE `--holdout` og den separate
bekreftelses-flagget `--bekreft-holdout`; den brukes opp NØYAKTIG ÉN GANG
for hele prosjektet, og den resulterende `run_id`-en må skrives inn i
`.planning/STATE.md` etterpå (plan 05-13).
"""

import argparse
import inspect
import os
import re
import sys
from datetime import date, datetime, timedelta

import backtest
import config


# ---------------------------------------------------------------------------
# 1. Validatorer (plan 05-10 Task 1)
# ---------------------------------------------------------------------------


def iso_dato(verdi):
    """
    argparse `type=`-validator for `--fra`/`--til`. Returnerer `verdi`
    UENDRET som en `str` — aldri en `datetime` — fordi hver nedstrøms-
    forbruker sammenligner datoer som strenger: `odds.hent_unike_kampdatoer`
    sitt fra/til-filter og `backtest._sikre_ikke_holdout` sin holdout-
    sammenligning gjør begge det. En `datetime` her ville brutt begge.

    To sjekker, begge bærende og bevisst adskilt. Først kreves den EKSAKTE
    nullpolstrede formen med `re.fullmatch` mot `\\d{4}-\\d{2}-\\d{2}` — FØR
    `datetime.strptime` i det hele tatt kalles — fordi `strptime` alene
    godtar `"2024-1-5"`: en ekte kalenderdato, men feil FORM, som sorterer
    leksikalsk UNDER `"2024-10-01"` (`-`-byten er under `0`) i stedet for å
    havne på riktig side av holdout-grensen. Deretter bekrefter
    `datetime.strptime` at datoen faktisk EKSISTERER (avviser f.eks.
    `"2024-13-45"`).
    """
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", verdi or ""):
        raise argparse.ArgumentTypeError(
            f"Ugyldig dato {verdi!r} — forventet nullpolstret YYYY-MM-DD "
            "(f.eks. 2024-09-05, ikke 2024-9-5)"
        )
    try:
        datetime.strptime(verdi, "%Y-%m-%d")
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Ugyldig dato {verdi!r} — dette er ikke en ekte kalenderdato "
            "(forventet YYYY-MM-DD)"
        )
    return verdi


def positiv_flyt(verdi):
    """
    argparse `type=`-validator for numeriske knapper som må være strengt
    positive — i dag kun `--startkapital`. Konverterer med `float()` og
    avviser en verdi som ikke er strengt større enn 0.

    Reglene som involverer TO flagg samtidig (`--kelly-fraksjon` mot 0/1,
    `--min-odds` mot `--maks-odds`) hører hjemme i Task 2s `main()`, der
    begge verdiene allerede er kjent — ikke her, hvor bare én verdi noensinne
    er synlig.
    """
    tall = float(verdi)
    if not tall > 0:
        raise argparse.ArgumentTypeError(
            f"Ugyldig verdi {verdi!r} — må være strengt større enn 0"
        )
    return tall


def dag_for_holdout():
    """
    Returnerer dagen FØR `config.HOLDOUT_START_DATO` som en ISO-streng —
    den beregnede standard-øvre-grensen `main()` bruker når verken `--til`
    eller `--holdout` er gitt.

    Beregnet, aldri skrevet som en literal: holdout-grensen er D-05-01s
    eneste sannhetskilde, og en andre kopi av datoen her ville drevet stille
    ut av synk den dagen grensen en gang blir låst på nytt.

    Grunnen til at en standard i det hele tatt finnes:
    `klargjor_backtestdata(til=None)` returnerer HVER dato i
    `nba_features.csv`, helt frem til 2025-04-13 — godt inne i holdouten —
    og `kjor_backtest` sin pre-flight (plan 05-07 Task 2) sjekker hver dato
    i den listen FØR noe annet arbeid skjer. En ubegrenset standard ville
    derfor fått den aller enkleste kjøringen — `python 08_kjor_backtest.py`
    uten flagg, den `KOMME_I_GANG.md` dokumenterer — til å kaste
    `HoldoutLaastFeil` i stedet for å spille av trening/kalibrering-bolken.
    Å begrense her svekker ikke vakten — den kjører fortsatt på hver dato,
    den blir bare aldri gitt en dato den må avvise.

    Returtypen er `str`, samme kontrakt som `iso_dato`, fordi verdien flyter
    inn i nøyaktig de samme streng-sammenligningene.
    """
    return (date.fromisoformat(config.HOLDOUT_START_DATO) - timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------
# 2. Parser (plan 05-10 Task 1)
# ---------------------------------------------------------------------------


# Defaultene for --features-fil/--arkiv leses fra backtest.klargjor_backtestdata
# sin egen signatur i stedet for å skrives av på nytt — de to må aldri kunne
# drive fra hverandre.
_KLARGJOR_PARAMETRE = inspect.signature(backtest.klargjor_backtestdata).parameters


def bygg_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Kjører walk-forward-backtesten (Fase 5) over trening/"
            "kalibrering-bolken som standard."
        )
    )
    parser.add_argument(
        "--fra",
        type=iso_dato,
        default=None,
        help=(
            "Nedre grense (YYYY-MM-DD, inklusiv) for hvilke kampdatoer som "
            "tas med. Utelatt: starter på tidligste dato i nba_features.csv."
        ),
    )
    parser.add_argument(
        "--til",
        type=iso_dato,
        default=None,
        help=(
            "Øvre grense (YYYY-MM-DD, inklusiv) for hvilke kampdatoer som "
            "tas med. Utelatt: kjører helt frem til og med DAGEN FØR den "
            "låste holdout-sesongen starter — trening/kalibrering-bolken."
        ),
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help=(
            "Re-simulerer innsats ved flat, kvart, halv og full Kelly mot "
            "SAMME predict-pass, og skriver kelly_sweep.json ved siden av "
            "manifestet. Kan ikke kombineres med --holdout."
        ),
    )
    parser.add_argument(
        "--holdout",
        action="store_true",
        help=(
            "Evaluerer den låste 2024-25-holdouten. Brukes opp NØYAKTIG ÉN "
            "GANG for hele prosjektet. Krever --bekreft-holdout. Kan ikke "
            "kombineres med --sweep eller med --fra/--til."
        ),
    )
    parser.add_argument(
        "--bekreft-holdout",
        action="store_true",
        help=(
            "Bekrefter at du vet holdouten brukes opp én gang for hele "
            "prosjektet, og at hver terskel- og Kelly-beslutning allerede er "
            "frosset (plan 05-12). Har ingen mening alene, uten --holdout."
        ),
    )
    parser.add_argument(
        "--uten-skadefilter",
        action="store_true",
        help=(
            "Slår AV skadefilteret. Det er PÅ som standard fordi det er en "
            "del av den samme live beslutningspipelinen BT-01 spiller av — "
            "en kjøring uten det er ikke sammenlignbar med live-strategien."
        ),
    )
    parser.add_argument(
        "--min-value-terskel",
        type=float,
        default=config.MIN_VALUE_TERSKEL,
        help=f"Minste value for å flagge et bet (standard: config.MIN_VALUE_TERSKEL={config.MIN_VALUE_TERSKEL}).",
    )
    parser.add_argument(
        "--min-odds",
        type=float,
        default=config.MIN_ODDS,
        help=f"Nedre odds-grense for å vurdere et bet (standard: config.MIN_ODDS={config.MIN_ODDS}).",
    )
    parser.add_argument(
        "--maks-odds",
        type=float,
        default=config.MAX_ODDS,
        help=f"Øvre odds-grense for å vurdere et bet (standard: config.MAX_ODDS={config.MAX_ODDS}).",
    )
    parser.add_argument(
        "--kelly-fraksjon",
        type=float,
        default=config.KELLY_FRAKSJON,
        help=f"Kelly-fraksjon for innsatsstørrelse (standard: config.KELLY_FRAKSJON={config.KELLY_FRAKSJON}).",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help=(
            "Bruker D-05-03s flate stake (backtest.flat_innsats_belop, 2% av "
            "--startkapital) i stedet for Kelly-staking som løpets HOVEDregel "
            "— ikke bare som én sweep-arm. Lagt til for plan 05-12s "
            "frysing, etter at et sweep-funn viste en flat-stake-konfigurasjon "
            "verdt å fryse på. Kan ikke kombineres med en eksplisitt endret "
            "--kelly-fraksjon (tvetydig hvilken som skal gjelde)."
        ),
    )
    parser.add_argument(
        "--startkapital",
        type=positiv_flyt,
        default=config.STARTKAPITAL,
        help=f"Startkapital i kr (standard: config.STARTKAPITAL={config.STARTKAPITAL}).",
    )
    parser.add_argument(
        "--min-treningskamper",
        type=int,
        default=backtest.MIN_TRENINGSKAMPER,
        help=(
            "Datoer med færre tidligere kamper enn dette hoppes over i "
            f"stedet for å scores (standard: {backtest.MIN_TRENINGSKAMPER})."
        ),
    )
    parser.add_argument(
        "--features-fil",
        default=_KLARGJOR_PARAMETRE["features_fil"].default,
        help=f"CSV-filen kampdatoene leses fra (standard: {_KLARGJOR_PARAMETRE['features_fil'].default}).",
    )
    parser.add_argument(
        "--arkiv",
        default=_KLARGJOR_PARAMETRE["arkiv_fil"].default,
        help=f"Sti til SQLite odds-arkivet (standard: {_KLARGJOR_PARAMETRE['arkiv_fil'].default}).",
    )
    parser.add_argument(
        "--katalog",
        default=backtest.BACKTEST_KATALOG,
        help=f"Katalogen kjøringen skrives under (standard: {backtest.BACKTEST_KATALOG}).",
    )
    parser.add_argument(
        "--stille",
        action="store_true",
        help=(
            "Demper backtest.py sine egne per-pass-bannere "
            "(PREDIKSJONSPASS/SIMULERINGSPASS/KELLY-SWEEP). CLI-ens egen "
            "BACKTEST-OPPSUMMERING skrives alltid."
        ),
    )
    # Bevisst INGEN --innbrenning-maaneder: innbrennings-vinduet er en
    # fase-nivå-rapporteringspolicy (D-05-02) som manifest.json allerede
    # rapporterer begge veier (full periode + ex-innbrenning), ikke en
    # per-kjøring-knapp.
    return parser


# ---------------------------------------------------------------------------
# 3. De to løpsveiene (plan 05-10 Task 2)
# ---------------------------------------------------------------------------


def bygg_kjoreargumenter(args):
    """
    Bygger nøkkelord-dict-en de to løpsveiene DELER — alt som er likt
    mellom en tuning-kjøring og en holdout-kjøring. Inneholder bevisst
    IKKE `holdout` og IKKE `kjor_sweep`: det er de to eneste tingene som
    faktisk skiller de to veiene fra hverandre, og å holde dem UTENFOR
    denne dict-en er det som gjør forskjellen grep-bar — hver av dem
    settes eksplisitt på kun ett kallsted (kjor_tuning/kjor_holdout).

    Når `--flat` er satt sendes `kelly_fraksjon=None` og `flat_innsats`
    beregnes fra `backtest.flat_innsats_belop(startkapital)` — nøyaktig
    samme gren `simuler_bets` allerede bruker for sweepens flate arm
    (D-05-03), nå som løpets hovedregel i stedet for én sweep-arm blant fire.
    """
    if args.flat:
        kelly_fraksjon = None
        flat_innsats = backtest.flat_innsats_belop(args.startkapital)
    else:
        kelly_fraksjon = args.kelly_fraksjon
        flat_innsats = None
    return dict(
        katalog=args.katalog,
        min_value_terskel=args.min_value_terskel,
        min_odds=args.min_odds,
        maks_odds=args.maks_odds,
        min_treningskamper=args.min_treningskamper,
        bruk_skadefilter=not args.uten_skadefilter,
        startkapital=args.startkapital,
        kelly_fraksjon=kelly_fraksjon,
        flat_innsats=flat_innsats,
        skriv_ut=not args.stille,
    )


def last_data(args, bruk_skadefilter):
    """
    Kaller backtest.klargjor_backtestdata og oversetter en manglende
    inndatafil til en instruktiv norsk melding + sys.exit(1) i stedet for
    en rå traceback.

    Dette er den ENESTE except-klausulen i hele filen utover iso_dato sin
    egen smale ValueEror->ArgumentTypeError-konvertering, og den fanger
    bevisst KUN FileNotFoundError: en bredere fanger her ville svelget
    backtest.HoldoutLaastFeil eller en ValueError fra kjor_og_lagre og
    gjort fasens primære vakt om til en printet advarsel i stedet for en
    feilende prosess — backtest.py selv håndheves med samme smale
    disiplin (dens egen kildenivå-test forbyr brede fangere).
    """
    try:
        return backtest.klargjor_backtestdata(
            features_fil=args.features_fil,
            arkiv_fil=args.arkiv,
            fra=args.fra,
            til=args.til,
            bruk_skadefilter=bruk_skadefilter,
        )
    except FileNotFoundError as e:
        print(f"Fant ikke en påkrevd inndatafil: {e}")
        print("Mulig årsak og hvilket script som produserer filen:")
        print(f"  - {args.features_fil} -> kjør 02_feature_engineering.py")
        print(f"  - {args.arkiv} -> kjør 07_hent_historisk_odds.py")
        print("  - nba_spillerlogg_raw.csv -> kjør spillerlogg.py")
        sys.exit(1)


def kjor_tuning(args):
    """
    Trening/kalibrering-veien — filens VANLIGE, gjentakbare vei. Kaller
    ALDRI navnet `holdout` i det hele tatt; parameterens egen standard
    (usann) får gjelde, som er hele poenget: denne funksjonens kildekode
    skal ikke måtte inneholde ordet for å bevise at den aldri åpner
    vinduet.
    """
    kjoreargumenter = bygg_kjoreargumenter(args)
    data = last_data(args, kjoreargumenter["bruk_skadefilter"])
    return backtest.kjor_og_lagre(data, kjor_sweep=args.sweep, **kjoreargumenter)


def kjor_holdout(args):
    """
    Den ENESTE funksjonen i denne filen som noensinne sender et sant
    `holdout`-argument, og den ENESTE hvis kildekode har lov til å
    inneholde tokenet `holdout=True` (håndhevet av
    test_bare_holdout_funksjonen_apner_vinduet). Den sender heller ALDRI
    noe `kjor_sweep`-argument — de to kan derfor aldri opptre sammen selv
    om en fremtidig redigering skulle svekke sjekken i main().

    Printer advarsels-blokken FØR noe lastes eller kjøres, i samme
    "!" * 60-form 07_hent_historisk_odds.py bruker før et ugjenkallelig
    steg.
    """
    print("!" * 60)
    print("ADVARSEL: Dette evaluerer den LÅSTE 2024-25-holdouten.")
    print("Den brukes opp NØYAKTIG ÉN GANG for hele prosjektet og kan IKKE")
    print("brukes opp på nytt etterpå.")
    print("Hver terskel- og Kelly-beslutning må allerede være FROSSET")
    print("(plan 05-12) FØR denne kjøringen — konfigurasjonen echoet over")
    print("må stemme med den frosne.")
    print("run_id-en fra denne kjøringen må skrives inn i")
    print(".planning/STATE.md etterpå (plan 05-13).")
    print("!" * 60)

    kjoreargumenter = bygg_kjoreargumenter(args)
    data = last_data(args, kjoreargumenter["bruk_skadefilter"])
    return backtest.kjor_og_lagre(data, holdout=True, **kjoreargumenter)


def skriv_oppsummering(sti, manifest, kjorte_sweep):
    """
    Printer BACKTEST-OPPSUMMERING: run id, løpstype, katalogsti,
    periode-tallene, deretter data-hopp-tellerne fra `datakvalitet` RETT
    VED SIDEN AV hovedtallene fra `metrikker` — ikke lenger nede i
    utskriften. Et bet-antall og en ROI uten hopp-tellerne ved siden av
    leser som sterkere bevis enn de er (05-RESEARCH.md Pitfall 2). Leser
    hver verdi rett ut av manifestet med dict-oppslag — regner ingenting
    ut selv.
    """
    periode = manifest["periode"]
    datakvalitet = manifest["datakvalitet"]
    metrikker = manifest["metrikker"]

    print("=" * 60)
    print("BACKTEST-OPPSUMMERING")
    print(f"run_id:               {manifest['run_id']}")
    print(f"type:                 {manifest['type']}")
    print(f"katalog:              {sti}")
    print(f"fra_dato:             {periode['fra_dato']}")
    print(f"til_dato:             {periode['til_dato']}")
    print(f"datoer_behandlet:     {periode['datoer_behandlet']}")
    print(f"kamper_totalt:        {periode['kamper_totalt']}")
    print(f"kamper_hoppet_over_manglende_odds:  {datakvalitet['kamper_hoppet_over_manglende_odds']}")
    print(f"kandidater_flagget:                 {datakvalitet['kandidater_flagget']}")
    print(f"kandidater_blokkert_av_skadefilter:  {datakvalitet['kandidater_blokkert_av_skadefilter']}")
    print(f"retreninger:                         {datakvalitet['retreninger']}")
    print(f"antall_bets:          {metrikker['antall_bets']}")
    print(
        f"roi:                  {metrikker['roi']:.1%} "
        f"(KI {metrikker['roi_ci_nedre']:.1%} – {metrikker['roi_ci_oevre']:.1%})"
    )
    print(f"vinnrate:             {metrikker['vinnrate']:.1%}")
    print(f"maks_drawdown:        {metrikker['maks_drawdown_andel']:.1%}")
    print(f"clv_snitt:            {metrikker['clv_snitt']}")
    print("=" * 60)
    print(f"manifest.json skrevet til: {os.path.join(sti, backtest.MANIFEST_FIL)}")
    if kjorte_sweep:
        print(f"kelly_sweep.json skrevet til: {os.path.join(sti, backtest.SWEEP_FIL)}")


# ---------------------------------------------------------------------------
# 4. main() (plan 05-10 Task 2)
# ---------------------------------------------------------------------------


def main():
    parser = bygg_parser()
    args = parser.parse_args()

    # 1. Bekreftelsen har intet subjekt uten --holdout.
    if args.bekreft_holdout and not args.holdout:
        parser.error(
            "--bekreft-holdout uten --holdout gir ingen mening — det er "
            "ingenting å bekrefte"
        )

    # 2. Ett flagg er ikke nok for en ugjenkallelig handling.
    if args.holdout and not args.bekreft_holdout:
        parser.error(
            "--holdout krever --bekreft-holdout — holdouten brukes opp "
            "NØYAKTIG ÉN GANG for hele prosjektet, og skal ikke kunne "
            "brukes opp av ett enkelt flagg. Legg til --bekreft-holdout."
        )

    # 3. En sweep VELGER en staking-regel; holdouten scores én gang på en
    #    allerede frosset regel — å sweepe holdouten er tuning på nettopp
    #    det som skal forbli urørt.
    if args.holdout and args.sweep:
        parser.error(
            "--holdout kan ikke kombineres med --sweep — en sweep finnes "
            "for å VELGE en staking-regel, mens holdouten skal scores én "
            "gang på en allerede frosset regel (plan 05-12)"
        )

    # 4. Holdout-veien begrenser sitt eget datoområde selv; et område gitt
    #    her gjør det evaluerte omfanget tvetydig.
    if args.holdout and (args.fra is not None or args.til is not None):
        parser.error(
            "--holdout kan ikke kombineres med --fra/--til — holdout-veien "
            "begrenser selv datoområdet til >= config.HOLDOUT_START_DATO; "
            "et område gitt her ville gjort det evaluerte omfanget tvetydig"
        )

    # 5. Standard øvre grense: KUN når holdout er usann OG --til er utelatt.
    #    klargjor_backtestdata(til=None) returnerer hver dato i
    #    nba_features.csv, og kjor_backtest sin pre-flight (plan 05-07
    #    Task 2) sjekker hver dato i den listen før noe annet arbeid skjer
    #    — en ubegrenset standard ville derfor fått den vanlige
    #    `python 08_kjor_backtest.py` til å kaste HoldoutLaastFeil i
    #    stedet for å spille av trening/kalibrering-bolken. Vakten
    #    svekkes ikke av dette — den kjører fortsatt på hver dato, den
    #    blir bare aldri gitt en dato den må avvise. Holdout-veien
    #    røres ALDRI her: kjor_og_lagre(holdout=True) narrower til
    #    >= config.HOLDOUT_START_DATO selv, og en klemt til her ville gitt
    #    den et tomt område.
    til_er_standard = False
    if not args.holdout and args.til is None:
        args.til = dag_for_holdout()
        til_er_standard = True

    # 6. Sammenligningen er en ren strengsammenligning fordi iso_dato
    #    allerede har garantert den nullpolstrede formen på begge sider.
    if args.fra is not None and args.til is not None and args.fra > args.til:
        parser.error(
            f"--fra ({args.fra}) er etter --til ({args.til}) — tomt "
            "datoområde. Standard øvre grense er dagen før den låste "
            "holdouten, så en startdato inne i holdouten gir et tomt "
            "område her — holdouten nås kun via --holdout."
        )

    # 7. --flat og en eksplisitt endret --kelly-fraksjon samtidig er
    #    tvetydig — hvilken skal faktisk gjelde som løpets hovedregel?
    if args.flat and args.kelly_fraksjon != config.KELLY_FRAKSJON:
        parser.error(
            "--flat kan ikke kombineres med en eksplisitt --kelly-fraksjon "
            f"({args.kelly_fraksjon}) — --flat erstatter Kelly-staking helt "
            "som løpets hovedregel, så det er tvetydig hvilken som skal gjelde."
        )

    # 8. Ved fraksjon 0 blir hver innsats 0.0 (strategy.beregn_innsats),
    #    som gir et løp som tilsynelatende aldri taper. Denne sjekken
    #    gjelder ikke når --flat er satt: da er --kelly-fraksjon irrelevant
    #    (kelly_fraksjon sendes som None til simuler_bets, ikke som et tall).
    if not args.flat and not (0 < args.kelly_fraksjon <= 1.0):
        parser.error(
            f"--kelly-fraksjon {args.kelly_fraksjon} må være strengt større "
            "enn 0 og høyst 1.0. Ved fraksjon 0 blir hver innsats 0.0 "
            "(strategy.beregn_innsats), som gir et løp som aldri kan tape — "
            "bruk --flat for en ekte flat-stake-hovedkjøring, eller --sweep "
            "for en flat-stake-sammenligning ved siden av Kelly-armene."
        )

    # 9. Et omvendt odds-bånd flagger ingenting og leser som "modellen fant
    #    ingen value".
    if not (args.min_odds < args.maks_odds):
        parser.error(
            f"--min-odds ({args.min_odds}) må være strengt under "
            f"--maks-odds ({args.maks_odds})"
        )

    modus = "holdout" if args.holdout else "tuning"
    print("=" * 60)
    print("WALK-FORWARD BACKTEST")
    print("=" * 60)
    print(f"Modus:                {modus}")
    print(f"Fra:                  {args.fra or '(tidligste dato i nba_features.csv)'}")
    til_merke = " (standard: dagen før holdout)" if til_er_standard else ""
    print(f"Til:                  {(args.til or '(ingen øvre grense — kun holdout-veien)')}{til_merke}")
    print(f"Sweep:                {args.sweep}")
    print(f"Uten skadefilter:     {args.uten_skadefilter}")
    print(f"Min value-terskel:    {args.min_value_terskel}")
    print(f"Min odds:             {args.min_odds}")
    print(f"Maks odds:            {args.maks_odds}")
    if args.flat:
        print(f"Kelly-fraksjon:       (flat stake, se under)")
        print(f"Flat innsats:         {backtest.flat_innsats_belop(args.startkapital)} kr")
    else:
        print(f"Kelly-fraksjon:       {args.kelly_fraksjon}")
    print(f"Startkapital:         {args.startkapital}")
    print(f"Min treningskamper:   {args.min_treningskamper}")
    print(f"Features-fil:         {args.features_fil}")
    print(f"Arkiv:                {args.arkiv}")
    print(f"Katalog:              {args.katalog}")
    print("=" * 60)

    if args.holdout:
        sti, manifest, ledger = kjor_holdout(args)
    else:
        sti, manifest, ledger = kjor_tuning(args)

    skriv_oppsummering(sti, manifest, args.sweep)

    # Ingen try/except her utover last_data sin smale FileNotFoundError-
    # fanger: en HoldoutLaastFeil eller en ValueError fra kjor_og_lagre er
    # motorens egne vakter og skal nå terminalen som en traceback med en
    # ikke-null avslutningskode — samme disiplin 04_value_detector.py sin
    # egen sys.exit(1)-kommentar advarer om andre steder i kodebasen. En
    # bred fanger her ville printet dem som en advarsel og avsluttet med
    # 0 på en blokkert kjøring.
    sys.exit(0)


if __name__ == "__main__":
    main()
