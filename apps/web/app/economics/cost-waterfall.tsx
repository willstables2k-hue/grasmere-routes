"use client";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { fmtGbp } from "@/lib/format";

export function CostWaterfall({
  fuel,
  labour,
  overhead,
}: {
  fuel: number;
  labour: number;
  overhead: number;
}) {
  const data = [
    { name: "Labour", value: labour },
    { name: "Fuel", value: fuel },
    { name: "Overhead", value: overhead },
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Where the money goes</CardTitle>
        <CardDescription>Weekly fleet cost breakdown</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <XAxis dataKey="name" />
              <YAxis tickFormatter={(v) => `£${(v / 100).toFixed(0)}`} />
              <Tooltip
                formatter={(v: number) => fmtGbp(v)}
                labelStyle={{ color: "#000" }}
              />
              <Bar dataKey="value" fill="hsl(222 47% 11%)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
