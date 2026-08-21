"""
Delt strategi-kjerne for NBA betting-pipeline.

Rene funksjoner for vig-fjerning, value/EV-beregning, halvt Kelly-kriteriet
og bet-dedup-nøkler — ingen I/O, ingen global tilstand. Importeres i dag av
04_value_detector.py og 06_bot.py, og skal senere importeres identisk av
Phase 5s backtest, slik at live-veien og backtest-veien aldri kan
beregne value/innsats forskjellig.

Modulen importerer bevisst INGENTING fra prosjektet (verken config.py eller
pandas) — konfigurasjonsverdier kommer inn som parametre til funksjonene.
Dette holder modulen fritt testbar med kant-verdier og import-syklus-fri.
"""


def fjern_vigorish(odds_hjemme, odds_borte):
    """
    Normaliserer implisitte sannsynligheter fra odds til å summere 100%.

    Bookmakerens rå implisitte sannsynligheter (1/odds) summerer til over
    100% pga. marginen ("vigorish") bookmakeren legger på. Å fjerne denne
    marginen er det som gjør at "value" betyr genuin modell-edge, ikke
    bare bookmakerens egen margin gjenoppdaget som falsk fordel.
    """
    impl_hjemme = 1 / odds_hjemme
    impl_borte  = 1 / odds_borte

    total = impl_hjemme + impl_borte
    impl_hjemme /= total
    impl_borte  /= total

    return impl_hjemme, impl_borte


def beregn_value_og_ev(modell_prob, odds, impl_prob):
    """
    VALUE = modellens sannsynlighet minus bookmakerens (vig-frie) implisitte.
    EV = (modell_prob * odds) - 1. Positiv EV betyr lønnsomt bet på sikt.

    NB: impl_prob må være den vig-frie sannsynligheten fra fjern_vigorish(),
    ikke en rå 1/odds — ellers blandes bookmakerens margin inn i value-tallet.
    """
    value = modell_prob - impl_prob
    ev    = (modell_prob * odds) - 1
    return value, ev


def beregn_innsats(saldo, modell_prob, odds, kelly_fraksjon, min_innsats, max_innsats):
    """
    Halvt Kelly-kriteriet:
      f* = (b*p - q) / b   der b = odds-1, p = modellsannsynlighet, q = 1-p
      innsats = saldo * f* * kelly_fraksjon

    Halvt Kelly gir lavere varians enn fullt Kelly, på bekostning av
    litt lavere forventet vekst. Anbefaltes bredt i sportsbetting.

    NB: min-klemmingen løfter selv en liten positiv edge OPP til
    min_innsats — overraskende, men bevisst og bevart fra originalen.
    """
    b = odds - 1.0          # netto gevinst per krone satset
    p = modell_prob
    q = 1.0 - p

    kelly = (b * p - q) / b

    if kelly <= 0:
        return 0.0          # Negativt Kelly = ingen edge, ikke bett

    innsats = saldo * kelly * kelly_fraksjon
    innsats = max(min_innsats, min(max_innsats, innsats))
    return round(innsats, 2)


def finn_bet_nokkel(kamp, bet, kamp_dato):
    """
    Bygger dedup-nøkkelen som hindrer dobbel-betting på samme fysiske kamp.
    Nøkkelen er keyet på kampens egen dato, ikke botens kjøredato, slik at
    samme kamp aldri bettes to ganger uansett hvilken dag boten kjørte.
    """
    return (kamp, bet, kamp_dato)


def bygg_bet_nokler(bets):
    """
    Bygger settet av dedup-nøkler fra en liste med bet-record-dicts.

    Faller tilbake til b["dato"] (botens kjøredato) når b["kamp_dato"]
    mangler — bet-records skrevet før 2026-08-19-fiksen har ikke noe
    kamp_dato-felt i det hele tatt, og dette fallbacket er det som
    holder de gamle (legacy) records med i dedup-settet.
    """
    return {
        (b["kamp"], b["bet"], b.get("kamp_dato") or b["dato"]) for b in bets
    }


def er_duplikat(nokkel, eksisterende_nokler):
    """Ren predikat-funksjon over dedup-settet — testbar uten DataFrame/I/O."""
    return nokkel in eksisterende_nokler
