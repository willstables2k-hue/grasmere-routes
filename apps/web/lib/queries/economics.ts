/**
 * Server-side queries for /economics — KPIs, ROI breakdown, leaderboards.
 *
 * Two ROI lines, never blended:
 *   - data hygiene saving = baseline-with-dormant minus baseline-live-only
 *   - routing optimisation saving = baseline-live-only minus optimised plans
 */
import { sql, eq } from "drizzle-orm";
import { db, schema } from "@/db/client";
import { execRows } from "@/lib/db-utils";

export interface EconomicsSummary {
  baselineWeeklyCostPence: number;
  baselineAnnualisedPence: number;
  baselineCostPerDeliveryPence: number;
  baselineStops: number;
  baselineCustomersIncluded: number;
  baselineCustomersExcluded: number;
  optimisedThisWeekPence: number | null;
  optimisedAnnualisedPence: number | null;
  cumulativeSavingsPence: number;
  dataHygieneAnnualisedSavingPence: number;
  routingOptimisationAnnualisedSavingPence: number;
  totalAnnualisedSavingPence: number;
}

export async function getEconomicsSummary(): Promise<EconomicsSummary> {
  const baseline = await db
    .select()
    .from(schema.baselineSnapshot)
    .where(eq(schema.baselineSnapshot.isCurrent, true))
    .limit(1);
  const b = baseline[0];

  const optimisedRows = await execRows<{
    weekly: string;
    annualised: string;
    cumulative: string;
  }>(sql`
    SELECT
      COALESCE(SUM(planned_total_cost_pence), 0)::bigint AS weekly,
      COALESCE(SUM(planned_total_cost_pence), 0)::bigint * 52 AS annualised,
      COALESCE(SUM(planned_total_cost_pence), 0)::bigint AS cumulative
    FROM routes
    WHERE delivery_date >= CURRENT_DATE - INTERVAL '7 days'
  `);
  const opt = optimisedRows[0];

  // Indicative data-hygiene saving: scaled from the spec's ~£40k/year figure,
  // computed properly only after we have a "with-dormant" baseline run.
  // For v1 we approximate from customer counts.
  const counts = await execRows<{
    live: number;
    dormant: number;
    no_history: number;
  }>(sql`
    SELECT
      SUM(CASE WHEN s.status = 'live' THEN 1 ELSE 0 END)::int AS live,
      SUM(CASE WHEN s.status = 'dormant' THEN 1 ELSE 0 END)::int AS dormant,
      SUM(CASE WHEN s.status = 'no_history' THEN 1 ELSE 0 END)::int AS no_history
    FROM customers c
    JOIN customer_status_v s ON s.customer_id = c.id
    WHERE c.active = TRUE
  `);
  const cnt = counts[0] ?? { live: 0, dormant: 0, no_history: 0 };

  // Spec scale: average £8.28/delivery true cost; ghost stops carry the same
  // average cost burden if they had been planned. Frequency assumption:
  // dormant + no_history customers would have averaged 1.5 deliveries/week each.
  const ghostStopsWeek = (cnt.dormant + cnt.no_history) * 1.5;
  const dataHygieneWeeklySavingPence = Math.round(ghostStopsWeek * 828);
  const dataHygieneAnnualisedSavingPence = dataHygieneWeeklySavingPence * 52;

  const baselineWeekly = b?.weeklyCostPence ?? 0;
  const baselineAnnualised = b?.annualisedCostPence ?? 0;
  const optimisedWeekly = Number(opt?.weekly ?? 0);
  const optimisedAnnualised = optimisedWeekly * 52;

  const routingOptimisationAnnualisedSavingPence =
    baselineAnnualised > 0 && optimisedAnnualised > 0
      ? baselineAnnualised - optimisedAnnualised
      : 0;

  return {
    baselineWeeklyCostPence: baselineWeekly,
    baselineAnnualisedPence: baselineAnnualised,
    baselineCostPerDeliveryPence: b && b.totalStops > 0
      ? Math.round(baselineWeekly / b.totalStops)
      : 0,
    baselineStops: b?.totalStops ?? 0,
    baselineCustomersIncluded: b?.customerCountIncluded ?? 0,
    baselineCustomersExcluded: b?.customerCountExcluded ?? 0,
    optimisedThisWeekPence: optimisedWeekly || null,
    optimisedAnnualisedPence: optimisedAnnualised || null,
    cumulativeSavingsPence: 0, // populated once we have completed routes vs baseline
    dataHygieneAnnualisedSavingPence,
    routingOptimisationAnnualisedSavingPence,
    totalAnnualisedSavingPence:
      dataHygieneAnnualisedSavingPence + routingOptimisationAnnualisedSavingPence,
  };
}

export interface BottomCustomerRow {
  id: string;
  name: string;
  customerCode: string;
  avgOrderValuePence: number | null;
  marginalCostPence: number | null;
  netContributionPence: number | null;
  frequencyPerYear: number | null;
}

export async function getBottomCustomersByNetContribution(
  limit = 20,
): Promise<BottomCustomerRow[]> {
  // From route_stops.planned_net_contribution_pence — populated once a plan is published.
  return execRows<BottomCustomerRow>(sql`
    SELECT
      c.id,
      c.name,
      c.customer_code AS "customerCode",
      c.avg_order_value_pence AS "avgOrderValuePence",
      AVG(rs.planned_marginal_cost_pence)::int AS "marginalCostPence",
      AVG(rs.planned_net_contribution_pence)::int AS "netContributionPence",
      COUNT(*)::int AS "frequencyPerYear"
    FROM customers c
    JOIN orders o ON o.customer_id = c.id
    JOIN route_stops rs ON rs.order_id = o.id
    WHERE rs.planned_net_contribution_pence IS NOT NULL
    GROUP BY c.id
    ORDER BY "netContributionPence" ASC
    LIMIT ${limit}
  `);
}
