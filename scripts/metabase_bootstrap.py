import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_COLLECTION_NAME = "Smart Logistics"
DEFAULT_DASHBOARD_NAME = "Smart Logistics Overview"

CARD_DEFINITIONS = [
    {
        "name": "KPIs Overview",
        "description": "Global logistics KPIs.",
        "display": "table",
        "query": "SELECT * FROM logistics_kpis;",
        "layout": {"row": 0, "col": 0, "size_x": 12, "size_y": 8},
    },
    {
        "name": "Ingestion Status",
        "description": "Freshness status for weather, traffic, and GPS ingestion.",
        "display": "table",
        "query": (
            "SELECT source, record_count, last_record_at, age_seconds, status, "
            "freshness_target_seconds FROM ingestion_status ORDER BY source;"
        ),
        "layout": {"row": 0, "col": 12, "size_x": 12, "size_y": 8},
    },
    {
        "name": "Business Control Tower",
        "description": "Operational business overview for dispatch decisions.",
        "display": "table",
        "query": "SELECT * FROM business_control_tower;",
        "layout": {"row": 8, "col": 0, "size_x": 12, "size_y": 8},
    },
    {
        "name": "Delivery Risk Predictions",
        "description": "Predicted delivery risk based on traffic, weather, and fleet status.",
        "display": "table",
        "query": (
            "SELECT reference, origin, destination, delivery_status, risk_score, risk_level, "
            "predicted_delay_minutes, recommendation FROM delivery_risk_predictions "
            "ORDER BY risk_score DESC, expected_arrival_time NULLS LAST, delivery_id;"
        ),
        "layout": {"row": 8, "col": 12, "size_x": 12, "size_y": 8},
    },
    {
        "name": "Latest Weather By City",
        "description": "Most recent weather snapshot for the monitored cities.",
        "display": "table",
        "query": (
            "SELECT city, temperature, humidity, weather, wind_speed, created_at "
            "FROM latest_weather_by_city ORDER BY city;"
        ),
        "layout": {"row": 16, "col": 0, "size_x": 12, "size_y": 8},
    },
    {
        "name": "Latest Traffic By Route",
        "description": "Latest traffic measurement by monitored route.",
        "display": "table",
        "query": (
            "SELECT route_name, distance_meters, duration_seconds, duration_typical_seconds, "
            "delay_seconds, created_at FROM latest_traffic_by_route ORDER BY route_name;"
        ),
        "layout": {"row": 16, "col": 12, "size_x": 12, "size_y": 8},
    },
    {
        "name": "Latest Transit By City",
        "description": "Real-time transit network status (metro, bus, tram, train) for 5 cities.",
        "display": "table",
        "query": (
            "SELECT city, region_id, total_disruptions, blocking_disruptions, "
            "network_status, most_severe_message, created_at "
            "FROM latest_transit_by_city ORDER BY city;"
        ),
        "layout": {"row": 24, "col": 0, "size_x": 24, "size_y": 8},
    },
    {
        "name": "Latest Vehicle Positions",
        "description": "Latest GPS position for each vehicle.",
        "display": "table",
        "query": (
            "SELECT vehicle_id, license_plate, driver_name, vehicle_status, latitude, longitude, "
            "speed, heading, gps_status, last_position_at FROM latest_vehicle_positions "
            "ORDER BY vehicle_id;"
        ),
        "layout": {"row": 32, "col": 0, "size_x": 12, "size_y": 8},
    },
    {
        "name": "Deliveries Status Summary",
        "description": "Current delivery summary by status.",
        "display": "table",
        "query": (
            "SELECT status, delivery_count, delayed_count, avg_cost, total_cost "
            "FROM deliveries_status_summary ORDER BY status;"
        ),
        "layout": {"row": 32, "col": 12, "size_x": 12, "size_y": 8},
    },
    {
        "name": "Weather History 24h",
        "description": "Hourly weather trend over the last 24 hours.",
        "display": "line",
        "query": (
            "SELECT date_trunc('hour', created_at) AS hour_bucket, city, "
            "ROUND(AVG(temperature)::numeric, 2) AS avg_temperature "
            "FROM weather_data WHERE created_at >= NOW() - INTERVAL '24 hours' "
            "GROUP BY hour_bucket, city ORDER BY hour_bucket DESC, city;"
        ),
        "layout": {"row": 40, "col": 0, "size_x": 24, "size_y": 8},
    },
    {
        "name": "Traffic Delay Trend 24h",
        "description": "Hourly traffic delay trend over the last 24 hours.",
        "display": "line",
        "query": (
            "SELECT date_trunc('hour', created_at) AS hour_bucket, route_name, "
            "ROUND(AVG(delay_seconds)::numeric, 2) AS avg_delay_seconds FROM traffic_data "
            "WHERE created_at >= NOW() - INTERVAL '24 hours' "
            "GROUP BY hour_bucket, route_name ORDER BY hour_bucket DESC, route_name;"
        ),
        "layout": {"row": 48, "col": 0, "size_x": 12, "size_y": 8},
    },
    {
        "name": "GPS Points Per Hour",
        "description": "Hourly GPS activity by vehicle.",
        "display": "bar",
        "query": (
            "SELECT date_trunc('hour', created_at) AS hour_bucket, "
            "('Vehicle ' || vehicle_id::text) AS vehicle_label, "
            "COUNT(*) AS gps_points_count "
            "FROM gps_tracking WHERE created_at >= NOW() - INTERVAL '24 hours' "
            "GROUP BY hour_bucket, vehicle_label ORDER BY hour_bucket DESC, vehicle_label;"
        ),
        "layout": {"row": 48, "col": 12, "size_x": 12, "size_y": 8},
    },
]


