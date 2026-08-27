"""
Delt modul for trening, kalibrering, lagring og lasting av prediksjonsmodellen.

Denne modulen eier ALLE .fit()-kall i kodebasen — både XGBoost sin
modell.fit() og isotonic regression sin kalibrerer.fit(). Importørene er
03_tren_modell.py (engangs-treningen, as_of=None) og backtest.py (Phase 5s
walk-forward-løkke, as_of=<dato> per gjenopptreningspunkt). Modulen leser
med vilje IKKE nba_features.csv eller config.py selv — kalleren gir alltid
DataFrame-en inn, slik at samme funksjon kan brukes både på hele historikken
og på et as_of-filtrert utsnitt uten noen fil-avhengighet.

Navnekollisjon å være obs på: denne modulen heter "model", mens den lokale
variabelen for en fittet XGBoost-estimator historisk heter "modell" — og
modell_utils.py er en TREDJE, annerledes ting: den eier kun
KalibrertModell-wrapperklassen som kombinerer XGBoost-sannsynligheter med
en fittet isotonic-kalibrerer bak et predict_proba-grensesnitt. model.py
importerer og bruker KalibrertModell, det reimplementerer den aldri.

Engangs-splitten (as_of=None) delegerer verbatim til den allerede testede
kalibrering.del_kronologisk_3veis, slik at fase 3s CALIB-01-lekkasjefiks
(disjunkte tren/kalibrer/test-bolker) overlever flyttingen uendret.
as_of-splitten (walk-forward) bruker derimot et ekspanderende vindu med en
ANDEL av vinduet til kalibrering — ikke et fast antall måneder — og har
ingen intern testbolk. Se del_for_trening()s docstring for hvorfor.
"""

import pickle

import pandas as pd
import xgboost as xgb
from sklearn.isotonic import IsotonicRegression

from kalibrering import del_kronologisk_3veis
from modell_utils import KalibrertModell

DATO_KOLONNE = "GAME_DATE_HJEMME"  # Kolonnen alle kronologiske splitter sorterer/filtrerer på
MAAL_KOLONNE = "HJEMME_VANT"       # Det binære målet: vant hjemmelaget kampen?
KALIBRER_ANDEL = 0.15              # Andel av as_of-vinduet (nyest først) som går til kalibrering
FEATURE_PREFIKSER = ("DIFF_", "HJEMME_RULL_", "BORTE_RULL_")  # Prefiksene som definerer feature-settet


def velg_feature_kolonner(df):
    """
    Returnerer kolonnene i df som starter med et av FEATURE_PREFIKSER, i
    df.columns sin rekkefølge. Rekkefølgen er avgjørende — den er det
    trente feature-skjemaet lagret i nba_modell.pkl og teksten i
    03_tren_modell.py sin "Features brukt:"-utskrift.
    """
    return [k for k in df.columns if k.startswith(FEATURE_PREFIKSER)]


