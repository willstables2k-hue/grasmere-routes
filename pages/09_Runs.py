"""Runs — planned vs actual variance over the last 60 days."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from grasmere_routes.auth import require_role
from grasmere_routes.format import fmt_gbp, fmt_km
from grasmere_routes.queries import runs_last_n_days

st.set_page_config(page_title="Runs · Grasmere Routes", page_icon="📜", layout="wide")
require_role("admin", "dispatcher")

st.title("Runs — planned vs actual")
st.caption("Variance flags where the plan diverged from reality.")


def _variance_pct(planned, actual) -> str:
    if planned in (None, 0) or actual is None or pd.isna(actual) or pd.isna(planned):
        return "—"
    delta = (float(actual) - float(planned)) / float(planned) * 100
    return f"{'+' if delta > 0 else ''}{delta:.1f}%"


rows = runs_last_n_days(60)
if rows.empty:
    st.info("No runs in the last 60 days.")
    st.stop()

view = pd.DataFrame(
    {
        "Date": rows["delivery_date"].astype(str),
        "Status": rows["status"],
        "Stops": rows["stops"],
        "Planned km": rows["planned_distance_km"].apply(
            lambda v: fmt_km(float(v)) if pd.notna(v) else "—"
        ),
        "Actual km": rows["actual_distance_km"].apply(
            lambda v: fmt_km(float(v)) if pd.notna(v) else "—"
        ),
        "Δ km": [
            _variance_pct(p, a) for p, a in zip(rows["planned_distance_km"], rows["actual_distance_km"])
        ],
        "Planned £": rows["planned_total_cost_pence"].apply(
            lambda v: fmt_gbp(int(v)) if pd.notna(v) else "—"
        ),
        "Actual £": rows["actual_total_cost_pence"].apply(
            lambda v: fmt_gbp(int(v)) if pd.notna(v) else "—"
        ),
        "Δ £": [
            _variance_pct(p, a)
            for p, a in zip(rows["planned_total_cost_pence"], rows["actual_total_cost_pence"])
        ],
    }
)
st.dataframe(view, hide_index=True, use_container_width=True)
