import asyncio
import json
import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import get_settings
from app.database import engine, fetch_all, fetch_one, ping
from app import ml_predictor
from app import ai_assistant


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Read-only API for the Smart Logistics project foundation.",
)

# Mount static files (live map, etc.)
_STATIC_DIR = Path(__file__).parent / "static"
_STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


CITY_CENTERS = {
    "paris": (48.856613, 2.352222),
    "lille": (50.629250, 3.057256),
}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _auto_complete_deliveries_from_gps() -> int:
    """
    Clôture automatiquement une livraison IN_TRANSIT si le véhicule est arrivé
    dans la zone de destination (Paris/Lille). Permet de faire évoluer les données réelles
    sans simulation en attendant un flux OMS complet.
    """
    rows = fetch_all(
        """
        SELECT
            d.id,
            d.destination,
            d.expected_arrival_time,
            g.latitude,
            g.longitude,
            g.created_at AS gps_time
        FROM deliveries d
        JOIN (
            SELECT DISTINCT ON (vehicle_id)
                vehicle_id,
                latitude,
                longitude,
                created_at
            FROM gps_tracking
            ORDER BY vehicle_id, created_at DESC
        ) g ON g.vehicle_id = d.vehicle_id
        WHERE d.status = 'IN_TRANSIT';
        """
    )

    now = datetime.now(timezone.utc)
    updated = 0
    for row in rows:
        dest = (row.get("destination") or "").strip().lower()
        center = CITY_CENTERS.get(dest)
        if not center:
            continue

        lat = row.get("latitude")
        lon = row.get("longitude")
        if lat is None or lon is None:
            continue

        # Sécurité: on n'auto-clôture pas trop tôt par rapport à ETA prévue.
        eta = row.get("expected_arrival_time")
        if eta and hasattr(eta, "tzinfo"):
            if eta > now:
                continue

        dist_km = _haversine_km(float(lat), float(lon), center[0], center[1])
        if dist_km > 12.0:
            continue

        with engine.begin() as connection:
            result = connection.execute(
                text(
                    """
                    UPDATE deliveries
                    SET
                        status = 'DELIVERED',
                        actual_arrival_time = COALESCE(actual_arrival_time, :actual_arrival_time)
                    WHERE id = :delivery_id
                    AND status = 'IN_TRANSIT'
                    """
                ),
                {
                    "delivery_id": int(row["id"]),
                    "actual_arrival_time": row.get("gps_time") or now,
                },
            )
            if result.rowcount and result.rowcount > 0:
                updated += 1

    return updated


def _ensure_ml_feature_snapshots_table() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ml_delivery_feature_snapshots (
                    delivery_id INTEGER PRIMARY KEY,
                    departure_time TIMESTAMPTZ,
                    departure_hour INTEGER NOT NULL,
                    departure_dow INTEGER NOT NULL,
                    departure_month INTEGER NOT NULL,
                    temperature DOUBLE PRECISION NOT NULL,
                    wind_speed DOUBLE PRECISION NOT NULL,
                    traffic_delay_s DOUBLE PRECISION NOT NULL,
                    route_duration_s DOUBLE PRECISION NOT NULL,
                    transit_disruptions INTEGER NOT NULL,
                    transit_blocking INTEGER NOT NULL,
                    transit_status VARCHAR(50) NOT NULL,
                    context_city VARCHAR(100),
                    captured_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
                )
                """
            )
        )


def _upsert_ml_feature_snapshot(
    delivery_id: int,
    departure_time,
    departure_hour: int,
    departure_dow: int,
    departure_month: int,
    temperature: float,
    wind_speed: float,
    traffic_delay_s: float,
    route_duration_s: float,
    transit_disruptions: int,
    transit_blocking: int,
    transit_status: str,
    context_city: str | None,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO ml_delivery_feature_snapshots (
                    delivery_id,
                    departure_time,
                    departure_hour,
                    departure_dow,
                    departure_month,
                    temperature,
                    wind_speed,
                    traffic_delay_s,
                    route_duration_s,
                    transit_disruptions,
                    transit_blocking,
                    transit_status,
                    context_city,
                    captured_at
                )
                VALUES (
                    :delivery_id,
                    :departure_time,
                    :departure_hour,
                    :departure_dow,
                    :departure_month,
                    :temperature,
                    :wind_speed,
                    :traffic_delay_s,
                    :route_duration_s,
                    :transit_disruptions,
                    :transit_blocking,
                    :transit_status,
                    :context_city,
                    NOW()
                )
                ON CONFLICT (delivery_id)
                DO UPDATE SET
                    departure_time = EXCLUDED.departure_time,
                    departure_hour = EXCLUDED.departure_hour,
                    departure_dow = EXCLUDED.departure_dow,
                    departure_month = EXCLUDED.departure_month,
                    temperature = EXCLUDED.temperature,
                    wind_speed = EXCLUDED.wind_speed,
                    traffic_delay_s = EXCLUDED.traffic_delay_s,
                    route_duration_s = EXCLUDED.route_duration_s,
                    transit_disruptions = EXCLUDED.transit_disruptions,
                    transit_blocking = EXCLUDED.transit_blocking,
                    transit_status = EXCLUDED.transit_status,
                    context_city = EXCLUDED.context_city,
                    captured_at = NOW()
                """
            ),
            {
                "delivery_id": delivery_id,
                "departure_time": departure_time,
                "departure_hour": int(departure_hour),
                "departure_dow": int(departure_dow),
                "departure_month": int(departure_month),
                "temperature": float(temperature),
                "wind_speed": float(wind_speed),
                "traffic_delay_s": float(traffic_delay_s),
                "route_duration_s": float(route_duration_s),
                "transit_disruptions": int(transit_disruptions),
                "transit_blocking": int(transit_blocking),
                "transit_status": str(transit_status),
                "context_city": context_city,
            },
        )


