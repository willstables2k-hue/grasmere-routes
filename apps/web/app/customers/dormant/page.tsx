import Link from "next/link";
import { sql } from "drizzle-orm";
import { execRows } from "@/lib/db-utils";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmtGbpRounded, fmtRelativeDays } from "@/lib/format";
import type { CustomerStatus } from "@/lib/status";
import { ConfirmLiveButton, MarkInactiveButton } from "./actions-client";

interface DormantRow {
  id: string;
  customerCode: string;
  name: string;
  status: CustomerStatus;
  daysSinceLastDelivery: number | null;
  lastDeliveryDate: string | null;
  legacyRunCode: string | null;
  salesRep: string | null;
  avgOrderValuePence: number | null;
}

interface Summary {
  dormant: number;
  noHistory: number;
  reincludeWeeklyCostPence: number; // estimated impact if all were re-added
  reEngagementUpsidePence: number; // sum of last known order values × annual freq
}

async function fetchDormant(): Promise<{ rows: DormantRow[]; summary: Summary }> {
  const list = await execRows<DormantRow>(sql`
    SELECT
      c.id,
      c.customer_code AS "customerCode",
      c.name,
      s.status,
      s.days_since_last_delivery AS "daysSinceLastDelivery",
      c.last_delivery_date::text AS "lastDeliveryDate",
      c.legacy_run_code AS "legacyRunCode",
      c.sales_rep AS "salesRep",
      c.avg_order_value_pence AS "avgOrderValuePence"
    FROM customers c
    JOIN customer_status_v s ON s.customer_id = c.id
    WHERE c.active = TRUE AND s.status IN ('dormant','no_history')
    ORDER BY s.days_since_last_delivery DESC NULLS LAST, c.name
  `);

  // Indicative re-engagement upside: sum of avg_order_value × 52 (weekly assumption)
  let upside = 0;
  for (const r of list) upside += (r.avgOrderValuePence ?? 0) * 52;

  return {
    rows: list,
    summary: {
      dormant: list.filter((r) => r.status === "dormant").length,
      noHistory: list.filter((r) => r.status === "no_history").length,
      // The optimiser would need to be called for a precise figure; this tile
      // is a coarse estimate showing 'order of magnitude' impact.
      reincludeWeeklyCostPence: list.length * 800,
      reEngagementUpsidePence: upside,
    },
  };
}

export default async function DormantPage() {
  const { rows, summary } = await fetchDormant();

  return (
    <div className="container py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Dormant + no-history customers</h1>
          <p className="text-sm text-muted-foreground">
            Excluded from auto-routing and the baseline. Confirm live, mark inactive,
            or export for sales follow-up.
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link href="/api/customers/dormant/export">Export CSV</Link>
        </Button>
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>Dormant</CardDescription>
            <CardTitle className="text-3xl tabular">{summary.dormant}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">Last delivery &gt; 180 days ago</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>No history</CardDescription>
            <CardTitle className="text-3xl tabular">{summary.noHistory}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">No delivery date recorded</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Estimated re-engagement upside</CardDescription>
            <CardTitle className="text-3xl tabular">
              {fmtGbpRounded(summary.reEngagementUpsidePence)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Σ avg order value × 52 weeks · sanity-check only
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Customer</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last delivery</TableHead>
                <TableHead>Days silent</TableHead>
                <TableHead>Run</TableHead>
                <TableHead>Sales rep</TableHead>
                <TableHead className="text-right">Avg order</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>
                    <Link href={`/customers/${r.id}`} className="font-medium hover:underline">
                      {r.name}
                    </Link>
                    <div className="text-xs text-muted-foreground">{r.customerCode}</div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={r.status} />
                  </TableCell>
                  <TableCell className="tabular text-sm">
                    {r.lastDeliveryDate ?? "never"}
                  </TableCell>
                  <TableCell className="tabular text-sm">
                    {r.daysSinceLastDelivery != null ? r.daysSinceLastDelivery : "—"}
                    <div className="text-xs text-muted-foreground">
                      {fmtRelativeDays(r.daysSinceLastDelivery)}
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{r.legacyRunCode ?? "—"}</TableCell>
                  <TableCell className="text-xs">{r.salesRep ?? "—"}</TableCell>
                  <TableCell className="text-right tabular">
                    {r.avgOrderValuePence != null ? fmtGbpRounded(r.avgOrderValuePence) : "—"}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <ConfirmLiveButton id={r.id} />
                      <MarkInactiveButton id={r.id} />
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {rows.length === 0 && (
                <TableRow>
                  <TableCell
                    colSpan={8}
                    className="py-12 text-center text-sm text-muted-foreground"
                  >
                    No dormant or no-history customers — clean list.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
