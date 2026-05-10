"""
Cost-minimising VRP solver using Google OR-Tools.

Objective is the platform's actual £ cost (fuel + labour) — NOT raw
distance — so the solver makes the same trade-offs the dispatcher would.

  per-arc cost = fuel_cost(km) + labour_cost(km / speed)
  per-vehicle  = vehicle_fixed_cost_per_day  (paid only if the vehicle is used)
  capacity     = kg AND crates  (two parallel dimensions)
  time         = driving + service  (per-stop service time included)
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from .cost_model import (
    KM_PER_MILE,
    UK_GALLON_L,
    CostParams,
    compute_route_cost,
)
from .matrix import LatLng, MatrixResult, driving_matrix
from .schemas import (
    OptimiseRequest,
    OptimiseResponse,
    RouteResult,
)

OPTIMISER_VERSION = "ortools-cost-minimising-v1"


def _per_km_pence(diesel_pence: int, mpg: float) -> float:
    """Pence per km for a given mpg + diesel price (imperial gallon)."""
    # litres per km = (1 / mpg) imp gallons per mile × 4.546 L/gal × 1/1.609344 mi/km
    l_per_km = (UK_GALLON_L / mpg) / KM_PER_MILE
    return l_per_km * diesel_pence


def _per_min_pence(hourly_pence: int) -> float:
    return hourly_pence / 60.0


@dataclass
class _Solved:
    routes: list[RouteResult]
    unassigned: list[str]
    objective_pence: int


def _solve(req: OptimiseRequest, matrix: MatrixResult) -> _Solved:
    n_stops = len(req.stops)
    n_nodes = n_stops + 1  # depot at index 0
    n_vehicles = len(req.vehicles)
    if n_stops == 0:
        return _Solved(routes=[], unassigned=[], objective_pence=0)

    manager = pywrapcp.RoutingIndexManager(n_nodes, n_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    # ----- per-vehicle cost callbacks -----
    arc_cost_callbacks: list[int] = []
    for v_idx, veh in enumerate(req.vehicles):
        per_km = _per_km_pence(veh.diesel_price_pence_per_litre, veh.mpg)
        per_min = _per_min_pence(veh.labour_cost_per_hour_pence)

        def make_arc_cost(per_km: float, per_min: float):
            def arc_cost(from_index: int, to_index: int) -> int:
                f = manager.IndexToNode(from_index)
                t = manager.IndexToNode(to_index)
                km = matrix.distance_m[f][t] / 1000.0
                drive_min = matrix.duration_s[f][t] / 60.0
                # Cost is per-arc only (service time costs handled by time dimension).
                return int(round(km * per_km + drive_min * per_min))

            return arc_cost

        cb_idx = routing.RegisterTransitCallback(make_arc_cost(per_km, per_min))
        routing.SetArcCostEvaluatorOfVehicle(cb_idx, v_idx)
        arc_cost_callbacks.append(cb_idx)

    # ----- fixed cost per vehicle (only if used) -----
    for v_idx, veh in enumerate(req.vehicles):
        routing.SetFixedCostOfVehicle(int(veh.overhead_pence), v_idx)

    # ----- capacity dimensions -----
    weights = [0] + [int(round(s.weight_kg)) for s in req.stops]
    crates = [0] + [int(s.crate_count) for s in req.stops]

    def weight_demand(idx: int) -> int:
        return weights[manager.IndexToNode(idx)]

    def crate_demand(idx: int) -> int:
        return crates[manager.IndexToNode(idx)]

    weight_cb = routing.RegisterUnaryTransitCallback(weight_demand)
    routing.AddDimensionWithVehicleCapacity(
        weight_cb,
        0,
        [int(round(v.capacity_kg)) for v in req.vehicles],
        True,
        "Weight",
    )
    crate_cb = routing.RegisterUnaryTransitCallback(crate_demand)
    routing.AddDimensionWithVehicleCapacity(
        crate_cb,
        0,
        [v.capacity_crates for v in req.vehicles],
        True,
        "Crates",
    )

    # ----- time dimension (drive + service) -----
    service_minutes = [0] + [s.service_minutes or req.service_time_minutes_default for s in req.stops]
    depot_loading = req.depot_loading_minutes

    def time_callback(from_index: int, to_index: int) -> int:
        f = manager.IndexToNode(from_index)
        t = manager.IndexToNode(to_index)
        drive_min = int(round(matrix.duration_s[f][t] / 60.0))
        # Service time is paid on departing the from-node.
        # Depot loading paid as the first leg out of node 0.
        srv = service_minutes[f] + (depot_loading if f == 0 else 0)
        return drive_min + srv

    time_cb = routing.RegisterTransitCallback(time_callback)
    routing.AddDimension(
        time_cb,
        0,
        max(v.shift_minutes for v in req.vehicles),
        True,
        "Time",
    )

    # ----- allow dropping stops as a last resort (very expensive penalty) -----
    drop_penalty = 100_000_000
    for i in range(1, n_nodes):
        routing.AddDisjunction([manager.NodeToIndex(i)], drop_penalty)

    # ----- search params -----
    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.seconds = 8
    search_params.log_search = False

    solution = routing.SolveWithParameters(search_params)
    if solution is None:
        return _Solved(routes=[], unassigned=[s.id for s in req.stops], objective_pence=0)

    routes: list[RouteResult] = []
    assigned: set[int] = set()
    for v_idx, veh in enumerate(req.vehicles):
        index = routing.Start(v_idx)
        seq_indices: list[int] = []
        leg_km: list[float] = []
        leg_min: list[int] = []
        prev_node: int | None = None
        total_dist_m = 0
        total_drive_s = 0
        total_srv_min = 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                seq_indices.append(node)
                assigned.add(node)
                total_srv_min += service_minutes[node]
            if prev_node is not None:
                d = matrix.distance_m[prev_node][node]
                t = matrix.duration_s[prev_node][node]
                total_dist_m += d
                total_drive_s += t
                leg_km.append(round(d / 1000.0, 3))
                leg_min.append(int(round(t / 60.0)))
            prev_node = node
            index = solution.Value(routing.NextVar(index))
        # final leg back to depot
        node = manager.IndexToNode(index)  # 0
        if prev_node is not None:
            d = matrix.distance_m[prev_node][node]
            t = matrix.duration_s[prev_node][node]
            total_dist_m += d
            total_drive_s += t
            leg_km.append(round(d / 1000.0, 3))
            leg_min.append(int(round(t / 60.0)))

        if not seq_indices:
            continue  # vehicle unused

        total_km = total_dist_m / 1000.0
        # Use the shared cost model so the figures match what the UI displays.
        params = CostParams(
            diesel_price_pence_per_litre=veh.diesel_price_pence_per_litre,
            vehicle_mpg=veh.mpg,
            driver_hourly_rate_pence=veh.labour_cost_per_hour_pence,
            avg_speed_kmh=req.avg_speed_kmh,
            service_min_per_stop=req.service_time_minutes_default,
            depot_loading_min=req.depot_loading_minutes,
            vehicle_fixed_cost_per_day_pence=veh.overhead_pence,
        )
        cost = compute_route_cost(
            distance_km=total_km, num_stops=len(seq_indices), params=params
        )
        routes.append(
            RouteResult(
                vehicle_id=veh.id,
                stop_sequence=[req.stops[i - 1].id for i in seq_indices],
                total_distance_km=round(total_km, 2),
                total_duration_min=int(round(total_drive_s / 60.0)) + total_srv_min + req.depot_loading_minutes,
                fuel_cost_pence=cost.fuel_cost_pence,
                labour_cost_pence=cost.labour_cost_pence,
                overhead_pence=cost.overhead_pence,
                total_cost_pence=cost.total_cost_pence,
                leg_distances_km=leg_km,
                leg_durations_min=leg_min,
            )
        )

    unassigned_idx = set(range(1, n_nodes)) - assigned
    unassigned = [req.stops[i - 1].id for i in sorted(unassigned_idx)]
    objective = sum(r.total_cost_pence for r in routes)
    return _Solved(routes=routes, unassigned=unassigned, objective_pence=objective)


async def optimise(req: OptimiseRequest) -> OptimiseResponse:
    started = time.perf_counter()
    points = [LatLng(req.depot.lat, req.depot.lng)] + [
        LatLng(s.lat, s.lng) for s in req.stops
    ]
    matrix = await driving_matrix(points)
    solved = _solve(req, matrix)
    return OptimiseResponse(
        status="ok" if not solved.unassigned else "infeasible",
        routes=solved.routes,
        unassigned_stops=solved.unassigned,
        objective_value_pence=solved.objective_pence,
        solve_seconds=round(time.perf_counter() - started, 3),
        optimiser_version=OPTIMISER_VERSION,
    )
