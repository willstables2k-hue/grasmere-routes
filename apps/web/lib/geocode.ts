/**
 * Customer-address geocoding via Mapbox.
 *
 * Bounded to the UK (gb), filtered to address/poi/place types. Returns
 * a single best candidate with a confidence band:
 *
 *   "rooftop"  → relevance ≥ 0.9 AND match_code.exact_match (or address type)
 *   "street"   → relevance 0.7–0.9 OR street type
 *   "postcode" → relevance 0.5–0.7 OR postcode-only match
 *   "failed"   → no usable match
 *
 * Customers with confidence < "street" go to a manual review queue —
 * routing them blindly would put pins in the wrong village.
 */

export type GeocodeConfidence = "rooftop" | "street" | "postcode" | "failed";

export interface GeocodeResult {
  lat: number | null;
  lng: number | null;
  confidence: GeocodeConfidence;
  matchedAddress: string | null;
  raw: unknown;
}

const MAPBOX_GEOCODE_URL =
  "https://api.mapbox.com/geocoding/v5/mapbox.places";

export async function geocodeAddress(
  address: string,
  opts: { token?: string } = {},
): Promise<GeocodeResult> {
  const token = opts.token ?? process.env.MAPBOX_TOKEN;
  if (!token) {
    return {
      lat: null,
      lng: null,
      confidence: "failed",
      matchedAddress: null,
      raw: { error: "MAPBOX_TOKEN not set" },
    };
  }
  const trimmed = address?.trim();
  if (!trimmed) {
    return { lat: null, lng: null, confidence: "failed", matchedAddress: null, raw: null };
  }

  const url = new URL(`${MAPBOX_GEOCODE_URL}/${encodeURIComponent(trimmed)}.json`);
  url.searchParams.set("access_token", token);
  url.searchParams.set("country", "gb");
  url.searchParams.set("limit", "1");
  url.searchParams.set("types", "address,poi,place,postcode");
  url.searchParams.set("autocomplete", "false");

  const res = await fetch(url, { method: "GET" });
  if (!res.ok) {
    return {
      lat: null,
      lng: null,
      confidence: "failed",
      matchedAddress: null,
      raw: { status: res.status, statusText: res.statusText },
    };
  }
  const body = await res.json();
  const feature = body?.features?.[0];
  if (!feature || !feature.center) {
    return { lat: null, lng: null, confidence: "failed", matchedAddress: null, raw: body };
  }

  const [lng, lat] = feature.center as [number, number];
  return {
    lat,
    lng,
    confidence: classifyConfidence(feature),
    matchedAddress: feature.place_name ?? null,
    raw: feature,
  };
}

/** Public so it can be unit-tested without hitting Mapbox. */
export function classifyConfidence(feature: {
  relevance?: number;
  place_type?: string[];
  properties?: { match_code?: { exact_match?: boolean } };
}): GeocodeConfidence {
  const rel = feature.relevance ?? 0;
  const types = feature.place_type ?? [];
  const exact = feature.properties?.match_code?.exact_match;

  if (rel >= 0.9 && (exact || types.includes("address"))) return "rooftop";
  if (rel >= 0.7 || types.includes("address") || types.includes("street")) return "street";
  if (rel >= 0.5 || types.includes("postcode") || types.includes("place")) return "postcode";
  return "failed";
}

/**
 * Batch helper for the import job — geocodes one customer at a time so a
 * single bad address doesn't poison the batch. Mapbox geocoding is
 * 600 req/min on the free tier; we throttle to ~5/sec to stay safe.
 */
export async function geocodeMany(
  rows: { id: string; address: string }[],
  onProgress?: (done: number, total: number) => void,
): Promise<Record<string, GeocodeResult>> {
  const out: Record<string, GeocodeResult> = {};
  let done = 0;
  for (const r of rows) {
    out[r.id] = await geocodeAddress(r.address);
    done++;
    onProgress?.(done, rows.length);
    await new Promise((res) => setTimeout(res, 200)); // ~5/sec
  }
  return out;
}
