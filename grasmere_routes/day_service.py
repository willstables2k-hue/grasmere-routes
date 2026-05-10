"""Day orchestrator — single entry point for both pages.

  load_or_compute_day(date)        — read orders for the date from DB (which
                                     have been imported via Fresho file), call
                                     OR-Tools to optimise + reconstruct the
                                     baseline using the run codes from each
                                     order, return a DayResult.
  import_file_and_compute(payload) — wraps orders_import then calls
                                     load_or_compute_day for the file's date.

The result holds both plans in memory; the Streamlit cache wraps this so
flicking between the Map and Costs pages doesn't re-solve.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass, field
from datetime import date as DateT, datetime
from typing import Any

from .baseline import reconstruct_baseline
from .optimise import optimise
from .orders_import import import_orders, parse_orders_excel
from .queries import deliveries_for_date, get_config, get_depot, list_vehicles
from .run_code import RUN_DAYS, decode_run_code
from .schemas import (
    BaselineRequest,
    BaselineRouteSpec,
    CostParamsModel,
    LatLngModel,
    OptimiseRequest,
    StopSpec,
    VehicleSpec,
)


@dataclass
class Delivery:
    order_id: str
    customer_id: str
    customer_code: str
    customer_name: str
    order_number: str | None
    order_value_pence: int | None
    legacy_run_code: str | None
    lat: float
    lng: float


@dataclass
class RouteSummary:
    vehicle_id: str
    label: str
    stop_sequence: list[str]  # order ids
    total_distance_km: float
    total_duration_min: int
    fuel_cost_pence: int
    labour_cost_pence: int
    overhead_pence: int
    total_cost_pence: int
    leg_distances_km: list[float] = field(default_factory=list)
    leg_durations_min: list[int] = field(default_factory=list)
    per_stop_cost_pence: dict[str, int] = field(default_factory=dict)


@dataclass
class DayResult:
    date: DateT
    deliveries: list[Delivery]
    optimised_routes: list[RouteSummary]
    original_routes: list[RouteSummary]  # legacy run-code groupings, NN-sequenced
    optimised_total_pence: int
    original_total_pence: int
    saving_pence: int
    saving_pct: float
    excluded: list[Delivery]  # mail order / unparseable codes / no geocode

    def vehicle_for_optimised(self, order_id: str) -> str | None:
        for r in self.optimised_routes:
            if order_id in r.stop_sequence:
                return r.vehicle_id
        return None

    def vehicle_for_original(self, order_id: str) -> str | None:
        for r in self.original_routes:
            if order_id in r.stop_sequence:
                return r.vehicle_id
        return None


# ----- internals -----

def _config_to_cost_params(cfg: dict) -> CostParamsModel:
    return CostParamsModel(
        diesel_price_pence_per_litre=int(cfg["diesel_price_pence_per_litre"]),
        vehicle_mpg=float(cfg["default_mpg"]),
        driver_hourly_rate_pence=int(cfg["default_driver_hourly_rate_pence"]),
        avg_speed_kmh=float(cfg["avg_speed_kmh"]),
        service_min_per_stop=int(cfg["service_time_min_per_stop"]),
        depot_loading_min=int(cfg["depot_loading_time_min"]),
        vehicle_fixed_cost_per_day_pence=int(cfg["vehicle_fixed_cost_per_day_pence"]),
    )


def _vehicles_for_optimiser(cfg: dict) -> list[VehicleSpec]:
    rows = list_vehicles(active_only=True)
    if rows.empty:
        return [
            VehicleSpec(
                id=f"default-v{i + 1}",
                capacity_kg=1200,
                capacity_crates=80,
                shift_minutes=int(round(float(cfg["driver_max_shift_hours"]) * 60)),
                mpg=float(cfg["default_mpg"]),
                diesel_price_pence_per_litre=int(cfg["diesel_price_pence_per_litre"]),
                labour_cost_per_hour_pence=int(cfg["default_driver_hourly_rate_pence"]),
                overhead_pence=int(cfg["vehicle_fixed_cost_per_day_pence"]),
            )
            for i in range(7)
        ]
    out = []
    for _, v in rows.iterrows():
        mpg_val = v["mpg"]
        out.append(
            VehicleSpec(
                id=str(v["id"]),
                capacity_kg=float(v["capacity_kg"]),
                capacity_crates=int(v["capacity_crates"]),
                shift_minutes=int(round(float(cfg["driver_max_shift_hours"]) * 60)),
                mpg=float(mpg_val) if mpg_val is not None and not (isinstance(mpg_val, float) and math.isnan(mpg_val)) else float(cfg["default_mpg"]),
                diesel_price_pence_per_litre=int(cfg["diesel_price_pence_per_litre"]),
                labour_cost_per_hour_pence=int(cfg["default_driver_hourly_rate_pence"]),
                overhead_pence=int(v["fixed_cost_per_day_pence"] or cfg["vehicle_fixed_cost_per_day_pence"]),
            )
        )
    return out


def _per_stop_cost_share(r: Any, vehicle_label: str) -> dict[str, int]:
    """Allocate one route's cost across its stops by leg km × fuel + leg min × labour
    + flat overhead share. Mirrors what the optimiser persistence layer does."""
    total_km = float(r.total_distance_km) or 0.001
    total_min = max(int(r.total_duration_min), 1)
    n_stops = max(len(r.stop_sequence), 1)
    out: dict[str, int] = {}
    legs_km = list(r.leg_distances_km)
    legs_min = list(r.leg_durations_min)
    overhead_share = int(r.overhead_pence) // n_stops
    for i, oid in enumerate(r.stop_sequence):
        leg_km = legs_km[i] if i < len(legs_km) else 0.0
        leg_min = legs_min[i] if i < len(legs_min) else 0
        fuel = round((leg_km / total_km) * int(r.fuel_cost_pence))
        labour = round((leg_min / total_min) * int(r.labour_cost_pence))
        out[str(oid)] = int(fuel + labour + overhead_share)
    _ = vehicle_label  # currently unused but kept for future per-route labelling
    return out


def load_or_compute_day(date: DateT) -> DayResult:
    """Load all deliveries for the date and compute both plans in memory."""
    cfg = get_config()
    depot = get_depot()

    rows = deliveries_for_date(date.isoformat())
    if rows.empty:
        return DayResult(
            date=date,
            deliveries=[],
            optimised_routes=[],
            original_routes=[],
            optimised_total_pence=0,
            original_total_pence=0,
            saving_pence=0,
            saving_pct=0.0,
            excluded=[],
        )

    deliveries: list[Delivery] = []
    excluded: list[Delivery] = []
    for _, r in rows.iterrows():
        d = Delivery(
            order_id=str(r["order_id"]),
            customer_id=str(r["customer_id"]),
            customer_code=str(r["customer_code"]),
            customer_name=str(r["name"]),
            order_number=(str(r["order_number"]) if r["order_number"] is not None else None),
            order_value_pence=(
                int(r["order_value_pence"])
                if r["order_value_pence"] is not None
                and not (isinstance(r["order_value_pence"], float) and math.isnan(r["order_value_pence"]))
                else None
            ),
            legacy_run_code=str(r["legacy_run_code"]) if r["legacy_run_code"] else None,
            lat=float(r["lat"]),
            lng=float(r["lng"]),
        )
        decoded = decode_run_code(d.legacy_run_code)
        # Mail orders ride no van; exclude. Unparseable codes still go to the
        # optimiser (they're real deliveries), but they don't appear in the
        # original baseline.
        if decoded.is_mail_order:
            excluded.append(d)
            continue
        deliveries.append(d)

    if not deliveries:
        return DayResult(
            date=date,
            deliveries=[],
            optimised_routes=[],
            original_routes=[],
            optimised_total_pence=0,
            original_total_pence=0,
            saving_pence=0,
            saving_pct=0.0,
            excluded=excluded,
        )

    # ---- optimised plan ----
    cost_params = _config_to_cost_params(cfg)
    vehicles = _vehicles_for_optimiser(cfg)
    opt_req = OptimiseRequest(
        depot=LatLngModel(lat=float(depot["lat"]), lng=float(depot["lng"])),
        delivery_date=date.isoformat(),
        vehicles=vehicles,
        stops=[
            StopSpec(
                id=d.order_id,
                lat=d.lat,
                lng=d.lng,
                weight_kg=50,  # deliberately uniform; we don't have weights
                crate_count=3,
                service_minutes=int(cfg["service_time_min_per_stop"]),
            )
            for d in deliveries
        ],
        service_time_minutes_default=int(cfg["service_time_min_per_stop"]),
        depot_loading_minutes=int(cfg["depot_loading_time_min"]),
        avg_speed_kmh=float(cfg["avg_speed_kmh"]),
    )
    opt_resp = asyncio.run(optimise(opt_req))
    optimised: list[RouteSummary] = []
    for r in opt_resp.routes:
        rs = RouteSummary(
            vehicle_id=r.vehicle_id,
            label=r.vehicle_id,
            stop_sequence=list(r.stop_sequence),
            total_distance_km=float(r.total_distance_km),
            total_duration_min=int(r.total_duration_min),
            fuel_cost_pence=int(r.fuel_cost_pence),
            labour_cost_pence=int(r.labour_cost_pence),
            overhead_pence=int(r.overhead_pence),
            total_cost_pence=int(r.total_cost_pence),
            leg_distances_km=list(r.leg_distances_km),
            leg_durations_min=list(r.leg_durations_min),
        )
        rs.per_stop_cost_pence = _per_stop_cost_share(rs, rs.label)
        optimised.append(rs)

    # ---- original plan: group by per-order legacy run code (already merged
    # into the optimised request as the deliveries' .legacy_run_code), call
    # the baseline reconstructor with each colour as a "van" for the day.
    dow = date.weekday()
    groups: dict[str, list[Delivery]] = {}
    if dow in RUN_DAYS:
        for d in deliveries:
            decoded = decode_run_code(d.legacy_run_code)
            if decoded.unparseable:
                continue
            colour = decoded.by_day.get(dow)
            if not colour:
                continue
            groups.setdefault(colour, []).append(d)

    if groups:
        baseline_req = BaselineRequest(
            depot=LatLngModel(lat=float(depot["lat"]), lng=float(depot["lng"])),
            baseline_routes=[
                BaselineRouteSpec(
                    van_colour=c,
                    day_of_week=dow,
                    stops=[
                        StopSpec(
                            id=d.order_id,
                            lat=d.lat,
                            lng=d.lng,
                            weight_kg=0,
                            crate_count=0,
                            service_minutes=int(cfg["service_time_min_per_stop"]),
                        )
                        for d in stops
                    ],
                )
                for c, stops in groups.items()
            ],
            cost_params=cost_params,
        )
        baseline_resp = asyncio.run(reconstruct_baseline(baseline_req))
        original: list[RouteSummary] = []
        for r in baseline_resp.baseline_routes:
            rs = RouteSummary(
                vehicle_id=r.van_colour,
                label=f"{r.van_colour} (legacy)",
                stop_sequence=list(r.stop_sequence),
                total_distance_km=float(r.total_distance_km),
                total_duration_min=int(r.total_duration_min),
                fuel_cost_pence=int(r.fuel_cost_pence),
                labour_cost_pence=int(r.labour_cost_pence),
                overhead_pence=int(r.overhead_pence),
                total_cost_pence=int(r.total_cost_pence),
                leg_distances_km=list(r.leg_distances_km),
                leg_durations_min=list(r.leg_durations_min),
            )
            rs.per_stop_cost_pence = _per_stop_cost_share(rs, rs.label)
            original.append(rs)
    else:
        original = []

    optimised_total = sum(r.total_cost_pence for r in optimised)
    original_total = sum(r.total_cost_pence for r in original)
    saving = original_total - optimised_total
    saving_pct = saving / original_total if original_total > 0 else 0.0

    return DayResult(
        date=date,
        deliveries=deliveries,
        optimised_routes=optimised,
        original_routes=original,
        optimised_total_pence=optimised_total,
        original_total_pence=original_total,
        saving_pence=saving,
        saving_pct=saving_pct,
        excluded=excluded,
    )


def import_file_and_compute(payload: bytes) -> tuple[DayResult, dict]:
    """Parse a Fresho delivery_runs Excel, upsert orders + customers, then
    return the DayResult for the file's delivery date.

    The summary dict carries import counts so the page can show a toast.
    """
    rows, parse_errors = parse_orders_excel(payload)
    if not rows:
        raise ValueError("Empty file or no parseable rows")
    summary = import_orders(rows)
    summary_dict = {
        "rows_parsed": summary.rows_parsed,
        "orders_inserted": summary.orders_inserted,
        "orders_updated": summary.orders_updated,
        "customers_created": summary.customers_created,
        "customers_geocoded": summary.customers_geocoded,
        "customers_missing_geocode": summary.customers_missing_geocode,
        "errors": summary.errors,
        "parse_errors": parse_errors,
    }
    file_date = rows[0].delivery_date
    return load_or_compute_day(file_date), summary_dict


def _to_iso(d: DateT | datetime) -> str:
    if isinstance(d, datetime):
        return d.date().isoformat()
    return d.isoformat()
