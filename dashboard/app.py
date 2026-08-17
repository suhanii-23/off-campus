"""Streamlit dashboard for reviewing discovered jobs.

Run with: streamlit run dashboard/app.py
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# `streamlit run` puts this file's own directory on sys.path, not the repo
# root, so sibling packages like `database` won't import without this.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from config import settings  # noqa: F401 - import triggers load_dotenv() so DATABASE_URL is read from .env
from database.engine import get_session, init_db
from database.models import Job

APPLICATION_STATUSES = ["new", "notified", "applied", "skipped", "rejected", "interview", "offer"]

st.set_page_config(page_title="Job Hunter Dashboard", layout="wide")


@st.cache_resource
def _init():
    init_db()


def load_jobs() -> pd.DataFrame:
    session = get_session()
    try:
        jobs = session.query(Job).filter(Job.is_active.is_(True)).all()
        rows = [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company_name,
                "score": j.score_final,
                "categories": ", ".join(j.categories or []),
                "experience_fit": j.experience_fit,
                "india_eligible": j.india_eligible,
                "location": j.location_raw,
                "employment_type": j.employment_type,
                "posted_at": j.posted_at,
                "first_seen_at": j.first_seen_at,
                "notified": j.notified_at is not None,
                "application_status": j.application_status,
                "apply_url": j.apply_url,
            }
            for j in jobs
        ]
        return pd.DataFrame(rows)
    finally:
        session.close()


def save_status_changes(edited_df: pd.DataFrame) -> None:
    session = get_session()
    try:
        for _, row in edited_df.iterrows():
            job = session.query(Job).filter(Job.id == row["id"]).one_or_none()
            if job and job.application_status != row["application_status"]:
                job.application_status = row["application_status"]
        session.commit()
    finally:
        session.close()


_init()
st.title("Job Hunter Dashboard")

df = load_jobs()

if df.empty:
    st.info("No jobs in the database yet. Run `python main.py` to scan companies first.")
    st.stop()

now = datetime.now(timezone.utc)
df["reference_date"] = df["posted_at"].fillna(df["first_seen_at"])
df["age_days"] = (now - pd.to_datetime(df["reference_date"], utc=True)).dt.days

# --- Top metrics ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total active jobs", len(df))
col2.metric("New today", int((df["age_days"] <= 0).sum()))
col3.metric("High matches (80+)", int((df["score"] >= 80).sum()))
col4.metric("Companies discovered", df["company"].nunique())

# --- Filters ---
st.sidebar.header("Filters")
min_score = st.sidebar.slider("Minimum score", 0, 100, 0)
all_categories = sorted({c for cats in df["categories"] for c in cats.split(", ") if c})
selected_categories = st.sidebar.multiselect("Categories", all_categories)
all_companies = sorted(df["company"].unique())
selected_companies = st.sidebar.multiselect("Companies", all_companies)
location_search = st.sidebar.text_input("Location contains")
employment_types = sorted(df["employment_type"].dropna().unique())
selected_employment = st.sidebar.multiselect("Employment type", employment_types)
max_age_days = st.sidebar.slider("Max posting age (days)", 0, 90, 90)

filtered = df[df["score"].fillna(0) >= min_score]
filtered = filtered[filtered["age_days"] <= max_age_days]
if selected_categories:
    filtered = filtered[filtered["categories"].apply(lambda c: any(cat in c for cat in selected_categories))]
if selected_companies:
    filtered = filtered[filtered["company"].isin(selected_companies)]
if location_search:
    filtered = filtered[filtered["location"].fillna("").str.contains(location_search, case=False)]
if selected_employment:
    filtered = filtered[filtered["employment_type"].isin(selected_employment)]

filtered = filtered.sort_values("score", ascending=False)

st.subheader(f"Jobs ({len(filtered)})")
editable = filtered[
    ["id", "title", "company", "score", "categories", "experience_fit", "india_eligible",
     "location", "employment_type", "age_days", "application_status", "apply_url"]
].reset_index(drop=True)

edited = st.data_editor(
    editable,
    column_config={
        "application_status": st.column_config.SelectboxColumn(options=APPLICATION_STATUSES),
        "apply_url": st.column_config.LinkColumn(),
        "id": None,  # hide internal id from view but keep it for saving
    },
    disabled=[c for c in editable.columns if c != "application_status"],
    hide_index=True,
    use_container_width=True,
)

if st.button("Save application status changes"):
    save_status_changes(edited)
    st.success("Saved.")
    st.cache_resource.clear()
    st.rerun()
