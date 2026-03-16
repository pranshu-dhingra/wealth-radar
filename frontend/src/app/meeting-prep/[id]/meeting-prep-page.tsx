"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft, Sparkles, Calendar, Zap, Mail, CheckCircle2,
  Copy, Check, AlertTriangle, Clock, FileText, TrendingUp,
  ChevronRight, Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useClient } from "@/hooks/use-clients";
import { useAgentStream } from "@/hooks/use-agent-stream";
import { AgentStream } from "@/components/agents/agent-stream";
import { AgentSteps } from "@/components/agents/agent-steps";
import type { MeetingPrep, ActionItem, Client } from "@/lib/types";

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

const PRIORITY_COLOR: Record<string, string> = {
  high:   "text-[var(--radar-red)] bg-[var(--radar-red)]/10",
  medium: "text-[var(--radar-yellow)] bg-[var(--radar-yellow)]/10",
  low:    "text-[var(--radar-green)] bg-[var(--radar-green)]/10",
};

const TRIGGER_LABELS: Record<string, string> = {
  RMD_DUE:               "RMD Due",
  RMD_OVERDUE:           "RMD Overdue",
  RMD_APPROACHING:       "RMD Approaching",
  PORTFOLIO_DRIFT:       "Portfolio Drift",
  TLH_OPPORTUNITY:       "Tax-Loss Harvesting",
  ROTH_WINDOW:           "Roth Window",
  QCD_OPPORTUNITY:       "QCD Opportunity",
  ESTATE_REVIEW_OVERDUE: "Estate Review Overdue",
  MEETING_OVERDUE:       "Meeting Overdue",
  LIFE_EVENT_RECENT:     "Recent Life Event",
  BENEFICIARY_REVIEW:    "Beneficiary Review",
  MARKET_EVENT:          "Market Event",
  APPROACHING_MILESTONE: "Upcoming Milestone",
};

function urgencyColor(u: number) {
  if (u >= 70) return "text-[var(--radar-red)]";
  if (u >= 40) return "text-[var(--radar-yellow)]";
  return "text-[var(--radar-green)]";
}

// ── Copy Button ───────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  function handle() {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }
  return (
    <button
      onClick={handle}
      className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md bg-secondary hover:bg-secondary/80 text-muted-foreground hover:text-foreground transition-colors"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-[var(--radar-green)]" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

// ── Section Card ─────────────────────────────────────────────────────────────

function SectionCard({ title, icon, children, action }: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="bg-card border border-border rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
          {icon}
          {title}
        </h3>
        {action}
      </div>
      {children}
    </div>
  );
}

// ── Trigger Summary ───────────────────────────────────────────────────────────

