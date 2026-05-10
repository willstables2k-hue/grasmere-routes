CREATE TABLE IF NOT EXISTS "baseline_route_stops" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"baseline_route_id" uuid NOT NULL,
	"customer_id" uuid NOT NULL,
	"sequence" integer NOT NULL,
	"km_to_stop" numeric(8, 3) NOT NULL,
	"min_to_stop" integer NOT NULL,
	"fuel_share_pence" integer NOT NULL,
	"labour_share_pence" integer NOT NULL,
	"overhead_share_pence" integer NOT NULL,
	"direct_cost_pence" integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "baseline_routes" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"snapshot_id" uuid NOT NULL,
	"van_colour" text NOT NULL,
	"day_of_week" integer NOT NULL,
	"stop_count" integer NOT NULL,
	"distance_km" numeric(8, 2) NOT NULL,
	"duration_min" integer NOT NULL,
	"fuel_cost_pence" integer NOT NULL,
	"labour_cost_pence" integer NOT NULL,
	"overhead_pence" integer NOT NULL,
	"total_cost_pence" integer NOT NULL,
	"cost_per_stop_pence" integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "baseline_snapshot" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"computed_at" timestamp with time zone DEFAULT now() NOT NULL,
	"config_hash" text NOT NULL,
	"customer_count_included" integer NOT NULL,
	"customer_count_excluded" integer NOT NULL,
	"total_distance_km" numeric(10, 2) NOT NULL,
	"total_fuel_cost_pence" integer NOT NULL,
	"total_labour_cost_pence" integer NOT NULL,
	"total_overhead_pence" integer NOT NULL,
	"total_cost_pence" integer NOT NULL,
	"total_stops" integer NOT NULL,
	"weekly_cost_pence" integer NOT NULL,
	"annualised_cost_pence" integer NOT NULL,
	"is_current" boolean DEFAULT false NOT NULL,
	"notes" text
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "config" (
	"id" smallint PRIMARY KEY DEFAULT 1 NOT NULL,
	"diesel_price_pence_per_litre" integer DEFAULT 188 NOT NULL,
	"default_mpg" numeric(5, 2) DEFAULT '25.00' NOT NULL,
	"default_driver_hourly_rate_pence" integer DEFAULT 1600 NOT NULL,
	"avg_speed_kmh" numeric(5, 2) DEFAULT '50.00' NOT NULL,
	"service_time_min_per_stop" integer DEFAULT 8 NOT NULL,
	"depot_loading_time_min" integer DEFAULT 30 NOT NULL,
	"vehicle_fixed_cost_per_day_pence" integer DEFAULT 2500 NOT NULL,
	"driver_max_shift_hours" numeric(4, 2) DEFAULT '8.00' NOT NULL,
	"default_gross_margin_pct" numeric(4, 3) DEFAULT '0.280' NOT NULL,
	"dormancy_threshold_days" integer DEFAULT 180 NOT NULL,
	"working_delivery_days" integer[] DEFAULT ARRAY[1,3,4]::int[] NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "customer_notes" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"customer_id" uuid NOT NULL,
	"note" text NOT NULL,
	"author_clerk_id" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "customers" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"customer_code" text NOT NULL,
	"name" text NOT NULL,
	"legal_entity_name" text,
	"delivery_address" text,
	"delivery_lat" double precision,
	"delivery_lng" double precision,
	"geocode_confidence" text,
	"geocoded_at" timestamp with time zone,
	"billing_address" text,
	"pricing_level" text,
	"gross_margin_pct" numeric(4, 3),
	"payment_term_days" integer,
	"is_cod" boolean DEFAULT false NOT NULL,
	"delivery_days_group" text,
	"preferred_days" integer[],
	"legacy_run_code" text,
	"legacy_run_position" integer,
	"standing_picking_instructions" text,
	"standing_delivery_instructions" text,
	"soft_window_start" time,
	"soft_window_end" time,
	"avg_order_value_pence" integer,
	"last_delivery_date" date,
	"manually_confirmed_live_at" timestamp with time zone,
	"active" boolean DEFAULT true NOT NULL,
	"sales_rep" text,
	"tags" text[],
	"raw_csv_row" jsonb,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "depot" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"name" text NOT NULL,
	"address" text NOT NULL,
	"lat" double precision NOT NULL,
	"lng" double precision NOT NULL,
	"opening_time" time DEFAULT '06:00' NOT NULL,
	"closing_time" time DEFAULT '18:00' NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "distance_cache" (
	"origin_h3" text NOT NULL,
	"dest_h3" text NOT NULL,
	"distance_m" integer NOT NULL,
	"duration_s" integer NOT NULL,
	"fetched_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "distance_cache_origin_h3_dest_h3_pk" PRIMARY KEY("origin_h3","dest_h3")
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "drivers" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"clerk_user_id" text,
	"name" text NOT NULL,
	"phone" text,
	"hourly_rate_pence" integer,
	"active" boolean DEFAULT true NOT NULL,
	CONSTRAINT "drivers_clerk_user_id_unique" UNIQUE("clerk_user_id")
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "orders" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"customer_id" uuid NOT NULL,
	"delivery_date" date NOT NULL,
	"weight_kg" numeric(8, 2),
	"crate_count" integer,
	"order_value_pence" integer,
	"cod_amount_pence" integer,
	"notes" text,
	"status" text DEFAULT 'pending' NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "route_stops" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"route_id" uuid NOT NULL,
	"order_id" uuid NOT NULL,
	"sequence" integer NOT NULL,
	"planned_arrival" timestamp with time zone,
	"planned_departure" timestamp with time zone,
	"planned_km_to_stop" numeric(8, 3),
	"planned_min_to_stop" integer,
	"planned_fuel_share_pence" integer,
	"planned_labour_share_pence" integer,
	"planned_overhead_share_pence" integer,
	"planned_direct_cost_pence" integer,
	"planned_marginal_cost_pence" integer,
	"planned_gross_profit_pence" integer,
	"planned_net_contribution_pence" integer,
	"actual_arrival" timestamp with time zone,
	"actual_departure" timestamp with time zone,
	"pod_photo_url" text,
	"pod_signature_url" text,
	"pod_notes" text,
	"cod_collected_pence" integer,
	"completed_at" timestamp with time zone,
	"failure_reason" text,
	CONSTRAINT "route_stops_order_id_unique" UNIQUE("order_id")
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "routes" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"delivery_date" date NOT NULL,
	"driver_id" uuid,
	"vehicle_id" uuid,
	"status" text DEFAULT 'draft' NOT NULL,
	"planned_distance_km" numeric(8, 2),
	"planned_duration_min" integer,
	"planned_fuel_cost_pence" integer,
	"planned_labour_cost_pence" integer,
	"planned_overhead_pence" integer,
	"planned_total_cost_pence" integer,
	"actual_distance_km" numeric(8, 2),
	"actual_duration_min" integer,
	"actual_fuel_cost_pence" integer,
	"actual_labour_cost_pence" integer,
	"actual_total_cost_pence" integer,
	"optimiser_version" text,
	"optimiser_seed" text DEFAULT 'from_scratch',
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "vehicles" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"registration" text,
	"name" text NOT NULL,
	"mpg" numeric(5, 2),
	"capacity_kg" numeric(8, 2) DEFAULT '1200.00' NOT NULL,
	"capacity_crates" integer DEFAULT 80 NOT NULL,
	"refrigerated" boolean DEFAULT true NOT NULL,
	"fixed_cost_per_day_pence" integer,
	"active" boolean DEFAULT true NOT NULL
);
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "baseline_route_stops" ADD CONSTRAINT "baseline_route_stops_baseline_route_id_baseline_routes_id_fk" FOREIGN KEY ("baseline_route_id") REFERENCES "public"."baseline_routes"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "baseline_route_stops" ADD CONSTRAINT "baseline_route_stops_customer_id_customers_id_fk" FOREIGN KEY ("customer_id") REFERENCES "public"."customers"("id") ON DELETE restrict ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "baseline_routes" ADD CONSTRAINT "baseline_routes_snapshot_id_baseline_snapshot_id_fk" FOREIGN KEY ("snapshot_id") REFERENCES "public"."baseline_snapshot"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "customer_notes" ADD CONSTRAINT "customer_notes_customer_id_customers_id_fk" FOREIGN KEY ("customer_id") REFERENCES "public"."customers"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "orders" ADD CONSTRAINT "orders_customer_id_customers_id_fk" FOREIGN KEY ("customer_id") REFERENCES "public"."customers"("id") ON DELETE restrict ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "route_stops" ADD CONSTRAINT "route_stops_route_id_routes_id_fk" FOREIGN KEY ("route_id") REFERENCES "public"."routes"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "route_stops" ADD CONSTRAINT "route_stops_order_id_orders_id_fk" FOREIGN KEY ("order_id") REFERENCES "public"."orders"("id") ON DELETE cascade ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "routes" ADD CONSTRAINT "routes_driver_id_drivers_id_fk" FOREIGN KEY ("driver_id") REFERENCES "public"."drivers"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "routes" ADD CONSTRAINT "routes_vehicle_id_vehicles_id_fk" FOREIGN KEY ("vehicle_id") REFERENCES "public"."vehicles"("id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "baseline_route_stops_route_seq_uidx" ON "baseline_route_stops" USING btree ("baseline_route_id","sequence");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "baseline_routes_snapshot_idx" ON "baseline_routes" USING btree ("snapshot_id");--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "customers_customer_code_uidx" ON "customers" USING btree ("customer_code");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "customers_geocode_idx" ON "customers" USING btree ("delivery_lat","delivery_lng");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "customers_last_delivery_idx" ON "customers" USING btree ("last_delivery_date");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "customers_active_idx" ON "customers" USING btree ("active");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "orders_customer_date_idx" ON "orders" USING btree ("customer_id","delivery_date");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "orders_date_status_idx" ON "orders" USING btree ("delivery_date","status");--> statement-breakpoint
CREATE UNIQUE INDEX IF NOT EXISTS "route_stops_route_seq_uidx" ON "route_stops" USING btree ("route_id","sequence");--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "routes_date_idx" ON "routes" USING btree ("delivery_date");