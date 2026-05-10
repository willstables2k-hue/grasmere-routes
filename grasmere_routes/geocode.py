"""Mapbox geocoder bounded to UK, with a confidence band.

Customers below 'street' confidence go to the import review queue —
routing them blindly would put pins in the wrong village.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterable, Literal

import httpx

GeocodeConfidence = Literal["rooftop", "street", "postcode", "failed"]

MAPBOX_GEOCODE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"


@dataclass(frozen=True)
class GeocodeResult:
    lat: float | None
    lng: float | None
    confidence: GeocodeConfidence
    matched_address: str | None
    raw: dict | None


def classify_confidence(feature: dict) -> GeocodeConfidence:
    rel = feature.get("relevance", 0)
    types = feature.get("place_type", []) or []
    exact = (feature.get("properties") or {}).get("match_code", {}).get("exact_match")
    if rel >= 0.9 and (exact or "address" in types):
        return "rooftop"
    if rel >= 0.7 or "address" in types or "street" in types:
        return "street"
    if rel >= 0.5 or "postcode" in types or "place" in types:
        return "postcode"
    return "failed"


def geocode_address(address: str, *, token: str | None = None) -> GeocodeResult:
    token = token or os.environ.get("MAPBOX_TOKEN")
    if not token:
        return GeocodeResult(None, None, "failed", None, {"error": "MAPBOX_TOKEN not set"})
    addr = (address or "").strip()
    if not addr:
        return GeocodeResult(None, None, "failed", None, None)

    from urllib.parse import quote

    params = {
        "access_token": token,
        "country": "gb",
        "limit": 1,
        "types": "address,poi,place,postcode",
        "autocomplete": "false",
    }
    url = f"{MAPBOX_GEOCODE_URL}/{quote(addr, safe='')}.json"
    try:
        resp = httpx.get(url, params=params, timeout=10.0)
        resp.raise_for_status()
        body = resp.json()
    except Exception as e:  # noqa: BLE001
        return GeocodeResult(None, None, "failed", None, {"error": str(e)})

    feats = body.get("features") or []
    if not feats:
        return GeocodeResult(None, None, "failed", None, body)
    f = feats[0]
    center = f.get("center") or [None, None]
    return GeocodeResult(
        lat=center[1],
        lng=center[0],
        confidence=classify_confidence(f),
        matched_address=f.get("place_name"),
        raw=f,
    )


def geocode_many(
    rows: Iterable[tuple[str, str]],
    *,
    on_progress=None,
) -> dict[str, GeocodeResult]:
    out: dict[str, GeocodeResult] = {}
    items = list(rows)
    for i, (cid, addr) in enumerate(items, start=1):
        out[cid] = geocode_address(addr)
        if on_progress:
            on_progress(i, len(items))
        time.sleep(0.2)  # ~5 req/s well under Mapbox free-tier limit
    return out
