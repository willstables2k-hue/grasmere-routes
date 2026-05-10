"""All SQL lives here — same convention as grasmere-sales-dashboard.

Functions return DataFrames or plain dicts. None of these queries cache;
calling pages add @st.cache_data with a short TTL where they want it.
"""

from __future__ import annotations

import pandas as pd

from .db import engine, execute, execute_returning, query_df


# ---------- config ----------

def get_config() -> dict:
    df = query_df("SELECT * FROM config WHERE id = 1")
    if df.empty:
        raise RuntimeError("config row missing — run migrations + seed")
    return df.iloc[0].to_dict()


def update_config(values: dict) -> None:
    allowed = {
        "diesel_price_pence_per_litre", "default_mpg",
        "default_driver_hourly_rate_pence", "avg_speed_kmh",
        "service_time_min_per_stop", "depot_loading_time_min",
        "vehicle_fixed_cost_per_day_pence", "driver_max_shift_hours",
        "default_gross_margin_pct", "dormancy_threshold_days",
    }
    cols = [k for k in values if k in allowed]
    if not cols:
        return
    set_sql = ", ".join(f"{k} = :{k}" for k in cols)
    execute(
        f"UPDATE config SET {set_sql}, updated_at = now() WHERE id = 1",
        {k: values[k] for k in cols},
    )


# ---------- depot ----------

def get_depot() -> dict:
    df = query_df("SELECT id, name, address, lat, lng FROM depot ORDER BY name LIMIT 1")
    if df.empty:
        raise RuntimeError("no depot row — run migrations + seed")
    return df.iloc[0].to_dict()


# ---------- vehicles & drivers ----------

def list_vehicles(active_only: bool = True) -> pd.DataFrame:
    if active_only:
        return query_df("SELECT * FROM vehicles WHERE active = TRUE ORDER BY name")
    return query_df("SELECT * FROM vehicles ORDER BY name")


def list_drivers(active_only: bool = True) -> pd.DataFrame:
    if active_only:
        return query_df("SELECT * FROM drivers WHERE active = TRUE ORDER BY name")
    return query_df("SELECT * FROM drivers ORDER BY name")


# ---------- customers ----------

def status_counts() -> dict[str, int]:
    df = query_df(
        """
        SELECT s.status, COUNT(*)::int AS n
        FROM customers c
        JOIN customer_status_v s ON s.customer_id = c.id
        WHERE c.active = TRUE
        GROUP BY s.status
        """
    )
    out = {"live": 0, "dormant": 0, "no_history": 0, "total": 0}
    for _, r in df.iterrows():
        out[r["status"]] = int(r["n"])
        out["total"] += int(r["n"])
    return out


def list_customers(
    *,
    statuses: tuple[str, ...] | None = ("live",),
    search: str | None = None,
    run_code: str | None = None,
    cod: bool | None = None,
    limit: int = 500,
    offset: int = 0,
) -> pd.DataFrame:
    where = ["c.active = TRUE"]
    params: dict = {"limit": limit, "offset": offset}
    if statuses:
        where.append("s.status = ANY(:statuses)")
        params["statuses"] = list(statuses)
    if search:
        where.append("(c.name ILIKE :search OR c.customer_code ILIKE :search)")
        params["search"] = f"%{search}%"
    if run_code:
        where.append("c.legacy_run_code = :run_code")
        params["run_code"] = run_code
    if cod is not None:
        where.append("c.is_cod = :cod")
        params["cod"] = cod
    where_sql = " AND ".join(where)
    return query_df(
        f"""
        SELECT
          c.id, c.customer_code, c.name, s.status,
          s.days_since_last_delivery,
          c.last_delivery_date, c.legacy_run_code, c.preferred_days,
          c.delivery_days_group, c.pricing_level, c.is_cod, c.sales_rep,
          c.delivery_address, c.delivery_lat, c.delivery_lng,
          c.geocode_confidence, c.avg_order_value_pence
        FROM customers c
        JOIN customer_status_v s ON s.customer_id = c.id
        WHERE {where_sql}
        ORDER BY c.name
        LIMIT :limit OFFSET :offset
        """,
        params,
    )


