import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { listCustomers, statusCounts } from "@/lib/queries/customers";
import { fmtGbp, fmtRelativeDays } from "@/lib/format";
import type { CustomerStatus } from "@/lib/status";

interface SearchParams {
  status?: string;
  search?: string;
  run?: string;
  cod?: string;
}

export default async function CustomersPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;

  // Defaults: live only. Status pill at top reveals what's hidden.
  const statusIn: CustomerStatus[] =
    params.status === "all"
      ? ["live", "dormant", "no_history"]
      : params.status
        ? (params.status.split(",") as CustomerStatus[])
        : ["live"];

  const [customers, counts] = await Promise.all([
    listCustomers({
      statusIn,
      search: params.search,
      runCode: params.run,
      cod: params.cod === "true" ? true : params.cod === "false" ? false : undefined,
    }),
    statusCounts(),
  ]);

  const hidden = counts.dormant + counts.no_history;

  return (
    <div className="container py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Customers</h1>
          <p className="text-sm text-muted-foreground">
            {customers.length} shown · {counts.live} live · {counts.dormant} dormant ·{" "}
            {counts.no_history} no history
          </p>
        </div>
        <Button asChild>
          <Link href="/customers/import">Import CSV</Link>
        </Button>
      </div>

      {statusIn.length === 1 && statusIn[0] === "live" && hidden > 0 && (
        <div className="mb-4 flex items-center justify-between rounded-md border bg-muted/40 px-4 py-3 text-sm">
          <span>
            <strong>+{counts.dormant} dormant, +{counts.no_history} no-history</strong>{" "}
            customers hidden from this view
          </span>
          <div className="flex gap-2">
            <Button asChild variant="outline" size="sm">
              <Link href="/customers/dormant">Review dormant</Link>
            </Button>
            <Button asChild variant="ghost" size="sm">
              <Link href="?status=all">Clear filter</Link>
            </Button>
          </div>
        </div>
      )}

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Customer</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Last delivery</TableHead>
                <TableHead>Run</TableHead>
                <TableHead>Days</TableHead>
                <TableHead>Pricing</TableHead>
                <TableHead className="text-right">Avg order</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {customers.map((c) => (
                <TableRow key={c.id}>
                  <TableCell>
                    <Link
                      href={`/customers/${c.id}`}
                      className="font-medium hover:underline"
                    >
                      {c.name}
                    </Link>
                    <div className="text-xs text-muted-foreground">{c.customerCode}</div>
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={c.status} />
                    {c.isCod && (
                      <Badge variant="destructive" className="ml-2">
                        COD
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="tabular text-sm">
                    {c.lastDeliveryDate ?? "never"}
                    <div className="text-xs text-muted-foreground">
                      {fmtRelativeDays(c.daysSinceLastDelivery)}
                    </div>
                  </TableCell>
                  <TableCell className="font-mono text-xs">{c.legacyRunCode ?? "—"}</TableCell>
                  <TableCell className="font-mono text-xs">
                    {c.deliveryDaysGroup ?? "—"}
                  </TableCell>
                  <TableCell className="text-xs">{c.pricingLevel ?? "—"}</TableCell>
                  <TableCell className="text-right tabular">
                    {c.avgOrderValuePence != null ? fmtGbp(c.avgOrderValuePence) : "—"}
                  </TableCell>
                </TableRow>
              ))}
              {customers.length === 0 && (
                <TableRow>
                  <TableCell colSpan={7} className="py-12 text-center text-sm text-muted-foreground">
                    No customers match these filters.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
