import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmtGbp, fmtGbpRounded, fmtKm, fmtMin } from "@/lib/format";
import { getCurrentBaseline, getCurrentBaselineRoutes } from "@/lib/baseline-service";
import { RecomputeButton } from "./recompute-client";

const DAY_LABELS: Record<number, string> = {
  0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun",
};

const COLOUR_HEX: Record<string, string> = {
  White: "bg-white border", Pink: "bg-pink-300", Blue: "bg-blue-400",
  Green: "bg-green-500", Red: "bg-red-500", Yellow: "bg-yellow-400",
};

export default async function BaselinePage() {
  const snap = await getCurrentBaseline();

  if (!snap) {
    return (
      <div className="container py-8">
        <h1 className="text-2xl font-semibold mb-2">Baseline</h1>
        <Card>
          <CardHeader>
            <CardTitle>No baseline computed yet</CardTitle>
            <CardDescription>
              Compute a baseline once customers have been imported and geocoded. The baseline
              measures the cost of running the legacy colour-coded routes for live customers
              only — it&apos;s the headline £/year figure we measure optimisation savings against.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RecomputeButton />
          </CardContent>
        </Card>
      </div>
    );
  }

  const routes = await getCurrentBaselineRoutes(snap.id);
  const sortedRoutes = [...routes].sort((a, b) => b.costPerStopPence - a.costPerStopPence);
  const avgCostPerDelivery = snap.totalStops > 0 ? snap.totalCostPence / snap.totalStops : 0;

  return (
    <div className="container py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Baseline</h1>
          <p className="text-sm text-muted-foreground">
            Current cost of running the legacy colour-coded routes — live customers only.
            Computed {new Date(snap.computedAt).toLocaleString("en-GB")}.
          </p>
        </div>
        <RecomputeButton />
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Weekly fleet cost</CardDescription>
            <CardTitle className="text-2xl tabular">{fmtGbpRounded(snap.weeklyCostPence)}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Annualised (× 52)</CardDescription>
            <CardTitle className="text-3xl tabular">
              {fmtGbpRounded(snap.annualisedCostPence)}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Average £/delivery</CardDescription>
            <CardTitle className="text-2xl tabular">
              {fmtGbp(Math.round(avgCostPerDelivery))}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Stops · km / week</CardDescription>
            <CardTitle className="text-2xl tabular">
              {snap.totalStops} · {fmtKm(Number(snap.totalDistanceKm))}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card className="border-amber-300 bg-amber-50/40">
        <CardHeader>
          <CardTitle>Honesty caveats</CardTitle>
          <CardDescription>
            The baseline is an estimate, not a measurement. These caveats are deliberately
            permanent — clicking the cost figure should never feel like reading a black box.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="list-disc pl-5 space-y-1 text-sm">
            <li>
              Sequencing within each van is <strong>assumed</strong> (nearest-neighbour from
              depot). The CSV&apos;s <code>delivery_run_position</code> is loading-bay zone
              info, not true drive order.
            </li>
            <li>
              <strong>{snap.customerCountExcluded}</strong> customers excluded — mail-order
              (~NR), unparseable run codes (e.g. <code>5ME</code>, <code>MMR</code>), or no
              geocode yet.
            </li>
            <li>
              Dormant + no-history customers are <strong>not counted</strong> here. The
              &quot;data hygiene&quot; line on the economics dashboard quantifies what those
              ghost stops would have cost if planned for.
            </li>
            <li>
              Both baseline and optimised plans use the same Mapbox driving distances and
              the same cost model — the only difference between them is sequencing and
              van assignment.
            </li>
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Routes — sorted by £/stop, worst first</CardTitle>
          <CardDescription>
            The top of this list is where the optimiser will save the most.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Van</TableHead>
                <TableHead>Day</TableHead>
                <TableHead className="text-right">Stops</TableHead>
                <TableHead className="text-right">km</TableHead>
                <TableHead className="text-right">Time</TableHead>
                <TableHead className="text-right">Fuel</TableHead>
                <TableHead className="text-right">Labour</TableHead>
                <TableHead className="text-right">Total £</TableHead>
                <TableHead className="text-right">£/stop</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedRoutes.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-block h-3 w-3 rounded-sm ${
                          COLOUR_HEX[r.vanColour] ?? "bg-gray-300"
                        }`}
                      />
                      <span className="text-sm">{r.vanColour}</span>
                    </div>
                  </TableCell>
                  <TableCell>{DAY_LABELS[r.dayOfWeek] ?? r.dayOfWeek}</TableCell>
                  <TableCell className="text-right tabular">{r.stopCount}</TableCell>
                  <TableCell className="text-right tabular">
                    {fmtKm(Number(r.distanceKm))}
                  </TableCell>
                  <TableCell className="text-right tabular">{fmtMin(r.durationMin)}</TableCell>
                  <TableCell className="text-right tabular">
                    {fmtGbp(r.fuelCostPence)}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {fmtGbp(r.labourCostPence)}
                  </TableCell>
                  <TableCell className="text-right tabular font-medium">
                    {fmtGbp(r.totalCostPence)}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {fmtGbp(r.costPerStopPence)}
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
