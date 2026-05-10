"""Baseline — what the legacy colour-coded routes cost today (live customers only)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from grasmere_routes.auth import require_role
from grasmere_routes.baseline_service import recompute_baseline
from grasmere_routes.format import fmt_gbp, fmt_gbp_rounded, fmt_km, fmt_min
from grasmere_routes.queries import get_baseline_routes, get_current_baseline

st.set_page_config(page_title="Baseline · Grasmere Routes", page_icon="🗺️", layout="wide")
require_role("admin", "dispatcher")

DAY_LABELS = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}

snap = get_current_baseline()

top_l, top_r = st.columns([3, 1])
with top_l:
    st.title("Baseline")
    if snap:
        st.caption(
            f"Cost of running the legacy colour-coded routes — live customers only. "
            f"Computed {snap['computed_at'].strftime('%Y-%m-%d %H:%M')}."
        )
    else:
        st.caption("No baseline computed yet — recompute once customers are imported and geocoded.")
with top_r:
    if st.button("Recompute baseline", type="primary", use_container_width=True):
        with st.spinner("Calling optimiser /baseline_cost…"):
            try:
                out = recompute_baseline()
                st.success(
                    f"Baseline recomputed · {out['customer_count_included']} live customers · "
                    f"{fmt_gbp_rounded(out['weekly_cost_pence'])}/week"
                )
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(str(e))

if not snap:
    st.stop()

# ---- KPI tiles ----
avg_per_delivery = snap["total_cost_pence"] / max(snap["total_stops"], 1)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Weekly fleet cost", fmt_gbp_rounded(snap["weekly_cost_pence"]))
k2.metric("Annualised (× 52)", fmt_gbp_rounded(snap["annualised_cost_pence"]))
k3.metric("Average £/delivery", fmt_gbp(round(avg_per_delivery)))
k4.metric("Stops · km/week", f"{snap['total_stops']} · {fmt_km(float(snap['total_distance_km']))}")

# ---- caveats panel (always visible) ----
st.divider()
with st.container(border=True):
    st.subheader("Honesty caveats")
    st.markdown(
        f"""
- Sequencing within each van is **assumed** (nearest-neighbour from depot). The CSV's
  `delivery_run_position` is loading-bay zone info, not true drive order.
- **{snap['customer_count_excluded']}** customers excluded — mail-order (`~NR`),
  unparseable run codes (e.g. `5ME`, `MMR`), or no geocode yet.
- Dormant + no-history customers are **not counted** here. The "data hygiene" line
  on /economics quantifies what those ghost stops would have cost.
- Baseline and optimised plans use the same Mapbox driving distances and the same
  cost model — the only difference between them is sequencing and van assignment.
        """
    )

# ---- per-route table sorted by £/stop, worst first ----
st.divider()
st.subheader("Routes — sorted by £/stop, worst first")
st.caption("The top of this list is where the optimiser will save the most.")

routes = get_baseline_routes(snap["id"])
routes = routes.sort_values("cost_per_stop_pence", ascending=False)
view = pd.DataFrame(
    {
        "Van": routes["van_colour"],
        "Day": [DAY_LABELS.get(int(d), d) for d in routes["day_of_week"]],
        "Stops": routes["stop_count"],
        "km": routes["distance_km"].apply(lambda v: fmt_km(float(v))),
        "Time": routes["duration_min"].apply(fmt_min),
        "Fuel": routes["fuel_cost_pence"].apply(fmt_gbp),
        "Labour": routes["labour_cost_pence"].apply(fmt_gbp),
        "Overhead": routes["overhead_pence"].apply(fmt_gbp),
        "Total £": routes["total_cost_pence"].apply(fmt_gbp),
        "£/stop": routes["cost_per_stop_pence"].apply(fmt_gbp),
    }
)
st.dataframe(view, hide_index=True, use_container_width=True)
