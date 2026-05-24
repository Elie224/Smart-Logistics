"""
Pipeline ML — Prédiction de retard livraisons France (multi-villes).

Modèle   : LightGBM calibré (sigmoid) après sélection CV
Features : 21 features incl. encodage cyclique heure/jour/mois, météo, trafic, TC
Data     : données réelles (vue ml_delivery_dataset) + données synthétiques
Éval     : StratifiedKFold(5), AUC/PR-AUC/Brier

Env vars :
    POSTGRES_HOST / PORT / DB / USER / PASSWORD
    MODELS_DIR   — répertoire de sauvegarde (défaut: /app/models)
"""

import json
import os
import random
from datetime import datetime, timezone

import numpy as np

try:
    import psycopg2
except ImportError:
    raise SystemExit("psycopg2 requis : pip install psycopg2-binary")

try:
    import lightgbm as lgb
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import (
        average_precision_score,
        brier_score_loss,
        classification_report,
        roc_auc_score,
    )
    import joblib
except ImportError:
    raise SystemExit("lightgbm, scikit-learn et joblib requis")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODELS_DIR = os.getenv("MODELS_DIR", "/app/models")
MODEL_PATH = os.path.join(MODELS_DIR, "delay_model.pkl")
META_PATH  = os.path.join(MODELS_DIR, "delay_model_meta.json")

TRANSIT_STATUS_MAP = {"NORMAL": 0, "REDUCED": 1, "DISRUPTED": 2}

FEATURES = [
    "departure_hour",       # heure départ brute
    "departure_dow",        # jour semaine brut
    "departure_month",      # mois de l'année (série temporelle)
    "hour_sin",             # encodage cyclique heure (sin)
    "hour_cos",             # encodage cyclique heure (cos)
    "dow_sin",              # encodage cyclique jour (sin)
    "dow_cos",              # encodage cyclique jour (cos)
    "month_sin",            # encodage cyclique mois (sin)
    "month_cos",            # encodage cyclique mois (cos)
    "is_weekend",           # flag week-end
    "is_rush_hour",         # flag heure de pointe
    "is_night",             # flag nuit (22h-6h)
    "temperature",          # température °C
    "wind_speed",           # vitesse vent m/s
    "temp_below_5",         # flag froid (<5°C)
    "traffic_delay_s",      # retard trafic en secondes
    "traffic_high",         # flag trafic fort (>300s)
    "transit_disruptions",  # nb perturbations TC totales
    "transit_blocking",     # nb perturbations TC bloquantes
    "transit_status_enc",   # statut réseau encodé (0/1/2)
    "route_duration_s",     # durée trajet attendue en secondes (proxy distance)
]


# ---------------------------------------------------------------------------
# Connexion PostgreSQL
# ---------------------------------------------------------------------------

