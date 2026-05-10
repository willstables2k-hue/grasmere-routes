"""
Cost-model tests — uses the SAME fixture cases as
apps/web/lib/cost-model.test.ts. The fixtures are duplicated here as a
literal Python list rather than auto-parsed from TS to keep the test
hermetic, but every numeric value MUST match the TS file exactly.

If you change SPEC_DEFAULTS or ROUTE_CASES in the TS fixtures, you must
make the same change here. Both suites then prove the change is
internally consistent.
"""

from __future__ import annotations

import pytest

from app.cost_model import (
    KM_PER_MILE,
    UK_GALLON_L,
    CostParams,
    allocate_stop_share,
    average_cost_per_stop,
    compute_route_cost,
    marginal_cost_pence,
    net_contribution_pence,
)

# Mirror of cost-model.fixtures.ts SPEC_DEFAULTS
SPEC_DEFAULTS = CostParams(
    diesel_price_pence_per_litre=188,
    vehicle_mpg=25,
    driver_hourly_rate_pence=1600,
    avg_speed_kmh=50,
    service_min_per_stop=8,
    depot_loading_min=30,
    vehicle_fixed_cost_per_day_pence=2500,
)

# Mirror of ROUTE_CASES
ROUTE_CASES = [
    {
        "name": "single short urban route, 5 stops, 30 km",
        "distance_km": 30,
        "num_stops": 5,
        "expected": {
            "fuel_cost_pence": 637,
            "labour_cost_pence": 2827,
            "overhead_pence": 2500,
            "total_cost_pence": 637 + 2827 + 2500,
        },
    },
    {
        "name": "long rural route, 25 stops, 180 km",
        "distance_km": 180,
        "num_stops": 25,
        "expected": {
            "fuel_cost_pence": 3824,
            "labour_cost_pence": 11893,
            "overhead_pence": 2500,
            "total_cost_pence": 3824 + 11893 + 2500,
        },
    },
    {
        "name": "edge: zero stops (cancelled day, still loaded out)",
        "distance_km": 0,
        "num_stops": 0,
        "expected": {
            "fuel_cost_pence": 0,
            "labour_cost_pence": 800,
            "overhead_pence": 2500,
            "total_cost_pence": 3300,
        },
    },
    {
        "name": "edge: single stop nearby",
        "distance_km": 4,
        "num_stops": 1,
        "expected": {
            "fuel_cost_pence": 85,
            "labour_cost_pence": 1141,
            "overhead_pence": 2500,
            "total_cost_pence": 85 + 1141 + 2500,
        },
    },
]


def test_constants_use_imperial_uk_gallon() -> None:
    assert UK_GALLON_L == 4.546
    assert abs(KM_PER_MILE - 1.609344) < 1e-9


@pytest.mark.parametrize("case", ROUTE_CASES, ids=lambda c: c["name"])
def test_compute_route_cost_matches_shared_fixtures(case: dict) -> None:
    out = compute_route_cost(
        distance_km=case["distance_km"],
        num_stops=case["num_stops"],
        params=SPEC_DEFAULTS,
    )
    e = case["expected"]
    assert out.fuel_cost_pence == e["fuel_cost_pence"], "fuel mismatch"
    assert out.labour_cost_pence == e["labour_cost_pence"], "labour mismatch"
    assert out.overhead_pence == e["overhead_pence"], "overhead mismatch"
    assert out.total_cost_pence == e["total_cost_pence"], "total mismatch"


def test_compute_route_cost_guards() -> None:
    bad_mpg = CostParams(**{**SPEC_DEFAULTS.__dict__, "vehicle_mpg": 0})
    with pytest.raises(ValueError):
        compute_route_cost(distance_km=10, num_stops=1, params=bad_mpg)

    bad_speed = CostParams(**{**SPEC_DEFAULTS.__dict__, "avg_speed_kmh": 0})
    with pytest.raises(ValueError):
        compute_route_cost(distance_km=10, num_stops=1, params=bad_speed)


def test_average_cost_per_stop() -> None:
    r = compute_route_cost(distance_km=0, num_stops=0, params=SPEC_DEFAULTS)
    assert average_cost_per_stop(r, 0) == 0.0
    r2 = compute_route_cost(distance_km=30, num_stops=5, params=SPEC_DEFAULTS)
    assert abs(average_cost_per_stop(r2, 5) - r2.total_cost_pence / 5) < 1e-6


def test_allocate_stop_share_recomposes_within_tolerance() -> None:
    route = compute_route_cost(distance_km=60, num_stops=4, params=SPEC_DEFAULTS)
    total_route_min = (route.driving_hours + route.service_hours + route.loading_hours) * 60
    legs = [(15, 18)] * 4
    shares = [
        allocate_stop_share(
            leg_km=lk,
            leg_min=lm,
            service_min=SPEC_DEFAULTS.service_min_per_stop,
            total_route_km=60,
            total_route_min=total_route_min,
            num_stops=4,
            route=route,
        )
        for (lk, lm) in legs
    ]
    sum_fuel = sum(s.fuel_share_pence for s in shares)
    sum_labour = sum(s.labour_share_pence for s in shares)
    sum_overhead = sum(s.overhead_share_pence for s in shares)

    assert abs(sum_fuel - route.fuel_cost_pence) <= 2
    assert 0 < sum_labour <= route.labour_cost_pence  # loading time excluded by design
    assert sum_overhead <= route.overhead_pence


def test_marginal_cost() -> None:
    with_stop = compute_route_cost(distance_km=50, num_stops=5, params=SPEC_DEFAULTS)
    without_stop = compute_route_cost(distance_km=38, num_stops=4, params=SPEC_DEFAULTS)
    assert marginal_cost_pence(with_stop, without_stop) == (
        with_stop.total_cost_pence - without_stop.total_cost_pence
    )


def test_net_contribution() -> None:
    gp, nc = net_contribution_pence(
        order_value_pence=30000, gross_margin_pct=0.28, marginal_cost_pence_=500
    )
    assert gp == 8400
    assert nc == 7900

    gp2, nc2 = net_contribution_pence(
        order_value_pence=5000, gross_margin_pct=0.28, marginal_cost_pence_=2500
    )
    assert gp2 == 1400
    assert nc2 == -1100
