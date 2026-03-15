"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import type { AgentEvent } from "@/lib/types";

interface AgentStreamProps {
  events: AgentEvent[];
  running?: boolean;
  className?: string;
}

const TYPE_STYLES: Record<string, string> = {
  status:    "text-muted-foreground",
  thinking:  "text-[var(--radar-blue)]",
  tool_call: "text-[var(--radar-yellow)]",
  result:    "text-[var(--radar-green)]",
  error:     "text-[var(--radar-red)]",
  done:      "text-[var(--radar-teal)]",
};

const TYPE_PREFIX: Record<string, string> = {
  status:    "→",
  thinking:  "◎",
  tool_call: "⚡",
  result:    "✓",
  error:     "✗",
  done:      "■",
};

function eventText(ev: AgentEvent): string {
  if (ev.message) return ev.message;
  if (ev.content && typeof ev.content === "string") return ev.content;
  if (ev.data) return JSON.stringify(ev.data, null, 2);
  if (ev.type === "done") return "Stream complete.";
  return "";
}

export function AgentStream({ events, running, className }: AgentStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (events.length > 0) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [events]);

  return (
    <div
      className={cn(
        "bg-[hsl(220,26%,5%)] border border-border rounded-lg p-4 overflow-y-auto font-mono text-xs",
        "min-h-[200px] max-h-[420px]",
        className,
      )}
    >
      {events.length === 0 && !running && (
        <p className="text-muted-foreground/50 italic">Waiting for agent output…</p>
      )}
      {events.map((ev, i) => {
        const text = eventText(ev);
        if (!text) return null;
        const isResult = ev.type === "result";
        return (
          <div key={i} className={cn("leading-relaxed", isResult ? "mt-2" : "")}>
            <span className={cn("mr-2 font-bold", TYPE_STYLES[ev.type] ?? "text-foreground")}>
              {TYPE_PREFIX[ev.type] ?? "·"}
            </span>
            {ev.agent && (
              <span className="text-[var(--radar-teal)]/60 mr-1">[{ev.agent}]</span>
            )}
            {isResult ? (
              <pre className={cn("whitespace-pre-wrap break-words inline", TYPE_STYLES[ev.type] ?? "text-foreground")}>
                {text}
              </pre>
            ) : (
              <span className={cn(TYPE_STYLES[ev.type] ?? "text-foreground")}>{text}</span>
            )}
          </div>
        );
      })}
      {running && (
        <div className="flex items-center gap-2 mt-2 text-[var(--radar-teal)]">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-current animate-ping" />
          <span className="opacity-70">Processing…</span>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