def del_for_trening(df, as_of=None, kalibrer_andel=KALIBRER_ANDEL, dato_kolonne=DATO_KOLONNE):
    """
    Deler df kronologisk i tre boolske masker (tren, kalibrer, test),
    indeks-justert mot df slik at kalleren kan skrive X[tren_mask] direkte.

    To grener:

    as_of=None (engangs-splitten, brukt av 03_tren_modell.py): delegerer
    verbatim til kalibrering.del_kronologisk_3veis, som bisekterer det
    eksisterende holdout-vinduet i tren/kalibrer/test. kalibrer_andel
    brukes IKKE i denne grenen — del_kronologisk_3veis har sine egne
    tren_cutoff_mnd/kalibrer_cutoff_mnd-parametre.

    as_of=<dato> (walk-forward-splitten, brukt av backtest.py): bygger det
    ekspanderende vinduet df[dato_kolonne] < as_of (strengt < — <= ville
    latt kampen vi prøver å spå trene modellen som skal spå den), sorterer
    vinduet kronologisk, og kutter det slik at den NYESTE andelen
    kalibrer_andel blir kalibreringsbolken. test_mask er alltid tom i
    denne grenen — walk-forward-løkkens egen prediksjon på as_of sine
    kamper ER testen, så en intern testbolk ville kun brent data uten å gi
    noe signal (05-RESEARCH.md Pattern 3).

    Kalibreringsbolken er en ANDEL av vinduet, ikke et fast antall måneder,
    fordi et fast 1-måneds-vindu gir ~50 kamper i november 2022 — godt
    under de 172 radene fase 3 allerede flagget som for lite for isotonic
    regression (05-RESEARCH.md Assumption A5 / Pitfall 4). En andel vokser
    derimot proporsjonalt med historikken etter hvert som walk-forward-
    løkken beveger seg framover.

    Kaster ValueError hvis kalibrer_andel ligger utenfor det åpne
    intervallet (0, 1), eller hvis vinduet før as_of har færre enn 2 rader
    (for lite til en tren/kalibrer-splitt).
    """
    if as_of is None:
        return del_kronologisk_3veis(df, dato_kolonne=dato_kolonne)

    if not (0 < kalibrer_andel < 1):
        raise ValueError(
            "kalibrer_andel må ligge i det åpne intervallet (0, 1), "
            f"fikk kalibrer_andel={kalibrer_andel}"
        )

    vindu_mask = df[dato_kolonne] < as_of
    vindu_df = df[vindu_mask].sort_values(dato_kolonne)

    if len(vindu_df) < 2:
        raise ValueError(
            f"For lite datagrunnlag før as_of={as_of!r}: {len(vindu_df)} rad(er) "
            "tilgjengelig, krever minst 2 for en tren/kalibrer-splitt"
        )

    kutt = int(len(vindu_df) * (1 - kalibrer_andel))
    kutt = min(max(kutt, 1), len(vindu_df) - 1)  # begge bolker skal ha minst 1 rad

    tren_indekser = vindu_df.index[:kutt]
    kalibrer_indekser = vindu_df.index[kutt:]

    tren_mask = pd.Series(False, index=df.index)
    kalibrer_mask = pd.Series(False, index=df.index)
    test_mask = pd.Series(False, index=df.index)

    tren_mask.loc[tren_indekser] = True
    kalibrer_mask.loc[kalibrer_indekser] = True

    return tren_mask, kalibrer_mask, test_mask


def tren_og_kalibrer(X_tren, y_tren, X_kalibrer, y_kalibrer, verbose=50):
    """
    Trener XGBoost på (X_tren, y_tren) og kalibrerer med isotonic
    regression på (X_kalibrer, y_kalibrer). Hyperparametrene er verbatim
    de samme som den opprinnelige 03_tren_modell.py brukte, uendret av
    denne ekstraksjonen.

    Returnerer en dict med nøklene raa_modell (den ukalibrerte XGBoost-
    modellen), kalibrerer (den fittede IsotonicRegression), y_raa_kalibrer
    (XGBoost sine rå sannsynligheter på kalibreringssettet — trengs av
    03_tren_modell.py til rapportering) og modell (KalibrertModell-
    wrapperen rundt de to første).
    """
    raa_modell = xgb.XGBClassifier(
        n_estimators=300,        # Antall trær
        max_depth=4,             # Dybde per tre (lav = mindre overfit)
        learning_rate=0.05,      # Læringshastighet (lav = roligere, bedre)
        subsample=0.8,           # Bruk 80% av treningsdataene per tre
        colsample_bytree=0.8,    # Bruk 80% av features per tre
        use_label_encoder=False,
        eval_metric="logloss",   # Optimaliser log-loss (god for sannsynligheter)
        random_state=42,
        early_stopping_rounds=20  # Stopp tidlig hvis modellen slutter å forbedre seg
    )

    # Early stopping ser på kalibreringssettet, ikke testsettet, slik at
    # testsettet forblir helt urørt av fitting (D-04). Ulempen: kalibrerings-
    # settet gjør dobbelt arbeid (early stopping + isotonic-fit) — en bevisst,
    # mindre avveining framfor å innføre en fjerde split.
    raa_modell.fit(
        X_tren, y_tren,
        eval_set=[(X_kalibrer, y_kalibrer)],
        verbose=verbose
    )

    # Kalibratoren fittes KUN på kalibreringssettet — aldri på testsettet.
    # Testsettet skal først møte kalibratoren gjennom .predict(), aldri
    # .fit() (CALIB-01).
    y_rå_kalibrer = raa_modell.predict_proba(X_kalibrer)[:, 1]
    kalibrerer = IsotonicRegression(out_of_bounds="clip")
    # Kalibreringssettet er lite og har et smalere score-spenn enn
    # testsettet, så testscorer utenfor det observerte området må klippes
    # til nærmeste kalibrerte verdi. Sklearn-standarden "nan" ville stille
    # korrumpert både metrikkene og bøttetabellen under (Pitfall 3).
    kalibrerer.fit(y_rå_kalibrer, y_kalibrer)

    kalibrert_modell = KalibrertModell(raa_modell, kalibrerer)

    return {
        "raa_modell": raa_modell,
        "kalibrerer": kalibrerer,
        "y_raa_kalibrer": y_rå_kalibrer,
        "modell": kalibrert_modell,
    }


