from __future__ import annotations

import os
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from databricks import sql
from databricks.sdk.core import Config


st.set_page_config(
    page_title="Faultline | CDC Reliability",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      :root { --signal: #ffb000; --good: #37d67a; --bad: #ff5b5b; }
      .stApp { background: #090d12; color: #eef3f8; }
      [data-testid="stSidebar"] { background: #101720; border-right: 1px solid #27313d; }
      [data-testid="stMetric"] {
        background: linear-gradient(145deg, #121a24, #0c1219);
        border: 1px solid #283443; border-radius: 10px; padding: 14px 16px;
      }
      [data-testid="stMetricValue"] { color: var(--signal); font-family: monospace; }
      h1, h2, h3 { letter-spacing: -0.02em; }
      .eyebrow { color: #8ea0b4; font: 600 0.75rem monospace; letter-spacing: .18em; }
      .status-ok {
        display: inline-block; padding: .28rem .65rem; border: 1px solid #237a4a;
        border-radius: 999px; color: var(--good); background: #0c2418; font: 600 .78rem monospace;
      }
      .status-warn {
        display: inline-block; padding: .28rem .65rem; border: 1px solid #805c12;
        border-radius: 999px; color: var(--signal); background: #281d08; font: 600 .78rem monospace;
      }
      div[data-testid="stDataFrame"] { border: 1px solid #283443; border-radius: 8px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required app resource: {name}")
    return value


@st.cache_resource
def get_connection():
    cfg = Config()
    hostname = urlparse(cfg.host).netloc or cfg.host
    warehouse_id = required_env("DATABRICKS_WAREHOUSE_ID")
    return sql.connect(
        server_hostname=hostname,
        http_path=f"/sql/1.0/warehouses/{warehouse_id}",
        credentials_provider=lambda: cfg.authenticate,
        _use_arrow_native_complex_types=False,
    )


@st.cache_data(ttl=15, show_spinner=False)
def query(statement: str) -> pd.DataFrame:
    with get_connection().cursor() as cursor:
        cursor.execute(statement)
        return cursor.fetchall_arrow().to_pandas()


def table_env(name: str) -> str:
    table = required_env(name)
    if not all(part.replace("_", "").isalnum() for part in table.split(".")):
        raise RuntimeError(f"Invalid managed table resource: {name}")
    return table


reliability_table = table_env("FAULTLINE_RELIABILITY_TABLE")
current_table = table_env("FAULTLINE_CURRENT_TABLE")
quarantine_table = table_env("FAULTLINE_QUARANTINE_TABLE")
history_table = table_env("FAULTLINE_HISTORY_TABLE")

with st.sidebar:
    st.markdown('<div class="eyebrow">FAULTLINE // CONTROL</div>', unsafe_allow_html=True)
    st.title("CDC Reliability Lab")
    st.markdown('<span class="status-ok">● WORKSPACE VALIDATED</span>', unsafe_allow_html=True)
    st.divider()
    st.caption("SOURCE MODE")
    st.code("Lakebase CDF-compatible Delta", language=None)
    st.caption(
        "Free Edition default storage cannot host native Lakebase CDF. "
        "The source preserves its documented row contract and system columns."
    )
    if st.button("Refresh signals", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.markdown('<div class="eyebrow">INCIDENT CONSOLE / LIVE STATE</div>', unsafe_allow_html=True)
st.title("Prove the lakehouse converges after bad delivery.")
st.caption(
    "Duplicates, corrupt values, update preimages, out-of-order sequences, and deletes "
    "flow through expectations, quarantine, and AUTO CDC projections."
)

try:
    reliability = query(f"SELECT * FROM {reliability_table}").iloc[0]
    current = query(
        f"SELECT order_id, customer_id, amount_cents, status, updated_at, _sort_by "
        f"FROM {current_table} ORDER BY order_id"
    )
    quarantine = query(
        f"SELECT order_id, amount_cents, status, violation_reasons, _sort_by "
        f"FROM {quarantine_table} ORDER BY _sort_by DESC"
    )
    history = query(
        f"SELECT order_id, status, amount_cents, __START_AT, __END_AT "
        f"FROM {history_table} ORDER BY order_id, __START_AT"
    )

    cols = st.columns(5)
    cols[0].metric("Received", int(reliability["received_events"]))
    cols[1].metric("Distinct", int(reliability["distinct_events"]))
    cols[2].metric("Duplicates", int(reliability["duplicate_events"]))
    cols[3].metric("Quarantined", len(quarantine))
    cols[4].metric("Current rows", len(current))

    left, right = st.columns([1.45, 1])
    with left:
        st.subheader("Current order state")
        st.caption("SCD Type 1 projection after ordered upserts and tombstone deletes.")
        st.dataframe(current, use_container_width=True, hide_index=True)

    with right:
        st.subheader("Data-quality disposition")
        quality = pd.DataFrame(
            {
                "disposition": ["accepted", "duplicate", "quarantined", "audit preimage"],
                "events": [
                    int(reliability["actionable_events"]) - len(quarantine),
                    int(reliability["duplicate_events"]),
                    len(quarantine),
                    int(reliability["audit_preimages"]),
                ],
            }
        ).set_index("disposition")
        st.bar_chart(quality, color="#ffb000", horizontal=True)

    st.subheader("Quarantine")
    if quarantine.empty:
        st.success("No invalid actionable events detected.")
    else:
        st.markdown(
            f'<span class="status-warn">{len(quarantine)} EVENT NEEDS REVIEW</span>',
            unsafe_allow_html=True,
        )
        st.dataframe(quarantine, use_container_width=True, hide_index=True)

    with st.expander("SCD Type 2 audit history", expanded=False):
        st.dataframe(history, use_container_width=True, hide_index=True)

    st.caption(
        f"Latest source sequence: {int(reliability['latest_source_sequence'])} · "
        f"Latest source timestamp: {reliability['latest_source_timestamp']}"
    )
except Exception as error:
    st.error("The console could not query its managed resources.")
    st.exception(error)

