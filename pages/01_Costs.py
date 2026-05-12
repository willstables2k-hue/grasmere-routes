"""Costs — per-route and per-delivery, original plan vs optimised."""

from __future__ import annotations

from datetime import date as DateT

import pandas as pd
import streamlit as st

from grasmere_routes.auth import require_user
from grasmere_routes.bootstrap import require_database
from grasmere_routes.day_service import DayResult, load_or_compute_day
from grasmere_routes.format import fmt_gbp, fmt_gbp_rounded, fmt_km, fmt_min, fmt_pct
from grasmere_routes.queries import dates_with_data

st.set_page_config(
    page_title="Grasmere Routes — Costs",
    page_icon="💷",
    layout="wide",
)
require_user()
require_database()


@st.cache_data(ttl=600, show_spinner=False)
def _cached_day(date_iso: str) -> DayResult:
    return load_or_compute_day(DateT.fromisoformat(date_iso))


# ---- date picker (carries over from Map page via session_state) ----
available = dates_with_data()
default = (
    st.session_state.get("active_date")
    or (available[0] if available else DateT.today())
)
if not isinstance(default, DateT):
    default = default.date() if hasattr(default, "date") else DateT.today()

active_date = st.date_input("Delivery date", value=default)
if active_date != st.session_state.get("active_date"):
    st.session_state["active_date"] = active_date

day = _cached_day(active_date.isoformat())

# ---- empty-state ----
if not day.deliveries:
    st.info(
        f"No deliveries imported for **{active_date}**. "
        "Drop a Fresho `delivery_runs` Excel file from the Map page first."
    )
    st.stop()

# ---- saving banner ----
b1, b2, b3 = st.columns([1, 1, 1])
b1.metric("Original plan", fmt_gbp(day.original_total_pence) if day.original_total_pence else "—")
b2.metric("Optimised", fmt_gbp(day.optimised_total_pence) if day.optimised_total_pence else "—")
b3.metric(
    "Saving",
    fmt_gbp(day.saving_pence) if day.saving_pence else "—",
    fmt_pct(day.saving_pct) if day.saving_pct else None,
)

st.divider()

# ---- per-route comparison ----
st.subheader("Cost per route")
st.caption(
    "Each row is one van. Original = legacy run-code grouping (nearest-neighbour "
    "from depot). Optimised = OR-Tools cost-minimised."
)

# Build per-route dataframes (original + optimised) keyed by van_id/colour.
orig_rows = [
    {
        "Van (original)": r.label,
        "Stops": len(r.stop_sequence),
        "km (original)": float(r.total_distance_km),
        "Time (original)": int(r.total_duration_min),
        "£ (original)": int(r.total_cost_pence),
    }
    for r in day.original_routes
]
opt_rows = [
    {
        "Van (optimised)": r.label,
        "Stops ": len(r.stop_sequence),
        "km (optimised)": float(r.total_distance_km),
        "Time (optimised)": int(r.total_duration_min),
        "£ (optimised)": int(r.total_cost_pence),
    }
    for r in day.optimised_routes
]

route_left, route_right = st.columns(2)
with route_left:
    st.markdown("**Original plan (legacy run codes)**")
    if orig_rows:
        df_o = pd.DataFrame(orig_rows)
        st.dataframe(
            pd.DataFrame({
                "Van": df_o["Van (original)"],
                "Stops": df_o["Stops"],
                "km": df_o["km (original)"].apply(fmt_km),
                "Time": df_o["Time (original)"].apply(fmt_min),
                "£": df_o["£ (original)"].apply(fmt_gbp),
            }),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(
            f"Total: {len(orig_rows)} vans · "
            f"{int(df_o['£ (original)'].sum() / 100):,}p · "
            f"{fmt_gbp_rounded(int(df_o['£ (original)'].sum()))}"
        )
    else:
        st.caption("No legacy routing reconstructable for this day.")
with route_right:
    st.markdown("**Optimised plan (OR-Tools)**")
    if opt_rows:
        df_p = pd.DataFrame(opt_rows)
        st.dataframe(
            pd.DataFrame({
                "Van": df_p["Van (optimised)"],
                "Stops": df_p["Stops "],
                "km": df_p["km (optimised)"].apply(fmt_km),
                "Time": df_p["Time (optimised)"].apply(fmt_min),
                "£": df_p["£ (optimised)"].apply(fmt_gbp),
            }),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(
            f"Total: {len(opt_rows)} vans · {fmt_gbp_rounded(int(df_p['£ (optimised)'].sum()))}"
        )
    else:
        st.caption("Optimiser produced no routes.")

st.divider()

# ---- per-delivery comparison ----
st.subheader("Cost per delivery")
st.caption(
    "One row per delivery — the cost allocated to that stop (fuel share + "
    "labour share + flat overhead share) under each plan."
)

orig_cost: dict[str, int] = {}
orig_van: dict[str, str] = {}
for r in day.original_routes:
    for oid, c in r.per_stop_cost_pence.items():
        orig_cost[oid] = c
        orig_van[oid] = r.label

opt_cost: dict[str, int] = {}
opt_van: dict[str, str] = {}
for r in day.optimised_routes:
    for oid, c in r.per_stop_cost_pence.items():
        opt_cost[oid] = c
        opt_van[oid] = r.label

rows = []
for d in day.deliveries:
    o = orig_cost.get(d.order_id)
    p = opt_cost.get(d.order_id)
    delta = (p - o) if (o is not None and p is not None) else None
    rows.append({
        "Customer": d.customer_name,
        "Code": d.customer_code,
        "Order #": d.order_number or "—",
        "Order £": fmt_gbp(d.order_value_pence) if d.order_value_pence else "—",
        "Original van": orig_van.get(d.order_id, "—"),
        "Original cost": fmt_gbp(o) if o is not None else "—",
        "Optimised van": opt_van.get(d.order_id, "—"),
        "Optimised cost": fmt_gbp(p) if p is not None else "—",
        "Δ": fmt_gbp(delta) if delta is not None else "—",
        "_delta": delta if delta is not None else 0,
    })

df = pd.DataFrame(rows).sort_values("_delta", ascending=True).drop(columns=["_delta"])
st.dataframe(df, hide_index=True, use_container_width=True, height=520)

# Excluded summary
if day.excluded:
    with st.expander(f"Excluded from VRP ({len(day.excluded)} mail-order)", expanded=False):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Customer": d.customer_name,
                        "Code": d.customer_code,
                        "Order #": d.order_number or "—",
                        "Order £": fmt_gbp(d.order_value_pence) if d.order_value_pence else "—",
                    }
                    for d in day.excluded
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
