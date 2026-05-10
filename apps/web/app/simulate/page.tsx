"use client";

import { useState, useTransition } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { fmtGbp } from "@/lib/format";

interface SimResult {
  optimisedTotalPence: number;
  baselineTotalPence: number;
  savingPence: number;
  savingPct: number;
}

export default function SimulatePage() {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [excludedCodes, setExcludedCodes] = useState<string>("");
  const [result, setResult] = useState<SimResult | null>(null);
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setError(null);
    start(async () => {
      const res = await fetch("/api/simulate", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          deliveryDate: date,
          excludeCustomerCodes: excludedCodes
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean),
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        setError(body.error ?? `HTTP ${res.status}`);
        return;
      }
      setResult(body);
    });
  }

  return (
    <div className="container py-8 space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold">What-if simulator</h1>
        <p className="text-sm text-muted-foreground">
          Drop customers, postcodes, or whole groups out of a delivery day and see the
          fleet-cost impact instantly.
        </p>
      </div>

      <Card>
        <CardContent className="space-y-3 pt-6">
          <div>
            <label className="text-xs text-muted-foreground">Delivery date</label>
            <Input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-44 mt-1"
            />
          </div>
          <div>
            <label className="text-xs text-muted-foreground">
              Exclude customer codes (comma separated)
            </label>
            <Input
              value={excludedCodes}
              onChange={(e) => setExcludedCodes(e.target.value)}
              placeholder="ABOTTRIP, 23COFF"
              className="mt-1"
            />
          </div>
          <Button onClick={run} disabled={pending}>
            {pending ? "Solving…" : "Re-solve"}
          </Button>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <CardTitle>Result</CardTitle>
            <CardDescription>For the chosen day, with exclusions applied.</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-3 gap-4">
            <div>
              <div className="text-xs text-muted-foreground">Optimised</div>
              <div className="text-2xl font-semibold tabular">
                {fmtGbp(result.optimisedTotalPence)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Baseline</div>
              <div className="text-2xl font-semibold tabular">
                {fmtGbp(result.baselineTotalPence)}
              </div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">Saving</div>
              <div className="text-2xl font-semibold tabular text-green-600">
                {fmtGbp(result.savingPence)}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
