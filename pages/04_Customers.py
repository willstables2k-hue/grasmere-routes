"""Customer database — searchable, filterable, defaults to live."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from grasmere_routes.auth import require_role
from grasmere_routes.format import fmt_gbp, fmt_relative_days
from grasmere_routes.queries import list_customers, status_counts

st.set_page_config(page_title="Customers · Grasmere Routes", page_icon="👥", layout="wide")
require_role("admin", "dispatcher")

st.title("Customers")
counts = status_counts()
st.caption(
    f"{counts['live']} live · {counts['dormant']} dormant · {counts['no_history']} no history"
)

# ---- filters ----
with st.expander("Filters", expanded=True):
    f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
    with f1:
        search = st.text_input("Search name or code", "")
    with f2:
        status_choice = st.selectbox(
            "Status",
            options=["live only", "all", "dormant", "no_history"],
            index=0,
        )
    with f3:
        run_code = st.text_input("Run code (e.g. WP0)", "")
    with f4:
        cod_choice = st.selectbox("COD?", options=["any", "yes", "no"], index=0)

status_map = {
    "live only": ("live",),
    "all": ("live", "dormant", "no_history"),
    "dormant": ("dormant",),
    "no_history": ("no_history",),
}
cod_param = {"yes": True, "no": False}.get(cod_choice)

rows = list_customers(
    statuses=status_map[status_choice],
    search=search or None,
    run_code=run_code.strip() or None,
    cod=cod_param,
    limit=500,
)

# ---- "+N hidden" pill when defaulting to live ----
if status_choice == "live only" and (counts["dormant"] + counts["no_history"]) > 0:
    st.info(
        f"➕ {counts['dormant']} dormant, +{counts['no_history']} no-history customers "
        "hidden — switch the Status filter to see them, or open Dormant review."
    )
    st.page_link("pages/05_Dormant.py", label="Review dormant →", icon="🗂️")

st.caption(f"{len(rows)} customers shown")

if rows.empty:
    st.warning("No customers match these filters.")
    st.stop()

# ---- table ----
def _status_emoji(s: str) -> str:
    return {"live": "🟢", "dormant": "⚫", "no_history": "🟡"}.get(s, "·")


view = pd.DataFrame(
    {
        "": rows["status"].apply(_status_emoji),
        "Customer": rows["name"] + " (" + rows["customer_code"] + ")",
        "Last delivery": rows["last_delivery_date"].astype(str),
        "Days": rows["days_since_last_delivery"].apply(fmt_relative_days),
        "Run": rows["legacy_run_code"].fillna("—"),
        "Day group": rows["delivery_days_group"].fillna("—"),
        "Pricing": rows["pricing_level"].fillna("—"),
        "COD": rows["is_cod"].apply(lambda b: "✓" if b else ""),
        "Avg order": rows["avg_order_value_pence"].apply(
            lambda v: fmt_gbp(v) if pd.notna(v) else "—"
        ),
        "id": rows["id"].astype(str),
    }
)

st.dataframe(view.drop(columns=["id"]), hide_index=True, use_container_width=True)

# ---- per-row drill-in ----
st.divider()
selected = st.selectbox(
    "Open customer detail",
    options=[""] + view["id"].tolist(),
    format_func=lambda i: "—" if i == "" else view[view["id"] == i]["Customer"].iloc[0],
)
if selected:
    st.session_state["customer_id"] = selected
    st.switch_page("pages/06_Customer_Detail.py")
