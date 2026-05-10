import { sql } from "drizzle-orm";
import { execRows } from "@/lib/db-utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmtGbp, fmtKm, fmtMin } from "@/lib/format";
import { Badge } from "@/components/ui/badge";

interface Row {
  routeId: string;
  date: string;
  vehicleId: string | null;
  status: string;
  plannedKm: number | null;
  actualKm: number | null;
  plannedMin: number | null;
  actualMin: number | null;
  plannedTotalPence: number | null;
  actualTotalPence: number | null;
  stops: number;
}

async function fetchRuns(): Promise<Row[]> {
  return execRows<Row>(sql`
    SELECT
      r.id AS "routeId",
      r.delivery_date::text AS date,
      r.vehicle_id::text AS "vehicleId",
      r.status,
      r.planned_distance_km::float AS "plannedKm",
      r.actual_distance_km::float AS "actualKm",
      r.planned_duration_min AS "plannedMin",
      r.actual_duration_min AS "actualMin",
      r.planned_total_cost_pence AS "plannedTotalPence",
      r.actual_total_cost_pence AS "actualTotalPence",
      (SELECT COUNT(*)::int FROM route_stops rs WHERE rs.route_id = r.id) AS stops
    FROM routes r
    WHERE r.delivery_date >= CURRENT_DATE - INTERVAL '60 days'
    ORDER BY r.delivery_date DESC, r.created_at DESC
  `);
}

function variancePct(planned: number | null, actual: number | null): string {
  if (planned == null || actual == null || planned === 0) return "—";
  const v = ((actual - planned) / planned) * 100;
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

export default async function RunsPage() {
  const rows = await fetchRuns();
  return (
    <div className="container py-8 space-y-4">
      <h1 className="text-2xl font-semibold">Runs — planned vs actual</h1>
      <Card>
        <CardHeader>
          <CardTitle>Last 60 days</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Stops</TableHead>
                <TableHead className="text-right">Planned km</TableHead>
                <TableHead className="text-right">Actual km</TableHead>
                <TableHead className="text-right">Δ</TableHead>
                <TableHead className="text-right">Planned £</TableHead>
                <TableHead className="text-right">Actual £</TableHead>
                <TableHead className="text-right">Δ</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="py-12 text-center text-sm text-muted-foreground">
                    No runs in the last 60 days.
                  </TableCell>
                </TableRow>
              )}
              {rows.map((r) => (
                <TableRow key={r.routeId}>
                  <TableCell>{r.date}</TableCell>
                  <TableCell><Badge variant="outline">{r.status}</Badge></TableCell>
                  <TableCell className="tabular">{r.stops}</TableCell>
                  <TableCell className="text-right tabular">
                    {r.plannedKm != null ? fmtKm(r.plannedKm) : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {r.actualKm != null ? fmtKm(r.actualKm) : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular text-xs">
                    {variancePct(r.plannedKm, r.actualKm)}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {r.plannedTotalPence != null ? fmtGbp(r.plannedTotalPence) : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {r.actualTotalPence != null ? fmtGbp(r.actualTotalPence) : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular text-xs">
                    {variancePct(r.plannedTotalPence, r.actualTotalPence)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

void fmtMin; // reserved for future "planned min vs actual min" column
