import argparse
import json
import os
import random
import time
import urllib.error
import urllib.request


DEFAULT_VEHICLE_COORDINATES = {
    1: (48.856613, 2.352222),   # Paris        (TR-001-AA — Mamadou Diallo)
    2: (48.875000, 2.295000),   # Paris nord    (TR-002-BB — Aicha Benali)
    3: (50.629250, 3.057256),   # Lille         (TR-003-CC — Jean Kouassi)
    4: (45.764000, 4.835700),   # Lyon          (TR-004-DD — Fatou Traoré)
    5: (43.296500, 5.369800),   # Marseille     (TR-005-EE — Karim Hadj)
    6: (43.604700, 1.444200),   # Toulouse      (TR-006-FF — Sophie Martin)
    7: (43.604700, 1.444200),   # Toulouse      (TR-007-GG — Omar Diop)
    8: (43.604700, 1.444200),   # Toulouse      (TR-008-HH — Lucie Bernard)
}


def build_payload(vehicle_id: int, latitude: float, longitude: float) -> dict:
    latitude += random.uniform(-0.002, 0.002)
    longitude += random.uniform(-0.002, 0.002)
    speed = round(random.uniform(25, 90), 2)
    heading = round(random.uniform(0, 360), 2)

    return {
        "vehicle_id": vehicle_id,
        "latitude": round(latitude, 6),
        "longitude": round(longitude, 6),
        "speed": speed,
        "heading": heading,
        "status": "IN_TRANSIT",
    }


def post_payload(url: str, payload: dict, timeout: int) -> str:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send simulated GPS data to an n8n webhook.")
    parser.add_argument(
        "--url",
        default=os.getenv("GPS_WEBHOOK_URL", "http://localhost:5679/webhook/gps-tracking"),
    )
    parser.add_argument("--vehicle-id", type=int, default=1)
    parser.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float)
    parser.add_argument("--interval", type=int, default=5, help="Seconds between events")
    parser.add_argument("--count", type=int, default=12, help="Number of events to send")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument(
        "--vehicle-ids",
        type=int,
        nargs="+",
        help="Optional list of vehicle IDs to simulate in sequence",
    )
    args = parser.parse_args()

    vehicle_ids = args.vehicle_ids or [args.vehicle_id]
    vehicle_positions: dict[int, tuple[float, float]] = {}

    for vehicle_id in vehicle_ids:
        default_latitude, default_longitude = DEFAULT_VEHICLE_COORDINATES.get(vehicle_id, DEFAULT_VEHICLE_COORDINATES[1])
        latitude = args.latitude if args.latitude is not None and vehicle_id == args.vehicle_id else default_latitude
        longitude = args.longitude if args.longitude is not None and vehicle_id == args.vehicle_id else default_longitude
        vehicle_positions[vehicle_id] = (latitude, longitude)

    for index in range(args.count):
        for vehicle_id in vehicle_ids:
            latitude, longitude = vehicle_positions[vehicle_id]
            payload = build_payload(vehicle_id, latitude, longitude)
            vehicle_positions[vehicle_id] = (payload["latitude"], payload["longitude"])

            try:
                response_body = post_payload(args.url, payload, args.timeout)
                print(f"[{index + 1}/{args.count}] sent {payload} -> {response_body}")
            except urllib.error.URLError as error:
                print(f"[{index + 1}/{args.count}] failed to send payload: {error}")

        if index < args.count - 1:
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
