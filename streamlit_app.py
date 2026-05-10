"""Grasmere Routes — Map (landing).

All deliveries on a given day plotted on a map, with the most efficient
route plotted. That's it.
"""

from __future__ import annotations

from datetime import date as DateT, datetime

import pandas as pd
import pydeck as pdk
import streamlit as st

from grasmere_routes.auth import require_user
from grasmere_routes.day_service import (
    DayResult,
    import_file_and_compute,
    load_or_compute_day,
)
from grasmere_routes.format import fmt_gbp, fmt_gbp_rounded, fmt_pct
from grasmere_routes.map_layers import (
    build_route_paths,
    delivery_pin_layer,
    depot_layer,
    make_view_state,
    route_path_layer,
)
from grasmere_routes.queries import (
    dates_with_data,
    get_config,
    get_depot,
    update_config,
)

st.set_page_config(
    page_title="Grasmere Routes — Map",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

require_user()


# ---- cached day loader so flicking between Map and Costs doesn't re-solve ----
@st.cache_data(ttl=600, show_spinner=False)
def _cached_day(date_iso: str) -> DayResult:
    return load_or_compute_day(DateT.fromisoformat(date_iso))


def _clear_day_cache() -> None:
    _cached_day.clear()


def _date_picker_default(available: list) -> DateT:
    if available:
        d = available[0]
        return d if isinstance(d, DateT) else d.date()
    return DateT.today()


def _settings_drawer() -> None:
    """Cost-model parameters tucked into the sidebar."""
    with st.sidebar:
        st.markdown("### ⚙ Cost parameters")
        st.caption("Edit and save — applies to the next page load.")
        cfg = get_config()
        with st.form("cost_params_form", border=False):
            c1, c2 = st.columns(2)
            diesel = c1.number_input(
                "Diesel pence/L", value=int(cfg["diesel_price_pence_per_litre"])
            )
            mpg = c2.number_input(
                "MPG (imperial)", value=float(cfg["default_mpg"]), step=0.1
            )
            hourly = c1.number_input(
                "Driver pence/hr", value=int(cfg["default_driver_hourly_rate_pence"])
            )
            speed = c2.number_input(
                "Avg speed km/h", value=float(cfg["avg_speed_kmh"]), step=0.5
            )
            service_min = c1.number_input(
                "Service min/stop", value=int(cfg["service_time_min_per_stop"])
            )
            loading = c2.number_input(
                "Depot loading min", value=int(cfg["depot_loading_time_min"])
            )
            overhead = c1.number_input(
                "Vehicle £/day pence", value=int(cfg["vehicle_fixed_cost_per_day_pence"])
            )
            shift = c2.number_input(
                "Max shift hrs",
                value=float(cfg["driver_max_shift_hours"]),
                step=0.5,
            )
            if st.form_submit_button("Save", use_container_width=True):
                update_config({
                    "diesel_price_pence_per_litre": diesel,
                    "default_mpg": mpg,
                    "default_driver_hourly_rate_pence": hourly,
                    "avg_speed_kmh": speed,
                    "service_time_min_per_stop": service_min,
                    "depot_loading_time_min": loading,
                    "vehicle_fixed_cost_per_day_pence": overhead,
                    "driver_max_shift_hours": shift,
                })
                _clear_day_cache()
                st.success("Saved.")


# ---- top strip: date picker + uploader ----

available_dates = dates_with_data()
default_date = _date_picker_default(available_dates)
active_date: DateT = st.session_state.get("active_date", default_date)

top_l, top_m, top_r = st.columns([2, 2, 2])
with top_l:
    chosen = st.date_input("Delivery date", value=active_date)
    if chosen != active_date:
        st.session_state["active_date"] = chosen
        active_date = chosen
        st.rerun()
with top_m:
    upload = st.file_uploader(
        "Drop a Fresho `delivery_runs` file",
        type=["xlsx", "xls"],
        label_visibility="visible",
    )
    if upload is not None and st.session_state.get("_last_upload_key") != upload.name + str(upload.size):
        st.session_state["_last_upload_key"] = upload.name + str(upload.size)
        with st.spinner("Importing + optimising…"):
            try:
                day, summary = import_file_and_compute(upload.getvalue())
            except Exception as e:  # noqa: BLE001
                st.error(f"Import failed: {e}")
                day, summary = None, None
        if day is not None:
            st.session_state["active_date"] = day.date
            _clear_day_cache()
            st.toast(
                f"Imported {summary['orders_inserted']} new + "
                f"{summary['orders_updated']} updated · "
                f"{summary['customers_created']} new customers"
            )
            st.rerun()
with top_r:
    if available_dates:
        st.caption(
            f"📅 {len(available_dates)} day(s) with data · most recent: "
            f"{available_dates[0]}"
        )
    else:
        st.caption("📅 No days imported yet")

# ---- compute (cached) ----
day = _cached_day(active_date.isoformat())

# ---- headline metrics ----
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Stops", len(day.deliveries))
total_value = sum((d.order_value_pence or 0) for d in day.deliveries)
m2.metric("Order value", fmt_gbp(total_value) if total_value else "—")
m3.metric("Optimised", fmt_gbp_rounded(day.optimised_total_pence) if day.optimised_total_pence else "—")
m4.metric("Original plan", fmt_gbp_rounded(day.original_total_pence) if day.original_total_pence else "—")
m5.metric(
    "Saving",
    fmt_gbp_rounded(day.saving_pence) if day.saving_pence else "—",
    fmt_pct(day.saving_pct) if day.saving_pct else None,
)

# ---- map ----
depot = get_depot()
depot_lat, depot_lng = float(depot["lat"]), float(depot["lng"])

if not day.deliveries:
    st.info(
        f"No deliveries imported for **{active_date}**. Drop a Fresho "
        "`delivery_runs` Excel file in the uploader above for that date."
    )
    deck = pdk.Deck(
        map_style=None,
        initial_view_state=pdk.ViewState(latitude=depot_lat, longitude=depot_lng, zoom=8),
        layers=[depot_layer(depot_lat, depot_lng)],
    )
else:
    # Decorate deliveries with their optimised vehicle assignment
    vehicle_for: dict[str, str] = {}
    for r in day.optimised_routes:
        for oid in r.stop_sequence:
            vehicle_for[oid] = r.vehicle_id

    delivery_dicts = []
    for d in day.deliveries:
        vid = vehicle_for.get(d.order_id)
        if vid is None:
            continue  # unassigned by optimiser
        # find sequence position within that route
        seq = next(
            (
                i + 1
                for r in day.optimised_routes
                if r.vehicle_id == vid
                for i, oid in enumerate(r.stop_sequence)
                if oid == d.order_id
            ),
            None,
        )
        delivery_dicts.append(
            {
                "order_id": d.order_id,
                "lat": d.lat,
                "lng": d.lng,
                "vehicle_id": vid,
                "name": d.customer_name,
                "order_number": d.order_number or "",
                "order_value_pence": d.order_value_pence,
                "sequence": seq,
            }
        )

    vehicle_order = sorted({d["vehicle_id"] for d in delivery_dicts})
    paths = build_route_paths(
        [{"vehicle_id": r.vehicle_id, "stop_sequence": r.stop_sequence} for r in day.optimised_routes],
        delivery_dicts,
        depot_lat=depot_lat,
        depot_lng=depot_lng,
    )

    deck = pdk.Deck(
        map_style=None,
        initial_view_state=make_view_state(delivery_dicts, depot_lat, depot_lng),
        layers=[
            route_path_layer(paths, vehicle_order=vehicle_order),
            delivery_pin_layer(delivery_dicts, vehicle_order=vehicle_order),
            depot_layer(depot_lat, depot_lng),
        ],
        tooltip={
            "html": (
                "<b>{name}</b><br/>"
                "Stop {sequence} · {vehicle_id}<br/>"
                "Order {order_number} · {order_value}"
            ),
            "style": {"backgroundColor": "rgba(15,23,42,0.92)", "color": "white"},
        },
    )

st.pydeck_chart(deck, use_container_width=True, height=620)

if day.excluded:
    st.caption(
        f"ℹ️ Excluded {len(day.excluded)} mail-order ({', '.join('~NR' for _ in day.excluded[:1])}) "
        "deliveries — they don't ride a van."
    )

_settings_drawer()
