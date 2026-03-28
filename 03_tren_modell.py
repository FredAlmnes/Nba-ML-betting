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
from sklearn.calibration import CalibratedClassifierCV
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

# Bruk de siste 2 månedene som testsett, resten til trening.
# Dette er bedre enn 80/20 fordi vi alltid tester på de nyeste kampene,
# uavhengig av hvor mye data vi har totalt.
fra_dato = df["GAME_DATE_HJEMME"].max() - pd.DateOffset(months=2)
tren_mask = df["GAME_DATE_HJEMME"] < fra_dato

X_tren = X[tren_mask]
y_tren = y[tren_mask]
X_test = X[~tren_mask]
y_test = y[~tren_mask]

print(f"\nTreningssett: {len(X_tren)} kamper")
print(f"Testsett:     {len(X_test)} kamper")
print(f"Siste treningskamp: {df['GAME_DATE_HJEMME'][tren_mask].iloc[-1].date()}")
print(f"Første testkamp:    {df['GAME_DATE_HJEMME'][~tren_mask].iloc[0].date()}")

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
    eval_set=[(X_test, y_test)],
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
# 7. Lagre modellen
# -------------------------------------------------------
with open("nba_modell.pkl", "wb") as f:
    pickle.dump({
        "modell": modell,
        "feature_kolonner": feature_kolonner
    }, f)

print("\nModell lagret til 'nba_modell.pkl'")
print("Kjør nå 04_value_detector.py for å sammenligne med bookmaker-odds!")
