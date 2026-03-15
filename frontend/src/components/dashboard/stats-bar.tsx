"use client";

import { cn } from "@/lib/utils";

interface StatItem {
  label: string;
  value: string | number;
  sub?: string;
  color?: "teal" | "green" | "yellow" | "red" | "blue" | "muted";
}

interface StatsBarProps {
  stats: StatItem[];
  className?: string;
}

const COLOR_MAP: Record<NonNullable<StatItem["color"]>, string> = {
  teal:   "text-[var(--radar-teal)]",
  green:  "text-[var(--radar-green)]",
  yellow: "text-[var(--radar-yellow)]",
  red:    "text-[var(--radar-red)]",
  blue:   "text-[var(--radar-blue)]",
  muted:  "text-muted-foreground",
};

const GRID_COLS: Record<number, string> = {
  1: "grid-cols-1",
  2: "grid-cols-2",
  3: "grid-cols-3",
  4: "grid-cols-4",
  5: "grid-cols-5",
};

const COLOR_BORDER: Record<NonNullable<StatItem["color"]>, string> = {
  teal:   "hover:border-[var(--radar-teal)]/40",
  green:  "hover:border-[var(--radar-green)]/40",
  yellow: "hover:border-[var(--radar-yellow)]/40",
  red:    "hover:border-[var(--radar-red)]/40",
  blue:   "hover:border-[var(--radar-blue)]/40",
  muted:  "hover:border-border",
};

export function StatsBar({ stats, className }: StatsBarProps) {
  return (
    <div className={cn("grid gap-4", GRID_COLS[stats.length] ?? "grid-cols-4", className)}>
      {stats.map((stat, i) => (
        <div
          key={i}
          className={cn(
            "bg-card border border-border rounded-lg px-5 py-4 transition-colors",
            COLOR_BORDER[stat.color ?? "teal"],
          )}
        >
          <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">
            {stat.label}
          </p>
          <p className={cn("text-2xl font-bold tabular-nums", COLOR_MAP[stat.color ?? "teal"])}>
            {stat.value}
          </p>
          {stat.sub && (
            <p className="text-xs text-muted-foreground mt-1">{stat.sub}</p>
          )}
        </div>
      ))}
    </div>
  );
}
