/**
 * Importer for Fresho-style customer CSV.
 *
 * Maps the columns documented in the build spec, extracts soft windows from
 * standing_delivery_instructions, parses the day-group into preferred_days,
 * detects COD from invoice_notes, and preserves the entire raw row in
 * raw_csv_row so the original truth is never lost.
 *
 * Returns rows ready for upsert on `customers.customer_code`.
 */
import { parse as parseCsv } from "csv-parse/sync";

// ---------- types ----------

export interface RawRow {
  [k: string]: string | undefined;
}

export interface ImportRow {
  customerCode: string;
  name: string;
  legalEntityName: string | null;
  deliveryAddress: string | null;
  billingAddress: string | null;
  pricingLevel: string | null;
  isCod: boolean;
  paymentTermDays: number | null;
  salesRep: string | null;
  deliveryDaysGroup: string | null;
  preferredDays: number[] | null;
  legacyRunCode: string | null;
  legacyRunPosition: number | null;
  standingPickingInstructions: string | null;
  standingDeliveryInstructions: string | null;
  softWindowStart: string | null;
  softWindowEnd: string | null;
  lastDeliveryDate: string | null; // ISO yyyy-mm-dd
  active: boolean;
  rawCsvRow: Record<string, string>;
  /** Set true when something didn't decode cleanly so it can go to a review queue. */
  flaggedForReview: boolean;
  flagReasons: string[];
}

// ---------- helpers ----------

const STRIP_QUOTES = /^'|'$/g;

function stripQuotes(v: string | undefined | null): string {
  return (v ?? "").replace(STRIP_QUOTES, "").trim();
}

function nonEmpty(v: string | undefined | null): string | null {
  const s = (v ?? "").trim();
  return s.length === 0 ? null : s;
}

/** Parse DD/MM/YYYY (the format the Fresho export uses) into ISO yyyy-mm-dd. */
export function parseUkDate(input: string | undefined | null): string | null {
  const s = (input ?? "").trim();
  if (!s) return null;
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(s);
  if (!m) return null;
  const [_, d, mo, y] = m;
  const dd = d!.padStart(2, "0");
  const mm = mo!.padStart(2, "0");
  return `${y}-${mm}-${dd}`;
}

/**
 * Day-group decoder. Map values seen in the real customer CSV:
 *
 *   "Default"               → [Tue, Thu]   (treat as standard)
 *   "TUES THURS"            → [Tue, Thu]
 *   "TUES FRI"              → [Tue, Fri]
 *   "THURS"                 → [Thu]
 *   "TUES"                  → [Tue]
 *   "FRI"                   → [Fri]
 *   "MON FRI"               → [Mon, Fri]
 *   "MON TUES THURS FRI"    → [Mon, Tue, Thu, Fri]
 *   "SAT"                   → [Sat]
 *   "Cromer", "Vine house…" → null (manual review)
 *
 * 0 = Mon … 6 = Sun.
 */
const DAY_TOKENS: Record<string, number> = {
  MON: 0, MONDAY: 0,
  TUE: 1, TUES: 1, TUESDAY: 1,
  WED: 2, WEDS: 2, WEDNESDAY: 2,
  THU: 3, THUR: 3, THURS: 3, THURSDAY: 3,
  FRI: 4, FRIDAY: 4,
  SAT: 5, SATURDAY: 5,
  SUN: 6, SUNDAY: 6,
};

export function parseDayGroup(group: string | null | undefined): number[] | null {
  const raw = (group ?? "").trim();
  if (!raw) return null;
  if (raw.toLowerCase() === "default") return [1, 3]; // Tue + Thu

  // Split on whitespace / common separators and look for day tokens
  const tokens = raw.toUpperCase().split(/[\s\/,]+/).filter(Boolean);
  const matched = new Set<number>();
  let unknown = 0;
  for (const t of tokens) {
    if (t in DAY_TOKENS) {
      matched.add(DAY_TOKENS[t]!);
    } else {
      unknown++;
    }
  }
  if (matched.size === 0) return null;
  // If most tokens didn't decode, give up — likely a freeform string ("Cromer")
  if (unknown > matched.size * 2) return null;
  return Array.from(matched).sort((a, b) => a - b);
}

/**
 * Soft-window extractor from delivery_instructions free text.
 * Returns ISO HH:MM strings or nulls. Conservative — only extracts when confident.
 */
