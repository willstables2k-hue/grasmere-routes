/**
 * Database schema for Grasmere Routes.
 *
 * All monetary values are stored as integer PENCE to avoid float drift.
 * UI converts to £ for display only.
 *
 * Customer status (live/dormant/no_history) is NOT stored as a column.
 * It is derived nightly from `last_delivery_date` + `manually_confirmed_live_at`
 * via the `customer_status_v` view (created in migration 0001 SQL).
 */
import {
  boolean,
  date,
  doublePrecision,
  index,
  integer,
  jsonb,
  numeric,
  pgTable,
  primaryKey,
  smallint,
  text,
  time,
  timestamp,
  uniqueIndex,
  uuid,
} from "drizzle-orm/pg-core";
import { sql } from "drizzle-orm";

// ---------- config (single row) ----------

export const config = pgTable("config", {
  id: smallint("id").primaryKey().default(1),
  dieselPricePencePerLitre: integer("diesel_price_pence_per_litre").notNull().default(188),
  defaultMpg: numeric("default_mpg", { precision: 5, scale: 2 }).notNull().default("25.00"),
  defaultDriverHourlyRatePence: integer("default_driver_hourly_rate_pence").notNull().default(1600),
  avgSpeedKmh: numeric("avg_speed_kmh", { precision: 5, scale: 2 }).notNull().default("50.00"),
  serviceTimeMinPerStop: integer("service_time_min_per_stop").notNull().default(8),
  depotLoadingTimeMin: integer("depot_loading_time_min").notNull().default(30),
  vehicleFixedCostPerDayPence: integer("vehicle_fixed_cost_per_day_pence").notNull().default(2500),
  driverMaxShiftHours: numeric("driver_max_shift_hours", { precision: 4, scale: 2 }).notNull().default("8.00"),
  defaultGrossMarginPct: numeric("default_gross_margin_pct", { precision: 4, scale: 3 }).notNull().default("0.280"),
  dormancyThresholdDays: integer("dormancy_threshold_days").notNull().default(180),
  workingDeliveryDays: integer("working_delivery_days").array().notNull().default(sql`ARRAY[1,3,4]::int[]`),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

// ---------- depot ----------

export const depot = pgTable("depot", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull(),
  address: text("address").notNull(),
  lat: doublePrecision("lat").notNull(),
  lng: doublePrecision("lng").notNull(),
  openingTime: time("opening_time").notNull().default("06:00"),
  closingTime: time("closing_time").notNull().default("18:00"),
});

// ---------- customers ----------

export const customers = pgTable(
  "customers",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    customerCode: text("customer_code").notNull(),
    name: text("name").notNull(),
    legalEntityName: text("legal_entity_name"),
    deliveryAddress: text("delivery_address"),
    deliveryLat: doublePrecision("delivery_lat"),
    deliveryLng: doublePrecision("delivery_lng"),
    geocodeConfidence: text("geocode_confidence"), // 'rooftop' | 'street' | 'postcode' | 'failed'
    geocodedAt: timestamp("geocoded_at", { withTimezone: true }),
    billingAddress: text("billing_address"),
    pricingLevel: text("pricing_level"),
    grossMarginPct: numeric("gross_margin_pct", { precision: 4, scale: 3 }),
    paymentTermDays: integer("payment_term_days"),
    isCod: boolean("is_cod").notNull().default(false),
    deliveryDaysGroup: text("delivery_days_group"),
    preferredDays: integer("preferred_days").array(), // 0=Mon … 6=Sun
    legacyRunCode: text("legacy_run_code"), // reference only, NOT used by optimiser
    legacyRunPosition: integer("legacy_run_position"), // reference only
    standingPickingInstructions: text("standing_picking_instructions"),
    standingDeliveryInstructions: text("standing_delivery_instructions"),
    softWindowStart: time("soft_window_start"),
    softWindowEnd: time("soft_window_end"),
    avgOrderValuePence: integer("avg_order_value_pence"),
    lastDeliveryDate: date("last_delivery_date"),
    manuallyConfirmedLiveAt: timestamp("manually_confirmed_live_at", { withTimezone: true }),
    active: boolean("active").notNull().default(true), // preserved from CSV; NOT used for routing
    salesRep: text("sales_rep"),
    tags: text("tags").array(),
    rawCsvRow: jsonb("raw_csv_row"),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => ({
    customerCodeIdx: uniqueIndex("customers_customer_code_uidx").on(t.customerCode),
    geocodeIdx: index("customers_geocode_idx").on(t.deliveryLat, t.deliveryLng),
    lastDeliveryIdx: index("customers_last_delivery_idx").on(t.lastDeliveryDate),
    activeIdx: index("customers_active_idx").on(t.active),
  }),
);

// ---------- vehicles ----------

export const vehicles = pgTable("vehicles", {
  id: uuid("id").primaryKey().defaultRandom(),
  registration: text("registration"),
  name: text("name").notNull(),
  mpg: numeric("mpg", { precision: 5, scale: 2 }),
  capacityKg: numeric("capacity_kg", { precision: 8, scale: 2 }).notNull().default("1200.00"),
  capacityCrates: integer("capacity_crates").notNull().default(80),
  refrigerated: boolean("refrigerated").notNull().default(true),
  fixedCostPerDayPence: integer("fixed_cost_per_day_pence"),
  active: boolean("active").notNull().default(true),
});

// ---------- drivers ----------

export const drivers = pgTable("drivers", {
  id: uuid("id").primaryKey().defaultRandom(),
  clerkUserId: text("clerk_user_id").unique(),
  name: text("name").notNull(),
  phone: text("phone"),
  hourlyRatePence: integer("hourly_rate_pence"),
  active: boolean("active").notNull().default(true),
});

// ---------- orders ----------

export const orders = pgTable(
  "orders",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    customerId: uuid("customer_id")
      .notNull()
      .references(() => customers.id, { onDelete: "restrict" }),
    deliveryDate: date("delivery_date").notNull(),
    weightKg: numeric("weight_kg", { precision: 8, scale: 2 }),
    crateCount: integer("crate_count"),
    orderValuePence: integer("order_value_pence"),
    codAmountPence: integer("cod_amount_pence"),
    notes: text("notes"),
    status: text("status").notNull().default("pending"),
    // 'pending' | 'planned' | 'out' | 'delivered' | 'failed' | 'cancelled'
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => ({
    customerDateIdx: index("orders_customer_date_idx").on(t.customerId, t.deliveryDate),
    dateStatusIdx: index("orders_date_status_idx").on(t.deliveryDate, t.status),
  }),
);

// ---------- routes ----------

export const routes = pgTable(
  "routes",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    deliveryDate: date("delivery_date").notNull(),
    driverId: uuid("driver_id").references(() => drivers.id),
    vehicleId: uuid("vehicle_id").references(() => vehicles.id),
    status: text("status").notNull().default("draft"),
    // 'draft' | 'published' | 'in_progress' | 'completed'

    // Planned (from optimiser)
    plannedDistanceKm: numeric("planned_distance_km", { precision: 8, scale: 2 }),
    plannedDurationMin: integer("planned_duration_min"),
    plannedFuelCostPence: integer("planned_fuel_cost_pence"),
    plannedLabourCostPence: integer("planned_labour_cost_pence"),
    plannedOverheadPence: integer("planned_overhead_pence"),
    plannedTotalCostPence: integer("planned_total_cost_pence"),

    // Actual (from completed deliveries)
    actualDistanceKm: numeric("actual_distance_km", { precision: 8, scale: 2 }),
    actualDurationMin: integer("actual_duration_min"),
    actualFuelCostPence: integer("actual_fuel_cost_pence"),
    actualLabourCostPence: integer("actual_labour_cost_pence"),
    actualTotalCostPence: integer("actual_total_cost_pence"),

    optimiserVersion: text("optimiser_version"),
    optimiserSeed: text("optimiser_seed").default("from_scratch"),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => ({
    dateIdx: index("routes_date_idx").on(t.deliveryDate),
  }),
);

// ---------- route_stops ----------

export const routeStops = pgTable(
  "route_stops",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    routeId: uuid("route_id")
      .notNull()
      .references(() => routes.id, { onDelete: "cascade" }),
    orderId: uuid("order_id")
      .notNull()
      .unique()
      .references(() => orders.id, { onDelete: "cascade" }),
    sequence: integer("sequence").notNull(),

    // Planned timings & legs
    plannedArrival: timestamp("planned_arrival", { withTimezone: true }),
    plannedDeparture: timestamp("planned_departure", { withTimezone: true }),
    plannedKmToStop: numeric("planned_km_to_stop", { precision: 8, scale: 3 }),
    plannedMinToStop: integer("planned_min_to_stop"),

    // Cost allocation (planned)
    plannedFuelSharePence: integer("planned_fuel_share_pence"),
    plannedLabourSharePence: integer("planned_labour_share_pence"),
    plannedOverheadSharePence: integer("planned_overhead_share_pence"),
    plannedDirectCostPence: integer("planned_direct_cost_pence"),
    plannedMarginalCostPence: integer("planned_marginal_cost_pence"),
    plannedGrossProfitPence: integer("planned_gross_profit_pence"),
    plannedNetContributionPence: integer("planned_net_contribution_pence"),

    // Actual
    actualArrival: timestamp("actual_arrival", { withTimezone: true }),
    actualDeparture: timestamp("actual_departure", { withTimezone: true }),
    podPhotoUrl: text("pod_photo_url"),
    podSignatureUrl: text("pod_signature_url"),
    podNotes: text("pod_notes"),
    codCollectedPence: integer("cod_collected_pence"),
    completedAt: timestamp("completed_at", { withTimezone: true }),
    failureReason: text("failure_reason"),
  },
  (t) => ({
    routeSeqIdx: uniqueIndex("route_stops_route_seq_uidx").on(t.routeId, t.sequence),
  }),
);

