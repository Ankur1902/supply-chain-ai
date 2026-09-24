"use client";

import {
  AlertTriangle,
  BarChart3,
  Bot,
  LayoutDashboard,
  Package,
  Truck,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/shipments", label: "Shipments", icon: Package },
  { href: "/suppliers", label: "Suppliers", icon: Users },
  { href: "/alerts", label: "Alerts", icon: AlertTriangle },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/copilot", label: "AI Copilot", icon: Bot },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="hidden w-56 shrink-0 border-r bg-card md:flex md:flex-col">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <Truck className="h-4 w-4" />
        </div>
        <span className="text-sm font-semibold leading-tight">Supply Chain AI</span>
      </div>
      <nav className="flex-1 space-y-0.5 p-2">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
