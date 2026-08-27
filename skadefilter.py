"""
Delt modul for skadefilter-beslutningslogikk.

Erstatter den gamle 05_skadefilter.py, som utførte alt — inkludert fire
nba_api-nettverkskall og en `print(f"Bruker sesong: {SESONG}")` — på
modul-nivå ved import. Det gjorde filen umulig å importere trygt fra
06_bot.py (som derfor måtte kjøre den som en egen underprosess i stedet —
se plan 04-08, som fjerner dette).

Denne modulen gjør ingen nettverkskall bare ved `import skadefilter` — alle
nba_api-kall skjer inne i funksjoner, og kalles først når noen faktisk ber
om ferske data (hent_spillerstatistikk / filtrer_bets_for_skader uten
injiserte DataFrames). Dette gjør beslutningslogikken testbar uten nettverk
og importerbar i prosess av 06_bot.py (plan 04-08).

05_skadefilter.py er nå en tynn CLI-wrapper som importerer herfra.
"""

import time
from datetime import datetime as _dt

import pandas as pd
from nba_api.stats.endpoints import leaguedashplayerstats

from teams import finn_lag_id

# -------------------------------------------------------
# Konfigurasjon
# -------------------------------------------------------
ANTALL_TOPPSPILLERE = 3     # Sjekk de N viktigste spillerne per lag
MIN_MINUTTER = 20           # Ignorer spillere med under 20 min/kamp (sesongsnitt)
SISTE_N_KAMPER = 3           # Speiler live-veiens LeagueDashPlayerStats(last_n_games=3) -- lagets N siste kamper, aldri uavhengig utledet på nytt i as-of-veien
SPILLERLOGG_KOLONNER = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "GAME_DATE", "MIN"]  # Delmengden av plan 05-05s nba_spillerlogg_raw.csv denne modulen trenger; SESONG og GAME_ID finnes i filen men brukes ikke her


def gjeldende_sesong():
    """
    Beregner NBA-sesong dynamisk, f.eks. '2025-26'.

    NB: denne funksjonen og gjeldende_sesong() i verdi_deteksjon.py (plan
    04-06, tidligere 04_value_detector.py) er samme NBA-sesong-utledning,
    duplisert i to filer. Begge ekstraheres i denne fasen, men
    04-CONTEXT.md skoper ikke en delt sesong-modul, og dette var aldri ett
    av Phase 2 D-03s fire oppførte duplikater — det er derfor ikke fikset
    her. Flagget som et konsolideringspunkt for Phase 5, samme behandling
    som DIFF_-kolonne-divergensen fikk i 02-05-SUMMARY.md.
    """
    år = _dt.now().year
    måned = _dt.now().month
    if måned >= 10:
        return f"{år}-{str(år + 1)[-2:]}"
    else:
        return f"{år - 1}-{str(år)[-2:]}"


def hent_spillerdata(season_type, sesong, last_n=0):
    """Henter spillerdata for gitt season_type/sesong. Returnerer tom DataFrame ved feil."""
    try:
        df = leaguedashplayerstats.LeagueDashPlayerStats(
            season=sesong,
            season_type_all_star=season_type,
            last_n_games=last_n
        ).get_data_frames()[0]
        time.sleep(1.0)  # Rate limiting
        return df
    except Exception as e:
        print(f"  (Kunne ikke hente {season_type} data: {e})")
        return pd.DataFrame()


