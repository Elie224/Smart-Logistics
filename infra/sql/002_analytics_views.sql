CREATE OR REPLACE VIEW latest_weather_by_city AS
SELECT DISTINCT ON (city)
    id,
    city,
    temperature,
    humidity,
    weather,
    wind_speed,
    created_at
FROM weather_data
ORDER BY city, created_at DESC;


CREATE OR REPLACE VIEW latest_vehicle_positions AS
SELECT DISTINCT ON (g.vehicle_id)
    g.vehicle_id,
    v.license_plate,
    v.driver_name,
    v.status AS vehicle_status,
    g.latitude,
    g.longitude,
    g.speed,
    g.heading,
    g.status AS gps_status,
    g.created_at AS last_position_at
FROM gps_tracking g
JOIN vehicles v ON v.id = g.vehicle_id
ORDER BY g.vehicle_id, g.created_at DESC;


CREATE OR REPLACE VIEW deliveries_status_summary AS
SELECT
    status,
    COUNT(*) AS delivery_count,
    COUNT(*) FILTER (WHERE delayed) AS delayed_count,
    ROUND(COALESCE(AVG(cost), 0)::numeric, 2) AS avg_cost,
    ROUND(COALESCE(SUM(cost), 0)::numeric, 2) AS total_cost
FROM deliveries
GROUP BY status
ORDER BY status;


CREATE OR REPLACE VIEW latest_traffic_by_route AS
SELECT DISTINCT ON (route_name)
    id,
    city,
    route_name,
    distance_meters,
    duration_seconds,
    duration_typical_seconds,
    delay_seconds,
    created_at
FROM traffic_data
ORDER BY route_name, created_at DESC;

-- Vue agrégeant le trafic par ville (Paris / Lille)
CREATE OR REPLACE VIEW latest_traffic_by_city AS
SELECT
    city,
    COUNT(*)                                                        AS route_count,
    ROUND(AVG(GREATEST(delay_seconds, 0))::numeric, 0)              AS avg_delay_seconds,
    ROUND(MAX(GREATEST(delay_seconds, 0))::numeric, 0)              AS max_delay_seconds,
    ROUND(AVG(duration_seconds)::numeric, 0)                        AS avg_duration_seconds,
    MAX(created_at)                                                 AS last_updated,
    CASE
        WHEN AVG(GREATEST(delay_seconds, 0)) > 600 THEN 'CONGESTED'
        WHEN AVG(GREATEST(delay_seconds, 0)) > 180 THEN 'SLOW'
        ELSE 'FLUID'
    END                                                             AS traffic_status
FROM (
    SELECT DISTINCT ON (route_name)
        city, route_name, delay_seconds, duration_seconds, created_at
    FROM traffic_data
    WHERE city IS NOT NULL
    ORDER BY route_name, created_at DESC
) latest_routes
GROUP BY city;


CREATE OR REPLACE VIEW latest_transit_by_city AS
WITH latest_lines AS (
    SELECT DISTINCT ON (city, line_name)
        city, network_status, most_severe_message,
        blocking_disruptions, total_disruptions, created_at
    FROM transit_data
    WHERE line_name IS NOT NULL
    ORDER BY city, line_name, created_at DESC
)
SELECT
    city,
    COUNT(*)::int                                                     AS total_lines,
    SUM(total_disruptions)::int                                       AS total_disruptions,
    SUM(blocking_disruptions)::int                                    AS blocking_disruptions,
    CASE
        WHEN SUM(blocking_disruptions) > 0 THEN 'DISRUPTED'
        WHEN SUM(total_disruptions)    > 0 THEN 'REDUCED'
        ELSE 'NORMAL'
    END                                                               AS network_status,
    MAX(CASE WHEN network_status = 'DISRUPTED' THEN most_severe_message END) AS most_severe_message,
    MAX(created_at)                                                   AS created_at
FROM latest_lines
GROUP BY city;


CREATE OR REPLACE VIEW latest_transit_by_line AS
SELECT DISTINCT ON (city, line_name)
    id,
    city,
    region_id,
    line_name,
    line_type,
    total_disruptions,
    blocking_disruptions,
    network_status,
    most_severe_message,
    created_at
FROM transit_data
WHERE line_name IS NOT NULL
ORDER BY city, line_name, created_at DESC;


