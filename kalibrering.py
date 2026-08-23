"""
Delt modul for kronologiske tren/kalibrer/test-grenser.

Denne modulen eier de kronologiske grensene som 03_tren_modell.py bruker
for å dele opp kampdataene i tre ikke-overlappende tidsvinduer: tren
(alt før kalibrer-vinduet), kalibrer (brukt til å fitte isotonic
regression-kalibratoren) og test (den nyeste halvdelen, brukt kun til
sluttevaluering). Modulen holdes ren (ingen I/O, ingen prints) så den
kan enhetstestes uten å kjøre hele treningsskriptet.
"""

import pandas as pd


def del_kronologisk_3veis(df, dato_kolonne="GAME_DATE_HJEMME",
                          tren_cutoff_mnd=2, kalibrer_cutoff_mnd=1):
    """
    Deler df kronologisk i tre bolker basert på dato_kolonne.

    Bisekterer det EKSISTERENDE tren_cutoff_mnd-holdout-vinduet i to:
    den eldste halvdelen av holdout-vinduet blir kalibrer, den nyeste
    halvdelen blir test. tren_cutoff_mnd utvides ikke.

    Returnerer tre boolske masker (tren, kalibrer, test) som aldri
    overlapper og til sammen dekker alle rader.
    """
    if kalibrer_cutoff_mnd >= tren_cutoff_mnd:
        raise ValueError(
            "kalibrer_cutoff_mnd må være mindre enn tren_cutoff_mnd, "
            "ellers blir kalibrer-vinduet tomt eller invertert "
            f"(fikk kalibrer_cutoff_mnd={kalibrer_cutoff_mnd}, "
            f"tren_cutoff_mnd={tren_cutoff_mnd})"
        )

    maks_dato = df[dato_kolonne].max()
    fra_dato  = maks_dato - pd.DateOffset(months=tren_cutoff_mnd)
    # midt_dato deler holdout-vinduet i kalibrer (eldst) og test (nyest) –
    # test er den nyeste halvdelen og skal ALDRI brukes til fitting (D-03/D-04).
    midt_dato = maks_dato - pd.DateOffset(months=kalibrer_cutoff_mnd)

    tren_mask     = df[dato_kolonne] < fra_dato
    kalibrer_mask = (df[dato_kolonne] >= fra_dato) & (df[dato_kolonne] < midt_dato)
    test_mask     = df[dato_kolonne] >= midt_dato

    return tren_mask, kalibrer_mask, test_mask
