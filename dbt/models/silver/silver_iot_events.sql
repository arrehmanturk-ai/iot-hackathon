-- Silver: parse the Debezium CDC envelope out of Snowflake's Bronze VARIANT
-- table, cast to proper types, drop deletes/tombstones, tag AQI severity.

with bronze as (
    select
        record_content:payload:after:device_id::varchar          as device_id,
        record_content:payload:after:latitude::float              as latitude,
        record_content:payload:after:longitude::float             as longitude,
        record_content:payload:after:temperature::float           as temperature,
        record_content:payload:after:humidity::float               as humidity,
        record_content:payload:after:aqi::float                    as aqi,
        -- Debezium sends epoch micros for timestamptz columns by default
        to_timestamp_ntz(record_content:payload:after:event_time::number, 6) as event_time,
        record_content:payload:op::varchar                        as cdc_op,
        record_content:payload:ts_ms::number                       as cdc_ts_ms,
        record_metadata:CreateTime::number                         as kafka_create_time
    from {{ source('raw', 'iot_events') }}
),

filtered as (
    select *
    from bronze
    where device_id is not null
      and event_time is not null
      -- keep inserts/updates, drop deletes ('d') and snapshot reads ('r') duplicates if desired
      and coalesce(cdc_op, 'c') != 'd'
)

select
    device_id,
    latitude,
    longitude,
    temperature,
    humidity,
    aqi,
    event_time,
    date_trunc('day', event_time)      as event_date,
    case
        when aqi is null           then 'unknown'
        when aqi <= 50              then 'good'
        when aqi <= 100             then 'moderate'
        when aqi <= 150             then 'unhealthy_sensitive'
        when aqi <= 200             then 'unhealthy'
        else                             'hazardous'
    end                                  as aqi_severity,
    cdc_op,
    cdc_ts_ms
from filtered
