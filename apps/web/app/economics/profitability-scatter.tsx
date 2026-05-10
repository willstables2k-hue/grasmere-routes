"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { fmtGbp } from "@/lib/format";

interface Row {
  name: string;
  avgOrderValuePence: number | null;
  marginalCostPence: number | null;
  frequencyPerYear: number | null;
}

export function ProfitabilityScatter({ rows }: { rows: Row[] }) {
  const data = rows
    .filter((r) => r.avgOrderValuePence && r.marginalCostPence)
    .map((r) => ({
      x: (r.avgOrderValuePence ?? 0) / 100,
      y: (r.marginalCostPence ?? 0) / 100,
      z: (r.frequencyPerYear ?? 1) * 4,
      name: r.name,
    }));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Customer profitability</CardTitle>
        <CardDescription>
          Order value vs marginal cost. Above the diagonal = unprofitable.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[280px]">
          {data.length === 0 ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              No data yet — publish a plan first.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <XAxis dataKey="x" name="Order £" tickFormatter={(v) => `£${v}`} />
                <YAxis dataKey="y" name="Marginal £" tickFormatter={(v) => `£${v}`} />
                <ZAxis dataKey="z" range={[40, 200]} />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3" }}
                  formatter={(v: number, key: string) =>
                    key === "z" ? `${v / 4}×/yr` : fmtGbp(v * 100)
                  }
                  labelFormatter={(_l, p) => p?.[0]?.payload?.name ?? ""}
                />
                <Scatter data={data} fill="hsl(222 47% 30%)" />
              </ScatterChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
