"""
Transit simulator — génère des données de statut ligne par ligne
pour Paris et Lille (métro, RER, Transilien, tramway, bus, TER).

Usage:
    python transit_simulator.py [--count N] [--interval S]

Variables d'environnement:
    TRANSIT_DB_URL   — URL SQLAlchemy complète (prioritaire)
    POSTGRES_HOST    — hôte PostgreSQL (défaut: localhost)
    POSTGRES_PORT    — port PostgreSQL (défaut: 5433)
    POSTGRES_DB      — nom de la base (défaut: smart_logistics)
    POSTGRES_USER    — utilisateur (défaut: postgres)
    POSTGRES_PASSWORD— mot de passe (défaut: postgres)
"""

import argparse
import json
import os
import random
import time
from datetime import datetime, timezone

try:
    import psycopg2
except ImportError:
    raise SystemExit("psycopg2 est requis : pip install psycopg2-binary")

# ---------------------------------------------------------------------------
# Lignes de référence
# ---------------------------------------------------------------------------

PARIS_LINES = [
    # ── Métro (5 plus fréquentés) ──────────────────────────────────────────
    {"line_name": "M1",    "line_type": "Métro",   "busy": True},
    {"line_name": "M4",    "line_type": "Métro",   "busy": True},
    {"line_name": "M6",    "line_type": "Métro",   "busy": False},
    {"line_name": "M13",   "line_type": "Métro",   "busy": True},
    {"line_name": "M14",   "line_type": "Métro",   "busy": True},
    # ── RER (tous) ─────────────────────────────────────────────────────────
    {"line_name": "RER A", "line_type": "RER",     "busy": True},
    {"line_name": "RER B", "line_type": "RER",     "busy": True},
    {"line_name": "RER C", "line_type": "RER",     "busy": False},
    {"line_name": "RER D", "line_type": "RER",     "busy": True},
    {"line_name": "RER E", "line_type": "RER",     "busy": False},
    # ── Tramway (2 lignes) ─────────────────────────────────────────────────
    {"line_name": "T3a",   "line_type": "Tramway", "busy": True},
    {"line_name": "T3b",   "line_type": "Tramway", "busy": False},
    # ── Bus (3 lignes) ─────────────────────────────────────────────────────
    {"line_name": "Bus 38","line_type": "Bus",     "busy": True},
    {"line_name": "Bus 63","line_type": "Bus",     "busy": False},
    {"line_name": "Bus 95","line_type": "Bus",     "busy": True},
]

LILLE_LINES = [
    # ── Métro VAL ──────────────────────────────────────────────────────────
    {"line_name": "M1",       "line_type": "Métro",   "busy": True},
    {"line_name": "M2",       "line_type": "Métro",   "busy": True},
    # ── Tramway ────────────────────────────────────────────────────────────
    {"line_name": "Tram R",   "line_type": "Tramway", "busy": False},
    # ── Bus ilévia (3 lignes) ──────────────────────────────────────────────
    {"line_name": "L1",       "line_type": "Bus",     "busy": True},
    {"line_name": "L3",       "line_type": "Bus",     "busy": True},
    {"line_name": "L5",       "line_type": "Bus",     "busy": False},
    # ── Train international ────────────────────────────────────────────────
    {"line_name": "Eurostar", "line_type": "Train",   "busy": True},
]

CITIES = [
    {"city": "Paris", "region_id": "fr-idf", "lines": PARIS_LINES},
    {"city": "Lille", "region_id": "fr-hdf", "lines": LILLE_LINES},
]

# ---------------------------------------------------------------------------
# Messages de perturbation réalistes par type
# ---------------------------------------------------------------------------

DISRUPTION_MESSAGES = {
    "Métro": [
        "Incident technique en station — circulation ralentie.",
        "Malaise voyageur — arrêt momentané du trafic.",
        "Travaux : espacement des rames augmenté.",
        "Panne de matériel roulant — navettes de remplacement.",
        "Affluence exceptionnelle — régulation en cours.",
    ],
    "RER": [
        "Incident de signalisation sur la ligne.",
        "Accident de personne — trafic interrompu momentanément.",
        "Grève partielle — fréquences réduites.",
        "Travaux entre deux gares — déviation en cours.",
        "Retards importants en cascade sur la branche Est.",
    ],
    "Transilien": [
        "Travaux de maintenance prolongés.",
        "Incident technique — départs limités depuis Paris.",
        "Retards dus aux intempéries.",
        "Suppression de trains aux heures creuses.",
    ],
    "Tramway": [
        "Obstacle sur les voies — circulation suspendue.",
        "Maintenance préventive — rames réduites.",
        "Incident au carrefour — trafic perturbé.",
        "Travaux de nuit prolongés.",
    ],
    "Bus": [
        "Déviation suite à travaux de voirie.",
        "Embouteillages — bus en retard sur la ligne.",
        "Perturbation en fin de ligne.",
        "Incident de circulation — temps de parcours augmenté.",
    ],
    "Train": [
        "Retard suite à un incident technique.",
        "Travaux entre deux gares.",
        "Perturbation trafic grandes lignes.",
        "Contrôle des billets rallongé — départ différé.",
    ],
}

