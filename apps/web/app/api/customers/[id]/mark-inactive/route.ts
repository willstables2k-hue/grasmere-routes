import { NextResponse } from "next/server";
import { markInactive } from "@/lib/queries/customers";

export const runtime = "nodejs";

export async function POST(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  await markInactive([id]);
  return NextResponse.json({ ok: true });
}
