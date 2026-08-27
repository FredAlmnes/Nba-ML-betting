"""
Ren rapporteringsmodul for backtest-ledgeren (BT-04/BT-06).

Denne modulen eier hele rapporterings-aritmetikken for et fullført backtest-
løp: ROI, vinnrate, maks drawdown, konfidensintervaller (bootstrap for ROI,
Wilson-score for vinnrate) og CLV (Closing Line Value). Den gjør INGEN I/O
og holder INGEN tilstand — alt kommer inn som funksjonsparametre, akkurat
som strategy.py. Importeres av backtest.py (plan 05-08/05-09) og av
08_kjor_backtest.py (plan 05-10) for å fylle manifest.json.

Modulen har bevisst kun to modulnivå-imports: numpy og
strategy.fjern_vigorish. Sistnevnte er et unntak fra strategy.py sin egen
regel om å ikke importere noe prosjekt-spesifikt — men unntaket er bevisst:
prosjektet skal aldri ha to implementasjoner av vig-fjerning. Å gjenbruke
strategy.fjern_vigorish her (i stedet for å skrive en lokal 1/odds-
normalisering for CLV) er det som holder value-tallet og CLV-tallet
konsistente med hverandre og med live-koden.
"""

import numpy as np
from strategy import fjern_vigorish


# ---------------------------------------------------------------------
# Ledger-kjerne: profitt, ROI, vinnrate, maks drawdown (BT-04)
# ---------------------------------------------------------------------


def beregn_profitt(innsats, odds, vant):
    """
    Kanonisk per-bet oppgjørsformel — den eneste i repoet.

    Vunnet bet: gevinst er innsats * (odds - 1) (nettoprofitt, ikke
    totalutbetaling). Tapt bet: hele innsatsen er tapt. Rundes til 2
    desimaler for å matche strategy.beregn_innsats sin avrundingskonvensjon,
    slik at plan 05-08s oppgjørssteg og denne modulens ROI aldri kan komme
    i utakt med hverandre.
    """
    if vant:
        return round(innsats * (odds - 1.0), 2)
    return round(-innsats, 2)


def beregn_roi(profitter, innsatser):
    """
    ROI på omsetning (turnover) — sum(profitt) / sum(innsats) — IKKE på
    startkapital. Dette valget av nevner er det som gjør BT-04s "rapportert
    kun på det flaggede bet-utvalget" sant: ROI måler avkastning på det som
    faktisk ble satset, uavhengig av hvor stor bankrollen var.

    Returnerer 0.0 for en tom ledger eller null total innsats, i stedet for
    å kaste eller returnere NaN — en tom flagget-bet-delmengde skal fortsatt
    produsere en skrivbar manifest.
    """
    if len(profitter) == 0:
        return 0.0
    sum_innsats = sum(innsatser)
    if sum_innsats == 0:
        return 0.0
    return sum(profitter) / sum_innsats


def beregn_vinnrate(vant_flagg):
    """
    Returnerer (vinnrate, antall_vunnet, antall_totalt).

    Kalleren-kontrakt: kun AVGJORTE bets skal sendes inn her. Plan 05-08
    gjør oppgjør på hvert bet først (BT-02), og en "venter"-rad talt som
    tap ville undervurdert vinnraten. Tom sekvens gir (0.0, 0, 0), ikke en
    feil.
    """
    antall_totalt = len(vant_flagg)
    if antall_totalt == 0:
        return 0.0, 0, 0
    antall_vunnet = sum(1 for v in vant_flagg if v)
    return antall_vunnet / antall_totalt, antall_vunnet, antall_totalt


def beregn_maks_drawdown(profitter, startkapital):
    """
    Returnerer (maks_drawdown_kroner, maks_drawdown_andel).

    Bygger bankroll-kurven ved å kumulativt legge profitter til
    startkapital, og behandler startkapital selv som kurvens FØRSTE punkt
    (og dermed dens første topp). Sporer løpende topp og returnerer det
    STØRSTE fallet i kroner og det STØRSTE fallet som andel av toppen det
    falt fra.

    De to returverdiene beregnes uavhengig av hverandre og kan i prinsippet
    stamme fra to ulike drawdown-episoder — kronetallet svarer på "verste
    absolutte tap fra en topp", andelstallet svarer på "verste
    prosentvise tap fra en topp", og å slå dem sammen til ett tall ville
    feilrapportert det ene av de to.

    Guard mot en ikke-positiv topp: bidrar med 0.0 til andelen i stedet for
    å dele på null eller negativt tall. Tom ledger gir (0.0, 0.0).
    """
    if len(profitter) == 0:
        return 0.0, 0.0

    kurve = [startkapital]
    løpende = startkapital
    for p in profitter:
        løpende += p
        kurve.append(løpende)

    topp = kurve[0]
    maks_dd_kroner = 0.0
    maks_dd_andel = 0.0
    for verdi in kurve:
        if verdi > topp:
            topp = verdi
        fall = topp - verdi
        if fall > maks_dd_kroner:
            maks_dd_kroner = fall
        if topp > 0:
            andel = fall / topp
            if andel > maks_dd_andel:
                maks_dd_andel = andel

    return round(float(maks_dd_kroner), 2), float(maks_dd_andel)