CREATE OR REPLACE VIEW logistics_kpis AS
SELECT
    (SELECT COUNT(*) FROM vehicles) AS total_vehicles,
    (SELECT COUNT(*) FROM vehicles WHERE status = 'AVAILABLE') AS available_vehicles,
    (SELECT COUNT(*) FROM vehicles WHERE status = 'IN_TRANSIT') AS in_transit_vehicles,
    (SELECT COUNT(*) FROM deliveries) AS total_deliveries,
    (SELECT COUNT(*) FROM deliveries WHERE status = 'PLANNED') AS planned_deliveries,
    (SELECT COUNT(*) FROM deliveries WHERE status = 'IN_TRANSIT') AS deliveries_in_transit,
    (SELECT COUNT(*) FROM deliveries WHERE status = 'DELIVERED') AS delivered_deliveries,
    (SELECT COUNT(*) FROM deliveries WHERE delayed) AS delayed_deliveries,
    (SELECT COUNT(*) FROM gps_tracking) AS total_gps_points,
    (SELECT COUNT(*) FROM weather_data) AS total_weather_records,
    (SELECT COUNT(*) FROM traffic_data) AS total_traffic_records,
    (SELECT COUNT(*) FROM transit_data) AS total_transit_records;


CREATE OR REPLACE VIEW ingestion_status AS
SELECT
    source,
    record_count,
    last_record_at,
    EXTRACT(EPOCH FROM (NOW() - last_record_at))::bigint AS age_seconds,
    CASE
        WHEN last_record_at IS NULL THEN 'missing'
        WHEN NOW() - last_record_at <= freshness_target THEN 'fresh'
        ELSE 'stale'
    END AS status,
    freshness_target_seconds
FROM (
    SELECT
        'weather' AS source,
        COUNT(*)::bigint AS record_count,
        MAX(created_at) AS last_record_at,
        INTERVAL '65 minutes' AS freshness_target,
        3900::bigint AS freshness_target_seconds
    FROM weather_data

    UNION ALL

    SELECT
        'gps' AS source,
        COUNT(*)::bigint AS record_count,
        MAX(created_at) AS last_record_at,
        INTERVAL '30 minutes' AS freshness_target,
        1800::bigint AS freshness_target_seconds
    FROM gps_tracking

    UNION ALL

    SELECT
        'traffic' AS source,
        COUNT(*)::bigint AS record_count,
        MAX(created_at) AS last_record_at,
        INTERVAL '65 minutes' AS freshness_target,
        3900::bigint AS freshness_target_seconds
    FROM traffic_data

    UNION ALL

    SELECT
        'transit' AS source,
        COUNT(*)::bigint AS record_count,
        MAX(created_at) AS last_record_at,
        INTERVAL '65 minutes' AS freshness_target,
        3900::bigint AS freshness_target_seconds
    FROM transit_data
) source_status;


DROP VIEW IF EXISTS dispatch_control_board;
DROP VIEW IF EXISTS business_control_tower;
DROP VIEW IF EXISTS delivery_risk_predictions;


