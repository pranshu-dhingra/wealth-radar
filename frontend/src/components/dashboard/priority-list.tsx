"use client";

import { useRouter } from "next/navigation";
import { ActionCard } from "./action-card";
import type { TriggerScanResult } from "@/lib/types";

interface PriorityListProps {
  clients: TriggerScanResult[];
  loading?: boolean;
}

function SkeletonRow() {
  return (
    <div className="bg-card border border-border border-l-4 border-l-border rounded-lg px-4 py-3.5 animate-pulse">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-2">
          <div className="h-3.5 bg-secondary rounded w-1/3" />
          <div className="h-3 bg-secondary rounded w-2/3" />
        </div>
        <div className="space-y-1 w-16">
          <div className="h-3 bg-secondary rounded" />
          <div className="h-3 bg-secondary rounded w-10" />
        </div>
      </div>
    </div>
  );
}

export function PriorityList({ clients, loading }: PriorityListProps) {
  const router = useRouter();

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)}
      </div>
    );
  }

  if (!clients.length) {
    return (
      <div className="text-center py-12 text-muted-foreground text-sm">
        No priority clients detected. Run Daily Scan to refresh.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {clients.map((c) => {
        const top = c.triggers[0];
        return (
          <ActionCard
            key={c.client_id}
            clientName={c.client_name}
            clientId={c.client_id}
            tier={c.tier}
            triggerType={c.top_trigger ?? top?.trigger_type ?? "REVIEW"}
            description={top?.description ?? "Multiple triggers detected"}
            priorityScore={c.priority_score}
            aum={c.aum}
            triggerCount={c.triggers.length}
            onClick={() => router.push(`/clients/${c.client_id}`)}
          />
        );
      })}
    </div>
  );
}
