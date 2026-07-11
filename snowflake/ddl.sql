-- Run in a Snowflake worksheet (or via SnowSQL) once you have a trial account.

CREATE DATABASE IF NOT EXISTS HACKATHON_IOT;
USE DATABASE HACKATHON_IOT;

CREATE SCHEMA IF NOT EXISTS RAW;        -- Bronze - loaded by the Kafka connector
CREATE SCHEMA IF NOT EXISTS CLEAN;      -- Silver - dbt output
CREATE SCHEMA IF NOT EXISTS ANALYTICS;  -- Gold   - dbt output

-- The Snowflake Kafka Connector auto-creates RAW.IOT_EVENTS the first time
-- it flushes a batch, with this shape:
--   RECORD_METADATA VARIANT   (topic, partition, offset, CreateTime, key...)
--   RECORD_CONTENT  VARIANT   (the Debezium CDC envelope: payload.after, .before, .op)
-- No need to create it by hand - just confirm it exists after the connector
-- has been running for a minute:
--   SELECT * FROM RAW.IOT_EVENTS LIMIT 10;

-- Recommended: a warehouse for dbt + Streamlit to query against.
CREATE WAREHOUSE IF NOT EXISTS HACKATHON_WH
    WAREHOUSE_SIZE = 'XSMALL'
    AUTO_SUSPEND = 60
    AUTO_RESUME = TRUE;

-- Recommended: a dedicated role/user for the Kafka connector (key-pair auth,
-- not password) and a separate one for dbt/Streamlit reads.
CREATE ROLE IF NOT EXISTS HACKATHON_LOADER;
GRANT USAGE ON DATABASE HACKATHON_IOT TO ROLE HACKATHON_LOADER;
GRANT USAGE ON SCHEMA RAW TO ROLE HACKATHON_LOADER;
GRANT CREATE TABLE ON SCHEMA RAW TO ROLE HACKATHON_LOADER;
GRANT USAGE ON WAREHOUSE HACKATHON_WH TO ROLE HACKATHON_LOADER;
