import { NextResponse } from "next/server";
import { generateOrders } from "@/lib/plan-service";

export const runtime = "nodejs";

export async function POST(req: Request) {
  const { deliveryDate } = (await req.json()) as { deliveryDate?: string };
  if (!deliveryDate) {
    return NextResponse.json({ error: "deliveryDate required" }, { status: 400 });
  }
  const out = await generateOrders(deliveryDate);
  return NextResponse.json({ ok: true, ...out });
}
