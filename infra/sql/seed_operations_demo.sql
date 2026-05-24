INSERT INTO vehicles (license_plate, driver_name, capacity_kg, status)
VALUES
    ('TR-001-AA', 'Mamadou Diallo', 12000, 'AVAILABLE'),
    ('TR-002-BB', 'Aicha Benali', 9500, 'IN_TRANSIT'),
    ('TR-003-CC', 'Jean Kouassi', 15000, 'MAINTENANCE')
ON CONFLICT (license_plate) DO NOTHING;

INSERT INTO deliveries (
    vehicle_id,
    reference,
    origin,
    destination,
    departure_time, 
    expected_arrival_time,
    actual_arrival_time,
    status,
    cost,
    delayed
)
SELECT
    v.id,
    seed.reference,
    seed.origin,
    seed.destination,
    seed.departure_time,
    seed.expected_arrival_time,
    seed.actual_arrival_time,
    seed.status,
    seed.cost,
    seed.delayed
FROM (
    VALUES
        ('TR-001-AA', 'DLV-2026-001', 'Lille', 'Paris', NOW() - INTERVAL '6 hours', NOW() + INTERVAL '1 hour', NULL, 'IN_TRANSIT', 420.00, FALSE),
        ('TR-002-BB', 'DLV-2026-002', 'Paris', 'Lille', NOW() - INTERVAL '10 hours', NOW() - INTERVAL '2 hours', NOW() - INTERVAL '1 hour', 'DELIVERED', 310.00, TRUE),
        ('TR-003-CC', 'DLV-2026-003', 'Paris', 'Lille', NULL, NOW() + INTERVAL '8 hours', NULL, 'PLANNED', 275.00, FALSE)
) AS seed(license_plate, reference, origin, destination, departure_time, expected_arrival_time, actual_arrival_time, status, cost, delayed)
JOIN vehicles v ON v.license_plate = seed.license_plate
ON CONFLICT (reference) DO NOTHING;