@app.get("/map", include_in_schema=False)
def live_map():
    """Redirect to the live map HTML page."""
    return RedirectResponse(url="/static/map.html")


def run_query(query: str, expect_one: bool = False):
    try:
        if expect_one:
            return fetch_one(query)
        return fetch_all(query)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "prefix": settings.api_prefix,
    }


@app.get(f"{settings.api_prefix}/health")
def health() -> dict:
    try:
        database_ok = ping()
    except Exception as error:
        return {
            "status": "degraded",
            "database": False,
            "error": str(error),
        }

    return {
        "status": "ok" if database_ok else "degraded",
        "database": database_ok,
    }


@app.get(f"{settings.api_prefix}/kpis")
def get_kpis() -> dict:
    return run_query("SELECT * FROM logistics_kpis;", expect_one=True)


@app.get(f"{settings.api_prefix}/ingestion-status")
def get_ingestion_status() -> list[dict]:
    return run_query("SELECT * FROM ingestion_status ORDER BY source;")


# ---------------------------------------------------------------------------
# Config endpoint (exposes non-secret public config to frontend)
# ---------------------------------------------------------------------------

@app.get(f"{settings.api_prefix}/config")
def get_config() -> dict:
    """Returns public configuration needed by the frontend (e.g. Mapbox token)."""
    return {
        "mapbox_token": settings.mapbox_api_key,
        "paris": {"lat": 48.856613, "lon": 2.352222, "label": "Paris"},
        "lille": {"lat": 50.629250, "lon": 3.057256, "label": "Lille"},
    }


# ---------------------------------------------------------------------------
# Live vehicle positions (latest GPS fix per vehicle)
# ---------------------------------------------------------------------------

@app.get(f"{settings.api_prefix}/vehicles/positions")
def get_vehicle_positions() -> list[dict]:
    """Returns the most recent GPS position for each vehicle, with active delivery context."""
    return run_query(
        """
        SELECT DISTINCT ON (g.vehicle_id)
            g.vehicle_id,
            v.license_plate,
            v.driver_name,
            v.status        AS vehicle_status,
            g.latitude,
            g.longitude,
            g.speed,
            g.heading,
            g.created_at    AS last_seen,
            d.reference     AS delivery_reference,
            d.status        AS delivery_status,
            d.origin,
            d.destination
        FROM gps_tracking g
        JOIN vehicles v ON v.id = g.vehicle_id
        LEFT JOIN deliveries d
            ON d.vehicle_id = g.vehicle_id
            AND d.status NOT IN ('DELIVERED', 'CANCELLED')
        ORDER BY g.vehicle_id, g.created_at DESC;
        """
    )


