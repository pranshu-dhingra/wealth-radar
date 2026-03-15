"use client";

import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

interface RadarVizProps {
  data: { subject: string; value: number; fullMark?: number }[];
  className?: string;
}

export function RadarVisualization({ data, className }: RadarVizProps) {
  const full = data.map((d) => ({ ...d, fullMark: d.fullMark ?? 100 }));

  return (
    <div className={className} style={{ width: "100%", height: 260 }}>
      <ResponsiveContainer>
        <RadarChart data={full} cx="50%" cy="50%" outerRadius="72%">
          <PolarGrid stroke="hsl(217.2 32.6% 22%)" />
          <PolarAngleAxis
            dataKey="subject"
            tick={{ fill: "hsl(215 20.2% 65.1%)", fontSize: 11 }}
          />
          <Radar
            dataKey="value"
            stroke="var(--radar-teal)"
            fill="var(--radar-teal)"
            fillOpacity={0.18}
            strokeWidth={2}
          />
          <Tooltip
            contentStyle={{
              background: "hsl(220 26% 8%)",
              border: "1px solid hsl(217.2 32.6% 17.5%)",
              borderRadius: "6px",
              color: "hsl(210 40% 98%)",
              fontSize: 12,
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
