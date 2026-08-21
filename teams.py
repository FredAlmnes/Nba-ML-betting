"""
Delt modul for lag-navn-oppslag.

Erstatter fire uavhengige implementasjoner: 04_value_detector.py (kallenavn-
først-så-fullt-navn-heuristikk), 05_skadefilter.py (kun full_name/nickname,
ingen forkortelse), 06_bot.py (finn_lag()-closure med substreng-fallback) og
debug_kamp.py (dict-comprehension-variant). Alle fire bygde sin egen kopi av
`teams.get_teams()`-oppslaget uavhengig av hverandre, med litt ulike nøkkel-
sett — nøyaktig den typen drift denne fasen finnes for å stoppe.

Dette er den eneste oppslags-modulen som skal importeres av både live-veien
(04/05/06) og en fremtidig Fase 5-backtest, slik at de aldri kan gjette
forskjellig hva et lag heter.

`finn_lag()` returnerer None for ukjente navn i stedet for å kaste en
exception — kallerne rundt om i pipelinen forventer dette (skip-and-log),
og denne modulen verken strammer inn eller løsner den kontrakten (ASVS V5).
"""

from nba_api.stats.static import teams as nba_teams


def bygg_lag_oppslag():
    """
    Bygger oppslagstabell: lowercase full_name/nickname/abbreviation -> full lag-info.

    nba_teams.get_teams() leser en pakket, statisk Python-liste — ingen
    nettverkskall, ingen rate-limit. Trygt å kalle ved import.
    """
    alle_lag = nba_teams.get_teams()
    oppslag = {}
    for lag in alle_lag:
        oppslag[lag["full_name"].lower()] = lag
        oppslag[lag["nickname"].lower()] = lag
        oppslag[lag["abbreviation"].lower()] = lag
    return oppslag


# Bygges én gang ved import — ingen nettverkskall (se docstring over).
LAG_OPPSLAG = bygg_lag_oppslag()


def finn_lag(navn):
    """
    Slår opp lag-info fra et navn (full_name, nickname, eller abbreviation).
    Faller tilbake til substreng-match hvis eksakt match ikke finnes.
    Returnerer lag-dict (id, full_name, abbreviation, nickname, ...) eller None.
    """
    navn = navn.lower()
    if navn in LAG_OPPSLAG:
        return LAG_OPPSLAG[navn]
    for nøkkel, info in LAG_OPPSLAG.items():
        if nøkkel in navn or navn in nøkkel:
            return info
    return None


def finn_lag_id(navn):
    """Bekvemmelighetsfunksjon: samme som finn_lag(navn), men returnerer bare id-en."""
    lag = finn_lag(navn)
    return lag["id"] if lag else None