def hent_spillerstatistikk(sesong=None):
    """
    Henter spillerstatistikk for hele NBA: siste 3 kamper og sesongsnitt,
    for Regular Season og Playoffs. Gjør de fire nba_api-kallene.

    'sesong' er None som standard, som betyr "bruk gjeldende_sesong()".
    Dette keyword-injeksjonspunktet er hele grunnen til at
    filtrer_bets_for_skader er testbar uten nettverk.

    Returnerer (siste3, sesong_snitt).
    """
    if sesong is None:
        sesong = gjeldende_sesong()

    print("Henter spillerstatistikk fra NBA (siste 3 kamper – Regular Season)...")
    siste3_reg = hent_spillerdata("Regular Season", sesong, last_n=3)
    print(f"  Hentet data for {len(siste3_reg)} spillere (Regular Season)")

    print("Henter spillerstatistikk fra NBA (siste 3 kamper – Playoffs)...")
    siste3_play = hent_spillerdata("Playoffs", sesong, last_n=3)
    print(f"  Hentet data for {len(siste3_play)} spillere (Playoffs)")

    # Slå sammen: behold Playoffs-data der det finnes, ellers Regular Season
    if not siste3_play.empty and not siste3_reg.empty:
        siste3 = pd.concat([siste3_play, siste3_reg]).drop_duplicates(
            subset=["PLAYER_ID"], keep="first"
        ).reset_index(drop=True)
    elif not siste3_play.empty:
        siste3 = siste3_play
    else:
        siste3 = siste3_reg
    print(f"  Totalt {len(siste3)} unike spillere etter sammenslåing\n")

    print("Henter sesongsnitt (for å identifisere toppspillere – Regular Season)...")
    sesong_reg = hent_spillerdata("Regular Season", sesong, last_n=0)
    print("Henter sesongsnitt (Playoffs)...")
    sesong_play = hent_spillerdata("Playoffs", sesong, last_n=0)

    # For sesongsnitt: summer minutter fra begge (Regular + Playoffs)
    if not sesong_play.empty and not sesong_reg.empty:
        sesong_snitt = pd.concat([sesong_play, sesong_reg]).groupby("PLAYER_ID", as_index=False).agg(
            PLAYER_NAME=("PLAYER_NAME", "first"),
            TEAM_ID=("TEAM_ID", "first"),
            MIN=("MIN", "sum")
        )
    elif not sesong_play.empty:
        sesong_snitt = sesong_play
    else:
        sesong_snitt = sesong_reg
    print(f"  Totalt {len(sesong_snitt)} unike spillere i sesongsnitt\n")

    return siste3, sesong_snitt


def hent_toppspillere_for_lag(sesong_snitt, team_id, antall=ANTALL_TOPPSPILLERE):
    """Finner de 'antall' spillerne med høyest sesongsnitt-minutter for et gitt lag."""
    lag_spillere = sesong_snitt[
        (sesong_snitt["TEAM_ID"] == team_id) &
        (sesong_snitt["MIN"] >= MIN_MINUTTER)
    ].sort_values("MIN", ascending=False).head(antall)
    return lag_spillere[["PLAYER_ID", "PLAYER_NAME", "MIN"]].to_dict("records")


def sjekk_spiller(siste3, spiller_id, spiller_navn, sesong_min):
    """
    Sjekker om spilleren er i siste-3-kamper-datasettet med
    et fornuftig antall minutter.
    """
    siste = siste3[siste3["PLAYER_ID"] == spiller_id]

    if siste.empty or siste["GP"].iloc[0] == 0:
        return False, f"{spiller_navn} ({sesong_min:.0f} min/kamp) – 0 kamper siste 3"

    gp = siste["GP"].iloc[0]
    min_snitt = siste["MIN"].iloc[0]

    if gp < 2 or min_snitt < 10:
        return False, f"{spiller_navn} ({sesong_min:.0f} min/kamp) – kun {gp} kamp(er), {min_snitt:.0f} min"

    return True, f"{spiller_navn} ({sesong_min:.0f} min/kamp) – {gp} kamper, {min_snitt:.0f} min"


def sjekk_lag_helse(siste3, sesong_snitt, team_id, lagnavn):
    """Sjekker et lags topp-N-spillere mot siste3-datasettet og returnerer en helsestatus-dict."""
    toppspillere = hent_toppspillere_for_lag(sesong_snitt, team_id, ANTALL_TOPPSPILLERE)

    resultat = {
        "lagnavn": lagnavn,
        "tilgjengelig": True,
        "advarsler": []
    }

    print(f"  {lagnavn}:")
    for sp in toppspillere:
        ok, melding = sjekk_spiller(siste3, sp["PLAYER_ID"], sp["PLAYER_NAME"], sp["MIN"])
        ikon = "✅" if ok else "⚠️ "
        print(f"    {ikon} {melding}")
        if not ok:
            resultat["tilgjengelig"] = False
            resultat["advarsler"].append(melding)

    if not toppspillere:
        print(f"    (Ingen spillere med >{MIN_MINUTTER} min/kamp funnet)")

    return resultat


