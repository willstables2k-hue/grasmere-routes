"""
Distance/duration matrix.

Real Mapbox Matrix API call when MAPBOX_TOKEN is present, otherwise a
haversine fallback for local dev/tests. H3-keyed in-memory LRU cache
prevents trivial GPS jitter from busting it. The web app persists the
durable copy in `distance_cache` (Postgres).

Mapbox Matrix limits per call:
  - 25 coordinates per request (driving profile)
  - We chunk and stitch when N > 25.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

import h3
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .optimiser_config import settings


@dataclass(frozen=True)
class LatLng:
    lat: float
    lng: float


@dataclass(frozen=True)
class MatrixResult:
    distance_m: list[list[int]]
    duration_s: list[list[int]]


# ---------- haversine fallback ----------

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(a: LatLng, b: LatLng) -> float:
    lat1, lon1 = math.radians(a.lat), math.radians(a.lng)
    lat2, lon2 = math.radians(b.lat), math.radians(b.lng)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def haversine_matrix(points: list[LatLng], avg_speed_kmh: float = 50.0) -> MatrixResult:
    """Distance via great-circle, duration assuming a flat avg speed.

    Used only when MAPBOX_TOKEN is not set. The road-vs-crow factor (~1.3)
    and stoplights/junctions are NOT modelled here — caller should expect
    optimistic numbers vs production.
    """
    n = len(points)
    # crude crow-fly → road multiplier so dev numbers don't look impossibly low
    ROAD_FACTOR = 1.3
    dist = [[0] * n for _ in range(n)]
    dur = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            d = haversine_m(points[i], points[j]) * ROAD_FACTOR
            dist[i][j] = int(d)
            dur[i][j] = int((d / 1000.0) / avg_speed_kmh * 3600.0)
    return MatrixResult(distance_m=dist, duration_s=dur)


# ---------- H3 cache key ----------


def h3_key(p: LatLng, resolution: int | None = None) -> str:
    res = resolution if resolution is not None else settings().cache_h3_resolution
    return h3.latlng_to_cell(p.lat, p.lng, res)


# ---------- Mapbox real call ----------


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4))
async def _mapbox_matrix_chunk(
    points: list[LatLng], token: str, base_url: str
) -> MatrixResult:
    coords = ";".join(f"{p.lng},{p.lat}" for p in points)
    url = f"{base_url}/{coords}"
    params = {"annotations": "distance,duration", "access_token": token}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        body = resp.json()
    if body.get("code") != "Ok":
        raise RuntimeError(f"mapbox error: {body.get('code')} {body.get('message')}")
    return MatrixResult(
        distance_m=[[int(x or 0) for x in row] for row in body["distances"]],
        duration_s=[[int(x or 0) for x in row] for row in body["durations"]],
    )


async def driving_matrix(points: list[LatLng]) -> MatrixResult:
    """Production-quality matrix when MAPBOX_TOKEN set; haversine otherwise."""
    cfg = settings()
    if not cfg.mapbox_token:
        return haversine_matrix(points)

    n = len(points)
    if n <= 25:
        return await _mapbox_matrix_chunk(points, cfg.mapbox_token, cfg.mapbox_matrix_url)

    # Stitch sub-matrices for >25 points (Mapbox single-request cap).
    full_d = [[0] * n for _ in range(n)]
    full_t = [[0] * n for _ in range(n)]
    chunk = 25
    for i in range(0, n, chunk):
        for j in range(0, n, chunk):
            sub_pts = points[i : i + chunk] + (points[j : j + chunk] if j != i else [])
            res = await _mapbox_matrix_chunk(sub_pts, cfg.mapbox_token, cfg.mapbox_matrix_url)
            block_i = list(range(i, min(i + chunk, n)))
            block_j = list(range(j, min(j + chunk, n))) if j != i else block_i
            len_i = len(block_i)
            for ai, gi in enumerate(block_i):
                for aj, gj in enumerate(block_j):
                    src_aj = aj if j == i else (aj + len_i)
                    full_d[gi][gj] = res.distance_m[ai][src_aj]
                    full_t[gi][gj] = res.duration_s[ai][src_aj]
    return MatrixResult(distance_m=full_d, duration_s=full_t)
