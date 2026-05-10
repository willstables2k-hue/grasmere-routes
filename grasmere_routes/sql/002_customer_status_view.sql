-- Derived customer status — recompute by querying this view, never store as a column.
-- Threshold is read from config.dormancy_threshold_days at view-resolution time.

CREATE OR REPLACE VIEW customer_status_v AS
SELECT
  c.id AS customer_id,
  c.customer_code,
  c.name,
  c.last_delivery_date,
  c.manually_confirmed_live_at,
  CASE
    WHEN c.manually_confirmed_live_at IS NOT NULL
         AND c.manually_confirmed_live_at >= now() - make_interval(days => (SELECT dormancy_threshold_days FROM config WHERE id = 1))
      THEN 'live'
    WHEN c.last_delivery_date IS NOT NULL
         AND c.last_delivery_date >= (CURRENT_DATE - ((SELECT dormancy_threshold_days FROM config WHERE id = 1) || ' days')::interval)::date
      THEN 'live'
    WHEN c.last_delivery_date IS NULL
      THEN 'no_history'
    ELSE 'dormant'
  END AS status,
  CASE
    WHEN c.last_delivery_date IS NULL THEN NULL
    ELSE (CURRENT_DATE - c.last_delivery_date)
  END AS days_since_last_delivery,
  now() AS computed_at
FROM customers c;
