CREATE TABLE IF NOT EXISTS transit_data (
    id                   SERIAL PRIMARY KEY,
    city                 VARCHAR(100)  NOT NULL,
    region_id            VARCHAR(100)  NOT NULL,
    line_name            VARCHAR(100),
    line_type            VARCHAR(50),
    total_disruptions    INT           DEFAULT 0,
    blocking_disruptions INT           DEFAULT 0,
    network_status       VARCHAR(50)   DEFAULT 'NORMAL',
    most_severe_message  TEXT,
    raw_payload          JSONB,
    created_at           TIMESTAMPTZ   DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS transit_data_city_idx       ON transit_data (city);
CREATE INDEX IF NOT EXISTS transit_data_created_at_idx ON transit_data (created_at DESC);
CREATE INDEX IF NOT EXISTS transit_data_line_idx       ON transit_data (city, line_name);
