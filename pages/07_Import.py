"""CSV import for the Fresho customer export."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from grasmere_routes.auth import require_role
from grasmere_routes.csv_import import parse_customer_csv
from grasmere_routes.customer_upsert import upsert_customers

st.set_page_config(
    page_title="Import · Grasmere Routes", page_icon="📥", layout="wide"
)
require_role("admin", "dispatcher")

st.title("Import customers")
st.caption(
    "Upserts on `customer_code`. Existing geocode + manual confirmations are preserved. "
    "Geocoding can be triggered from Admin once the import is in."
)

uploaded = st.file_uploader("Fresho customer CSV", type=["csv"])

if uploaded and st.button("Import", type="primary"):
    with st.spinner("Parsing & upserting…"):
        text = uploaded.getvalue().decode("utf-8-sig")
        parsed = parse_customer_csv(text)
        result = upsert_customers(parsed.rows)

    st.success(
        f"Inserted {result['inserted']} · updated {result['updated']} · "
        f"errors {len(parsed.errors) + len(result['errors'])} · "
        f"flagged {sum(1 for r in parsed.rows if r.flagged_for_review)}"
    )

    if parsed.errors or result["errors"]:
        st.subheader("Errors")
        rows = [{"line/code": f"line {ln}", "error": msg} for ln, msg in parsed.errors[:50]] + [
            {"line/code": e["customer_code"], "error": e["error"]} for e in result["errors"][:50]
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    flagged = [r for r in parsed.rows if r.flagged_for_review]
    if flagged:
        st.subheader("Flagged for review")
        st.dataframe(
            pd.DataFrame(
                [
                    {"customer_code": r.customer_code, "name": r.name, "reasons": " · ".join(r.flag_reasons)}
                    for r in flagged[:100]
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