class GpsIngestRequest(BaseModel):
    vehicle_id: int
    latitude: float
    longitude: float
    speed: float | None = None
    heading: float | None = None
    status: str | None = None
    timestamp: datetime | None = None


@app.post(f"{settings.api_prefix}/ingest/gps")
def ingest_gps_position(
    payload: GpsIngestRequest,
    x_ingest_token: Annotated[str | None, Header(alias="X-Ingest-Token")] = None,
) -> dict:
    """Ingestion GPS réel depuis traceurs (sans simulation)."""
    if settings.gps_ingest_token and x_ingest_token != settings.gps_ingest_token:
        raise HTTPException(status_code=401, detail="Invalid ingest token")

    raw_payload = {
        "source": "gps_device",
        "received_at": datetime.now(timezone.utc).isoformat(),
        "device_timestamp": payload.timestamp.isoformat() if payload.timestamp else None,
    }

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO gps_tracking (
                    vehicle_id,
                    latitude,
                    longitude,
                    speed,
                    heading,
                    status,
                    raw_payload,
                    created_at
                )
                VALUES (
                    :vehicle_id,
                    :latitude,
                    :longitude,
                    :speed,
                    :heading,
                    :status,
                    CAST(:raw_payload AS jsonb),
                    COALESCE(:created_at, NOW())
                )
                """
            ),
            {
                "vehicle_id": payload.vehicle_id,
                "latitude": payload.latitude,
                "longitude": payload.longitude,
                "speed": payload.speed,
                "heading": payload.heading,
                "status": payload.status or "IN_TRANSIT",
                "raw_payload": json.dumps(raw_payload),
                "created_at": payload.timestamp,
            },
        )

    return {"status": "ok", "message": "GPS position ingested"}


@app.get(f"{settings.api_prefix}/business/overview")
def get_business_overview() -> dict:
    return run_query("SELECT * FROM business_control_tower;", expect_one=True)


@app.get(f"{settings.api_prefix}/business/dispatch-board")
def get_dispatch_board() -> list[dict]:
    return run_query(
        "SELECT * FROM dispatch_control_board ORDER BY vehicle_id, delivery_reference NULLS LAST;"
    )


@app.get(f"{settings.api_prefix}/business/alerts")
def get_business_alerts() -> list[dict]:
    return run_query(
        """
        SELECT
            'ingestion' AS alert_type,
            source AS reference,
            status AS severity,
            'Source status is ' || status AS message,
            last_record_at AS event_time
        FROM ingestion_status
        WHERE status <> 'fresh'

        UNION ALL

        SELECT
            'delivery-risk' AS alert_type,
            reference,
            LOWER(risk_level) AS severity,
            recommendation AS message,
            expected_arrival_time AS event_time
        FROM delivery_risk_predictions
        WHERE risk_level = 'HIGH'

        ORDER BY event_time DESC NULLS LAST, alert_type;
        """
    )


@app.get(f"{settings.api_prefix}/predictions/delivery-risks")
def get_delivery_risk_predictions() -> list[dict]:
    return run_query(
        """
        SELECT *
        FROM delivery_risk_predictions
        ORDER BY risk_score DESC, expected_arrival_time NULLS LAST, delivery_id;
        """
    )


@app.get(f"{settings.api_prefix}/transit/latest")
def get_latest_transit() -> list[dict]:
    return run_query("SELECT * FROM latest_transit_by_city ORDER BY city;")


@app.get(f"{settings.api_prefix}/transit/lines")
def get_transit_lines() -> list[dict]:
    """Retourne le statut de chaque ligne (métro, RER, tram, bus, train) pour Paris et Lille."""
    return run_query("""
        SELECT city, line_type, line_name, network_status, most_severe_message
        FROM latest_transit_by_line
        ORDER BY city, line_type, line_name;
    """)


@app.get(f"{settings.api_prefix}/weather/latest")
def get_latest_weather() -> list[dict]:
    return run_query("SELECT * FROM latest_weather_by_city ORDER BY city;")


@app.get(f"{settings.api_prefix}/traffic/latest")
def get_latest_traffic() -> list[dict]:
    """Retourne les conditions de trafic par ville (Paris, Lille) avec agrégation par axe."""
    return run_query("""
        SELECT
            c.city,
            c.route_count,
            c.avg_delay_seconds,
            c.max_delay_seconds,
            c.avg_duration_seconds,
            c.traffic_status,
            c.last_updated,
            json_agg(
                json_build_object(
                    'route_name',        r.route_name,
                    'delay_seconds',     GREATEST(r.delay_seconds, 0),
                    'duration_seconds',  r.duration_seconds,
                    'created_at',        r.created_at
                ) ORDER BY r.route_name
            ) AS routes
        FROM latest_traffic_by_city c
        JOIN latest_traffic_by_route r ON r.city = c.city
        GROUP BY c.city, c.route_count, c.avg_delay_seconds, c.max_delay_seconds,
                 c.avg_duration_seconds, c.traffic_status, c.last_updated
        ORDER BY c.city;
    """)


@app.get(f"{settings.api_prefix}/vehicles")
def get_vehicles() -> list[dict]:
    return run_query("SELECT * FROM vehicles ORDER BY id;")


@app.get(f"{settings.api_prefix}/deliveries")
def get_deliveries() -> list[dict]:
    return run_query("SELECT * FROM deliveries ORDER BY created_at DESC, id DESC;")


@app.get(f"{settings.api_prefix}/operations")
def get_operations() -> list[dict]:
    return run_query(
        """
        SELECT
            v.id AS vehicle_id,
            v.license_plate,
            v.driver_name,
            v.status AS vehicle_status,
            d.reference AS delivery_reference,
            d.origin,
            d.destination,
            d.status AS delivery_status,
            d.delayed,
            d.expected_arrival_time,
            d.actual_arrival_time
        FROM vehicles v
        LEFT JOIN deliveries d ON d.vehicle_id = v.id
        ORDER BY v.id, d.created_at DESC NULLS LAST;
        """
    )


# ---------------------------------------------------------------------------
# Endpoints ML — Prédiction de retard (régression logistique)
# ---------------------------------------------------------------------------

@app.get(f"{settings.api_prefix}/predictions/ml-model-info")
def get_ml_model_info() -> dict:
    """Métadonnées du modèle ML entraîné (features, AUC, date d'entraînement)."""
    return ml_predictor.get_model_meta()


@app.get(f"{settings.api_prefix}/predictions/ml-delay-risk")
def get_ml_delay_risk() -> list[dict]:
    """
    Prédit le risque de retard pour chaque livraison active (IN_TRANSIT ou PLANNED)
    en utilisant le contexte météo + trafic + transit en temps réel.
    """
    _auto_complete_deliveries_from_gps()

    # Contexte temps réel
    weather  = fetch_all("SELECT city, temperature, wind_speed FROM latest_weather_by_city")
    traffic  = fetch_all(
        "SELECT city, avg_delay_seconds, avg_duration_seconds FROM latest_traffic_by_city"
    )
    TC_CITIES = {"paris", "lille"}   # TC surveillé uniquement à Paris & Lille
    transit  = fetch_all(
        "SELECT city, network_status, total_disruptions, blocking_disruptions "
        "FROM latest_transit_by_city WHERE city IN ('Paris', 'Lille')"
    )
    deliveries = fetch_all(
        "SELECT id, reference, origin, destination, departure_time, "
        "expected_arrival_time, status "
        "FROM deliveries WHERE status IN ('IN_TRANSIT', 'PLANNED') "
        "AND (origin IN ('Paris', 'Lille') OR destination IN ('Paris', 'Lille'))"
    )

    # Index par ville
    weather_map  = {row["city"].lower(): row for row in weather}
    transit_map  = {row["city"].lower(): row for row in transit}
    traffic_map  = {row["city"].lower(): row for row in traffic}

    now = datetime.now(timezone.utc)
    _ensure_ml_feature_snapshots_table()

    results = []
    for d in deliveries:
        dest   = (d.get("destination") or "").lower()
        origin = (d.get("origin")      or "").lower()

        # Ville de contexte opérationnel (trafic/TC/météo): Paris ou Lille
        # Priorité à l'origine, sinon destination.
        context_city = origin if origin in TC_CITIES else dest if dest in TC_CITIES else origin or dest

        w  = weather_map.get(context_city, {})
        # TC disponible uniquement pour Paris & Lille
        t  = transit_map.get(context_city, {}) if context_city in TC_CITIES else {}
        tr = traffic_map.get(context_city, {})

        dep_time = d.get("departure_time") or now
        if hasattr(dep_time, "hour"):
            dep_hour = dep_time.hour
            dep_dow  = dep_time.weekday()   # 0=lundi
            dep_month = dep_time.month
        else:
            dep_hour = now.hour
            dep_dow  = now.weekday()
            dep_month = now.month

        # Durée de trajet : depuis expected_arrival - departure si dispo, sinon DB
        route_duration_s = 1800.0
        exp_arr = d.get("expected_arrival_time")
        if exp_arr and dep_time and hasattr(exp_arr, "hour"):
            diff = (exp_arr - dep_time).total_seconds()
            if diff > 0:
                route_duration_s = float(diff)
        elif tr.get("avg_duration_seconds"):
            route_duration_s = float(tr["avg_duration_seconds"])

        prediction = ml_predictor.predict_delay_risk(
            departure_hour      = dep_hour,
            departure_dow       = dep_dow,
            temperature         = float(w.get("temperature") or 12.0),
            wind_speed          = float(w.get("wind_speed")  or 3.0),
            traffic_delay_s     = float(tr.get("avg_delay_seconds") or 0),
            transit_disruptions = int(t.get("total_disruptions")    or 0),
            transit_blocking    = int(t.get("blocking_disruptions") or 0),
            transit_status      = str(t.get("network_status") or "NORMAL"),
            route_duration_s    = route_duration_s,
        )

        # Capture des features réelles pour futur training (quand la livraison sera DELIVERED).
        _upsert_ml_feature_snapshot(
            delivery_id=d["id"],
            departure_time=d.get("departure_time"),
            departure_hour=dep_hour,
            departure_dow=dep_dow,
            departure_month=dep_month,
            temperature=float(w.get("temperature") or 12.0),
            wind_speed=float(w.get("wind_speed") or 3.0),
            traffic_delay_s=float(tr.get("avg_delay_seconds") or 0),
            route_duration_s=route_duration_s,
            transit_disruptions=int(t.get("total_disruptions") or 0),
            transit_blocking=int(t.get("blocking_disruptions") or 0),
            transit_status=str(t.get("network_status") or "NORMAL"),
            context_city=context_city.capitalize() if context_city else None,
        )

        if prediction is None:
            prediction = {
                "delay_probability": None,
                "risk_level":        "UNKNOWN",
                "risk_factors":      [],
                "recommendation":    "Modèle ML pas encore entraîné.",
                "predicted_at":      now.isoformat(),
            }

        results.append({
            "delivery_id":           d["id"],
            "reference":             d["reference"],
            "origin":                d["origin"],
            "destination":           d["destination"],
            "context_city":          context_city.capitalize() if context_city else None,
            "status":                d["status"],
            "expected_arrival_time": d.get("expected_arrival_time"),
            **prediction,
        })

    # Tri : HIGH en premier
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNKNOWN": 3}
    results.sort(key=lambda r: order.get(r["risk_level"], 9))
    return results


@app.post(f"{settings.api_prefix}/predictions/ml-reload")
def reload_ml_model() -> dict:
    """Recharge le modèle ML depuis le disque (après un nouvel entraînement)."""
    ok = ml_predictor.reload_model()
    if ok:
        return {"status": "ok", "message": "Modèle rechargé avec succès."}
    return {"status": "unavailable", "message": "Aucun modèle trouvé."}


@app.post(f"{settings.api_prefix}/predictions/ml-train")
def train_ml_model(
    x_train_token: Annotated[str | None, Header(alias="X-Train-Token")] = None,
) -> dict:
    """Entraîne le modèle puis le recharge (endpoint prévu pour un job planifié)."""
    if not settings.ml_train_token:
        raise HTTPException(status_code=503, detail="ML_TRAIN_TOKEN n'est pas configuré.")
    if x_train_token != settings.ml_train_token:
        raise HTTPException(status_code=401, detail="Invalid train token")

    try:
        proc = subprocess.run(
            ["python", "/app/scripts/ml_trainer.py"],
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail=f"Training timeout: {exc}") from exc

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise HTTPException(status_code=500, detail=f"Training failed: {err[-1000:]}")

    # Recharge le modèle si un modèle a bien été produit.
    ml_predictor.reload_model()
    meta = ml_predictor.get_model_meta()

    return {
        "status": "ok",
        "message": "Training terminé.",
        "meta": meta,
        "train_log_tail": (proc.stdout or "")[-1200:],
    }


# ---------------------------------------------------------------------------
# Assistant IA conversationnel — Shamar
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []

class ChatResponse(BaseModel):
    reply: str


@app.post(f"{settings.api_prefix}/chat")
async def chat(body: ChatRequest) -> ChatResponse:
    """
    Envoie un message à Shamar (Assistant IA) avec contexte temps réel complet.
    L'historique de conversation est fourni par le client.
    """
    try:
        history = [{"role": m.role, "content": m.content} for m in body.history]
        reply = await ai_assistant.answer(body.message, history)
        return ChatResponse(reply=reply)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(f"{settings.api_prefix}/chat/stream")
async def chat_stream(body: ChatRequest):
    """
    Streaming SSE — Shamar répond token par token (text/event-stream).
    Format : data: {"token": "..."} puis data: [DONE]
    """
    history = [{"role": m.role, "content": m.content} for m in body.history]

    async def generate():
        try:
            async for token in ai_assistant.stream_answer(body.message, history):
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# WebSocket — Flux temps réel (alertes TC, trafic, météo)
# ---------------------------------------------------------------------------

@app.websocket(f"{settings.api_prefix}/ws/live")
async def websocket_live(websocket: WebSocket):
    """
    WebSocket temps réel — pousse un snapshot + alertes de changement toutes les 8 secondes.
    Payload JSON: { type, timestamp, alerts: [...], snapshot: { transit, traffic, weather } }
    """
    await websocket.accept()
    prev_disrupted: set[str] = set()
    prev_congested: set[str] = set()
    try:
        while True:
            now_iso = datetime.now(timezone.utc).isoformat()
            try:
                transit_lines = fetch_all(
                    "SELECT city, line_name, network_status "
                    "FROM latest_transit_by_line ORDER BY city, line_name"
                )
                traffic_rows = fetch_all(
                    "SELECT city, traffic_status, avg_delay_seconds "
                    "FROM latest_traffic_by_city"
                )
                weather_rows = fetch_all(
                    "SELECT city, temperature, wind_speed FROM latest_weather_by_city"
                )
            except Exception:
                await asyncio.sleep(8)
                continue

            # Sets for change detection
            curr_disrupted = {
                f"{r['city']}/{r['line_name']}"
                for r in transit_lines if r.get("network_status") == "DISRUPTED"
            }
            curr_congested = {
                r["city"] for r in traffic_rows if r.get("traffic_status") == "CONGESTED"
            }

            alerts: list[dict] = []
            for key in curr_disrupted - prev_disrupted:
                city, line = key.split("/", 1)
                alerts.append({"level": "critical", "icon": "🚨", "source": "transit",
                                "message": f"{line} perturbée ({city})"})
            for key in prev_disrupted - curr_disrupted:
                city, line = key.split("/", 1)
                alerts.append({"level": "info", "icon": "✅", "source": "transit",
                                "message": f"{line} rétablie ({city})"})
            for city in curr_congested - prev_congested:
                alerts.append({"level": "warning", "icon": "🚦", "source": "traffic",
                                "message": f"Trafic congestionné à {city}"})
            for city in prev_congested - curr_congested:
                alerts.append({"level": "info", "icon": "🟢", "source": "traffic",
                                "message": f"Trafic fluidifié à {city}"})

            prev_disrupted = curr_disrupted
            prev_congested = curr_congested

            snapshot = {
                "transit": {
                    "disrupted": len(curr_disrupted),
                    "reduced": sum(1 for r in transit_lines if r.get("network_status") == "REDUCED"),
                    "normal":   sum(1 for r in transit_lines if r.get("network_status") == "NORMAL"),
                },
                "traffic": {r["city"]: r.get("traffic_status", "UNKNOWN") for r in traffic_rows},
                "weather": {
                    r["city"]: {
                        "temp": round(float(r.get("temperature") or 0), 1),
                        "wind": round(float(r.get("wind_speed")  or 0), 1),
                    }
                    for r in weather_rows
                },
            }

            await websocket.send_json({
                "type":      "live",
                "timestamp": now_iso,
                "alerts":    alerts,
                "snapshot":  snapshot,
            })
            await asyncio.sleep(8)

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
