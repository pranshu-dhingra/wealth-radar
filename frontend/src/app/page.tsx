"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Zap, RefreshCw, AlertTriangle, BarChart3, Radio } from "lucide-react";
import { StatsBar } from "@/components/dashboard/stats-bar";
import { PriorityList } from "@/components/dashboard/priority-list";
import { AgentStream } from "@/components/agents/agent-stream";
import { PortfolioHealthChart } from "@/components/dashboard/portfolio-health-chart";
import { MarketAlerts } from "@/components/dashboard/market-alerts";
import { useAgentStream } from "@/hooks/use-agent-stream";
import { useClients } from "@/hooks/use-clients";
import { marketEvents } from "@/data/mock-data";
import type { TriggerScanResult, DailyScanResult } from "@/lib/types";

// Meeting frequency thresholds in days by tier (A=quarterly, B=~4mo, C=semi-annual, D=annual)
const MEETING_FREQ: Record<string, number> = { A: 91, B: 121, C: 182, D: 365 };

function fmtAum(aum: number): string {
  if (aum >= 1_000_000_000) return `$${(aum / 1_000_000_000).toFixed(1)}B`;
  if (aum >= 1_000_000)     return `$${(aum / 1_000_000).toFixed(1)}M`;
  return `$${(aum / 1_000).toFixed(0)}K`;
}

