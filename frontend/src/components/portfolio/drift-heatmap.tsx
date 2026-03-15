"use client";

import { cn } from "@/lib/utils";
import type { DriftEntry } from "@/lib/types";

interface DriftHeatmapProps {
  /** Array from /api/portfolio/{id}/drift — target_pct / current_pct / drift_pct are 0-100 scale */
  drifts: DriftEntry[];
  className?: string;
}

// Thresholds in percentage points (0-100 scale)
function driftColor(drift_pct: number): string {
  const abs = Math.abs(drift_pct);
  if (abs < 2) return "bg-[var(--radar-green)]/15 text-[var(--radar-green)] border-[var(--radar-green)]/30";
  if (abs < 5) return "bg-[var(--radar-yellow)]/15 text-[var(--radar-yellow)] border-[var(--radar-yellow)]/30";
  return "bg-[var(--radar-red)]/15 text-[var(--radar-red)] border-[var(--radar-red)]/30";
}

function driftLabel(drift_pct: number): string {
  const abs = Math.abs(drift_pct);
  if (abs < 2) return "On Target";
  if (abs < 5) return "Monitor";
  return "Rebalance";
}

export function DriftHeatmap({ drifts, className }: DriftHeatmapProps) {
  if (!drifts.length) {
    return (
      <p className="text-sm text-muted-foreground text-center py-4">No drift data available.</p>
    );
  }

  return (
    <div
      className={cn("grid gap-2", className)}
      style={{ gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))" }}
    >
      {drifts.map((entry) => {
        const colorCls = driftColor(entry.drift_pct);
        const label    = driftLabel(entry.drift_pct);
        const sign     = entry.drift_pct > 0 ? "+" : "";
        const barWidth = Math.min(100, Math.abs(entry.drift_pct) / 10 * 100);

        return (
          <div
            key={entry.asset_class}
            className={cn("border rounded-lg p-3 flex flex-col gap-1", colorCls)}
          >
            <p className="text-[10px] font-bold uppercase tracking-wider truncate">
              {entry.asset_class.replace(/_/g, " ")}
            </p>
            <div className="flex items-end justify-between mt-0.5">
              <div>
                <p className="text-lg font-bold tabular-nums leading-tight">
                  {sign}{entry.drift_pct.toFixed(1)}%
                </p>
                <p className="text-[10px] opacity-80">{label}</p>
              </div>
              <div className="text-right text-[10px] opacity-70 space-y-0.5">
                <p>Curr: {entry.current_pct.toFixed(1)}%</p>
                <p>Tgt: {entry.target_pct.toFixed(1)}%</p>
              </div>
            </div>
            {/* Progress bar — full bar = 10% drift */}
            <div className="mt-1 h-1 bg-current/20 rounded-full overflow-hidden">
              <div
                className="h-full bg-current rounded-full"
                style={{ width: `${barWidth}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
