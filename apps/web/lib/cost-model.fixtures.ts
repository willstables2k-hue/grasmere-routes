/**
 * Shared fixtures: Both the TypeScript test suite and the Python test suite
 * compute against these EXACT inputs and assert against these EXACT outputs.
 *
 * If a number changes here, both suites need to update — that is intentional.
 * It guarantees that the optimiser objective and the UI £ figures agree.
 */
import type { CostParams } from "./cost-model";

export const SPEC_DEFAULTS: CostParams = {
  dieselPricePencePerLitre: 188,
  vehicleMpg: 25,
  driverHourlyRatePence: 1600,
  avgSpeedKmh: 50,
  serviceMinPerStop: 8,
  depotLoadingMin: 30,
  vehicleFixedCostPerDayPence: 2500,
};

export interface RouteCase {
  name: string;
  distanceKm: number;
  numStops: number;
  // Expected outputs (all integer pence)
  expected: {
    fuelCostPence: number;
    labourCostPence: number;
    overheadPence: number;
    totalCostPence: number;
  };
}

/**
 * Hand-computed cases — see comments for the arithmetic.
 *
 *   fuel_l   = (km / 1.609344) / mpg * 4.546
 *   fuel_p   = fuel_l × dieselPricePencePerLitre
 *   labour_h = km/speed + numStops*serviceMin/60 + depotLoadingMin/60
 *   labour_p = labour_h × driverHourlyRatePence  (rounded)
 */
export const ROUTE_CASES: RouteCase[] = [
  {
    name: "single short urban route, 5 stops, 30 km",
    distanceKm: 30,
    numStops: 5,
    expected: {
      // 30/1.609344 = 18.6411 mi → /25 = 0.74564 imp gal → ×4.546 = 3.38971 L
      // 3.38971 × 188 = 637.27 pence → 637
      fuelCostPence: 637,
      // hours: 30/50 + 5*8/60 + 30/60 = 0.6 + 0.6667 + 0.5 = 1.7667 → ×1600 = 2826.67 → 2827
      labourCostPence: 2827,
      overheadPence: 2500,
      totalCostPence: 637 + 2827 + 2500,
    },
  },
  {
    name: "long rural route, 25 stops, 180 km",
    distanceKm: 180,
    numStops: 25,
    expected: {
      // 180/1.609344 = 111.847 mi → /25 = 4.4739 imp gal → ×4.546 = 20.3382 L
      // 20.3382 × 188 = 3823.58 → 3824
      fuelCostPence: 3824,
      // hours: 180/50 + 25*8/60 + 30/60 = 3.6 + 3.3333 + 0.5 = 7.4333 → ×1600 = 11893.33 → 11893
      labourCostPence: 11893,
      overheadPence: 2500,
      totalCostPence: 3824 + 11893 + 2500,
    },
  },
  {
    name: "edge: zero stops (cancelled day, still loaded out)",
    distanceKm: 0,
    numStops: 0,
    expected: {
      fuelCostPence: 0,
      // 0/50 + 0 + 30/60 = 0.5 × 1600 = 800
      labourCostPence: 800,
      overheadPence: 2500,
      totalCostPence: 3300,
    },
  },
  {
    name: "edge: single stop nearby",
    distanceKm: 4,
    numStops: 1,
    expected: {
      // 4/1.609344 = 2.4855 mi → /25 = 0.09942 imp gal → ×4.546 = 0.45195 L
      // 0.45195 × 188 = 84.97 → 85
      fuelCostPence: 85,
      // hours: 4/50 + 1*8/60 + 30/60 = 0.08 + 0.1333 + 0.5 = 0.7133 → ×1600 = 1141.33 → 1141
      labourCostPence: 1141,
      overheadPence: 2500,
      totalCostPence: 85 + 1141 + 2500,
    },
  },
];
