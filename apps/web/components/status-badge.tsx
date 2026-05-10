import { Badge } from "@/components/ui/badge";
import type { CustomerStatus } from "@/lib/status";

export function StatusBadge({ status }: { status: CustomerStatus }) {
  if (status === "live") return <Badge variant="live">Live</Badge>;
  if (status === "no_history") return <Badge variant="nohistory">No history</Badge>;
  return <Badge variant="dormant">Dormant</Badge>;
}
