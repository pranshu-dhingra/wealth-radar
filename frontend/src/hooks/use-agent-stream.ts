"use client";

import { useState, useCallback, useRef } from "react";
import { streamAgentSSE } from "@/lib/api";
import type { AgentEvent } from "@/lib/types";

export interface AgentStreamState {
  events: AgentEvent[];
  running: boolean;
  done: boolean;
  error: string | null;
  result: unknown;
}

export function useAgentStream() {
  const [state, setState] = useState<AgentStreamState>({
    events: [],
    running: false,
    done: false,
    error: null,
    result: null,
  });
  const stopRef = useRef<(() => void) | null>(null);

  const start = useCallback(
    (path: string, body: Record<string, unknown>) => {
      stopRef.current?.();
      setState({ events: [], running: true, done: false, error: null, result: null });

      const stop = streamAgentSSE(
        path,
        body,
        (event: AgentEvent) => {
          setState((prev) => ({
            ...prev,
            events: [...prev.events, event],
            result: event.type === "result" ? (event.data ?? event.content ?? prev.result) : prev.result,
          }));
        },
        () => {
          setState((prev) => ({ ...prev, running: false, done: true }));
        },
        (err: Error) => {
          setState((prev) => ({
            ...prev,
            running: false,
            error: err.message,
            events: [...prev.events, { type: "error", message: err.message }],
          }));
        },
      );
      stopRef.current = stop;
    },
    [],
  );

  const stop = useCallback(() => {
    stopRef.current?.();
    setState((prev) => ({ ...prev, running: false }));
  }, []);

  const reset = useCallback(() => {
    stopRef.current?.();
    setState({ events: [], running: false, done: false, error: null, result: null });
  }, []);

  return { ...state, start, stop, reset };
}
