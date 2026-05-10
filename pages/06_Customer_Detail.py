"""Per-customer detail — history, profile, profitability."""

from __future__ import annotations

import streamlit as st

from grasmere_routes.auth import require_role
from grasmere_routes.format import fmt_gbp, fmt_relative_days
from grasmere_routes.queries import (
    confirm_live,
    get_customer,
    list_customer_notes,
    mark_inactive,
)

st.set_page_config(
    page_title="Customer · Grasmere Routes", page_icon="👤", layout="wide"
)
require_role("admin", "dispatcher")

cid = st.session_state.get("customer_id")
if not cid:
    st.warning("Pick a customer from the Customers page first.")
    st.page_link("pages/04_Customers.py", label="← Customers")
    st.stop()

c = get_customer(str(cid))
if not c:
    st.error("Customer not found.")
    st.stop()

st.title(c["name"])
st.caption(f"`{c['customer_code']}` · {c['status']}")

k1, k2, k3 = st.columns(3)
k1.metric("Last delivery", str(c["last_delivery_date"] or "never"))
k2.metric(
    "Days since",
    fmt_relative_days(c.get("days_since_last_delivery")),
    delta_color="off",
)
k3.metric(
    "Avg order value",
    fmt_gbp(c["avg_order_value_pence"]) if c["avg_order_value_pence"] else "—",
)

st.divider()

with st.container(border=True):
    st.subheader("Delivery profile")
    grid_l, grid_r = st.columns(2)
    with grid_l:
        st.markdown(f"**Address:** {c.get('delivery_address') or '—'}")
        st.markdown(f"**Day group:** {c.get('delivery_days_group') or '—'}")
        st.markdown(f"**COD:** {'Yes' if c.get('is_cod') else 'No'}")
    with grid_r:
        if c.get("delivery_lat") and c.get("delivery_lng"):
            st.markdown(
                f"**Geocode:** {float(c['delivery_lat']):.5f}, {float(c['delivery_lng']):.5f} "
                f"({c.get('geocode_confidence') or '?'})"
            )
        else:
            st.markdown("**Geocode:** not geocoded yet")
        st.markdown(
            f"**Legacy run code:** `{c.get('legacy_run_code') or '—'}` "
            "*(reference only)*"
        )
        st.markdown(f"**Sales rep:** {c.get('sales_rep') or '—'}")

st.divider()

with st.container(border=True):
    st.subheader("Notes")
    notes = list_customer_notes(str(cid))
    if notes.empty:
        st.caption("No notes yet.")
    for _, n in notes.iterrows():
        st.markdown(f"- _{n['created_at']:%Y-%m-%d}_ · **{n['author_email']}**: {n['note']}")

st.divider()

with st.container(border=True):
    st.subheader("Actions")
    a, b = st.columns(2)
    with a:
        if st.button("Confirm live", use_container_width=True):
            confirm_live(str(cid))
            st.success("Confirmed.")
            st.rerun()
    with b:
        if st.button("Mark inactive", use_container_width=True):
            mark_inactive([str(cid)])
            st.success("Marked inactive.")
            st.rerun()
