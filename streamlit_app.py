"""Grasmere Routes — landing / Overview page."""

from __future__ import annotations

import streamlit as st

from grasmere_routes.auth import require_user
from grasmere_routes.format import fmt_gbp_rounded
from grasmere_routes.queries import (
    get_current_baseline,
    optimised_cost_last_n_days,
    status_counts,
)

st.set_page_config(
    page_title="Grasmere Routes",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded",
)

user = require_user()

st.title("Grasmere Routes")
st.caption(
    "Plan deliveries from scratch each week to minimise fleet cost. "
    "See the unit economics of every route, stop, and customer."
)

# ---- top-line tiles ----
counts = status_counts()
baseline = get_current_baseline()
optimised_week = optimised_cost_last_n_days(7)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Live customers", counts["live"])
c2.metric(
    "Hidden",
    f"{counts['dormant']} dormant",
    f"+{counts['no_history']} no history",
    delta_color="off",
)
c3.metric(
    "Annualised baseline",
    fmt_gbp_rounded(baseline["annualised_cost_pence"]) if baseline else "—",
    help="Live customers only · what the legacy run structure costs to operate",
)
c4.metric(
    "Optimised last 7 days",
    fmt_gbp_rounded(optimised_week) if optimised_week else "—",
)

st.divider()

# ---- shortcuts ----
left, mid, right = st.columns(3)
with left:
    st.subheader("This week")
    st.caption("Pick a date, generate orders, optimise the routes from scratch.")
    st.page_link("pages/01_Plan.py", label="Open planner →", icon="📅")
with mid:
    st.subheader("Current state")
    st.caption("What the legacy colour-coded routes are costing today.")
    st.page_link("pages/02_Baseline.py", label="View baseline →", icon="🗺️")
with right:
    st.subheader("Economics")
    st.caption(
        "Two ROI lines, never blended: data hygiene saving + routing optimisation."
    )
    st.page_link("pages/03_Economics.py", label="Open dashboard →", icon="📈")

st.divider()
st.caption(f"Signed in as {user.email} ({user.role})")
