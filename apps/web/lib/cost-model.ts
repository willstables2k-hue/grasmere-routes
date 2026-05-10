/**
 * Cost-model library — the spine of the Grasmere Routes platform.
 *
 *   route_total = fuel_cost + labour_cost + overhead
 *
 *     fuel_litres   = (km / 1.609) / mpg × UK_GALLON_L
 *     fuel_cost_£   = fuel_litres × diesel_price_per_litre
 *     driving_hours = km / avg_speed_kmh
 *     service_hours = num_stops × service_min / 60
 *     loading_hours = depot_loading_min / 60
 *     labour_cost_£ = (driving + service + loading) × hourly_rate
 *     overhead_£    = vehicle_fixed_cost_per_day  (flat, per route)
 *
 * Mirrored byte-for-byte in apps/optimiser/app/cost_model.py — the two are
 * tested against shared fixtures so both produce identical penny figures.
 *
 * IMPORTANT: mpg here is IMPERIAL (UK gallon = 4.546 L), not US (3.785 L).
 * UK_GALLON_L is hard-coded; do NOT promote it to a config option.
 *
 * All money in this module is integer PENCE. Floats are used only for
 * intermediate physics (km, hours, litres) before rounding to pence.
 */

// --- physical constants (do not move to config) ---
export const KM_PER_MILE = 1.609344;
export const UK_GALLON_L = 4.546;

// ---------- types ----------

export interface CostParams {
  /** £/L diesel, in pence — e.g. 188 = £1.88/L */
  dieselPricePencePerLitre: number;
  /** vehicle fuel economy in imperial mpg */
  vehicleMpg: number;
  /** driver gross hourly rate in pence — e.g. 1600 = £16.00/h */
  driverHourlyRatePence: number;
  /** rural-mix average road speed in km/h */
  avgSpeedKmh: number;
  /** minutes spent at each delivery (park, walk, hand-over, paperwork) */
  serviceMinPerStop: number;
  /** one-time depot loading penalty per route */
  depotLoadingMin: number;
  /** flat insurance/tax/maintenance allocation per route */
  vehicleFixedCostPerDayPence: number;
}

export interface RouteCostInputs {
  distanceKm: number;
  numStops: number;
}

export interface RouteCost {
  fuelLitres: number;
  drivingHours: number;
  serviceHours: number;
  loadingHours: number;
  totalHours: number;
  fuelCostPence: number;
  labourCostPence: number;
  overheadPence: number;
  totalCostPence: number;
}

export interface StopCostShare {
  fuelSharePence: number;
  labourSharePence: number;
  overheadSharePence: number;
  directCostPence: number;
}

// ---------- helpers ----------

const round = (n: number) => Math.round(n);

const safeDiv = (num: number, den: number, fallback = 0) =>
  den === 0 ? fallback : num / den;

// ---------- public API ----------

/**
 * Cost of a single route given total km and stop count.
 *
 *   - num_stops = 0  → still has loading + overhead (a route was dispatched
 *     but had no live deliveries, e.g. all cancelled). distance/fuel will
 *     just be zero in that case.
 *   - distance = 0   → fuel = 0, driving_hours = 0; labour still includes
 *     loading + service.
 */
export function computeRouteCost(
  inputs: RouteCostInputs,
  params: CostParams,
): RouteCost {
  const { distanceKm, numStops } = inputs;
  const {
    dieselPricePencePerLitre,
    vehicleMpg,
    driverHourlyRatePence,
    avgSpeedKmh,
    serviceMinPerStop,
    depotLoadingMin,
    vehicleFixedCostPerDayPence,
  } = params;

  if (vehicleMpg <= 0) throw new Error("vehicleMpg must be > 0");
  if (avgSpeedKmh <= 0) throw new Error("avgSpeedKmh must be > 0");

  const fuelLitres =
    distanceKm <= 0 ? 0 : (distanceKm / KM_PER_MILE / vehicleMpg) * UK_GALLON_L;
  const fuelCostPence = round(fuelLitres * dieselPricePencePerLitre);

  const drivingHours = distanceKm / avgSpeedKmh;
  const serviceHours = (numStops * serviceMinPerStop) / 60;
  const loadingHours = depotLoadingMin / 60;
  const totalHours = drivingHours + serviceHours + loadingHours;
  const labourCostPence = round(totalHours * driverHourlyRatePence);

  const overheadPence = vehicleFixedCostPerDayPence;
  const totalCostPence = fuelCostPence + labourCostPence + overheadPence;

  return {
    fuelLitres,
    drivingHours,
    serviceHours,
    loadingHours,
    totalHours,
    fuelCostPence,
    labourCostPence,
    overheadPence,
    totalCostPence,
  };
}

/** Average cost per stop. Misleading when stops vary in detour cost; pair with marginal. */
export function averageCostPerStop(route: RouteCost, numStops: number): number {
  return safeDiv(route.totalCostPence, numStops, 0);
}

/**
 * Allocate the route's costs to a single stop, given the leg km and minutes
 * to that stop and the totals for the route. Used to populate
 * route_stops.planned_*_share_pence.
 *
 *   - fuel and labour are allocated proportionally to leg km / leg time
 *   - overhead is split evenly across stops
 *
 * The shares for all stops on a route should sum (within rounding) to the
 * route totals.
 */
export function allocateStopShare(args: {
  legKm: number;
  legMin: number;
  serviceMin: number;
  totalRouteKm: number;
  totalRouteMin: number;
  numStops: number;
  route: RouteCost;
}): StopCostShare {
  const { legKm, legMin, serviceMin, totalRouteKm, totalRouteMin, numStops, route } = args;

  const fuelShare = round(safeDiv(legKm, totalRouteKm, 0) * route.fuelCostPence);
  // Time-share = leg drive time + this stop's service time, divided by total route minutes.
  const labourShare = round(
    safeDiv(legMin + serviceMin, totalRouteMin, 0) * route.labourCostPence,
  );
  const overheadShare = numStops > 0 ? Math.floor(route.overheadPence / numStops) : 0;
  const direct = fuelShare + labourShare + overheadShare;

  return {
    fuelSharePence: fuelShare,
    labourSharePence: labourShare,
    overheadSharePence: overheadShare,
    directCostPence: direct,
  };
}

/**
 * Marginal cost = cost_with − cost_without. Caller must supply the two
 * already-computed route costs (typically obtained by calling the optimiser
 * once with the stop included and once without).
 */
export function marginalCostPence(withStop: RouteCost, withoutStop: RouteCost): number {
  return withStop.totalCostPence - withoutStop.totalCostPence;
}

/**
 * Net contribution = gross profit − marginal cost.
 * Negative numbers identify customers being served at a loss after delivery cost.
 */
export function netContributionPence(args: {
  orderValuePence: number;
  grossMarginPct: number; // 0..1
  marginalCostPence: number;
}): { grossProfitPence: number; netContributionPence: number } {
  const grossProfit = round(args.orderValuePence * args.grossMarginPct);
  return {
    grossProfitPence: grossProfit,
    netContributionPence: grossProfit - args.marginalCostPence,
  };
}

// ---------- formatting helpers (UI use) ----------

export const pence = {
  toGbpString(p: number, opts: { digits?: number } = {}): string {
    const digits = opts.digits ?? 2;
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: "GBP",
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(p / 100);
  },
  toGbpRounded(p: number): string {
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: "GBP",
      maximumFractionDigits: 0,
    }).format(p / 100);
  },
};
