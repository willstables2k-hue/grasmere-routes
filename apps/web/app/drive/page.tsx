import { sql } from "drizzle-orm";
import { execRows } from "@/lib/db-utils";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Navigation, Camera } from "lucide-react";

interface StopRow {
  routeStopId: string;
  sequence: number;
  customerName: string;
  customerCode: string;
  address: string;
  lat: number;
  lng: number;
  notes: string | null;
  pickingNotes: string | null;
  isCod: boolean;
  codAmountPence: number | null;
  softWindow: string | null;
  status: string;
}

async function fetchTodayStops(): Promise<{ date: string; stops: StopRow[] }> {
  const today = new Date().toISOString().slice(0, 10);
  const rows = await execRows<StopRow>(sql`
    SELECT
      rs.id AS "routeStopId",
      rs.sequence,
      c.name AS "customerName",
      c.customer_code AS "customerCode",
      c.delivery_address AS address,
      c.delivery_lat AS lat,
      c.delivery_lng AS lng,
      c.standing_delivery_instructions AS notes,
      c.standing_picking_instructions AS "pickingNotes",
      c.is_cod AS "isCod",
      o.cod_amount_pence AS "codAmountPence",
      CASE
        WHEN c.soft_window_start IS NOT NULL OR c.soft_window_end IS NOT NULL
        THEN COALESCE(c.soft_window_start::text, '?') || '–' || COALESCE(c.soft_window_end::text, '?')
        ELSE NULL
      END AS "softWindow",
      o.status
    FROM route_stops rs
    JOIN routes r ON r.id = rs.route_id
    JOIN orders o ON o.id = rs.order_id
    JOIN customers c ON c.id = o.customer_id
    WHERE r.delivery_date = ${today} AND r.status IN ('published','in_progress','completed')
    ORDER BY rs.sequence
  `);
  return { date: today, stops: rows };
}

function navigateUrl(s: StopRow) {
  return `https://www.google.com/maps/dir/?api=1&destination=${s.lat},${s.lng}`;
}

export default async function DrivePage() {
  const { date, stops } = await fetchTodayStops();

  return (
    <div className="container max-w-2xl py-6 space-y-3">
      <div>
        <h1 className="text-xl font-semibold">Today&apos;s route</h1>
        <p className="text-sm text-muted-foreground">{date} · {stops.length} stops</p>
      </div>

      {stops.length === 0 && (
        <Card>
          <CardContent className="pt-6 text-center text-sm text-muted-foreground">
            No published route for today.
          </CardContent>
        </Card>
      )}

      {stops.map((s, i) => (
        <Card key={s.routeStopId} className={s.status === "delivered" ? "opacity-60" : ""}>
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <div>
                <CardDescription>Stop {i + 1}</CardDescription>
                <CardTitle className="text-lg leading-tight">{s.customerName}</CardTitle>
              </div>
              <div className="flex flex-col items-end gap-1">
                {s.isCod && (
                  <Badge variant="destructive">
                    COD{s.codAmountPence != null ? ` £${(s.codAmountPence / 100).toFixed(2)}` : ""}
                  </Badge>
                )}
                {s.softWindow && <Badge variant="outline">{s.softWindow}</Badge>}
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div>{s.address}</div>
            {s.notes && (
              <div className="rounded-md bg-amber-50 p-2 text-amber-900 text-xs">
                <strong>Notes:</strong> {s.notes}
              </div>
            )}
            {s.pickingNotes && (
              <div className="text-xs text-muted-foreground">
                <strong>Picking:</strong> {s.pickingNotes}
              </div>
            )}
            <div className="flex gap-2">
              <Button asChild className="flex-1">
                <a href={navigateUrl(s)} target="_blank" rel="noreferrer">
                  <Navigation className="h-4 w-4" /> Navigate
                </a>
              </Button>
              <Button variant="outline" asChild>
                <a href={`/drive/${s.routeStopId}/deliver`}>
                  <Camera className="h-4 w-4" /> Deliver
                </a>
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