CREATE OR REPLACE VIEW delivery_risk_predictions AS
WITH delivery_context AS (
    SELECT
        d.id AS delivery_id,
        d.reference,
        d.origin,
        d.destination,
        d.status AS delivery_status,
        d.delayed,
        d.expected_arrival_time,
        d.actual_arrival_time,
        d.cost,
        v.id AS vehicle_id,
        v.license_plate,
        v.driver_name,
        v.status AS vehicle_status,
        lvp.gps_status,
        lvp.last_position_at,
        lvp.latitude,
        lvp.longitude,
        COALESCE(GREATEST(ltc.avg_delay_seconds, 0), 0) AS route_delay_seconds,
        lw.weather AS destination_weather,
        lw.temperature AS destination_temperature,
        lw.humidity AS destination_humidity
    FROM deliveries d
    LEFT JOIN vehicles v ON v.id = d.vehicle_id
    LEFT JOIN latest_vehicle_positions lvp ON lvp.vehicle_id = d.vehicle_id
    LEFT JOIN latest_traffic_by_city ltc ON LOWER(ltc.city) = LOWER(d.origin)
    LEFT JOIN latest_weather_by_city lw ON LOWER(lw.city) = LOWER(d.destination)
), scored_deliveries AS (
    SELECT
        delivery_context.*,
        LEAST(
            100,
            (
                CASE WHEN delayed THEN 35 ELSE 0 END
                + CASE
                    WHEN delivery_status = 'IN_TRANSIT' THEN 15
                    WHEN delivery_status = 'PLANNED' THEN 5
                    ELSE 0
                END
                + CASE
                    WHEN expected_arrival_time IS NOT NULL
                        AND expected_arrival_time < NOW()
                        AND delivery_status <> 'DELIVERED' THEN 20
                    ELSE 0
                END
                + LEAST(25, route_delay_seconds / 60.0 * 2)
                + CASE
                    WHEN destination_weather ILIKE '%storm%' OR destination_weather ILIKE '%snow%' THEN 20
                    WHEN destination_weather ILIKE '%rain%' THEN 15
                    WHEN destination_weather ILIKE '%cloud%' THEN 6
                    ELSE 0
                END
                + CASE
                    WHEN vehicle_status = 'MAINTENANCE' THEN 30
                    WHEN vehicle_status = 'IN_TRANSIT' THEN 5
                    ELSE 0
                END
                + CASE
                    WHEN last_position_at IS NULL THEN 15
                    WHEN NOW() - last_position_at > INTERVAL '30 minutes' THEN 15
                    ELSE 0
                END
            )
        )::numeric(5, 2) AS risk_score
    FROM delivery_context
)
SELECT
    delivery_id,
    reference,
    origin,
    destination,
    delivery_status,
    delayed,
    expected_arrival_time,
    actual_arrival_time,
    cost,
    vehicle_id,
    license_plate,
    driver_name,
    vehicle_status,
    gps_status,
    last_position_at,
    latitude,
    longitude,
    route_delay_seconds,
    destination_weather,
    destination_temperature,
    destination_humidity,
    risk_score,
    CASE
        WHEN risk_score >= 60 THEN 'HIGH'
        WHEN risk_score >= 30 THEN 'MEDIUM'
        ELSE 'LOW'
    END AS risk_level,
    ROUND((route_delay_seconds / 60.0)::numeric, 2) AS predicted_delay_minutes,
    CASE
        WHEN risk_score >= 60 THEN 'Escalate dispatch follow-up and reassess ETA immediately.'
        WHEN risk_score >= 30 THEN 'Monitor closely and update stakeholders on route conditions.'
        ELSE 'Maintain current plan and continue routine monitoring.'
    END AS recommendation
FROM scored_deliveries;


CREATE OR REPLACE VIEW dispatch_control_board AS
SELECT
    v.id AS vehicle_id,
    v.license_plate,
    v.driver_name,
    v.status AS vehicle_status,
    lvp.latitude,
    lvp.longitude,
    lvp.speed,
    lvp.heading,
    lvp.gps_status,
    lvp.last_position_at,
    d.id AS delivery_id,
    d.reference AS delivery_reference,
    d.origin,
    d.destination,
    d.status AS delivery_status,
    d.expected_arrival_time,
    d.actual_arrival_time,
    drp.risk_score,
    drp.risk_level,
    drp.predicted_delay_minutes,
    drp.recommendation
FROM vehicles v
LEFT JOIN deliveries d ON d.vehicle_id = v.id
LEFT JOIN latest_vehicle_positions lvp ON lvp.vehicle_id = v.id
LEFT JOIN delivery_risk_predictions drp ON drp.delivery_id = d.id
ORDER BY v.id, d.created_at DESC NULLS LAST;


CREATE OR REPLACE VIEW business_control_tower AS
SELECT
    (SELECT COUNT(*) FROM ingestion_status WHERE status = 'fresh') AS fresh_sources,
    (SELECT COUNT(*) FROM ingestion_status WHERE status = 'stale') AS stale_sources,
    (SELECT COUNT(*) FROM delivery_risk_predictions WHERE risk_level = 'HIGH') AS high_risk_deliveries,
    (SELECT COUNT(*) FROM delivery_risk_predictions WHERE risk_level = 'MEDIUM') AS medium_risk_deliveries,
    (SELECT COUNT(*) FROM delivery_risk_predictions WHERE predicted_delay_minutes > 0) AS delayed_route_predictions,
    (SELECT ROUND(GREATEST(COALESCE(AVG(avg_delay_seconds), 0), 0)::numeric, 2) FROM latest_traffic_by_city) AS average_route_delay_seconds,
    (SELECT ROUND(COALESCE(AVG(temperature), 0)::numeric, 2) FROM latest_weather_by_city WHERE LOWER(city) IN ('paris', 'lille')) AS average_temperature,
    (SELECT COUNT(*) FROM deliveries WHERE expected_arrival_time BETWEEN NOW() AND NOW() + INTERVAL '2 hours') AS deliveries_due_next_2h,
    (SELECT COUNT(*) FROM latest_vehicle_positions WHERE NOW() - last_position_at > INTERVAL '30 minutes') AS stale_vehicle_positions,
    (SELECT ROUND(COALESCE(AVG(risk_score), 0)::numeric, 2) FROM delivery_risk_predictions) AS average_delivery_risk_score;
