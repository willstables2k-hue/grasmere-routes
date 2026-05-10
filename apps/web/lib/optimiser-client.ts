/**
 * Server-side client for the Python optimiser microservice.
 * Use in Next.js API routes / server components only — never expose
 * OPTIMISER_API_KEY to the browser.
 */

const OPTIMISER_URL = process.env.OPTIMISER_URL ?? "http://localhost:8000";
const OPTIMISER_API_KEY = process.env.OPTIMISER_API_KEY ?? "";

async function call<TReq, TRes>(path: string, body: TReq): Promise<TRes> {
  const res = await fetch(`${OPTIMISER_URL}${path}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(OPTIMISER_API_KEY ? { "x-api-key": OPTIMISER_API_KEY } : {}),
    },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`optimiser ${path} → ${res.status}: ${txt}`);
  }
  return (await res.json()) as TRes;
}

// ---------- payload types (mirror schemas.py) ----------

export interface OptimiseRequest {
  depot: { lat: number; lng: number };
  delivery_date: string;
  vehicles: VehicleSpec[];
  stops: StopSpec[];
  service_time_minutes_default?: number;
  depot_loading_minutes?: number;
  avg_speed_kmh?: number;
}

export interface VehicleSpec {
  id: string;
  capacity_kg?: number;
  capacity_crates?: number;
  shift_minutes?: number;
  mpg?: number;
  diesel_price_pence_per_litre?: number;
  labour_cost_per_hour_pence?: number;
  overhead_pence?: number;
}

export interface StopSpec {
  id: string;
  lat: number;
  lng: number;
  weight_kg?: number;
  crate_count?: number;
  service_minutes?: number;
}

export interface RouteResult {
  vehicle_id: string;
  stop_sequence: string[];
  total_distance_km: number;
  total_duration_min: number;
  fuel_cost_pence: number;
  labour_cost_pence: number;
  overhead_pence: number;
  total_cost_pence: number;
  leg_distances_km: number[];
  leg_durations_min: number[];
}

export interface OptimiseResponse {
  status: "ok" | "infeasible";
  routes: RouteResult[];
  unassigned_stops: string[];
  objective_value_pence: number;
  solve_seconds: number;
  optimiser_version: string;
}

export interface BaselineRequest {
  depot: { lat: number; lng: number };
  baseline_routes: {
    van_colour: string;
    day_of_week: number;
    stops: StopSpec[];
  }[];
  cost_params?: Partial<{
    diesel_price_pence_per_litre: number;
    vehicle_mpg: number;
    driver_hourly_rate_pence: number;
    avg_speed_kmh: number;
    service_min_per_stop: number;
    depot_loading_min: number;
    vehicle_fixed_cost_per_day_pence: number;
  }>;
}

export interface BaselineResponse {
  baseline_routes: (RouteResult & { van_colour: string; day_of_week: number })[];
  summary: {
    total_distance_km: number;
    total_cost_pence: number;
    total_stops: number;
    weekly_cost_pence: number;
    annualised_cost_pence: number;
  };
}

export interface MarginalCostRequest {
  depot: { lat: number; lng: number };
  route: RouteResult;
  excluded_stop_id: string;
  stops_for_route: Record<string, { lat: number; lng: number }>;
  cost_params?: BaselineRequest["cost_params"];
}

export interface MarginalCostResponse {
  cost_with_pence: number;
  cost_without_pence: number;
  marginal_cost_pence: number;
}

// ---------- public API ----------

export const optimiser = {
  optimise: (req: OptimiseRequest) =>
    call<OptimiseRequest, OptimiseResponse>("/optimise", req),
  baselineCost: (req: BaselineRequest) =>
    call<BaselineRequest, BaselineResponse>("/baseline_cost", req),
  marginalCost: (req: MarginalCostRequest) =>
    call<MarginalCostRequest, MarginalCostResponse>("/marginal_cost", req),
};
