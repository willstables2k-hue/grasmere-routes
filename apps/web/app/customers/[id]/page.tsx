import { notFound } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { fmtGbp, fmtRelativeDays } from "@/lib/format";
import { getCustomerById } from "@/lib/queries/customers";

export default async function CustomerDetail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const c = await getCustomerById(id);
  if (!c) notFound();

  return (
    <div className="container py-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{c.name}</h1>
          <p className="text-sm text-muted-foreground">{c.customerCode}</p>
        </div>
        <div className="flex gap-2">
          <StatusBadge status={c.status} />
          {c.isCod && <Badge variant="destructive">COD</Badge>}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardDescription>Last delivery</CardDescription>
            <CardTitle className="text-2xl tabular">
              {c.lastDeliveryDate ?? "never"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              {fmtRelativeDays(c.daysSinceLastDelivery)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Average order value</CardDescription>
            <CardTitle className="text-2xl tabular">
              {c.avgOrderValuePence != null ? fmtGbp(c.avgOrderValuePence) : "—"}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <CardDescription>Pricing level</CardDescription>
            <CardTitle className="text-2xl">{c.pricingLevel ?? "—"}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Delivery profile</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm md:grid-cols-2">
          <div>
            <span className="text-muted-foreground">Address:</span>{" "}
            {c.deliveryAddress ?? "—"}
          </div>
          <div>
            <span className="text-muted-foreground">Geocode:</span>{" "}
            {c.deliveryLat != null && c.deliveryLng != null
              ? `${c.deliveryLat.toFixed(5)}, ${c.deliveryLng.toFixed(5)} (${c.geocodeConfidence ?? "?"})`
              : "not geocoded"}
          </div>
          <div>
            <span className="text-muted-foreground">Day group:</span>{" "}
            {c.deliveryDaysGroup ?? "—"}
          </div>
          <div>
            <span className="text-muted-foreground">Legacy run code:</span>{" "}
            <span className="font-mono">{c.legacyRunCode ?? "—"}</span>{" "}
            <span className="text-xs text-muted-foreground">(reference only)</span>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Profitability</CardTitle>
          <CardDescription>
            Rolling 12-week unit economics — populated once orders flow through the platform.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No completed routes yet.</p>
        </CardContent>
      </Card>
    </div>
  );
}
