"""
Ingestion transit — données réelles pour Paris et Lille.

Sources réelles:
- Paris : IDFM Prim estimated-timetable (SIRI JSON, clé API requise)
- Lille : ILEVIA GTFS-RT trip-updates (protobuf via proxy transport.data.gouv.fr)

Env vars:
    IDFM_API_KEY            — token PRIM (obligatoire pour Paris réel)
    POSTGRES_HOST / PORT / DB / USER / PASSWORD
"""

import json
import os
import time
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone

try:
    import psycopg2
except ImportError:
    raise SystemExit("psycopg2 requis : pip install psycopg2-binary")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

IDFM_API_KEY = os.getenv("IDFM_API_KEY", "")
IDFM_ET_URL = "https://prim.iledefrance-mobilites.fr/marketplace/estimated-timetable"


# Seuils de retard (secondes)
DELAY_MINOR_S = 300   # > 5 min  → perturbation mineure
DELAY_MAJOR_S = 900   # > 15 min → perturbation bloquante

# ---------------------------------------------------------------------------
# Ingestion Paris via IDFM Prim API
# ---------------------------------------------------------------------------

def _parse_iso(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def _analyze_raw_bytes(raw: bytes) -> dict | None:
    """
    Analyse par regex sur un échantillon de bytes SIRI.
    Cherche les paires (AimedDepartureTime, ExpectedDepartureTime) au sein
    du même objet EstimatedCall (les deux apparaissent à moins de 800 chars d'intervalle).
    """
    import re
    text = raw.decode("utf-8", errors="replace")

    # Cherche AimedDepartureTime suivi de ExpectedDepartureTime dans le même bloc JSON
    pattern = re.compile(
        r'"AimedDepartureTime"\s*:\s*"([^"]+)"'
        r'.{0,800}?'
        r'"ExpectedDepartureTime"\s*:\s*"([^"]+)"',
        re.DOTALL,
    )

    delayed = 0
    blocked = 0
    total_pairs = 0

    for m in pattern.finditer(text):
        a = _parse_iso(m.group(1))
        e = _parse_iso(m.group(2))
        if a and e:
            total_pairs += 1
            delay_s = (e - a).total_seconds()
            if delay_s > DELAY_MINOR_S:
                delayed += 1
            if delay_s > DELAY_MAJOR_S:
                blocked += 1

    if total_pairs == 0:
        print("[IDFM] Aucune paire de temps trouvée dans l'échantillon.")
        return None

    delay_pct = round(delayed / total_pairs * 100, 1)
    if delay_pct > 20:
        network_status = "DISRUPTED"
    elif delay_pct > 5:
        network_status = "REDUCED"
    else:
        network_status = "NORMAL"

    print(
        f"[IDFM] Échantillon Paris: {total_pairs} appels analysés, "
        f"{delayed} retards ({delay_pct}%) → {network_status}"
    )

    msg = f"Paris: {delayed}/{total_pairs} véhicules en retard (données réelles IDFM)" if delayed > 0 else None

    return {
        "city": "Paris",
        "region_id": "fr-idf",
        "total_disruptions": delayed,
        "blocking_disruptions": blocked,
        "network_status": network_status,
        "most_severe_message": msg,
        "raw_payload": json.dumps({
            "source": "idfm_prim_sample",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "sample_size_mb": round(len(raw) / 1_000_000, 1),
            "pairs_analyzed": total_pairs,
            "delayed": delayed,
            "blocked": blocked,
            "delay_pct": delay_pct,
        }),
    }


def fetch_paris_idfm() -> dict | None:
    """
    Appelle l'API PRIM estimated-timetable et calcule l'état du réseau Paris.
    Retourne un dict compatible transit_data, ou None en cas d'erreur.
    """
    if not IDFM_API_KEY:
        print("[IDFM] Pas de IDFM_API_KEY — impossible de collecter Paris en réel.")
        return None

    req = urllib.request.Request(
        IDFM_ET_URL,
        headers={"apikey": IDFM_API_KEY, "Accept": "application/json"},
    )
    print(f"[IDFM] Appel API → {IDFM_ET_URL}")

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            # Lire seulement les 5 premiers MB comme échantillon représentatif
            raw = resp.read(5_000_000)
    except urllib.error.HTTPError as e:
        print(f"[IDFM] HTTP {e.code}: {e.reason}")
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"[IDFM] Connexion échouée: {e}")
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Réponse tronquée (>5MB) — analyse par regex sur l'échantillon
        print("[IDFM] Réponse SIRI > 5 MB — analyse par échantillon (regex)")
        return _analyze_raw_bytes(raw)

    # --- Parcours de la réponse SIRI ET ---
    try:
        deliveries = (
            data["Siri"]["ServiceDelivery"]["EstimatedTimetableDelivery"]
        )
    except (KeyError, TypeError):
        print("[IDFM] Structure SIRI inattendue.")
        return None

    total_journeys = 0
    delayed_journeys = 0
    blocked_journeys = 0
    top_messages: list[str] = []

    for delivery in deliveries:
        for frame in delivery.get("EstimatedJourneyVersionFrame", []):
            for journey in frame.get("EstimatedVehicleJourney", []):
                total_journeys += 1
                max_delay_s: float = 0.0
                line_ref = journey.get("LineRef", {}).get("value", "?")

                calls = journey.get("EstimatedCalls", {}).get("EstimatedCall", [])
                for call in calls[:10]:  # analyse les 10 premiers arrêts
                    aimed = _parse_iso(call.get("AimedDepartureTime") or call.get("AimedArrivalTime"))
                    expected = _parse_iso(call.get("ExpectedDepartureTime") or call.get("ExpectedArrivalTime"))
                    if aimed and expected:
                        delay_s = (expected - aimed).total_seconds()
                        if delay_s > max_delay_s:
                            max_delay_s = delay_s

                if max_delay_s > DELAY_MINOR_S:
                    delayed_journeys += 1
                    delay_min = int(max_delay_s / 60)
                    if max_delay_s > DELAY_MAJOR_S:
                        blocked_journeys += 1
                        if len(top_messages) < 3:
                            top_messages.append(f"Ligne {line_ref}: retard {delay_min} min")

    print(
        f"[IDFM] Paris: {total_journeys} voyages analysés, "
        f"{delayed_journeys} en retard, {blocked_journeys} bloquants."
    )

    if total_journeys == 0:
        network_status = "NORMAL"
        delay_pct = 0.0
    else:
        delay_pct = round(delayed_journeys / total_journeys * 100, 1)
        if delay_pct > 20:
            network_status = "DISRUPTED"
        elif delay_pct > 5:
            network_status = "REDUCED"
        else:
            network_status = "NORMAL"

    msg = top_messages[0] if top_messages else None

    return {
        "city": "Paris",
        "region_id": "fr-idf",
        "total_disruptions": delayed_journeys,
        "blocking_disruptions": blocked_journeys,
        "network_status": network_status,
        "most_severe_message": msg,
        "raw_payload": json.dumps({
            "source": "idfm_prim",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_journeys": total_journeys,
            "delayed_journeys": delayed_journeys,
            "blocked_journeys": blocked_journeys,
            "delay_pct": delay_pct,
            "top_messages": top_messages,
        }),
    }


