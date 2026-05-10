"""Runtime configuration loaded from env vars."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    mapbox_token: str | None
    mapbox_matrix_url: str
    cache_h3_resolution: int


@lru_cache
def settings() -> Settings:
    return Settings(
        api_key=os.environ.get("OPTIMISER_API_KEY"),
        mapbox_token=os.environ.get("MAPBOX_TOKEN"),
        mapbox_matrix_url=os.environ.get(
            "MAPBOX_MATRIX_URL",
            "https://api.mapbox.com/directions-matrix/v1/mapbox/driving",
        ),
        cache_h3_resolution=int(os.environ.get("CACHE_H3_RESOLUTION", "9")),
    )
