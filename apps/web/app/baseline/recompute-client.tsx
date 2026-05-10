"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Loader2, RefreshCcw } from "lucide-react";

export function RecomputeButton() {
  const router = useRouter();
  const [pending, start] = useTransition();
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="flex flex-col items-end gap-1">
      <Button
        variant="outline"
        disabled={pending}
        onClick={() =>
          start(async () => {
            setError(null);
            const res = await fetch("/api/baseline/recompute", { method: "POST" });
            if (!res.ok) {
              const body = await res.json().catch(() => ({}));
              setError(body?.error ?? `HTTP ${res.status}`);
              return;
            }
            router.refresh();
          })
        }
      >
        {pending ? (
          <>
            <Loader2 className="h-4 w-4 animate-spin" /> Recomputing…
          </>
        ) : (
          <>
            <RefreshCcw className="h-4 w-4" /> Recompute baseline
          </>
        )}
      </Button>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
