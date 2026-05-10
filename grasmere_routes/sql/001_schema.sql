-- Grasmere Routes — initial schema
-- Idempotent: safe to re-run.
--
-- All monetary values stored as integer PENCE.
-- Customer status (live/dormant/no_history) is NOT a column — derived
-- by `customer_status_v` view at read time.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------- config (single row) ----------
CREATE TABLE IF NOT EXISTS config (
  id                                    smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  diesel_price_pence_per_litre          int NOT NULL DEFAULT 188,
  default_mpg                           numeric(5,2) NOT NULL DEFAULT 25.00,
  default_driver_hourly_rate_pence      int NOT NULL DEFAULT 1600,
  avg_speed_kmh                         numeric(5,2) NOT NULL DEFAULT 50.00,
  service_time_min_per_stop             int NOT NULL DEFAULT 8,
  depot_loading_time_min                int NOT NULL DEFAULT 30,
  vehicle_fixed_cost_per_day_pence      int NOT NULL DEFAULT 2500,
  driver_max_shift_hours                numeric(4,2) NOT NULL DEFAULT 8.00,
  default_gross_margin_pct              numeric(4,3) NOT NULL DEFAULT 0.280,
  dormancy_threshold_days               int NOT NULL DEFAULT 180,
  working_delivery_days                 int[] NOT NULL DEFAULT ARRAY[1,3,4]::int[],
  updated_at                            timestamptz NOT NULL DEFAULT now()
);

-- ---------- depot ----------
CREATE TABLE IF NOT EXISTS depot (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text NOT NULL,
  address         text NOT NULL,
  lat             double precision NOT NULL,
  lng             double precision NOT NULL,
  opening_time    time NOT NULL DEFAULT '06:00',
  closing_time    time NOT NULL DEFAULT '18:00'
);

