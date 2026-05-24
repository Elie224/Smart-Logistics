"""
Traffic Collector — collecte les données de trafic urbain en temps réel
via l'API Mapbox Directions pour Paris et Lille.

Surveille 4 axes logistiques clés :
  - Paris  : Périphérique Nord + Axe La Défense → Nation
  - Lille  : Grand Boulevard  + Centre → Villeneuve-d'Ascq

Usage:
    python traffic_collector.py [--once] [--interval S]

Variables d'environnement:
    MAPBOX_API_KEY      — token Mapbox (requis pour les données réelles)
    POSTGRES_HOST       — hôte PostgreSQL  (défaut: localhost)
    POSTGRES_PORT       — port PostgreSQL  (défaut: 5432)
    POSTGRES_DB         — nom de la base   (défaut: smart_logistics)
    POSTGRES_USER       — utilisateur      (défaut: postgres)
    POSTGRES_PASSWORD   — mot de passe     (défaut: postgres)
    TRAFFIC_COLLECTOR_CYCLE_SECONDS — intervalle entre deux collectes (défaut: 1800)
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

try:
    import psycopg2
except ImportError:
    raise SystemExit("psycopg2 est requis : pip install psycopg2-binary")


# ---------------------------------------------------------------------------
# Axes de trafic urbain à surveiller
# (city, route_name, origin_lon, origin_lat, dest_lon, dest_lat)
# ---------------------------------------------------------------------------
CITY_ROUTES = [
    {
        "city":        "Paris",
        "route_name":  "Paris - Périphérique Nord",
        "origin_lat":  48.8929, "origin_lon":  2.3522,
        "dest_lat":    48.8481, "dest_lon":    2.4390,
    },
    {
        "city":        "Paris",
        "route_name":  "Paris - Axe La Défense → Nation",
        "origin_lat":  48.8921, "origin_lon":  2.2382,
        "dest_lat":    48.8484, "dest_lon":    2.3954,
    },
    {
        "city":        "Lille",
        "route_name":  "Lille - Grand Boulevard",
        "origin_lat":  50.6942, "origin_lon":  3.1789,
        "dest_lat":    50.6282, "dest_lon":    3.0544,
    },
    {
        "city":        "Lille",
        "route_name":  "Lille - Centre → Villeneuve-d'Ascq",
        "origin_lat":  50.6282, "origin_lon":  3.0544,
        "dest_lat":    50.6175, "dest_lon":    3.1417,
    },
]

TYPICAL_DURATIONS = {
    "Paris - Périphérique Nord":         1380,
    "Paris - Axe La Défense → Nation":   1920,
    "Lille - Grand Boulevard":            900,
    "Lille - Centre → Villeneuve-d'Ascq": 660,
}

MAPBOX_BASE = "https://api.mapbox.com/directions/v5/mapbox/driving-traffic"


# ---------------------------------------------------------------------------
# Appel Mapbox
# ---------------------------------------------------------------------------
def fetch_mapbox(route: dict, token: str, timeout: int = 15) -> dict | None:
    """Appelle l'API Mapbox Directions (driving-traffic) pour un axe donné.
    Renvoie le dict 'route[0]' de la réponse, ou None en cas d'erreur."""
    coords = f"{route['origin_lon']},{route['origin_lat']};{route['dest_lon']},{route['dest_lat']}"
    params = urllib.parse.urlencode({
        "access_token": token,
        "annotations":  "duration,distance,speed",
        "overview":     "full",
        "steps":        "false",
    })
    url = f"{MAPBOX_BASE}/{coords}?{params}"

    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            routes = data.get("routes") or []
            if routes:
                return {"route": routes[0], "raw": data}
            print(f"  [WARN] Mapbox — aucune route retournée pour {route['route_name']}")
            return None
    except urllib.error.HTTPError as exc:
        print(f"  [ERROR] Mapbox HTTP {exc.code} pour {route['route_name']}: {exc.reason}")
        return None
    except Exception as exc:
        print(f"  [ERROR] Mapbox pour {route['route_name']}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Construction du payload DB
# ---------------------------------------------------------------------------
def build_record(route: dict, result: dict) -> dict:
    r = result["route"]
    duration = r.get("duration") or 0
    typical  = r.get("duration_typical") or duration
    delay    = max(0, duration - typical)

    return {
        "city":                    route["city"],
        "route_name":              route["route_name"],
        "origin_latitude":         route["origin_lat"],
        "origin_longitude":        route["origin_lon"],
        "destination_latitude":    route["dest_lat"],
        "destination_longitude":   route["dest_lon"],
        "distance_meters":         r.get("distance") or 0,
        "duration_seconds":        duration,
        "duration_typical_seconds": typical,
        "delay_seconds":           delay,
        "raw_payload":             json.dumps(result["raw"]),
    }


# ---------------------------------------------------------------------------
# Connexion PostgreSQL
# ---------------------------------------------------------------------------
def get_connection():
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5433" if host in ("localhost", "127.0.0.1") else "5432"))
    sslmode = os.getenv("POSTGRES_SSLMODE", "prefer")
    return psycopg2.connect(
        host=host,
        port=port,
        dbname=os.getenv("POSTGRES_DB", "smart_logistics"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        sslmode=sslmode,
    )


INSERT_SQL = """
INSERT INTO traffic_data (
    city, route_name,
    origin_latitude, origin_longitude,
    destination_latitude, destination_longitude,
    distance_meters, duration_seconds, duration_typical_seconds,
    delay_seconds, raw_payload
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
"""


def insert_records(records: list[dict]) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for rec in records:
                cur.execute(INSERT_SQL, (
                    rec["city"],
                    rec["route_name"],
                    rec["origin_latitude"],
                    rec["origin_longitude"],
                    rec["destination_latitude"],
                    rec["destination_longitude"],
                    rec["distance_meters"],
                    rec["duration_seconds"],
                    rec["duration_typical_seconds"],
                    rec["delay_seconds"],
                    rec["raw_payload"],
                ))
        conn.commit()
        print(f"  [OK] {len(records)} enregistrement(s) stocké(s) en base.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Cycle de collecte
# ---------------------------------------------------------------------------
def run_cycle(mapbox_token: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n[{ts}] Collecte du trafic urbain France (multi-villes)")

    if not mapbox_token:
        raise RuntimeError("MAPBOX_API_KEY absent: collecte trafic réelle impossible.")

    records: list[dict] = []

    for route in CITY_ROUTES:
        result = fetch_mapbox(route, mapbox_token)
        if result is None:
            raise RuntimeError(f"Collecte trafic incomplète: échec Mapbox pour {route['route_name']}")

        if result["route"].get("duration_typical") in (None, 0):
            result["route"]["duration_typical"] = TYPICAL_DURATIONS.get(route["route_name"], result["route"].get("duration") or 0)

        rec = build_record(route, result)
        delay_min = round(rec["delay_seconds"] / 60)
        dur_min   = round(rec["duration_seconds"] / 60)
        print(f"  {route['city']:6s}  {route['route_name']:<45s}  "
              f"durée {dur_min:3d} min  retard +{delay_min:2d} min  [Mapbox]")

        records.append(rec)

    insert_records(records)


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collecteur de trafic Mapbox pour le réseau France.")
    p.add_argument("--once",     action="store_true", help="Exécuter une seule fois et quitter.")
    p.add_argument("--interval", type=int, default=None,
                   help="Secondes entre deux collectes (défaut: TRAFFIC_COLLECTOR_CYCLE_SECONDS ou 1800).")
    return p.parse_args()


def main() -> None:
    args    = parse_args()
    token   = os.getenv("MAPBOX_API_KEY", "")
    interval = args.interval or int(os.getenv("TRAFFIC_COLLECTOR_CYCLE_SECONDS", "1800"))

    if args.once:
        run_cycle(token)
        return

    print(f"Traffic Collector démarré — cycle toutes les {interval // 60} min.")
    while True:
        try:
            run_cycle(token)
        except Exception as exc:
            print(f"[ERROR] Cycle échoué : {exc}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