// ---------- baseline (legacy routing snapshot) ----------

export const baselineSnapshot = pgTable("baseline_snapshot", {
  id: uuid("id").primaryKey().defaultRandom(),
  computedAt: timestamp("computed_at", { withTimezone: true }).notNull().defaultNow(),
  configHash: text("config_hash").notNull(),
  customerCountIncluded: integer("customer_count_included").notNull(),
  customerCountExcluded: integer("customer_count_excluded").notNull(),
  totalDistanceKm: numeric("total_distance_km", { precision: 10, scale: 2 }).notNull(),
  totalFuelCostPence: integer("total_fuel_cost_pence").notNull(),
  totalLabourCostPence: integer("total_labour_cost_pence").notNull(),
  totalOverheadPence: integer("total_overhead_pence").notNull(),
  totalCostPence: integer("total_cost_pence").notNull(),
  totalStops: integer("total_stops").notNull(),
  weeklyCostPence: integer("weekly_cost_pence").notNull(),
  annualisedCostPence: integer("annualised_cost_pence").notNull(),
  isCurrent: boolean("is_current").notNull().default(false),
  notes: text("notes"),
});

export const baselineRoutes = pgTable(
  "baseline_routes",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    snapshotId: uuid("snapshot_id")
      .notNull()
      .references(() => baselineSnapshot.id, { onDelete: "cascade" }),
    vanColour: text("van_colour").notNull(),
    dayOfWeek: integer("day_of_week").notNull(), // 1=Tue, 3=Thu, 4=Fri
    stopCount: integer("stop_count").notNull(),
    distanceKm: numeric("distance_km", { precision: 8, scale: 2 }).notNull(),
    durationMin: integer("duration_min").notNull(),
    fuelCostPence: integer("fuel_cost_pence").notNull(),
    labourCostPence: integer("labour_cost_pence").notNull(),
    overheadPence: integer("overhead_pence").notNull(),
    totalCostPence: integer("total_cost_pence").notNull(),
    costPerStopPence: integer("cost_per_stop_pence").notNull(),
  },
  (t) => ({
    snapshotIdx: index("baseline_routes_snapshot_idx").on(t.snapshotId),
  }),
);

