import { NextResponse } from "next/server";
import { sql } from "drizzle-orm";
import { db } from "@/db/client";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const body = (await req.json()) as Record<string, string | number>;
  // Whitelisted keys to prevent arbitrary column writes.
  const allowed = [
    "diesel_price_pence_per_litre",
    "default_mpg",
    "default_driver_hourly_rate_pence",
    "avg_speed_kmh",
    "service_time_min_per_stop",
    "depot_loading_time_min",
    "vehicle_fixed_cost_per_day_pence",
    "driver_max_shift_hours",
    "default_gross_margin_pct",
    "dormancy_threshold_days",
  ];

  await db.execute(sql`
    UPDATE config SET
      diesel_price_pence_per_litre = ${body.diesel_price_pence_per_litre},
      default_mpg = ${body.default_mpg},
      default_driver_hourly_rate_pence = ${body.default_driver_hourly_rate_pence},
      avg_speed_kmh = ${body.avg_speed_kmh},
      service_time_min_per_stop = ${body.service_time_min_per_stop},
      depot_loading_time_min = ${body.depot_loading_time_min},
      vehicle_fixed_cost_per_day_pence = ${body.vehicle_fixed_cost_per_day_pence},
      driver_max_shift_hours = ${body.driver_max_shift_hours},
      default_gross_margin_pct = ${body.default_gross_margin_pct},
      dormancy_threshold_days = ${body.dormancy_threshold_days},
      updated_at = now()
    WHERE id = 1
  `);
  return NextResponse.json({ ok: true });
  void allowed;
}
