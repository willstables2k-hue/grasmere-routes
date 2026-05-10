"""Weekly plan orchestrator (in-process).

  generate_orders(date) — create pending orders for live customers whose
                          preferred_days includes date. Skips dormant + no_history.
  optimise_plan(date)   — fetch all pending orders, call optimiser, persist
                          routes + route_stops, compute the matched baseline
                          cost for the same customer set, return a comparison.
"""

from __future__ import annotations

import asyncio
import math
from datetime import datetime
from typing import Any

from sqlalchemy import text

from .baseline import reconstruct_baseline
from .db import engine, query_df
from .optimise import optimise
from .queries import (
    dormant_count_for_day,
    get_config,
    get_depot,
    insert_pending_order,
    live_customers_for_day,
    list_vehicles,
    orders_for_date,
)
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


def _js_day_to_pref_day(weekday_mon0: int) -> int:
    """Python's date.weekday() returns 0=Mon..6=Sun, which is what we store."""
    return weekday_mon0


def generate_orders(delivery_date: str) -> dict:
    dow = datetime.strptime(delivery_date, "%Y-%m-%d").weekday()
    live = live_customers_for_day(dow)
    dormant_n = dormant_count_for_day(dow)
    created = 0
    for cid in live["id"].astype(str).tolist():
        before = orders_for_date(delivery_date)
        insert_pending_order(cid, delivery_date)
        after = orders_for_date(delivery_date)
        if len(after) > len(before):
            created += 1
    return {
        "orders_created": created,
        "live_matching": int(len(live)),
        "dormant_matching_hidden": dormant_n,
    }