def get_connection():
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT",
                         "5433" if host in ("localhost", "127.0.0.1") else "5432"))
    return psycopg2.connect(
        host=host, port=port,
        dbname=os.getenv("POSTGRES_DB", "smart_logistics"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


# ---------------------------------------------------------------------------
# Chargement des données réelles
# ---------------------------------------------------------------------------

def load_real_data() -> list[tuple]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    departure_hour, departure_dow,
                    EXTRACT(month FROM departure_time)::integer AS departure_month,
                    temperature, wind_speed,
                    traffic_delay_s,
                    route_duration_s,
                    transit_disruptions, transit_blocking,
                    transit_status,
                    is_delayed
                FROM ml_delivery_dataset
            """)
            return cur.fetchall()
    finally:
        conn.close()


def _build_features(hour: int, dow: int, month: int, temperature: float, wind_speed: float,
                    traffic_delay_s: float, transit_disruptions: int,
                    transit_blocking: int, transit_enc: int,
                    route_duration_s: float = 1800.0) -> list[float]:
    """Construit le vecteur de 21 features à partir des valeurs brutes."""
    is_weekend  = 1 if dow >= 5 else 0
    is_rush     = 1 if (7 <= hour <= 9 or 17 <= hour <= 19) and not is_weekend else 0
    is_night    = 1 if hour < 6 or hour >= 22 else 0

    hour_sin  = float(np.sin(2 * np.pi * hour / 24))
    hour_cos  = float(np.cos(2 * np.pi * hour / 24))
    dow_sin   = float(np.sin(2 * np.pi * dow / 7))
    dow_cos   = float(np.cos(2 * np.pi * dow / 7))
    month_sin = float(np.sin(2 * np.pi * (month - 1) / 12))
    month_cos = float(np.cos(2 * np.pi * (month - 1) / 12))

    temp_below_5 = 1 if temperature < 5.0 else 0
    traffic_high = 1 if traffic_delay_s > 300 else 0

    return [
        hour, dow, month,
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
    ]


def encode_real_row(row: tuple):
    try:
        (hour, dow, month, temperature, wind_speed, traffic_delay_s,
         route_duration_s, transit_disruptions, transit_blocking,
         transit_status, is_delayed) = row

        transit_enc = TRANSIT_STATUS_MAP.get(str(transit_status), 0)
        feats = _build_features(
            int(hour), int(dow), int(month),
            float(temperature), float(wind_speed),
            float(traffic_delay_s),
            int(transit_disruptions), int(transit_blocking),
            transit_enc,
            float(route_duration_s) if route_duration_s else 1800.0,
        )
        return feats, int(is_delayed)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Génération de données synthétiques réalistes (réseau France multi-villes)
# ---------------------------------------------------------------------------

def generate_synthetic_data(n: int = 2500) -> tuple[list, list]:
    """
    Génère des exemples synthétiques calibrés pour le réseau logistique France.

    Taux de retard de base : 15%
    Facteurs aggravants :
      heure de pointe (7-9h/17-19h) : +20 %
      nuit (22h-6h)                 : +5 %
      vent fort (> 10 m/s)          : +10 %
      froid (< 5 °C)                : +6 %
      gel (< 0 °C)                  : +8 %  bonus
      trafic fort (> 300 s)         : +18 %
      trafic très fort (> 600 s)    : +12 % bonus
      perturbations bloquantes TC   : +12 %
      réseau DISRUPTED              : +10 %
    """
    rng    = random.Random(42)
    np_rng = np.random.default_rng(42)

    X, y = [], []

    for _ in range(n):
        hour       = rng.randint(0, 23)
        dow        = rng.randint(0, 6)
        month      = rng.randint(1, 12)  # variation saisonnière
        is_weekend = 1 if dow >= 5 else 0
        is_rush    = 1 if (7 <= hour <= 9 or 17 <= hour <= 19) and not is_weekend else 0
        is_night   = 1 if hour < 6 or hour >= 22 else 0

        # Météo réaliste France (saisonnalisée, valeurs moyennes réseau)
        base_temp = 14.0 + 12.0 * np.cos(2 * np.pi * (month - 7) / 12)  # max juillet, min janvier
        temperature     = float(np.clip(np_rng.normal(base_temp, 5.0), -15.0, 40.0))
        wind_speed      = float(abs(np_rng.normal(4.5, 3.5)))
        # Durée de trajet synthétique (proxy distance) : 900s à 14400s (15min→4h)
        # Distribution log-normale : la plupart 1-3h, quelques longues distances
        route_duration_s = float(np.clip(np_rng.lognormal(7.8, 0.7), 900, 14400))

        # Trafic : exponentiel centré sur 180s, plus fort aux heures de pointe
        # Les longs trajets ont statistiquement plus d'exposition au trafic
        base_traffic    = 200 if is_rush else 120
        if route_duration_s > 7200:   # >2h → plus d'exposition trafic
            base_traffic = int(base_traffic * 1.4)
        traffic_delay_s = float(abs(np_rng.exponential(base_traffic)))
        transit_disrupt = int(np_rng.poisson(0.7))
        transit_blocking = min(int(np_rng.poisson(0.15)), transit_disrupt)

        if transit_blocking > 0 and transit_disrupt >= 3:
            transit_enc = 2
        elif transit_disrupt > 0:
            transit_enc = 1
        else:
            transit_enc = 0

        # Probabilité de retard calibrée (~25-30% base réelle observée)
        p = 0.20
        if is_rush:
            p += 0.18
        if is_night:
            p += 0.05
        if wind_speed > 10:
            p += 0.10
        if temperature < 5:
            p += 0.06
        if temperature < 0:
            p += 0.08
        if traffic_delay_s > 300:
            p += 0.15
        if traffic_delay_s > 600:
            p += 0.10
        if transit_blocking > 0:
            p += 0.12
        if transit_enc == 2:
            p += 0.08
        if route_duration_s > 7200:   # long trajet = plus de risque
            p += 0.08
        p = min(p, 0.95)

        label = 1 if rng.random() < p else 0

        feats = _build_features(
            hour, dow, month,
            temperature, wind_speed,
            traffic_delay_s,
            transit_disrupt, transit_blocking,
            transit_enc,
            route_duration_s,
        )
        X.append(feats)
        y.append(label)

    return X, y


def build_sample_weights(n_real: int, y: np.ndarray) -> np.ndarray:
    """Pondère les données réelles et corrige légèrement le déséquilibre de classes."""
    weights = np.ones(len(y), dtype=float)

    # Les données réelles sont rares: on augmente leur poids sans les surdominer.
    real_weight = 6.0 if n_real > 0 else 1.0
    weights[:n_real] *= real_weight

    pos = max(int(y.sum()), 1)
    neg = max(int((y == 0).sum()), 1)
    pos_boost = min(3.0, neg / pos)
    weights[y == 1] *= pos_boost
    return weights


def evaluate_cv(params: dict, X: np.ndarray, y: np.ndarray, weights: np.ndarray) -> dict:
    """Évalue un set d'hyperparamètres via CV stratifiée."""
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    auc_scores, ap_scores, brier_scores = [], [], []

    for train_idx, val_idx in cv.split(X, y):
        clf = lgb.LGBMClassifier(
            **params,
            objective="binary",
            random_state=42,
            n_jobs=1,
            verbose=-1,
        )
        clf.fit(X[train_idx], y[train_idx], sample_weight=weights[train_idx])
        prob = clf.predict_proba(X[val_idx])[:, 1]

        auc_scores.append(roc_auc_score(y[val_idx], prob))
        ap_scores.append(average_precision_score(y[val_idx], prob))
        brier_scores.append(brier_score_loss(y[val_idx], prob))

    return {
        "auc_mean": float(np.mean(auc_scores)),
        "auc_std": float(np.std(auc_scores)),
        "ap_mean": float(np.mean(ap_scores)),
        "brier_mean": float(np.mean(brier_scores)),
    }


# ---------------------------------------------------------------------------
# Entraînement du modèle
# ---------------------------------------------------------------------------

def train_model() -> tuple:
    os.makedirs(MODELS_DIR, exist_ok=True)

    # --- Données réelles ---
    real_rows = load_real_data()
    real_X, real_y = [], []
    for row in real_rows:
        encoded = encode_real_row(row)
        if encoded:
            x, label = encoded
            real_X.append(x)
            real_y.append(label)
    print(f"[ML] {len(real_X)} exemples réels chargés.")

    # --- Données synthétiques ---
    syn_X, syn_y = generate_synthetic_data(5000)
    print(f"[ML] {len(syn_X)} exemples synthétiques générés.")

    X = np.array(real_X + syn_X, dtype=float)
    y = np.array(real_y + syn_y, dtype=int)
    weights = build_sample_weights(len(real_X), y)

    print(f"[ML] Dataset total : {len(X)} exemples "
          f"({int(y.sum())} retards / {int((y == 0).sum())} à l'heure)")

    # --- Sélection d'hyperparamètres par CV ---
    candidates = [
        {
            "n_estimators": 300,
            "max_depth": 5,
            "learning_rate": 0.05,
            "subsample": 0.75,
            "colsample_bytree": 0.75,
            "min_child_samples": 25,
            "reg_lambda": 1.0,
            "reg_alpha": 0.1,
        },
        {
            "n_estimators": 450,
            "max_depth": 6,
            "learning_rate": 0.035,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_samples": 30,
            "reg_lambda": 1.2,
            "reg_alpha": 0.2,
        },
        {
            "n_estimators": 220,
            "max_depth": 4,
            "learning_rate": 0.07,
            "subsample": 0.7,
            "colsample_bytree": 0.7,
            "min_child_samples": 20,
            "reg_lambda": 0.9,
            "reg_alpha": 0.05,
        },
    ]

    best_params = None
    best_metrics = None
    best_score = -1.0

    for idx, params in enumerate(candidates, start=1):
        metrics = evaluate_cv(params, X, y, weights)
        # Score composite orienté performance + calibration
        score = metrics["auc_mean"] + 0.25 * metrics["ap_mean"] - 0.15 * metrics["brier_mean"]
        print(
            f"[ML] Candidate #{idx} -> "
            f"AUC={metrics['auc_mean']:.3f}±{metrics['auc_std']:.3f}, "
            f"PR-AUC={metrics['ap_mean']:.3f}, Brier={metrics['brier_mean']:.3f}"
        )
        if score > best_score:
            best_score = score
            best_params = params
            best_metrics = metrics

    print(
        f"[ML] Best params sélectionnés -> "
        f"AUC CV: {best_metrics['auc_mean']:.3f} ± {best_metrics['auc_std']:.3f}, "
        f"PR-AUC: {best_metrics['ap_mean']:.3f}, Brier: {best_metrics['brier_mean']:.3f}"
    )

    # --- Entraînement final + calibration probabiliste ---
    base_clf = lgb.LGBMClassifier(
        **best_params,
        objective="binary",
        random_state=42,
        n_jobs=1,
        verbose=-1,
    )
    base_clf.fit(X, y, sample_weight=weights)

    clf = CalibratedClassifierCV(estimator=base_clf, method="sigmoid", cv=5)
    clf.fit(X, y, sample_weight=weights)

    y_pred = clf.predict(X)
    y_prob = clf.predict_proba(X)[:, 1]
    auc_train = roc_auc_score(y, y_prob)
    pr_auc_train = average_precision_score(y, y_prob)
    brier_train = brier_score_loss(y, y_prob)

    print(f"[ML] AUC (train complet) : {auc_train:.3f}")
    print(f"[ML] PR-AUC (train complet) : {pr_auc_train:.3f}")
    print(f"[ML] Brier (train complet) : {brier_train:.3f}")
    print(classification_report(y, y_pred, target_names=["ON_TIME", "DELAYED"]))

    delayed_pct = round(float(y.sum()) / len(y) * 100, 1)
    print(f"[ML] Taux de retard dataset : {delayed_pct} %")

    # --- Sauvegarde ---
    joblib.dump(clf, MODEL_PATH)
    print(f"\n[ML] Modèle sauvegardé → {MODEL_PATH}")

    # Importance des features (modèle de base LightGBM)
    importances = dict(zip(
        FEATURES,
        [round(float(v), 4) for v in base_clf.feature_importances_]
    ))

    meta = {
        "model_type":           "LightGBM",
        "features":             FEATURES,
        "n_real":               len(real_X),
        "n_synthetic":          len(syn_X),
        "n_total":              len(X),
        "real_weight":          6.0 if len(real_X) > 0 else 1.0,
        "auc_train":            round(auc_train, 4),
        "pr_auc_train":         round(pr_auc_train, 4),
        "brier_train":          round(brier_train, 4),
        "cv_auc_mean":          round(best_metrics["auc_mean"], 4),
        "cv_auc_std":           round(best_metrics["auc_std"], 4),
        "cv_pr_auc_mean":       round(best_metrics["ap_mean"], 4),
        "cv_brier_mean":        round(best_metrics["brier_mean"], 4),
        "calibration":          "sigmoid",
        "selected_params":      best_params,
        "delayed_pct":          delayed_pct,
        "feature_importances":  importances,
        "trained_at":           datetime.now(timezone.utc).isoformat(),
    }

    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"[ML] Métadonnées → {META_PATH}")
    return clf, meta


if __name__ == "__main__":
    train_model()