export const baselineRouteStops = pgTable(
  "baseline_route_stops",
  {
    id: uuid("id").primaryKey().defaultRandom(),
    baselineRouteId: uuid("baseline_route_id")
      .notNull()
      .references(() => baselineRoutes.id, { onDelete: "cascade" }),
    customerId: uuid("customer_id")
      .notNull()
      .references(() => customers.id, { onDelete: "restrict" }),
    sequence: integer("sequence").notNull(),
    kmToStop: numeric("km_to_stop", { precision: 8, scale: 3 }).notNull(),
    minToStop: integer("min_to_stop").notNull(),
    fuelSharePence: integer("fuel_share_pence").notNull(),
    labourSharePence: integer("labour_share_pence").notNull(),
    overheadSharePence: integer("overhead_share_pence").notNull(),
    directCostPence: integer("direct_cost_pence").notNull(),
  },
  (t) => ({
    routeSeqIdx: uniqueIndex("baseline_route_stops_route_seq_uidx").on(
      t.baselineRouteId,
      t.sequence,
    ),
  }),
);

// ---------- distance_cache (Mapbox Matrix, H3-keyed) ----------

export const distanceCache = pgTable(
  "distance_cache",
  {
    originH3: text("origin_h3").notNull(),
    destH3: text("dest_h3").notNull(),
    distanceM: integer("distance_m").notNull(),
    durationS: integer("duration_s").notNull(),
    fetchedAt: timestamp("fetched_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => ({
    pk: primaryKey({ columns: [t.originH3, t.destH3] }),
  }),
);

// ---------- baseline-related notes per customer ----------

export const customerNotes = pgTable("customer_notes", {
  id: uuid("id").primaryKey().defaultRandom(),
  customerId: uuid("customer_id")
    .notNull()
    .references(() => customers.id, { onDelete: "cascade" }),
  note: text("note").notNull(),
  authorClerkId: text("author_clerk_id"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

// ---------- Re-exports for migrate / inference ----------

export type Customer = typeof customers.$inferSelect;
export type NewCustomer = typeof customers.$inferInsert;
export type Order = typeof orders.$inferSelect;
export type Route = typeof routes.$inferSelect;
export type RouteStop = typeof routeStops.$inferSelect;
export type BaselineSnapshot = typeof baselineSnapshot.$inferSelect;
export type BaselineRoute = typeof baselineRoutes.$inferSelect;
export type Vehicle = typeof vehicles.$inferSelect;
export type Driver = typeof drivers.$inferSelect;
export type Config = typeof config.$inferSelect;
