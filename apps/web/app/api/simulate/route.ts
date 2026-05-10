import { NextResponse } from "next/server";
import { sql } from "drizzle-orm";
import { db } from "@/db/client";
import { optimisePlan } from "@/lib/plan-service";

export const runtime = "nodejs";
export const maxDuration = 120;

/**
 * Quick & dirty v1: temporarily soft-cancel the orders for excluded customers,
 * re-solve, then restore. A future iteration will keep the planner stateless
 * and pass excludeIds directly to the optimiser.
 */
export async function POST(req: Request) {
  const { deliveryDate, excludeCustomerCodes = [] } =
    (await req.json()) as { deliveryDate?: string; excludeCustomerCodes?: string[] };
  if (!deliveryDate) {
    return NextResponse.json({ error: "deliveryDate required" }, { status: 400 });
  }

  if (excludeCustomerCodes.length > 0) {
    await db.execute(sql`
      UPDATE orders
      SET status = 'cancelled'
      WHERE delivery_date = ${deliveryDate}
        AND customer_id IN (
          SELECT id FROM customers WHERE customer_code = ANY(${excludeCustomerCodes})
        )
        AND status IN ('pending','planned')
    `);
  }

  try {
    const out = await optimisePlan(deliveryDate);
    return NextResponse.json(out);
  } finally {
    if (excludeCustomerCodes.length > 0) {
      await db.execute(sql`
        UPDATE orders
        SET status = 'pending'
        WHERE delivery_date = ${deliveryDate}
          AND customer_id IN (
            SELECT id FROM customers WHERE customer_code = ANY(${excludeCustomerCodes})
          )
          AND status = 'cancelled'
      `);
    }
  }
}