def _vehicles_for_optimiser(cfg: dict) -> list[VehicleSpec]:
    rows = list_vehicles(active_only=True)
    if rows.empty:
        # spec default: 7-vehicle fleet so the planner can solve before vehicles are configured
        return [
            VehicleSpec(
                id=f"default-v{i+1}",
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
        out.append(
            VehicleSpec(
                id=str(v["id"]),
                capacity_kg=float(v["capacity_kg"]),
                capacity_crates=int(v["capacity_crates"]),
                shift_minutes=int(round(float(cfg["driver_max_shift_hours"]) * 60)),
                mpg=float(v["mpg"]) if v["mpg"] is not None and not (isinstance(v["mpg"], float) and math.isnan(v["mpg"])) else float(cfg["default_mpg"]),
                diesel_price_pence_per_litre=int(cfg["diesel_price_pence_per_litre"]),
                labour_cost_per_hour_pence=int(cfg["default_driver_hourly_rate_pence"]),
                overhead_pence=int(v["fixed_cost_per_day_pence"] or cfg["vehicle_fixed_cost_per_day_pence"]),
            )
        )
    return out


def optimise_plan(delivery_date: str) -> dict[str, Any]:
    cfg = get_config()
    depot = get_depot()
    orders = orders_for_date(delivery_date)
    if orders.empty:
        return {"ok": False, "reason": "no orders for date — generate orders first"}

    vehicles = _vehicles_for_optimiser(cfg)

    stops = [
        StopSpec(
            id=str(o["order_id"]),
            lat=float(o["lat"]),
            lng=float(o["lng"]),
            weight_kg=float(o["weight_kg"]) if o["weight_kg"] is not None and not (isinstance(o["weight_kg"], float) and math.isnan(o["weight_kg"])) else 50.0,
            crate_count=int(o["crate_count"]) if o["crate_count"] is not None and not (isinstance(o["crate_count"], float) and math.isnan(o["crate_count"])) else 3,
            service_minutes=int(cfg["service_time_min_per_stop"]),
        )
        for _, o in orders.iterrows()
    ]

    opt_req = OptimiseRequest(
        depot=LatLngModel(lat=float(depot["lat"]), lng=float(depot["lng"])),
        delivery_date=delivery_date,
        vehicles=vehicles,
        stops=stops,
        service_time_minutes_default=int(cfg["service_time_min_per_stop"]),
        depot_loading_minutes=int(cfg["depot_loading_time_min"]),
        avg_speed_kmh=float(cfg["avg_speed_kmh"]),
    )
    opt_resp = asyncio.run(optimise(opt_req))

    # Matched baseline for the same set of customers, this day only
    dow = datetime.strptime(delivery_date, "%Y-%m-%d").weekday()
    cost_params = CostParamsModel(
        diesel_price_pence_per_litre=int(cfg["diesel_price_pence_per_litre"]),
        vehicle_mpg=float(cfg["default_mpg"]),
        driver_hourly_rate_pence=int(cfg["default_driver_hourly_rate_pence"]),
        avg_speed_kmh=float(cfg["avg_speed_kmh"]),
        service_min_per_stop=int(cfg["service_time_min_per_stop"]),
        depot_loading_min=int(cfg["depot_loading_time_min"]),
        vehicle_fixed_cost_per_day_pence=int(cfg["vehicle_fixed_cost_per_day_pence"]),
    )
    groups: dict[str, list[StopSpec]] = {}
    if dow in RUN_DAYS:
        for o in orders.itertuples():
            decoded = decode_run_code(o.legacy_run_code)
            if decoded.is_mail_order or decoded.unparseable:
                continue
            colour = decoded.by_day.get(dow)
            if not colour:
                continue
            groups.setdefault(colour, []).append(
                StopSpec(
                    id=str(o.customer_id),
                    lat=float(o.lat),
                    lng=float(o.lng),
                    weight_kg=0,
                    crate_count=0,
                    service_minutes=int(cfg["service_time_min_per_stop"]),
                )
            )
    baseline_resp = asyncio.run(
        reconstruct_baseline(
            BaselineRequest(
                depot=LatLngModel(lat=float(depot["lat"]), lng=float(depot["lng"])),
                baseline_routes=[
                    BaselineRouteSpec(van_colour=c, day_of_week=dow, stops=s)
                    for c, s in groups.items()
                ],
                cost_params=cost_params,
            )
        )
    )

    # Persist new draft routes (clears any previous draft for the same date)
    vehicles_df = list_vehicles(active_only=True)
    vehicle_ids_by_id = {str(v): str(v) for v in vehicles_df["id"]} if not vehicles_df.empty else {}
    with engine().begin() as conn:
        conn.execute(
            text("DELETE FROM routes WHERE delivery_date = :d AND status = 'draft'"),
            {"d": delivery_date},
        )
        for r in opt_resp.routes:
            stops_n = max(len(r.stop_sequence), 1)
            route_row = conn.execute(
                text(
                    """
                    INSERT INTO routes (
                      delivery_date, vehicle_id, status,
                      planned_distance_km, planned_duration_min,
                      planned_fuel_cost_pence, planned_labour_cost_pence,
                      planned_overhead_pence, planned_total_cost_pence,
                      optimiser_version, optimiser_seed
                    ) VALUES (
                      :d, :vid, 'draft',
                      :km, :min, :fuel, :lab, :ovh, :tot,
                      :ver, 'from_scratch'
                    ) RETURNING id::text AS id
                    """
                ),
                {
                    "d": delivery_date,
                    "vid": vehicle_ids_by_id.get(r.vehicle_id),
                    "km": float(r.total_distance_km),
                    "min": int(r.total_duration_min),
                    "fuel": int(r.fuel_cost_pence),
                    "lab": int(r.labour_cost_pence),
                    "ovh": int(r.overhead_pence),
                    "tot": int(r.total_cost_pence),
                    "ver": opt_resp.optimiser_version,
                },
            ).first()
            route_id = route_row[0]

            for i, oid in enumerate(r.stop_sequence):
                leg_km = r.leg_distances_km[i] if i < len(r.leg_distances_km) else 0.0
                leg_min = r.leg_durations_min[i] if i < len(r.leg_durations_min) else 0
                fuel_share = int(round((leg_km / max(r.total_distance_km, 0.001)) * r.fuel_cost_pence))
                labour_share = int(round((leg_min / max(r.total_duration_min, 1)) * r.labour_cost_pence))
                overhead_share = r.overhead_pence // stops_n
                conn.execute(
                    text(
                        """
                        INSERT INTO route_stops (
                          route_id, order_id, sequence,
                          planned_km_to_stop, planned_min_to_stop,
                          planned_fuel_share_pence, planned_labour_share_pence,
                          planned_overhead_share_pence, planned_direct_cost_pence
                        ) VALUES (
                          :rid, :oid, :seq, :km, :min, :fuel, :lab, :ovh, :direct
                        )
                        """
                    ),
                    {
                        "rid": route_id,
                        "oid": oid,
                        "seq": i + 1,
                        "km": leg_km,
                        "min": leg_min,
                        "fuel": fuel_share,
                        "lab": labour_share,
                        "ovh": overhead_share,
                        "direct": fuel_share + labour_share + overhead_share,
                    },
                )
                conn.execute(
                    text("UPDATE orders SET status = 'planned' WHERE id = :id"),
                    {"id": oid},
                )

    saving = int(baseline_resp.summary["total_cost_pence"]) - int(opt_resp.objective_value_pence)
    pct = (
        saving / int(baseline_resp.summary["total_cost_pence"])
        if baseline_resp.summary["total_cost_pence"] > 0
        else 0.0
    )
    return {
        "ok": True,
        "optimised_total_pence": int(opt_resp.objective_value_pence),
        "baseline_total_pence": int(baseline_resp.summary["total_cost_pence"]),
        "saving_pence": saving,
        "saving_pct": pct,
        "routes": [r.model_dump() for r in opt_resp.routes],
        "baseline_routes": [r.model_dump() for r in baseline_resp.baseline_routes],
        "unassigned": opt_resp.unassigned_stops,
        "solve_seconds": opt_resp.solve_seconds,
    }


def publish_routes(delivery_date: str) -> int:
    """Mark all draft routes for the given date as published."""
    with engine().begin() as conn:
        result = conn.execute(
            text("UPDATE routes SET status = 'published' WHERE delivery_date = :d AND status = 'draft'"),
            {"d": delivery_date},
        )
        return result.rowcount or 0
