"use client";

import { cn } from "@/lib/utils";
import { TrendingDown, TrendingUp, AlertCircle, Info } from "lucide-react";
import type { MarketEvent } from "@/lib/types";

const SEVERITY_CONFIG = {
  HIGH:   { color: "text-[var(--radar-red)]",    bg: "bg-[var(--radar-red)]/8",    border: "border-[var(--radar-red)]/20",    icon: TrendingDown },
  MEDIUM: { color: "text-[var(--radar-yellow)]", bg: "bg-[var(--radar-yellow)]/8", border: "border-[var(--radar-yellow)]/20", icon: AlertCircle },
  LOW:    { color: "text-[var(--radar-green)]",  bg: "bg-[var(--radar-green)]/8",  border: "border-[var(--radar-green)]/20",  icon: TrendingUp },
  INFO:   { color: "text-[var(--radar-blue)]",   bg: "bg-[var(--radar-blue)]/8",   border: "border-[var(--radar-blue)]/20",   icon: Info },
} as const;

export function MarketAlerts({ events }: { events: MarketEvent[] }) {
  return (
    <div className="space-y-2">
      {events.map((event) => {
        const cfg = SEVERITY_CONFIG[event.severity] ?? SEVERITY_CONFIG.INFO;
        const Icon = cfg.icon;
        return (
          <div
            key={event.id}
            className={cn("rounded-lg p-2.5 border transition-all duration-150 hover:brightness-110", cfg.bg, cfg.border)}
          >
            <div className="flex items-start gap-2">
              <Icon className={cn("w-3.5 h-3.5 mt-0.5 shrink-0", cfg.color)} />
              <div className="min-w-0">
                <p className={cn("text-[11px] font-semibold leading-tight", cfg.color)}>
                  {event.title}
                </p>
                <p className="text-[10px] text-muted-foreground mt-0.5">
                  {new Date(event.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                  {event.trigger_types && event.trigger_types.length > 0 && (
                    <span className="ml-1.5 opacity-60">
                      · {event.trigger_types.slice(0, 2).join(", ").replace(/_/g, " ")}
                    </span>
                  )}
                </p>
                {event.recommended_action && (
                  <p className="text-[10px] text-muted-foreground/80 mt-1 leading-relaxed line-clamp-2">
                    {event.recommended_action}
                  </p>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
