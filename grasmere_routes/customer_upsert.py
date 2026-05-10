"""Bulk upsert of parsed customer rows.

Upsert key: customer_code. Never overwrites geocode columns or
manually_confirmed_live_at on re-import — those are platform state.
last_delivery_date only ever moves forwards.
"""

from __future__ import annotations

import json

from .csv_import import ImportRow
from .db import engine
from sqlalchemy import text


UPSERT_SQL = """
INSERT INTO customers (
  customer_code, name, legal_entity_name, delivery_address, billing_address,
  pricing_level, is_cod, payment_term_days, sales_rep,
  delivery_days_group, preferred_days,
  legacy_run_code, legacy_run_position,
  standing_picking_instructions, standing_delivery_instructions,
  soft_window_start, soft_window_end,
  last_delivery_date, active, raw_csv_row, updated_at
) VALUES (
  :customer_code, :name, :legal_entity_name, :delivery_address, :billing_address,
  :pricing_level, :is_cod, :payment_term_days, :sales_rep,
  :delivery_days_group, :preferred_days,
  :legacy_run_code, :legacy_run_position,
  :standing_picking_instructions, :standing_delivery_instructions,
  :soft_window_start, :soft_window_end,
  :last_delivery_date, :active, CAST(:raw_csv_row AS jsonb), now()
)
ON CONFLICT (customer_code) DO UPDATE SET
  name                            = EXCLUDED.name,
  legal_entity_name               = EXCLUDED.legal_entity_name,
  delivery_address                = EXCLUDED.delivery_address,
  billing_address                 = EXCLUDED.billing_address,
  pricing_level                   = EXCLUDED.pricing_level,
  is_cod                          = EXCLUDED.is_cod,
  payment_term_days               = EXCLUDED.payment_term_days,
  sales_rep                       = EXCLUDED.sales_rep,
  delivery_days_group             = EXCLUDED.delivery_days_group,
  preferred_days                  = EXCLUDED.preferred_days,
  legacy_run_code                 = EXCLUDED.legacy_run_code,
  legacy_run_position             = EXCLUDED.legacy_run_position,
  standing_picking_instructions   = EXCLUDED.standing_picking_instructions,
  standing_delivery_instructions  = EXCLUDED.standing_delivery_instructions,
  soft_window_start               = EXCLUDED.soft_window_start,
  soft_window_end                 = EXCLUDED.soft_window_end,
  -- never go backwards on last_delivery_date
  last_delivery_date              = GREATEST(customers.last_delivery_date, EXCLUDED.last_delivery_date),
  active                          = EXCLUDED.active,
  raw_csv_row                     = EXCLUDED.raw_csv_row,
  updated_at                      = now()
RETURNING (xmax = 0) AS inserted
"""


def upsert_customers(rows: list[ImportRow]) -> dict:
    inserted = 0
    updated = 0
    errors: list[dict] = []
    with engine().begin() as conn:
        for r in rows:
            try:
                params = {
                    "customer_code": r.customer_code,
                    "name": r.name,
                    "legal_entity_name": r.legal_entity_name,
                    "delivery_address": r.delivery_address,
                    "billing_address": r.billing_address,
                    "pricing_level": r.pricing_level,
                    "is_cod": r.is_cod,
                    "payment_term_days": r.payment_term_days,
                    "sales_rep": r.sales_rep,
                    "delivery_days_group": r.delivery_days_group,
                    "preferred_days": r.preferred_days,
                    "legacy_run_code": r.legacy_run_code,
                    "legacy_run_position": r.legacy_run_position,
                    "standing_picking_instructions": r.standing_picking_instructions,
                    "standing_delivery_instructions": r.standing_delivery_instructions,
                    "soft_window_start": r.soft_window_start,
                    "soft_window_end": r.soft_window_end,
                    "last_delivery_date": r.last_delivery_date,
                    "active": r.active,
                    "raw_csv_row": json.dumps(r.raw_csv_row),
                }
                row = conn.execute(text(UPSERT_SQL), params).first()
                if row and row[0]:
                    inserted += 1
                else:
                    updated += 1
            except Exception as e:  # noqa: BLE001
                errors.append({"customer_code": r.customer_code, "error": str(e)})
    return {"inserted": inserted, "updated": updated, "errors": errors}
