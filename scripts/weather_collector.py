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


CITIES = ["Paris", "Lille", "Lyon", "Marseille", "Toulouse"]
WEATHER_BASE = "https://api.openweathermap.org/data/2.5/weather"


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


def fetch_weather(city: str, api_key: str, timeout: int = 20) -> dict:
    params = urllib.parse.urlencode({
        "q": city,
        "appid": api_key,
        "units": "metric",
        "lang": "fr",
    })
    url = f"{WEATHER_BASE}?{params}"

    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_row(city: str, payload: dict) -> tuple:
    main = payload.get("main", {})
    wind = payload.get("wind", {})
    weather_list = payload.get("weather") or []
    weather_name = weather_list[0].get("main") if weather_list else None

    stored_payload = {
        "source": "openweather",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }

    return (
        city,
        main.get("temp"),
        main.get("humidity"),
        weather_name,
        wind.get("speed"),
        json.dumps(stored_payload),
    )


def run_cycle(api_key: str) -> None:
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY absent: collecte météo réelle impossible.")

    rows = []
    for city in CITIES:
        try:
            payload = fetch_weather(city, api_key)
            rows.append(build_row(city, payload))
            temp = payload.get("main", {}).get("temp")
            print(f"  {city:10s} météo reçue ({temp}°C)")
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"OpenWeather HTTP {exc.code} pour {city}") from exc
        except Exception as exc:
            raise RuntimeError(f"OpenWeather erreur pour {city}: {exc}") from exc

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO weather_data (city, temperature, humidity, weather, wind_speed, raw_payload)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                rows,
            )
        conn.commit()
    finally:
        conn.close()

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] météo: {len(rows)} enregistrements insérés")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collecteur météo OpenWeather (réel)")
    p.add_argument("--once", action="store_true", help="Exécuter une seule fois")
    p.add_argument("--interval", type=int, default=None, help="Intervalle en secondes")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    api_key = os.getenv("OPENWEATHER_API_KEY", "")
    interval = args.interval or int(os.getenv("WEATHER_COLLECTOR_CYCLE_SECONDS", "1800"))

    if args.once:
        run_cycle(api_key)
        return

    print(f"Weather Collector démarré — cycle toutes les {interval // 60} min")
    while True:
        try:
            run_cycle(api_key)
        except Exception as exc:
            print(f"[ERROR] Cycle météo échoué: {exc}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
