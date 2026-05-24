-- Vue dataset ML pour la prédiction de retard de livraison
-- Features : météo, trafic, transit, heure, ville de destination
-- Target   : is_delayed (0 = à l'heure, 1 = retard)

CREATE OR REPLACE VIEW ml_delivery_dataset AS
SELECT
    d.id                                                           AS delivery_id,
    d.reference,
    d.origin,
    d.destination,
    d.departure_time,
    d.expected_arrival_time,
    d.actual_arrival_time,
    -- Target
    COALESCE(d.delayed, FALSE)::int                                AS is_delayed,
    -- Features temporelles
    EXTRACT(HOUR FROM COALESCE(d.departure_time, NOW()))::int      AS departure_hour,
    EXTRACT(DOW  FROM COALESCE(d.departure_time, NOW()))::int      AS departure_dow,
    -- Météo à destination
    COALESCE(lw.temperature,  12.0)                                AS temperature,
    COALESCE(lw.wind_speed,    3.0)                                AS wind_speed,
    -- Trafic dans la ville d'origine
    COALESCE(ltc.avg_delay_seconds,     0)                         AS traffic_delay_s,
    COALESCE(ltc.avg_duration_seconds, 900)                        AS route_duration_s,
    -- Transit à destination
    COALESCE(ltr.total_disruptions,     0)                         AS transit_disruptions,
    COALESCE(ltr.blocking_disruptions,  0)                         AS transit_blocking,
    COALESCE(ltr.network_status, 'NORMAL')                         AS transit_status
FROM deliveries d
LEFT JOIN latest_weather_by_city  lw  ON LOWER(lw.city)  = LOWER(d.destination)
LEFT JOIN latest_traffic_by_city  ltc ON LOWER(ltc.city) = LOWER(d.origin)
LEFT JOIN latest_transit_by_city  ltr ON LOWER(ltr.city) = LOWER(d.destination)
WHERE d.departure_time IS NOT NULL;
