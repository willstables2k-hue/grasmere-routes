import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";
import * as schema from "./schema";

const url = process.env.DATABASE_URL;
if (!url) {
  // eslint-disable-next-line no-console
  console.warn("[db] DATABASE_URL not set — db client will throw on use");
}

const client = postgres(url ?? "postgres://localhost/placeholder", {
  prepare: false,
  max: 5,
});

export const db = drizzle(client, { schema });
export { schema };
