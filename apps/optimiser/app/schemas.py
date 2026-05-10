"""Pydantic request/response models for the optimiser HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ConfigDict


class LatLngModel(BaseModel):
    lat: float
    lng: float


class VehicleSpec(BaseModel):
    id: str
    capacity_kg: float = Field(default=1200, ge=0)
    capacity_crates: int = Field(default=80, ge=0)
    shift_minutes: int = Field(default=480, gt=0)
    fuel_cost_per_km_pence: int | None = None  # if absent computed from mpg
    mpg: float = Field(default=25.0, gt=0)
    diesel_price_pence_per_litre: int = Field(default=188, gt=0)
    labour_cost_per_hour_pence: int = Field(default=1600, ge=0)
    overhead_pence: int = Field(default=2500, ge=0)


class StopSpec(BaseModel):
    id: str
    lat: float
    lng: float
    weight_kg: float = 0
    crate_count: int = 0
    service_minutes: int = 8


class CostParamsModel(BaseModel):
    diesel_price_pence_per_litre: int = 188
    vehicle_mpg: float = 25.0
    driver_hourly_rate_pence: int = 1600
    avg_speed_kmh: float = 50.0
    service_min_per_stop: int = 8
    depot_loading_min: int = 30
    vehicle_fixed_cost_per_day_pence: int = 2500


class OptimiseRequest(BaseModel):
    depot: LatLngModel
    delivery_date: str
    vehicles: list[VehicleSpec]
    stops: list[StopSpec]
    service_time_minutes_default: int = 8
    depot_loading_minutes: int = 30
    avg_speed_kmh: float = 50.0


class RouteResult(BaseModel):
    vehicle_id: str
    stop_sequence: list[str]
    total_distance_km: float
    total_duration_min: int
    fuel_cost_pence: int
    labour_cost_pence: int
    overhead_pence: int
    total_cost_pence: int
    leg_distances_km: list[float]
    leg_durations_min: list[int]


class OptimiseResponse(BaseModel):
    status: Literal["ok", "infeasible"]
    routes: list[RouteResult]
    unassigned_stops: list[str]
    objective_value_pence: int
    solve_seconds: float
    optimiser_version: str


class MarginalCostRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    route: RouteResult
    excluded_stop_id: str
    depot: LatLngModel
    cost_params: CostParamsModel = CostParamsModel()


class MarginalCostResponse(BaseModel):
    cost_with_pence: int
    cost_without_pence: int
    marginal_cost_pence: int


class BaselineRouteSpec(BaseModel):
    van_colour: str
    day_of_week: int
    stops: list[StopSpec]


class BaselineRequest(BaseModel):
    depot: LatLngModel
    baseline_routes: list[BaselineRouteSpec]
    cost_params: CostParamsModel = CostParamsModel()


class BaselineRouteResult(BaseModel):
    van_colour: str
    day_of_week: int
    stop_sequence: list[str]
    total_distance_km: float
    total_duration_min: int
    fuel_cost_pence: int
    labour_cost_pence: int
    overhead_pence: int
    total_cost_pence: int
    leg_distances_km: list[float]
    leg_durations_min: list[int]


class BaselineResponse(BaseModel):
    baseline_routes: list[BaselineRouteResult]
    summary: dict