def filtrer_bets_for_skader(value_df, siste3=None, sesong_snitt=None):
    """
    Kjører skadefilteret over value_df og returnerer en DataFrame med
    Skadestatus/Skadeinfo-kolonner lagt til.

    Injiser siste3/sesong_snitt (f.eks. fra tester) for å unngå
    nettverkskall; hvis enten er None hentes begge ferskt via
    hent_spillerstatistikk().
    """
    if siste3 is None or sesong_snitt is None:
        siste3, sesong_snitt = hent_spillerstatistikk()

    cache = {}
    filtrerte_bets = []

    for _, rad in value_df.iterrows():
        kamp = rad["Kamp"]
        bet = rad["Bet"]

        deler = kamp.split(" vs ")
        hjemme_navn = deler[0].strip()
        borte_navn = deler[1].strip()

        print(f"\n{'─'*50}")
        print(f"Kamp: {kamp}")
        print(f"Bet:  {bet}")

        advarsler = []

        for lagnavn in [hjemme_navn, borte_navn]:
            if lagnavn in cache:
                status = cache[lagnavn]
            else:
                # NB: teams.finn_lag_id() matcher også på forkortelse (abbreviation),
                # noe denne filens gamle full_name/nickname-only-oppslag ikke gjorde.
                # Dette utvider treffoverflaten (flere navn matcher), det snevrer
                # den aldri inn — en bevisst, dokumentert forening, ikke en
                # regresjon. Se 02-04-SUMMARY.md.
                team_id = finn_lag_id(lagnavn)

                if not team_id:
                    print(f"  ⚠️  Finner ikke team-ID for {lagnavn}")
                    continue

                status = sjekk_lag_helse(siste3, sesong_snitt, team_id, lagnavn)
                cache[lagnavn] = status

            for advarsel in status["advarsler"]:
                advarsler.append(f"{lagnavn}: {advarsel}")

        bet_rad = rad.to_dict()
        if advarsler:
            bet_rad["Skadestatus"] = "⚠️  USIKKER"
            bet_rad["Skadeinfo"] = " | ".join(advarsler)
            print(f"  → BET FLAGGET SOM USIKKER")
            for a in advarsler:
                print(f"     ⚠️  {a}")
        else:
            bet_rad["Skadestatus"] = "✅ OK"
            bet_rad["Skadeinfo"] = "Alle nøkkelspillere spilte siste 3 kamper"
            print(f"  → ✅ Alle nøkkelspillere tilgjengelige")

        filtrerte_bets.append(bet_rad)

    return pd.DataFrame(filtrerte_bets)


def skriv_skadefilter_csv(resultat_df, sti="value_bets_med_skadefilter.csv"):
    """Skriver skadefilter-resultatet til CSV og bekrefter med en print."""
    resultat_df.to_csv(sti, index=False)
    print(f"\nResultat lagret til '{sti}'")


# ---------------------------------------------------------------------
# As-of-vei (plan 05-06, Fase 5s walk-forward-backtest)
#
# Alt under her er additivt og parallelt til funksjonene over -- ingen av
# de eksisterende live-funksjonene (gjeldende_sesong, hent_spillerdata,
# hent_spillerstatistikk, hent_toppspillere_for_lag, sjekk_spiller,
# sjekk_lag_helse, filtrer_bets_for_skader, skriv_skadefilter_csv) er
# endret. 06_bot.py og 05_skadefilter.py trenger dem byte-identiske.
#
# Denne modulen importerer bevisst IKKE spillerlogg -- DataFramen
# injiseres alltid av kalleren (backtest.py i plan 05-07), slik at
# avhengighetsretningen forblir backtest -> {spillerlogg, skadefilter}
# og live-importgrafen 06_bot.py bruker er uendret.
# ---------------------------------------------------------------------


