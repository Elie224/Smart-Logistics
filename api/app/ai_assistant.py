"""
Shamar — Assistant IA opérationnel de la plateforme Smart Logistics.
Module d'IA conversationnelle avec contexte temps réel et streaming.
"""
from __future__ import annotations

from typing import AsyncGenerator

from openai import AsyncOpenAI

from app.config import get_settings
from app.database import fetch_all, fetch_one

# ── Prompt système ─────────────────────────────────────────────────────────
_SYSTEM = """Tu es Shamar, l'assistant IA opérationnel de la plateforme Smart Logistics.

Ton périmètre :
- Flotte de 8 véhicules avec livraisons France (Paris, Lille, Lyon, Marseille, Toulouse)
- Météo en temps réel pour toutes les villes de livraison
- Trafic routier et transports en commun (métro, RER, bus, tram) surveillés à Paris et Lille uniquement
- Prédiction de risque de retard via modèle LightGBM (context trafic/TC disponible pour Paris et Lille)

Règles :
- Réponds TOUJOURS en français.
- Sois concis(e), opérationnel(le) et factuel(le).
- Si tu identifies un risque ou une anomalie, mentionne-le proactivement.
- Si une action est recommandée, propose-la clairement.
- Pour les livraisons hors Paris/Lille, précise que les données trafic/TC ne sont pas disponibles pour ces villes.
- Utilise les données temps réel ci-dessous pour répondre avec précision.

══════════════════ CONTEXTE TEMPS RÉEL ══════════════════
{context}
═════════════════════════════════════════════════════════"""


# ── Construction du contexte DB ────────────────────────────────────────────
def _build_context() -> str:
    lines: list[str] = []

    try:
        kpis = fetch_one("SELECT * FROM logistics_kpis")
        if kpis:
            lines.append(
                f"[FLOTTE] {kpis['total_vehicles']} véhicules — "
                f"{kpis['available_vehicles']} disponibles, "
                f"{kpis['in_transit_vehicles']} en transit"
            )
            lines.append(
                f"[LIVRAISONS] {kpis['total_deliveries']} total — "
                f"{kpis['deliveries_in_transit']} en cours, "
                f"{kpis['delayed_deliveries']} en retard, "
                f"{kpis['delivered_deliveries']} livrées"
            )
    except Exception:
        pass

    try:
        weather = fetch_all("SELECT city, temperature, wind_speed, description FROM latest_weather_by_city")
        for w in weather:
            lines.append(
                f"[MÉTÉO {w['city']}] {w.get('temperature', '?')}°C, "
                f"vent {w.get('wind_speed', '?')} m/s"
                + (f", {w['description']}" if w.get('description') else "")
            )
    except Exception:
        pass

    try:
        traffic = fetch_all(
            "SELECT city, traffic_status, avg_delay_seconds, max_delay_seconds "
            "FROM latest_traffic_by_city WHERE city IN ('Paris', 'Lille') ORDER BY city"
        )
        for t in traffic:
            delay_min = round((t.get("avg_delay_seconds") or 0) / 60)
            max_min = round((t.get("max_delay_seconds") or 0) / 60)
            lines.append(
                f"[TRAFIC {t['city']}] statut: {t.get('traffic_status', '?')}, "
                f"retard moyen {delay_min} min, max {max_min} min"
            )
    except Exception:
        pass

    try:
        transit = fetch_all(
            "SELECT city, network_status, total_disruptions, blocking_disruptions "
            "FROM latest_transit_by_city "
            "WHERE city IN ('Paris', 'Lille')"
        )
        for t in transit:
            lines.append(
                f"[TRANSIT {t['city']}] statut: {t.get('network_status', '?')}, "
                f"{t.get('total_disruptions', 0)} perturbation(s), "
                f"{t.get('blocking_disruptions', 0)} bloquante(s)"
            )
    except Exception:
        pass

    try:
        positions = fetch_all(
            """
            SELECT DISTINCT ON (g.vehicle_id)
                v.license_plate, v.driver_name, v.status AS vehicle_status,
                g.latitude, g.longitude, g.speed,
                d.reference AS delivery_ref, d.origin, d.destination, d.status AS delivery_status
            FROM gps_tracking g
            JOIN vehicles v ON v.id = g.vehicle_id
            LEFT JOIN deliveries d
                ON d.vehicle_id = g.vehicle_id
                AND d.status NOT IN ('DELIVERED', 'CANCELLED')
            ORDER BY g.vehicle_id, g.created_at DESC
            """
        )
        for v in positions:
            speed = v.get("speed")
            spd = f"{speed:.0f} km/h" if speed is not None else "vitesse inconnue"
            delivery = (
                f" — livraison {v['delivery_ref']} ({v['origin']}→{v['destination']}, {v['delivery_status']})"
                if v.get("delivery_ref")
                else " — sans livraison active"
            )
            lines.append(
                f"[VÉHICULE {v['license_plate']}] {v['driver_name']}, "
                f"statut: {v['vehicle_status']}, {spd}{delivery}"
            )
    except Exception:
        pass

    try:
        dispatch = fetch_all(
            "SELECT delivery_reference, origin, destination, delivery_status, "
            "risk_level, risk_score, predicted_delay_minutes, recommendation "
            "FROM dispatch_control_board WHERE delivery_reference IS NOT NULL"
        )
        for d in dispatch:
            lines.append(
                f"[RISQUE {d['delivery_reference']}] {d['origin']}→{d['destination']}, "
                f"niveau: {d.get('risk_level', '?')} (score {d.get('risk_score', '?')}), "
                f"retard prédit: {d.get('predicted_delay_minutes', 0)} min — "
                f"{d.get('recommendation', '')}"
            )
    except Exception:
        pass

    return "\n".join(lines) if lines else "Aucune donnée disponible pour le moment."


# ── Appel OpenAI ───────────────────────────────────────────────────────────
async def answer(message: str, history: list[dict]) -> str:
    settings = get_settings()

    if not settings.openai_api_key:
        return "Clé OpenAI non configurée. Ajoutez OPENAI_API_KEY dans le fichier .env."

    context = _build_context()
    system_prompt = _SYSTEM.format(context=context)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    # Garde les 20 derniers échanges pour rester dans les limites de tokens
    for turn in history[-20:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": message})

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=600,
        temperature=0.4,
    )
    return response.choices[0].message.content.strip()


async def stream_answer(message: str, history: list[dict]) -> AsyncGenerator[str, None]:
    """Génère la réponse token par token via streaming OpenAI."""
    settings = get_settings()

    if not settings.openai_api_key:
        yield "Clé OpenAI non configurée. Ajoutez OPENAI_API_KEY dans le fichier .env."
        return

    context = _build_context()
    system_prompt = _SYSTEM.format(context=context)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for turn in history[-20:]:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": message})

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    stream = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=600,
        temperature=0.4,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
