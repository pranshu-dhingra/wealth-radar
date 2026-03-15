"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";
import { cn } from "@/lib/utils";

const CLASS_COLORS: Record<string, string> = {
  US_EQUITY:    "#00D4B4",
  INTL_EQUITY:  "#00F0C8",
  US_BOND:      "#3290FF",
  INTL_BOND:    "#7BB5FF",
  REAL_ESTATE:  "#FFB832",
  COMMODITIES:  "#FF8C32",
  CASH:         "#888888",
  ALTERNATIVES: "#CC66FF",
};

function pickColor(key: string, idx: number): string {
  const fallbacks = ["#00D4B4", "#00F0C8", "#3290FF", "#FFB832", "#FF4B4B", "#CC66FF"];
  return CLASS_COLORS[key] ?? fallbacks[idx % fallbacks.length];
}

// Values from the backend are 0–100 scale (e.g., 25.0 means 25%)
function normalizePct(val: number): number {
  return Math.round(val * 10) / 10;
}

const TOOLTIP_STYLE = {
  contentStyle: {
    background: "hsl(220 26% 8%)",
    border: "1px solid hsl(217.2 32.6% 17.5%)",
    borderRadius: "6px",
    fontSize: "11px",
  },
  itemStyle: { color: "hsl(215 20.2% 65.1%)" },
};

interface AllocationChartProps {
  actual: Record<string, number>;
  target?: Record<string, number>;
  className?: string;
}

function DonutPanel({
  data,
  label,
  opacity = 1,
}: {
  data: { name: string; key: string; value: number; color: string }[];
  label: string;
  opacity?: number;
}) {
  return (
    <div>
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3 text-center">
        {label}
      </p>
      <ResponsiveContainer width="100%" height={180}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={50}
            outerRadius={75}
            paddingAngle={2}
            dataKey="value"
            strokeWidth={0}
          >
            {data.map((e, i) => <Cell key={i} fill={e.color} opacity={opacity} />)}
          </Pie>
          <Tooltip
            {...TOOLTIP_STYLE}
            formatter={(v: number) => [`${v}%`, ""]}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="space-y-1 mt-2">
        {data.map((d) => (
          <div key={d.key} className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5">
              <div
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: d.color, opacity }}
              />
              <span className="text-muted-foreground truncate max-w-[120px]">{d.name}</span>
            </div>
            <span className="font-mono font-medium text-foreground tabular-nums">{d.value}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function AllocationChart({ actual, target, className }: AllocationChartProps) {
  const actualData = Object.entries(actual).map(([key, val], i) => ({
    name: key.replace(/_/g, " "),
    key,
    value: normalizePct(val),
    color: pickColor(key, i),
  }));

  const targetData = target
    ? Object.entries(target).map(([key, val], i) => ({
        name: key.replace(/_/g, " "),
        key,
        value: normalizePct(val),
        color: pickColor(key, i),
      }))
    : null;

  return (
    <div className={cn("grid gap-6", targetData ? "grid-cols-2" : "grid-cols-1", className)}>
      <DonutPanel data={actualData} label="Current Allocation" />
      {targetData && <DonutPanel data={targetData} label="Target Allocation" opacity={0.65} />}
    </div>
  );
}
