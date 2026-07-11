# IoT On-Prem-to-Cloud Data Pipeline (AWS + Snowflake)

End-to-end pipeline: simulated IoT sensors → AWS IoT Core → Kafka (MSK) →
PostgreSQL-on-EC2 ("on-prem") → Debezium CDC → Snowflake (Bronze/Silver/Gold via dbt)
→ Streamlit dashboard, with a bonus Timestream + Grafana time-series path.

This repo is generated code for the hackathon brief. It is deployment-ready in
structure but **you must supply your own AWS account, Snowflake trial account,
and credentials** — nothing here has been deployed or tested against live
infrastructure.

## Repo layout

```
cdk/                CDK (Python) app — VPC, MSK, EC2 (Postgres + bastion), S3, Secrets
kafka-connect/      Connector configs (JDBC sink, S3 sink, Debezium source, Snowflake sink)
postgres/           On-prem schema DDL + WAL notes
snowflake/          Database/schema DDL (RAW / CLEAN / ANALYTICS)
dbt/                dbt project — silver + gold models with tests
streamlit/          BI dashboard reading the Gold layer
lambda/             Snowflake → Timestream writer (bonus path)
grafana/            Sample dashboard JSON for the Timestream panel
docs/               Architecture diagram (SVG)
```

## Assumptions made (adjust as needed)

- Telemetry beyond lat/long/timestamp/device_id includes `temperature`,
  `humidity`, and `aqi` — the brief's Streamlit task asks for an "AQI trend"
  chart, but Task 1.2 only specifies geolocation fields. Added synthetic
  telemetry fields so that chart (and the gold aggregates) have something
  real to compute. Trim these from the device simulator template / schema if
  you only want pure geolocation.
- Kafka Connect runs as **MSK Connect** (fully managed) rather than a
  self-hosted Connect cluster on EC2 — fewer moving parts to provision via CDK.
  Swap `msk_connect` for a self-managed Connect-on-EC2/ECS stack if you'd
  rather not depend on MSK Connect's custom-plugin flow.
- The AWS IoT Device Simulator is Anthropic — sorry, AWS's — own pre-built
  solution (deployed via its own CloudFormation template from the Solutions
  Library), not something to hand-write; setup steps are in Phase 1 below.

## Prerequisites

- AWS account with admin-ish IAM permissions, AWS CLI configured
- Node.js 18+ (for CDK CLI) and Python 3.10+
- `pip install aws-cdk-lib constructs`
- A Snowflake trial account (snowflake.com/trial)
- `dbt-snowflake`, `streamlit`, `snowflake-connector-python` (see each folder's requirements.txt)

## Phase 1 — Ingestion & on-prem simulation

1. **Bootstrap & deploy infra**
   ```
   cd cdk
   pip install -r requirements.txt
   cdk bootstrap
   cdk deploy --all
   ```
   This provisions: VPC (public + private subnets), MSK cluster, an EC2
   Postgres instance in the private subnet, a bastion host (SSM only, no
   public SSH), an S3 backup bucket, and a Secrets Manager secret for DB
   credentials. Note the MSK bootstrap broker string and EC2 instance IDs from
   the stack outputs.

2. **Set up Postgres** — connect via SSM Session Manager to the bastion, then
   to the Postgres box, and run `postgres/schema.sql`. Set `wal_level =
   logical` in `postgresql.conf` (see comment at top of that file) and restart
   Postgres — this is required for Debezium in Phase 2.

3. **Deploy the AWS IoT Device Simulator** — this is a pre-built AWS Solutions
   Library CloudFormation template (search "AWS IoT Device Simulator" in the
   Solutions Library), not custom code. Deploy it, then in its console:
   create a device type with fields `device_id, latitude, longitude,
   timestamp, temperature, humidity, aqi`, and start 5+ simulated devices.

4. **Wire IoT Core → MSK** — create an IoT Core topic rule with an action
   that forwards messages to your MSK cluster's `iot-events` topic (IoT Core
   has a native Kafka/MSK action).

5. **Deploy connectors** — via MSK Connect, create the JDBC sink connector
   using `kafka-connect/jdbc-sink-connector.json` (fill in the real host/port
   and point credentials at the Secrets Manager secret), and optionally the
   S3 sink using `kafka-connect/s3-sink-connector.json`.

6. **Verify** — confirm rows are landing in Postgres `iot_events` table.

## Phase 2 — CDC, Snowflake, dbt, Streamlit

1. Deploy the Debezium Postgres connector (`kafka-connect/debezium-postgres-connector.json`)
   via MSK Connect. Confirm change events appear on `cdc.public.iot_events`.

2. Create the Snowflake database/schemas from `snowflake/ddl.sql`, then
   deploy the Snowflake Kafka connector
   (`kafka-connect/snowflake-connector.json`) and confirm `RAW.IOT_EVENTS`
   is receiving records (Snowflake's connector auto-creates this table as
   `RECORD_METADATA VARIANT, RECORD_CONTENT VARIANT`).

3. **dbt**
   ```
   cd dbt
   pip install dbt-snowflake
   cp profiles.yml.example ~/.dbt/profiles.yml   # fill in your account/creds
   dbt run
   dbt test
   dbt docs generate && dbt docs serve
   ```

4. **Streamlit**
   ```
   cd streamlit
   pip install -r requirements.txt
   streamlit run app.py
   ```
   Set Snowflake creds via `.streamlit/secrets.toml` (see comment in `app.py`).

5. **Bonus: Timestream + Grafana** — deploy `lambda/snowflake_to_timestream.py`
   on a schedule (e.g. EventBridge every 5 min), point a Grafana Timestream
   data source at the resulting table, and import `grafana/dashboard.json`.

## Submission checklist mapping

- GitHub repo → this repo
- Architecture diagram → `docs/architecture.svg`
- Screenshots → capture these yourself once deployed
- README → this file
- 5-min demo → walk through Postgres row → CDC event → Snowflake Gold row
