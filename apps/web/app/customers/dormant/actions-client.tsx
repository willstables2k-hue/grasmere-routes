"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { CheckCircle2, XCircle } from "lucide-react";

async function postAction(action: "confirm-live" | "mark-inactive", id: string) {
  await fetch(`/api/customers/${id}/${action}`, { method: "POST" });
}

export function ConfirmLiveButton({ id }: { id: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  return (
    <Button
      variant="outline"
      size="sm"
      disabled={pending}
      onClick={() =>
        start(async () => {
          await postAction("confirm-live", id);
          router.refresh();
        })
      }
    >
      <CheckCircle2 className="h-4 w-4 mr-1" /> Live
    </Button>
  );
}

export function MarkInactiveButton({ id }: { id: string }) {
  const router = useRouter();
  const [pending, start] = useTransition();
  return (
    <Button
      variant="ghost"
      size="sm"
      disabled={pending}
      onClick={() => {
        if (!confirm("Mark inactive? They'll disappear from the platform.")) return;
        start(async () => {
          await postAction("mark-inactive", id);
          router.refresh();
        });
      }}
    >
      <XCircle className="h-4 w-4 mr-1" /> Inactive
    </Button>
  );
}
