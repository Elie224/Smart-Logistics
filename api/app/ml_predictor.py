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
    """Retourne les métadonnées du modèle avec un schéma stable."""
    defaults = {
        "status": "unknown",
        "message": "",
        "model_type": None,
        "features": [],
        "n_real": 0,
        "n_synthetic": 0,
        "n_total": 0,
        "real_weight": None,
        "auc_train": None,
        "pr_auc_train": None,
        "brier_train": None,
        "cv_auc_mean": None,
        "cv_auc_std": None,
        "cv_pr_auc_mean": None,
        "cv_brier_mean": None,
        "calibration": None,
        "selected_params": {},
        "delayed_pct": None,
        "feature_importances": {},
        "coefficients": {},
        "trained_at": None,
    }

    try:
        with open(META_PATH) as f:
            raw = json.load(f)

        if not isinstance(raw, dict):
            return {
                **defaults,
                "status": "error",
                "message": "Format de métadonnées invalide.",
            }

        merged = {**defaults, **raw}
        if not merged.get("status"):
            merged["status"] = "ok"

        # Garantit des structures attendues côté UI.
        if not isinstance(merged.get("feature_importances"), dict):
            merged["feature_importances"] = {}
        if not isinstance(merged.get("coefficients"), dict):
            merged["coefficients"] = {}
        if not isinstance(merged.get("features"), list):
            merged["features"] = []

        return merged
    except FileNotFoundError:
        return {
            **defaults,
            "status": "not_trained",
            "message": "Modèle pas encore entraîné.",
        }
    except Exception as exc:
        return {
            **defaults,
            "status": "error",
            "message": str(exc),
        }


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _heuristic_probability(
    departure_hour: int,
    departure_dow: int,
    temperature: float,
    wind_speed: float,
    traffic_delay_s: float,
    transit_disruptions: int,
    transit_blocking: int,
    transit_enc: int,
    route_duration_s: float,
) -> float:
    """Score métier déterministe pour stabiliser les prédictions en faible-data."""
    p = 0.14

    is_weekend = departure_dow >= 5
    is_rush = (7 <= departure_hour <= 9 or 17 <= departure_hour <= 19) and not is_weekend
    is_night = departure_hour < 6 or departure_hour >= 22

    if is_rush:
        p += 0.16
    if is_night:
        p += 0.05
    if wind_speed > 10:
        p += 0.08
    if temperature < 5:
        p += 0.06
    if temperature < 0:
        p += 0.07
    if traffic_delay_s > 300:
        p += 0.16
    if traffic_delay_s > 600:
        p += 0.10
    if transit_disruptions >= 2:
        p += 0.05
    if transit_blocking > 0:
        p += 0.12
    if transit_enc == 1:
        p += 0.05
    if transit_enc == 2:
        p += 0.10
    if route_duration_s > 7200:
        p += 0.07

    return _clip01(p)


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
        (fallback heuristique si le modèle n'est pas disponible)
    """
    clf = _load_model()

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

    meta = get_model_meta()
    n_real = _safe_int(meta.get("n_real", 0), 0) if isinstance(meta, dict) else 0
    cv_auc = _safe_float(meta.get("cv_auc_mean", 0.0), 0.0) if isinstance(meta, dict) else 0.0

    heuristic_prob = _heuristic_probability(
        departure_hour=departure_hour,
        departure_dow=departure_dow,
        temperature=float(temperature),
        wind_speed=float(wind_speed),
        traffic_delay_s=float(traffic_delay_s),
        transit_disruptions=int(transit_disruptions),
        transit_blocking=int(transit_blocking),
        transit_enc=transit_enc,
        route_duration_s=float(route_duration_s),
    )

    ml_prob = None
    alpha = 0.0

    if clf is not None:
        try:
            ml_prob = float(clf.predict_proba(X)[0][1])
        except Exception as exc:
            print(f"[ML] Erreur prédiction (modèle obsolète?) : {exc}")
            ml_prob = None

    if ml_prob is not None:
        # Faible historique réel -> on réduit le poids du modèle pur.
        if n_real < 20:
            alpha = 0.35
        elif n_real < 100:
            alpha = 0.5
        else:
            alpha = 0.7

        if cv_auc < 0.62:
            alpha = max(0.25, alpha - 0.15)

        prob = _clip01(alpha * ml_prob + (1.0 - alpha) * heuristic_prob)
    else:
        # Fallback 100% réel (trafic/TC/météo) si modèle indisponible.
        prob = heuristic_prob

    if prob > 0.65:
        risk_level = "HIGH"
    elif prob > 0.40:
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

    if n_real < 20:
        risk_factors.append("Confiance ML limitée (historique réel faible)")
    if ml_prob is None:
        risk_factors.append("Mode estimation réelle sans modèle entraîné")

    recommendation = (
        "Reporter ou anticiper le départ." if risk_level == "HIGH"
        else "Surveiller attentivement." if risk_level == "MEDIUM"
        else "Conditions nominales."
    )

    return {
        "delay_probability": round(prob, 3),
        "ml_probability": round(ml_prob, 3) if ml_prob is not None else None,
        "heuristic_probability": round(heuristic_prob, 3),
        "model_weight": round(alpha, 2),
        "risk_level":        risk_level,
        "risk_factors":      risk_factors,
        "recommendation":    recommendation,
        "predicted_at":      datetime.now(timezone.utc).isoformat(),
    }