def list_dormant() -> pd.DataFrame:
    return query_df(
        """
        SELECT
          c.id, c.customer_code, c.name, s.status,
          s.days_since_last_delivery, c.last_delivery_date,
          c.legacy_run_code, c.sales_rep, c.avg_order_value_pence
        FROM customers c
        JOIN customer_status_v s ON s.customer_id = c.id
        WHERE c.active = TRUE AND s.status IN ('dormant','no_history')
        ORDER BY s.days_since_last_delivery DESC NULLS LAST, c.name
        """
    )


def get_customer(cid: str) -> dict | None:
    df = query_df(
        """
        SELECT c.*, s.status, s.days_since_last_delivery
        FROM customers c
        JOIN customer_status_v s ON s.customer_id = c.id
        WHERE c.id = :id
        LIMIT 1
        """,
        {"id": cid},
    )
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def confirm_live(cid: str) -> None:
    execute(
        "UPDATE customers SET manually_confirmed_live_at = now(), updated_at = now() WHERE id = :id",
        {"id": cid},
    )


def mark_inactive(ids: list[str]) -> None:
    if not ids:
        return
    execute(
        """
        UPDATE customers
        SET active = FALSE, manually_confirmed_live_at = NULL, updated_at = now()
        WHERE id = ANY(:ids)
        """,
        {"ids": ids},
    )


def add_customer_note(cid: str, note: str, author_email: str) -> None:
    execute(
        """
        INSERT INTO customer_notes (customer_id, note, author_email)
        VALUES (:id, :note, :author)
        """,
        {"id": cid, "note": note, "author": author_email},
    )


def list_customer_notes(cid: str) -> pd.DataFrame:
    return query_df(
        "SELECT note, author_email, created_at FROM customer_notes WHERE customer_id = :id ORDER BY created_at DESC",
        {"id": cid},
    )


# ---------- orders & routes ----------

def orders_for_date(delivery_date: str) -> pd.DataFrame:
    return query_df(
        """
        SELECT o.id AS order_id, c.id AS customer_id, c.name,
               o.weight_kg, o.crate_count, o.order_value_pence, o.status,
               c.delivery_lat AS lat, c.delivery_lng AS lng,
               c.legacy_run_code, c.is_cod
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        WHERE o.delivery_date = :d
          AND o.status IN ('pending','planned')
          AND c.delivery_lat IS NOT NULL AND c.delivery_lng IS NOT NULL
        ORDER BY c.name
        """,
        {"d": delivery_date},
    )


def insert_pending_order(customer_id: str, delivery_date: str) -> None:
    execute(
        """
        INSERT INTO orders (customer_id, delivery_date, status)
        SELECT :cid, :d, 'pending'
        WHERE NOT EXISTS (
          SELECT 1 FROM orders WHERE customer_id = :cid AND delivery_date = :d
            AND status IN ('pending','planned','out')
        )
        """,
        {"cid": customer_id, "d": delivery_date},
    )


def live_customers_for_day(dow_mon0: int) -> pd.DataFrame:
    return query_df(
        """
        SELECT c.id
        FROM customers c
        JOIN customer_status_v s ON s.customer_id = c.id
        WHERE c.active = TRUE AND s.status = 'live'
          AND :dow = ANY(c.preferred_days)
        """,
        {"dow": dow_mon0},
    )


def dormant_count_for_day(dow_mon0: int) -> int:
    df = query_df(
        """
        SELECT COUNT(*)::int AS n
        FROM customers c
        JOIN customer_status_v s ON s.customer_id = c.id
        WHERE c.active = TRUE AND s.status IN ('dormant','no_history')
          AND :dow = ANY(c.preferred_days)
        """,
        {"dow": dow_mon0},
    )
    return int(df.iloc[0]["n"])


def routes_for_date(delivery_date: str) -> pd.DataFrame:
    return query_df(
        """
        SELECT r.*,
               (SELECT COUNT(*)::int FROM route_stops rs WHERE rs.route_id = r.id) AS stop_count
        FROM routes r
        WHERE r.delivery_date = :d
        ORDER BY r.created_at DESC
        """,
        {"d": delivery_date},
    )


