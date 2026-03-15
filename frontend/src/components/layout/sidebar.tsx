"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  Search,
  CalendarCheck,
  Activity,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/",           label: "Dashboard",     icon: LayoutDashboard },
  { href: "/clients",    label: "Clients",        icon: Users },
  { href: "/search",     label: "Doc Search",     icon: Search },
  { href: "/meeting-prep", label: "Meeting Prep", icon: CalendarCheck },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex flex-col w-[250px] min-h-screen bg-card border-r border-border shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-border">
        <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-[var(--radar-teal)] glow-teal-sm shrink-0">
          <Activity className="w-4 h-4 text-background" strokeWidth={2.5} />
        </div>
        <div>
          <span className="text-[15px] font-bold tracking-tight text-white">WealthRadar</span>
          <span className="block text-[10px] text-muted-foreground leading-tight tracking-wide">AI Chief of Staff</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const active =
            href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 group",
                active
                  ? "bg-[var(--radar-teal)]/12 text-[var(--radar-teal)] border border-[var(--radar-teal)]/25 shadow-sm"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary/70"
              )}
            >
              <Icon className={cn(
                "w-4 h-4 shrink-0 transition-colors",
                active ? "text-[var(--radar-teal)]" : "group-hover:text-foreground"
              )} />
              <span className="flex-1">{label}</span>
              {active && <ChevronRight className="w-3 h-3 opacity-40" />}
            </Link>
          );
        })}
      </nav>

      {/* Advisor profile footer */}
      <div className="px-4 py-4 border-t border-border">
        <div className="flex items-center gap-3 px-1 py-2 rounded-lg hover:bg-secondary/50 transition-colors cursor-default">
          <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[var(--radar-teal)]/20 text-[var(--radar-teal)] text-xs font-bold ring-1 ring-[var(--radar-teal)]/25 shrink-0">
            SC
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate">Sarah Chen</p>
            <p className="text-xs text-muted-foreground truncate">CFP® · Senior Advisor</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
