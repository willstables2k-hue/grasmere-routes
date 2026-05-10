"""Admin — config, vehicles, drivers, migrations."""

from __future__ import annotations

import streamlit as st

from grasmere_routes.auth import require_role
from grasmere_routes.db import run_migrations
from grasmere_routes.queries import (
    get_config,
    list_drivers,
    list_vehicles,
    update_config,
)

st.set_page_config(page_title="Admin · Grasmere Routes", page_icon="⚙️", layout="wide")
require_role("admin")

st.title("Admin")

# ---- migrations ----
with st.container(border=True):
    st.subheader("Schema")
    if st.button("Run migrations + seed", help="Idempotent — safe to re-run"):
        with st.spinner("Applying SQL files…"):
            try:
                run_migrations()
                st.success("Migrations applied.")
            except Exception as e:  # noqa: BLE001
                st.error(str(e))

# ---- config ----
st.divider()
st.subheader("Cost parameters")
st.caption(
    "Defaults from the build spec. Edit and save; effects apply to the next plan. "
    "Recompute the baseline manually for these to flow through."
)

cfg = get_config()
with st.form("cfg"):
    g1, g2 = st.columns(2)
    with g1:
        diesel = st.number_input("Diesel price (pence/L)", value=int(cfg["diesel_price_pence_per_litre"]))
        mpg = st.number_input("Vehicle mpg (imperial)", value=float(cfg["default_mpg"]), step=0.1)
        hourly = st.number_input("Driver wage (pence/hr)", value=int(cfg["default_driver_hourly_rate_pence"]))
        speed = st.number_input("Average road speed (km/h)", value=float(cfg["avg_speed_kmh"]), step=0.5)
        service_min = st.number_input("Service time per stop (min)", value=int(cfg["service_time_min_per_stop"]))
    with g2:
        loading = st.number_input("Depot loading time (min)", value=int(cfg["depot_loading_time_min"]))
        veh_fixed = st.number_input("Vehicle fixed cost / day (pence)", value=int(cfg["vehicle_fixed_cost_per_day_pence"]))
        max_shift = st.number_input("Max shift (hours)", value=float(cfg["driver_max_shift_hours"]), step=0.5)
        margin = st.number_input("Default gross margin", value=float(cfg["default_gross_margin_pct"]), step=0.001, format="%.3f")
        dormancy = st.number_input("Dormancy threshold (days)", value=int(cfg["dormancy_threshold_days"]))

    if st.form_submit_button("Save", type="primary"):
        update_config({
            "diesel_price_pence_per_litre": diesel,
            "default_mpg": mpg,
            "default_driver_hourly_rate_pence": hourly,
            "avg_speed_kmh": speed,
            "service_time_min_per_stop": service_min,
            "depot_loading_time_min": loading,
            "vehicle_fixed_cost_per_day_pence": veh_fixed,
            "driver_max_shift_hours": max_shift,
            "default_gross_margin_pct": margin,
            "dormancy_threshold_days": dormancy,
        })
        st.success("Saved.")

# ---- vehicles + drivers ----
st.divider()
st.subheader("Vehicles")
st.dataframe(list_vehicles(active_only=False), hide_index=True, use_container_width=True)

st.subheader("Drivers")
st.dataframe(list_drivers(active_only=False), hide_index=True, use_container_width=True)
