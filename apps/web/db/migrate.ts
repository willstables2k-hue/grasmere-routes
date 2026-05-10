/**
 * Run all generated migrations, then apply the SQL view + seed.
 *
 *   npm run db:migrate
 */
import "dotenv/config";
import { drizzle } from "drizzle-orm/postgres-js";
import { migrate } from "drizzle-orm/postgres-js/migrator";
import postgres from "postgres";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";

async function main() {
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL not set");

  const client = postgres(url, { max: 1 });
  const db = drizzle(client);

  const migrationsFolder = join(__dirname, "migrations");
  const hasMigrations =
    existsSync(migrationsFolder) &&
    readdirSync(migrationsFolder).some((f) => f.endsWith(".sql"));
  if (!hasMigrations) {
    console.warn(
      "[migrate] no SQL migrations found — run `npm run db:generate` first to create them from the Drizzle schema",
    );
  } else {
    console.log("[migrate] running drizzle migrations…");
    await migrate(db, { migrationsFolder });
  }

  console.log("[migrate] applying customer_status_v…");
  const viewSql = readFileSync(join(__dirname, "sql", "customer_status_view.sql"), "utf8");
  await client.unsafe(viewSql);

  console.log("[migrate] applying seed…");
  const seedSql = readFileSync(join(__dirname, "seed.sql"), "utf8");
  await client.unsafe(seedSql);

  await client.end();
  console.log("[migrate] done");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
