"""Planning Pulse NSW — public Streamlit dashboard.

Reads only pre-aggregated, reviewed CSV snapshots from dashboard_data/. It
never opens the local DuckDB database, and the CSVs it reads contain no
addresses, coordinates, application numbers, or lot/plan details — see
dashboard_data/README (referenced from the main project README) for how
they are generated (scripts/export_dashboard_data.py).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

DATA_DIR = Path("dashboard_data")

st.set_page_config(
    page_title="Planning Pulse NSW",
    page_icon="🏗️",
    layout="wide",
)


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    council = pd.read_csv(DATA_DIR / "council_activity.csv")
    category = pd.read_csv(DATA_DIR / "category_activity.csv")
    metadata = pd.read_csv(DATA_DIR / "snapshot_metadata.csv").iloc[0]
    return council, category, metadata


council_activity, category_activity, metadata = load_data()

st.title("🏗️ Planning Pulse NSW")
st.caption(
    "Development-application activity from the NSW Online DA Data API, "
    "published by the NSW Department of Planning, Housing and Infrastructure "
    "/ NSW Planning Portal, licensed under CC BY 4.0."
)

st.subheader("About this snapshot")
st.info(
    f"This is a **recent-update snapshot**, not a complete record of all NSW planning "
    f"activity: **{int(metadata['total_applications']):,} applications** across "
    f"**{int(metadata['distinct_councils'])} councils**, fetched as a "
    f"{int(metadata['snapshot_record_limit']):,}-record local sample filtered to applications "
    f"last updated on or after **{metadata['application_last_updated_from']}**. "
    f"Within that sample, source `date_last_updated` values range from "
    f"{metadata['date_last_updated_min']} to {metadata['date_last_updated_max']}. "
    "This does **not** mean every application updated since that date is included — "
    "it is a bounded, point-in-time pull, not a full or time-consistent extract.\n\n"
    "**This project is descriptive, not evaluative.** Application counts and cost "
    "figures reflect what is present in this sample and must not be used to rank "
    "council performance, infer processing efficiency, or draw equity conclusions. "
    "Council participation in the Online DA Data API became mandatory only in July "
    "2021; earlier coverage may be incomplete."
)
st.caption(f"Snapshot exported at {metadata['export_generated_at']} (UTC).")

st.divider()

st.subheader("Application counts by status and type")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**By application status**")
    status_counts = (
        council_activity.groupby("application_status")["application_count"].sum().sort_values(ascending=False)
    )
    st.bar_chart(status_counts)
with col2:
    st.markdown("**By application type**")
    type_counts = council_activity.groupby("application_type")["application_count"].sum().sort_values(ascending=False)
    st.bar_chart(type_counts)

st.divider()

st.subheader("Council activity")
st.caption(
    "Application counts per council in this sample. Not a ranking — councils vary in "
    "size, population, and development volume, and this is a partial, filtered sample."
)
status_options = ["All"] + sorted(council_activity["application_status"].unique().tolist())
selected_status = st.selectbox("Filter by application status", status_options, key="council_status_filter")

filtered_council = council_activity if selected_status == "All" else council_activity[
    council_activity["application_status"] == selected_status
]
council_totals = (
    filtered_council.groupby("council_name")["application_count"]
    .sum()
    .sort_values(ascending=False)
    .head(20)
)
st.bar_chart(council_totals)
st.dataframe(filtered_council.sort_values("application_count", ascending=False), use_container_width=True)

st.divider()

st.subheader("Development-category activity")
st.caption("Application counts per development category in this sample.")
category_options = ["All"] + sorted(category_activity["application_status"].unique().tolist())
selected_category_status = st.selectbox("Filter by application status", category_options, key="category_status_filter")

filtered_category = category_activity if selected_category_status == "All" else category_activity[
    category_activity["application_status"] == selected_category_status
]
category_totals = (
    filtered_category.groupby("development_type")["application_count"]
    .sum()
    .sort_values(ascending=False)
    .head(20)
)
st.bar_chart(category_totals)
st.dataframe(filtered_category.sort_values("application_count", ascending=False), use_container_width=True)
