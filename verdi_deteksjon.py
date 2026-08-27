"""
Delt modul for value-deteksjon-beslutningslogikk.

Erstatter den gamle 04_value_detector.py, som utførte alt — lasting av
pickle-modellen, et nettverkskall mot The Odds API, henting av fersk
lagstatistikk fra nba_api og en CSV-skriving — på modul-nivå ved import.
Det gjorde filen umulig å importere trygt fra 06_bot.py (som derfor måtte
kjøre den som en egen underprosess i stedet — se plan 04-08, som fjerner dette).

Denne modulen gjør ingen nettverkskall, laster ingen pickle og skriver ingen
fil bare ved `import verdi_deteksjon` — alt skjer inne i funksjoner. Live-
oddsen hentes nå fra odds.hent_live_odds() (D-07) i stedet for det gamle
inline HTTP-kallet mot The Odds API, som er fjernet fra denne kodebasen.
Dette gjør beslutningslogikken testbar uten nettverk og importerbar i
prosess av 06_bot.py (plan 04-08).

04_value_detector.py er nå en tynn CLI-wrapper som importerer herfra.
"""

import pickle
import time
from datetime import datetime as _dt

import pandas as pd
from nba_api.stats.endpoints import teamgamelogs

import odds
from config import MAX_ODDS, MIN_ODDS, MIN_VALUE_TERSKEL
from features import bygg_feature_rad, snitt_fra_kamplogg
from modell_utils import KalibrertModell  # nødvendig for å laste pickle
from strategy import beregn_value_og_ev, fjern_vigorish
from teams import finn_lag_id

KOLONNER = ["Kamp", "KampDato", "Bet", "Odds", "Bookmaker", "Modell_prob",
            "Modell %", "Bookmaker %", "Value", "Forv. EV"]


def gjeldende_sesong():
    """
    Returnerer NBA-sesongen for inneværende dato, f.eks. '2025-26'.

    NB: denne funksjonen og gjeldende_sesong() i skadefilter.py (plan 04-02)
    er samme NBA-sesong-utledning, duplisert i to filer. Begge ekstraheres
    i denne fasen, men 04-CONTEXT.md skoper ikke en delt sesong-modul, og
    dette var aldri ett av Phase 2 D-03s fire oppførte duplikater — det er
    derfor ikke fikset her. Flagget som et konsolideringspunkt for Phase 5,
    samme behandling som DIFF_-kolonne-divergensen fikk i 02-05-SUMMARY.md.
    """
    år = _dt.now().year
    måned = _dt.now().month
    # NBA-sesongen starter i oktober – hvis vi er før oktober er vi i fjorårets sesong
    if måned >= 10:
        return f"{år}-{str(år + 1)[-2:]}"
    else:
        return f"{år - 1}-{str(år)[-2:]}"


def hent_siste_lagstats(team_id, antall_kamper=10, sesong=None):
    """Henter siste N kamper for et lag og beregner snittet."""
    if sesong is None:
        sesong = gjeldende_sesong()

    logs = teamgamelogs.TeamGameLogs(
        team_id_nullable=team_id,
        season_nullable=sesong,
        season_type_nullable="Regular Season"
    )
    df = logs.get_data_frames()[0].head(antall_kamper)
    time.sleep(0.5)  # Rate limiting

    if len(df) < 3:
        return None

    return snitt_fra_kamplogg(df)


def last_modell(sti="nba_modell.pkl"):
    """Laster den trente, kalibrerte modellen fra pickle. Returnerer (modell, feature_kolonner)."""
    with open(sti, "rb") as f:
        data = pickle.load(f)
    return data["modell"], data["feature_kolonner"]


