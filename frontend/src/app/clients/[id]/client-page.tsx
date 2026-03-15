"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import {
  ArrowLeft, User, Briefcase, Mail, Phone, MapPin, Calendar,
  AlertTriangle, TrendingDown, TrendingUp, Zap, FileText,
  Clock, CheckCircle2, DollarSign,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useClient } from "@/hooks/use-clients";
import { usePortfolio, useDrift, useOpportunities } from "@/hooks/use-portfolio";
import { useAgentStream } from "@/hooks/use-agent-stream";
import { AllocationChart } from "@/components/portfolio/allocation-chart";
import { DriftHeatmap } from "@/components/portfolio/drift-heatmap";
import { HoldingsTable } from "@/components/portfolio/holdings-table";
import { AgentStream } from "@/components/agents/agent-stream";
import { AgentSteps } from "@/components/agents/agent-steps";
import { ApprovalWorkflow } from "@/components/agents/approval-modal";
import type { Client, TriggerScanResult } from "@/lib/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmt$(v?: number | null) {
  if (v == null) return "—";
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000)     return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v}`;
}

const TIER_COLOR: Record<string, string> = {
  A: "bg-[var(--radar-green)]/15 text-[var(--radar-green)]",
  B: "bg-[var(--radar-teal)]/15 text-[var(--radar-teal)]",
  C: "bg-[var(--radar-yellow)]/15 text-[var(--radar-yellow)]",
  D: "bg-secondary text-muted-foreground",
};

const URGENCY_COLOR = (u: number) =>
  u >= 70 ? "text-[var(--radar-red)]" : u >= 40 ? "text-[var(--radar-yellow)]" : "text-[var(--radar-green)]";

// RMD age rules: 73 for born 1951-1959, 75 for born 1960+
function getRmdAge(dob?: string): number | null {
  if (!dob) return null;
  const birthYear = new Date(dob).getFullYear();
  if (birthYear <= 1950) return 70; // legacy
  if (birthYear <= 1959) return 73;
  return 75;
}

function computeAge(dob?: string): number | null {
  if (!dob) return null;
  const today = new Date();
  const birth = new Date(dob);
  let age = today.getFullYear() - birth.getFullYear();
  if (today.getMonth() < birth.getMonth() || (today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate())) {
    age--;
  }
  return age;
}

const MILESTONE_DEFS = [
  { age: 59.5, label: "Penalty-free IRA withdrawals begin",         icon: "🔓" },
  { age: 62,   label: "Early Social Security eligibility",           icon: "💰" },
  { age: 65,   label: "Medicare enrollment window",                  icon: "🏥" },
  { age: 70.5, label: "QCD eligibility begins ($111K/yr limit)",     icon: "🎁" },
  { age: 73,   label: "RMD begins (born 1951–1959)",                 icon: "📋" },
  { age: 75,   label: "RMD begins (born 1960+)",                     icon: "📋" },
];

// ── Sub-sections ──────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color = "teal" }: { label: string; value: string | number; sub?: string; color?: string }) {
  const colorCls: Record<string, string> = {
    teal: "text-[var(--radar-teal)]", green: "text-[var(--radar-green)]",
    yellow: "text-[var(--radar-yellow)]", red: "text-[var(--radar-red)]", muted: "text-muted-foreground",
  };
  return (
    <div className="bg-card border border-border rounded-lg px-4 py-3">
      <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-0.5">{label}</p>
      <p className={cn("text-xl font-bold tabular-nums", colorCls[color] ?? colorCls.teal)}>{value}</p>
      {sub && <p className="text-[10px] text-muted-foreground mt-0.5">{sub}</p>}
    </div>
  );
}

function SectionTitle({ children, icon }: { children: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <h3 className="text-sm font-semibold text-foreground flex items-center gap-2 mb-3">
      {icon}
      {children}
    </h3>
  );
}

function Skeleton({ className }: { className?: string }) {
  return <div className={cn("bg-secondary rounded animate-pulse", className)} />;
}

// ── Overview Tab ─────────────────────────────────────────────────────────────

function OverviewTab({ client }: { client: Client }) {
  const age = computeAge(client.date_of_birth) ?? client.age;
  const rmdAge = getRmdAge(client.date_of_birth);
  const yearAsClient = client.last_meeting_date
    ? Math.max(1, new Date().getFullYear() - new Date(client.last_meeting_date).getFullYear() + 1)
    : null;

  // Upcoming milestones
  const milestones = age
    ? MILESTONE_DEFS.filter((m) => m.age > (age!) && m.age <= (age!) + 7)
    : [];

  return (
    <div className="space-y-6">
      {/* Top stats */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard label="Total AUM"       value={fmt$(client.aum)}          sub="book value" />
        <StatCard label="Risk Tolerance"  value={client.risk_tolerance ?? "—"} sub="investment profile" color="yellow" />
        <StatCard label="Tax Bracket"     value={client.tax_bracket ?? "—"} sub="income bracket" color="muted" />
        <StatCard label="Last Meeting"    value={client.last_meeting_date ? new Date(client.last_meeting_date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }) : "—"} sub="most recent contact" color="muted" />
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Demographics card */}
        <div className="col-span-2 space-y-4">
          <div className="bg-card border border-border rounded-lg p-5">
            <SectionTitle icon={<User className="w-4 h-4 text-[var(--radar-teal)]" />}>
              Client Profile
            </SectionTitle>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2.5">
                {client.occupation && (
                  <div className="flex items-center gap-2 text-xs">
                    <Briefcase className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <span className="text-muted-foreground">{client.occupation}</span>
                  </div>
                )}
                {client.email && (
                  <div className="flex items-center gap-2 text-xs">
                    <Mail className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <span className="text-muted-foreground">{client.email}</span>
                  </div>
                )}
                {client.phone && (
                  <div className="flex items-center gap-2 text-xs">
                    <Phone className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <span className="text-muted-foreground">{client.phone}</span>
                  </div>
                )}
                {client.state && (
                  <div className="flex items-center gap-2 text-xs">
                    <MapPin className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                    <span className="text-muted-foreground">{client.state}</span>
                  </div>
                )}
              </div>
              <div className="space-y-2.5 text-xs text-muted-foreground">
                {age && <p>Age: <span className="text-foreground font-medium">{age}</span></p>}
                {client.marital_status && <p>Status: <span className="text-foreground font-medium">{client.marital_status}</span></p>}
                {client.date_of_birth && <p>DOB: <span className="text-foreground font-medium">{new Date(client.date_of_birth).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</span></p>}
                {rmdAge && age && <p>RMD Age: <span className={cn("font-medium", age >= rmdAge ? "text-[var(--radar-red)]" : "text-foreground")}>{rmdAge} {age >= rmdAge ? "(eligible now)" : `(in ${rmdAge - age} yrs)`}</span></p>}
              </div>
            </div>
          </div>

          {/* Account summary */}
          {client.accounts && client.accounts.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-5">
              <SectionTitle icon={<DollarSign className="w-4 h-4 text-[var(--radar-teal)]" />}>
                Account Summary
              </SectionTitle>
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-border text-[10px] text-muted-foreground uppercase tracking-wider">
                    <th className="pb-2 text-left">Account</th>
                    <th className="pb-2 text-left">Type</th>
                    <th className="pb-2 text-left">Custodian</th>
                    <th className="pb-2 text-right">Balance</th>
                  </tr>
                </thead>
                <tbody>
                  {client.accounts.map((acct, i) => (
                    <tr key={i} className="border-b border-border/40">
                      <td className="py-2 font-mono text-foreground">{acct.account_number}</td>
                      <td className="py-2">
                        <span className="px-1.5 py-0.5 rounded bg-secondary text-muted-foreground text-[10px] uppercase tracking-wide">
                          {acct.account_type}
                        </span>
                      </td>
                      <td className="py-2 text-muted-foreground">{acct.institution ?? acct.custodian ?? "—"}</td>
                      <td className="py-2 text-right font-mono font-medium text-[var(--radar-teal)]">
                        {fmt$(acct.balance)}
                      </td>
                    </tr>
                  ))}
                  <tr>
                    <td colSpan={3} className="pt-2 text-xs text-muted-foreground font-semibold">Total</td>
                    <td className="pt-2 text-right font-mono font-semibold text-foreground">
                      {fmt$(client.accounts.reduce((s, a) => s + a.balance, 0))}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right: triggers + milestones */}
        <div className="space-y-4">
          {/* Portfolio drift alert */}
          {client.has_portfolio_drift && (
            <div className="bg-[var(--radar-yellow)]/10 border border-[var(--radar-yellow)]/30 rounded-lg p-3">
              <div className="flex items-center gap-2 text-[var(--radar-yellow)] text-xs font-semibold mb-1">
                <AlertTriangle className="w-3.5 h-3.5" /> Portfolio Drift Detected
              </div>
              <p className="text-[10px] text-muted-foreground">
                One or more asset classes have drifted {'>'} 5% from target. Rebalancing recommended.
              </p>
            </div>
          )}

          {/* Upcoming milestones */}
          {milestones.length > 0 && (
            <div className="bg-card border border-border rounded-lg p-4">
              <SectionTitle icon={<Calendar className="w-4 h-4 text-[var(--radar-teal)]" />}>
                Upcoming Milestones
              </SectionTitle>
              <div className="space-y-2.5">
                {milestones.map((m) => (
                  <div key={m.age} className="flex items-start gap-2">
                    <span className="text-base">{m.icon}</span>
                    <div>
                      <p className="text-xs font-semibold text-foreground">Age {m.age}</p>
                      <p className="text-[10px] text-muted-foreground">{m.label}</p>
                      {age && (
                        <p className="text-[10px] text-[var(--radar-teal)]">
                          In {(m.age - age).toFixed(1)} years
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Portfolio Tab ─────────────────────────────────────────────────────────────

function PortfolioTab({ clientId, client }: { clientId: string; client: Client }) {
  const { portfolio, loading: pLoad } = usePortfolio(clientId);
  const { drift, loading: dLoad }     = useDrift(clientId);
  const { data: opps }                = useOpportunities(clientId);

  const holdings = portfolio?.holdings ?? client.holdings ?? [];
  const actualAlloc  = portfolio?.current_allocation ?? client.current_allocation ?? {};
  const targetAlloc  = portfolio?.target_allocation  ?? client.target_allocation  ?? {};
  const hasDriftData = drift?.drifts && drift.drifts.length > 0;

  // TLH opportunities — opps structure: { tlh: { opportunities: [...] }, roth: {...}, qcd: {...} }
  const tlhOpps = ((opps as Record<string, unknown> | null)?.tlh as { opportunities?: { ticker: string; harvest_value?: number; loss_amount?: number; wash_sale_safe?: boolean }[] } | undefined)?.opportunities ?? [];

  if (pLoad || dLoad) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Allocation charts */}
      <div className="bg-card border border-border rounded-lg p-5">
        <SectionTitle icon={<TrendingUp className="w-4 h-4 text-[var(--radar-teal)]" />}>
          Asset Allocation
        </SectionTitle>
        {Object.keys(actualAlloc).length > 0 ? (
          <AllocationChart actual={actualAlloc} target={Object.keys(targetAlloc).length > 0 ? targetAlloc : undefined} />
        ) : (
          <p className="text-sm text-muted-foreground">No allocation data available.</p>
        )}
      </div>

      {/* Drift heatmap */}
      {hasDriftData && (
        <div className="bg-card border border-border rounded-lg p-5">
          <SectionTitle icon={<AlertTriangle className="w-4 h-4 text-[var(--radar-yellow)]" />}>
            Portfolio Drift
            <span className={cn("ml-2 text-xs font-normal",
              drift!.rebalancing_needed ? "text-[var(--radar-yellow)]" : "text-[var(--radar-green)]")}>
              {drift!.rebalancing_needed ? "⚠ Rebalancing needed" : "✓ Within thresholds"}
            </span>
          </SectionTitle>
          <DriftHeatmap drifts={drift!.drifts!} />
        </div>
      )}

      {/* TLH opportunities */}
      {tlhOpps.length > 0 && (
        <div className="bg-[var(--radar-teal)]/5 border border-[var(--radar-teal)]/20 rounded-lg p-5">
          <SectionTitle icon={<DollarSign className="w-4 h-4 text-[var(--radar-teal)]" />}>
            Tax-Loss Harvesting Opportunities
          </SectionTitle>
          <div className="space-y-2">
            {tlhOpps.map((opp, i) => (
              <div key={i} className="flex items-center justify-between bg-background/50 rounded p-3 text-xs">
                <div>
                  <span className="font-mono font-bold text-foreground">{opp.ticker}</span>
                  {opp.wash_sale_safe && (
                    <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-[var(--radar-green)]/15 text-[var(--radar-green)]">
                      Wash-Sale Safe
                    </span>
                  )}
                </div>
                <span className="font-mono font-semibold text-[var(--radar-teal)]">
                  {fmt$(opp.loss_amount)} potential deduction
                </span>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-muted-foreground mt-3">
            Tax-loss harvesting applies only to taxable accounts. Wash-sale rule: 30 days before and after sale.
          </p>
        </div>
      )}

      {/* Holdings table */}
      <div className="bg-card border border-border rounded-lg p-5">
        <SectionTitle icon={<Briefcase className="w-4 h-4 text-[var(--radar-teal)]" />}>
          Holdings ({holdings.length})
        </SectionTitle>
        <HoldingsTable holdings={holdings} />
      </div>
    </div>
  );
}

// ── Planning Tab ──────────────────────────────────────────────────────────────

function PlanningCard({ title, icon, children, highlight = false }: {
  title: string; icon: React.ReactNode; children: React.ReactNode; highlight?: boolean;
}) {
  return (
    <div className={cn(
      "border rounded-lg p-5",
      highlight ? "bg-[var(--radar-teal)]/5 border-[var(--radar-teal)]/30" : "bg-card border-border",
    )}>
      <SectionTitle icon={icon}>{title}</SectionTitle>
      {children}
    </div>
  );
}

function PlanningTab({ client }: { client: Client }) {
  const age = computeAge(client.date_of_birth) ?? client.age ?? 0;
  const rmdAge = getRmdAge(client.date_of_birth) ?? 73;
  const isRmdEligible = age >= rmdAge;
  const isQcdEligible = age >= 70.5;
  const isRothWindow  = !isRmdEligible && age >= 59.5; // simplified: retired + pre-RMD

  // QCD limit 2026
  const QCD_LIMIT = 111_000;

  // Upcoming milestones (all, within 10 years)
  const milestones = MILESTONE_DEFS.filter((m) => m.age > age && m.age <= age + 10);

  return (
    <div className="space-y-4">
      {/* RMD */}
      <PlanningCard
        title="Required Minimum Distribution"
        icon={<Clock className={cn("w-4 h-4", isRmdEligible ? "text-[var(--radar-red)]" : "text-muted-foreground")} />}
        highlight={isRmdEligible}
      >
        {isRmdEligible ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-xs text-[var(--radar-red)]">
              <AlertTriangle className="w-3.5 h-3.5" />
              <span className="font-semibold">RMD Required — Client is {age}, past RMD age of {rmdAge}</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Failure to take RMD results in a 25% IRS penalty on the undistributed amount.
              Review account balances to calculate 2026 RMD using the IRS Uniform Lifetime Table III.
            </p>
            <div className="bg-background/60 rounded p-3 text-xs">
              <p className="text-muted-foreground">Estimated RMD (using IRS table):</p>
              <p className="text-xl font-bold text-[var(--radar-red)] tabular-nums mt-1">
                {fmt$(client.aum / 26.5)} {/* age 73 factor ≈ 26.5 */}
              </p>
              <p className="text-[10px] text-muted-foreground mt-1">
                Based on total AUM. Actual RMD is calculated per IRA account balance on Dec 31, prior year.
              </p>
            </div>
          </div>
        ) : (
          <div className="text-xs text-muted-foreground space-y-1">
            <p>RMD not yet required. Client is <strong className="text-foreground">{age}</strong>, RMD age is <strong className="text-foreground">{rmdAge}</strong>.</p>
            <p className="text-[10px]">Years until RMD: <span className="text-[var(--radar-teal)] font-semibold">{rmdAge - age}</span></p>
          </div>
        )}
      </PlanningCard>

      {/* QCD */}
      <PlanningCard
        title="Qualified Charitable Distribution"
        icon={<CheckCircle2 className={cn("w-4 h-4", isQcdEligible ? "text-[var(--radar-green)]" : "text-muted-foreground")} />}
        highlight={isQcdEligible}
      >
        {isQcdEligible ? (
          <div className="space-y-2 text-xs">
            <p className="text-[var(--radar-green)] font-semibold">✓ Eligible — Age {age} ≥ 70½</p>
            <p className="text-muted-foreground">
              Client can make QCDs directly from IRA to qualified charities, up to <strong className="text-foreground">${QCD_LIMIT.toLocaleString()}</strong> in 2026.
              QCDs satisfy RMD requirements and are excluded from taxable income.
            </p>
            <div className="bg-background/60 rounded p-3">
              <p className="text-muted-foreground">Annual QCD Limit (2026):</p>
              <p className="text-xl font-bold text-[var(--radar-green)] tabular-nums">${QCD_LIMIT.toLocaleString()}</p>
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            Client becomes QCD-eligible at age 70½. Currently <strong className="text-foreground">{age}</strong> — eligible in <span className="text-[var(--radar-teal)]">{(70.5 - age).toFixed(1)} years</span>.
          </p>
        )}
      </PlanningCard>

      {/* Roth Conversion */}
      <PlanningCard
        title="Roth Conversion Analysis"
        icon={<TrendingUp className={cn("w-4 h-4", isRothWindow ? "text-[var(--radar-teal)]" : "text-muted-foreground")} />}
        highlight={isRothWindow}
      >
        {isRothWindow ? (
          <div className="space-y-2 text-xs">
            <p className="text-[var(--radar-teal)] font-semibold">✓ Roth Conversion Window — Optimal timing</p>
            <p className="text-muted-foreground">
              Client is in the pre-RMD gap years — retired, past 59½ penalty window, but before RMDs begin.
              This is typically the optimal window for Roth conversions.
            </p>
            <p className="text-[10px] text-muted-foreground">
              Note: Pro-rata rule applies across ALL Traditional IRA balances. Coordinate with CPA before executing.
            </p>
            <div className="bg-background/60 rounded p-3 space-y-1">
              <p className="text-muted-foreground">Tax bracket: <strong className="text-foreground">{client.tax_bracket ?? "Not specified"}</strong></p>
              <p className="text-muted-foreground">Risk tolerance: <strong className="text-foreground">{client.risk_tolerance ?? "Not specified"}</strong></p>
              <p className="text-[10px] text-[var(--radar-teal)] mt-2">
                Run the full meeting prep analysis for a Roth conversion recommendation.
              </p>
            </div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            {age < 59.5
              ? `Roth conversions possible but 10% early withdrawal penalty applies until age 59½ (${(59.5 - age).toFixed(1)} years away).`
              : isRmdEligible
              ? "Client is in RMD phase. Roth conversions reduce future RMDs — coordinate amounts carefully."
              : "Monitoring for Roth conversion window."}
          </p>
        )}
      </PlanningCard>

      {/* Milestones timeline */}
      {milestones.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-5">
          <SectionTitle icon={<Calendar className="w-4 h-4 text-[var(--radar-teal)]" />}>
            10-Year Milestone Timeline
          </SectionTitle>
          <div className="space-y-3">
            {milestones.map((m, i) => {
              const yearsAway = m.age - age;
              return (
                <div key={m.age} className="flex items-start gap-3">
                  <div className="flex flex-col items-center">
                    <div className="w-6 h-6 rounded-full bg-[var(--radar-teal)]/15 border border-[var(--radar-teal)]/30 flex items-center justify-center text-xs">
                      {m.icon}
                    </div>
                    {i < milestones.length - 1 && <div className="w-px h-4 bg-border mt-1" />}
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-foreground">Age {m.age}</p>
                    <p className="text-[10px] text-muted-foreground">{m.label}</p>
                    <p className="text-[10px] text-[var(--radar-teal)]">In {yearsAway.toFixed(1)} years (~{new Date().getFullYear() + Math.round(yearsAway)})</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Actions Tab ───────────────────────────────────────────────────────────────

type ActionMode = "idle" | "meeting-prep" | "outreach";

function ActionsTab({ clientId }: { clientId: string }) {
  const [mode, setMode]               = useState<ActionMode>("idle");
  const [approvalContent, setContent] = useState<string | null>(null);
  const [approvalTitle, setTitle]     = useState("");
  const { events, running, done, start, reset } = useAgentStream();

  function handleMeetingPrep() {
    reset();
    setContent(null);
    setMode("meeting-prep");
    start(`/api/agents/meeting-prep/${clientId}`, {});
  }

  function handleOutreach() {
    reset();
    setContent(null);
    setMode("outreach");
    start(`/api/agents/outreach/${clientId}`, { tone: "professional", include_numbers: true });
  }

  function handleRegenerate() {
    if (mode === "meeting-prep") handleMeetingPrep();
    else if (mode === "outreach") handleOutreach();
  }

  // Extract result content from SSE events
  const resultEvent = [...events].reverse().find((e) => e.type === "result");
  const generatedContent = (() => {
    if (!resultEvent) return null;
    try {
      const raw = typeof resultEvent.data === "string"
        ? JSON.parse(resultEvent.data)
        : resultEvent.data as Record<string, unknown>;
      if (typeof raw === "object" && raw) {
        return (
          (raw as Record<string, unknown>).outreach_draft as string
          ?? (raw as Record<string, unknown>).talking_points_text as string
          ?? JSON.stringify(raw, null, 2)
        );
      }
      return resultEvent.content ?? JSON.stringify(raw, null, 2);
    } catch {
      return resultEvent.content ?? String(resultEvent.data ?? "");
    }
  })();

  return (
    <div className="space-y-6">
      {/* Action buttons */}
      <div className="grid grid-cols-2 gap-4">
        <button
          onClick={handleMeetingPrep}
          disabled={running}
          className="flex flex-col items-start gap-2 bg-card border border-border rounded-lg p-5 hover:border-[var(--radar-teal)]/50 hover:bg-[var(--radar-teal)]/5 transition-colors disabled:opacity-60 disabled:cursor-not-allowed text-left"
        >
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-[var(--radar-teal)]" />
            <span className="font-semibold text-sm text-foreground">Generate Meeting Prep</span>
          </div>
          <p className="text-xs text-muted-foreground">
            AI analyzes triggers, documents, and market context to produce a complete pre-meeting package
            with talking points, action items, and agenda.
          </p>
          {mode === "meeting-prep" && running && (
            <span className="text-[10px] text-[var(--radar-teal)] font-medium animate-pulse">Running…</span>
          )}
        </button>

        <button
          onClick={handleOutreach}
          disabled={running}
          className="flex flex-col items-start gap-2 bg-card border border-border rounded-lg p-5 hover:border-[var(--radar-teal)]/50 hover:bg-[var(--radar-teal)]/5 transition-colors disabled:opacity-60 disabled:cursor-not-allowed text-left"
        >
          <div className="flex items-center gap-2">
            <Mail className="w-5 h-5 text-[var(--radar-teal)]" />
            <span className="font-semibold text-sm text-foreground">Draft Outreach Email</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Composer agent generates a personalized outreach email based on detected triggers and
            client profile — ready to review and send.
          </p>
          {mode === "outreach" && running && (
            <span className="text-[10px] text-[var(--radar-teal)] font-medium animate-pulse">Running…</span>
          )}
        </button>
      </div>

      {/* Pipeline + stream */}
      {mode !== "idle" && (
        <div className="grid grid-cols-5 gap-6">
          {/* Agent steps (3/5) */}
          <div className="col-span-3 bg-card border border-border rounded-lg p-5">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-4">
              Agent Pipeline
            </p>
            <AgentSteps events={events} running={running} done={done} />
          </div>

          {/* Raw terminal log (2/5) */}
          <div className="col-span-2 space-y-2">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Live Output
            </p>
            <AgentStream events={events} running={running} className="h-64 max-h-64" />
          </div>
        </div>
      )}

      {/* Approval workflow */}
      {done && generatedContent && (
        <div className="bg-card border border-border rounded-lg p-5">
          <ApprovalWorkflow
            title={mode === "meeting-prep" ? "Meeting Prep Package" : "Outreach Email Draft"}
            content={generatedContent}
            onRegenerate={handleRegenerate}
          />
        </div>
      )}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

const TABS = [
  { id: "overview",  label: "Overview" },
  { id: "portfolio", label: "Portfolio" },
  { id: "planning",  label: "Planning" },
  { id: "actions",   label: "Actions" },
] as const;

export default function ClientDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const clientId = params.id;

  const { client, loading, error } = useClient(clientId);

  if (loading) {
    return (
      <div className="space-y-6 max-w-5xl">
        <div className="flex items-center gap-4">
          <Skeleton className="w-8 h-8 rounded" />
          <div className="space-y-2">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-3 w-32" />
          </div>
        </div>
        <div className="grid grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-20 rounded-lg" />)}
        </div>
        <Skeleton className="h-96 rounded-lg" />
      </div>
    );
  }

  if (error || !client) {
    return (
      <div className="text-center py-20">
        <p className="text-[var(--radar-red)] text-sm font-semibold">Failed to load client</p>
        <p className="text-muted-foreground text-xs mt-1">{error ?? "Client not found"}</p>
        <button onClick={() => router.back()} className="mt-4 text-xs text-[var(--radar-teal)] hover:underline">
          ← Go back
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-5 max-w-5xl">
      {/* Page header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="p-1.5 rounded-md hover:bg-secondary transition-colors text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex items-center gap-3 min-w-0">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-foreground">{client.name}</h2>
              <span className={cn("text-xs font-bold px-2 py-0.5 rounded uppercase", TIER_COLOR[client.tier] ?? TIER_COLOR.D)}>
                Tier {client.tier}
              </span>
              {client.has_portfolio_drift && (
                <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-[var(--radar-yellow)]/15 text-[var(--radar-yellow)]">
                  Drift
                </span>
              )}
            </div>
            <p className="text-xs text-muted-foreground mt-0.5">
              {client.id} · AUM: {fmt$(client.aum)}
              {client.occupation && ` · ${client.occupation}`}
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <TabsPrimitive.Root defaultValue="overview">
        <TabsPrimitive.List className="flex gap-1 border-b border-border pb-0 mb-5">
          {TABS.map((tab) => (
            <TabsPrimitive.Trigger
              key={tab.id}
              value={tab.id}
              className={cn(
                "px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px",
                "text-muted-foreground hover:text-foreground border-transparent",
                "data-[state=active]:text-[var(--radar-teal)] data-[state=active]:border-[var(--radar-teal)]",
              )}
            >
              {tab.label}
            </TabsPrimitive.Trigger>
          ))}
        </TabsPrimitive.List>

        <TabsPrimitive.Content value="overview">
          <OverviewTab client={client} />
        </TabsPrimitive.Content>

        <TabsPrimitive.Content value="portfolio">
          <PortfolioTab clientId={clientId} client={client} />
        </TabsPrimitive.Content>

        <TabsPrimitive.Content value="planning">
          <PlanningTab client={client} />
        </TabsPrimitive.Content>

        <TabsPrimitive.Content value="actions">
          <ActionsTab clientId={clientId} />
        </TabsPrimitive.Content>
      </TabsPrimitive.Root>
    </div>
  );
}
