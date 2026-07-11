-- Gold: one row per device per day - the shape the Streamlit dashboard and
-- Timestream/Grafana bonus path both read from.

select
    device_id,
    event_date,
    count(*)                          as event_count,
    avg(latitude)                     as avg_latitude,
    avg(longitude)                    as avg_longitude,
    avg(temperature)                  as avg_temperature,
    avg(humidity)                     as avg_humidity,
    avg(aqi)                          as avg_aqi,
    max(aqi)                          as max_aqi,
    min(aqi)                          as min_aqi,
    max(event_time)                   as last_seen_at
from {{ ref('silver_iot_events') }}
group by device_id, event_date
