import { sql } from "drizzle-orm";
import { execRows } from "@/lib/db-utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfigForm } from "./config-form";

interface ConfigRow {
  diesel_price_pence_per_litre: number;
  default_mpg: string;
  default_driver_hourly_rate_pence: number;
  avg_speed_kmh: string;
  service_time_min_per_stop: number;
  depot_loading_time_min: number;
  vehicle_fixed_cost_per_day_pence: number;
  driver_max_shift_hours: string;
  default_gross_margin_pct: string;
  dormancy_threshold_days: number;
}

export default async function AdminPage() {
  const rows = await execRows<ConfigRow>(sql`SELECT * FROM config WHERE id = 1`);
  const cfg = rows[0];

  return (
    <div className="container py-8 space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold">Admin</h1>
        <p className="text-sm text-muted-foreground">
          Cost parameters used by the optimiser and the cost model. Changing any value
          here recomputes per-route economics — the baseline must be re-run manually.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Cost parameters</CardTitle>
          <CardDescription>
            Defaults from the build spec. Edit and save; effects apply to the next plan.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ConfigForm config={cfg} />
        </CardContent>
      </Card>
    </div>
  );
}
