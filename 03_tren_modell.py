"""
STEG 3: Tren prediksjonsmodell
================================
Her trener vi en modell som spår sannsynligheten for at
hjemmelaget vinner en NBA-kamp.

Vi bruker XGBoost – en kraftig og populær algoritme for
tabelldata. Den er mye brukt i praksis for sportsanalyse.

Viktig konsept: vi trener på gamle kamper og tester
på nyere kamper (tidsserie-split). Vi må ALDRI trene
på fremtidige data!
"""

import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, log_loss, brier_score_loss
# NB: modulen heter "model" (entall, engelsk), den fittede XGBoost-
# estimatoren under kalles fortsatt "modell" (norsk), og modell_utils er en
# TREDJE, annerledes ting (kun KalibrertModell-wrapperklassen). model.py
# eier nå alle .fit()-kall — se model.py sin modul-docstring.
import model

# -------------------------------------------------------
# 1. Les inn features
# -------------------------------------------------------
print("Leser inn features...")
df = pd.read_csv("nba_features.csv", parse_dates=["GAME_DATE_HJEMME"])
df = df.sort_values("GAME_DATE_HJEMME").reset_index(drop=True)

print(f"Totalt {len(df)} kamper tilgjengelig")

# -------------------------------------------------------
# 2. Velg hvilke features vi bruker
# -------------------------------------------------------
# Vi bruker differanse-features + rullende stats for hvert lag
feature_kolonner = model.velg_feature_kolonner(df)

maal_kolonne = model.MAAL_KOLONNE

print(f"\nAntall features: {len(feature_kolonner)}")
print("Features brukt:", feature_kolonner)

X = df[feature_kolonner]
y = df[maal_kolonne]

# -------------------------------------------------------
# 3. Tidsserie-split (VELDIG VIKTIG!)
# -------------------------------------------------------
# I vanlig maskinlæring kan man dele data tilfeldig.
# Men for tidsseriedata MÅ vi bruke tidsserie-split:
# - Tren på eldre kamper
# - Test på nyere kamper
# Dette simulerer virkeligheten: vi kan aldri spå fortiden.

# Bruk de siste 2 månedene som holdout, resten til trening. Dette er bedre
# enn 80/20 fordi vi alltid tester på de nyeste kampene, uavhengig av hvor
# mye data vi har totalt.
#
# Holdout-vinduet deles nå i TRE ikke-overlappende bolker i stedet for to:
# tren (alt før holdout), kalibrer (den eldste halvdelen av holdout-vinduet)
# og test (den nyeste halvdelen). Kalibrer brukes til early stopping og til
# å fitte isotonic-kalibratoren; test er den nyeste halvdelen og berøres
# ALDRI av noen .fit()-kall — den brukes kun til sluttrapportering. Uten
# dette skillet ville kalibratoren blitt evaluert på nøyaktig de samme
# dataene den ble fittet på — kunstig gode tall som ikke sier noe om ekte
# generalisering (CALIB-01).
tren_mask, kalibrer_mask, test_mask = model.del_for_trening(df)

X_tren, y_tren = X[tren_mask], y[tren_mask]
X_kalibrer, y_kalibrer = X[kalibrer_mask], y[kalibrer_mask]
X_test, y_test = X[test_mask], y[test_mask]

print(f"\nTreningssett:     {len(X_tren)} kamper  "
      f"({df['GAME_DATE_HJEMME'][tren_mask].iloc[0].date()} -> "
      f"{df['GAME_DATE_HJEMME'][tren_mask].iloc[-1].date()})")
print(f"Kalibreringssett: {len(X_kalibrer)} kamper  "
      f"({df['GAME_DATE_HJEMME'][kalibrer_mask].iloc[0].date()} -> "
      f"{df['GAME_DATE_HJEMME'][kalibrer_mask].iloc[-1].date()})")
print(f"Testsett:         {len(X_test)} kamper  "
      f"({df['GAME_DATE_HJEMME'][test_mask].iloc[0].date()} -> "
      f"{df['GAME_DATE_HJEMME'][test_mask].iloc[-1].date()})")

# Scikit-learn anbefaler >~1000 eksempler for isotonic regression (D-03).
# Dette er en kjørende sjekk mot det faktiske datagrunnlaget, ikke et fast
# tall — kalibreringen kan være støyende/overfittet på et lite datasett.
if len(X_kalibrer) < 1000:
    print(f"\nADVARSEL: Kalibreringssettet har kun {len(X_kalibrer)} kamper "
          f"(under sklearns anbefalte ~1000 for isotonic regression). "
          f"Kalibreringen kan derfor være støyende/overfittet på et lite "
          f"datasett.")

# -------------------------------------------------------
# 4. Tren XGBoost-modellen
# -------------------------------------------------------
print("\nTrener XGBoost-modell...")

# Selve XGBoost-fittingen (inkl. early stopping mot kalibreringssettet,
# D-04) skjer nå inne i model.tren_og_kalibrer — se dens docstring for
# hyperparametrene og begrunnelsen. verbose=50 er funksjonens standard,
# så konsoll-fremgangen ("[0]"/"[50]"/...) er uendret.
resultat = model.tren_og_kalibrer(X_tren, y_tren, X_kalibrer, y_kalibrer)
modell     = resultat["raa_modell"]
kalibrerer = resultat["kalibrerer"]

# -------------------------------------------------------
# 5. Evaluer modellen
# -------------------------------------------------------
print("\n--- Evaluering på testsett ---")

