/**
 * Server-side orchestration of the baseline reconstruction.
 *
 *   1. Pull live customers (status filter via customer_status_v).
 *   2. Drop those whose legacy_run_code is mail-order (~NR) or unparseable.
 *   3. Group survivors by (van colour × day of week) using decoded codes.
 *   4. Call the optimiser /baseline_cost endpoint.
 *   5. Persist baseline_snapshot + baseline_routes + baseline_route_stops.
 *   6. Mark this snapshot as is_current = TRUE; demote previous current.
 *
 * The "data hygiene" line item in /economics relies on this being correct.
 */
import { sql, eq, and, ne } from "drizzle-orm";
import { createHash } from "node:crypto";
import { db, schema } from "@/db/client";
import { execRows } from "./db-utils";
import { decodeRunCode, RUN_DAYS, type DayOfWeek, type VanColour } from "./run-code";
import { optimiser, type BaselineRequest } from "./optimiser-client";

export interface BaselineComputeResult {
  snapshotId: string;
  customerCountIncluded: number;
  customerCountExcluded: number;
  weeklyCostPence: number;
  annualisedCostPence: number;
  totalDistanceKm: number;
  routeBreakdown: { vanColour: string; dayOfWeek: number; totalCostPence: number }[];
}

interface LiveCustomerRow {
  id: string;
  legacy_run_code: string | null;
  delivery_lat: number | null;
  delivery_lng: number | null;
}

interface ConfigRow {
  diesel_price_pence_per_litre: number;
  default_mpg: string;
  default_driver_hourly_rate_pence: number;
  avg_speed_kmh: string;
  service_time_min_per_stop: number;
  depot_loading_time_min: number;
  vehicle_fixed_cost_per_day_pence: number;
}

