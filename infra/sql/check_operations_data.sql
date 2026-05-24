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
    d.actual_arrival_time
FROM vehicles v
LEFT JOIN deliveries d ON d.vehicle_id = v.id
ORDER BY v.id, d.created_at DESC NULLS LAST;
