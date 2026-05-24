-- Metabase dashboard query pack for Smart Logistics.
-- Each query can be pasted into a native SQL question in Metabase.

-- KPI overview
SELECT *
FROM logistics_kpis;


-- Ingestion freshness status
SELECT
    source,
    record_count,
    last_record_at,
    age_seconds,
    status,
    freshness_target_seconds
FROM ingestion_status
ORDER BY source;


-- Latest transit status by city (metro, bus, tram, train)
SELECT
    city,
    region_id,
    total_disruptions,
    blocking_disruptions,
    network_status,
    most_severe_message,
    created_at
FROM latest_transit_by_city
ORDER BY city;


-- Business control tower overview
SELECT *
FROM business_control_tower;


-- Delivery risk predictions
SELECT
    reference,
    origin,
    destination,
    delivery_status,
    risk_score,
    risk_level,
    predicted_delay_minutes,
    recommendation
FROM delivery_risk_predictions
ORDER BY risk_score DESC, expected_arrival_time NULLS LAST, delivery_id;


-- Dispatch control board
SELECT
    vehicle_id,
    license_plate,
    driver_name,
    vehicle_status,
    delivery_reference,
    delivery_status,
    origin,
    destination,
    risk_score,
    risk_level,
    predicted_delay_minutes,
    recommendation,
    last_position_at
FROM dispatch_control_board
ORDER BY vehicle_id, delivery_reference NULLS LAST;


-- Latest weather by city
SELECT
    city,
    temperature,
    humidity,
    weather,
    wind_speed,
    created_at
FROM latest_weather_by_city
ORDER BY city;


-- Weather history over the last 24 hours
SELECT
    date_trunc('hour', created_at) AS hour_bucket,
    city,
    ROUND(AVG(temperature)::numeric, 2) AS avg_temperature
FROM weather_data
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY hour_bucket, city
ORDER BY hour_bucket DESC, city;


-- Latest vehicle positions
SELECT
    vehicle_id,
    license_plate,
    driver_name,
    vehicle_status,
    latitude,
    longitude,
    speed,
    heading,
    gps_status,
    last_position_at
FROM latest_vehicle_positions
ORDER BY vehicle_id;


-- GPS points received per hour
SELECT
    date_trunc('hour', created_at) AS hour_bucket,
    ('Vehicle ' || vehicle_id::text) AS vehicle_label,
    COUNT(*) AS gps_points_count
FROM gps_tracking
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY hour_bucket, vehicle_label
ORDER BY hour_bucket DESC, vehicle_label;


-- Latest traffic by route
SELECT
    route_name,
    distance_meters,
    duration_seconds,
    duration_typical_seconds,
    delay_seconds,
    created_at
FROM latest_traffic_by_route
ORDER BY route_name;


-- Traffic evolution over the last 24 hours
SELECT
    date_trunc('hour', created_at) AS hour_bucket,
    route_name,
    ROUND(AVG(delay_seconds)::numeric, 2) AS avg_delay_seconds
FROM traffic_data
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY hour_bucket, route_name
ORDER BY hour_bucket DESC, route_name;


-- Deliveries status summary
SELECT
    status,
    delivery_count,
    delayed_count,
    avg_cost,
    total_cost
FROM deliveries_status_summary
ORDER BY status;


-- Vehicle and delivery operational view
SELECT
    vehicle_id,
    license_plate,
    driver_name,
    vehicle_status,
    delivery_reference,
    origin,
    destination,
    delivery_status,
    delayed,
    expected_arrival_time,
    actual_arrival_time
FROM (
    SELECT
        v.id AS vehicle_id,
        v.license_plate,
        v.driver_name,
        v.status AS vehicle_status,
        d.reference AS delivery_reference,
        d.origin,
        d.destination,
        d.status AS delivery_status,
        d.delayed,
        d.expected_arrival_time,
        d.actual_arrival_time,
        d.created_at
    FROM vehicles v
    LEFT JOIN deliveries d ON d.vehicle_id = v.id
) operations
ORDER BY vehicle_id, created_at DESC NULLS LAST;