import { describe, it, expect } from "vitest";
import {
  computeRouteCost,
  averageCostPerStop,
  allocateStopShare,
  marginalCostPence,
  netContributionPence,
  KM_PER_MILE,
  UK_GALLON_L,
} from "./cost-model";
import { ROUTE_CASES, SPEC_DEFAULTS } from "./cost-model.fixtures";

describe("constants", () => {
  it("uses imperial UK gallon, not US", () => {
    expect(UK_GALLON_L).toBe(4.546);
    // sanity: km per mile rounded
    expect(KM_PER_MILE).toBeCloseTo(1.609344, 6);
  });
});

describe("computeRouteCost — shared fixtures", () => {
  for (const c of ROUTE_CASES) {
    it(c.name, () => {
      const out = computeRouteCost(
        { distanceKm: c.distanceKm, numStops: c.numStops },
        SPEC_DEFAULTS,
      );
      expect(out.fuelCostPence).toBe(c.expected.fuelCostPence);
      expect(out.labourCostPence).toBe(c.expected.labourCostPence);
      expect(out.overheadPence).toBe(c.expected.overheadPence);
      expect(out.totalCostPence).toBe(c.expected.totalCostPence);
    });
  }
});

describe("computeRouteCost — guards", () => {
  it("throws when mpg ≤ 0", () => {
    expect(() =>
      computeRouteCost({ distanceKm: 10, numStops: 1 }, { ...SPEC_DEFAULTS, vehicleMpg: 0 }),
    ).toThrow();
  });
  it("throws when speed ≤ 0", () => {
    expect(() =>
      computeRouteCost({ distanceKm: 10, numStops: 1 }, { ...SPEC_DEFAULTS, avgSpeedKmh: 0 }),
    ).toThrow();
  });
});

describe("averageCostPerStop", () => {
  it("returns 0 when num stops is 0 (avoid div by zero)", () => {
    const r = computeRouteCost({ distanceKm: 0, numStops: 0 }, SPEC_DEFAULTS);
    expect(averageCostPerStop(r, 0)).toBe(0);
  });
  it("divides correctly", () => {
    const r = computeRouteCost({ distanceKm: 30, numStops: 5 }, SPEC_DEFAULTS);
    expect(averageCostPerStop(r, 5)).toBeCloseTo(r.totalCostPence / 5, 6);
  });
});

describe("allocateStopShare", () => {
  it("splits a route's costs across stops and recomposes near-totals", () => {
    const route = computeRouteCost({ distanceKm: 60, numStops: 4 }, SPEC_DEFAULTS);
    // 4 equal legs of 15 km, each leg taking 18 minutes (15/50h × 60), service 8 min each
    const legs = [
      { legKm: 15, legMin: 18 },
      { legKm: 15, legMin: 18 },
      { legKm: 15, legMin: 18 },
      { legKm: 15, legMin: 18 },
    ];
    const totalRouteMin =
      route.drivingHours * 60 + route.serviceHours * 60 + route.loadingHours * 60;
    const shares = legs.map((l) =>
      allocateStopShare({
        legKm: l.legKm,
        legMin: l.legMin,
        serviceMin: SPEC_DEFAULTS.serviceMinPerStop,
        totalRouteKm: 60,
        totalRouteMin,
        numStops: 4,
        route,
      }),
    );
    const sumFuel = shares.reduce((a, s) => a + s.fuelSharePence, 0);
    const sumLabour = shares.reduce((a, s) => a + s.labourSharePence, 0);
    const sumOverhead = shares.reduce((a, s) => a + s.overheadSharePence, 0);

    // Within rounding tolerance: each leg is 25% of fuel, ~96% of labour
    // (the loading 30min isn't allocated to any single stop)
    expect(Math.abs(sumFuel - route.fuelCostPence)).toBeLessThanOrEqual(2);
    // Loading minutes are deliberately unaccounted for in per-stop shares.
    // sum(labour shares) ≈ labour − loading_share. Just sanity-check it's positive
    // and less than total labour.
    expect(sumLabour).toBeGreaterThan(0);
    expect(sumLabour).toBeLessThanOrEqual(route.labourCostPence);
    expect(sumOverhead).toBeLessThanOrEqual(route.overheadPence);
  });
});

describe("marginalCostPence", () => {
  it("returns delta between two route costs", () => {
    const withStop = computeRouteCost({ distanceKm: 50, numStops: 5 }, SPEC_DEFAULTS);
    const withoutStop = computeRouteCost({ distanceKm: 38, numStops: 4 }, SPEC_DEFAULTS);
    expect(marginalCostPence(withStop, withoutStop)).toBe(
      withStop.totalCostPence - withoutStop.totalCostPence,
    );
  });
});

describe("netContributionPence", () => {
  it("computes positive contribution for healthy order", () => {
    const r = netContributionPence({
      orderValuePence: 30000, // £300
      grossMarginPct: 0.28,
      marginalCostPence: 500, // £5
    });
    expect(r.grossProfitPence).toBe(8400);
    expect(r.netContributionPence).toBe(7900);
  });
  it("returns negative when delivery cost exceeds gross profit", () => {
    const r = netContributionPence({
      orderValuePence: 5000, // £50
      grossMarginPct: 0.28,
      marginalCostPence: 2500, // £25
    });
    expect(r.grossProfitPence).toBe(1400);
    expect(r.netContributionPence).toBe(-1100);
  });
});
