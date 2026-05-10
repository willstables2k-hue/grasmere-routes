import { NextResponse } from "next/server";
import { parseCustomerCsv } from "@/lib/csv-import";
import { upsertCustomers } from "@/lib/customer-upsert";

export const runtime = "nodejs";
export const maxDuration = 60;

export async function POST(req: Request) {
  const form = await req.formData();
  const file = form.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ error: "missing file" }, { status: 400 });
  }
  const text = await file.text();

  const { rows, errors: parseErrors } = parseCustomerCsv(text);
  const upsert = await upsertCustomers(rows);

  return NextResponse.json({
    inserted: upsert.inserted,
    updated: upsert.updated,
    errors: [
      ...parseErrors.map((e) => ({ customerCode: `(line ${e.line})`, error: e.message })),
      ...upsert.errors,
    ],
    flagged: rows
      .filter((r) => r.flaggedForReview)
      .map((r) => ({ customerCode: r.customerCode, reasons: r.flagReasons })),
  });
}
