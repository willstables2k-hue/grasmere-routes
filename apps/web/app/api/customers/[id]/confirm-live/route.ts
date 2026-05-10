import { NextResponse } from "next/server";
import { confirmLive } from "@/lib/queries/customers";

export const runtime = "nodejs";

export async function POST(
  _req: Request,
  ctx: { params: Promise<{ id: string }> },
) {
  const { id } = await ctx.params;
  await confirmLive(id);
  return NextResponse.json({ ok: true });
}
