SELECT
    id,
    route_name,
    distance_meters,
    duration_seconds,
    duration_typical_seconds,
    delay_seconds,
    created_at
FROM traffic_data
ORDER BY created_at DESC;
