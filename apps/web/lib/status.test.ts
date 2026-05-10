import { describe, it, expect } from "vitest";
import { deriveStatus } from "./status";

const TODAY = new Date("2026-05-09T00:00:00Z");
const days = (n: number) => new Date(TODAY.getTime() - n * 86400_000);

describe("deriveStatus — defaults at 180-day threshold", () => {
  it("live: delivered within 180 days", () => {
    const r = deriveStatus({
      lastDeliveryDate: days(45),
      manuallyConfirmedLiveAt: null,
      thresholdDays: 180,
      today: TODAY,
    });
    expect(r.status).toBe("live");
    expect(r.daysSinceLastDelivery).toBe(45);
  });

  it("dormant: last delivery exactly 181 days ago", () => {
    const r = deriveStatus({
      lastDeliveryDate: days(181),
      manuallyConfirmedLiveAt: null,
      thresholdDays: 180,
      today: TODAY,
    });
    expect(r.status).toBe("dormant");
  });

  it("no_history: no last delivery date", () => {
    const r = deriveStatus({
      lastDeliveryDate: null,
      manuallyConfirmedLiveAt: null,
      thresholdDays: 180,
      today: TODAY,
    });
    expect(r.status).toBe("no_history");
    expect(r.daysSinceLastDelivery).toBeNull();
  });

  it("manual confirm overrides dormancy if recent", () => {
    const r = deriveStatus({
      lastDeliveryDate: days(400),
      manuallyConfirmedLiveAt: days(10),
      thresholdDays: 180,
      today: TODAY,
    });
    expect(r.status).toBe("live");
  });

  it("manual confirm older than threshold does NOT keep customer live", () => {
    const r = deriveStatus({
      lastDeliveryDate: days(400),
      manuallyConfirmedLiveAt: days(200),
      thresholdDays: 180,
      today: TODAY,
    });
    expect(r.status).toBe("dormant");
  });
});
