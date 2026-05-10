"""Pydeck layer builders for the Map page.

Two layer types: delivery pins (one per stop, coloured by van) and route
paths (one polyline per van, depot → stops → depot). Plus a black depot
pin so the user always knows where the day starts.

Vans are coloured from a fixed 8-colour palette so consecutive page loads
look the same — same van always gets the same colour for visual continuity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pydeck as pdk

# Fixed palette — colour-blind friendly, ordered for distinct vans.
PALETTE: list[list[int]] = [
    [231, 76, 60],   # red
    [52, 152, 219],  # blue
    [46, 204, 113],  # green
    [241, 196, 15],  # yellow
    [155, 89, 182],  # purple
    [230, 126, 34],  # orange
    [26, 188, 156],  # teal
    [149, 165, 166], # grey
]
DEPOT_COLOUR: list[int] = [0, 0, 0]


@dataclass(frozen=True)
class RoutePath:
    """One van's path: depot → ordered stops → depot, plus an id for colouring."""
    vehicle_id: str
    coords: list[list[float]]  # [[lng, lat], ...] — pydeck expects lng first


def colour_for(index: int) -> list[int]:
    return PALETTE[index % len(PALETTE)]


def delivery_pin_layer(
    deliveries: list[dict],
    *,
    vehicle_order: list[str] | None = None,
    radius: int = 350,
) -> pdk.Layer:
    """One pin per delivery, coloured by its assigned vehicle.

    Each delivery dict needs at minimum: lat, lng, vehicle_id. Optional fields
    (name, order_number, order_value_pence, sequence) appear in the tooltip.
    """
    order = vehicle_order or sorted({d["vehicle_id"] for d in deliveries})
    colour_map = {v: colour_for(i) for i, v in enumerate(order)}
    data = [
        {
            "position": [float(d["lng"]), float(d["lat"])],
            "color": colour_map.get(d["vehicle_id"], PALETTE[0]),
            "name": d.get("name", ""),
            "vehicle_id": d["vehicle_id"],
            "sequence": d.get("sequence"),
            "order_number": d.get("order_number", ""),
            "order_value": (
                f"£{d['order_value_pence'] / 100:.2f}"
                if d.get("order_value_pence") is not None
                else ""
            ),
        }
        for d in deliveries
    ]
    return pdk.Layer(
        "ScatterplotLayer",
        data=data,
        get_position="position",
        get_color="color",
        get_radius=radius,
        radius_min_pixels=4,
        radius_max_pixels=12,
        pickable=True,
        opacity=0.9,
    )


def route_path_layer(
    paths: Iterable[RoutePath],
    *,
    vehicle_order: list[str] | None = None,
    width: int = 3,
) -> pdk.Layer:
    paths = list(paths)
    order = vehicle_order or [p.vehicle_id for p in paths]
    colour_map = {v: colour_for(i) for i, v in enumerate(order)}
    data = [
        {
            "path": p.coords,
            "color": colour_map.get(p.vehicle_id, PALETTE[0]),
            "vehicle_id": p.vehicle_id,
        }
        for p in paths
    ]
    return pdk.Layer(
        "PathLayer",
        data=data,
        get_path="path",
        get_color="color",
        width_scale=20,
        width_min_pixels=width,
        pickable=False,
    )


def depot_layer(lat: float, lng: float) -> pdk.Layer:
    return pdk.Layer(
        "ScatterplotLayer",
        data=[{"position": [float(lng), float(lat)]}],
        get_position="position",
        get_color=DEPOT_COLOUR,
        get_radius=700,
        radius_min_pixels=6,
        radius_max_pixels=14,
        pickable=False,
    )


def build_route_paths(
    routes: list[dict],
    deliveries: list[dict],
    depot_lat: float,
    depot_lng: float,
) -> list[RoutePath]:
    """Turn a routes list (each with stop_sequence + vehicle_id) and the
    deliveries lookup into a list of RoutePath objects ready for
    route_path_layer. Each path starts and ends at the depot."""
    by_id = {str(d["order_id"]): (float(d["lat"]), float(d["lng"])) for d in deliveries}
    paths: list[RoutePath] = []
    for r in routes:
        seq = r.get("stop_sequence") or []
        coords: list[list[float]] = [[depot_lng, depot_lat]]
        for oid in seq:
            latlng = by_id.get(str(oid))
            if not latlng:
                continue
            lat, lng = latlng
            coords.append([lng, lat])
        coords.append([depot_lng, depot_lat])
        if len(coords) >= 3:  # depot + ≥1 stop + depot
            paths.append(RoutePath(vehicle_id=str(r["vehicle_id"]), coords=coords))
    return paths


def make_view_state(deliveries: list[dict], depot_lat: float, depot_lng: float) -> pdk.ViewState:
    """Auto-fit the view to the depot + all deliveries."""
    if not deliveries:
        return pdk.ViewState(latitude=depot_lat, longitude=depot_lng, zoom=8)
    lats = [float(d["lat"]) for d in deliveries] + [depot_lat]
    lngs = [float(d["lng"]) for d in deliveries] + [depot_lng]
    min_lat, max_lat = min(lats), max(lats)
    min_lng, max_lng = min(lngs), max(lngs)
    centre_lat = (min_lat + max_lat) / 2
    centre_lng = (min_lng + max_lng) / 2
    span = max(max_lat - min_lat, max_lng - min_lng)
    # Rough zoom heuristic for the East Midlands span we expect (~2°).
    if span <= 0.05:
        zoom = 12
    elif span <= 0.2:
        zoom = 10
    elif span <= 0.5:
        zoom = 9
    elif span <= 1.5:
        zoom = 8
    else:
        zoom = 7
    return pdk.ViewState(latitude=centre_lat, longitude=centre_lng, zoom=zoom)
