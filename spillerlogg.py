"""
Historisk spiller-kamplogg-innhenting, normalisering og lagring/lesing.

Denne modulen eksisterer fordi `nba_kamper_raw.csv` og `nba_features.csv`
kun er på lag-nivå (én rad per lag per kamp) — ingen `PLAYER_ID`, ingen
per-spiller `MIN`. Det betyr at det live skadefilteret (`skadefilter.py`)
ikke kan gjøres as-of-bevisst (dvs. "hvem spilte faktisk før dato X") uten
en spiller-nivå kamplogg. Denne modulen bygger og lagrer nettopp den
loggen: `nba_spillerlogg_raw.csv`.

Forbrukeren av arkivet er plan 05-06 sin `sjekk_lag_helse_som_of()` i
`skadefilter.py`, som slår opp spillerens minutter i tidsvinduet før en
gitt kampdato for å avgjøre om en toppspiller var tilgjengelig.

Henting skjer utelukkende mot det gratis, nøkkelfrie `nba_api`-biblioteket
(samme kilde som `01_hent_data.py` og `skadefilter.py` allerede bruker) —
aldri mot The Odds API. Å kjøre denne modulen på nytt koster derfor ingen
Odds API-kreditter.

Denne modulen gjør ingen nettverkskall bare ved `import spillerlogg` —
akkurat som `skadefilter.py`, ligger alle nba_api-kall inne i funksjoner
og utløses først når noen faktisk ber om ferske data.
"""

import sys
import time

import pandas as pd
from nba_api.stats.endpoints import leaguegamelog

# -------------------------------------------------------
# Konfigurasjon
# -------------------------------------------------------
SESONGER = ["2022-23", "2023-24", "2024-25"]  # Må holdes i sync med 01_hent_data.py:29 —
                                                # en sesong som finnes i én fil og mangler i
                                                # den andre gjør skadesjekken stille meningsløs
                                                # for de datoene.
SPILLERLOGG_FIL = "nba_spillerlogg_raw.csv"
SESONGTYPE = "Regular Season"  # Matcher 01_hent_data.py sin season_type_nullable="Regular
                                # Season", slik at spillerloggen dekker akkurat de kampene
                                # nba_features.csv inneholder — ingen sluttspillkamper i tillegg.
PAUSE_SEKUNDER = 1.0  # Viktig: nba_api har rate limiting, se 01_hent_data.py:47-48

KILDEKOLONNER = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "GAME_ID", "GAME_DATE", "MIN"]
KOLONNER = ["SESONG"] + KILDEKOLONNER


def hent_sesong_logg(sesong):
    """
    Henter én sesongs spiller-kamplogg fra nba_api. Returnerer tom
    DataFrame ved feil — samme konvensjon som skadefilter.hent_spillerdata.

    player_or_team_abbreviation="P" er obligatorisk: parameterklassens
    standardverdi er "T" (lag-modus), som ville gitt lag-nivå-rader helt
    uten PLAYER_ID — akkurat den feilen denne modulen finnes for å unngå.
    """
    try:
        df = leaguegamelog.LeagueGameLog(
            league_id="00",
            player_or_team_abbreviation="P",
            season=sesong,
            season_type_all_star=SESONGTYPE,
        ).get_data_frames()[0]
        time.sleep(PAUSE_SEKUNDER)
        return df
    except Exception as e:
        print(f"  (Kunne ikke hente spillerlogg for sesong {sesong}: {e})")
        return pd.DataFrame()


def normaliser_spillerlogg(df, sesong):
    """
    Ren funksjon, ingen nettverk, ingen I/O. Normaliserer en rå
    nba_api-spillerlogg-DataFrame til KOLONNER-skjemaet.

    Kaster ValueError hvis en forventet kildekolonne mangler — dette er
    det eneste stedet i modulen som kaster i stedet for å hoppe over,
    fordi en stille manglende kolonne ville gjort as-of-skadesjekken i
    plan 05-06 til en tom groupby som slipper alle lag gjennom uten
    advarsel (Pitfall 1 sin stille-bias-feil).
    """
    manglende = [k for k in KILDEKOLONNER if k not in df.columns]
    if manglende:
        raise ValueError(
            f"nba_api-responsen mangler forventede kolonner: {manglende}. "
            "En stille manglende kolonne her ville gjort as-of-skadefilteret "
            "i skadefilter.py til en tom sjekk som slipper alle lag gjennom "
            "uten varsel (Pitfall 1)."
        )

    ut = df[KILDEKOLONNER].copy()
    ut["SESONG"] = sesong
    ut = ut[KOLONNER]

    # GAME_DATE tvinges til en YYYY-MM-DD-streng uansett hva nba_api
    # returnerte. Dette er det som gjør plan 05-06 sin rene
    # GAME_DATE < as_of_dato-strengsammenligning korrekt, identisk med
    # features.py sin GAME_DATE_HJEMME < as_of-konvensjon. Streng < (aldri
    # <=) er kallerens ansvar.
    ut["GAME_DATE"] = pd.to_datetime(ut["GAME_DATE"]).dt.strftime("%Y-%m-%d")

    # Null eller uparserbar MIN blir bevisst 0.0 — det biaser den
    # nedstrøms sjekken mot "spilleren ser utilgjengelig ut" (betten
    # flagges usikker), som er den konservative retningen. Motsatt
    # standard ville skapt falsk trygghet om en spiller som kanskje ikke
    # spilte.
    ut["MIN"] = pd.to_numeric(ut["MIN"], errors="coerce").fillna(0.0).astype(float)

    ut = ut.dropna(subset=["PLAYER_ID", "GAME_DATE"])
    ut = ut.sort_values(["GAME_DATE", "TEAM_ID", "PLAYER_ID"]).reset_index(drop=True)
    return ut


