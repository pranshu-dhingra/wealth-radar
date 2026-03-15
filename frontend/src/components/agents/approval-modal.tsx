"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, Edit3, RefreshCw, Copy, Check } from "lucide-react";
import { cn } from "@/lib/utils";

type ApprovalState = "review" | "editing" | "approved" | "rejected";

interface ApprovalWorkflowProps {
  title: string;
  content: string;
  onApprove?: (finalContent: string) => void;
  onReject?: () => void;
  onRegenerate?: () => void;
  className?: string;
}

export function ApprovalWorkflow({
  title,
  content,
  onApprove,
  onReject,
  onRegenerate,
  className,
}: ApprovalWorkflowProps) {
  const [state, setState]       = useState<ApprovalState>("review");
  const [edited, setEdited]     = useState(content);
  const [copied, setCopied]     = useState(false);

  function handleApprove() {
    setState("approved");
    onApprove?.(state === "editing" ? edited : content);
  }

  function handleCopy() {
    navigator.clipboard.writeText(state === "editing" ? edited : content).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (state === "approved") {
    return (
      <div className={cn("bg-[var(--radar-green)]/10 border border-[var(--radar-green)]/30 rounded-lg p-6 text-center", className)}>
        <CheckCircle2 className="w-10 h-10 text-[var(--radar-green)] mx-auto mb-3" />
        <p className="text-sm font-semibold text-[var(--radar-green)]">Approved & Saved</p>
        <p className="text-xs text-muted-foreground mt-1">{title} has been approved.</p>
        <button onClick={() => setState("review")} className="mt-3 text-xs text-[var(--radar-teal)] hover:underline">
          Review again
        </button>
      </div>
    );
  }

  if (state === "rejected") {
    return (
      <div className={cn("bg-[var(--radar-red)]/10 border border-[var(--radar-red)]/30 rounded-lg p-6 text-center", className)}>
        <XCircle className="w-10 h-10 text-[var(--radar-red)] mx-auto mb-3" />
        <p className="text-sm font-semibold text-[var(--radar-red)]">Rejected</p>
        <p className="text-xs text-muted-foreground mt-1">The generated content was not approved.</p>
        {onRegenerate && (
          <button
            onClick={() => { setState("review"); onRegenerate(); }}
            className="mt-3 flex items-center gap-1 text-xs text-[var(--radar-teal)] hover:underline mx-auto"
          >
            <RefreshCw className="w-3 h-3" /> Regenerate
          </button>
        )}
      </div>
    );
  }

  return (
    <div className={cn("space-y-3", className)}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded bg-secondary text-muted-foreground hover:text-foreground transition-colors"
          >
            {copied ? <Check className="w-3 h-3 text-[var(--radar-green)]" /> : <Copy className="w-3 h-3" />}
            {copied ? "Copied" : "Copy"}
          </button>
          {state === "review" && (
            <button
              onClick={() => setState("editing")}
              className="flex items-center gap-1 text-[10px] font-medium px-2 py-1 rounded bg-secondary text-muted-foreground hover:text-foreground transition-colors"
            >
              <Edit3 className="w-3 h-3" /> Edit
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      {state === "editing" ? (
        <textarea
          value={edited}
          onChange={(e) => setEdited(e.target.value)}
          rows={12}
          className="w-full bg-[hsl(220,26%,5%)] border border-border rounded-lg p-4 text-xs text-foreground font-mono resize-y focus:outline-none focus:border-[var(--radar-teal)]"
        />
      ) : (
        <div className="bg-[hsl(220,26%,5%)] border border-border rounded-lg p-4 max-h-80 overflow-y-auto">
          <pre className="text-xs text-foreground/90 whitespace-pre-wrap break-words font-mono leading-relaxed">
            {content}
          </pre>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleApprove}
          className="flex items-center gap-1.5 px-4 py-2 rounded-md text-xs font-semibold bg-[var(--radar-green)]/15 text-[var(--radar-green)] hover:bg-[var(--radar-green)]/25 border border-[var(--radar-green)]/30 transition-colors"
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          Approve{state === "editing" ? " Edits" : ""}
        </button>
        {onRegenerate && (
          <button
            onClick={onRegenerate}
            className="flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium bg-secondary text-muted-foreground hover:text-foreground transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> Regenerate
          </button>
        )}
        <button
          onClick={() => setState("rejected")}
          className="flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium bg-[var(--radar-red)]/10 text-[var(--radar-red)] hover:bg-[var(--radar-red)]/20 transition-colors ml-auto"
        >
          <XCircle className="w-3.5 h-3.5" /> Reject
        </button>
      </div>
    </div>
  );
}
