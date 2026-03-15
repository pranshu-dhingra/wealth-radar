"use client";

import { useState, useMemo } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Holding } from "@/lib/types";

const col = createColumnHelper<Holding>();

function fmt$(v?: number) {
  if (v == null) return "—";
  return v >= 0
    ? `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`
    : `-$${Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

function fmtPct(v?: number) {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
}

const COLUMNS = [
  col.accessor("ticker", {
    header: "Ticker",
    cell: (info) => (
      <span className="font-mono font-bold text-foreground text-xs">{info.getValue()}</span>
    ),
  }),
  col.accessor("name", {
    header: "Name",
    cell: (info) => (
      <span className="text-xs text-muted-foreground truncate max-w-[160px] block">{info.getValue()}</span>
    ),
  }),
  col.accessor("asset_class", {
    header: "Class",
    cell: (info) => (
      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-secondary text-muted-foreground uppercase tracking-wide">
        {info.getValue().replace(/_/g, " ")}
      </span>
    ),
  }),
  col.accessor("current_value", {
    header: "Value",
    cell: (info) => (
      <span className="text-xs font-mono text-foreground tabular-nums">{fmt$(info.getValue())}</span>
    ),
  }),
  col.accessor("unrealized_gain", {
    header: "Unreal. P&L",
    cell: (info) => {
      const v = info.getValue();
      if (v == null) return <span className="text-xs text-muted-foreground">—</span>;
      return (
        <span className={cn("text-xs font-mono tabular-nums", v >= 0 ? "text-[var(--radar-green)]" : "text-[var(--radar-red)]")}>
          {fmt$(v)}
        </span>
      );
    },
  }),
  col.accessor("unrealized_gain_pct", {
    header: "P&L %",
    cell: (info) => {
      const v = info.getValue();
      if (v == null) return <span className="text-xs text-muted-foreground">—</span>;
      return (
        <span className={cn("text-xs font-mono tabular-nums", v >= 0 ? "text-[var(--radar-green)]" : "text-[var(--radar-red)]")}>
          {fmtPct(v)}
        </span>
      );
    },
  }),
  col.accessor("account_type", {
    header: "Account",
    cell: (info) => (
      <span className="text-[10px] text-muted-foreground">{info.getValue() ?? "—"}</span>
    ),
  }),
  col.accessor("is_taxable", {
    header: "Taxable",
    cell: (info) => {
      const v = info.getValue();
      if (v == null) return <span className="text-xs text-muted-foreground">—</span>;
      return (
        <span className={cn("text-[10px] font-medium", v ? "text-[var(--radar-yellow)]" : "text-muted-foreground")}>
          {v ? "Yes" : "No"}
        </span>
      );
    },
  }),
];

interface HoldingsTableProps {
  holdings: Holding[];
  className?: string;
}

export function HoldingsTable({ holdings, className }: HoldingsTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "current_value", desc: true },
  ]);

  const table = useReactTable({
    data: holdings,
    columns: COLUMNS,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  if (!holdings.length) {
    return <p className="text-sm text-muted-foreground py-4 text-center">No holdings data available.</p>;
  }

  return (
    <div className={cn("overflow-x-auto", className)}>
      <table className="w-full text-left">
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} className="border-b border-border">
              {hg.headers.map((header) => {
                const sorted = header.column.getIsSorted();
                const canSort = header.column.getCanSort();
                return (
                  <th
                    key={header.id}
                    onClick={canSort ? header.column.getToggleSortingHandler() : undefined}
                    className={cn(
                      "px-3 py-2 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider",
                      canSort && "cursor-pointer select-none hover:text-foreground",
                    )}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {canSort && (
                        sorted === "asc"  ? <ArrowUp className="w-3 h-3" /> :
                        sorted === "desc" ? <ArrowDown className="w-3 h-3" /> :
                        <ArrowUpDown className="w-3 h-3 opacity-30" />
                      )}
                    </div>
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="border-b border-border/40 hover:bg-secondary/20 transition-colors">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-3 py-2">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
