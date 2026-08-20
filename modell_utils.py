"""
Delt modul for NBA betting-pipeline.
Importeres av 03_tren_modell.py og 04_value_detector.py.
"""
import numpy as np


class KalibrertModell:
    """
    Wrapper som kombinerer XGBoost med en isotonic regression-kalibrerer.
    Samme grensesnitt som sklearn-modeller (predict_proba), slik at
    resten av pipelinen ikke trenger å endres.
    """
    def __init__(self, modell, kalibrerer):
        self.modell               = modell
        self.kalibrerer           = kalibrerer
        self.feature_importances_ = modell.feature_importances_

    def predict_proba(self, X):
        rå        = self.modell.predict_proba(X)[:, 1]
        kalibrert = self.kalibrerer.predict(rå)
        return np.column_stack([1 - kalibrert, kalibrert])
