CREATE TABLE IF NOT EXISTS weather_data (
    id SERIAL PRIMARY KEY,
    city VARCHAR(100) NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    weather VARCHAR(100),
    wind_speed DOUBLE PRECISION,
    raw_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_weather_data_city_created_at
    ON weather_data (city, created_at DESC);

CREATE TABLE IF NOT EXISTS vehicles (
    id SERIAL PRIMARY KEY,
    license_plate VARCHAR(50) NOT NULL UNIQUE,
    driver_name VARCHAR(100) NOT NULL,
    capacity_kg INTEGER,
    status VARCHAR(50) NOT NULL DEFAULT 'AVAILABLE',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_vehicles_status
    ON vehicles (status);

CREATE TABLE IF NOT EXISTS gps_tracking (
    id SERIAL PRIMARY KEY,
    vehicle_id INTEGER NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    speed DOUBLE PRECISION,
    heading DOUBLE PRECISION,
    status VARCHAR(50),
    raw_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gps_tracking_vehicle_created_at
    ON gps_tracking (vehicle_id, created_at DESC);

CREATE TABLE IF NOT EXISTS traffic_data (
    id SERIAL PRIMARY KEY,
    city VARCHAR(100),
    route_name VARCHAR(150) NOT NULL,
    origin_latitude DOUBLE PRECISION NOT NULL,
    origin_longitude DOUBLE PRECISION NOT NULL,
    destination_latitude DOUBLE PRECISION NOT NULL,
    destination_longitude DOUBLE PRECISION NOT NULL,
    distance_meters DOUBLE PRECISION,
    duration_seconds DOUBLE PRECISION,
    duration_typical_seconds DOUBLE PRECISION,
    delay_seconds DOUBLE PRECISION,
    raw_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_traffic_data_route_created_at
    ON traffic_data (route_name, created_at DESC);

CREATE TABLE IF NOT EXISTS deliveries (
    id SERIAL PRIMARY KEY,
    vehicle_id INTEGER,
    reference VARCHAR(100) NOT NULL UNIQUE,
    origin VARCHAR(255) NOT NULL,
    destination VARCHAR(255) NOT NULL,
    departure_time TIMESTAMPTZ,
    expected_arrival_time TIMESTAMPTZ,
    actual_arrival_time TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL DEFAULT 'PLANNED',
    cost NUMERIC(12, 2),
    delayed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_deliveries_status
    ON deliveries (status);

CREATE INDEX IF NOT EXISTS idx_deliveries_vehicle_id
    ON deliveries (vehicle_id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_gps_tracking_vehicle'
    ) THEN
        ALTER TABLE gps_tracking
            ADD CONSTRAINT fk_gps_tracking_vehicle
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_deliveries_vehicle'
    ) THEN
        ALTER TABLE deliveries
            ADD CONSTRAINT fk_deliveries_vehicle
            FOREIGN KEY (vehicle_id) REFERENCES vehicles (id);
    END IF;
END $$;
