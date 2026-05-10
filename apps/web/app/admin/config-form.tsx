"use client";

import { useState, useTransition } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface Config {
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

export function ConfigForm({ config }: { config: Config }) {
  const [form, setForm] = useState(config);
  const [pending, start] = useTransition();
  const [saved, setSaved] = useState(false);

  const fields: { key: keyof Config; label: string; suffix: string; step?: string }[] = [
    { key: "diesel_price_pence_per_litre", label: "Diesel price", suffix: "pence/L" },
    { key: "default_mpg", label: "Vehicle mpg (imperial)", suffix: "mpg", step: "0.1" },
    { key: "default_driver_hourly_rate_pence", label: "Driver wage", suffix: "pence/hr" },
    { key: "avg_speed_kmh", label: "Average road speed", suffix: "km/h", step: "0.1" },
    { key: "service_time_min_per_stop", label: "Service time per stop", suffix: "min" },
    { key: "depot_loading_time_min", label: "Depot loading time", suffix: "min" },
    { key: "vehicle_fixed_cost_per_day_pence", label: "Vehicle fixed cost / day", suffix: "pence" },
    { key: "driver_max_shift_hours", label: "Max shift", suffix: "hours", step: "0.5" },
    { key: "default_gross_margin_pct", label: "Default gross margin", suffix: "0–1", step: "0.001" },
    { key: "dormancy_threshold_days", label: "Dormancy threshold", suffix: "days" },
  ];

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        setSaved(false);
        start(async () => {
          await fetch("/api/admin/config", {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify(form),
          });
          setSaved(true);
        });
      }}
    >
      <div className="grid grid-cols-2 gap-4">
        {fields.map((f) => (
          <label key={f.key} className="text-sm">
            <span className="text-muted-foreground">{f.label}</span>
            <div className="flex items-center gap-2 mt-1">
              <Input
                type="number"
                step={f.step ?? "1"}
                value={form[f.key] as any}
                onChange={(e) =>
                  setForm({ ...form, [f.key]: f.step ? e.target.value : Number(e.target.value) })
                }
              />
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {f.suffix}
              </span>
            </div>
          </label>
        ))}
      </div>
      <Button type="submit" disabled={pending}>
        {pending ? "Saving…" : "Save"}
      </Button>
      {saved && <span className="ml-2 text-sm text-green-600">Saved.</span>}
    </form>
  );
}