export default function DashboardPage() {
  const router = useRouter();
  const { clients, loading: clientsLoading } = useClients();
  const { events, running, done, start, reset } = useAgentStream();
  const [priorityClients, setPriorityClients] = useState<TriggerScanResult[]>([]);
  const [scanResult, setScanResult]           = useState<DailyScanResult | null>(null);

  // Extract result from SSE scan events
  useEffect(() => {
    const resultEvent = [...events].reverse().find((e) => e.type === "result");
    if (!resultEvent) return;
    try {
      const raw = typeof resultEvent.data === "string"
        ? JSON.parse(resultEvent.data)
        : resultEvent.data as DailyScanResult;
      if (raw && Array.isArray(raw.top_clients)) {
        // Normalize backend shape → frontend TriggerScanResult:
        // - filter out error dicts (no triggers array)
        // - backend uses "final_priority", frontend expects "priority_score"
        // - backend trigger items use "type" key, frontend expects "trigger_type"
        const normalized = (raw.top_clients as Record<string, unknown>[])
          .filter((c) => !c.error && Array.isArray(c.triggers))
          .map((c) => ({
            ...c,
            priority_score: (c.priority_score ?? c.final_priority ?? 0) as number,
            triggers: (c.triggers as Record<string, unknown>[]).map((t) => ({
              ...t,
              trigger_type: (t.trigger_type ?? t.type ?? "REVIEW") as string,
              description: (t.description ?? t.details ?? "") as string,
              urgency: (t.urgency ?? t.base_urgency ?? 0) as number,
            })),
          }));
        const sorted = [...normalized as unknown as TriggerScanResult[]].sort(
          (a, b) => b.priority_score - a.priority_score,
        );
        setPriorityClients(sorted);
        // Normalize cohort_patterns: backend returns list[dict], frontend expects string[]
        const rawPatterns = Array.isArray(raw.cohort_patterns) ? raw.cohort_patterns : [];
        const normalizedPatterns: string[] = rawPatterns.map((p: unknown) => {
          if (typeof p === "string") return p;
          if (p && typeof p === "object") {
            const pat = p as Record<string, unknown>;
            return String(pat.description ?? pat.recommended_action ?? pat.pattern_name ?? pat.pattern_type ?? JSON.stringify(p));
          }
          return String(p);
        });
        setScanResult({ ...(raw as DailyScanResult), cohort_patterns: normalizedPatterns });
      }
    } catch { /* malformed — ignore */ }
  }, [events]);

  function handleScan() {
    reset();
    start("/api/agents/daily-scan", { top_n: 10 });
  }

  // ── Computed stats from client list ──────────────────────────────────────────
  const totalAum    = clients.reduce((sum, c) => sum + c.aum, 0);
  const driftCount  = clients.filter((c) => c.has_portfolio_drift).length;
  const overdueCount = clients.filter((c) => {
    if (!c.last_meeting_date) return true;
    const days = (Date.now() - new Date(c.last_meeting_date).getTime()) / 86_400_000;
    return days > (MEETING_FREQ[c.tier] ?? 365);
  }).length;

  const highPriorityCount = scanResult?.high_priority_count
    ?? priorityClients.filter((c) => c.priority_score > 70).length;

  // ── Portfolio health distribution ─────────────────────────────────────────────
  const actionSet  = new Set(priorityClients.filter((c) => c.priority_score > 70).map((c) => c.client_id));
  const monitorSet = new Set(priorityClients.filter((c) => c.priority_score >= 40 && c.priority_score <= 70).map((c) => c.client_id));

  const healthData = done
    ? {
        action:  actionSet.size,
        monitor: monitorSet.size,
        healthy: Math.max(0, clients.length - actionSet.size - monitorSet.size),
      }
    : {
        action:  driftCount,
        monitor: Math.max(0, overdueCount - driftCount),
        healthy: Math.max(0, clients.length - overdueCount),
      };

  return (
    <div className="space-y-6 max-w-[1400px]">

      {/* ── Page header ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-foreground">Morning Briefing</h2>
          <p className="text-sm text-muted-foreground mt-0.5" suppressHydrationWarning>
            {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
          </p>
        </div>
        <button
          onClick={handleScan}
          disabled={running}
          className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-semibold bg-[var(--radar-teal)] text-background hover:opacity-90 transition-opacity disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {running
            ? <RefreshCw className="w-4 h-4 animate-spin" />
            : <Zap className="w-4 h-4" />}
          {running ? "Scanning…" : "Run Daily Scan"}
        </button>
      </div>

      {/* ── Stats bar ────────────────────────────────────────────────────────── */}
      <StatsBar
        stats={[
          {
            label: "Total Clients",
            value: clientsLoading ? "—" : clients.length,
            sub:   clientsLoading ? "loading…" : `Total AUM: ${fmtAum(totalAum)}`,
            color: "teal",
          },
          {
            label: "Portfolio Drift",
            value: clientsLoading ? "—" : driftCount,
            sub:   "clients need rebalancing",
            color: driftCount > 5 ? "yellow" : "green",
          },
          {
            label: "Meetings Overdue",
            value: clientsLoading ? "—" : overdueCount,
            sub:   "past tier frequency",
            color: overdueCount > 10 ? "red" : overdueCount > 5 ? "yellow" : "green",
          },
          {
            label: "High Priority",
            value: !done && priorityClients.length === 0 ? "—" : highPriorityCount,
            sub:   done ? "from last scan" : "run scan to detect",
            color: highPriorityCount > 5 ? "red" : highPriorityCount > 0 ? "yellow" : "green",
          },
        ]}
        className="grid-cols-4"
      />

      {/* ── Main grid: 2/3 priority list + 1/3 sidebar ───────────────────────── */}
      <div className="grid grid-cols-3 gap-6 items-start">

        {/* Left: Priority Action List */}
        <div className="col-span-2 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-[var(--radar-yellow)]" />
              Priority Clients
              {priorityClients.length > 0 && (
                <span className="text-xs font-normal text-muted-foreground">
                  — {priorityClients.length} detected
                </span>
              )}
            </h3>
            <button
              onClick={() => router.push("/clients")}
              className="text-xs text-[var(--radar-teal)] hover:underline"
            >
              View all clients →
            </button>
          </div>

          {/* Skeleton while scan is running and no results yet */}
          {running && priorityClients.length === 0 ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="bg-card border border-border border-l-4 border-l-border rounded-lg px-4 pt-3.5 pb-3 animate-pulse">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="h-3.5 bg-secondary rounded w-1/3" />
                    <div className="h-3.5 bg-secondary rounded w-8" />
                    <div className="h-3.5 bg-secondary rounded w-16 ml-auto" />
                  </div>
                  <div className="h-3 bg-secondary rounded w-2/3 mb-3" />
                  <div className="h-1 bg-secondary rounded w-full mb-3" />
                  <div className="flex gap-2">
                    <div className="h-5 bg-secondary rounded w-24" />
                    <div className="h-5 bg-secondary rounded w-20" />
                  </div>
                </div>
              ))}
            </div>
          ) : priorityClients.length > 0 ? (
            <PriorityList clients={priorityClients} />
          ) : (
            <div className="bg-card border border-border rounded-lg p-10 text-center">
              <Zap className="w-8 h-8 text-muted-foreground/20 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                Click <strong className="text-foreground">Run Daily Scan</strong> to detect priority clients
              </p>
              <p className="text-xs text-muted-foreground/60 mt-1">
                The AI agent will analyze all {clients.length} clients and surface actionable opportunities
              </p>
            </div>
          )}
        </div>

        {/* Right: Sidebar panels */}
        <div className="space-y-4">

          {/* Portfolio Health Donut */}
          <div className="bg-card border border-border rounded-lg p-4">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2 mb-3">
              <BarChart3 className="w-4 h-4 text-[var(--radar-teal)]" />
              Portfolio Health
              {!done && (
                <span className="text-[10px] font-normal text-muted-foreground ml-auto">pre-scan estimate</span>
              )}
            </h3>
            <PortfolioHealthChart data={healthData} />
          </div>

          {/* Market Alerts */}
          <div className="bg-card border border-border rounded-lg p-4">
            <h3 className="text-sm font-semibold text-foreground mb-3">Market Alerts</h3>
            <MarketAlerts events={marketEvents} />
          </div>

          {/* Cohort Patterns — shown only after a scan */}
          {(scanResult?.cohort_patterns?.length ?? 0) > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <h3 className="text-sm font-semibold text-foreground mb-3">Cohort Patterns</h3>
              <div className="space-y-2">
                {scanResult!.cohort_patterns!.map((pattern, i) => (
                  <p key={i} className="text-xs text-muted-foreground leading-relaxed">
                    · {pattern}
                  </p>
                ))}
              </div>
            </div>
          )}

          {/* Agent Activity */}
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              <Radio className="w-4 h-4 text-[var(--radar-teal)]" />
              Agent Activity
            </h3>
            <AgentStream events={events} running={running} className="h-52 max-h-52" />
          </div>

        </div>
      </div>
    </div>
  );
}
