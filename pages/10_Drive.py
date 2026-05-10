"""Driver mobile view — today's stops, navigate handoff, POD capture."""

from __future__ import annotations

from datetime import datetime

import streamlit as st
from sqlalchemy import text

from grasmere_routes.auth import require_user
from grasmere_routes.db import engine
from grasmere_routes.queries import todays_published_stops_for_driver

st.set_page_config(
    page_title="Drive · Grasmere Routes",
    page_icon="🚚",
    layout="centered",
)
user = require_user()

st.title("Today's route")
stops = todays_published_stops_for_driver(user.email)
st.caption(f"{datetime.now():%a %d %b %Y} · {len(stops)} stops")

if stops.empty:
    st.info("No published route for today.")
    st.stop()

for i, s in enumerate(stops.itertuples(), start=1):
    delivered = s.status == "delivered"
    with st.container(border=True):
        head_l, head_r = st.columns([2, 1])
        with head_l:
            st.markdown(f"**Stop {i}: {s.customer_name}**")
            st.caption(s.customer_code)
        with head_r:
            if s.is_cod:
                cod_amount = (
                    f" £{s.cod_amount_pence/100:.2f}" if s.cod_amount_pence else ""
                )
                st.markdown(f"<span style='color:#dc2626;font-weight:bold'>COD{cod_amount}</span>", unsafe_allow_html=True)
            if s.soft_window:
                st.markdown(f"_{s.soft_window}_")

        st.markdown(s.address or "—")
        if s.notes:
            st.warning(f"**Notes:** {s.notes}")
        if s.picking_notes:
            st.caption(f"**Picking:** {s.picking_notes}")

        nav_url = f"https://www.google.com/maps/dir/?api=1&destination={s.lat},{s.lng}"
        col_n, col_d = st.columns(2)
        with col_n:
            st.link_button("🧭 Navigate", nav_url, use_container_width=True)
        with col_d:
            if not delivered:
                with st.popover("📷 Deliver", use_container_width=True):
                    photo = st.camera_input("POD photo", key=f"cam-{s.route_stop_id}")
                    pod_notes = st.text_area("Notes (optional)", key=f"podnote-{s.route_stop_id}")
                    cod_collected = (
                        st.number_input("COD collected (£)", min_value=0.0, value=0.0, step=0.5, key=f"cod-{s.route_stop_id}")
                        if s.is_cod
                        else None
                    )
                    if st.button("Mark delivered", key=f"deliver-{s.route_stop_id}", type="primary"):
                        with engine().begin() as conn:
                            conn.execute(
                                text(
                                    """
                                    UPDATE route_stops
                                    SET completed_at = now(),
                                        actual_arrival = now(),
                                        actual_departure = now(),
                                        pod_notes = :notes,
                                        cod_collected_pence = :cod
                                    WHERE id = :id
                                    """
                                ),
                                {
                                    "id": str(s.route_stop_id),
                                    "notes": pod_notes or None,
                                    "cod": int(cod_collected * 100) if cod_collected else None,
                                },
                            )
                            conn.execute(
                                text(
                                    """
                                    UPDATE orders SET status = 'delivered'
                                    WHERE id = (SELECT order_id FROM route_stops WHERE id = :id)
                                    """
                                ),
                                {"id": str(s.route_stop_id)},
                            )
                        st.success("Delivered.")
                        st.rerun()
                    # NOTE: photo upload to R2 is the next iteration — for now we
                    # store the binary length only, since Streamlit Community Cloud
                    # disk is ephemeral.
                    if photo:
                        st.caption(f"Photo captured ({len(photo.getvalue())} bytes — R2 upload pending)")
            else:
                st.success("✓ Delivered")