# ---------------------------------------------------------------------
# Konfidensintervaller: bootstrap ROI + Wilson vinnrate (BT-04)
# ---------------------------------------------------------------------


def bootstrap_roi_ci(profitter, innsatser, n_resamples=1000, seed=42, konfidensnivaa=0.95):
    """
    Persentil-metode bootstrap-konfidensintervall for ROI.

    Tre poeng er avgjørende, ikke pynt:

    1. Det som resamples er individuelle BETS, ikke kamper og ikke datoer —
       et enkelt bet er enheten for uavhengig risiko her. Å resample kamper
       eller datoer ville implisitt antatt korrelasjon mellom bets på samme
       kamp/dato som ikke finnes i denne strategien (ett bet per kamp).

    2. Seeden er en fast standardverdi, ikke klokke-avledet, slik at en
       ny kjøring av samme manifest-konfigurasjon reproduserer et
       bit-identisk konfidensintervall. Seeden skrives selv inn i
       manifest.json (BT-05) for sporbarhet.

    3. Et bredt intervall på skalaen dette prosjektet forventer på
       trenings-/kalibreringsdelen (~190-360 bets) er det KORREKTE og
       forventede resultatet, og er nøyaktig grunnen til at BT-04 krever
       et konfidensintervall i det hele tatt — det er ikke en defekt som
       skal tunes bort.

    Kaster ValueError ved ulik lengde på profitter/innsatser — en
    lengdeforskjell betyr at ledgeren er korrupt, og å fortsette stille
    ville fabrikkert en ROI fra feiljusterte arrays.

    Returnerer (punktestimat, nedre, oevre) som rene Python-floats —
    np.percentile gir numpy.float64, og plan 05-08 serialiserer disse
    verdiene direkte inn i manifest.json via json.dumps, som feiler på
    numpy.float64.
    """
    profitter = np.asarray(profitter, dtype=float)
    innsatser = np.asarray(innsatser, dtype=float)

    if len(profitter) != len(innsatser):
        raise ValueError(
            "profitter og innsatser må ha samme lengde — ledgeren er korrupt"
        )

    if len(profitter) == 0:
        return 0.0, 0.0, 0.0

    # Punktestimatet kommer fra den ORIGINALE ledgeren, aldri fra
    # resample-fordelingens gjennomsnitt.
    punktestimat = float(profitter.sum() / innsatser.sum())

    rng = np.random.default_rng(seed)
    n = len(profitter)
    resample_roi = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        resample_roi[i] = profitter[idx].sum() / innsatser[idx].sum()

    halv_hale = 100 * (1 - konfidensnivaa) / 2
    nedre = np.percentile(resample_roi, halv_hale)
    oevre = np.percentile(resample_roi, 100 - halv_hale)

    return punktestimat, float(nedre), float(oevre)


def wilson_ci(antall_vunnet, antall_totalt, z=1.96):
    """
    Wilson score-intervall for en binomisk andel (vinnrate).

    Returnerer (p, nedre, oevre) som rene Python-floats, med nedre
    klemt til 0.0 og oevre til 1.0. Returnerer (0.0, 0.0, 0.0) når
    antall_totalt er null.

    z=1.96 er en hardkodet konstant for et 95%-intervall, ikke et
    norm.ppf-oppslag fra en ekstern statistikk-pakke — z-scoren for et
    fast konfidensnivå endrer seg aldri, og å hente inn en udeklarert
    avhengighet for én konstant er avhengighets-krypp, ikke rigor.

    Wilson brukes i stedet for en naiv normal-approksimasjon fordi den
    naive intervallformen produserer grenser utenfor [0, 1] ved dette
    utvalgs-nivået — 0/10-tilfellet i testene demonstrerer akkurat det
    Wilson fikser (en naiv 0 ± 0 kollapser til et intervall uten
    informasjon, mens Wilson gir en meningsfull øvre grense).
    """
    if antall_totalt == 0:
        return 0.0, 0.0, 0.0

    n = float(antall_totalt)
    p = antall_vunnet / n
    z2 = z * z

    senter = (p + z2 / (2 * n)) / (1 + z2 / n)
    halvbredde = (z / (1 + z2 / n)) * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5)

    nedre = max(0.0, senter - halvbredde)
    oevre = min(1.0, senter + halvbredde)

    return float(p), float(nedre), float(oevre)
