import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function Home() {
  return (
    <div className="container py-10">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Grasmere Routes</h1>
        <p className="text-muted-foreground mt-1">
          Plan deliveries from scratch each week to minimise fleet cost. See the unit
          economics of every route, stop, and customer.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <span>This week</span>
              <Badge variant="outline">Tue 12 May</Badge>
            </CardTitle>
            <CardDescription>Optimised plan vs current routing</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/plan" className="text-sm font-medium hover:underline">
              Open planner →
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Current state</CardTitle>
            <CardDescription>Annualised baseline cost — live customers only</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/baseline" className="text-sm font-medium hover:underline">
              View baseline →
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Economics</CardTitle>
            <CardDescription>Cumulative savings + bottom 20 customers</CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/economics" className="text-sm font-medium hover:underline">
              Open dashboard →
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
