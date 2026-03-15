"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search, Filter, ChevronUp, ChevronDown, AlertTriangle, RefreshCw } from "lucide-react";
import { useClients } from "@/hooks/use-clients";
import { mockClients } from "@/data/mock-data";

const TIERS = ["All", "A", "B", "C", "D"] as const;
const AUM_RANGES = ["All", "<$500K", "$500K–$1M", "$1M–$2M", "$2M+"] as const;

function fmtAum(aum: number): string {
  if (aum >= 1_000_000) return `$${(aum / 1_000_000).toFixed(2)}M`;
  return `$${(aum / 1_000).toFixed(0)}K`;
}

const TIER_COLORS: Record<string, string> = {
  A: "text-[var(--radar-green)] bg-[var(--radar-green)]/10",
  B: "text-[var(--radar-teal)] bg-[var(--radar-teal)]/10",
  C: "text-[var(--radar-yellow)] bg-[var(--radar-yellow)]/10",
  D: "text-muted-foreground bg-secondary",
};

function inAumRange(aum: number, range: string): boolean {
  if (range === "All") return true;
  if (range === "<$500K")     return aum < 500_000;
  if (range === "$500K–$1M")  return aum >= 500_000 && aum < 1_000_000;
  if (range === "$1M–$2M")    return aum >= 1_000_000 && aum < 2_000_000;
  if (range === "$2M+")       return aum >= 2_000_000;
  return true;
}

/** Compute action badge labels for a client */
function getStatusBadges(c: { has_portfolio_drift?: boolean; last_meeting_date?: string; tier: string }): string[] {
  const badges: string[] = [];
  if (c.has_portfolio_drift) badges.push("Drift");
  if (c.last_meeting_date) {
    const daysSince = Math.floor((Date.now() - new Date(c.last_meeting_date).getTime()) / 86400000);
    const freqDays: Record<string, number> = { A: 91, B: 121, C: 182, D: 365 };
    const limit = freqDays[c.tier] ?? 365;
    if (daysSince > limit) badges.push("Overdue");
  }
  return badges;
}

