"""Fresho auto-pull — instructions + Fresho deep-link.

Streamlit Community Cloud can't reliably host headless browsers, so the
actual pull runs locally on William's machine via `scripts/fresho_pull.py`
(same machine as the KPI dashboard pipeline). This page tells you what to
run and gives you a one-click jump to Fresho for manual export.
"""

from __future__ import annotations

from datetime import date as DateT

import streamlit as st

from grasmere_routes.auth import require_user

st.set_page_config(
    page_title="Fresho · Grasmere Routes",
    page_icon="📦",
    layout="centered",
)
require_user()

st.title("Pull from Fresho")

active = st.session_state.get("active_date") or DateT.today()
if not isinstance(active, DateT):
    active = active.date() if hasattr(active, "date") else DateT.today()
chosen = st.date_input("Delivery date", value=active)
if chosen != st.session_state.get("active_date"):
    st.session_state["active_date"] = chosen

st.divider()

st.subheader("Automated pull (recommended)")
st.markdown(
    f"""
Run this on the same machine as the KPI dashboard pipeline (Fresho login
needs Playwright + Chrome, which the Streamlit Cloud container can't host).

```powershell
# inside the grasmere-routes repo, with .venv activated and
# FRESHO_EMAIL / FRESHO_PASSWORD / BRAIN_DB_URL in your env
python scripts/fresho_pull.py --date {chosen.isoformat()}
```

Once it finishes, refresh the **Map** page — the day's deliveries will be
populated.

For a daily auto-pull, schedule it via Windows Task Scheduler at, say, 06:00
each weekday. The script is idempotent (orders dedupe on Fresho `Order Number`)
so re-running the same day is safe.

If you don't yet know the Fresho URL for the delivery_runs export, run once
with `--explore` first — it opens Fresho in a visible Chrome window, lists
every candidate link, and saves a screenshot so we can lock in the right URL:

```powershell
python scripts/fresho_pull.py --explore
```
"""
)

st.divider()

st.subheader("Manual fallback")
st.markdown(
    "Open Fresho in a new tab, navigate to the delivery_runs export for the chosen "
    "date, download the .xlsx, and drop it on the **Map** page uploader."
)
st.link_button(
    "Open Fresho",
    "https://app.fresho.com",
    use_container_width=False,
)
