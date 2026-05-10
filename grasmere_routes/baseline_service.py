"""Baseline reconstruction orchestrator (in-process — no HTTP service).

  1. Pull live customers (status filter via customer_status_v).
  2. Drop those whose legacy_run_code is mail-order (~NR) or unparseable.
  3. Group survivors by (van colour × day of week) using decoded codes.
  4. Call the optimiser baseline reconstructor (nearest-neighbour per group).
  5. Persist baseline_snapshot + baseline_routes + baseline_route_stops.
  6. Mark this snapshot as is_current = TRUE; demote previous current.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
from typing import Any

from sqlalchemy import text

from .baseline import reconstruct_baseline
from .db import engine, query_df
from .queries import get_config, get_depot
from .run_code import RUN_DAYS, decode_run_code
from .schemas import (
    BaselineRequest,
    BaselineRouteSpec,
    CostParamsModel,
    LatLngModel,
    StopSpec,
)


def _cost_params_from_config(cfg: dict) -> CostParamsModel:
    return CostParamsModel(
        diesel_price_pence_per_litre=int(cfg["diesel_price_pence_per_litre"]),
        vehicle_mpg=float(cfg["default_mpg"]),
        driver_hourly_rate_pence=int(cfg["default_driver_hourly_rate_pence"]),
        avg_speed_kmh=float(cfg["avg_speed_kmh"]),
        service_min_per_stop=int(cfg["service_time_min_per_stop"]),
        depot_loading_min=int(cfg["depot_loading_time_min"]),
        vehicle_fixed_cost_per_day_pence=int(cfg["vehicle_fixed_cost_per_day_pence"]),
    )


def _config_hash(cfg: dict) -> str:
    payload = {k: (str(v) if not isinstance(v, (int, float, list)) else v) for k, v in cfg.items() if k != "updated_at"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


def recompute_baseline() -> dict[str, Any]:
    cfg = get_config()
    depot = get_depot()

    live = query_df(
        """
        SELECT c.id::text AS id, c.legacy_run_code,
               c.delivery_lat, c.delivery_lng
        FROM customers c
        JOIN customer_status_v s ON s.customer_id = c.id
        WHERE c.active = TRUE AND s.status = 'live'
        """
    )

    excluded = 0
    groups: dict[tuple[str, int], list[dict]] = {}
    for _, r in live.iterrows():
        if r["delivery_lat"] is None or r["delivery_lng"] is None or (
            isinstance(r["delivery_lat"], float) and math.isnan(r["delivery_lat"])
        ):
            excluded += 1
            continue
        decoded = decode_run_code(r["legacy_run_code"])
        if decoded.is_mail_order or decoded.unparseable:
            excluded += 1
            continue
        for d in RUN_DAYS:
            colour = decoded.by_day.get(d)
            if not colour:
                continue
            groups.setdefault((colour, d), []).append(
                {
                    "id": r["id"],
                    "lat": float(r["delivery_lat"]),
                    "lng": float(r["delivery_lng"]),
                }
            )

    cost_params = _cost_params_from_config(cfg)
    req = BaselineRequest(
        depot=LatLngModel(lat=float(depot["lat"]), lng=float(depot["lng"])),
        baseline_routes=[
            BaselineRouteSpec(
                van_colour=colour,
                day_of_week=d,
                stops=[
                    StopSpec(
                        id=s["id"],
                        lat=s["lat"],
                        lng=s["lng"],
                        weight_kg=0,
                        crate_count=0,
                        service_minutes=int(cfg["service_time_min_per_stop"]),
                    )
                    for s in stops
                ],
            )
            for (colour, d), stops in groups.items()
        ],
        cost_params=cost_params,
    )
    resp = asyncio.run(reconstruct_baseline(req))

    # Persist
    cfg_hash = _config_hash(cfg)
    with engine().begin() as conn:
        conn.execute(
            text("UPDATE baseline_snapshot SET is_current = FALSE WHERE is_current = TRUE")
        )
        snap = conn.execute(
            text(
                """
                INSERT INTO baseline_snapshot (
                  config_hash, customer_count_included, customer_count_excluded,
                  total_distance_km, total_fuel_cost_pence, total_labour_cost_pence,
                  total_overhead_pence, total_cost_pence, total_stops,
                  weekly_cost_pence, annualised_cost_pence, is_current, notes
                ) VALUES (
                  :config_hash, :inc, :exc,
                  :dist, :fuel, :lab,
                  :ovh, :tot, :stops,
                  :wk, :ann, TRUE, :notes
                ) RETURNING id::text AS id
                """
            ),
            {
                "config_hash": cfg_hash,
                "inc": int(len(live) - excluded),
                "exc": int(excluded),
                "dist": float(resp.summary["total_distance_km"]),
                "fuel": int(sum(r.fuel_cost_pence for r in resp.baseline_routes)),
                "lab": int(sum(r.labour_cost_pence for r in resp.baseline_routes)),
                "ovh": int(sum(r.overhead_pence for r in resp.baseline_routes)),
                "tot": int(resp.summary["total_cost_pence"]),
                "stops": int(resp.summary["total_stops"]),
                "wk": int(resp.summary["weekly_cost_pence"]),
                "ann": int(resp.summary["annualised_cost_pence"]),
                "notes": (
                    f"Computed from {len(live)} live customers; {excluded} excluded "
                    "(mail-order, unparseable codes, or no geocode)"
                ),
            },
        ).first()
        snap_id = snap[0]

        for br in resp.baseline_routes:
            stops = max(len(br.stop_sequence), 1)
            route_id = conn.execute(
                text(
                    """
                    INSERT INTO baseline_routes (
                      snapshot_id, van_colour, day_of_week, stop_count,
                      distance_km, duration_min,
                      fuel_cost_pence, labour_cost_pence, overhead_pence,
                      total_cost_pence, cost_per_stop_pence
                    ) VALUES (
                      :sid, :van, :dow, :n, :km, :min,
                      :fuel, :lab, :ovh, :tot, :pps
                    ) RETURNING id::text AS id
                    """
                ),
                {
                    "sid": snap_id,
                    "van": br.van_colour,
                    "dow": br.day_of_week,
                    "n": stops,
                    "km": float(br.total_distance_km),
                    "min": int(br.total_duration_min),
                    "fuel": int(br.fuel_cost_pence),
                    "lab": int(br.labour_cost_pence),
                    "ovh": int(br.overhead_pence),
                    "tot": int(br.total_cost_pence),
                    "pps": int(round(br.total_cost_pence / stops)),
                },
            ).first()[0]

            for i, cid in enumerate(br.stop_sequence):
                leg_km = br.leg_distances_km[i] if i < len(br.leg_distances_km) else 0.0
                leg_min = br.leg_durations_min[i] if i < len(br.leg_durations_min) else 0
                fuel_share = int(round((leg_km / max(br.total_distance_km, 0.001)) * br.fuel_cost_pence))
                labour_share = int(round((leg_min / max(br.total_duration_min, 1)) * br.labour_cost_pence))
                overhead_share = br.overhead_pence // stops
                conn.execute(
                    text(
                        """
                        INSERT INTO baseline_route_stops (
                          baseline_route_id, customer_id, sequence,
                          km_to_stop, min_to_stop,
                          fuel_share_pence, labour_share_pence,
                          overhead_share_pence, direct_cost_pence
                        ) VALUES (
                          :brid, :cid, :seq, :km, :min,
                          :fuel, :lab, :ovh, :direct
                        )
                        """
                    ),
                    {
                        "brid": route_id,
                        "cid": cid,
                        "seq": i + 1,
                        "km": leg_km,
                        "min": leg_min,
                        "fuel": fuel_share,
                        "lab": labour_share,
                        "ovh": overhead_share,
                        "direct": fuel_share + labour_share + overhead_share,
                    },
                )

    return {
        "snapshot_id": snap_id,
        "customer_count_included": len(live) - excluded,
        "customer_count_excluded": excluded,
        "weekly_cost_pence": int(resp.summary["weekly_cost_pence"]),
        "annualised_cost_pence": int(resp.summary["annualised_cost_pence"]),
        "total_distance_km": float(resp.summary["total_distance_km"]),
    }
