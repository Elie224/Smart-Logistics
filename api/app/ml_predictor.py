"""
Chargement du modèle ML et prédiction de risque de retard.

Charge le modèle depuis MODELS_DIR/delay_model.pkl (créé par ml_trainer.py).
Si le modèle n'est pas encore disponible, retourne None (pas d'erreur fatale).
"""

import json
import os
from datetime import datetime, timezone
from typing import Optional

import numpy as np

MODELS_DIR = os.getenv("MODELS_DIR", "/app/models")
MODEL_PATH = os.path.join(MODELS_DIR, "delay_model.pkl")
META_PATH  = os.path.join(MODELS_DIR, "delay_model_meta.json")

TRANSIT_STATUS_MAP = {"NORMAL": 0, "REDUCED": 1, "DISRUPTED": 2}

FEATURES = [
    "departure_hour", "departure_dow", "departure_month",
    "hour_sin", "hour_cos",
    "dow_sin", "dow_cos",
    "month_sin", "month_cos",
    "is_weekend", "is_rush_hour", "is_night",
    "temperature", "wind_speed",
    "temp_below_5",
    "traffic_delay_s", "traffic_high",
    "transit_disruptions", "transit_blocking",
    "transit_status_enc",
    "route_duration_s",
]

_model = None   # cache process-level


def _load_model():
    global _model
    if _model is not None:
        return _model
    try:
        import joblib
        _model = joblib.load(MODEL_PATH)
        print(f"[ML] Modèle chargé depuis {MODEL_PATH}")
    except Exception as exc:
        print(f"[ML] Modèle non disponible : {exc}")
        _model = None
    return _model


def reload_model():
    """Force le rechargement du modèle (utile après entraînement)."""
    global _model
    _model = None
    return _load_model() is not None


def get_model_meta() -> dict:
    """Retourne les métadonnées du modèle entraîné."""
    try:
        with open(META_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"status": "not_trained", "message": "Modèle pas encore entraîné."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


def predict_delay_risk(
    departure_hour:      int,
    departure_dow:       int,
    temperature:         float,
    wind_speed:          float,
    traffic_delay_s:     float,
    transit_disruptions: int,
    transit_blocking:    int,
    transit_status:      str,
    route_duration_s:    float = 1800.0,
) -> Optional[dict]:
    """
    Prédit la probabilité de retard pour une livraison donnée.

    Returns:
        dict avec delay_probability, risk_level, risk_factors
        None si le modèle n'est pas disponible
    """
    clf = _load_model()
    if clf is None:
        return None

    # ── Feature engineering (identique au trainer) ──
    now         = datetime.now(timezone.utc)
    month       = now.month
    is_weekend  = 1 if departure_dow >= 5 else 0
    is_rush     = 1 if (7 <= departure_hour <= 9 or 17 <= departure_hour <= 19) and not is_weekend else 0
    is_night    = 1 if departure_hour < 6 or departure_hour >= 22 else 0

    hour_sin  = float(np.sin(2 * np.pi * departure_hour / 24))
    hour_cos  = float(np.cos(2 * np.pi * departure_hour / 24))
    dow_sin   = float(np.sin(2 * np.pi * departure_dow / 7))
    dow_cos   = float(np.cos(2 * np.pi * departure_dow / 7))
    month_sin = float(np.sin(2 * np.pi * (month - 1) / 12))
    month_cos = float(np.cos(2 * np.pi * (month - 1) / 12))

    temp_below_5 = 1 if float(temperature) < 5.0 else 0
    traffic_high = 1 if float(traffic_delay_s) > 300 else 0
    transit_enc  = TRANSIT_STATUS_MAP.get(str(transit_status), 0)

    X = np.array([[
        departure_hour, departure_dow, month,
        hour_sin, hour_cos,
        dow_sin, dow_cos,
        month_sin, month_cos,
        is_weekend, is_rush, is_night,
        float(temperature), float(wind_speed),
        temp_below_5,
        float(traffic_delay_s), traffic_high,
        int(transit_disruptions), int(transit_blocking),
        transit_enc,
        float(route_duration_s),
    ]], dtype=float)

    try:
        prob = float(clf.predict_proba(X)[0][1])
    except Exception as exc:
        print(f"[ML] Erreur prédiction (modèle obsolète?) : {exc}")
        return None

    if prob > 0.60:
        risk_level = "HIGH"
    elif prob > 0.35:
        risk_level = "MEDIUM"
    else:
        risk_level = "LOW"

    # Facteurs de risque identifiés
    risk_factors = []
    if is_rush:
        risk_factors.append("Heure de pointe")
    if is_night:
        risk_factors.append("Départ nocturne")
    if wind_speed > 10:
        risk_factors.append(f"Vent fort ({wind_speed:.0f} m/s)")
    if float(temperature) < 5:
        risk_factors.append(f"Températures basses ({temperature:.1f} °C)")
    if traffic_delay_s > 300:
        risk_factors.append(f"Trafic congestionné (+{int(traffic_delay_s // 60)} min)")
    if transit_blocking > 0:
        risk_factors.append(f"{transit_blocking} perturbation(s) bloquante(s) TC")
    if transit_enc == 2:
        risk_factors.append("Réseau TC perturbé")
    elif transit_enc == 1:
        risk_factors.append("Réseau TC en service réduit")
    if float(route_duration_s) > 7200:
        risk_factors.append(f"Long trajet ({int(route_duration_s / 3600):.0f}h)")

    recommendation = (
        "Reporter ou anticiper le départ." if risk_level == "HIGH"
        else "Surveiller attentivement." if risk_level == "MEDIUM"
        else "Conditions nominales."
    )

    return {
        "delay_probability": round(prob, 3),
        "risk_level":        risk_level,
        "risk_factors":      risk_factors,
        "recommendation":    recommendation,
        "predicted_at":      datetime.now(timezone.utc).isoformat(),
    }

