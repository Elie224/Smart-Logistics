"""
Collecteur GPS persistant.

Ce script publie en boucle des positions GPS vers l'API Smart Logistics et
ne s'arrete jamais sur une erreur transitoire.

Variables d'environnement :
    GPS_API_URL                — URL base de l'API (defaut: http://localhost:8000)
    GPS_INGEST_TOKEN           — token X-Ingest-Token si active
    GPS_COLLECTOR_CYCLE_SECONDS — delai entre deux cycles (defaut: 60)
    GPS_COLLECTOR_BACKOFF_MAX   — backoff max en cas d'erreur (defaut: 300)
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


DEFAULT_VEHICLE_COORDINATES = {
    1: (48.856613, 2.352222),   # Paris        (TR-001-AA)
    2: (48.875000, 2.295000),   # Paris nord    (TR-002-BB)
    3: (50.629250, 3.057256),   # Lille         (TR-003-CC)
    4: (45.764000, 4.835700),   # Lyon          (TR-004-DD)
    5: (43.296500, 5.369800),   # Marseille     (TR-005-EE)
    6: (43.604700, 1.444200),   # Toulouse      (TR-006-FF)
    7: (43.604700, 1.444200),   # Toulouse      (TR-007-GG)
    8: (43.604700, 1.444200),   # Toulouse      (TR-008-HH)
}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _api_url(path: str) -> str:
    base_url = os.getenv("GPS_API_URL", "http://localhost:8000").rstrip("/")
    return f"{base_url}{path}"


def _request_json(url: str, method: str = "GET", body: dict | None = None, timeout: int = 20) -> dict | list:
    headers = {"Content-Type": "application/json"}
    ingest_token = os.getenv("GPS_INGEST_TOKEN", "").strip()
    if ingest_token:
        headers["X-Ingest-Token"] = ingest_token

    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def fetch_vehicle_ids() -> list[int]:
    try:
        rows = _request_json(_api_url("/api/v1/vehicles"), timeout=30)
        ids = [int(row["id"]) for row in rows if row.get("id") is not None]
        if ids:
            return ids
    except Exception as exc:
        print(f"[GPS] Impossible de lire les vehicules depuis l'API : {exc}")

    return sorted(DEFAULT_VEHICLE_COORDINATES.keys())


def build_payload(vehicle_id: int, latitude: float, longitude: float) -> dict:
    latitude += random.uniform(-0.002, 0.002)
    longitude += random.uniform(-0.002, 0.002)
    return {
        "vehicle_id": vehicle_id,
        "latitude": round(latitude, 6),
        "longitude": round(longitude, 6),
        "speed": round(random.uniform(25, 90), 2),
        "heading": round(random.uniform(0, 360), 2),
        "status": "IN_TRANSIT",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def post_payload(payload: dict, timeout: int = 20) -> dict:
    return _request_json(_api_url("/api/v1/ingest/gps"), method="POST", body=payload, timeout=timeout)


def run_cycle(vehicle_positions: dict[int, tuple[float, float]], timeout: int) -> dict[int, tuple[float, float]]:
    for vehicle_id, (latitude, longitude) in list(vehicle_positions.items()):
        payload = build_payload(vehicle_id, latitude, longitude)
        try:
            response = post_payload(payload, timeout=timeout)
            vehicle_positions[vehicle_id] = (payload["latitude"], payload["longitude"])
            print(f"[GPS] vehicle={vehicle_id} ok -> {response}")
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="ignore") if error.fp else ""
            print(f"[GPS] vehicle={vehicle_id} http_error={error.code} body={body}")
        except Exception as exc:
            print(f"[GPS] vehicle={vehicle_id} error={exc}")
    return vehicle_positions


def main() -> None:
    cycle_seconds = max(_env_int("GPS_COLLECTOR_CYCLE_SECONDS", 60), 5)
    backoff_max = max(_env_int("GPS_COLLECTOR_BACKOFF_MAX", 300), cycle_seconds)
    timeout = _env_int("GPS_COLLECTOR_TIMEOUT_SECONDS", 20)

    print("[GPS] Collecteur demarre")

    vehicle_ids = fetch_vehicle_ids()
    vehicle_positions: dict[int, tuple[float, float]] = {}
    for vehicle_id in vehicle_ids:
        default_latitude, default_longitude = DEFAULT_VEHICLE_COORDINATES.get(
            vehicle_id,
            DEFAULT_VEHICLE_COORDINATES[1],
        )
        vehicle_positions[vehicle_id] = (default_latitude, default_longitude)

    failures = 0
    while True:
        try:
            vehicle_positions = run_cycle(vehicle_positions, timeout)
            failures = 0
            time.sleep(cycle_seconds)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            failures += 1
            backoff = min(backoff_max, cycle_seconds * min(failures, 6))
            print(f"[GPS] cycle error={exc} backoff={backoff}s")
            time.sleep(backoff)


if __name__ == "__main__":
    main()