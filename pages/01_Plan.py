"""Plan a delivery week — generate orders, optimise from scratch, see savings vs baseline."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from grasmere_routes.auth import require_role
from grasmere_routes.format import fmt_gbp, fmt_km, fmt_min, fmt_pct
from grasmere_routes.plan_service import generate_orders, optimise_plan, publish_routes

st.set_page_config(page_title="Plan · Grasmere Routes", page_icon="📅", layout="wide")
require_role("admin", "dispatcher")

st.title("Plan delivery week")
st.caption(
    "Pick a date, generate orders for live customers, then re-cut routes from scratch. "
    "Dormant + no-history customers are excluded automatically."
)


def _next_tuesday() -> date:
    today = date.today()
    days_ahead = (1 - today.weekday()) % 7 or 7
    return today + timedelta(days=days_ahead)


col_date, col_gen, col_opt, col_pub = st.columns([1, 1, 1, 1])
with col_date:
    chosen = st.date_input("Delivery date", value=_next_tuesday())
date_str = chosen.isoformat()

with col_gen:
    if st.button("Generate orders", use_container_width=True):
        with st.spinner("Generating orders…"):
            res = generate_orders(date_str)
        st.session_state["plan_orders_msg"] = (
            f"{res['orders_created']} new orders · "
            f"{res['live_matching']} live customers match this day · "
            f"{res['dormant_matching_hidden']} dormant hidden"
        )

if msg := st.session_state.get("plan_orders_msg"):
    st.info(msg)

with col_opt:
    if st.button("Optimise", use_container_width=True, type="primary"):
        with st.spinner("Solving VRP…"):
            res = optimise_plan(date_str)
        st.session_state["plan_result"] = res

with col_pub:
    if st.button("Publish to drivers", use_container_width=True):
        n = publish_routes(date_str)
        st.success(f"Published {n} draft routes to drivers.")

result = st.session_state.get("plan_result")
if result and result.get("ok") is False:
    st.warning(result.get("reason"))
elif result and result.get("ok"):
    st.divider()

    # ---- headline saving banner ----
    a, b, c = st.columns(3)
    a.metric("Optimised plan", fmt_gbp(result["optimised_total_pence"]))
    b.metric(
        "Baseline (same customers, current routing)",
        fmt_gbp(result["baseline_total_pence"]),
    )
    c.metric(
        "Saving",
        fmt_gbp(result["saving_pence"]),
        f"{fmt_pct(result['saving_pct'])} vs baseline",
    )

    st.caption(
        f"Solved in {result['solve_seconds']:.2f}s · "
        + (
            f"{len(result['unassigned'])} stops unassigned"
            if result["unassigned"]
            else "all stops assigned"
        )
    )

    # ---- per-route table ----
    st.subheader("Routes")
    rows = []
    for r in result["routes"]:
        n = max(len(r["stop_sequence"]), 1)
        rows.append(
            {
                "Vehicle": r["vehicle_id"],
                "Stops": len(r["stop_sequence"]),
                "km": fmt_km(r["total_distance_km"]),
                "Time": fmt_min(r["total_duration_min"]),
                "Fuel": fmt_gbp(r["fuel_cost_pence"]),
                "Labour": fmt_gbp(r["labour_cost_pence"]),
                "Overhead": fmt_gbp(r["overhead_pence"]),
                "Total £": fmt_gbp(r["total_cost_pence"]),
                "£/stop": fmt_gbp(round(r["total_cost_pence"] / n))
                if r["stop_sequence"]
                else "—",
            }
        )
    st.dataframe(rows, hide_index=True, use_container_width=True)

    # ---- map ----
    st.subheader("Map")
    try:
        import pydeck as pdk
        from grasmere_routes.queries import get_depot, orders_for_date

        depot = get_depot()
        orders = orders_for_date(date_str)
        order_lookup = {str(o["order_id"]): (float(o["lat"]), float(o["lng"])) for _, o in orders.iterrows()}
        palette = [
            [231, 76, 60], [52, 152, 219], [46, 204, 113], [241, 196, 15],
            [155, 89, 182], [230, 126, 34], [26, 188, 156], [149, 165, 166],
        ]
        path_data = []
        scatter_data = []
        for i, r in enumerate(result["routes"]):
            colour = palette[i % len(palette)]
            path = [[depot["lng"], depot["lat"]]]
            for oid in r["stop_sequence"]:
                latlng = order_lookup.get(str(oid))
                if not latlng:
                    continue
                lat, lng = latlng
                path.append([lng, lat])
                scatter_data.append({"position": [lng, lat], "color": colour, "vehicle": r["vehicle_id"]})
            path.append([depot["lng"], depot["lat"]])
            path_data.append({"path": path, "color": colour})

        layer_paths = pdk.Layer(
            "PathLayer",
            data=path_data,
            get_path="path",
            get_color="color",
            width_scale=20,
            width_min_pixels=2,
        )
        layer_stops = pdk.Layer(
            "ScatterplotLayer",
            data=scatter_data,
            get_position="position",
            get_color="color",
            get_radius=400,
            pickable=True,
        )
        layer_depot = pdk.Layer(
            "ScatterplotLayer",
            data=[{"position": [depot["lng"], depot["lat"]]}],
            get_position="position",
            get_color=[0, 0, 0],
            get_radius=900,
        )
        st.pydeck_chart(
            pdk.Deck(
                map_style=None,
                initial_view_state=pdk.ViewState(
                    latitude=depot["lat"], longitude=depot["lng"], zoom=8
                ),
                layers=[layer_paths, layer_stops, layer_depot],
            )
        )
    except Exception as e:  # noqa: BLE001
        st.info(f"Map render failed: {e}")