function TriggerSummary({ prep }: { prep: MeetingPrep }) {
  const triggers = prep.trigger_analysis?.triggers ?? [];
  if (triggers.length === 0) return null;
  return (
    <SectionCard
      title="Active Triggers"
      icon={<Zap className="w-4 h-4 text-[var(--radar-yellow)]" />}
    >
      <div className="space-y-2">
        {triggers.map((t, i) => (
          <div key={i} className="flex items-center justify-between py-2 border-b border-border/40 last:border-0">
            <div className="flex items-center gap-2">
              <AlertTriangle className={cn("w-3.5 h-3.5 shrink-0", urgencyColor(t.urgency ?? 50))} />
              <span className="text-sm text-foreground font-medium">
                {TRIGGER_LABELS[t.trigger_type ?? ""] ?? (t.trigger_type ?? "Unknown")}
              </span>
              {t.description && (
                <span className="text-xs text-muted-foreground hidden sm:inline">— {t.description}</span>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className={cn("text-xs font-mono font-bold tabular-nums", urgencyColor(t.urgency ?? 50))}>
                {Math.round(t.urgency ?? 50)}
              </span>
              <span className="text-[10px] text-muted-foreground">urgency</span>
            </div>
          </div>
        ))}
      </div>
      {prep.trigger_analysis?.priority_score != null && (
        <div className="flex items-center gap-2 pt-1">
          <span className="text-xs text-muted-foreground">Priority Score:</span>
          <span className="text-sm font-bold tabular-nums text-[var(--radar-teal)]">
            {Math.round(prep.trigger_analysis.priority_score)}
          </span>
          <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
            <div
              className="h-full bg-[var(--radar-teal)] rounded-full"
              style={{ width: `${Math.min(100, Math.round(prep.trigger_analysis.priority_score))}%` }}
            />
          </div>
        </div>
      )}
    </SectionCard>
  );
}

// ── Meeting Agenda ────────────────────────────────────────────────────────────

function AgendaSection({ prep }: { prep: MeetingPrep }) {
  const agenda = prep.meeting_agenda;
  const points = prep.talking_points ?? [];

  if (!agenda && points.length === 0) return null;

  return (
    <SectionCard
      title="Meeting Agenda"
      icon={<Calendar className="w-4 h-4 text-[var(--radar-teal)]" />}
    >
      {agenda?.estimated_duration && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Clock className="w-3.5 h-3.5" />
          Estimated duration: <span className="text-foreground font-medium">{agenda.estimated_duration}</span>
        </div>
      )}
      {agenda?.topics && agenda.topics.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Topics</p>
          <ol className="space-y-2">
            {agenda.topics.map((topic, i) => (
              <li key={i} className="flex items-start gap-3 text-sm">
                <span className="w-5 h-5 rounded-full bg-[var(--radar-teal)]/15 text-[var(--radar-teal)] text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <span className="text-foreground">{topic}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {agenda?.key_documents && agenda.key_documents.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Key Documents</p>
          <div className="flex flex-wrap gap-2">
            {agenda.key_documents.map((doc, i) => (
              <span key={i} className="flex items-center gap-1.5 text-xs px-2.5 py-1 bg-secondary rounded-full text-muted-foreground">
                <FileText className="w-3 h-3" />
                {doc}
              </span>
            ))}
          </div>
        </div>
      )}
      {points.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Talking Points</p>
          <ul className="space-y-2">
            {points.map((point, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-foreground">
                <ChevronRight className="w-3.5 h-3.5 text-[var(--radar-teal)] shrink-0 mt-0.5" />
                {point}
              </li>
            ))}
          </ul>
        </div>
      )}
    </SectionCard>
  );
}

// ── Action Items ──────────────────────────────────────────────────────────────

function ActionItemsSection({ prep }: { prep: MeetingPrep }) {
  const items = prep.action_items ?? [];
  if (items.length === 0) return null;

  const sorted = [...items].sort((a, b) => {
    const order = { high: 0, medium: 1, low: 2 };
    return (order[a.priority] ?? 1) - (order[b.priority] ?? 1);
  });

  return (
    <SectionCard
      title="Action Items"
      icon={<CheckCircle2 className="w-4 h-4 text-[var(--radar-green)]" />}
    >
      <div className="space-y-3">
        {sorted.map((item, i) => (
          <div key={i} className="flex items-start gap-3 p-3 bg-secondary/30 rounded-lg">
            <span className={cn("text-[10px] font-bold uppercase px-2 py-0.5 rounded shrink-0 mt-0.5", PRIORITY_COLOR[item.priority])}>
              {item.priority}
            </span>
            <div className="flex-1 space-y-1">
              <p className="text-sm text-foreground font-medium">{item.action}</p>
              {item.details && <p className="text-xs text-muted-foreground">{item.details}</p>}
              <div className="flex items-center gap-3 flex-wrap">
                {item.deadline && (
                  <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                    <Clock className="w-3 h-3" /> Due: {item.deadline}
                  </span>
                )}
                {item.revenue_impact != null && (
                  <span className="text-[10px] text-[var(--radar-green)] flex items-center gap-1">
                    <TrendingUp className="w-3 h-3" /> {fmt$(item.revenue_impact)} impact
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

// ── Outreach Email ────────────────────────────────────────────────────────────

function OutreachSection({ prep }: { prep: MeetingPrep }) {
  const draft = prep.outreach_draft;
  if (!draft) return null;

  return (
    <SectionCard
      title="Outreach Email Draft"
      icon={<Mail className="w-4 h-4 text-[var(--radar-teal)]" />}
      action={<CopyButton text={draft} />}
    >
      <div className="bg-secondary/40 border border-border rounded-lg p-4">
        <pre className="text-sm text-foreground whitespace-pre-wrap font-sans leading-relaxed">{draft}</pre>
      </div>
    </SectionCard>
  );
}

// ── Context Cards ─────────────────────────────────────────────────────────────

function ContextSection({ prep }: { prep: MeetingPrep }) {
  const hasDocs = !!prep.document_summary;
  const hasMarket = !!prep.market_context;
  if (!hasDocs && !hasMarket) return null;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {hasDocs && (
        <SectionCard
          title="Document Summary"
          icon={<FileText className="w-4 h-4 text-blue-400" />}
        >
          <p className="text-sm text-muted-foreground leading-relaxed">{prep.document_summary}</p>
        </SectionCard>
      )}
      {hasMarket && (
        <SectionCard
          title="Market Context"
          icon={<TrendingUp className="w-4 h-4 text-[var(--radar-yellow)]" />}
        >
          <p className="text-sm text-muted-foreground leading-relaxed">{prep.market_context}</p>
        </SectionCard>
      )}
    </div>
  );
}

// ── Client Header ─────────────────────────────────────────────────────────────

function ClientHeader({ client, clientId }: { client: Client | null; clientId: string }) {
  const router = useRouter();
  return (
    <div className="flex items-center gap-4">
      <button
        onClick={() => router.push(`/clients/${clientId}`)}
        className="p-2 rounded-lg bg-secondary hover:bg-secondary/80 text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
      </button>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h1 className="text-lg font-bold text-foreground">
            {client?.name ?? clientId} — Meeting Prep
          </h1>
          {client?.tier && (
            <span className={cn("text-xs font-bold px-2 py-0.5 rounded", TIER_COLOR[client.tier])}>
              Tier {client.tier}
            </span>
          )}
        </div>
        <p className="text-sm text-muted-foreground mt-0.5">
          {client ? `${fmt$(client.aum)} AUM · Age ${client.age} · ${client.occupation ?? ""}` : "Loading client…"}
        </p>
      </div>
    </div>
  );
}

// ── Parse SSE result ─────────────────────────────────────────────────────────

function parseMeetingPrep(events: ReturnType<typeof useAgentStream>["events"]): MeetingPrep | null {
  const resultEvent = [...events].reverse().find((e) => e.type === "result");
  if (!resultEvent) return null;
  try {
    const raw = typeof resultEvent.data === "string"
      ? JSON.parse(resultEvent.data)
      : (resultEvent.data as Record<string, unknown>);
    if (typeof raw === "object" && raw !== null) {
      return raw as MeetingPrep;
    }
  } catch {
    // content might be a raw string
  }
  // fallback: try to build a minimal prep from content string
  if (resultEvent.content) {
    return { client_id: "", outreach_draft: resultEvent.content };
  }
  return null;
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function MeetingPrepPage() {
  const { id } = useParams<{ id: string }>();
  const clientId = id ?? "";

  const { client } = useClient(clientId);
  const { events, running, done, start, reset } = useAgentStream();

  const [started, setStarted] = useState(false);

  function handleGenerate() {
    reset();
    setStarted(true);
    start(`/api/agents/meeting-prep/${clientId}`, {});
  }

  const prep = done ? parseMeetingPrep(events) : null;
  const errorEvent = events.find((e) => e.type === "error");

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <ClientHeader client={client} clientId={clientId} />

      {/* Generate button (idle state) */}
      {!started && (
        <div className="bg-card border border-border rounded-xl p-8 flex flex-col items-center gap-4 text-center">
          <div className="w-14 h-14 rounded-full bg-[var(--radar-teal)]/10 flex items-center justify-center">
            <Sparkles className="w-7 h-7 text-[var(--radar-teal)]" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-foreground">Generate Meeting Package</h2>
            <p className="text-sm text-muted-foreground mt-1 max-w-sm">
              AI agents will analyze triggers, review documents, research market context,
              and draft a complete meeting brief + outreach email.
            </p>
          </div>
          <button
            onClick={handleGenerate}
            className="flex items-center gap-2 px-6 py-2.5 bg-[var(--radar-teal)] text-background text-sm font-semibold rounded-lg hover:opacity-90 transition-opacity"
          >
            <Sparkles className="w-4 h-4" />
            Generate Meeting Package
          </button>
          <p className="text-[10px] text-muted-foreground">
            Runs Sentinel → Document Intelligence → Scout → Composer pipeline (~30–60s)
          </p>
        </div>
      )}

      {/* Agent activity */}
      {started && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground flex items-center gap-2">
              {running && <Loader2 className="w-4 h-4 animate-spin text-[var(--radar-teal)]" />}
              {done && <CheckCircle2 className="w-4 h-4 text-[var(--radar-green)]" />}
              {running ? "Agents Running…" : done ? "Package Ready" : "Agent Activity"}
            </h3>
            {done && (
              <button
                onClick={handleGenerate}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Regenerate
              </button>
            )}
          </div>
          <AgentSteps events={events} running={running} done={done} />
          {running && (
            <AgentStream events={events} running={running} className="h-48 max-h-48" />
          )}
        </div>
      )}

      {/* Error */}
      {errorEvent && (
        <div className="flex items-start gap-3 p-4 bg-[var(--radar-red)]/10 border border-[var(--radar-red)]/20 rounded-lg">
          <AlertTriangle className="w-4 h-4 text-[var(--radar-red)] shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-[var(--radar-red)]">Generation failed</p>
            <p className="text-xs text-muted-foreground mt-0.5">{errorEvent.content ?? errorEvent.message}</p>
          </div>
        </div>
      )}

      {/* Results */}
      {prep && (
        <div className="space-y-4">
          <TriggerSummary prep={prep} />
          <AgendaSection prep={prep} />
          <ActionItemsSection prep={prep} />
          <OutreachSection prep={prep} />
          <ContextSection prep={prep} />

          {/* Fallback: raw content if nothing parsed */}
          {!prep.trigger_analysis && !prep.meeting_agenda && !prep.talking_points?.length
           && !prep.action_items?.length && !prep.outreach_draft && !prep.document_summary && !prep.market_context && (
            <div className="bg-card border border-border rounded-xl p-5">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-3">Raw Output</p>
              <pre className="text-sm text-foreground whitespace-pre-wrap font-sans leading-relaxed">
                {JSON.stringify(prep, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
