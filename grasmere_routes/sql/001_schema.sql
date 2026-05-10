-- Grasmere Routes — schema (v2, day-centric).
-- Idempotent: safe to re-run.
--
-- All monetary values stored as integer PENCE.

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

-- ---------- customers (lean — no status, no notes; lazy-created from the Fresho file) ----------
CREATE TABLE IF NOT EXISTS customers (
  id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_code             text NOT NULL UNIQUE,
  name                      text NOT NULL,
  delivery_address          text,
  delivery_lat              double precision,
  delivery_lng              double precision,
  geocode_confidence        text,
  geocoded_at               timestamptz,
  legacy_run_code           text,
  active                    boolean NOT NULL DEFAULT true,
  raw_csv_row               jsonb,
  created_at                timestamptz NOT NULL DEFAULT now(),
  updated_at                timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS customers_geocode_idx ON customers (delivery_lat, delivery_lng);

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

-- ---------- orders ----------
CREATE TABLE IF NOT EXISTS orders (
  id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id                 uuid NOT NULL REFERENCES customers(id) ON DELETE RESTRICT,
  delivery_date               date NOT NULL,
  weight_kg                   numeric(8,2),
  crate_count                 int,
  order_value_pence           int,
  cod_amount_pence            int,
  notes                       text,
  status                      text NOT NULL DEFAULT 'pending',
  order_number                text,
  legacy_run_code_override    text,
  delivery_address_override   text,
  created_at                  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS orders_date_idx ON orders (delivery_date);
CREATE UNIQUE INDEX IF NOT EXISTS orders_order_number_uidx
  ON orders (order_number) WHERE order_number IS NOT NULL;

-- ---------- routes (kept for future "publish" flows; nothing reads them in v2) ----------
CREATE TABLE IF NOT EXISTS routes (
  id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  delivery_date               date NOT NULL,
  vehicle_id                  uuid REFERENCES vehicles(id),
  status                      text NOT NULL DEFAULT 'draft',
  planned_distance_km         numeric(8,2),
  planned_duration_min        int,
  planned_total_cost_pence    int,
  optimiser_version           text,
  created_at                  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS route_stops (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  route_id      uuid NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
  order_id      uuid NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
  sequence      int NOT NULL,
  UNIQUE (route_id, sequence)
);

-- ---------- distance cache (Mapbox Matrix → H3-keyed) ----------
CREATE TABLE IF NOT EXISTS distance_cache (
  origin_h3   text NOT NULL,
  dest_h3     text NOT NULL,
  distance_m  int NOT NULL,
  duration_s  int NOT NULL,
  fetched_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (origin_h3, dest_h3)
);
