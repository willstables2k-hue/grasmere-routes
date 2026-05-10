import { NextResponse } from "next/server";
import { recomputeBaseline } from "@/lib/baseline-service";

export const runtime = "nodejs";
export const maxDuration = 120;

export async function POST() {
  try {
    const out = await recomputeBaseline();
    return NextResponse.json({ ok: true, ...out });
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: e instanceof Error ? e.message : String(e) },
      { status: 500 },
    );
  }
}
