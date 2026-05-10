import { NextResponse } from "next/server";
import { optimisePlan } from "@/lib/plan-service";

export const runtime = "nodejs";
export const maxDuration = 120;

export async function POST(req: Request) {
  const { deliveryDate } = (await req.json()) as { deliveryDate?: string };
  if (!deliveryDate) {
    return NextResponse.json({ error: "deliveryDate required" }, { status: 400 });
  }
  try {
    const out = await optimisePlan(deliveryDate);
    return NextResponse.json(out);
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: e instanceof Error ? e.message : String(e) },
      { status: 500 },
    );
  }
}
