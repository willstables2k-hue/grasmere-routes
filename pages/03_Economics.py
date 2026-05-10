"""Economics dashboard — KPIs, two ROI lines never blended, bottom 20 customers."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from grasmere_routes.auth import require_role
from grasmere_routes.format import fmt_gbp, fmt_gbp_rounded
from grasmere_routes.queries import (
    bottom_customers_by_net_contribution,
    get_current_baseline,
    optimised_cost_last_n_days,
    status_counts,
)

st.set_page_config(page_title="Economics · Grasmere Routes", page_icon="📈", layout="wide")
require_role("admin", "dispatcher")

st.title("Economics")
st.caption(
    "Where the money goes, what the platform is saving, and which customers are costing you."
)

snap = get_current_baseline()
counts = status_counts()
optimised_week = optimised_cost_last_n_days(7)

baseline_weekly = snap["weekly_cost_pence"] if snap else 0
baseline_annual = snap["annualised_cost_pence"] if snap else 0
baseline_stops = snap["total_stops"] if snap else 0
baseline_per_delivery = baseline_weekly / max(baseline_stops, 1) if snap else 0
optimised_annual = (optimised_week or 0) * 52

# --- two-line ROI ---
# Data hygiene saving — coarse estimate from spec scale (£8.28 true cost/delivery,
# dormant + no_history customers averaging 1.5 deliveries/week each)
ghost_stops_per_week = (counts["dormant"] + counts["no_history"]) * 1.5
data_hygiene_weekly = round(ghost_stops_per_week * 828)
data_hygiene_annual = data_hygiene_weekly * 52

routing_optim_annual = (
    baseline_annual - optimised_annual if baseline_annual and optimised_annual else 0
)
total_annual = data_hygiene_annual + routing_optim_annual

# ---- top KPIs ----
k1, k2, k3, k4 = st.columns(4)
k1.metric(
    "Baseline / week",
    fmt_gbp(baseline_weekly),
    f"Live only · {baseline_stops} stops",
    delta_color="off",
)
k2.metric(
    "Optimised this week",
    fmt_gbp(optimised_week) if optimised_week else "—",
    "sum of planned routes (last 7d)",
    delta_color="off",
)
k3.metric("Avg cost / delivery", fmt_gbp(round(baseline_per_delivery)))
k4.metric("Annualised baseline", fmt_gbp_rounded(baseline_annual))

# ---- two ROI lines (the most important panel) ----
st.divider()
with st.container(border=True):
    st.subheader("Annual saving — broken down")
    st.caption("Two lines, deliberately additive, never blended.")
    a, b, c = st.columns(3)
    with a:
        st.markdown("**1. Data hygiene** ▸ recurring")
        st.markdown(f"### {fmt_gbp_rounded(data_hygiene_annual)}/year")
        st.caption(
            f"Recovered from no longer planning for {counts['dormant']} dormant + "
            f"{counts['no_history']} no-history customers."
        )
    with b:
        st.markdown("**2. Routing optimisation** ▸ requires solver")
        st.markdown(f"### {fmt_gbp_rounded(routing_optim_annual)}/year")
        st.caption(
            "What OR-Tools contributes on top, after the customer base is honest."
        )
    with c:
        st.markdown("**Total annual saving**")
        st.markdown(
            f"<h2 style='color:#16a34a;margin-top:0'>{fmt_gbp_rounded(total_annual)}/year</h2>",
            unsafe_allow_html=True,
        )
        st.caption("Sum of the two lines — defendable to a sceptic.")

# ---- charts ----
st.divider()
chart_l, chart_r = st.columns(2)
with chart_l:
    st.subheader("Where the money goes")
    breakdown = pd.DataFrame(
        {
            "Component": ["Labour", "Fuel", "Overhead"],
            "Pence": [
                round(baseline_weekly * 0.69),
                round(baseline_weekly * 0.21),
                round(baseline_weekly * 0.10),
            ],
        }
    )
    breakdown["£"] = breakdown["Pence"] / 100
    st.plotly_chart(
        px.bar(breakdown, x="Component", y="£", text=breakdown["£"].apply(lambda v: f"£{v:,.0f}")),
        use_container_width=True,
    )

bottom = bottom_customers_by_net_contribution(20)
with chart_r:
    st.subheader("Customer profitability")
    if bottom.empty:
        st.info("Populated once you publish your first optimised plan.")
    else:
        fig = px.scatter(
            bottom,
            x=bottom["avg_order_value_pence"] / 100,
            y=bottom["marginal_cost_pence"] / 100,
            size=bottom["frequency_per_year"],
            hover_name="name",
            labels={"x": "Avg order £", "y": "Marginal cost £"},
        )
        st.plotly_chart(fig, use_container_width=True)

# ---- bottom 20 table ----
st.divider()
st.subheader("Bottom 20 customers by net contribution")
st.caption(
    "Negative contribution = losing money on every delivery, after the marginal "
    "cost of serving them. Renegotiate, add a delivery fee, or move to a different day."
)
if bottom.empty:
    st.info("No published routes yet — populate this table by publishing a plan.")
else:
    view = pd.DataFrame(
        {
            "Customer": bottom["name"] + " (" + bottom["customer_code"] + ")",
            "Avg order": bottom["avg_order_value_pence"].apply(fmt_gbp),
            "Marginal cost": bottom["marginal_cost_pence"].apply(fmt_gbp),
            "Net contribution": bottom["net_contribution_pence"].apply(fmt_gbp),
            "Freq / yr": bottom["frequency_per_year"],
        }
    )
    st.dataframe(view, hide_index=True, use_container_width=True)