-- ---------- customers ----------
CREATE TABLE IF NOT EXISTS customers (
  id                                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_code                     text NOT NULL UNIQUE,
  name                              text NOT NULL,
  legal_entity_name                 text,
  delivery_address                  text,
  delivery_lat                      double precision,
  delivery_lng                      double precision,
  geocode_confidence                text,
  geocoded_at                       timestamptz,
  billing_address                   text,
  pricing_level                     text,
  gross_margin_pct                  numeric(4,3),
  payment_term_days                 int,
  is_cod                            boolean NOT NULL DEFAULT false,
  delivery_days_group               text,
  preferred_days                    int[],
  legacy_run_code                   text,
  legacy_run_position               int,
  standing_picking_instructions     text,
  standing_delivery_instructions    text,
  soft_window_start                 time,
  soft_window_end                   time,
  avg_order_value_pence             int,
  last_delivery_date                date,
  manually_confirmed_live_at        timestamptz,
  active                            boolean NOT NULL DEFAULT true,
  sales_rep                         text,
  tags                              text[],
  raw_csv_row                       jsonb,
  created_at                        timestamptz NOT NULL DEFAULT now(),
  updated_at                        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS customers_geocode_idx        ON customers (delivery_lat, delivery_lng);
CREATE INDEX IF NOT EXISTS customers_last_delivery_idx  ON customers (last_delivery_date);
CREATE INDEX IF NOT EXISTS customers_active_idx         ON customers (active);

-- ---------- vehicles ----------
CREATE TABLE IF NOT EXISTS vehicles (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  registration             text,
  name                     text NOT NULL,
  mpg                      numeric(5,2),
  capacity_kg              numeric(8,2) NOT NULL DEFAULT 1200,
  capacity_crates          int NOT NULL DEFAULT 80,
  refrigerated             boolean NOT NULL DEFAULT true,
  fixed_cost_per_day_pence int,
  active                   boolean NOT NULL DEFAULT true
);

-- ---------- drivers ----------
CREATE TABLE IF NOT EXISTS drivers (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email               text UNIQUE,
  name                text NOT NULL,
  phone               text,
  hourly_rate_pence   int,
  active              boolean NOT NULL DEFAULT true
);

-- ---------- orders ----------
CREATE TABLE IF NOT EXISTS orders (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id       uuid NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
  delivery_date     date NOT NULL,
  weight_kg         numeric(8,2),
  crate_count       int,
  order_value_pence int,
  cod_amount_pence  int,
  notes             text,
  status            text NOT NULL DEFAULT 'pending',
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS orders_customer_date_idx ON orders (customer_id, delivery_date);
CREATE INDEX IF NOT EXISTS orders_date_status_idx   ON orders (delivery_date, status);

-- ---------- routes ----------
CREATE TABLE IF NOT EXISTS routes (
  id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  delivery_date               date NOT NULL,
  driver_id                   uuid REFERENCES drivers(id),
  vehicle_id                  uuid REFERENCES vehicles(id),
  status                      text NOT NULL DEFAULT 'draft',
  planned_distance_km         numeric(8,2),
  planned_duration_min        int,
  planned_fuel_cost_pence     int,
  planned_labour_cost_pence   int,
  planned_overhead_pence      int,
  planned_total_cost_pence    int,
  actual_distance_km          numeric(8,2),
  actual_duration_min         int,
  actual_fuel_cost_pence      int,
  actual_labour_cost_pence    int,
  actual_total_cost_pence     int,
  optimiser_version           text,
  optimiser_seed              text DEFAULT 'from_scratch',
  created_at                  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS routes_date_idx ON routes (delivery_date);

-- ---------- route_stops ----------
CREATE TABLE IF NOT EXISTS route_stops (
  id                                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  route_id                          uuid NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
  order_id                          uuid NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
  sequence                          int NOT NULL,
  planned_arrival                   timestamptz,
  planned_departure                 timestamptz,
  planned_km_to_stop                numeric(8,3),
  planned_min_to_stop               int,
  planned_fuel_share_pence          int,
  planned_labour_share_pence        int,
  planned_overhead_share_pence      int,
  planned_direct_cost_pence         int,
  planned_marginal_cost_pence       int,
  planned_gross_profit_pence        int,
  planned_net_contribution_pence    int,
  actual_arrival                    timestamptz,
  actual_departure                  timestamptz,
  pod_photo_url                     text,
  pod_signature_url                 text,
  pod_notes                         text,
  cod_collected_pence               int,
  completed_at                      timestamptz,
  failure_reason                    text,
  UNIQUE (route_id, sequence)
);

-- ---------- baseline snapshots ----------
CREATE TABLE IF NOT EXISTS baseline_snapshot (
  id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  computed_at                 timestamptz NOT NULL DEFAULT now(),
  config_hash                 text NOT NULL,
  customer_count_included     int NOT NULL,
  customer_count_excluded     int NOT NULL,
  total_distance_km           numeric(10,2) NOT NULL,
  total_fuel_cost_pence       int NOT NULL,
  total_labour_cost_pence     int NOT NULL,
  total_overhead_pence        int NOT NULL,
  total_cost_pence            int NOT NULL,
  total_stops                 int NOT NULL,
  weekly_cost_pence           int NOT NULL,
  annualised_cost_pence       int NOT NULL,
  is_current                  boolean NOT NULL DEFAULT false,
  notes                       text
);

CREATE TABLE IF NOT EXISTS baseline_routes (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  snapshot_id         uuid NOT NULL REFERENCES baseline_snapshot(id) ON DELETE CASCADE,
  van_colour          text NOT NULL,
  day_of_week         int NOT NULL,
  stop_count          int NOT NULL,
  distance_km         numeric(8,2) NOT NULL,
  duration_min        int NOT NULL,
  fuel_cost_pence     int NOT NULL,
  labour_cost_pence   int NOT NULL,
  overhead_pence      int NOT NULL,
  total_cost_pence    int NOT NULL,
  cost_per_stop_pence int NOT NULL
);
CREATE INDEX IF NOT EXISTS baseline_routes_snapshot_idx ON baseline_routes (snapshot_id);

CREATE TABLE IF NOT EXISTS baseline_route_stops (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  baseline_route_id     uuid NOT NULL REFERENCES baseline_routes(id) ON DELETE CASCADE,
  customer_id           uuid NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
  sequence              int NOT NULL,
  km_to_stop            numeric(8,3) NOT NULL,
  min_to_stop           int NOT NULL,
  fuel_share_pence      int NOT NULL,
  labour_share_pence    int NOT NULL,
  overhead_share_pence  int NOT NULL,
  direct_cost_pence     int NOT NULL,
  UNIQUE (baseline_route_id, sequence)
);

-- ---------- distance cache ----------
CREATE TABLE IF NOT EXISTS distance_cache (
  origin_h3   text NOT NULL,
  dest_h3     text NOT NULL,
  distance_m  int NOT NULL,
  duration_s  int NOT NULL,
  fetched_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (origin_h3, dest_h3)
);

-- ---------- customer notes ----------
CREATE TABLE IF NOT EXISTS customer_notes (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id     uuid NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
  note            text NOT NULL,
  author_email    text,
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- ---------- import jobs (audit trail) ----------
CREATE TABLE IF NOT EXISTS import_jobs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  filename        text,
  rows_inserted   int NOT NULL DEFAULT 0,
  rows_updated    int NOT NULL DEFAULT 0,
  rows_errored    int NOT NULL DEFAULT 0,
  rows_flagged    int NOT NULL DEFAULT 0,
  errors          jsonb,
  imported_by     text,
  imported_at     timestamptz NOT NULL DEFAULT now()
);
