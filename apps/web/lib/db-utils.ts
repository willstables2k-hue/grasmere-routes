/**
 * Helpers around Drizzle's `db.execute<T>` which requires `T extends Record<string, unknown>`.
 * We almost always know the exact column shape, so this wrapper keeps the call sites tidy.
 */
import type { sql } from "drizzle-orm";
import { db } from "@/db/client";

type SqlChunk = ReturnType<typeof sql>;

export async function execRows<T>(query: SqlChunk): Promise<T[]> {
  const rows = await db.execute(query);
  return rows as unknown as T[];
}
