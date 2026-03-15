"use client";

import { useRouter } from "next/navigation";
import { CalendarCheck, Search, ChevronRight } from "lucide-react";
import { useState } from "react";
import { useClients } from "@/hooks/use-clients";

function fmtAum(aum: number): string {
  if (aum >= 1_000_000) return `$${(aum / 1_000_000).toFixed(1)}M`;
  return `$${(aum / 1_000).toFixed(0)}K`;
}

const TIER_COLOR: Record<string, string> = {
  A: "text-[var(--radar-green)] bg-[var(--radar-green)]/10",
  B: "text-[var(--radar-teal)] bg-[var(--radar-teal)]/10",
  C: "text-[var(--radar-yellow)] bg-[var(--radar-yellow)]/10",
  D: "text-muted-foreground bg-secondary",
};

export default function MeetingPrepIndexPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const { clients, loading } = useClients({ search: search || undefined, sort: "tier" });

  return (
    <div className="space-y-5 max-w-3xl">
      <div>
        <h2 className="text-xl font-bold text-foreground flex items-center gap-2">
          <CalendarCheck className="w-5 h-5 text-[var(--radar-teal)]" />
          Meeting Prep
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Select a client to generate an AI-powered pre-meeting package with talking points, action items, and outreach drafts.
        </p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search clients…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full pl-9 pr-4 py-2 text-sm bg-secondary border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-[var(--radar-teal)]"
        />
      </div>

      <div className="bg-card border border-border rounded-lg overflow-hidden">
        {loading
          ? Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 px-4 py-3.5 border-b border-border animate-pulse">
                <div className="h-4 w-6 bg-secondary rounded" />
                <div className="h-4 bg-secondary rounded flex-1" />
                <div className="h-4 w-16 bg-secondary rounded" />
                <div className="h-4 w-4 bg-secondary rounded" />
              </div>
            ))
          : clients.map((c) => (
              <button
                key={c.id}
                onClick={() => router.push(`/meeting-prep/${c.id}`)}
                className="w-full flex items-center gap-4 px-4 py-3.5 border-b border-border hover:bg-secondary/20 transition-colors text-left group"
              >
                <span className={`text-xs font-bold px-2 py-0.5 rounded uppercase shrink-0 ${TIER_COLOR[c.tier] ?? ""}`}>
                  {c.tier}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground truncate">{c.name}</p>
                  <p className="text-xs text-muted-foreground font-mono">{c.id}</p>
                </div>
                <span className="text-xs text-muted-foreground tabular-nums shrink-0">
                  {fmtAum(c.aum)}
                </span>
                <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-[var(--radar-teal)] transition-colors shrink-0" />
              </button>
            ))}
        {!loading && clients.length === 0 && (
          <div className="py-10 text-center text-muted-foreground text-sm">
            No clients found.
          </div>
        )}
      </div>
    </div>
  );
}
