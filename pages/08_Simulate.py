"""What-if simulator — drop customers from a day, re-solve, see fleet-cost impact."""

from __future__ import annotations

from datetime import date

import streamlit as st
from sqlalchemy import text

from grasmere_routes.auth import require_role
from grasmere_routes.db import engine
from grasmere_routes.format import fmt_gbp, fmt_pct
from grasmere_routes.plan_service import optimise_plan

st.set_page_config(
    page_title="Simulate · Grasmere Routes", page_icon="🧪", layout="wide"
)
require_role("admin", "dispatcher")

st.title("What-if simulator")
st.caption(
    "Exclude customers from a delivery day and see the fleet-cost impact. The "
    "simulator soft-cancels their orders, re-solves, then restores them."
)

c1, c2 = st.columns([1, 2])
with c1:
    chosen = st.date_input("Delivery date", value=date.today())
with c2:
    excludes = st.text_input(
        "Exclude customer codes (comma-separated)",
        placeholder="ABOTTRIP, 23COFF",
    )

if st.button("Re-solve", type="primary"):
    codes = [c.strip() for c in excludes.split(",") if c.strip()]
    date_str = chosen.isoformat()

    if codes:
        with engine().begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE orders SET status = 'cancelled'
                    WHERE delivery_date = :d
                      AND customer_id IN (SELECT id FROM customers WHERE customer_code = ANY(:codes))
                      AND status IN ('pending','planned')
                    """
                ),
                {"d": date_str, "codes": codes},
            )
    try:
        with st.spinner("Solving…"):
            result = optimise_plan(date_str)
    finally:
        if codes:
            with engine().begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE orders SET status = 'pending'
                        WHERE delivery_date = :d
                          AND customer_id IN (SELECT id FROM customers WHERE customer_code = ANY(:codes))
                          AND status = 'cancelled'
                        """
                    ),
                    {"d": date_str, "codes": codes},
                )

    if result.get("ok") is False:
        st.warning(result.get("reason"))
    else:
        a, b, c = st.columns(3)
        a.metric("Optimised", fmt_gbp(result["optimised_total_pence"]))
        b.metric("Baseline (matched set)", fmt_gbp(result["baseline_total_pence"]))
        c.metric(
            "Saving",
            fmt_gbp(result["saving_pence"]),
            f"{fmt_pct(result['saving_pct'])} vs baseline",
        )
