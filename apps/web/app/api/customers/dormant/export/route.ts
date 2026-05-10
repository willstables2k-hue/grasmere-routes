import { sql } from "drizzle-orm";
import { execRows } from "@/lib/db-utils";

export const runtime = "nodejs";

interface Row {
  customerCode: string;
  name: string;
  status: string;
  lastDeliveryDate: string | null;
  daysSinceLastDelivery: number | null;
  legacyRunCode: string | null;
  salesRep: string | null;
  avgOrderValuePence: number | null;
}

export async function GET() {
  const list = await execRows<Row>(sql`
    SELECT
      c.customer_code AS "customerCode",
      c.name,
      s.status,
      c.last_delivery_date::text AS "lastDeliveryDate",
      s.days_since_last_delivery AS "daysSinceLastDelivery",
      c.legacy_run_code AS "legacyRunCode",
      c.sales_rep AS "salesRep",
      c.avg_order_value_pence AS "avgOrderValuePence"
    FROM customers c
    JOIN customer_status_v s ON s.customer_id = c.id
    WHERE c.active = TRUE AND s.status IN ('dormant','no_history')
    ORDER BY s.days_since_last_delivery DESC NULLS LAST, c.name
  `);

  const header = [
    "customer_code",
    "name",
    "status",
    "last_delivery_date",
    "days_since_last_delivery",
    "legacy_run_code",
    "sales_rep",
    "avg_order_value_gbp",
  ].join(",");
  const lines = list.map((r) =>
    [
      r.customerCode,
      escape(r.name),
      r.status,
      r.lastDeliveryDate ?? "",
      r.daysSinceLastDelivery ?? "",
      r.legacyRunCode ?? "",
      escape(r.salesRep ?? ""),
      r.avgOrderValuePence != null ? (r.avgOrderValuePence / 100).toFixed(2) : "",
    ].join(","),
  );

  return new Response([header, ...lines].join("\n"), {
    headers: {
      "content-type": "text/csv; charset=utf-8",
      "content-disposition": `attachment; filename="grasmere-dormant-${new Date()
        .toISOString()
        .slice(0, 10)}.csv"`,
    },
  });
}

function escape(v: string): string {
  if (/[",\n]/.test(v)) return `"${v.replace(/"/g, '""')}"`;
  return v;
}
