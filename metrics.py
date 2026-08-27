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