# Probabilité de perturbation de base par type de ligne
BASE_DISRUPTION_PROB = {
    "Métro":      0.18,
    "RER":        0.28,
    "Transilien": 0.14,
    "Tramway":    0.07,
    "Bus":        0.10,
    "Train":      0.10,
}


def build_line_snapshot(city: str, region_id: str, line: dict) -> dict:
    prob = min(BASE_DISRUPTION_PROB.get(line["line_type"], 0.10) * (1.6 if line["busy"] else 1.0), 0.65)
    r = random.random()
    if r > prob:
        status, total_d, blocking_d, msg = "NORMAL", 0, 0, None
    elif r > prob * 0.45:
        msgs = DISRUPTION_MESSAGES.get(line["line_type"], ["Perturbation en cours."])
        status, total_d, blocking_d = "REDUCED", 1, 0
        msg = f"{line['line_name']} — {random.choice(msgs)}"
    else:
        msgs = DISRUPTION_MESSAGES.get(line["line_type"], ["Perturbation en cours."])
        status, total_d, blocking_d = "DISRUPTED", 1, 1
        msg = f"{line['line_name']} — {random.choice(msgs)}"

    return {
        "city":                 city,
        "region_id":            region_id,
        "line_name":            line["line_name"],
        "line_type":            line["line_type"],
        "total_disruptions":    total_d,
        "blocking_disruptions": blocking_d,
        "network_status":       status,
        "most_severe_message":  msg,
        "raw_payload":          json.dumps({"simulated": True, "busy": line["busy"]}),
    }


# ---------------------------------------------------------------------------
# Connexion PostgreSQL
# ---------------------------------------------------------------------------

def get_connection():
    db_url = os.getenv("TRANSIT_DB_URL")
    if db_url:
        db_url = db_url.replace("postgresql+psycopg2://", "postgresql://")
        import urllib.parse as up
        r = up.urlparse(db_url)
        return psycopg2.connect(
            host=r.hostname, port=r.port or 5432,
            dbname=r.path.lstrip("/"), user=r.username, password=r.password,
        )
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = int(os.getenv("POSTGRES_PORT", "5433" if host in ("localhost", "127.0.0.1") else "5432"))
    return psycopg2.connect(
        host=host, port=port,
        dbname=os.getenv("POSTGRES_DB", "smart_logistics"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


INSERT_SQL = """
INSERT INTO transit_data
    (city, region_id, line_name, line_type, total_disruptions, blocking_disruptions,
     network_status, most_severe_message, raw_payload)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
"""


def insert_snapshots(snapshots: list) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            for s in snapshots:
                cur.execute(
                    INSERT_SQL,
                    (
                        s["city"], s["region_id"],
                        s["line_name"], s["line_type"],
                        s["total_disruptions"], s["blocking_disruptions"],
                        s["network_status"], s["most_severe_message"],
                        s["raw_payload"],
                    ),
                )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Entrée principale
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulateur transit par ligne — France multi-villes.")
    parser.add_argument("--count",    type=int,   default=0, help="Cycles à envoyer (0 = infini)")
    parser.add_argument("--interval", type=float, default=0, help="Secondes entre cycles")
    return parser.parse_args()


def run_cycle() -> None:
    snapshots = []
    for city_info in CITIES:
        for line in city_info["lines"]:
            snapshots.append(build_line_snapshot(city_info["city"], city_info["region_id"], line))
    insert_snapshots(snapshots)
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    for city_info in CITIES:
        city_snaps = [s for s in snapshots if s["city"] == city_info["city"]]
        disrupted = sum(1 for s in city_snaps if s["network_status"] == "DISRUPTED")
        reduced   = sum(1 for s in city_snaps if s["network_status"] == "REDUCED")
        print(f"[{ts}] {city_info['city']:8s}  {len(city_snaps):2d} lignes  "
              f"perturbées={disrupted}  réduites={reduced}")


def main() -> None:
    args = parse_args()
    cycle_seconds = int(os.getenv("TRANSIT_COLLECTOR_CYCLE_SECONDS",
                                  os.getenv("TRANSIT_CYCLE_SECONDS", "1800")))
    total_lines = sum(len(c["lines"]) for c in CITIES)
    print(f"Simulateur transit démarré — {total_lines} lignes "
          f"({', '.join(c['city'] for c in CITIES)})")

    cycle_n = 0
    while True:
        try:
            run_cycle()
        except Exception as exc:
            print(f"[WARN] Cycle échoué : {exc}")
        cycle_n += 1
        if args.count > 0 and cycle_n >= args.count:
            break
        delay = args.interval if args.interval > 0 else cycle_seconds
        time.sleep(delay)


if __name__ == "__main__":
    main()
