/**
 * Server-side bulk upsert of parsed customer rows into Postgres.
 * Called from /api/customers/import after CSV parsing succeeds.
 *
 * Upsert key: customer_code. We never overwrite manuallyConfirmedLiveAt
 * or geocode columns from a CSV reimport — those are set by the platform.
 */
import { sql } from "drizzle-orm";
import { db, schema } from "@/db/client";
import type { ImportRow } from "./csv-import";

export interface UpsertResult {
  inserted: number;
  updated: number;
  errors: { customerCode: string; error: string }[];
}

export async function upsertCustomers(rows: ImportRow[]): Promise<UpsertResult> {
  const result: UpsertResult = { inserted: 0, updated: 0, errors: [] };

  for (const r of rows) {
    try {
      const ret = await db
        .insert(schema.customers)
        .values({
          customerCode: r.customerCode,
          name: r.name,
          legalEntityName: r.legalEntityName,
          deliveryAddress: r.deliveryAddress,
          billingAddress: r.billingAddress,
          pricingLevel: r.pricingLevel,
          isCod: r.isCod,
          paymentTermDays: r.paymentTermDays,
          salesRep: r.salesRep,
          deliveryDaysGroup: r.deliveryDaysGroup,
          preferredDays: r.preferredDays ?? undefined,
          legacyRunCode: r.legacyRunCode,
          legacyRunPosition: r.legacyRunPosition,
          standingPickingInstructions: r.standingPickingInstructions,
          standingDeliveryInstructions: r.standingDeliveryInstructions,
          softWindowStart: r.softWindowStart,
          softWindowEnd: r.softWindowEnd,
          lastDeliveryDate: r.lastDeliveryDate,
          active: r.active,
          rawCsvRow: r.rawCsvRow,
          updatedAt: new Date(),
        })
        .onConflictDoUpdate({
          target: schema.customers.customerCode,
          set: {
            name: sql`EXCLUDED.name`,
            legalEntityName: sql`EXCLUDED.legal_entity_name`,
            deliveryAddress: sql`EXCLUDED.delivery_address`,
            billingAddress: sql`EXCLUDED.billing_address`,
            pricingLevel: sql`EXCLUDED.pricing_level`,
            isCod: sql`EXCLUDED.is_cod`,
            paymentTermDays: sql`EXCLUDED.payment_term_days`,
            salesRep: sql`EXCLUDED.sales_rep`,
            deliveryDaysGroup: sql`EXCLUDED.delivery_days_group`,
            preferredDays: sql`EXCLUDED.preferred_days`,
            legacyRunCode: sql`EXCLUDED.legacy_run_code`,
            legacyRunPosition: sql`EXCLUDED.legacy_run_position`,
            standingPickingInstructions: sql`EXCLUDED.standing_picking_instructions`,
            standingDeliveryInstructions: sql`EXCLUDED.standing_delivery_instructions`,
            softWindowStart: sql`EXCLUDED.soft_window_start`,
            softWindowEnd: sql`EXCLUDED.soft_window_end`,
            // CRITICAL: never go BACKWARDS on lastDeliveryDate. CSV is a snapshot;
            // platform-derived deliveries may be more recent.
            lastDeliveryDate: sql`GREATEST(${schema.customers.lastDeliveryDate}, EXCLUDED.last_delivery_date)`,
            active: sql`EXCLUDED.active`,
            rawCsvRow: sql`EXCLUDED.raw_csv_row`,
            updatedAt: sql`now()`,
            // Deliberately NOT set: deliveryLat/Lng, geocodeConfidence,
            // geocodedAt, manuallyConfirmedLiveAt — those belong to the platform.
          },
        })
        .returning({ id: schema.customers.id, inserted: sql<boolean>`xmax = 0` });

      if (ret[0]?.inserted) result.inserted++;
      else result.updated++;
    } catch (err) {
      result.errors.push({
        customerCode: r.customerCode,
        error: err instanceof Error ? err.message : String(err),
      });
    }
  }

  return result;
}
