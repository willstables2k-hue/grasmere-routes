"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  UserMinus,
  Calendar,
  Map,
  TrendingUp,
  Settings,
  Truck,
  TestTube,
  History,
} from "lucide-react";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/plan", label: "Plan", icon: Calendar },
  { href: "/baseline", label: "Baseline", icon: Map },
  { href: "/economics", label: "Economics", icon: TrendingUp },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/customers/dormant", label: "Dormant", icon: UserMinus },
  { href: "/runs", label: "Runs", icon: History },
  { href: "/simulate", label: "Simulate", icon: TestTube },
  { href: "/drive", label: "Drive", icon: Truck },
  { href: "/admin", label: "Admin", icon: Settings },
] as const;

export function SidebarNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1 p-3">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || (href !== "/" && pathname.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm",
              active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
