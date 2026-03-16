"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("App error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-background p-8 text-center">
      <h2 className="text-lg font-semibold text-foreground mb-2">Something went wrong</h2>
      <pre className="text-xs text-muted-foreground bg-secondary rounded p-4 max-w-2xl w-full text-left overflow-auto mb-4 whitespace-pre-wrap">
        {error?.message ?? "Unknown error"}
        {error?.stack ? `\n\n${error.stack}` : ""}
      </pre>
      <button
        onClick={reset}
        className="px-4 py-2 rounded bg-[var(--radar-teal)] text-background text-sm font-semibold hover:opacity-90"
      >
        Try again
      </button>
    </div>
  );
}