export function extractSoftWindow(
  text: string | null | undefined,
): { start: string | null; end: string | null } {
  const t = (text ?? "").toUpperCase();
  if (!t) return { start: null, end: null };

  // "BETWEEN 7AM AND 9AM", "BETWEEN 9 AND 10", "BETWEEN 9:00 AND 10:30"
  const between = /BETWEEN\s+([0-9]{1,2})(?::([0-9]{2}))?\s*(AM|PM)?\s+AND\s+([0-9]{1,2})(?::([0-9]{2}))?\s*(AM|PM)?/.exec(t);
  if (between) {
    const start = to24h(between[1]!, between[2], between[3]);
    const end = to24h(between[4]!, between[5], between[6] ?? between[3]);
    if (start && end) return { start, end };
  }

  // "BEFORE 1PM", "BY 1PM"
  const before = /(?:BEFORE|BY)\s+([0-9]{1,2})(?::([0-9]{2}))?\s*(AM|PM)?/.exec(t);
  if (before) {
    const end = to24h(before[1]!, before[2], before[3]);
    if (end) return { start: null, end };
  }

  // "AFTER 9AM", "FROM 9AM"
  const after = /(?:AFTER|FROM)\s+([0-9]{1,2})(?::([0-9]{2}))?\s*(AM|PM)?/.exec(t);
  if (after) {
    const start = to24h(after[1]!, after[2], after[3]);
    if (start) return { start, end: null };
  }

  // "OPENING TIMES: 06:45 - 17:30" / "OPENING TIMES 9.00 AM TO 4.30 PM"
  const opening = /OPENING\s+TIMES?[:\s]+([0-9]{1,2})[:.]([0-9]{2})\s*(AM|PM)?\s*[-–TO]+\s*([0-9]{1,2})[:.]([0-9]{2})\s*(AM|PM)?/.exec(t);
  if (opening) {
    const start = to24h(opening[1]!, opening[2], opening[3]);
    const end = to24h(opening[4]!, opening[5], opening[6]);
    if (start && end) return { start, end };
  }

  return { start: null, end: null };
}

function to24h(hStr: string, mStr: string | undefined, ampm: string | undefined): string | null {
  let h = parseInt(hStr, 10);
  const m = mStr ? parseInt(mStr, 10) : 0;
  if (Number.isNaN(h) || Number.isNaN(m) || h > 23 || m > 59) return null;
  if (ampm === "PM" && h < 12) h += 12;
  if (ampm === "AM" && h === 12) h = 0;
  return `${h.toString().padStart(2, "0")}:${m.toString().padStart(2, "0")}`;
}

function detectCod(invoiceNotes: string | undefined | null): boolean {
  const s = (invoiceNotes ?? "").toUpperCase();
  if (!s) return false;
  return /\bCOD\b/.test(s) || /CHEQUE\/COD/.test(s);
}

// ---------- main entrypoint ----------

const COL = {
  name: "customer_name (do not edit)",
  legal: "legal_entity_name (do not edit)",
  delivery: "delivery_address (do not edit)",
  billing: "billing_address (do not edit)",
  lastDate: "latest_delivery_date (do not edit)",
  code: "customer_code",
  active: "active (Yes or No)",
  pricing: "pricing_level",
  invoiceNotes: "invoice_notes",
  picking: "standing_picking_instructions",
  delivInstr: "standing_delivery_instructions",
  runCode: "delivery_run_code",
  runPos: "delivery_run_position",
  daysGroup: "delivery_days_and_cut_off_times_group",
  paymentDays: "payment_term_days",
  salesRep: "sales_rep",
} as const;

export function parseCustomerCsv(csvText: string): {
  rows: ImportRow[];
  errors: { line: number; message: string }[];
} {
  const records: RawRow[] = parseCsv(csvText, {
    columns: true,
    bom: true,
    skip_empty_lines: true,
    relax_quotes: true,
    relax_column_count: true,
    trim: false,
  });

  const rows: ImportRow[] = [];
  const errors: { line: number; message: string }[] = [];

  records.forEach((rec, i) => {
    const name = nonEmpty(rec[COL.name]);
    const code = stripQuotes(rec[COL.code]);
    if (!code) {
      errors.push({ line: i + 2, message: "missing customer_code" });
      return;
    }
    if (!name) {
      errors.push({ line: i + 2, message: `customer_code ${code} missing name` });
      return;
    }

    const reasons: string[] = [];
    const preferredDays = parseDayGroup(rec[COL.daysGroup]);
    if (preferredDays === null && nonEmpty(rec[COL.daysGroup])) {
      reasons.push(`unparseable delivery_days_group: ${rec[COL.daysGroup]}`);
    }

    const window = extractSoftWindow(rec[COL.delivInstr]);

    const runPos = parseInt(stripQuotes(rec[COL.runPos]) || "", 10);
    const paymentDays = parseInt(rec[COL.paymentDays] ?? "", 10);

    const row: ImportRow = {
      customerCode: code,
      name,
      legalEntityName: nonEmpty(rec[COL.legal]),
      deliveryAddress: nonEmpty(rec[COL.delivery]),
      billingAddress: nonEmpty(rec[COL.billing]),
      pricingLevel: nonEmpty(rec[COL.pricing]),
      isCod: detectCod(rec[COL.invoiceNotes]),
      paymentTermDays: Number.isFinite(paymentDays) ? paymentDays : null,
      salesRep: nonEmpty(rec[COL.salesRep]),
      deliveryDaysGroup: nonEmpty(rec[COL.daysGroup]),
      preferredDays,
      legacyRunCode: stripQuotes(rec[COL.runCode]) || null,
      legacyRunPosition: Number.isFinite(runPos) ? runPos : null,
      standingPickingInstructions: nonEmpty(rec[COL.picking]),
      standingDeliveryInstructions: nonEmpty(rec[COL.delivInstr]),
      softWindowStart: window.start,
      softWindowEnd: window.end,
      lastDeliveryDate: parseUkDate(rec[COL.lastDate]),
      active: (rec[COL.active] ?? "").trim().toLowerCase() === "yes",
      rawCsvRow: Object.fromEntries(
        Object.entries(rec).filter(([_, v]) => v !== undefined),
      ) as Record<string, string>,
      flaggedForReview: reasons.length > 0,
      flagReasons: reasons,
    };
    rows.push(row);
  });

  return { rows, errors };
}
