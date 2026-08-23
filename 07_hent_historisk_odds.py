"""
STEG 7: Historisk odds-backfill (tørrkjøring som standard)
=============================================================
En engangs-/periodisk jobb som fyller det permanente SQLite-arkivet
(`odds_arkiv.db`) med historiske NBA-odds for hver unike kampdato i
`nba_features.csv` – grunnlaget Fase 5-backtesten skal stå på (ODDS-01).

Jobben er GJENOPPTAGBAR: en dato som allerede er arkivert for gitt
`--snapshot-type` blir aldri hentet på nytt (se odds.er_allerede_arkivert),
så å kjøre dette scriptet flere ganger på rad koster ingenting utover det
som gjenstår. Alt betalt arbeid ligger i odds.kjor_backfill – denne filen
er en tynn CLI-innpakning rundt den og inneholder selv ingen hentelogikk.

Scriptet er en TØRRKJØRING med mindre du eksplisitt gir `--utfor` – uten det
flagget gjøres ingen nettverkskall i det hele tatt, og du trenger ikke
engang en API-nøkkel for å se hva et ekte løp ville gjort.

Verifisert kostnadsmodell (04-RESEARCH.md, D-03-amendmentet):
  - bet_time:  1 sport-wide odds-kall PER DATO  = 10 kreditter/dato
  - closing:   1 discovery-kall (1 kreditt) + 1 odds-kall PER avspark-klynge
               (10 kreditter/klynge) – en travel dato kan ha flere klynger,
               så closing sin faktiske kostnad kan bli høyere enn 11/dato

Bruk et lite `--datoer N` som smoke-test-knapp før du noensinne setter
`--maks-kreditt` høyt nok til å dekke alle 480 datoene.
"""

import argparse
import sys

import odds


def bygg_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Historisk odds-backfill mot The Odds API – gjenopptagbar, "
            "kredittbegrenset, tørrkjøring med mindre --utfor gis."
        )
    )
    parser.add_argument(
        "--snapshot-type",
        required=True,
        choices=["bet_time", "closing"],
        help="Hvilken type historisk snapshot som skal hentes for hver dato.",
    )
    parser.add_argument(
        "--maks-kreditt",
        required=True,
        type=int,
        help=(
            "Øvre grense for kreditter dette løpet får bruke totalt. "
            "Ingen standardverdi – du må oppgi den hver gang."
        ),
    )
    parser.add_argument(
        "--utfor",
        action="store_true",
        help=(
            "Utfør ekte kall og bruk ekte kreditter. Uten dette flagget er "
            "løpet en TØRRKJØRING og gjør ingen nettverkskall i det hele tatt."
        ),
    )
    parser.add_argument(
        "--fra",
        default=None,
        help="Valgfri nedre grense (YYYY-MM-DD, inklusiv) for hvilke kampdatoer som tas med.",
    )
    parser.add_argument(
        "--til",
        default=None,
        help="Valgfri øvre grense (YYYY-MM-DD, inklusiv) for hvilke kampdatoer som tas med.",
    )
    parser.add_argument(
        "--datoer",
        type=int,
        default=None,
        help="Begrens løpet til de N første datoene (etter --fra/--til-filtrering) – smoke-test-knapp.",
    )
    parser.add_argument(
        "--features-fil",
        default="nba_features.csv",
        help="CSV-filen kampdatoene leses fra (standard: nba_features.csv).",
    )
    parser.add_argument(
        "--arkiv",
        default=odds.ARKIV_FIL,
        help=f"Sti til SQLite-arkivet (standard: {odds.ARKIV_FIL}).",
    )
    return parser


def main():
    args = bygg_parser().parse_args()

    print("=" * 60)
    print("HISTORISK ODDS-BACKFILL")
    print("=" * 60)
    print(f"Snapshot-type:   {args.snapshot_type}")
    print(f"Maks kreditt:    {args.maks_kreditt}")
    print(f"Utfør (ekte):    {args.utfor}")
    print(f"Fra:             {args.fra or '(ingen nedre grense)'}")
    print(f"Til:             {args.til or '(ingen øvre grense)'}")
    print(f"Features-fil:    {args.features_fil}")
    print(f"Arkiv:           {args.arkiv}")

    datoer = odds.hent_unike_kampdatoer(args.features_fil, args.fra, args.til)
    if args.datoer is not None:
        datoer = datoer[: args.datoer]

    print(f"Antall datoer:   {len(datoer)}")

    api_nokkel = None
    if args.utfor:
        api_nokkel = odds.hent_api_nokkel()
        per_dato = 10 if args.snapshot_type == "bet_time" else 11
        print("!" * 60)
        print("ADVARSEL: Dette løpet vil nå bruke EKTE kreditter.")
        print(f"Kredittgrense:            {args.maks_kreditt}")
        print(
            f"Verste-fall-kostnad:      {len(datoer) * per_dato} "
            f"({'nedre anslag – closing kan ha flere klynger per dato' if args.snapshot_type == 'closing' else 'nøyaktig'})"
        )
        print("!" * 60)
    else:
        print("TØRRKJØRING – ingen API-kall utføres. Legg til --utfor for å hente på ekte.")

    con = odds.apne_arkiv(args.arkiv)
    try:
        resultat = odds.kjor_backfill(
            con,
            api_nokkel,
            datoer,
            args.snapshot_type,
            args.maks_kreditt,
            utfor=args.utfor,
        )
    finally:
        con.close()

    print("\nResultat:")
    for nokkel, verdi in resultat.items():
        print(f"  {nokkel}: {verdi}")

    if resultat["avbrutt_grunn"]:
        print(f"\nLøpet stoppet før alle datoer var behandlet: {resultat['avbrutt_grunn']}")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
