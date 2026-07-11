"""Streamlit dashboard reading Snowflake's Gold layer.

Credentials: create .streamlit/secrets.toml next to this file with:

    [snowflake]
    account = "REPLACE_WITH_ACCOUNT_LOCATOR"
    user = "REPLACE_WITH_USER"
    password = "REPLACE_WITH_PASSWORD"
    role = "HACKATHON_LOADER"
    warehouse = "HACKATHON_WH"
    database = "HACKATHON_IOT"
    schema = "ANALYTICS"

Run with: streamlit run app.py
"""
import pandas as pd
import streamlit as st
import snowflake.connector
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="IoT Fleet Dashboard", layout="wide")

# Auto-refresh every 30 seconds (Task 2.4 requirement)
st_autorefresh(interval=30_000, key="dashboard_refresh")


@st.cache_resource
def get_connection():
    creds = st.secrets["snowflake"]
    return snowflake.connector.connect(
        account=creds["account"],
        user=creds["user"],
        password=creds["password"],
        role=creds["role"],
        warehouse=creds["warehouse"],
        database=creds["database"],
        schema=creds["schema"],
    )


@st.cache_data(ttl=25)
def load_gold() -> pd.DataFrame:
    conn = get_connection()
    query = """
        select device_id, event_date, event_count, avg_latitude, avg_longitude,
               avg_temperature, avg_humidity, avg_aqi, max_aqi, last_seen_at
        from gold_daily_device_agg
        order by event_date desc
    """
    return conn.cursor().execute(query).fetch_pandas_all()


st.title("IoT Fleet Dashboard")
st.caption("Live from Snowflake Gold layer - refreshes every 30s")

df = load_gold()

if df.empty:
    st.warning("No data in the Gold layer yet - check that the pipeline is running.")
    st.stop()

col1, col2, col3 = st.columns(3)
col1.metric("Active devices", df["device_id"].nunique())
col2.metric("Total events (all time)", int(df["event_count"].sum()))
col3.metric("Avg AQI (latest day)", round(df.loc[df["event_date"] == df["event_date"].max(), "avg_aqi"].mean(), 1))

st.subheader("Device activity map")
map_df = df.rename(columns={"avg_latitude": "lat", "avg_longitude": "lon"})
st.map(map_df[["lat", "lon"]].dropna())

st.subheader("AQI trend over time")
aqi_trend = (
    df.groupby("event_date")[["avg_aqi", "max_aqi"]]
    .mean()
    .sort_index()
)
st.line_chart(aqi_trend)

st.subheader("Top devices by event count")
top_n = (
    df.groupby("device_id")["event_count"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
)
st.bar_chart(top_n)

with st.expander("Raw gold table"):
    st.dataframe(df, use_container_width=True)