def stops_for_route(route_id: str) -> pd.DataFrame:
    return query_df(
        """
        SELECT rs.*, c.name, c.delivery_address, c.delivery_lat, c.delivery_lng,
               c.standing_delivery_instructions, c.standing_picking_instructions,
               c.is_cod, o.cod_amount_pence
        FROM route_stops rs
        JOIN orders o ON o.id = rs.order_id
        JOIN customers c ON c.id = o.customer_id
        WHERE rs.route_id = :rid
        ORDER BY rs.sequence
        """,
        {"rid": route_id},
    )


def todays_published_stops_for_driver(driver_email: str | None) -> pd.DataFrame:
    """Today's published route stops. driver_email currently optional —
    when drivers are assigned we'll filter by routes.driver_id."""
    return query_df(
        """
        SELECT rs.id AS route_stop_id, rs.sequence,
               c.name AS customer_name, c.customer_code,
               c.delivery_address AS address,
               c.delivery_lat AS lat, c.delivery_lng AS lng,
               c.standing_delivery_instructions AS notes,
               c.standing_picking_instructions AS picking_notes,
               c.is_cod, o.cod_amount_pence,
               CASE WHEN c.soft_window_start IS NOT NULL OR c.soft_window_end IS NOT NULL
                 THEN COALESCE(c.soft_window_start::text, '?') || '–' || COALESCE(c.soft_window_end::text, '?')
                 ELSE NULL END AS soft_window,
               o.status
        FROM route_stops rs
        JOIN routes r ON r.id = rs.route_id
        JOIN orders o ON o.id = rs.order_id
        JOIN customers c ON c.id = o.customer_id
        WHERE r.delivery_date = CURRENT_DATE
          AND r.status IN ('published','in_progress','completed')
        ORDER BY rs.sequence
        """,
    )


# ---------- baseline ----------

def get_current_baseline() -> dict | None:
    df = query_df("SELECT * FROM baseline_snapshot WHERE is_current = TRUE LIMIT 1")
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def get_baseline_routes(snapshot_id: str) -> pd.DataFrame:
    return query_df(
        "SELECT * FROM baseline_routes WHERE snapshot_id = :sid ORDER BY day_of_week, van_colour",
        {"sid": snapshot_id},
    )


# ---------- runs / variance ----------

def runs_last_n_days(days: int = 60) -> pd.DataFrame:
    return query_df(
        """
        SELECT r.id, r.delivery_date, r.vehicle_id, r.status,
               r.planned_distance_km, r.actual_distance_km,
               r.planned_duration_min, r.actual_duration_min,
               r.planned_total_cost_pence, r.actual_total_cost_pence,
               (SELECT COUNT(*)::int FROM route_stops rs WHERE rs.route_id = r.id) AS stops
        FROM routes r
        WHERE r.delivery_date >= CURRENT_DATE - (:n || ' days')::interval
        ORDER BY r.delivery_date DESC, r.created_at DESC
        """,
        {"n": days},
    )


# ---------- economics ----------

def bottom_customers_by_net_contribution(limit: int = 20) -> pd.DataFrame:
    return query_df(
        """
        SELECT c.id, c.name, c.customer_code, c.avg_order_value_pence,
               AVG(rs.planned_marginal_cost_pence)::int AS marginal_cost_pence,
               AVG(rs.planned_net_contribution_pence)::int AS net_contribution_pence,
               COUNT(*)::int AS frequency_per_year
        FROM customers c
        JOIN orders o ON o.customer_id = c.id
        JOIN route_stops rs ON rs.order_id = o.id
        WHERE rs.planned_net_contribution_pence IS NOT NULL
        GROUP BY c.id
        ORDER BY net_contribution_pence ASC NULLS LAST
        LIMIT :limit
        """,
        {"limit": limit},
    )


def optimised_cost_last_n_days(n: int = 7) -> int:
    df = query_df(
        """
        SELECT COALESCE(SUM(planned_total_cost_pence), 0)::bigint AS pence
        FROM routes
        WHERE delivery_date >= CURRENT_DATE - (:n || ' days')::interval
        """,
        {"n": n},
    )
    return int(df.iloc[0]["pence"])


# silence unused-import lint — engine and execute_returning kept for future endpoints
_ = engine, execute_returning
