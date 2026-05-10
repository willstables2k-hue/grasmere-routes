/**
 * Server-side customer queries.
 *
 * The customer_status_v view does the live/dormant/no_history derivation
 * in Postgres so we don't have to maintain it in TS at the same time.
 */
import { sql } from "drizzle-orm";
import { db } from "@/db/client";
import { execRows } from "@/lib/db-utils";
import type { CustomerStatus } from "@/lib/status";

export interface CustomerRow {
  id: string;
  customerCode: string;
  name: string;
  status: CustomerStatus;
  daysSinceLastDelivery: number | null;
  lastDeliveryDate: string | null;
  legacyRunCode: string | null;
  preferredDays: number[] | null;
  deliveryDaysGroup: string | null;
  pricingLevel: string | null;
  isCod: boolean;
  salesRep: string | null;
  deliveryAddress: string | null;
  deliveryLat: number | null;
  deliveryLng: number | null;
  geocodeConfidence: string | null;
  avgOrderValuePence: number | null;
}

export interface ListOptions {
  statusIn?: CustomerStatus[];
  search?: string;
  runCode?: string;
  cod?: boolean;
  limit?: number;
  offset?: number;
}

export async function listCustomers(opts: ListOptions = {}): Promise<CustomerRow[]> {
  const statusFilter =
    opts.statusIn && opts.statusIn.length > 0
      ? sql`AND s.status = ANY(${opts.statusIn})`
      : sql``;
  const searchFilter = opts.search
    ? sql`AND (c.name ILIKE ${"%" + opts.search + "%"} OR c.customer_code ILIKE ${
        "%" + opts.search + "%"
      })`
    : sql``;
  const runFilter = opts.runCode ? sql`AND c.legacy_run_code = ${opts.runCode}` : sql``;
  const codFilter =
    opts.cod === undefined ? sql`` : sql`AND c.is_cod = ${opts.cod}`;
  const limit = opts.limit ?? 200;
  const offset = opts.offset ?? 0;

  return execRows<CustomerRow>(sql`
    SELECT
      c.id,
      c.customer_code AS "customerCode",
      c.name,
      s.status,
      s.days_since_last_delivery AS "daysSinceLastDelivery",
      c.last_delivery_date::text AS "lastDeliveryDate",
      c.legacy_run_code AS "legacyRunCode",
      c.preferred_days AS "preferredDays",
      c.delivery_days_group AS "deliveryDaysGroup",
      c.pricing_level AS "pricingLevel",
      c.is_cod AS "isCod",
      c.sales_rep AS "salesRep",
      c.delivery_address AS "deliveryAddress",
      c.delivery_lat AS "deliveryLat",
      c.delivery_lng AS "deliveryLng",
      c.geocode_confidence AS "geocodeConfidence",
      c.avg_order_value_pence AS "avgOrderValuePence"
    FROM customers c
    JOIN customer_status_v s ON s.customer_id = c.id
    WHERE c.active = TRUE
    ${statusFilter}
    ${searchFilter}
    ${runFilter}
    ${codFilter}
    ORDER BY c.name
    LIMIT ${limit} OFFSET ${offset}
  `);
}

export interface StatusCounts {
  live: number;
  dormant: number;
  no_history: number;
  total: number;
}

export async function statusCounts(): Promise<StatusCounts> {
  const rows = await execRows<{ status: CustomerStatus; n: number }>(sql`
    SELECT s.status, COUNT(*)::int AS n
    FROM customers c
    JOIN customer_status_v s ON s.customer_id = c.id
    WHERE c.active = TRUE
    GROUP BY s.status
  `);
  const out: StatusCounts = { live: 0, dormant: 0, no_history: 0, total: 0 };
  for (const r of rows) {
    out[r.status] = r.n;
    out.total += r.n;
  }
  return out;
}

export async function getCustomerById(id: string) {
  const rows = await execRows<CustomerRow>(sql`
    SELECT c.*, s.status, s.days_since_last_delivery AS "daysSinceLastDelivery"
    FROM customers c
    JOIN customer_status_v s ON s.customer_id = c.id
    WHERE c.id = ${id}
    LIMIT 1
  `);
  return rows[0] ?? null;
}

/** Force-confirm a customer live (used by /customers/dormant). */
export async function confirmLive(id: string) {
  await db.execute(sql`
    UPDATE customers SET manually_confirmed_live_at = now(), updated_at = now() WHERE id = ${id}
  `);
}

export async function markInactive(ids: string[]) {
  if (ids.length === 0) return;
  await db.execute(sql`
    UPDATE customers
    SET active = FALSE, manually_confirmed_live_at = NULL, updated_at = now()
    WHERE id = ANY(${ids})
  `);
}
