/**
 * Plan-week service.
 *
 *   generateOrders(date)  — create pending orders for live customers whose
 *                           preferred_days includes that day. Skips dormant +
 *                           no_history. Returns the count.
 *   optimisePlan(date)    — fetch all pending orders for date, call optimiser,
 *                           persist routes + route_stops, compute the matched
 *                           baseline cost for the same customer set, return
 *                           a comparison.
 */
import { sql, eq, and } from "drizzle-orm";
import { db, schema } from "@/db/client";
import { execRows } from "./db-utils";
import { optimiser, type OptimiseRequest, type StopSpec, type VehicleSpec } from "./optimiser-client";
import { decodeRunCode, RUN_DAYS, type DayOfWeek } from "./run-code";

export async function generateOrders(deliveryDate: string): Promise<{
  ordersCreated: number;
  liveMatching: number;
  dormantMatchingHidden: number;
}> {
  const dow = jsDayToPrefDay(new Date(deliveryDate).getDay());

  // 1. Find live customers whose preferred_days includes this day
  const liveList = await execRows<{ id: string }>(sql`
    SELECT c.id
    FROM customers c
    JOIN customer_status_v s ON s.customer_id = c.id
    WHERE c.active = TRUE
      AND s.status = 'live'
      AND ${dow} = ANY(c.preferred_days)
  `);

  // 2. Count dormant matches for the "X dormant could be added" message
  const dormant = await execRows<{ n: number }>(sql`
    SELECT COUNT(*)::int AS n
    FROM customers c
    JOIN customer_status_v s ON s.customer_id = c.id
    WHERE c.active = TRUE
      AND s.status IN ('dormant','no_history')
      AND ${dow} = ANY(c.preferred_days)
  `);
  const dormantCount = dormant[0]?.n ?? 0;

  // 3. Insert pending orders idempotently — skip customers that already have a pending order today
  let created = 0;
  for (const c of liveList) {
    const exists = await db
      .select({ id: schema.orders.id })
      .from(schema.orders)
      .where(
        and(
          eq(schema.orders.customerId, c.id),
          eq(schema.orders.deliveryDate, deliveryDate),
        ),
      )
      .limit(1);
    if (exists[0]) continue;
    await db.insert(schema.orders).values({
      customerId: c.id,
      deliveryDate,
      status: "pending",
      orderValuePence: null,
    });
    created++;
  }

  return { ordersCreated: created, liveMatching: liveList.length, dormantMatchingHidden: dormantCount };
}

