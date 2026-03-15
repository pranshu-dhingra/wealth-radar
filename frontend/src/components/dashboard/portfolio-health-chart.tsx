"use client";

import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

export interface HealthData {
  healthy: number;
  monitor: number;
  action: number;
}

const SEGMENTS = [
  { key: "action",  label: "Action Needed", color: "#FF4B4B" },
  { key: "monitor", label: "Monitor",        color: "#FFB832" },
  { key: "healthy", label: "Healthy",        color: "#00F0C8" },
] as const;

export function PortfolioHealthChart({ data }: { data: HealthData }) {
  const chartData = SEGMENTS.map((s) => ({ name: s.label, value: data[s.key], color: s.color }));
  const total = data.healthy + data.monitor + data.action;

  return (
    <div>
      <div className="relative">
        <ResponsiveContainer width="100%" height={140}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={42}
              outerRadius={60}
              paddingAngle={2}
              dataKey="value"
              strokeWidth={0}
            >
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{
                background: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "8px",
                fontSize: "11px",
                boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
              }}
              itemStyle={{ color: "hsl(var(--muted-foreground))" }}
              cursor={false}
            />
          </PieChart>
        </ResponsiveContainer>
        {/* Center total */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="text-xl font-bold text-foreground tabular-nums">{total}</span>
          <span className="text-[10px] text-muted-foreground">clients</span>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-col gap-2 mt-3">
        {SEGMENTS.map((s) => {
          const count = data[s.key];
          const pct = total > 0 ? Math.round((count / total) * 100) : 0;
          return (
            <div key={s.key} className="space-y-1">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: s.color }} />
                  <span className="text-[11px] text-muted-foreground">{s.label}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold text-foreground tabular-nums">{count}</span>
                  <span className="text-[10px] text-muted-foreground w-7 text-right tabular-nums">{pct}%</span>
                </div>
              </div>
              <div className="h-0.5 w-full bg-secondary/60 rounded-full overflow-hidden">
                <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: s.color, opacity: 0.7 }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
