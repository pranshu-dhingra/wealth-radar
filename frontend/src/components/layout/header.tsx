"use client";

import { useState } from "react";
import { Bell, Zap, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { streamAgentSSE } from "@/lib/api";
import type { AgentEvent } from "@/lib/types";

interface HeaderProps {
  title?: string;
}

export function Header({ title }: HeaderProps) {
  const [scanning, setScanning] = useState(false);
  const [done, setDone] = useState(false);
  const router = useRouter();

  function handleDailyScan() {
    if (scanning) return;
    setScanning(true);
    setDone(false);

    const stop = streamAgentSSE(
      "/api/agents/daily-scan",
      { top_n: 10 },
      (_event: AgentEvent) => { /* streamed to agent panel */ },
      () => { setScanning(false); setDone(true); stop(); router.refresh(); },
      () => { setScanning(false); stop(); },
    );
  }

  return (
    <header className="flex items-center justify-between px-6 h-14 border-b border-border bg-card shrink-0">
      {/* Page title */}
      <h1 className="text-[15px] font-semibold text-foreground">
        {title ?? "Dashboard"}
      </h1>

      {/* Actions */}
      <div className="flex items-center gap-3">
        {/* Notification bell */}
        <button
          className="relative p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
          aria-label="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-[var(--radar-red)] animate-pulse-dot" />
        </button>

        {/* Daily scan CTA */}
        <button
          onClick={handleDailyScan}
          disabled={scanning}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold bg-[var(--radar-teal)] text-background hover:opacity-90 active:scale-95 transition-all disabled:opacity-60 disabled:cursor-not-allowed disabled:active:scale-100"
        >
          {scanning
            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
            : <Zap className="w-3.5 h-3.5" />
          }
          {scanning ? "Scanning…" : done ? "Scan Done ✓" : "Run Daily Scan"}
        </button>
      </div>
    </header>
  );
}
