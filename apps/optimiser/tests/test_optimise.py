"""End-to-end optimiser tests using the haversine fallback (no Mapbox token)."""

from __future__ import annotations

import pytest

from app.baseline import reconstruct_baseline
from app.optimise import optimise
from app.schemas import (
    BaselineRequest,
    BaselineRouteSpec,
    LatLngModel,
    OptimiseRequest,
    StopSpec,
    VehicleSpec,
)

DEPOT = LatLngModel(lat=52.7691, lng=-0.3819)  # Grasmere Farm, Bourne


def _stops(coords: list[tuple[float, float]]) -> list[StopSpec]:
    return [
        StopSpec(id=f"s{i}", lat=lat, lng=lng, weight_kg=20, crate_count=1, service_minutes=8)
        for i, (lat, lng) in enumerate(coords)
    ]


@pytest.mark.asyncio
async def test_optimise_assigns_all_stops() -> None:
    req = OptimiseRequest(
        depot=DEPOT,
        delivery_date="2026-05-12",
        vehicles=[VehicleSpec(id="v1"), VehicleSpec(id="v2")],
        stops=_stops(
            [
                (52.6730, -0.4823),  # Stamford
                (52.5707, -0.2480),  # Peterborough
                (52.6307, -1.1397),  # Leicester
                (52.5300, -1.2500),  # Hinckley
                (52.9540, -1.1550),  # Nottingham
            ]
        ),
    )
    out = await optimise(req)
    assert out.status == "ok"
    assert out.unassigned_stops == []
    assigned = sum(len(r.stop_sequence) for r in out.routes)
    assert assigned == 5
    # at least one of the two vehicles should run
    assert any(len(r.stop_sequence) > 0 for r in out.routes)


@pytest.mark.asyncio
async def test_optimise_respects_capacity() -> None:
    # 5 stops × 300 kg = 1500 kg → won't fit one 1200 kg van, must split
    heavy_stops = [
        StopSpec(id=f"h{i}", lat=lat, lng=lng, weight_kg=300, crate_count=20)
        for i, (lat, lng) in enumerate(
            [
                (52.6730, -0.4823),
                (52.5707, -0.2480),
                (52.6307, -1.1397),
                (52.5300, -1.2500),
                (52.9540, -1.1550),
            ]
        )
    ]
    req = OptimiseRequest(
        depot=DEPOT,
        delivery_date="2026-05-12",
        vehicles=[VehicleSpec(id="v1"), VehicleSpec(id="v2")],
        stops=heavy_stops,
    )
    out = await optimise(req)
    assert out.status == "ok"
    used_routes = [r for r in out.routes if r.stop_sequence]
    assert len(used_routes) >= 2, "capacity should have forced both vehicles"


@pytest.mark.asyncio
async def test_baseline_nearest_neighbour_basic() -> None:
    req = BaselineRequest(
        depot=DEPOT,
        baseline_routes=[
            BaselineRouteSpec(
                van_colour="Green",
                day_of_week=1,
                stops=_stops(
                    [
                        (52.6730, -0.4823),
                        (52.5707, -0.2480),
                        (52.6307, -1.1397),
                    ]
                ),
            )
        ],
    )
    out = await reconstruct_baseline(req)
    assert len(out.baseline_routes) == 1
    r = out.baseline_routes[0]
    assert len(r.stop_sequence) == 3
    assert r.total_cost_pence > 0
    assert r.fuel_cost_pence + r.labour_cost_pence + r.overhead_pence == r.total_cost_pence
    # summary annualised = weekly × 52
    assert out.summary["annualised_cost_pence"] == r.total_cost_pence * 52