def load_dotenv(dotenv_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not dotenv_path.exists():
        return values

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


class MetabaseClient:
    def __init__(self, base_url: str, session_id: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.session_id = session_id

    def _request(self, method: str, path: str, payload: dict | list | None = None):
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        if self.session_id:
            headers["X-Metabase-Session"] = self.session_id

        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    return None
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} failed with {error.code}: {body}") from error

    def login(self, username: str, password: str) -> None:
        response = self._request("POST", "/api/session", {"username": username, "password": password})
        if not response or "id" not in response:
            raise RuntimeError("Metabase login did not return a session id")
        self.session_id = response["id"]

    def get(self, path: str):
        return self._request("GET", path)

    def post(self, path: str, payload: dict):
        return self._request("POST", path, payload)

    def put(self, path: str, payload: dict):
        return self._request("PUT", path, payload)


def get_arg_or_env(args_value: str | None, env_key: str, dotenv: dict[str, str]) -> str | None:
    return args_value or os.getenv(env_key) or dotenv.get(env_key)


def ensure_database(client: MetabaseClient, database_name: str, db_details: dict) -> int:
    databases = client.get("/api/database")
    for database in databases.get("data", []):
        if database.get("name") == database_name:
            return int(database["id"])

    created = client.post(
        "/api/database",
        {
            "engine": "postgres",
            "name": database_name,
            "details": db_details,
            "is_full_sync": True,
            "is_on_demand": False,
            "auto_run_queries": True,
        },
    )
    return int(created["id"])


def ensure_collection(client: MetabaseClient, collection_name: str) -> int:
    collections = client.get("/api/collection")
    for collection in collections:
        if collection.get("name") == collection_name and not collection.get("archived"):
            return int(collection["id"])

    created = client.post(
        "/api/collection",
        {
            "name": collection_name,
            "description": "Operational dashboards for the Smart Logistics stack.",
            "parent_id": None,
        },
    )
    return int(created["id"])


def ensure_dashboard(client: MetabaseClient, collection_id: int, dashboard_name: str) -> int:
    dashboards = client.get("/api/dashboard")
    for dashboard in dashboards:
        if dashboard.get("name") == dashboard_name and dashboard.get("collection_id") == collection_id:
            return int(dashboard["id"])

    created = client.post(
        "/api/dashboard",
        {
            "name": dashboard_name,
            "description": "Operational overview of ingestion, weather, traffic, GPS, and deliveries.",
            "collection_id": collection_id,
            "width": "fixed",
        },
    )
    return int(created["id"])


def ensure_cards(client: MetabaseClient, collection_id: int, database_id: int) -> dict[str, int]:
    items = client.get(f"/api/collection/{collection_id}/items?models=card")
    existing_cards = {item["name"]: int(item["id"]) for item in items.get("data", []) if item.get("name")}

    card_ids: dict[str, int] = {}
    for definition in CARD_DEFINITIONS:
        payload = {
            "name": definition["name"],
            "description": definition["description"],
            "display": definition["display"],
            "collection_id": collection_id,
            "visualization_settings": {},
            "dataset_query": {
                "database": database_id,
                "type": "native",
                "native": {
                    "query": definition["query"],
                    "template-tags": {},
                },
            },
        }

        if definition["name"] in existing_cards:
            card_id = existing_cards[definition["name"]]
            client.put(f"/api/card/{card_id}", payload)
            card_ids[definition["name"]] = card_id
            continue

        created = client.post("/api/card", payload)
        card_ids[definition["name"]] = int(created["id"])

    return card_ids


def sync_dashboard_layout(client: MetabaseClient, dashboard_id: int, card_ids: dict[str, int]) -> None:
    dashboard = client.get(f"/api/dashboard/{dashboard_id}")
    existing_dashcards = {
        int(dashcard["card_id"]): dashcard
        for dashcard in dashboard.get("dashcards", [])
        if dashcard.get("card_id") is not None
    }

    cards_payload = []
    next_temporary_id = -1
    for definition in CARD_DEFINITIONS:
        card_id = card_ids[definition["name"]]
        current = existing_dashcards.get(card_id, {})
        layout = definition["layout"]
        dashcard_id = current.get("id")
        if dashcard_id is None:
            dashcard_id = next_temporary_id
            next_temporary_id -= 1

        cards_payload.append(
            {
                "id": dashcard_id,
                "card_id": card_id,
                "row": layout["row"],
                "col": layout["col"],
                "size_x": layout["size_x"],
                "size_y": layout["size_y"],
                "dashboard_tab_id": None,
                "parameter_mappings": current.get("parameter_mappings", []),
                "visualization_settings": current.get("visualization_settings", {}),
            }
        )

    client.put(f"/api/dashboard/{dashboard_id}/cards", {"cards": cards_payload})


def parse_args(dotenv: dict[str, str]) -> argparse.Namespace:
    default_metabase_port = dotenv.get("METABASE_HOST_PORT", "3003")
    parser = argparse.ArgumentParser(description="Bootstrap the Smart Logistics Metabase dashboard.")
    parser.add_argument("--metabase-url", default=f"http://localhost:{default_metabase_port}")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--database-name", default="Smart Logistics")
    parser.add_argument("--postgres-host", default="postgres")
    parser.add_argument("--postgres-port", type=int, default=5432)
    parser.add_argument("--postgres-db", default=dotenv.get("POSTGRES_DB", "smart_logistics"))
    parser.add_argument("--postgres-user", default=dotenv.get("POSTGRES_USER", "postgres"))
    parser.add_argument("--postgres-password", default=dotenv.get("POSTGRES_PASSWORD", "postgres"))
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument("--dashboard-name", default=DEFAULT_DASHBOARD_NAME)
    return parser.parse_args()


def main() -> int:
    dotenv = load_dotenv(ROOT_DIR / ".env")
    args = parse_args(dotenv)

    username = get_arg_or_env(args.username, "METABASE_ADMIN_EMAIL", dotenv)
    password = get_arg_or_env(args.password, "METABASE_ADMIN_PASSWORD", dotenv)
    if not username or not password:
        print(
            "Metabase admin credentials are required. Provide --username and --password "
            "or define METABASE_ADMIN_EMAIL and METABASE_ADMIN_PASSWORD.",
            file=sys.stderr,
        )
        return 1

    client = MetabaseClient(args.metabase_url)
    client.login(username, password)

    database_id = ensure_database(
        client,
        args.database_name,
        {
            "host": args.postgres_host,
            "port": args.postgres_port,
            "dbname": args.postgres_db,
            "user": args.postgres_user,
            "password": args.postgres_password,
            "ssl": False,
            "tunnel-enabled": False,
            "advanced-options": False,
        },
    )
    collection_id = ensure_collection(client, args.collection_name)
    dashboard_id = ensure_dashboard(client, collection_id, args.dashboard_name)
    card_ids = ensure_cards(client, collection_id, database_id)
    sync_dashboard_layout(client, dashboard_id, card_ids)

    print(
        json.dumps(
            {
                "metabase_url": args.metabase_url,
                "database_id": database_id,
                "collection_id": collection_id,
                "dashboard_id": dashboard_id,
                "card_ids": card_ids,
                "dashboard_url": f"{args.metabase_url}/dashboard/{dashboard_id}-smart-logistics-overview",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())