export async function optimisePlan(deliveryDate: string) {
  // ---- read config + depot + vehicles ----
  type ConfigRow = {
    diesel_price_pence_per_litre: number;
    default_mpg: string;
    default_driver_hourly_rate_pence: number;
    avg_speed_kmh: string;
    service_time_min_per_stop: number;
    depot_loading_time_min: number;
    vehicle_fixed_cost_per_day_pence: number;
    driver_max_shift_hours: string;
  };
  const cfgRows = await execRows<ConfigRow>(sql`SELECT * FROM config WHERE id = 1`);
  const cfg = cfgRows[0];
  const depotRow = await execRows<{ lat: number; lng: number }>(
    sql`SELECT lat, lng FROM depot ORDER BY name LIMIT 1`,
  );
  const depot = depotRow[0];
  if (!cfg || !depot) throw new Error("config/depot not seeded");

  const vehiclesRows = await db
    .select()
    .from(schema.vehicles)
    .where(eq(schema.vehicles.active, true));

  // If no vehicles are configured, fall back to a sensible default fleet so the user can plan.
  const vehicles: VehicleSpec[] =
    vehiclesRows.length > 0
      ? vehiclesRows.map((v) => ({
          id: v.id,
          capacity_kg: Number(v.capacityKg),
          capacity_crates: v.capacityCrates,
          shift_minutes: Math.round(Number(cfg.driver_max_shift_hours) * 60),
          mpg: v.mpg ? Number(v.mpg) : Number(cfg.default_mpg),
          diesel_price_pence_per_litre: cfg.diesel_price_pence_per_litre,
          labour_cost_per_hour_pence: cfg.default_driver_hourly_rate_pence,
          overhead_pence: v.fixedCostPerDayPence ?? cfg.vehicle_fixed_cost_per_day_pence,
        }))
      : Array.from({ length: 7 }, (_, i) => ({
          id: `default-v${i + 1}`,
          capacity_kg: 1200,
          capacity_crates: 80,
          shift_minutes: Math.round(Number(cfg.driver_max_shift_hours) * 60),
          mpg: Number(cfg.default_mpg),
          diesel_price_pence_per_litre: cfg.diesel_price_pence_per_litre,
          labour_cost_per_hour_pence: cfg.default_driver_hourly_rate_pence,
          overhead_pence: cfg.vehicle_fixed_cost_per_day_pence,
        }));

  // ---- pull pending orders + customer geocodes ----
  type OrderRow = {
    order_id: string;
    customer_id: string;
    weight_kg: string | null;
    crate_count: number | null;
    lat: number;
    lng: number;
    legacy_run_code: string | null;
  };
  const orders = await execRows<OrderRow>(sql`
    SELECT o.id AS order_id, c.id AS customer_id,
           o.weight_kg, o.crate_count,
           c.delivery_lat AS lat, c.delivery_lng AS lng,
           c.legacy_run_code
    FROM orders o
    JOIN customers c ON c.id = o.customer_id
    WHERE o.delivery_date = ${deliveryDate}
      AND o.status IN ('pending','planned')
      AND c.delivery_lat IS NOT NULL
      AND c.delivery_lng IS NOT NULL
  `);

  if (orders.length === 0) {
    return { ok: false as const, reason: "no orders for date — generate orders first" };
  }

  // ---- call optimiser ----
  const stops: StopSpec[] = orders.map((o) => ({
    id: o.order_id,
    lat: o.lat,
    lng: o.lng,
    weight_kg: o.weight_kg ? Number(o.weight_kg) : 50,
    crate_count: o.crate_count ?? 3,
    service_minutes: cfg.service_time_min_per_stop,
  }));

  const optReq: OptimiseRequest = {
    depot: { lat: depot.lat, lng: depot.lng },
    delivery_date: deliveryDate,
    vehicles,
    stops,
    service_time_minutes_default: cfg.service_time_min_per_stop,
    depot_loading_minutes: cfg.depot_loading_time_min,
    avg_speed_kmh: Number(cfg.avg_speed_kmh),
  };
  const optResp = await optimiser.optimise(optReq);

  // ---- compute matched baseline (same customers, legacy van groupings, this day only) ----
  const dow = jsDayToPrefDay(new Date(deliveryDate).getDay()) as DayOfWeek;
  const customerById = new Map(orders.map((o) => [o.customer_id, o]));
  const groupsMap = new Map<string, OrderRow[]>();
  for (const o of orders) {
    const decoded = decodeRunCode(o.legacy_run_code);
    if (decoded.isMailOrder || decoded.unparseable) continue;
    if (!RUN_DAYS.includes(dow)) continue;
    const colour = decoded.byDay[dow];
    if (!colour) continue;
    const key = colour;
    const arr = groupsMap.get(key) ?? [];
    arr.push(o);
    groupsMap.set(key, arr);
  }
  const baselineForDay = await optimiser.baselineCost({
    depot: { lat: depot.lat, lng: depot.lng },
    baseline_routes: Array.from(groupsMap.entries()).map(([colour, custs]) => ({
      van_colour: colour,
      day_of_week: dow,
      stops: custs.map((c) => ({
        id: c.customer_id,
        lat: c.lat,
        lng: c.lng,
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
  });

  // ---- persist routes ----
  // Wipe previous draft routes for this date so re-running is safe.
  await db.execute(sql`
    DELETE FROM routes WHERE delivery_date = ${deliveryDate} AND status = 'draft'
  `);

  const persistedRoutes: { id: string; vehicleId: string; stops: string[]; totalCostPence: number }[] = [];
  for (const r of optResp.routes) {
    const [persisted] = await db
      .insert(schema.routes)
      .values({
        deliveryDate,
        vehicleId: vehiclesRows.find((v) => v.id === r.vehicle_id)?.id ?? null,
        status: "draft",
        plannedDistanceKm: r.total_distance_km.toString(),
        plannedDurationMin: r.total_duration_min,
        plannedFuelCostPence: r.fuel_cost_pence,
        plannedLabourCostPence: r.labour_cost_pence,
        plannedOverheadPence: r.overhead_pence,
        plannedTotalCostPence: r.total_cost_pence,
        optimiserVersion: optResp.optimiser_version,
        optimiserSeed: "from_scratch",
      })
      .returning({ id: schema.routes.id });

    for (let i = 0; i < r.stop_sequence.length; i++) {
      const orderId = r.stop_sequence[i]!;
      const legKm = r.leg_distances_km[i] ?? 0;
      const legMin = r.leg_durations_min[i] ?? 0;
      const fuelShare = Math.round((legKm / Math.max(r.total_distance_km, 0.001)) * r.fuel_cost_pence);
      const labourShare = Math.round((legMin / Math.max(r.total_duration_min, 1)) * r.labour_cost_pence);
      const overheadShare = Math.floor(r.overhead_pence / Math.max(r.stop_sequence.length, 1));
      await db.insert(schema.routeStops).values({
        routeId: persisted!.id,
        orderId,
        sequence: i + 1,
        plannedKmToStop: legKm.toString(),
        plannedMinToStop: legMin,
        plannedFuelSharePence: fuelShare,
        plannedLabourSharePence: labourShare,
        plannedOverheadSharePence: overheadShare,
        plannedDirectCostPence: fuelShare + labourShare + overheadShare,
      });
      await db
        .update(schema.orders)
        .set({ status: "planned" })
        .where(eq(schema.orders.id, orderId));
    }
    persistedRoutes.push({
      id: persisted!.id,
      vehicleId: r.vehicle_id,
      stops: r.stop_sequence,
      totalCostPence: r.total_cost_pence,
    });
  }

  return {
    ok: true as const,
    optimisedTotalPence: optResp.objective_value_pence,
    baselineTotalPence: baselineForDay.summary.total_cost_pence,
    savingPence:
      baselineForDay.summary.total_cost_pence - optResp.objective_value_pence,
    savingPct:
      baselineForDay.summary.total_cost_pence > 0
        ? (baselineForDay.summary.total_cost_pence - optResp.objective_value_pence) /
          baselineForDay.summary.total_cost_pence
        : 0,
    routes: optResp.routes,
    baselineRoutes: baselineForDay.baseline_routes,
    unassigned: optResp.unassigned_stops,
    solveSeconds: optResp.solve_seconds,
  };

  void customerById; // reserved for future drag-drop deltas
}

/** JS getDay() returns 0=Sun .. 6=Sat. We store preferred_days as 0=Mon .. 6=Sun. */
function jsDayToPrefDay(jsDay: number): number {
  return (jsDay + 6) % 7;
}
