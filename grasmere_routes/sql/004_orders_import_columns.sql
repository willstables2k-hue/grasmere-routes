-- Migration 004: support importing orders from a Fresho delivery-runs export.
-- Idempotent.

ALTER TABLE orders
  ADD COLUMN IF NOT EXISTS order_number              text,
  ADD COLUMN IF NOT EXISTS legacy_run_code_override  text,
  ADD COLUMN IF NOT EXISTS delivery_address_override text;

-- order_number: the Fresho order ID from the export. Unique per real order;
-- we use it to dedupe when re-importing the same file.
CREATE UNIQUE INDEX IF NOT EXISTS orders_order_number_uidx
  ON orders (order_number)
  WHERE order_number IS NOT NULL;