def paris_snapshot() -> dict:
    """Collecte Paris en réel (IDFM), échoue si indisponible."""
    result = fetch_paris_idfm()
    if result is None:
        raise RuntimeError("IDFM indisponible pour Paris")
    return result





# ---------------------------------------------------------------------------
# Ingestion Lille via ILEVIA GTFS-RT (protobuf, proxy transport.data.gouv.fr)
# ---------------------------------------------------------------------------

LILLE_GTFS_RT_URL = "https://proxy.transport.data.gouv.fr/resource/ilevia-lille-gtfs-rt"

# Seuils retard (secondes) — cohérents avec les constantes Paris
_DELAY_MINOR = DELAY_MINOR_S    # 300s = 5 min
_DELAY_MAJOR = DELAY_MAJOR_S    # 900s = 15 min


# ---------------------------------------------------------------------------
# Ingestion Lille via ILEVIA GTFS-RT (protobuf, proxy transport.data.gouv.fr)
# ---------------------------------------------------------------------------

LILLE_GTFS_RT_URL = "https://proxy.transport.data.gouv.fr/resource/ilevia-lille-gtfs-rt"

# Seuils retard (secondes) — cohérents avec les constantes Paris
_DELAY_MINOR = DELAY_MINOR_S    # 300s = 5 min
_DELAY_MAJOR = DELAY_MAJOR_S    # 900s = 15 min


