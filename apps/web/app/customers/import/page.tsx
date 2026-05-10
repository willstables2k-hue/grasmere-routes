"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface ImportSummary {
  inserted: number;
  updated: number;
  errors: { customerCode: string; error: string }[];
  flagged: { customerCode: string; reasons: string[] }[];
}

export default function ImportCustomersPage() {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    setSummary(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/customers/import", { method: "POST", body: fd });
      if (!res.ok) throw new Error(await res.text());
      const body = (await res.json()) as ImportSummary;
      setSummary(body);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container py-8 max-w-3xl">
      <h1 className="text-2xl font-semibold mb-6">Import customers</h1>
      <Card>
        <CardHeader>
          <CardTitle>Upload a Fresho customer CSV</CardTitle>
          <CardDescription>
            Upserts on <code>customer_code</code>. Geocoding runs as a background job after
            insert. Existing manual confirmations and lat/lng are preserved.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <Button onClick={submit} disabled={!file || busy}>
            {busy ? "Importing…" : "Import"}
          </Button>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </CardContent>
      </Card>

      {summary && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Import complete</CardTitle>
            <CardDescription>
              {summary.inserted} inserted · {summary.updated} updated · {summary.errors.length} errors ·{" "}
              {summary.flagged.length} flagged
            </CardDescription>
          </CardHeader>
          {(summary.errors.length > 0 || summary.flagged.length > 0) && (
            <CardContent className="space-y-3 text-sm">
              {summary.errors.length > 0 && (
                <div>
                  <h3 className="font-medium">Errors</h3>
                  <ul className="list-disc pl-5 text-destructive">
                    {summary.errors.slice(0, 20).map((e, i) => (
                      <li key={i}>
                        <span className="font-mono">{e.customerCode}</span>: {e.error}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {summary.flagged.length > 0 && (
                <div>
                  <h3 className="font-medium">Flagged for review</h3>
                  <ul className="list-disc pl-5 text-muted-foreground">
                    {summary.flagged.slice(0, 20).map((f, i) => (
                      <li key={i}>
                        <span className="font-mono">{f.customerCode}</span>: {f.reasons.join(", ")}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          )}
        </Card>
      )}
    </div>
  );
}
