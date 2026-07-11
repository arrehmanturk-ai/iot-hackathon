"""Bonus path (Task 2.5): reads recent Gold rows from Snowflake and writes
them to AWS Timestream so Grafana can render a live sensor panel.

Deploy on a schedule (e.g. EventBridge rule every 5 minutes). Snowflake
credentials are read from environment variables (set these in the Lambda
console or via CDK/SAM - do not hardcode them):
  SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD, SNOWFLAKE_ROLE,
  SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA,
  TIMESTREAM_DB, TIMESTREAM_TABLE
"""
import os
import time

import boto3
import snowflake.connector

TIMESTREAM_DB = os.environ.get("TIMESTREAM_DB", "iot_hackathon")
TIMESTREAM_TABLE = os.environ.get("TIMESTREAM_TABLE", "device_metrics")

ts_client = boto3.client("timestream-write")


def get_snowflake_connection():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        role=os.environ.get("SNOWFLAKE_ROLE", "HACKATHON_LOADER"),
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "ANALYTICS"),
    )


def fetch_recent_rows(conn):
    query = """
        select device_id, event_date, event_count, avg_aqi, avg_temperature, avg_humidity
        from gold_daily_device_agg
        where event_date >= dateadd(day, -1, current_date())
    """
    cur = conn.cursor()
    cur.execute(query)
    return cur.fetchall()


def to_timestream_records(rows):
    now_ms = str(int(time.time() * 1000))
    records = []
    for device_id, event_date, event_count, avg_aqi, avg_temperature, avg_humidity in rows:
        dimensions = [{"Name": "device_id", "Value": str(device_id)}]
        for measure_name, value in (
            ("event_count", event_count),
            ("avg_aqi", avg_aqi),
            ("avg_temperature", avg_temperature),
            ("avg_humidity", avg_humidity),
        ):
            if value is None:
                continue
            records.append({
                "Dimensions": dimensions,
                "MeasureName": measure_name,
                "MeasureValue": str(value),
                "MeasureValueType": "DOUBLE",
                "Time": now_ms,
            })
    return records


def handler(event, context):
    conn = get_snowflake_connection()
    try:
        rows = fetch_recent_rows(conn)
    finally:
        conn.close()

    records = to_timestream_records(rows)

    # Timestream write_records caps out at 100 records per call
    written = 0
    for i in range(0, len(records), 100):
        batch = records[i:i + 100]
        ts_client.write_records(
            DatabaseName=TIMESTREAM_DB,
            TableName=TIMESTREAM_TABLE,
            Records=batch,
        )
        written += len(batch)

    return {"rows_read": len(rows), "records_written": written}
