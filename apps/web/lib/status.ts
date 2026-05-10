/**
 * Customer status derivation. Logic mirrors the Postgres view
 * `customer_status_v` but is exposed for in-memory use during CSV import,
 * planning, and tests where we don't want to hit the DB.
 */

export type CustomerStatus = "live" | "dormant" | "no_history";

export interface StatusInputs {
  lastDeliveryDate: Date | null;
  manuallyConfirmedLiveAt: Date | null;
  /** Default 180 — keep aligned with config.dormancy_threshold_days */
  thresholdDays: number;
  /** Defaults to "now" in the caller's clock — testable */
  today?: Date;
}

const MS_PER_DAY = 24 * 60 * 60 * 1000;

export function deriveStatus(args: StatusInputs): {
  status: CustomerStatus;
  daysSinceLastDelivery: number | null;
} {
  const today = args.today ?? new Date();
  const cutoff = new Date(today.getTime() - args.thresholdDays * MS_PER_DAY);

  if (args.manuallyConfirmedLiveAt && args.manuallyConfirmedLiveAt >= cutoff) {
    return {
      status: "live",
      daysSinceLastDelivery: args.lastDeliveryDate
        ? Math.floor((today.getTime() - args.lastDeliveryDate.getTime()) / MS_PER_DAY)
        : null,
    };
  }

  if (!args.lastDeliveryDate) {
    return { status: "no_history", daysSinceLastDelivery: null };
  }

  const days = Math.floor((today.getTime() - args.lastDeliveryDate.getTime()) / MS_PER_DAY);
  return {
    status: days <= args.thresholdDays ? "live" : "dormant",
    daysSinceLastDelivery: days,
  };
}
