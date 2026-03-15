"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { AgentEvent } from "@/lib/types";

// ── Step definitions for the agent pipeline ──────────────────────────────────

export interface PipelineStep {
  id: string;
  label: string;
  description: string;
  emoji: string;
  agentKey: string;   // matches AgentEvent.agent value
  status: "pending" | "running" | "done" | "error";
  detail?: string;    // last message from that agent
}

const DEFAULT_STEPS: Omit<PipelineStep, "status" | "detail">[] = [
  { id: "sentinel", label: "Sentinel Agent",  description: "Scanning triggers & portfolio...", emoji: "🔍", agentKey: "sentinel" },
  { id: "doc",      label: "Document Agent",  description: "Analyzing client documents...",    emoji: "📄", agentKey: "doc_agent" },
  { id: "scout",    label: "Scout Agent",     description: "Checking market & yield data...",  emoji: "🌐", agentKey: "scout" },
  { id: "composer", label: "Composer Agent",  description: "Generating action package...",     emoji: "✍️", agentKey: "composer" },
];

function deriveSteps(events: AgentEvent[]): PipelineStep[] {
  const steps: PipelineStep[] = DEFAULT_STEPS.map((s) => ({ ...s, status: "pending" }));

  for (const ev of events) {
    const agentKey = ev.agent?.toLowerCase() ?? "";
    const stepIdx = steps.findIndex((s) => agentKey.includes(s.agentKey));

    if (stepIdx === -1) continue;
    const step = steps[stepIdx];

    if (ev.type === "error") {
      step.status = "error";
      step.detail = ev.message ?? "Error occurred";
    } else if (ev.type === "result" || ev.type === "done") {
      step.status = "done";
      step.detail = typeof ev.content === "string" ? ev.content.slice(0, 120) : step.detail;
    } else {
      // status / tool_call / thinking
      if (step.status === "pending") step.status = "running";
      if (ev.message) step.detail = ev.message.slice(0, 120);
      // Mark previous steps as done
      for (let i = 0; i < stepIdx; i++) {
        if (steps[i].status === "pending" || steps[i].status === "running") {
          steps[i].status = "done";
        }
      }
    }
  }
  return steps;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StepIcon({ status, emoji }: { status: PipelineStep["status"]; emoji: string }) {
  if (status === "running") {
    return (
      <div className="w-8 h-8 rounded-full bg-[var(--radar-teal)]/10 border border-[var(--radar-teal)]/40 flex items-center justify-center text-sm animate-pulse">
        {emoji}
      </div>
    );
  }
  if (status === "done") {
    return (
      <div className="w-8 h-8 rounded-full bg-[var(--radar-green)]/15 border border-[var(--radar-green)]/40 flex items-center justify-center text-sm">
        ✓
      </div>
    );
  }
  if (status === "error") {
    return (
      <div className="w-8 h-8 rounded-full bg-[var(--radar-red)]/15 border border-[var(--radar-red)]/40 flex items-center justify-center text-sm">
        ✗
      </div>
    );
  }
  // pending
  return (
    <div className="w-8 h-8 rounded-full bg-secondary border border-border flex items-center justify-center text-sm opacity-40">
      {emoji}
    </div>
  );
}

const STATUS_COLORS: Record<PipelineStep["status"], string> = {
  pending: "text-muted-foreground/40",
  running: "text-[var(--radar-teal)]",
  done:    "text-[var(--radar-green)]",
  error:   "text-[var(--radar-red)]",
};

// ── Main component ────────────────────────────────────────────────────────────

interface AgentStepsProps {
  events: AgentEvent[];
  running: boolean;
  done: boolean;
  className?: string;
}

export function AgentSteps({ events, running, done, className }: AgentStepsProps) {
  const steps = deriveSteps(events);
  const hasActivity = events.length > 0;

  if (!hasActivity && !running) {
    return (
      <div className={cn("space-y-3", className)}>
        {DEFAULT_STEPS.map((s) => (
          <div key={s.id} className="flex items-start gap-3 opacity-30">
            <div className="w-8 h-8 rounded-full bg-secondary border border-border flex items-center justify-center text-sm">
              {s.emoji}
            </div>
            <div className="flex-1 pt-1">
              <p className="text-xs font-semibold text-muted-foreground">{s.label}</p>
              <p className="text-[10px] text-muted-foreground/60 mt-0.5">{s.description}</p>
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className={cn("space-y-0", className)}>
      {steps.map((step, idx) => {
        const isLast = idx === steps.length - 1;
        return (
          <div key={step.id} className="flex gap-3">
            {/* Left: icon + connector */}
            <div className="flex flex-col items-center">
              <StepIcon status={step.status} emoji={step.emoji} />
              {!isLast && (
                <div className={cn(
                  "w-px flex-1 my-1 min-h-[16px]",
                  step.status === "done" ? "bg-[var(--radar-green)]/30" : "bg-border",
                )} />
              )}
            </div>

            {/* Right: text */}
            <div className={cn("flex-1 pb-4", isLast && "pb-0")}>
              <p className={cn("text-xs font-semibold", STATUS_COLORS[step.status])}>
                {step.label}
                {step.status === "running" && (
                  <span className="ml-2 inline-block w-1.5 h-1.5 rounded-full bg-[var(--radar-teal)] animate-ping" />
                )}
              </p>
              {step.detail ? (
                <p className="text-[10px] text-muted-foreground mt-0.5 leading-relaxed">
                  {step.detail}
                </p>
              ) : (
                <p className="text-[10px] text-muted-foreground/50 mt-0.5">
                  {step.status === "pending" ? "Waiting…" : step.description}
                </p>
              )}
            </div>
          </div>
        );
      })}

      {done && (
        <div className="mt-2 flex items-center gap-2 text-[11px] text-[var(--radar-green)]">
          <span className="w-2 h-2 rounded-full bg-current" />
          Pipeline complete
        </div>
      )}
    </div>
  );
}
