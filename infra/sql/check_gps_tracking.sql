SELECT
    id,
    vehicle_id,
    latitude,
    longitude,
    speed,
    heading,
    status,
    created_at
FROM gps_tracking
ORDER BY created_at DESC;
