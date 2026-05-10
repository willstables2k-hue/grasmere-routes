"use client";

import { useState, useTransition } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmtGbp, fmtKm, fmtMin, fmtPct } from "@/lib/format";
import { Loader2, Calendar, PlayCircle } from "lucide-react";

interface PlanResult {
  ok: boolean;
  optimisedTotalPence: number;
  baselineTotalPence: number;
  savingPence: number;
  savingPct: number;
  routes: {
    vehicle_id: string;
    stop_sequence: string[];
    total_distance_km: number;
    total_duration_min: number;
    fuel_cost_pence: number;
    labour_cost_pence: number;
    overhead_pence: number;
    total_cost_pence: number;
  }[];
  baselineRoutes: { van_colour: string; total_cost_pence: number; stop_sequence: string[] }[];
  unassigned: string[];
  solveSeconds: number;
}

export default function PlanPage() {
  const [date, setDate] = useState(nextTuesday());
  const [orders, setOrders] = useState<{ created: number; liveMatching: number; dormantHidden: number } | null>(null);
  const [plan, setPlan] = useState<PlanResult | null>(null);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);

  async function genOrders() {
    setError(null);
    start(async () => {
      const res = await fetch("/api/plan/generate-orders", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ deliveryDate: date }),
      });
      const body = await res.json();
      if (!res.ok) {
        setError(body.error ?? `HTTP ${res.status}`);
        return;
      }
      setOrders({
        created: body.ordersCreated,
        liveMatching: body.liveMatching,
        dormantHidden: body.dormantMatchingHidden,
      });
    });
  }

  async function optimise() {
    setError(null);
    setPlan(null);
    start(async () => {
      const res = await fetch("/api/plan/optimise", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ deliveryDate: date }),
      });
      const body = await res.json();
      if (!res.ok || body.ok === false) {
        setError(body.error ?? body.reason ?? `HTTP ${res.status}`);
        return;
      }
      setPlan(body);
    });
  }

  return (
    <div className="container py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Plan delivery week</h1>
        <p className="text-sm text-muted-foreground">
          Pick a date, generate orders for live customers, then re-cut routes from
          scratch. Dormant + no-history customers are excluded automatically.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6 flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-muted-foreground flex items-center gap-1">
              <Calendar className="h-3 w-3" /> Delivery date
            </label>
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-44"
            />
          </div>
          <Button onClick={genOrders} disabled={pending} variant="outline">
            Generate orders
          </Button>
          <Button onClick={optimise} disabled={pending}>
            {pending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" /> Solving…
              </>
            ) : (
              <>
                <PlayCircle className="h-4 w-4" /> Optimise
              </>
            )}
          </Button>
          {orders && (
            <span className="text-sm text-muted-foreground">
              {orders.created} new orders · {orders.liveMatching} live customers match this day
              {orders.dormantHidden > 0 && (
                <>
                  {" · "}
                  <Badge variant="dormant" className="ml-1">
                    +{orders.dormantHidden} dormant hidden
                  </Badge>
                </>
              )}
            </span>
          )}
          {error && <span className="text-sm text-destructive">{error}</span>}
        </CardContent>
      </Card>

      {plan && (
        <>
          <Card className="border-primary/30">
            <CardContent className="pt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <div className="text-xs text-muted-foreground">Optimised plan</div>
                <div className="text-3xl font-semibold tabular">
                  {fmtGbp(plan.optimisedTotalPence)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">
                  Baseline (current routing for the same customers)
                </div>
                <div className="text-3xl font-semibold tabular">
                  {fmtGbp(plan.baselineTotalPence)}
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">Saving</div>
                <div
                  className={`text-3xl font-semibold tabular ${
                    plan.savingPence > 0 ? "text-green-600" : "text-destructive"
                  }`}
                >
                  {plan.savingPence > 0 ? "+" : ""}
                  {fmtGbp(plan.savingPence)}{" "}
                  <span className="text-base font-normal text-muted-foreground">
                    ({fmtPct(plan.savingPct)})
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Routes</CardTitle>
              <CardDescription>
                Solved in {plan.solveSeconds.toFixed(2)}s.
                {plan.unassigned.length > 0 && (
                  <span className="text-destructive">
                    {" "}{plan.unassigned.length} stops could not be assigned.
                  </span>
                )}
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Vehicle</TableHead>
                    <TableHead className="text-right">Stops</TableHead>
                    <TableHead className="text-right">km</TableHead>
                    <TableHead className="text-right">Time</TableHead>
                    <TableHead className="text-right">Fuel</TableHead>
                    <TableHead className="text-right">Labour</TableHead>
                    <TableHead className="text-right">Total</TableHead>
                    <TableHead className="text-right">£/stop</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {plan.routes.map((r) => (
                    <TableRow key={r.vehicle_id}>
                      <TableCell className="font-mono text-xs">{r.vehicle_id}</TableCell>
                      <TableCell className="text-right tabular">
                        {r.stop_sequence.length}
                      </TableCell>
                      <TableCell className="text-right tabular">
                        {fmtKm(r.total_distance_km)}
                      </TableCell>
                      <TableCell className="text-right tabular">
                        {fmtMin(r.total_duration_min)}
                      </TableCell>
                      <TableCell className="text-right tabular">
                        {fmtGbp(r.fuel_cost_pence)}
                      </TableCell>
                      <TableCell className="text-right tabular">
                        {fmtGbp(r.labour_cost_pence)}
                      </TableCell>
                      <TableCell className="text-right tabular font-medium">
                        {fmtGbp(r.total_cost_pence)}
                      </TableCell>
                      <TableCell className="text-right tabular">
                        {r.stop_sequence.length > 0
                          ? fmtGbp(Math.round(r.total_cost_pence / r.stop_sequence.length))
                          : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function nextTuesday(): string {
  const d = new Date();
  const days = (2 - d.getDay() + 7) % 7 || 7;
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}
