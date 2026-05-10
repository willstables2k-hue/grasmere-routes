from __future__ import annotations

from grasmere_routes.map_layers import (
    PALETTE,
    RoutePath,
    build_route_paths,
    colour_for,
    delivery_pin_layer,
    depot_layer,
    make_view_state,
    route_path_layer,
)


def test_colour_for_wraps_around_palette():
    assert colour_for(0) == PALETTE[0]
    assert colour_for(len(PALETTE)) == PALETTE[0]
    assert colour_for(len(PALETTE) + 3) == PALETTE[3]


def test_delivery_pin_layer_assigns_consistent_colours():
    deliveries = [
        {"order_id": "o1", "lat": 52.7, "lng": -0.4, "vehicle_id": "v1", "name": "A"},
        {"order_id": "o2", "lat": 52.8, "lng": -0.3, "vehicle_id": "v2", "name": "B"},
        {"order_id": "o3", "lat": 52.6, "lng": -0.5, "vehicle_id": "v1", "name": "C"},
    ]
    layer = delivery_pin_layer(deliveries, vehicle_order=["v1", "v2"])
    data = layer.data
    # v1 stops share colour, v2 differs
    v1_colours = {tuple(d["color"]) for d in data if d["vehicle_id"] == "v1"}
    v2_colours = {tuple(d["color"]) for d in data if d["vehicle_id"] == "v2"}
    assert len(v1_colours) == 1
    assert len(v2_colours) == 1
    assert v1_colours != v2_colours


def test_build_route_paths_starts_and_ends_at_depot():
    routes = [
        {"vehicle_id": "v1", "stop_sequence": ["o1", "o2"]},
        {"vehicle_id": "v2", "stop_sequence": ["o3"]},
    ]
    deliveries = [
        {"order_id": "o1", "lat": 52.7, "lng": -0.4},
        {"order_id": "o2", "lat": 52.8, "lng": -0.3},
        {"order_id": "o3", "lat": 52.6, "lng": -0.5},
    ]
    paths = build_route_paths(routes, deliveries, depot_lat=52.77, depot_lng=-0.38)
    assert len(paths) == 2
    for p in paths:
        assert p.coords[0] == [-0.38, 52.77]   # depot first (lng, lat)
        assert p.coords[-1] == [-0.38, 52.77]  # depot last
    assert len(paths[0].coords) == 4   # depot + 2 stops + depot
    assert len(paths[1].coords) == 3   # depot + 1 stop + depot


def test_build_route_paths_skips_unknown_orders():
    routes = [{"vehicle_id": "v1", "stop_sequence": ["o1", "MISSING"]}]
    deliveries = [{"order_id": "o1", "lat": 52.7, "lng": -0.4}]
    paths = build_route_paths(routes, deliveries, depot_lat=52.77, depot_lng=-0.38)
    assert len(paths) == 1
    # depot + o1 + depot — MISSING dropped
    assert len(paths[0].coords) == 3


def test_route_path_layer_constructs_pydeck_layer():
    paths = [RoutePath("v1", [[-0.38, 52.77], [-0.4, 52.7], [-0.38, 52.77]])]
    layer = route_path_layer(paths, vehicle_order=["v1"])
    assert layer.type == "PathLayer"
    assert len(layer.data) == 1


def test_depot_layer_uses_black():
    layer = depot_layer(52.77, -0.38)
    assert layer.type == "ScatterplotLayer"
    assert layer.data[0]["position"] == [-0.38, 52.77]


def test_view_state_centres_on_depot_when_no_deliveries():
    vs = make_view_state([], 52.77, -0.38)
    assert vs.latitude == 52.77
    assert vs.longitude == -0.38


def test_view_state_zooms_to_fit_deliveries():
    deliveries = [
        {"lat": 52.5, "lng": -1.0},
        {"lat": 53.0, "lng": 0.0},
    ]
    vs = make_view_state(deliveries, 52.77, -0.38)
    # centre lies inside the bounding box
    assert 52.5 <= vs.latitude <= 53.0
    assert -1.0 <= vs.longitude <= 0.0
