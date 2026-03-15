"use client";

import { cn } from "@/lib/utils";
import { AlertTriangle, Clock, TrendingUp, Info, CalendarDays, Mail, ChevronRight } from "lucide-react";
import { useRouter } from "next/navigation";

export type ActionSeverity = "high" | "medium" | "low" | "info";

export interface ActionCardProps {
  clientName: string;
  clientId: string;
  tier: string;
  triggerType: string;
  description: string;
  priorityScore?: number;
  severity?: ActionSeverity;
  aum?: number;
  triggerCount?: number;
  onClick?: () => void;
}

const TIER_BADGE: Record<string, string> = {
  A: "bg-[var(--radar-green)]/15 text-[var(--radar-green)]",
  B: "bg-[var(--radar-teal)]/15 text-[var(--radar-teal)]",
  C: "bg-[var(--radar-yellow)]/15 text-[var(--radar-yellow)]",
  D: "bg-secondary text-muted-foreground",
};

const SEVERITY_CONFIG: Record<ActionSeverity, {
  border: string; badge: string; bar: string; icon: typeof AlertTriangle;
}> = {
  high:   { border: "border-l-[var(--radar-red)]",    badge: "bg-[var(--radar-red)]/15 text-[var(--radar-red)]",       bar: "bg-[var(--radar-red)]",    icon: AlertTriangle },
  medium: { border: "border-l-[var(--radar-yellow)]", badge: "bg-[var(--radar-yellow)]/15 text-[var(--radar-yellow)]", bar: "bg-[var(--radar-yellow)]", icon: Clock },
  low:    { border: "border-l-[var(--radar-teal)]",   badge: "bg-[var(--radar-teal)]/15 text-[var(--radar-teal)]",     bar: "bg-[var(--radar-teal)]",   icon: TrendingUp },
  info:   { border: "border-l-[var(--radar-blue)]",   badge: "bg-[var(--radar-blue)]/15 text-[var(--radar-blue)]",     bar: "bg-[var(--radar-blue)]",   icon: Info },
};

function scoreSeverity(score?: number): ActionSeverity {
  if (!score) return "info";
  if (score >= 70) return "high";
  if (score >= 40) return "medium";
  return "low";
}

export function fmtAum(aum?: number): string {
  if (!aum) return "";
  if (aum >= 1_000_000) return `$${(aum / 1_000_000).toFixed(1)}M`;
  return `$${(aum / 1_000).toFixed(0)}K`;
}

export function ActionCard({
  clientName,
  clientId,
  tier,
  triggerType,
  description,
  priorityScore,
  severity,
  aum,
  triggerCount,
  onClick,
}: ActionCardProps) {
  const router = useRouter();
  const sev = severity ?? scoreSeverity(priorityScore);
  const { border, badge, bar, icon: Icon } = SEVERITY_CONFIG[sev];
  const scoreWidth = priorityScore ? Math.min(100, Math.round(priorityScore)) : 0;

  function handleAction(e: React.MouseEvent, action: "meeting" | "outreach" | "details") {
    e.stopPropagation();
    if (action === "meeting") router.push(`/meeting-prep/${clientId}`);
    else if (action === "details") router.push(`/clients/${clientId}`);
    else router.push(`/clients/${clientId}?tab=outreach`);
  }

  return (
    <div
      onClick={onClick}
      className={cn(
        "bg-card border border-border border-l-4 rounded-lg px-4 pt-3.5 pb-3 cursor-pointer",
        "hover:bg-secondary/40 hover:shadow-sm transition-all duration-150",
        border,
      )}
    >
      {/* Row 1: name, tier badge, signal count, AUM */}
      <div className="flex items-center justify-between gap-3 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          <Icon className="w-3.5 h-3.5 shrink-0 opacity-80" />
          <span className="text-sm font-semibold text-foreground truncate">{clientName}</span>
          <span className={cn(
            "text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide shrink-0",
            TIER_BADGE[tier] ?? TIER_BADGE.D,
          )}>
            {tier}
          </span>
          {triggerCount !== undefined && triggerCount > 1 && (
            <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-secondary text-muted-foreground shrink-0">
              {triggerCount} signals
            </span>
          )}
        </div>
        {aum && (
          <span className="text-xs font-medium text-[var(--radar-teal)] shrink-0">{fmtAum(aum)}</span>
        )}
      </div>

      {/* Row 2: trigger type badge + description */}
      <div className="mb-2">
        <span className={cn("text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide mr-1.5", badge)}>
          {triggerType.replace(/_/g, " ")}
        </span>
        <span className="text-xs text-muted-foreground leading-relaxed">{description}</span>
      </div>

      {/* Row 3: priority score bar */}
      {priorityScore !== undefined && (
        <div className="flex items-center gap-2 mb-3">
          <div className="flex-1 bg-secondary/60 rounded-full h-1">
            <div
              className={cn("h-1 rounded-full", bar)}
              style={{ width: `${scoreWidth}%` }}
            />
          </div>
          <span className="text-[10px] text-muted-foreground font-mono w-7 text-right tabular-nums">
            {Math.round(priorityScore)}
          </span>
        </div>
      )}

      {/* Row 4: action buttons */}
      <div className="flex items-center gap-2">
        <button
          onClick={(e) => handleAction(e, "meeting")}
          className="flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded bg-[var(--radar-teal)]/10 text-[var(--radar-teal)] hover:bg-[var(--radar-teal)]/20 transition-colors"
        >
          <CalendarDays className="w-3 h-3" />
          Prepare Meeting
        </button>
        <button
          onClick={(e) => handleAction(e, "outreach")}
          className="flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded bg-[var(--radar-teal)]/8 text-[var(--radar-teal)]/70 hover:bg-[var(--radar-teal)]/20 hover:text-[var(--radar-teal)] transition-colors"
        >
          <Mail className="w-3 h-3" />
          Draft Outreach
        </button>
        <button
          onClick={(e) => handleAction(e, "details")}
          className="flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded bg-secondary text-muted-foreground hover:text-foreground transition-colors ml-auto"
        >
          View Details
          <ChevronRight className="w-3 h-3" />
        </button>
      </div>
    </div>
  );
}