# Sannsynlighetsforutsigelser (dette er det vi trenger for value betting)
y_sann = modell.predict_proba(X_test)[:, 1]
y_pred = (y_sann > 0.5).astype(int)

noyaktighet = accuracy_score(y_test, y_pred)
logloss     = log_loss(y_test, y_sann)
brier       = brier_score_loss(y_test, y_sann)

print(f"Nøyaktighet:   {noyaktighet:.3f}  ({noyaktighet:.1%})")
print(f"Log-loss:      {logloss:.4f}  (lavere = bedre, tilfeldig gjetning ≈ 0.693)")
print(f"Brier Score:   {brier:.4f}  (lavere = bedre, perfekt = 0)")

# Sammenlign med naiv baseline (alltid spå hjemmelaget vinner)
baseline_noy = y_test.mean()
print(f"\nBaseline (alltid hjemme): {baseline_noy:.1%}")
print(f"Vår modell:               {noyaktighet:.1%}")
print(f"Forbedring:               {(noyaktighet - baseline_noy):.1%}")

# -------------------------------------------------------
# 6. Feature importance – hva betyr mest?
# -------------------------------------------------------
print("\n--- Viktigste features ---")
importance = pd.DataFrame({
    "feature": feature_kolonner,
    "importance": modell.feature_importances_
}).sort_values("importance", ascending=False)

print(importance.head(10).to_string(index=False))

# -------------------------------------------------------
# 7. Kalibrer modellen med isotonic regression
# -------------------------------------------------------
# XGBoost-sannsynligheter er ofte feilkalibrert – modellen kan
# si "70% sjanse" når den faktisk har rett 60% av gangene.
# Isotonic regression fitter en monoton funksjon fra rå XGBoost-
# score til faktisk observert treffsannsynlighet.

print("\nKalibrerer modellen (isotonic regression)...")

# Selve isotonic-fittingen skjedde allerede inne i model.tren_og_kalibrer
# (kalibratoren fittes KUN på kalibreringssettet, aldri på testsettet —
# CALIB-01). Denne seksjonen henter kun ut det ferdige resultatet og
# scorer/rapporterer det.
y_rå_kalibrer = resultat["y_raa_kalibrer"]

# Score testsettet gjennom den allerede fittede kalibratoren — testsettet
# har aldri blitt sett under noen .fit()-kall.
y_rå_test   = modell.predict_proba(X_test)[:, 1]
y_kal_test  = kalibrerer.predict(y_rå_test)
logloss_kal = log_loss(y_test, y_kal_test)
brier_kal   = brier_score_loss(y_test, y_kal_test)

print(f"\n{'=' * 60}")
print(f"Kalibrator FITTET på:   kalibreringssett ({len(X_kalibrer)} kamper)")
print(f"Kalibrator EVALUERT på: testsett ({len(X_test)} kamper) — aldri sett under fitting")
print(f"{'=' * 60}")

print(f"\n--- Kalibrering: før vs etter (målt på testsettet) ---")
print(f"{'':25} {'Ukalibrert':>12} {'Kalibrert':>12}")
print(f"{'Log-loss':25} {logloss:>12.4f} {logloss_kal:>12.4f}")
print(f"{'Brier Score':25} {brier:>12.4f} {brier_kal:>12.4f}")
print(f"(Lavere er bedre for begge)")
print(f"Merk: hvis Kalibrert er DÅRLIGERE enn Ukalibrert, har isotonic-fitten")
print(f"sannsynligvis overfittet det lille kalibreringssettet — et funn å ta")
print(f"videre, ikke noe å skjule.")

# In-sample-diagnose på kalibreringssettet — KUN diagnostisk, IKKE et mål på
# generalisering (kalibratoren har sett akkurat disse dataene under fitting).
y_kal_kalibrer        = kalibrerer.predict(y_rå_kalibrer)
logloss_kal_insample  = log_loss(y_kalibrer, y_kal_kalibrer)
brier_kal_insample    = brier_score_loss(y_kalibrer, y_kal_kalibrer)
print(f"\n--- In-sample på kalibreringssettet (kun diagnostisk, IKKE et mål på generalisering) ---")
print(f"Log-loss: {logloss_kal_insample:.4f}   Brier Score: {brier_kal_insample:.4f}")

# Diagnose: sammenlign forutsagt sannsynlighet med faktisk treffsrate per
# bøtte — beregnet på TESTSETTET (out-of-sample), som kalibratoren aldri
# fikk se under fitting.
print(f"\n--- Kalibreringsdiagnose / reliabilitetstabell — TESTSETT (out-of-sample, 10 bøtter) ---")
if len(X_kalibrer) < 1000:
    print(f"(NB: kalibreringssett: {len(X_kalibrer)} kamper — under sklearns anbefalte ~1000)")
print(f"{'Pred. sann. (kal.)':>20} {'Faktisk treffsrate':>20} {'Antall kamper':>15}")
diag = pd.DataFrame({"pred": y_kal_test, "faktisk": y_test.values})
for _, gruppe in diag.groupby(pd.cut(diag["pred"], bins=10), observed=True):
    if len(gruppe) > 0:
        print(f"{gruppe['pred'].mean():>20.1%} {gruppe['faktisk'].mean():>20.1%} {len(gruppe):>15}")

# -------------------------------------------------------
# 8. Lagre kalibrert modell
# -------------------------------------------------------
kalibrert_modell = resultat["modell"]

model.lagre(kalibrert_modell, feature_kolonner)

print("\nKalibrert modell lagret til 'nba_modell.pkl'")
print("Kjør nå 04_value_detector.py for å sammenligne med bookmaker-odds!")