def sesong_grenser_for_dato(dato):
    """
    Speiler gjeldende_sesong()s år/måned>=10-logikk, men tar datoen som
    PARAMETER i stedet for å lese systemklokken -- denne parameteriseringen
    ER as-of-fiksen. En backtest som i stedet kalte gjeldende_sesong() ville
    stille scope hver historiske dato til den ekte, nåværende sesongen.

    Godtar en "YYYY-MM-DD"-streng eller et pd.Timestamp. Returnerer
    (sesong_start, sesong_slutt) som "YYYY-10-01"-strenger, der
    sesong_slutt er EKSKLUSIV.
    """
    ts = pd.Timestamp(dato)
    if ts.month >= 10:
        return f"{ts.year}-10-01", f"{ts.year + 1}-10-01"
    return f"{ts.year - 1}-10-01", f"{ts.year}-10-01"


def valider_spillerlogg(spillerlogg_df):
    """
    Ren vaktfunksjon -- kaster ValueError ved brudd i stedet for å hoppe
    over og logge, i motsetning til resten av modulen. En manglende
    kolonne eller en datetime-typet GAME_DATE gjør at nedstrøms-filteret
    ikke matcher noe, som leses som "ingen nøkkelspillere funnet" og lar
    ethvert lag passere ubetinget -- en usynlig oppadgående ROI-bias
    fremfor en synlig feil. En tom, men korrekt kolonneskjema-rammer er
    lovlig og skal passere.
    """
    manglende = [k for k in SPILLERLOGG_KOLONNER if k not in spillerlogg_df.columns]
    if manglende:
        raise ValueError(f"spillerlogg_df mangler påkrevde kolonner: {manglende}")

    if pd.api.types.is_datetime64_any_dtype(spillerlogg_df["GAME_DATE"]):
        raise ValueError(
            "GAME_DATE er datetime-typet, forventet YYYY-MM-DD-streng. "
            "Last spillerloggen via spillerlogg.les_spillerlogg(), som tvinger dtype=str."
        )


def hent_sesonglogg_som_of(spillerlogg_df, team_id, as_of_dato):
    """
    Det ENESTE as-of-sjekkpunktet i denne modulen. Strengt < på
    as_of_dato, ALDRI <= -- en kamp spilt på beslutningsdatoen er ikke
    kjent når betten legges, samme regel features.py følger og
    tests/test_parity.py::test_grenserad_paa_as_of_er_ekskludert allerede
    vokter der. sesong_slutt er bevisst ubrukt som øvre grense fordi
    as_of_dato alltid er den strammeste grensen innenfor sin egen sesong.
    Enhver as-of-filtrering i denne modulen skal rute gjennom denne ene
    funksjonen, slik at lekkasjegrensen bor på nøyaktig ett sted.
    """
    valider_spillerlogg(spillerlogg_df)
    as_of_dato = pd.Timestamp(as_of_dato).strftime("%Y-%m-%d")
    sesong_start, sesong_slutt = sesong_grenser_for_dato(as_of_dato)

    rader = spillerlogg_df[
        (spillerlogg_df["TEAM_ID"] == team_id)
        & (spillerlogg_df["GAME_DATE"] >= sesong_start)
        & (spillerlogg_df["GAME_DATE"] < as_of_dato)
    ]
    return rader.sort_values("GAME_DATE").reset_index(drop=True)


def hent_toppspillere_som_of(sesong_logg, antall=ANTALL_TOPPSPILLERE):
    """
    As-of-analogen til hent_toppspillere_for_lag. Den ene bevisste
    forskjellen fra live-veien: dette er et sesong-til-dato-snitt, ikke
    et fullsesong-snitt, fordi fullsesong-tallet ikke er kjent per
    as_of_dato. Returnerer samme record-form som hent_toppspillere_for_lag
    (PLAYER_ID, PLAYER_NAME, MIN), slik at sjekk_spiller konsumerer den
    uendret. Tom liste for en tom input-ramme, ikke en exception.
    """
    if sesong_logg.empty:
        return []

    snitt = sesong_logg.groupby("PLAYER_ID", as_index=False).agg(
        MIN=("MIN", "mean"),
        PLAYER_NAME=("PLAYER_NAME", "first"),
    )
    topp = snitt[snitt["MIN"] >= MIN_MINUTTER].sort_values("MIN", ascending=False).head(antall)
    return topp[["PLAYER_ID", "PLAYER_NAME", "MIN"]].to_dict("records")


