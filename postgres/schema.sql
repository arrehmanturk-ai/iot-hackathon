-- Run this on the Postgres EC2 instance ("on-prem" DB).
--
-- IMPORTANT: wal_level = logical must be set in postgresql.conf (not here)
-- and Postgres restarted before Debezium (Phase 2) will work. The CDK
-- EC2 user-data script already sets this for you; if you're doing it by
-- hand:
--   sudo sed -i "s/#wal_level = replica/wal_level = logical/" \
--       /var/lib/pgsql/data/postgresql.conf
--   sudo systemctl restart postgresql

CREATE DATABASE iot_db;

\c iot_db

CREATE TABLE IF NOT EXISTS iot_events (
    id           BIGSERIAL PRIMARY KEY,
    device_id    VARCHAR(64)      NOT NULL,
    latitude     DOUBLE PRECISION NOT NULL,
    longitude    DOUBLE PRECISION NOT NULL,
    temperature  DOUBLE PRECISION,
    humidity     DOUBLE PRECISION,
    aqi          DOUBLE PRECISION,
    event_time   TIMESTAMPTZ      NOT NULL,
    ingested_at  TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_iot_events_device_time
    ON iot_events (device_id, event_time DESC);

-- Debezium needs REPLICA IDENTITY FULL to capture full before/after row
-- images for UPDATE/DELETE (default only captures the primary key).
ALTER TABLE iot_events REPLICA IDENTITY FULL;