def tren(features_df, as_of=None, kalibrer_andel=KALIBRER_ANDEL, verbose=False):
    """
    Ett-kalls bekvemmelighetsfunksjon: velger feature-kolonner, splitter
    via del_for_trening, og trener+kalibrerer på tren/kalibrer-bolkene.
    Dette er funksjonen Phase 5s walk-forward-løkke (backtest.py) kaller
    én gang per gjenopptreningspunkt med as_of=<dato>.

    verbose er False som standard fordi backtest-løkken fitter ~24
    modeller per kjøring og ikke trenger XGBoost sin fremgangsutskrift for
    hver av dem; 03_tren_modell.py sender inn verbose=50 eksplisitt for
    sin egen konsoll-rapportering (via tren_og_kalibrer direkte, ikke
    denne wrapperen).

    Returnerer tren_og_kalibrer sin dict, utvidet med feature_kolonner,
    tren_mask, kalibrer_mask, test_mask og as_of.
    """
    feature_kolonner = velg_feature_kolonner(features_df)
    X = features_df[feature_kolonner]
    y = features_df[MAAL_KOLONNE]

    tren_mask, kalibrer_mask, test_mask = del_for_trening(
        features_df, as_of=as_of, kalibrer_andel=kalibrer_andel
    )

    resultat = tren_og_kalibrer(
        X[tren_mask], y[tren_mask],
        X[kalibrer_mask], y[kalibrer_mask],
        verbose=verbose,
    )
    resultat["feature_kolonner"] = feature_kolonner
    resultat["tren_mask"] = tren_mask
    resultat["kalibrer_mask"] = kalibrer_mask
    resultat["test_mask"] = test_mask
    resultat["as_of"] = as_of
    return resultat


def lagre(kalibrert_modell, feature_kolonner, sti="nba_modell.pkl"):
    """
    Pickler en dict med nøyaktig nøklene "modell" og "feature_kolonner" —
    samme kontrakt verdi_deteksjon.py::last_modell allerede leser. Lagre
    ALDRI et bart modell-objekt, og ENDRE ALDRI disse nøkkelnavnene uten å
    endre verdi_deteksjon.py i samme commit.
    """
    with open(sti, "wb") as f:
        pickle.dump({
            "modell": kalibrert_modell,
            "feature_kolonner": feature_kolonner,
        }, f)


def last(sti="nba_modell.pkl"):
    """
    Leser tilbake dict-en lagre() skrev og returnerer (modell,
    feature_kolonner) — identisk kontrakt med
    verdi_deteksjon.py::last_modell, som fortsatt leser filen direkte og
    IKKE er endret av denne planen.
    """
    with open(sti, "rb") as f:
        data = pickle.load(f)
    return data["modell"], data["feature_kolonner"]