def fetch_lille_gtfs_rt() -> dict | None:
    """
    Récupère et parse le feed GTFS-RT ILEVIA (Lille Métropole).
    Utilise gtfs-realtime-bindings pour décoder le protobuf.
    """
    try:
        from google.transit import gtfs_realtime_pb2
    except ImportError:
        print("[Lille] gtfs-realtime-bindings non disponible — impossible en réel.")
        return None

    req = urllib.request.Request(
        LILLE_GTFS_RT_URL,
        headers={"User-Agent": "SmartLogistics/1.0"},
    )
    print(f"[Lille] Appel GTFS-RT → {LILLE_GTFS_RT_URL}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read(5_000_000)
    except urllib.error.HTTPError as e:
        print(f"[Lille] HTTP {e.code}: {e.reason}")
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"[Lille] Connexion échouée: {e}")
        return None

    # Parser le protobuf
    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(raw)
    except Exception as e:
        print(f"[Lille] Erreur parsing protobuf: {e}")
        return None

    total_trips = 0
    delayed_trips = 0
    blocking_trips = 0
    top_delays: list[int] = []

    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        total_trips += 1
        max_delay = 0
        for stu in entity.trip_update.stop_time_update:
            dep_delay = 0
            arr_delay = 0
            if stu.HasField("departure"):
                dep_delay = stu.departure.delay  # secondes
            if stu.HasField("arrival"):
                arr_delay = stu.arrival.delay
            max_delay = max(max_delay, dep_delay, arr_delay)

        if max_delay > _DELAY_MINOR:
            delayed_trips += 1
            top_delays.append(max_delay)
        if max_delay > _DELAY_MAJOR:
            blocking_trips += 1

    print(
        f"[Lille] GTFS-RT: {total_trips} voyages, "
        f"{delayed_trips} retardés, {blocking_trips} bloquants"
    )

    if total_trips == 0:
        network_status = "NORMAL"
        delay_pct = 0.0
    else:
        delay_pct = round(delayed_trips / total_trips * 100, 1)
        if delay_pct > 20:
            network_status = "DISRUPTED"
        elif delay_pct > 5:
            network_status = "REDUCED"
        else:
            network_status = "NORMAL"

    avg_delay = int(sum(top_delays) / len(top_delays)) if top_delays else 0
    msg = (
        f"Lille: {delayed_trips}/{total_trips} trajets en retard "
        f"(retard moy. {avg_delay // 60} min)"
        if delayed_trips > 0
        else None
    )

    return {
        "city": "Lille",
        "region_id": "fr-hdf",
        "total_disruptions": delayed_trips,
        "blocking_disruptions": blocking_trips,
        "network_status": network_status,
        "most_severe_message": msg,
        "raw_payload": json.dumps({
            "source": "gtfs_rt_ilevia",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_trips": total_trips,
            "delayed_trips": delayed_trips,
            "blocking_trips": blocking_trips,
            "delay_pct": delay_pct if total_trips > 0 else 0.0,
        }),
    }


def lille_snapshot() -> dict:
    """Collecte Lille en réel (GTFS-RT), échoue si indisponible."""
    result = fetch_lille_gtfs_rt()
    if result is None:
        raise RuntimeError("GTFS-RT Lille indisponible")
    return result


# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------

def get_connection():
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT",
                         "5433" if host in ("localhost", "127.0.0.1") else "5432"))
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
INSERT INTO transit_data
    (city, region_id, total_disruptions, blocking_disruptions,
     network_status, most_severe_message, raw_payload)
VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
"""


def insert_snapshots(snapshots: list[dict]) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for s in snapshots:
                cur.execute(INSERT_SQL, (
                    s["city"],
                    s["region_id"],
                    s["total_disruptions"],
                    s["blocking_disruptions"],
                    s["network_status"],
                    s["most_severe_message"],
                    s["raw_payload"],
                ))
        conn.commit()
        print(f"[DB] {len(snapshots)} lignes insérées dans transit_data.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def run_once() -> None:
    snapshots: list[dict] = []

    # Paris : API IDFM réelle
    snapshots.append(paris_snapshot())

    # Lille : GTFS-RT ILEVIA réel
    snapshots.append(lille_snapshot())

    insert_snapshots(snapshots)

    # Résumé
    for s in snapshots:
        src = json.loads(s["raw_payload"]).get("source", "?")
        print(
            f"  [{s['city']:10s}] {s['network_status']:10s} | "
            f"perturbations: {s['total_disruptions']:2d} "
            f"(bloquantes: {s['blocking_disruptions']}) | source: {src}"
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collecteur transit réel (Paris/Lille)")
    p.add_argument("--once", action="store_true", help="Exécuter une seule fois")
    p.add_argument("--interval", type=int, default=None, help="Intervalle en secondes")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    interval = args.interval or int(os.getenv("TRANSIT_COLLECTOR_CYCLE_SECONDS", "1800"))

    if args.once:
        run_once()
        return

    print(f"Transit collector réel démarré — cycle toutes les {interval // 60} min")
    while True:
        try:
            run_once()
        except Exception as exc:
            print(f"[ERROR] Cycle transit échoué : {exc}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
