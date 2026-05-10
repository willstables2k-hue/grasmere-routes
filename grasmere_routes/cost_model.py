"""
Python mirror of apps/web/lib/cost-model.ts.

This module produces identical penny-level results to the TypeScript
cost model. The shared test suite (tests/test_cost_model.py) loads the
*same* fixture cases as the Vitest suite to guarantee they cannot drift.

Money is integer PENCE everywhere. Floats are used only for intermediate
physics before rounding.

Imperial gallon (4.546 L), NOT US (3.785 L) — hard-coded constant.
"""

from __future__ import annotations

from dataclasses import dataclass

# --- physical constants (do not move to config) ---
KM_PER_MILE = 1.609344
UK_GALLON_L = 4.546


@dataclass(frozen=True)
class CostParams:
    diesel_price_pence_per_litre: int
    vehicle_mpg: float
    driver_hourly_rate_pence: int
    avg_speed_kmh: float
    service_min_per_stop: int
    depot_loading_min: int
    vehicle_fixed_cost_per_day_pence: int


@dataclass(frozen=True)
class RouteCost:
    fuel_litres: float
    driving_hours: float
    service_hours: float
    loading_hours: float
    total_hours: float
    fuel_cost_pence: int
    labour_cost_pence: int
    overhead_pence: int
    total_cost_pence: int


@dataclass(frozen=True)
class StopCostShare:
    fuel_share_pence: int
    labour_share_pence: int
    overhead_share_pence: int
    direct_cost_pence: int


def _round_half_to_even(x: float) -> int:
    """Match JavaScript's Math.round semantics for non-negative values.

    Math.round rounds half AWAY from zero (e.g. 2.5 → 3, -2.5 → -2).
    Python's round() is banker's rounding. For our pence values which are
    always positive, we explicitly use the "half up" rule to match JS.
    """
    if x >= 0:
        return int(x + 0.5)
    return -int(-x + 0.5)


def _safe_div(num: float, den: float, fallback: float = 0.0) -> float:
    return fallback if den == 0 else num / den


def compute_route_cost(*, distance_km: float, num_stops: int, params: CostParams) -> RouteCost:
    """Cost of a single route given total km and stop count."""
    if params.vehicle_mpg <= 0:
        raise ValueError("vehicle_mpg must be > 0")
    if params.avg_speed_kmh <= 0:
        raise ValueError("avg_speed_kmh must be > 0")

    fuel_litres = (
        0.0
        if distance_km <= 0
        else (distance_km / KM_PER_MILE / params.vehicle_mpg) * UK_GALLON_L
    )
    fuel_cost_pence = _round_half_to_even(fuel_litres * params.diesel_price_pence_per_litre)

    driving_hours = distance_km / params.avg_speed_kmh
    service_hours = (num_stops * params.service_min_per_stop) / 60
    loading_hours = params.depot_loading_min / 60
    total_hours = driving_hours + service_hours + loading_hours
    labour_cost_pence = _round_half_to_even(total_hours * params.driver_hourly_rate_pence)

    overhead_pence = params.vehicle_fixed_cost_per_day_pence
    total_cost_pence = fuel_cost_pence + labour_cost_pence + overhead_pence

    return RouteCost(
        fuel_litres=fuel_litres,
        driving_hours=driving_hours,
        service_hours=service_hours,
        loading_hours=loading_hours,
        total_hours=total_hours,
        fuel_cost_pence=fuel_cost_pence,
        labour_cost_pence=labour_cost_pence,
        overhead_pence=overhead_pence,
        total_cost_pence=total_cost_pence,
    )


def average_cost_per_stop(route: RouteCost, num_stops: int) -> float:
    return _safe_div(route.total_cost_pence, num_stops, 0.0)


def allocate_stop_share(
    *,
    leg_km: float,
    leg_min: float,
    service_min: float,
    total_route_km: float,
    total_route_min: float,
    num_stops: int,
    route: RouteCost,
) -> StopCostShare:
    fuel_share = _round_half_to_even(_safe_div(leg_km, total_route_km) * route.fuel_cost_pence)
    labour_share = _round_half_to_even(
        _safe_div(leg_min + service_min, total_route_min) * route.labour_cost_pence
    )
    overhead_share = route.overhead_pence // num_stops if num_stops > 0 else 0
    direct = fuel_share + labour_share + overhead_share
    return StopCostShare(
        fuel_share_pence=fuel_share,
        labour_share_pence=labour_share,
        overhead_share_pence=overhead_share,
        direct_cost_pence=direct,
    )


def marginal_cost_pence(with_stop: RouteCost, without_stop: RouteCost) -> int:
    return with_stop.total_cost_pence - without_stop.total_cost_pence


def net_contribution_pence(
    *, order_value_pence: int, gross_margin_pct: float, marginal_cost_pence_: int
) -> tuple[int, int]:
    gross_profit = _round_half_to_even(order_value_pence * gross_margin_pct)
    return gross_profit, gross_profit - marginal_cost_pence_
