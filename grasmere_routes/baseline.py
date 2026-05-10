"""
Baseline reconstruction: nearest-neighbour from depot for each (van, day).

This is INTENTIONALLY simple — it represents the status-quo cost we are
measuring against. The CSV's `delivery_run_position` is loading-bay zone
information, not true drive sequence, so we fall back to nearest-neighbour
which approximates how a driver who knows their territory would actually
drive it. This assumption is surfaced in the /baseline UI's caveats panel.
"""

from __future__ import annotations

from .cost_model import CostParams, compute_route_cost
from .matrix import LatLng, driving_matrix
from .schemas import (
    BaselineRequest,
    BaselineResponse,
    BaselineRouteResult,
    BaselineRouteSpec,
    CostParamsModel,
)


def _nearest_neighbour_sequence(
    depot_idx: int, stop_indices: list[int], dist: list[list[int]]
) -> list[int]:
    remaining = list(stop_indices)
    seq: list[int] = []
    current = depot_idx
    while remaining:
        nxt = min(remaining, key=lambda j: dist[current][j])
        seq.append(nxt)
        remaining.remove(nxt)
        current = nxt
    return seq


async def reconstruct_baseline(req: BaselineRequest) -> BaselineResponse:
    if not req.baseline_routes:
        return BaselineResponse(
            baseline_routes=[],
            summary={
                "total_distance_km": 0,
                "total_cost_pence": 0,
                "total_stops": 0,
                "weekly_cost_pence": 0,
                "annualised_cost_pence": 0,
            },
        )

    # Single matrix call across all unique points in this snapshot
    all_points: list[LatLng] = [LatLng(req.depot.lat, req.depot.lng)]
    point_index_by_stop: dict[str, int] = {}
    for br in req.baseline_routes:
        for s in br.stops:
            if s.id not in point_index_by_stop:
                point_index_by_stop[s.id] = len(all_points)
                all_points.append(LatLng(s.lat, s.lng))

    matrix = await driving_matrix(all_points)

    cost_params = req.cost_params or CostParamsModel()
    params = CostParams(
        diesel_price_pence_per_litre=cost_params.diesel_price_pence_per_litre,
        vehicle_mpg=cost_params.vehicle_mpg,
        driver_hourly_rate_pence=cost_params.driver_hourly_rate_pence,
        avg_speed_kmh=cost_params.avg_speed_kmh,
        service_min_per_stop=cost_params.service_min_per_stop,
        depot_loading_min=cost_params.depot_loading_min,
        vehicle_fixed_cost_per_day_pence=cost_params.vehicle_fixed_cost_per_day_pence,
    )

    out_routes: list[BaselineRouteResult] = []
    total_dist = 0.0
    total_cost = 0
    total_stops = 0

    for br in req.baseline_routes:
        if not br.stops:
            continue
        stop_idx_list = [point_index_by_stop[s.id] for s in br.stops]
        seq = _nearest_neighbour_sequence(0, stop_idx_list, matrix.distance_m)
        # Build the trip: depot -> seq[0] -> seq[1] -> ... -> depot
        trip = [0] + seq + [0]
        leg_km: list[float] = []
        leg_min: list[int] = []
        total_km = 0.0
        total_drive_min = 0
        for a, b in zip(trip[:-1], trip[1:]):
            d_m = matrix.distance_m[a][b]
            t_s = matrix.duration_s[a][b]
            total_km += d_m / 1000.0
            total_drive_min += int(round(t_s / 60.0))
            leg_km.append(round(d_m / 1000.0, 3))
            leg_min.append(int(round(t_s / 60.0)))

        cost = compute_route_cost(
            distance_km=total_km, num_stops=len(seq), params=params
        )

        # Map index back to stop id (we walk seq in matrix-index order)
        idx_to_id = {point_index_by_stop[s.id]: s.id for s in br.stops}
        stop_sequence_ids = [idx_to_id[i] for i in seq]

        out_routes.append(
            BaselineRouteResult(
                van_colour=br.van_colour,
                day_of_week=br.day_of_week,
                stop_sequence=stop_sequence_ids,
                total_distance_km=round(total_km, 2),
                total_duration_min=total_drive_min
                + len(seq) * cost_params.service_min_per_stop
                + cost_params.depot_loading_min,
                fuel_cost_pence=cost.fuel_cost_pence,
                labour_cost_pence=cost.labour_cost_pence,
                overhead_pence=cost.overhead_pence,
                total_cost_pence=cost.total_cost_pence,
                leg_distances_km=leg_km,
                leg_durations_min=leg_min,
            )
        )
        total_dist += total_km
        total_cost += cost.total_cost_pence
        total_stops += len(seq)

    return BaselineResponse(
        baseline_routes=out_routes,
        summary={
            "total_distance_km": round(total_dist, 2),
            "total_cost_pence": total_cost,
            "total_stops": total_stops,
            "weekly_cost_pence": total_cost,
            "annualised_cost_pence": total_cost * 52,
        },
    )