def bygg_siste3_som_of(sesong_logg, antall_kamper=SISTE_N_KAMPER):
    """
    Adapteren som lar sjekk_spiller gjenbrukes uendret. Vinduet er
    LAGETS siste N kampdatoer (ikke spillerens egne siste N opptredener),
    fordi det er nøyaktig det live last_n_games=3-spørringen måler, og
    den eneste definisjonen der en skadet spiller kan registreres som
    fraværende. Kun MIN > 0-rader telles, fordi en null-minutt-rad er et
    DNP og å telle den som en spilt kamp ville skape falsk trygghet --
    samme konservative retning plan 05-05 valgte da null MIN ble tvunget
    til 0.0. En spiller som ikke opptrer i noen av vindusrader er ganske
    enkelt fraværende fra resultatet, som sjekk_spiller allerede
    rapporterer som "0 kamper siste 3".
    """
    kolonner = ["PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "MIN", "GP"]
    if sesong_logg.empty:
        return pd.DataFrame(columns=kolonner)

    siste_datoer = sorted(sesong_logg["GAME_DATE"].unique())[-antall_kamper:]
    vindu = sesong_logg[
        sesong_logg["GAME_DATE"].isin(siste_datoer) & (sesong_logg["MIN"] > 0)
    ]
    if vindu.empty:
        return pd.DataFrame(columns=kolonner)

    siste3 = vindu.groupby("PLAYER_ID", as_index=False).agg(
        PLAYER_NAME=("PLAYER_NAME", "first"),
        TEAM_ID=("TEAM_ID", "first"),
        MIN=("MIN", "mean"),
        GP=("MIN", "count"),
    )
    return siste3[kolonner]


def sjekk_lag_helse_som_of(spillerlogg_df, team_id, lagnavn, as_of_dato, antall=ANTALL_TOPPSPILLERE, skriv_ut=False):
    """
    Inngangspunktet plan 05-07 kaller. Strukturelt identisk med
    sjekk_lag_helse sin løkke, men datakilden er spillerlogg_df
    (injisert, aldri hentet via nettverk) i stedet for live
    siste3/sesong_snitt.

    Returnerer en dict med samme første tre nøkler som sjekk_lag_helse
    (lagnavn, tilgjengelig, advarsler) slik at backtest.py kan behandle
    live- og as-of-resultater likt, pluss to additive diagnostikk-nøkler:
    antall_toppspillere og antall_kamprader. Et lag uten spillerlogg-
    dekning gir null toppspillere og dermed tilgjengelig=True vacuously,
    akkurat som live-veien når ingen klarer MIN_MINUTTER -- tellerne lar
    backtest.py rapportere hvor mange skadesjekker som kjørte på tomt
    datagrunnlag i kjøre-manifestet i stedet for å absorbere dem stille
    som friske.

    skriv_ut er False som standard fordi denne kjører omtrent to ganger
    per kampdato over ~480 datoer i walk-forward-løkken; live-veien
    printer fordi den kjører én gang, interaktivt, per dag.
    """
    sesong_logg = hent_sesonglogg_som_of(spillerlogg_df, team_id, as_of_dato)
    toppspillere = hent_toppspillere_som_of(sesong_logg, antall)
    siste3 = bygg_siste3_som_of(sesong_logg)

    resultat = {
        "lagnavn": lagnavn,
        "tilgjengelig": True,
        "advarsler": [],
        "antall_toppspillere": len(toppspillere),
        "antall_kamprader": len(sesong_logg),
    }

    if skriv_ut:
        print(f"  {lagnavn}:")
    for sp in toppspillere:
        ok, melding = sjekk_spiller(siste3, sp["PLAYER_ID"], sp["PLAYER_NAME"], sp["MIN"])
        if skriv_ut:
            ikon = "✅" if ok else "⚠️ "
            print(f"    {ikon} {melding}")
        if not ok:
            resultat["tilgjengelig"] = False
            resultat["advarsler"].append(melding)

    return resultat