def hent_spillerlogg(sesonger=None, hent_fn=None, eksisterende_df=None):
    """
    Sløyfer over sesongene og bygger den fullstendige spillerloggen.

    'hent_fn' er dette modulens injeksjonspunkt og hele grunnen til at
    testene ikke trenger nettverk — samme mønster som
    skadefilter.hent_spillerstatistikk sine siste3/sesong_snitt-keywords.

    'eksisterende_df', hvis gitt og ikke tom, brukes til å hoppe over
    sesonger som allerede er hentet (gjenopptakelse). Det holder også
    repeterte kjøringer unna det gratis nba_api-endepunktet.

    En sesong der hent_fn returnerer en tom DataFrame logges og hoppes
    over — aldri raise, aldri avbryt de gjenværende sesongene.

    Returnerer (spillerlogg_df, resultat).
    """
    if sesonger is None:
        sesonger = SESONGER
    if hent_fn is None:
        hent_fn = hent_sesong_logg

    allerede_hentede_sesonger = set()
    eksisterende_rammer = []
    if eksisterende_df is not None and not eksisterende_df.empty:
        allerede_hentede_sesonger = set(eksisterende_df["SESONG"].unique())
        eksisterende_rammer.append(eksisterende_df)

    resultat = {
        "sesonger_totalt": len(sesonger),
        "sesonger_hentet": 0,
        "allerede_hentet": 0,
        "hoppet_over": [],
        "rader_totalt": 0,
    }

    nye_rammer = []
    for sesong in sesonger:
        if sesong in allerede_hentede_sesonger:
            resultat["allerede_hentet"] += 1
            continue

        rå_df = hent_fn(sesong)
        if rå_df.empty:
            print(f"  Advarsel: ingen data for sesong {sesong} — hopper over.")
            resultat["hoppet_over"].append(sesong)
            continue

        normalisert = normaliser_spillerlogg(rå_df, sesong)
        nye_rammer.append(normalisert)
        resultat["sesonger_hentet"] += 1

    alle_rammer = eksisterende_rammer + nye_rammer
    if alle_rammer:
        spillerlogg_df = pd.concat(alle_rammer, ignore_index=True)
        spillerlogg_df = spillerlogg_df.sort_values(
            ["GAME_DATE", "TEAM_ID", "PLAYER_ID"]
        ).reset_index(drop=True)
    else:
        spillerlogg_df = pd.DataFrame(columns=KOLONNER)

    resultat["rader_totalt"] = len(spillerlogg_df)
    return spillerlogg_df, resultat


def lagre_spillerlogg(df, filnavn=SPILLERLOGG_FIL):
    """Lagrer spillerloggen til CSV."""
    df.to_csv(filnavn, index=False)
    print(f"Spillerlogg lagret til '{filnavn}' ({len(df)} rader)")


def les_spillerlogg(filnavn=SPILLERLOGG_FIL):
    """
    Leser spillerloggen fra CSV. GAME_DATE/SESONG/PLAYER_NAME tvinges til
    str slik at GAME_DATE aldri kommer tilbake som datetime og stille
    ødelegger streng-as-of-sammenligningen.

    Kaster FileNotFoundError med en forklarende melding hvis filen
    mangler — samme brukervendte-instruksjon-konvensjon som
    05_skadefilter.py bruker for en manglende value_bets_idag.csv.
    """
    try:
        df = pd.read_csv(
            filnavn,
            dtype={"SESONG": str, "GAME_DATE": str, "PLAYER_NAME": str},
        )
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Finner ikke '{filnavn}' – kjør 'python3 spillerlogg.py' først!"
        )

    manglende = [k for k in KILDEKOLONNER if k not in df.columns]
    if manglende:
        raise ValueError(
            f"'{filnavn}' mangler forventede kolonner: {manglende} — "
            "filen er kanskje håndredigert eller avkuttet."
        )
    return df


def main():
    print("=" * 60)
    print("STEG: Hent historisk spiller-kamplogg")
    print("=" * 60)

    eksisterende_df = None
    try:
        eksisterende_df = les_spillerlogg()
        print(f"Fant eksisterende arkiv med {len(eksisterende_df)} rader — henter kun manglende sesonger.")
    except FileNotFoundError:
        print("Ingen eksisterende spillerlogg funnet — henter alle sesonger fra bunnen av.")

    spillerlogg_df, resultat = hent_spillerlogg(eksisterende_df=eksisterende_df)

    print("\n" + "=" * 60)
    print("OPPSUMMERING")
    print("=" * 60)
    for nokkel, verdi in resultat.items():
        print(f"  {nokkel}: {verdi}")

    if spillerlogg_df.empty:
        print("\nFEIL: ingen spillerdata hentet for noen sesong. Skriver IKKE fil — "
              "en tom spillerlogg ville gjort backtestens skadefilter til en stille "
              "no-op som slipper alle lag gjennom.")
        sys.exit(1)  # NB: bare exit() gir exitkode 0 (=suksess) og gjemmer feilen for kalleren

    lagre_spillerlogg(spillerlogg_df)

    if resultat["hoppet_over"]:
        print(f"\nDelvis kjøring — sesonger hoppet over: {resultat['hoppet_over']}. "
              "Kjør 'python3 spillerlogg.py' på nytt for å hente kun disse.")
        sys.exit(1)  # NB: bare exit() gir exitkode 0 (=suksess) og gjemmer feilen for kalleren

    sys.exit(0)


if __name__ == "__main__":
    main()
