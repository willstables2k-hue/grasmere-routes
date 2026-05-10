"""
Marginal cost = leave-one-out re-solve of a single route.

Rather than re-optimising globally, we strip the excluded stop from the
provided route and re-sequence the remainder via nearest-neighbour from
the depot. This is much faster than a full TSP and gives a tight upper
bound on the true marginal cost — good enough for the UI's "what is this
customer costing me" answer.
"""

from __future__ import annotations

from .baseline import _nearest_neighbour_sequence
from .cost_model import CostParams, compute_route_cost
from .matrix import LatLng, driving_matrix
from .schemas import (
    MarginalCostRequest,
    MarginalCostResponse,
)


async def marginal_cost(req: MarginalCostRequest) -> MarginalCostResponse:
    # The route DTO doesn't carry coordinates, only IDs. The web caller
    # supplies stops via an extra field on the route. We pull lat/lng from
    # the request body's `stops_for_route` map (set by the API route handler).
    extra: dict = req.model_dump().get("__pydantic_extra__") or {}
    stops_map: dict[str, dict] = extra.get("stops_for_route", {})

    if req.excluded_stop_id not in req.route.stop_sequence:
        return MarginalCostResponse(
            cost_with_pence=req.route.total_cost_pence,
            cost_without_pence=req.route.total_cost_pence,
            marginal_cost_pence=0,
        )

    remaining_ids = [s for s in req.route.stop_sequence if s != req.excluded_stop_id]
    if not stops_map:
        # Without coordinates we can only return zero — caller must include them.
        return MarginalCostResponse(
            cost_with_pence=req.route.total_cost_pence,
            cost_without_pence=req.route.total_cost_pence,
            marginal_cost_pence=0,
        )

    points: list[LatLng] = [LatLng(req.depot.lat, req.depot.lng)] + [
        LatLng(stops_map[i]["lat"], stops_map[i]["lng"]) for i in remaining_ids
    ]
    matrix = await driving_matrix(points)
    seq = _nearest_neighbour_sequence(0, list(range(1, len(points))), matrix.distance_m)

    trip = [0] + seq + [0]
    total_km = sum(matrix.distance_m[a][b] for a, b in zip(trip[:-1], trip[1:])) / 1000.0
    cp = req.cost_params
    params = CostParams(
        diesel_price_pence_per_litre=cp.diesel_price_pence_per_litre,
        vehicle_mpg=cp.vehicle_mpg,
        driver_hourly_rate_pence=cp.driver_hourly_rate_pence,
        avg_speed_kmh=cp.avg_speed_kmh,
        service_min_per_stop=cp.service_min_per_stop,
        depot_loading_min=cp.depot_loading_min,
        vehicle_fixed_cost_per_day_pence=cp.vehicle_fixed_cost_per_day_pence,
    )
    without = compute_route_cost(
        distance_km=total_km, num_stops=len(remaining_ids), params=params
    )
    return MarginalCostResponse(
        cost_with_pence=req.route.total_cost_pence,
        cost_without_pence=without.total_cost_pence,
        marginal_cost_pence=req.route.total_cost_pence - without.total_cost_pence,
    )
