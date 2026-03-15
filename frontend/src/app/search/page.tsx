"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Search, FileText, User, TrendingUp, Loader2, AlertCircle } from "lucide-react";
import { semanticSearch } from "@/lib/api";
import type { SearchResult } from "@/lib/types";

const MODALITIES = [
  { id: "all",          label: "All",          icon: Search      },
  { id: "documents",    label: "Documents",    icon: FileText    },
  { id: "client_data",  label: "Client Data",  icon: User        },
  { id: "financial",    label: "Financial",    icon: TrendingUp  },
] as const;

type Modality = typeof MODALITIES[number]["id"];

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, score)) * 100);
  const color =
    pct >= 70 ? "bg-[var(--radar-green)]" :
    pct >= 40 ? "bg-[var(--radar-teal)]" :
                "bg-[var(--radar-yellow)]";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1 w-20 bg-secondary rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-muted-foreground tabular-nums">{pct}%</span>
    </div>
  );
}

function TypeBadge({ type }: { type: string }) {
  const map: Record<string, string> = {
    document:    "bg-blue-500/10 text-blue-400",
    client:      "bg-[var(--radar-teal)]/10 text-[var(--radar-teal)]",
    holding:     "bg-[var(--radar-green)]/10 text-[var(--radar-green)]",
    transaction: "bg-[var(--radar-yellow)]/10 text-[var(--radar-yellow)]",
  };
  return (
    <span className={`text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 rounded ${map[type] ?? "bg-secondary text-muted-foreground"}`}>
      {type}
    </span>
  );
}

function ResultCard({ result, onClick }: { result: SearchResult; onClick?: () => void }) {
  return (
    <div
      className={`bg-card border border-border rounded-lg p-4 space-y-2 ${onClick ? "cursor-pointer hover:bg-secondary/20 transition-colors" : ""}`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <TypeBadge type={result.type} />
          {result.client_id && (
            <span className="text-xs font-mono text-muted-foreground">{result.client_id}</span>
          )}
          {result.source_file && (
            <span className="text-xs text-muted-foreground truncate max-w-[200px]">{result.source_file}</span>
          )}
          {result.page_num != null && (
            <span className="text-xs text-muted-foreground">p.{result.page_num}</span>
          )}
        </div>
        <ScoreBar score={result.score} />
      </div>
      {result.text_preview && (
        <p className="text-sm text-muted-foreground leading-relaxed line-clamp-3">
          {result.text_preview}
        </p>
      )}
    </div>
  );
}

export default function SearchPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [modality, setModality] = useState<Modality>("all");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function runSearch(q = query) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await semanticSearch({
        query: q.trim(),
        modality: modality === "all" ? undefined : modality,
        top_k: 20,
      });
      setResults(resp.results);
      setTotal(resp.total);
    } catch (err) {
      setError((err as Error).message);
      setResults(null);
    } finally {
      setLoading(false);
    }
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter") runSearch();
  }

  function navigateToResult(r: SearchResult) {
    if (r.client_id) router.push(`/clients/${r.client_id}`);
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-foreground">Semantic Search</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Search across client data, documents, and financial records using AI embeddings.
        </p>
      </div>

      {/* Search bar */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search clients, documents, holdings, transactions…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKey}
            className="w-full pl-10 pr-28 py-3 text-sm bg-card border border-border rounded-lg text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-[var(--radar-teal)]"
          />
          <button
            onClick={() => runSearch()}
            disabled={loading || !query.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-1.5 text-xs font-medium bg-[var(--radar-teal)] text-background rounded-md disabled:opacity-40 hover:opacity-90 transition-opacity"
          >
            {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Search"}
          </button>
        </div>

        {/* Modality tabs */}
        <div className="flex items-center gap-1 bg-secondary border border-border rounded-md p-1 w-fit">
          {MODALITIES.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setModality(id)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                modality === id
                  ? "bg-[var(--radar-teal)] text-background"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="w-3 h-3" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Suggested queries (empty state) */}
      {results === null && !loading && !error && (
        <div className="space-y-3">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">Suggested queries</p>
          <div className="flex flex-wrap gap-2">
            {[
              "clients approaching RMD age",
              "trust documents executed before 2022",
              "equity overweight rebalancing",
              "Roth conversion candidates",
              "tax-loss harvesting opportunities",
              "clients with portfolio drift",
            ].map((q) => (
              <button
                key={q}
                onClick={() => { setQuery(q); runSearch(q); }}
                className="px-3 py-1.5 text-xs bg-secondary border border-border rounded-md text-muted-foreground hover:text-foreground hover:border-[var(--radar-teal)]/40 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-start gap-3 p-4 bg-[var(--radar-red)]/10 border border-[var(--radar-red)]/20 rounded-lg">
          <AlertCircle className="w-4 h-4 text-[var(--radar-red)] shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-[var(--radar-red)]">Search unavailable</p>
            <p className="text-xs text-muted-foreground mt-0.5">{error}</p>
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-card border border-border rounded-lg p-4 animate-pulse space-y-2">
              <div className="flex gap-2">
                <div className="h-4 w-16 bg-secondary rounded" />
                <div className="h-4 w-24 bg-secondary rounded" />
              </div>
              <div className="h-3 bg-secondary rounded w-full" />
              <div className="h-3 bg-secondary rounded w-3/4" />
            </div>
          ))}
        </div>
      )}

      {/* Results */}
      {results !== null && !loading && (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            {total} result{total !== 1 ? "s" : ""} for <span className="text-foreground font-medium">&ldquo;{query}&rdquo;</span>
          </p>
          {results.length === 0 ? (
            <div className="py-12 text-center text-muted-foreground text-sm">
              No results found. Try a different query or modality.
            </div>
          ) : (
            results.map((r) => (
              <ResultCard
                key={r.id}
                result={r}
                onClick={r.client_id ? () => navigateToResult(r) : undefined}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