def finn_value_bets(modell, feature_kolonner, kamper=None, api_nokkel=None, hent_lagstats=None):
    """
    Beregner modellens sannsynligheter mot dagens NBA-odds og flagger value bets.

    kamper: injiser en liste av kamp-dicts (Odds API-format) for testing;
        None (standard) betyr "hent ferskt via odds.hent_live_odds(api_nokkel)"
        — dette ER D-07: det gamle inline HTTP-kallet finnes ikke lenger i
        denne kodebasen.
    hent_lagstats: injiser en stub (f.eks. fra tester) for å unngå
        nettverkskall; None (standard) betyr "bruk denne modulens
        hent_siste_lagstats".

    Returnerer value_bets-listen.
    """
    if kamper is None:
        kamper = odds.hent_live_odds(api_nokkel)

    if hent_lagstats is None:
        hent_lagstats = hent_siste_lagstats

    value_bets = []

    for kamp in kamper:
        hjemme_navn = kamp["home_team"]
        borte_navn  = kamp["away_team"]
        kamp_tid    = kamp["commence_time"]

        # Finn lag-IDs. NB: resolusjonsrekkefølgen endres bevisst her — den gamle
        # heuristikken prøvde kallenavn (siste ord) først og hele navnet som
        # fallback; teams.finn_lag() prøver eksakt match (alle tre nøkkeltyper)
        # først og substreng-fallback etterpå. Begge løser de samme navnene
        # (bevist av test_odds_api_navn_loses i tests/test_teams.py), men
        # REKKEFØLGEN de prøver ting i er ulik — se 02-04-SUMMARY.md.
        hjemme_id = finn_lag_id(hjemme_navn)
        borte_id  = finn_lag_id(borte_navn)

        if not hjemme_id or not borte_id:
            print(f"  Kunne ikke finne lag-ID for: {hjemme_navn} vs {borte_navn}")
            continue

        # Hent statistikk
        hjemme_stats = hent_lagstats(hjemme_id)
        borte_stats  = hent_lagstats(borte_id)

        if not hjemme_stats or not borte_stats:
            continue

        # Bygg feature-rad for modellen
        feature_rad = bygg_feature_rad(hjemme_stats, borte_stats)

        # Filtrer til bare de feature-kolonnene modellen forventer
        X = pd.DataFrame([feature_rad])[feature_kolonner]

        # Modellens sannsynlighet for at hjemmelaget vinner
        modell_sann_hjemme = modell.predict_proba(X)[0][1]
        modell_sann_borte  = 1 - modell_sann_hjemme

        # Prisvalg lever bevisst ikke lenger her: odds.velg_beste_pris_per_utfall
        # er den samme funksjonen Fase 5-backtesten kaller (odds.hent_bet_time_pris),
        # så live og backtest aldri kan drifte til to forskjellige prisingsregler —
        # samme grunn som fjern_vigorish/beregn_value_og_ev ble flyttet til
        # strategy.py (se kommentaren rett under).
        beste_hjemme_odds, beste_borte_odds, beste_hjemme_book, beste_borte_book = (
            odds.velg_beste_pris_per_utfall(
                odds.prisrader_fra_kamp(kamp), hjemme_navn, borte_navn
            )
        )

        if beste_hjemme_odds is None or beste_borte_odds is None:
            continue

        # Vig-fri normalisering og value/EV-beregning bor nå i strategy.py, slik
        # at Phase 5-backtesten regner disse identisk med live-veien.
        impl_sann_hjemme, impl_sann_borte = fjern_vigorish(beste_hjemme_odds, beste_borte_odds)
        value_hjemme, ev_hjemme = beregn_value_og_ev(modell_sann_hjemme, beste_hjemme_odds, impl_sann_hjemme)
        value_borte,  ev_borte  = beregn_value_og_ev(modell_sann_borte,  beste_borte_odds,  impl_sann_borte)

        print(f"\n{hjemme_navn} vs {borte_navn}")
        print(f"  Modell:     Hjemme {modell_sann_hjemme:.1%}  |  Borte {modell_sann_borte:.1%}")
        print(f"  Bookmaker:  Hjemme {impl_sann_hjemme:.1%}  |  Borte {impl_sann_borte:.1%}")
        print(f"  Beste odds: Hjemme {beste_hjemme_odds} ({beste_hjemme_book}) | Borte {beste_borte_odds} ({beste_borte_book})")
        print(f"  Value:      Hjemme {value_hjemme:+.1%}  |  Borte {value_borte:+.1%}")
        print(f"  Forv. EV:   Hjemme {ev_hjemme:+.1%}  |  Borte {ev_borte:+.1%}")

        # Trekk ut faktisk kampdato fra Odds API (UTC → dato-streng)
        kamp_dato_str = kamp_tid[:10] if kamp_tid else str(_dt.now().date())

        # Flagg value bets
        if value_hjemme > MIN_VALUE_TERSKEL and MIN_ODDS <= beste_hjemme_odds <= MAX_ODDS:
            value_bets.append({
                "Kamp":         f"{hjemme_navn} vs {borte_navn}",
                "KampDato":     kamp_dato_str,
                "Bet":          f"Hjemme ({hjemme_navn})",
                "Odds":         beste_hjemme_odds,
                "Bookmaker":    beste_hjemme_book,
                "Modell_prob":  round(modell_sann_hjemme, 4),   # rå float til Kelly
                "Modell %":     f"{modell_sann_hjemme:.1%}",
                "Bookmaker %":  f"{impl_sann_hjemme:.1%}",
                "Value":        f"{value_hjemme:+.1%}",
                "Forv. EV":     f"{ev_hjemme:+.1%}"
            })

        if value_borte > MIN_VALUE_TERSKEL and MIN_ODDS <= beste_borte_odds <= MAX_ODDS:
            value_bets.append({
                "Kamp":         f"{hjemme_navn} vs {borte_navn}",
                "KampDato":     kamp_dato_str,
                "Bet":          f"Borte ({borte_navn})",
                "Odds":         beste_borte_odds,
                "Bookmaker":    beste_borte_book,
                "Modell_prob":  round(modell_sann_borte, 4),    # rå float til Kelly
                "Modell %":     f"{modell_sann_borte:.1%}",
                "Bookmaker %":  f"{impl_sann_borte:.1%}",
                "Value":        f"{value_borte:+.1%}",
                "Forv. EV":     f"{ev_borte:+.1%}"
            })

    return value_bets


def skriv_value_bets_csv(value_bets, sti="value_bets_idag.csv"):
    """
    Skriver value_bets til CSV.

    VIKTIG: skriv alltid til value_bets_idag.csv, også når vi ikke fant noen
    value bets (f.eks. NBA-sommerpause). Ellers ligger gårsdagens (eller forrige
    måneds!) fil igjen urørt, og 05/06 vil stille-gjenbruke gamle, allerede
    spilte kamper som om de var dagens anbefalinger.
    """
    if value_bets:
        value_df = pd.DataFrame(value_bets)
        print(value_df.to_string(index=False))
        value_df.to_csv(sti, index=False)
        print(f"\n{len(value_bets)} value bet(s) funnet og lagret til '{sti}'")
    else:
        print("Ingen value bets funnet i dag med gjeldende terskelverdier.")
        print(f"(Terskel: {MIN_VALUE_TERSKEL:.0%} value, odds mellom {MIN_ODDS}–{MAX_ODDS})")
        pd.DataFrame(columns=KOLONNER).to_csv(sti, index=False)
        print(f"'{sti}' tømt/oppdatert (ingen anbefalinger i dag).")
