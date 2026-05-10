/**
 * Decoder for legacy delivery_run_code values.
 *
 *   3 characters = [Tuesday, Thursday, Friday] colour assignments
 *
 *   W = White, P = Pink, B = Blue, G = Green, R = Red, Y = Yellow
 *   0 or O = van not running that day
 *   ~NR    = mail order / no fixed run  (exclude from baseline)
 *
 * Codes that don't decode cleanly (e.g. '5ME', 'MMR', single-letter codes)
 * return { unparseable: true } and should be flagged for manual review,
 * not silently dropped.
 */

export type DayOfWeek = 1 | 3 | 4; // Tue, Thu, Fri
export const DAY_TUE: DayOfWeek = 1;
export const DAY_THU: DayOfWeek = 3;
export const DAY_FRI: DayOfWeek = 4;
export const RUN_DAYS: readonly DayOfWeek[] = [DAY_TUE, DAY_THU, DAY_FRI];

export type VanColour = "White" | "Pink" | "Blue" | "Green" | "Red" | "Yellow";

const COLOUR_MAP: Record<string, VanColour> = {
  W: "White",
  P: "Pink",
  B: "Blue",
  G: "Green",
  R: "Red",
  Y: "Yellow",
};

export interface DecodedRunCode {
  raw: string;
  isMailOrder: boolean;
  unparseable: boolean;
  /** colour by day of week (1, 3, 4) — null means van not running that day */
  byDay: Record<DayOfWeek, VanColour | null>;
}

export function decodeRunCode(input: string | null | undefined): DecodedRunCode {
  const raw = (input ?? "").trim();
  // CSV stores values wrapped in single quotes: 'WP0'
  const cleaned = raw.replace(/^'|'$/g, "").trim().toUpperCase();

  const emptyByDay: Record<DayOfWeek, VanColour | null> = {
    [DAY_TUE]: null,
    [DAY_THU]: null,
    [DAY_FRI]: null,
  } as Record<DayOfWeek, VanColour | null>;

  const empty: DecodedRunCode = {
    raw,
    isMailOrder: false,
    unparseable: true,
    byDay: { ...emptyByDay },
  };

  if (!cleaned) return empty;

  if (cleaned === "~NR" || cleaned === "NR") {
    return { ...empty, isMailOrder: true, unparseable: false };
  }

  if (cleaned.length !== 3) return empty;

  const out: DecodedRunCode = {
    raw,
    isMailOrder: false,
    unparseable: false,
    byDay: { ...emptyByDay },
  };

  const days: DayOfWeek[] = [DAY_TUE, DAY_THU, DAY_FRI];
  for (let i = 0; i < 3; i++) {
    const ch = cleaned[i]!;
    if (ch === "0" || ch === "O") {
      out.byDay[days[i]!] = null;
      continue;
    }
    const colour = COLOUR_MAP[ch];
    if (!colour) {
      // Unknown letter (e.g. 'M', '5') — flag the whole code unparseable.
      return empty;
    }
    out.byDay[days[i]!] = colour;
  }
  return out;
}

/** Returns the days the van runs (Tue/Thu/Fri subset). */
export function activeDays(decoded: DecodedRunCode): DayOfWeek[] {
  return RUN_DAYS.filter((d) => decoded.byDay[d] != null);
}
