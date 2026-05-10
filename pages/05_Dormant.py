"""Dormant + no-history review queue."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from grasmere_routes.auth import require_role
from grasmere_routes.format import fmt_gbp_rounded, fmt_relative_days
from grasmere_routes.queries import (
    confirm_live,
    list_dormant,
    mark_inactive,
)

st.set_page_config(
    page_title="Dormant · Grasmere Routes", page_icon="🗂️", layout="wide"
)
user = require_role("admin", "dispatcher")

st.title("Dormant + no-history customers")
st.caption(
    "Excluded from auto-routing and the baseline. Confirm live, mark inactive, or "
    "export for sales follow-up."
)

rows = list_dormant()
dormant_n = int((rows["status"] == "dormant").sum())
nohist_n = int((rows["status"] == "no_history").sum())
upside = int(
    (rows["avg_order_value_pence"].fillna(0) * 52).sum()
)  # naive — sum × 52

k1, k2, k3 = st.columns(3)
k1.metric("Dormant", dormant_n, "Last delivery > 180d", delta_color="off")
k2.metric("No history", nohist_n, "No delivery date recorded", delta_color="off")
k3.metric(
    "Re-engagement upside (estimate)",
    fmt_gbp_rounded(upside),
    "Σ avg order × 52 — order-of-magnitude only",
    delta_color="off",
)

st.divider()

# CSV export button
csv_buf = io.StringIO()
rows.to_csv(csv_buf, index=False)
st.download_button(
    "Download CSV for sales re-engagement",
    csv_buf.getvalue(),
    file_name="grasmere-dormant.csv",
    mime="text/csv",
)

st.divider()

if rows.empty:
    st.success("No dormant or no-history customers — clean list.")
    st.stop()

# ---- per-row actions ----
for _, r in rows.iterrows():
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([3, 2, 1, 1, 1])
        with c1:
            st.markdown(
                f"**{r['name']}** · `{r['customer_code']}` · "
                f"sales rep: {r['sales_rep'] or '—'}"
            )
        with c2:
            st.caption(
                f"{r['status']} · last delivery {r['last_delivery_date']} "
                f"({fmt_relative_days(r['days_since_last_delivery'])})"
            )
        with c3:
            if st.button("Confirm live", key=f"live-{r['id']}"):
                confirm_live(str(r["id"]))
                st.success("Confirmed.")
                st.rerun()
        with c4:
            if st.button("Mark inactive", key=f"inact-{r['id']}"):
                mark_inactive([str(r["id"])])
                st.success("Marked inactive.")
                st.rerun()
        with c5:
            with st.popover("Note"):
                note = st.text_area("Add note", key=f"note-{r['id']}", height=80)
                if st.button("Save note", key=f"savenote-{r['id']}"):
                    if note.strip():
                        from grasmere_routes.queries import add_customer_note

                        add_customer_note(str(r["id"]), note.strip(), user.email)
                        st.success("Saved.")
                        st.rerun()
