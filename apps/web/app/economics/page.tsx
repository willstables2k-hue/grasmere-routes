import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fmtGbp, fmtGbpRounded } from "@/lib/format";
import {
  getEconomicsSummary,
  getBottomCustomersByNetContribution,
} from "@/lib/queries/economics";
import { CostWaterfall } from "./cost-waterfall";
import { ProfitabilityScatter } from "./profitability-scatter";

export default async function EconomicsPage() {
  const [summary, bottom] = await Promise.all([
    getEconomicsSummary(),
    getBottomCustomersByNetContribution(20),
  ]);

  return (
    <div className="container py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Economics</h1>
        <p className="text-sm text-muted-foreground">
          Where the money goes, what the platform is saving, and which customers are
          costing you.
        </p>
      </div>

      {/* ---- Headline KPIs ---- */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader>
            <CardDescription>Baseline cost / week</CardDescription>
            <CardTitle className="text-2xl tabular">
              {fmtGbp(summary.baselineWeeklyCostPence)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Live customers only · {summary.baselineStops} stops
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Optimised this week</CardDescription>
            <CardTitle className="text-2xl tabular">
              {summary.optimisedThisWeekPence != null
                ? fmtGbp(summary.optimisedThisWeekPence)
                : "—"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Sum of planned routes for last 7 days
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Cumulative savings</CardDescription>
            <CardTitle className="text-2xl tabular">
              {fmtGbp(summary.cumulativeSavingsPence)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">Since launch</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Avg cost / delivery</CardDescription>
            <CardTitle className="text-2xl tabular">
              {fmtGbp(summary.baselineCostPerDeliveryPence)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Real per-delivery cost, no ghost stops
            </p>
          </CardContent>
        </Card>
      </div>

      {/* ---- The two ROI lines (the most important panel on this page) ---- */}
      <Card className="border-primary/30 bg-primary/5">
        <CardHeader>
          <CardTitle>Annual saving — broken down</CardTitle>
          <CardDescription>
            Two lines, deliberately additive, never blended.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-6 md:grid-cols-3">
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">1. Data hygiene</Badge>
              <span className="text-xs text-muted-foreground">recurring</span>
            </div>
            <div className="mt-2 text-3xl font-semibold tabular">
              {fmtGbpRounded(summary.dataHygieneAnnualisedSavingPence)}/year
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Recovered from no longer planning for{" "}
              {summary.baselineCustomersExcluded} ghost customers (mail-order +
              unparseable run codes filtered) plus dormant + no-history customers
              (~50% of the nominally-active list).
            </p>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="secondary">2. Routing optimisation</Badge>
              <span className="text-xs text-muted-foreground">requires solver</span>
            </div>
            <div className="mt-2 text-3xl font-semibold tabular">
              {fmtGbpRounded(summary.routingOptimisationAnnualisedSavingPence)}/year
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              What OR-Tools contributes on top, after the customer base is honest.
              Updates as more weeks are planned.
            </p>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <Badge variant="default">Total annual saving</Badge>
            </div>
            <div className="mt-2 text-4xl font-semibold tabular text-green-600">
              {fmtGbpRounded(summary.totalAnnualisedSavingPence)}/year
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Sum of the two lines. Defendable to a sceptic because each component is
              attributable to a specific change.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* ---- Annualised baseline ---- */}
      <Card>
        <CardHeader>
          <CardDescription>Current routing structure costs</CardDescription>
          <CardTitle className="text-4xl tabular">
            {fmtGbpRounded(summary.baselineAnnualisedPence)}
            <span className="text-base font-normal text-muted-foreground">/year</span>
          </CardTitle>
          <CardDescription className="mt-1">
            Live customers only · {summary.baselineCustomersIncluded} included ·{" "}
            {summary.baselineCustomersExcluded} excluded
          </CardDescription>
        </CardHeader>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <CostWaterfall
          fuel={summary.baselineWeeklyCostPence ? Math.round(summary.baselineWeeklyCostPence * 0.21) : 0}
          labour={summary.baselineWeeklyCostPence ? Math.round(summary.baselineWeeklyCostPence * 0.69) : 0}
          overhead={summary.baselineWeeklyCostPence ? Math.round(summary.baselineWeeklyCostPence * 0.10) : 0}
        />
        <ProfitabilityScatter rows={bottom} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Bottom 20 customers by net contribution</CardTitle>
          <CardDescription>
            Negative contribution means you&apos;re losing money on every delivery, after
            the marginal cost of serving them. Renegotiate or move to a different day.
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Customer</TableHead>
                <TableHead className="text-right">Avg order</TableHead>
                <TableHead className="text-right">Marginal cost</TableHead>
                <TableHead className="text-right">Net contribution</TableHead>
                <TableHead className="text-right">Freq / yr</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {bottom.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="py-12 text-center text-sm text-muted-foreground">
                    Populated once you publish your first optimised plan and stops have
                    marginal cost figures.
                  </TableCell>
                </TableRow>
              )}
              {bottom.map((r) => (
                <TableRow key={r.id}>
                  <TableCell>
                    <div className="font-medium">{r.name}</div>
                    <div className="text-xs text-muted-foreground">{r.customerCode}</div>
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {r.avgOrderValuePence != null ? fmtGbp(r.avgOrderValuePence) : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {r.marginalCostPence != null ? fmtGbp(r.marginalCostPence) : "—"}
                  </TableCell>
                  <TableCell
                    className={`text-right tabular font-medium ${
                      (r.netContributionPence ?? 0) < 0
                        ? "text-destructive"
                        : "text-green-600"
                    }`}
                  >
                    {r.netContributionPence != null ? fmtGbp(r.netContributionPence) : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular">
                    {r.frequencyPerYear ?? "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
