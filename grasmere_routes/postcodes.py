"""UK postcode → lat/lng via postcodes.io (free, no auth, generous rate limits).

Used as a fallback geocoder when MAPBOX_TOKEN isn't set, so the planner can
demo against real customer data without a Mapbox account. Mapbox is still
preferred for production: postcodes.io returns the postcode CENTROID, not the
exact house, so a route through 30 stops in 30 different postcodes will be
roughly right but not pixel-perfect.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import httpx

# UK postcode regex per Royal Mail spec (rough but matches every variation
# in the real customer data + the example delivery file).
UK_POSTCODE_RE = re.compile(
    r"\b([A-PR-UWYZ][A-HK-Y]?[0-9][0-9A-HJKMNP-Y]?\s*[0-9][ABD-HJLNP-UW-Z]{2})\b",
    re.IGNORECASE,
)


def extract_postcode(address: str | None) -> str | None:
    if not address:
        return None
    m = UK_POSTCODE_RE.search(address.upper())
    if not m:
        return None
    raw = m.group(1).upper().replace(" ", "")
    if len(raw) < 5:
        return None
    # Insert canonical space before the inward code (always last 3 chars).
    return f"{raw[:-3]} {raw[-3:]}"


@dataclass(frozen=True)
class PostcodePoint:
    postcode: str
    lat: float
    lng: float


@lru_cache(maxsize=4096)
def geocode_postcode(postcode: str) -> PostcodePoint | None:
    pc = postcode.replace(" ", "").upper()
    try:
        resp = httpx.get(
            f"https://api.postcodes.io/postcodes/{pc}",
            timeout=5.0,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        body = resp.json().get("result") or {}
    except Exception:  # noqa: BLE001
        return None
    lat = body.get("latitude")
    lng = body.get("longitude")
    if lat is None or lng is None:
        return None
    return PostcodePoint(postcode=postcode, lat=float(lat), lng=float(lng))


def geocode_postcodes_bulk(postcodes: list[str]) -> dict[str, PostcodePoint]:
    """Batch endpoint: up to 100 postcodes per request, much faster than
    one-by-one when seeding a fresh customer set."""
    if not postcodes:
        return {}
    out: dict[str, PostcodePoint] = {}
    for chunk_start in range(0, len(postcodes), 100):
        chunk = postcodes[chunk_start : chunk_start + 100]
        try:
            resp = httpx.post(
                "https://api.postcodes.io/postcodes",
                json={"postcodes": chunk},
                timeout=10.0,
            )
            resp.raise_for_status()
            body = resp.json().get("result") or []
        except Exception:  # noqa: BLE001
            continue
        for item in body:
            pc = (item.get("query") or "").upper()
            res = item.get("result") or {}
            lat = res.get("latitude")
            lng = res.get("longitude")
            if lat is None or lng is None:
                continue
            out[pc] = PostcodePoint(postcode=pc, lat=float(lat), lng=float(lng))
    return out
