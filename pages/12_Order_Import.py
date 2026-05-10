"""Import orders from a Fresho `delivery_runs` Excel export.

This is the production path for getting real orders into the planner — pull
the file from Fresho (Data → Sales → Delivery Runs → CSV/XLSX) and upload it
here. The planner then has actual £ values, real box counts, and the
run-code-on-the-day for each order — which the matched-baseline calculation
uses instead of the customer's static legacy code.
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from grasmere_routes.auth import require_role
from grasmere_routes.format import fmt_gbp
from grasmere_routes.orders_import import import_orders, parse_orders_excel

st.set_page_config(
    page_title="Order import · Grasmere Routes", page_icon="📦", layout="wide"
)
require_role("admin", "dispatcher")

st.title("Import orders from Fresho")
st.caption(
    "Upload a `delivery_runs` Excel export. Customers not yet in the database are "
    "created automatically. Re-importing the same file is safe — orders are "
    "deduped on `Order Number`."
)

if not os.environ.get("MAPBOX_TOKEN"):
    st.info(
        "🛈 No `MAPBOX_TOKEN` set — new customers will be geocoded to their "
        "**postcode centroid** via postcodes.io (free). Routes will be roughly "
        "right but not pixel-perfect. Set `MAPBOX_TOKEN` in secrets for "
        "production-grade geocodes."
    )

uploaded = st.file_uploader(
    "Fresho delivery-runs file", type=["xlsx", "xls"], accept_multiple_files=False
)

if uploaded:
    try:
        rows, parse_errors = parse_orders_excel(uploaded.getvalue())
    except Exception as e:  # noqa: BLE001
        st.error(f"Couldn't read the file: {e}")
        st.stop()

    # ---- preview ----
    if rows:
        days = sorted({r.delivery_date for r in rows})
        codes = sorted({r.delivery_run_code or "" for r in rows})
        st.success(
            f"Parsed **{len(rows)}** orders across "
            f"**{len({r.customer_code for r in rows})}** customers · "
            f"day(s): {', '.join(d.strftime('%a %d %b %Y') for d in days)} · "
            f"run codes: {', '.join(c for c in codes if c)}"
        )
        preview = pd.DataFrame(
            [
                {
                    "Run": r.delivery_run_code or "—",
                    "Date": r.delivery_date,
                    "Customer": f"{r.customer_name} ({r.customer_code})",
                    "Boxes": r.boxes,
                    "Order #": r.order_number,
                    "Value": fmt_gbp(r.order_value_pence) if r.order_value_pence else "—",
                    "Address": r.delivery_address,
                }
                for r in rows[:25]
            ]
        )
        st.dataframe(preview, hide_index=True, use_container_width=True)
        if len(rows) > 25:
            st.caption(f"…and {len(rows) - 25} more rows.")

        total_value = sum((r.order_value_pence or 0) for r in rows)
        c1, c2, c3 = st.columns(3)
        c1.metric("Total order value", fmt_gbp(total_value))
        c2.metric("Mail orders (~NR)", sum(1 for r in rows if r.delivery_run_code == "~NR"))
        c3.metric("Excludes from VRP", sum(1 for r in rows if r.delivery_run_code == "~NR"))
    if parse_errors:
        with st.expander(f"Parse errors ({len(parse_errors)})", expanded=False):
            st.dataframe(pd.DataFrame(parse_errors), hide_index=True)

    if rows and st.button("Import to database", type="primary"):
        with st.spinner("Upserting customers and inserting orders…"):
            summary = import_orders(rows)
        st.success(
            f"Imported · {summary.orders_inserted} new orders · "
            f"{summary.orders_updated} updated · "
            f"{summary.customers_created} new customers "
            f"({summary.customers_geocoded} geocoded, "
            f"{summary.customers_missing_geocode} missing geocode)"
        )
        if summary.errors:
            with st.expander(f"Errors ({len(summary.errors)})", expanded=False):
                st.dataframe(pd.DataFrame(summary.errors), hide_index=True)
        st.divider()
        st.caption("Next step:")
        st.page_link(
            "pages/01_Plan.py",
            label=f"Open the planner for {rows[0].delivery_date} →",
            icon="📅",
        )