export default function ClientsPage() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [tier, setTier] = useState<string>("All");
  const [aumRange, setAumRange] = useState<string>("All");
  const [sort, setSort] = useState<"aum" | "name" | "tier">("aum");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");

  const { clients: liveClients, loading, error, refetch } = useClients({
    tier: tier === "All" ? undefined : tier,
    sort,
    search: search || undefined,
  });

  // Fall back to mock data if backend unavailable
  const rawClients = error ? mockClients : liveClients;

  // AUM range filter (client-side only)
  const clients = rawClients.filter((c) => inAumRange(c.aum, aumRange));

  const sorted = sortDir === "asc" ? [...clients] : [...clients].reverse();

  const totalAum = clients.reduce((s, c) => s + c.aum, 0);

  function toggleSort(field: "aum" | "name" | "tier") {
    if (sort === field) { setSortDir((d) => (d === "asc" ? "desc" : "asc")); }
    else { setSort(field); setSortDir("desc"); }
  }

  function SortIcon({ field }: { field: string }) {
    if (sort !== field) return null;
    return sortDir === "asc"
      ? <ChevronUp className="w-3 h-3 inline ml-1" />
      : <ChevronDown className="w-3 h-3 inline ml-1" />;
  }

  return (
    <div className="space-y-5 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-foreground">Clients</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            {sorted.length} clients &middot; {fmtAum(totalAum)} total AUM
            {error && <span className="ml-2 text-[var(--radar-yellow)]">(offline — showing demo data)</span>}
          </p>
        </div>
        {error && (
          <button
            onClick={refetch}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry
          </button>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search name, ID, email…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm bg-secondary border border-border rounded-md text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-[var(--radar-teal)]"
          />
        </div>

        {/* Tier filter */}
        <div className="flex items-center gap-1 bg-secondary border border-border rounded-md p-1">
          <Filter className="w-3.5 h-3.5 text-muted-foreground ml-1" />
          {TIERS.map((t) => (
            <button
              key={t}
              onClick={() => setTier(t)}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${
                tier === t
                  ? "bg-[var(--radar-teal)] text-background"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* AUM range filter */}
        <div className="flex items-center gap-1 bg-secondary border border-border rounded-md p-1 flex-wrap">
          {AUM_RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setAumRange(r)}
              className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${
                aumRange === r
                  ? "bg-[var(--radar-teal)] text-background"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-secondary/30">
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Client
              </th>
              <th
                className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer hover:text-foreground"
                onClick={() => toggleSort("tier")}
              >
                Tier <SortIcon field="tier" />
              </th>
              <th
                className="px-4 py-3 text-right text-xs font-medium text-muted-foreground uppercase tracking-wider cursor-pointer hover:text-foreground"
                onClick={() => toggleSort("aum")}
              >
                AUM <SortIcon field="aum" />
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Risk
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Last Meeting
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Status
              </th>
              <th className="px-4 py-3 text-center text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Drift
              </th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 10 }).map((_, i) => (
                  <tr key={i} className="border-b border-border animate-pulse">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-4 py-3.5">
                        <div className="h-3 bg-secondary rounded w-3/4" />
                      </td>
                    ))}
                  </tr>
                ))
              : sorted.map((c) => {
                  const badges = getStatusBadges(c);
                  return (
                    <tr
                      key={c.id}
                      className="border-b border-border hover:bg-secondary/20 cursor-pointer transition-colors"
                      onClick={() => router.push(`/clients/${c.id}`)}
                    >
                      <td className="px-4 py-3.5">
                        <p className="font-medium text-foreground">{c.name}</p>
                        <p className="text-xs text-muted-foreground font-mono">{c.id}</p>
                      </td>
                      <td className="px-4 py-3.5">
                        <span className={`text-xs font-bold px-2 py-1 rounded uppercase ${TIER_COLORS[c.tier] ?? ""}`}>
                          {c.tier}
                        </span>
                      </td>
                      <td className="px-4 py-3.5 text-right font-medium tabular-nums text-[var(--radar-teal)]">
                        {fmtAum(c.aum)}
                      </td>
                      <td className="px-4 py-3.5 text-xs text-muted-foreground capitalize">
                        {c.risk_tolerance?.toLowerCase() ?? "—"}
                      </td>
                      <td className="px-4 py-3.5 text-xs text-muted-foreground">
                        {c.last_meeting_date ?? "—"}
                      </td>
                      <td className="px-4 py-3.5">
                        <div className="flex flex-wrap gap-1">
                          {badges.length === 0 ? (
                            <span className="text-xs text-[var(--radar-green)]/70">OK</span>
                          ) : (
                            badges.map((b) => (
                              <span
                                key={b}
                                className={`inline-flex items-center gap-0.5 text-[10px] font-medium px-1.5 py-0.5 rounded ${
                                  b === "Drift"
                                    ? "bg-[var(--radar-yellow)]/15 text-[var(--radar-yellow)]"
                                    : "bg-[var(--radar-red)]/15 text-[var(--radar-red)]"
                                }`}
                              >
                                <AlertTriangle className="w-2.5 h-2.5" />
                                {b}
                              </span>
                            ))
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-center">
                        {c.has_portfolio_drift ? (
                          <span className="inline-block w-2 h-2 rounded-full bg-[var(--radar-yellow)]" title="Portfolio drift detected" />
                        ) : (
                          <span className="inline-block w-2 h-2 rounded-full bg-[var(--radar-green)]/50" title="No drift" />
                        )}
                      </td>
                    </tr>
                  );
                })}
          </tbody>
        </table>
        {!loading && sorted.length === 0 && (
          <div className="py-12 text-center text-muted-foreground text-sm">
            No clients found matching your filters.
          </div>
        )}
      </div>
    </div>
  );
}
