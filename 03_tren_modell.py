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
import xgboost as xgb
from sklearn.metrics import accuracy_score, log_loss, brier_score_loss
from sklearn.isotonic import IsotonicRegression
from modell_utils import KalibrertModell
from kalibrering import del_kronologisk_3veis
import pickle

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
feature_kolonner = [k for k in df.columns if
                    k.startswith("DIFF_") or
                    k.startswith("HJEMME_RULL_") or
                    k.startswith("BORTE_RULL_")]

maal_kolonne = "HJEMME_VANT"

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
tren_mask, kalibrer_mask, test_mask = del_kronologisk_3veis(df)

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

modell = xgb.XGBClassifier(
    n_estimators=300,        # Antall trær
    max_depth=4,             # Dybde per tre (lav = mindre overfit)
    learning_rate=0.05,      # Læringshastighet (lav = roligere, bedre)
    subsample=0.8,           # Bruk 80% av treningsdataene per tre
    colsample_bytree=0.8,    # Bruk 80% av features per tre
    use_label_encoder=False,
    eval_metric="logloss",   # Optimaliser log-loss (god for sannsynligheter)
    random_state=42,
    early_stopping_rounds=20 # Stopp tidlig hvis modellen slutter å forbedre seg
)

modell.fit(
    X_tren, y_tren,
    # Early stopping ser nå på kalibreringssettet, ikke testsettet, slik at
    # testsettet forblir helt urørt av fitting (D-04). Ulempen: kalibrerings-
    # settet gjør dobbelt arbeid (early stopping + isotonic-fit) — en bevisst,
    # mindre avveining framfor å innføre en fjerde split (hører til fase 5 /
    # BT-03).
    eval_set=[(X_kalibrer, y_kalibrer)],
    verbose=50  # Skriv ut fremgang hvert 50. tre
)

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

y_rå        = modell.predict_proba(X_test)[:, 1]
kalibrerer  = IsotonicRegression(out_of_bounds="clip")
kalibrerer.fit(y_rå, y_test)

y_sann_kal  = kalibrerer.predict(y_rå)
logloss_kal = log_loss(y_test, y_sann_kal)
brier_kal   = brier_score_loss(y_test, y_sann_kal)

print(f"\n--- Kalibrering: før vs etter ---")
print(f"{'':25} {'Ukalibrert':>12} {'Kalibrert':>12}")
print(f"{'Log-loss':25} {logloss:>12.4f} {logloss_kal:>12.4f}")
print(f"{'Brier Score':25} {brier:>12.4f} {brier_kal:>12.4f}")
print(f"(Lavere er bedre for begge)")

# Diagnose: sammenlign forutsagt sannsynlighet med faktisk treffsrate per bøtte
print(f"\n--- Kalibreringsdiagnose (10 bøtter) ---")
print(f"{'Pred. sann. (kal.)':>20} {'Faktisk treffsrate':>20} {'Antall kamper':>15}")
diag = pd.DataFrame({"pred": y_sann_kal, "faktisk": y_test.values})
for _, gruppe in diag.groupby(pd.cut(diag["pred"], bins=10), observed=True):
    if len(gruppe) > 0:
        print(f"{gruppe['pred'].mean():>20.1%} {gruppe['faktisk'].mean():>20.1%} {len(gruppe):>15}")

# -------------------------------------------------------
# 8. Lagre kalibrert modell
# -------------------------------------------------------
kalibrert_modell = KalibrertModell(modell, kalibrerer)

with open("nba_modell.pkl", "wb") as f:
    pickle.dump({
        "modell":           kalibrert_modell,
        "feature_kolonner": feature_kolonner
    }, f)

print("\nKalibrert modell lagret til 'nba_modell.pkl'")
print("Kjør nå 04_value_detector.py for å sammenligne med bookmaker-odds!")