export async function recomputeBaseline(): Promise<BaselineComputeResult> {
  // ---- read config ----
  const cfgRows = await execRows<ConfigRow>(sql`SELECT * FROM config WHERE id = 1`);
  const cfg = cfgRows[0];
  if (!cfg) throw new Error("config row missing — run db:migrate seed");

  const depotRow = await execRows<{ lat: number; lng: number }>(
    sql`SELECT lat, lng FROM depot ORDER BY name LIMIT 1`,
  );
  const depot = depotRow[0];
  if (!depot) throw new Error("no depot row — run db:migrate seed");

  // ---- pull live customers with geocodes ----
  const live = await execRows<LiveCustomerRow>(sql`
    SELECT c.id, c.legacy_run_code, c.delivery_lat, c.delivery_lng
    FROM customers c
    JOIN customer_status_v s ON s.customer_id = c.id
    WHERE c.active = TRUE AND s.status = 'live'
  `);

  // ---- group by van colour and day ----
  type Group = {
    vanColour: VanColour;
    dayOfWeek: DayOfWeek;
    customers: LiveCustomerRow[];
  };
  const groups = new Map<string, Group>();
  let excluded = 0;

  for (const c of live) {
    if (c.delivery_lat == null || c.delivery_lng == null) {
      excluded++;
      continue;
    }
    const decoded = decodeRunCode(c.legacy_run_code);
    if (decoded.isMailOrder || decoded.unparseable) {
      excluded++;
      continue;
    }
    for (const day of RUN_DAYS) {
      const colour = decoded.byDay[day];
      if (!colour) continue;
      const key = `${colour}|${day}`;
      const g =
        groups.get(key) ??
        ({ vanColour: colour, dayOfWeek: day, customers: [] } satisfies Group);
      g.customers.push(c);
      groups.set(key, g);
    }
  }

  // ---- call optimiser /baseline_cost ----
  const req: BaselineRequest = {
    depot: { lat: depot.lat, lng: depot.lng },
    baseline_routes: Array.from(groups.values()).map((g) => ({
      van_colour: g.vanColour,
      day_of_week: g.dayOfWeek,
      stops: g.customers.map((c) => ({
        id: c.id,
        lat: c.delivery_lat!,
        lng: c.delivery_lng!,
        weight_kg: 0,
        crate_count: 0,
        service_minutes: cfg.service_time_min_per_stop,
      })),
    })),
    cost_params: {
      diesel_price_pence_per_litre: cfg.diesel_price_pence_per_litre,
      vehicle_mpg: Number(cfg.default_mpg),
      driver_hourly_rate_pence: cfg.default_driver_hourly_rate_pence,
      avg_speed_kmh: Number(cfg.avg_speed_kmh),
      service_min_per_stop: cfg.service_time_min_per_stop,
      depot_loading_min: cfg.depot_loading_time_min,
      vehicle_fixed_cost_per_day_pence: cfg.vehicle_fixed_cost_per_day_pence,
    },
  };

  const resp = await optimiser.baselineCost(req);

  // ---- persist ----
  const cfgHash = hashConfig(cfg);

  // Demote previous current
  await db
    .update(schema.baselineSnapshot)
    .set({ isCurrent: false })
    .where(eq(schema.baselineSnapshot.isCurrent, true));

  const [snap] = await db
    .insert(schema.baselineSnapshot)
    .values({
      configHash: cfgHash,
      customerCountIncluded: live.length - excluded,
      customerCountExcluded: excluded,
      totalDistanceKm: resp.summary.total_distance_km.toString(),
      totalFuelCostPence: resp.baseline_routes.reduce((a, r) => a + r.fuel_cost_pence, 0),
      totalLabourCostPence: resp.baseline_routes.reduce((a, r) => a + r.labour_cost_pence, 0),
      totalOverheadPence: resp.baseline_routes.reduce((a, r) => a + r.overhead_pence, 0),
      totalCostPence: resp.summary.total_cost_pence,
      totalStops: resp.summary.total_stops,
      weeklyCostPence: resp.summary.weekly_cost_pence,
      annualisedCostPence: resp.summary.annualised_cost_pence,
      isCurrent: true,
      notes: `Computed from ${live.length} live customers; ${excluded} excluded (mail-order, unparseable codes, or no geocode)`,
    })
    .returning({ id: schema.baselineSnapshot.id });

  for (const r of resp.baseline_routes) {
    const [insertedRoute] = await db
      .insert(schema.baselineRoutes)
      .values({
        snapshotId: snap!.id,
        vanColour: r.van_colour,
        dayOfWeek: r.day_of_week,
        stopCount: r.stop_sequence.length,
        distanceKm: r.total_distance_km.toString(),
        durationMin: r.total_duration_min,
        fuelCostPence: r.fuel_cost_pence,
        labourCostPence: r.labour_cost_pence,
        overheadPence: r.overhead_pence,
        totalCostPence: r.total_cost_pence,
        costPerStopPence: Math.round(r.total_cost_pence / Math.max(r.stop_sequence.length, 1)),
      })
      .returning({ id: schema.baselineRoutes.id });

    // Per-stop allocation rows
    for (let i = 0; i < r.stop_sequence.length; i++) {
      const cid = r.stop_sequence[i]!;
      const legKm = r.leg_distances_km[i] ?? 0;
      const legMin = r.leg_durations_min[i] ?? 0;
      const fuelShare = Math.round((legKm / Math.max(r.total_distance_km, 0.001)) * r.fuel_cost_pence);
      const labourShare = Math.round((legMin / Math.max(r.total_duration_min, 1)) * r.labour_cost_pence);
      const overheadShare = Math.floor(r.overhead_pence / Math.max(r.stop_sequence.length, 1));
      await db.insert(schema.baselineRouteStops).values({
        baselineRouteId: insertedRoute!.id,
        customerId: cid,
        sequence: i + 1,
        kmToStop: legKm.toString(),
        minToStop: legMin,
        fuelSharePence: fuelShare,
        labourSharePence: labourShare,
        overheadSharePence: overheadShare,
        directCostPence: fuelShare + labourShare + overheadShare,
      });
    }
  }

  return {
    snapshotId: snap!.id,
    customerCountIncluded: live.length - excluded,
    customerCountExcluded: excluded,
    weeklyCostPence: resp.summary.weekly_cost_pence,
    annualisedCostPence: resp.summary.annualised_cost_pence,
    totalDistanceKm: resp.summary.total_distance_km,
    routeBreakdown: resp.baseline_routes.map((r) => ({
      vanColour: r.van_colour,
      dayOfWeek: r.day_of_week,
      totalCostPence: r.total_cost_pence,
    })),
  };
}

function hashConfig(cfg: ConfigRow): string {
  return createHash("sha256")
    .update(JSON.stringify(cfg))
    .digest("hex")
    .slice(0, 16);
}

export async function getCurrentBaseline() {
  const rows = await db
    .select()
    .from(schema.baselineSnapshot)
    .where(eq(schema.baselineSnapshot.isCurrent, true))
    .limit(1);
  return rows[0] ?? null;
}

export async function getCurrentBaselineRoutes(snapshotId: string) {
  return db
    .select()
    .from(schema.baselineRoutes)
    .where(eq(schema.baselineRoutes.snapshotId, snapshotId))
    .orderBy(schema.baselineRoutes.dayOfWeek, schema.baselineRoutes.vanColour);
}

// silence unused-import lint (and, ne) — kept for future filters
void and; void ne;
