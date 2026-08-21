"""
Tester for teams.py — den ene lag-navn-resolveren som erstattet fire kopier.

En feil her betyr at boten bytter feil lag i en value/EV-beregning og setter
penger (om enn virtuelle, foreløpig) på feil resultat. Testene kaller kun
den ekte teams.finn_lag() — ingen egen oppslagslogikk gjenoppfinnes her
(RESEARCH.md "don't write a fifth implementation just for tests").
"""

from nba_api.stats.static import teams as nba_teams

from teams import LAG_OPPSLAG, finn_lag, finn_lag_id


def test_alle_lag_loses_paa_alle_tre_nokkeltyper():
    """
    For hvert av de 30 NBA-lagene skal full_name, nickname og abbreviation
    alle løse til samme lag-id. Dette er 90 assertions som beviser at ingen
    av de 90 nøklene i LAG_OPPSLAG kolliderer med eller overskygger en annen.
    """
    for lag in nba_teams.get_teams():
        for navn in (lag["full_name"], lag["nickname"], lag["abbreviation"]):
            funnet = finn_lag(navn)
            assert funnet is not None, f"Fant ikke lag for {navn!r}"
            assert funnet["id"] == lag["id"], (
                f"{navn!r} løste til feil lag: forventet {lag['full_name']}, "
                f"fikk {funnet['full_name']}"
            )


def test_oppslag_er_case_insensitivt():
    """Store/små bokstaver skal ikke påvirke oppslaget — Odds API og nba_api er ikke konsistente på dette."""
    stor = finn_lag("BOSTON CELTICS")
    liten = finn_lag("boston celtics")
    normal = finn_lag("Boston Celtics")
    assert stor is not None and liten is not None and normal is not None
    assert stor["id"] == liten["id"] == normal["id"]


def test_odds_api_navn_loses():
    """
    De faktiske full_name-strengene The Odds API sender for live-veien.
    Dette er de vriene tilfellene (LA Clippers vs. Los Angeles Clippers,
    siffer i 76ers) der en resolver som stille matcher feil lag koster
    ekte penger.
    """
    # NB: nba_api's egen full_name for Clippers er "Los Angeles Clippers" —
    # Odds API sender "LA Clippers", som løses via nickname-substreng-fallback
    # ("clippers" i "la clippers") til riktig lag, ikke via eksakt full_name-match.
    forventet = {
        "Los Angeles Lakers": "Los Angeles Lakers",
        "LA Clippers": "Los Angeles Clippers",
        "Golden State Warriors": "Golden State Warriors",
        "Portland Trail Blazers": "Portland Trail Blazers",
        "Oklahoma City Thunder": "Oklahoma City Thunder",
        "Philadelphia 76ers": "Philadelphia 76ers",
    }
    for odds_api_navn, forventet_full_name in forventet.items():
        lag = finn_lag(odds_api_navn)
        assert lag is not None, f"Fant ikke lag for Odds-API-navnet {odds_api_navn!r}"
        assert lag["full_name"] == forventet_full_name


def test_ukjent_navn_gir_none():
    """
    Ukjente navn skal returnere None uten å kaste exception — kallerne skip-and-log'er på dette.

    NB: en tom streng testes IKKE her. Substreng-fallbacket ("nøkkel in navn or
    navn in nøkkel", kopiert verbatim fra 06_bot.py sin opprinnelige finn_lag()-
    closure) gjør at "" trivielt er en substreng av ethvert lagnavn, så
    finn_lag("") matcher det første laget i oppslagsrekkefølgen i stedet for
    å returnere None. Dette er eksisterende, uendret oppførsel fra før
    ekstraheringen (samme closure, samme logikk) — ikke en regresjon denne
    planen introduserer, og D-07/Pitfall 1 forbyr å endre logikken for å
    "fikse" dette under en ren ekstrahering.
    """
    assert finn_lag("Manchester United") is None


def test_finn_lag_id_speiler_finn_lag():
    """finn_lag_id() skal returnere samme id som finn_lag(navn)['id'], og None for ukjente navn."""
    for navn in ("Boston Celtics", "Lakers", "GSW".lower()):
        forventet = finn_lag(navn)
        assert finn_lag_id(navn) == (forventet["id"] if forventet else None)
    assert finn_lag_id("Manchester United") is None


def test_substring_fallback_virker():
    """
    Bet-etiketter med ekstra tekst rundt lagnavnet (formen 06_bot.py sender når
    en betlabel bærer med seg mer enn selve lagnavnet) skal fortsatt løses
    via substreng-fallbacket.
    """
    lag = finn_lag("Lakers (hjemme)")
    assert lag is not None
    assert lag["full_name"] == "Los Angeles Lakers"
