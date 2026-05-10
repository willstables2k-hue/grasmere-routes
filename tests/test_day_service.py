"""Smoke tests for day_service.

End-to-end DB-backed tests need a live Postgres; they live in a separate
manual smoke (run by the user against Supabase). What we validate here:

  - The DayResult dataclass shape and zero-state behaviour.
  - vehicle_for_optimised / vehicle_for_original lookups work.
"""

from __future__ import annotations

from datetime import date

from grasmere_routes.day_service import DayResult, Delivery, RouteSummary


def test_day_result_zero_state():
    r = DayResult(
        date=date(2026, 4, 30),
        deliveries=[],
        optimised_routes=[],
        original_routes=[],
        optimised_total_pence=0,
        original_total_pence=0,
        saving_pence=0,
        saving_pct=0.0,
        excluded=[],
    )
    assert r.vehicle_for_optimised("nope") is None
    assert r.vehicle_for_original("nope") is None


def test_vehicle_lookup_round_trip():
    optimised = RouteSummary(
        vehicle_id="v1",
        label="v1",
        stop_sequence=["o1", "o2"],
        total_distance_km=10.0,
        total_duration_min=60,
        fuel_cost_pence=200,
        labour_cost_pence=1600,
        overhead_pence=2500,
        total_cost_pence=4300,
    )
    original = RouteSummary(
        vehicle_id="Pink",
        label="Pink (legacy)",
        stop_sequence=["o1", "o2"],
        total_distance_km=15.0,
        total_duration_min=80,
        fuel_cost_pence=300,
        labour_cost_pence=2100,
        overhead_pence=2500,
        total_cost_pence=4900,
    )
    r = DayResult(
        date=date(2026, 4, 30),
        deliveries=[
            Delivery("o1", "c1", "ABC", "A", "1", 10000, "WP0", 52.7, -0.4),
            Delivery("o2", "c2", "DEF", "B", "2", 5000, "WP0", 52.6, -0.5),
        ],
        optimised_routes=[optimised],
        original_routes=[original],
        optimised_total_pence=4300,
        original_total_pence=4900,
        saving_pence=600,
        saving_pct=0.122,
        excluded=[],
    )
    assert r.vehicle_for_optimised("o1") == "v1"
    assert r.vehicle_for_optimised("o2") == "v1"
    assert r.vehicle_for_original("o1") == "Pink"
    assert r.vehicle_for_original("missing") is None
