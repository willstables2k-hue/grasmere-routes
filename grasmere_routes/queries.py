"""All SQL lives here.

The two pages need a small surface:
  - get_config / update_config            — cost parameters
  - get_depot                             — depot lat/lng
  - list_vehicles                         — for the optimiser fleet
  - dates_with_data                       — date picker options
  - deliveries_for_date                   — Map + Costs source rows
"""

from __future__ import annotations

import pandas as pd

from .db import engine, execute, query_df


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
        "default_gross_margin_pct",
    }
    cols = [k for k in values if k in allowed]
    if not cols:
        return
    set_sql = ", ".join(f"{k} = :{k}" for k in cols)
    execute(
        f"UPDATE config SET {set_sql}, updated_at = now() WHERE id = 1",
        {k: values[k] for k in cols},
    )


# ---------- depot + vehicles ----------

def get_depot() -> dict:
    df = query_df("SELECT id, name, address, lat, lng FROM depot ORDER BY name LIMIT 1")
    if df.empty:
        raise RuntimeError("no depot row — run migrations + seed")
    return df.iloc[0].to_dict()


def list_vehicles(active_only: bool = True) -> pd.DataFrame:
    if active_only:
        return query_df("SELECT * FROM vehicles WHERE active = TRUE ORDER BY name")
    return query_df("SELECT * FROM vehicles ORDER BY name")


# ---------- the day-centric queries the two pages care about ----------

def dates_with_data() -> list:
    """Distinct delivery dates that have at least one geocoded order, newest
    first. Powers the date picker."""
    df = query_df(
        """
        SELECT DISTINCT o.delivery_date
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        WHERE c.delivery_lat IS NOT NULL AND c.delivery_lng IS NOT NULL
        ORDER BY o.delivery_date DESC
        """
    )
    return df["delivery_date"].tolist()


def deliveries_for_date(delivery_date: str) -> pd.DataFrame:
    """Every importable delivery for a given date with everything the Map
    and Costs pages need. The run code returned is the per-order override
    from the Fresho file, falling back to the customer's static code."""
    return query_df(
        """
        SELECT
          o.id::text                AS order_id,
          c.id::text                AS customer_id,
          c.customer_code,
          c.name,
          o.order_number,
          o.order_value_pence,
          c.delivery_lat            AS lat,
          c.delivery_lng            AS lng,
          COALESCE(o.legacy_run_code_override, c.legacy_run_code) AS legacy_run_code,
          c.geocode_confidence
        FROM orders o
        JOIN customers c ON c.id = o.customer_id
        WHERE o.delivery_date = :d
          AND c.delivery_lat IS NOT NULL
          AND c.delivery_lng IS NOT NULL
        ORDER BY c.name
        """,
        {"d": delivery_date},
    )


# silence unused-import lint
_ = engine
