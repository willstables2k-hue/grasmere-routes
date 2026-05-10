"""Importer for the Fresho `delivery_runs` Excel export.

Format (columns observed in the supplied 2026-04-30 file):
    Delivery Run Code, Delivery Date, Customer Name, Customer Code,
    Number of Boxes, Order Number, Order Value, Order Currency,
    Delivery Address, Delivery Instructions, Additional Notes

Each row is one order. We:
  1. Parse the file into typed OrderRow dataclasses.
  2. For each row, ensure the customer exists (lazy upsert from name + code +
     address). If the customer is brand-new, geocode immediately — Mapbox if
     MAPBOX_TOKEN is set, otherwise postcodes.io centroid as a fallback.
  3. Insert orders with the per-row order_value_pence, crate_count (boxes),
     and run-code-on-the-day. The customer's static legacy_run_code is left
     untouched — the per-order override on `orders` is what the planner uses.

The planner's matched-baseline calculation reads
`orders.legacy_run_code_override` first, falling back to the customer's
static code if absent. That makes the saving figure honest for the actual
day, not a synthetic profile.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable

import pandas as pd
from sqlalchemy import text

from .db import engine, query_df
from .geocode import geocode_address
from .postcodes import extract_postcode, geocode_postcodes_bulk

# ---------- types ----------


@dataclass
class OrderRow:
    delivery_run_code: str | None
    delivery_date: date
    customer_name: str
    customer_code: str
    boxes: int | None
    order_number: str
    order_value_pence: int | None
    delivery_address: str | None
    delivery_instructions: str | None
    additional_notes: str | None


@dataclass
class ImportSummary:
    rows_parsed: int
    orders_inserted: int
    orders_updated: int
    customers_created: int
    customers_geocoded: int
    customers_missing_geocode: int
    errors: list[dict] = field(default_factory=list)


# ---------- column mapping (exact headers from the supplied file) ----------

COL_RUN = "Delivery Run Code"
COL_DATE = "Delivery Date"
COL_NAME = "Customer Name"
COL_CODE = "Customer Code"
COL_BOXES = "Number of Boxes"
COL_ORDER_NO = "Order Number"
COL_VALUE = "Order Value"
COL_ADDRESS = "Delivery Address"
COL_DELIV_INSTR = "Delivery Instructions"
COL_ADD_NOTES = "Additional Notes"


def _to_pence(v) -> int | None:
    if v is None or pd.isna(v):
        return None
    try:
        return int(round(float(v) * 100))
    except (TypeError, ValueError):
        return None


def _coerce_str(v) -> str | None:
    if v is None or pd.isna(v):
        return None
    if isinstance(v, str):
        s = v.strip()
        return s or None
    return str(v)


def _coerce_int(v) -> int | None:
    if v is None or pd.isna(v):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _coerce_date(v) -> date | None:
    if v is None or pd.isna(v):
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return pd.to_datetime(v).date()
    except Exception:  # noqa: BLE001
        return None


def parse_orders_excel(payload: bytes | str) -> tuple[list[OrderRow], list[dict]]:
    """Parse the Fresho delivery-runs xlsx. Returns (rows, errors)."""
    if isinstance(payload, (bytes, bytearray)):
        df = pd.read_excel(io.BytesIO(payload))
    else:
        df = pd.read_excel(payload)

    rows: list[OrderRow] = []
    errors: list[dict] = []
    for i, rec in df.iterrows():
        line = int(i) + 2  # +2 = header + 1-based
        code = _coerce_str(rec.get(COL_CODE))
        name = _coerce_str(rec.get(COL_NAME))
        d = _coerce_date(rec.get(COL_DATE))
        if not code or not name or not d:
            errors.append({"line": line, "error": "missing customer_code, name, or delivery_date"})
            continue
        order_no = _coerce_str(rec.get(COL_ORDER_NO))
        if not order_no:
            errors.append({"line": line, "error": f"{code}: missing order_number"})
            continue
        rows.append(
            OrderRow(
                delivery_run_code=_coerce_str(rec.get(COL_RUN)),
                delivery_date=d,
                customer_name=name,
                customer_code=code,
                boxes=_coerce_int(rec.get(COL_BOXES)),
                order_number=order_no,
                order_value_pence=_to_pence(rec.get(COL_VALUE)),
                delivery_address=_coerce_str(rec.get(COL_ADDRESS)),
                delivery_instructions=_coerce_str(rec.get(COL_DELIV_INSTR)),
                additional_notes=_coerce_str(rec.get(COL_ADD_NOTES)),
            )
        )
    return rows, errors


# ---------- DB-backed import ----------


def _existing_customers(codes: list[str]) -> dict[str, dict]:
    if not codes:
        return {}
    df = query_df(
        """
        SELECT id::text AS id, customer_code, name,
               delivery_lat, delivery_lng, geocode_confidence
        FROM customers WHERE customer_code = ANY(:codes)
        """,
        {"codes": codes},
    )
    return {r["customer_code"]: r.to_dict() for _, r in df.iterrows()}


def _geocode_one(address: str | None) -> tuple[float | None, float | None, str | None]:
    """Try Mapbox first if the token is set, else postcodes.io centroid."""
    if not address:
        return None, None, None
    if os.environ.get("MAPBOX_TOKEN"):
        res = geocode_address(address)
        if res.lat is not None and res.lng is not None:
            return res.lat, res.lng, res.confidence
    pc = extract_postcode(address)
    if not pc:
        return None, None, None
    pts = geocode_postcodes_bulk([pc])
    p = pts.get(pc.upper())
    if not p:
        return None, None, None
    return p.lat, p.lng, "postcode"


def import_orders(rows: Iterable[OrderRow]) -> ImportSummary:
    """Idempotent — re-importing the same file is a no-op (uniqueness on
    order_number)."""
    rows = list(rows)
    summary = ImportSummary(
        rows_parsed=len(rows),
        orders_inserted=0,
        orders_updated=0,
        customers_created=0,
        customers_geocoded=0,
        customers_missing_geocode=0,
    )
    if not rows:
        return summary

    # ---- pre-fetch existing customers, batch-geocode any new postcodes ----
    distinct_codes = sorted({r.customer_code for r in rows})
    existing = _existing_customers(distinct_codes)
    new_codes = [c for c in distinct_codes if c not in existing]

    # Bulk-geocode postcodes for new customers (single HTTP roundtrip)
    new_addresses_by_code: dict[str, str | None] = {}
    for r in rows:
        if r.customer_code in new_codes and r.customer_code not in new_addresses_by_code:
            new_addresses_by_code[r.customer_code] = r.delivery_address
    postcodes = list({extract_postcode(a) for a in new_addresses_by_code.values() if a})
    postcodes = [p for p in postcodes if p]
    bulk_pts = geocode_postcodes_bulk(postcodes) if not os.environ.get("MAPBOX_TOKEN") else {}

    with engine().begin() as conn:
        # ---- ensure customers ----
        for code in new_codes:
            row_for_code = next(r for r in rows if r.customer_code == code)
            address = row_for_code.delivery_address
            lat = lng = None
            confidence = None
            if os.environ.get("MAPBOX_TOKEN"):
                lat, lng, confidence = _geocode_one(address)
            else:
                pc = extract_postcode(address) if address else None
                p = bulk_pts.get(pc) if pc else None
                if p:
                    lat, lng, confidence = p.lat, p.lng, "postcode"
            try:
                conn.execute(
                    text(
                        """
                        INSERT INTO customers (
                          customer_code, name, delivery_address,
                          delivery_lat, delivery_lng, geocode_confidence,
                          geocoded_at, legacy_run_code, active, updated_at
                        ) VALUES (
                          :code, :name, :addr,
                          :lat, :lng, :conf,
                          CASE WHEN :lat IS NULL THEN NULL ELSE now() END,
                          :run, TRUE, now()
                        )
                        ON CONFLICT (customer_code) DO NOTHING
                        """
                    ),
                    {
                        "code": code,
                        "name": row_for_code.customer_name,
                        "addr": address,
                        "lat": lat,
                        "lng": lng,
                        "conf": confidence,
                        "run": row_for_code.delivery_run_code,
                    },
                )
                summary.customers_created += 1
                if lat is not None:
                    summary.customers_geocoded += 1
                else:
                    summary.customers_missing_geocode += 1
            except Exception as e:  # noqa: BLE001
                summary.errors.append(
                    {"customer_code": code, "error": f"customer ensure failed: {e}"}
                )

        # ---- insert / update orders by order_number ----
        for r in rows:
            try:
                result = conn.execute(
                    text(
                        """
                        INSERT INTO orders (
                          customer_id, delivery_date, weight_kg, crate_count,
                          order_value_pence, status, order_number,
                          legacy_run_code_override, delivery_address_override
                        )
                        SELECT c.id, :d, NULL, :boxes,
                               :value, 'pending', :order_no,
                               :run_override, :addr_override
                        FROM customers c WHERE c.customer_code = :code
                        ON CONFLICT (order_number) DO UPDATE SET
                          delivery_date = EXCLUDED.delivery_date,
                          crate_count = EXCLUDED.crate_count,
                          order_value_pence = EXCLUDED.order_value_pence,
                          legacy_run_code_override = EXCLUDED.legacy_run_code_override,
                          delivery_address_override = EXCLUDED.delivery_address_override
                        RETURNING (xmax = 0) AS inserted
                        """
                    ),
                    {
                        "code": r.customer_code,
                        "d": r.delivery_date,
                        "boxes": r.boxes,
                        "value": r.order_value_pence,
                        "order_no": r.order_number,
                        "run_override": r.delivery_run_code,
                        "addr_override": r.delivery_address,
                    },
                ).first()
                if result is None:
                    summary.errors.append(
                        {
                            "customer_code": r.customer_code,
                            "error": f"order {r.order_number}: customer not found in DB",
                        }
                    )
                elif result[0]:
                    summary.orders_inserted += 1
                else:
                    summary.orders_updated += 1
            except Exception as e:  # noqa: BLE001
                summary.errors.append(
                    {"customer_code": r.customer_code, "error": f"{r.order_number}: {e}"}
                )

    return summary
