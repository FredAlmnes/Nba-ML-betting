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
    # Bevisst INGEN --flat-innsats: den flate staken er en sweep-ARM
    # (D-05-03), ikke en egen kjøremodus — en "flat kjøring" utenfor
    # sweepen ville gitt en hovedtall-ROI uten noen Kelly-basislinje ved
    # siden av å sammenligne mot.
    # Bevisst INGEN --innbrenning-maaneder: innbrennings-vinduet er en
    # fase-nivå-rapporteringspolicy (D-05-02) som manifest.json allerede
    # rapporterer begge veier (full periode + ex-innbrenning), ikke en
    # per-kjøring-knapp.
    return parser


if __name__ == "__main__":
    # Task 1 gir denne guarden bevisst INGEN dispatch/main() ennå —
    # bygg_kjoreargumenter/kjor_tuning/kjor_holdout/main() og de fire
    # holdout-kombinasjonsvaktene kommer i Task 2. Det som står her er kun
    # de rene TO-FLAGG-vaktene som ikke avhenger av noen dispatch: en
    # eksplisitt gitt --fra etter en eksplisitt gitt --til, en
    # --kelly-fraksjon utenfor (0, 1.0], og en --min-odds som ikke er
    # strengt under --maks-odds. Standard-øvre-grense-utledningen
    # (dag_for_holdout() anvendt på en UTELATT --til) er Task 2s jobb —
    # den avhenger av om --holdout er gitt, som denne guarden ennå ikke
    # bryr seg om. Ingen data leses og ingen katalog opprettes herfra.
    _parser = bygg_parser()
    _args = _parser.parse_args()

    if _args.fra is not None and _args.til is not None and _args.fra > _args.til:
        _parser.error(
            f"--fra ({_args.fra}) er etter --til ({_args.til}) — tomt datoområde"
        )

    if not (0 < _args.kelly_fraksjon <= 1.0):
        _parser.error(
            f"--kelly-fraksjon {_args.kelly_fraksjon} må være strengt større enn 0 "
            "og høyst 1.0. Ved fraksjon 0 blir hver innsats 0.0 "
            "(strategy.beregn_innsats), som gir et løp som aldri kan tape — bruk "
            "--sweep for en ekte flat-stake-sammenligning i stedet."
        )

    if not (_args.min_odds < _args.maks_odds):
        _parser.error(
            f"--min-odds ({_args.min_odds}) må være strengt under "
            f"--maks-odds ({_args.maks_odds})"
        )
