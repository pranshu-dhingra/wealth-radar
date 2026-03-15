import type {
  Client,
  TriggerScanResult,
  PortfolioResponse,
  DriftAnalysis,
  MeetingPrep,
  DailyScanResult,
  SearchResponse,
  AgentEvent,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─── Generic fetch helper ────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ─── Clients ─────────────────────────────────────────────────────────────────

export interface ListClientsParams {
  tier?: string;
  sort?: "aum" | "name" | "tier";
  search?: string;
  limit?: number;
}

export function listClients(params?: ListClientsParams): Promise<Client[]> {
  const q = new URLSearchParams();
  if (params?.tier)   q.set("tier",   params.tier);
  if (params?.sort)   q.set("sort",   params.sort);
  if (params?.search) q.set("search", params.search);
  if (params?.limit)  q.set("limit",  String(params.limit));
  const qs = q.toString();
  return apiFetch<Client[]>(`/api/clients${qs ? "?" + qs : ""}`);
}

export function getClient(clientId: string): Promise<Client> {
  return apiFetch<Client>(`/api/clients/${clientId}`);
}

export function getClientTriggers(clientId: string): Promise<TriggerScanResult> {
  return apiFetch<TriggerScanResult>(`/api/clients/${clientId}/triggers`);
}

// ─── Portfolio ────────────────────────────────────────────────────────────────

export function getPortfolio(clientId: string): Promise<PortfolioResponse> {
  return apiFetch<PortfolioResponse>(`/api/portfolio/${clientId}`);
}

export function getDrift(clientId: string): Promise<DriftAnalysis> {
  return apiFetch<DriftAnalysis>(`/api/portfolio/${clientId}/drift`);
}

export function getOpportunities(clientId: string): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>(`/api/portfolio/${clientId}/opportunities`);
}

// ─── Search ───────────────────────────────────────────────────────────────────

export interface SearchParams {
  query: string;
  client_id?: string;
  top_k?: number;
  modality?: "documents" | "client_data" | "financial";
}

export function semanticSearch(params: SearchParams): Promise<SearchResponse> {
  return apiFetch<SearchResponse>("/api/search", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

// ─── Health ───────────────────────────────────────────────────────────────────

export function getHealth(): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/health");
}

// ─── SSE streaming helper ────────────────────────────────────────────────────

/**
 * Opens an SSE stream against a POST endpoint.
 * Calls onEvent for each parsed event frame, onDone when the stream ends.
 * Returns a cleanup function that aborts the stream.
 */
export function streamAgentSSE(
  path: string,
  body: Record<string, unknown>,
  onEvent: (event: AgentEvent) => void,
  onDone: () => void,
  onError?: (err: Error) => void,
): () => void {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(`SSE ${res.status}: ${res.statusText}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // SSE frames are separated by double newline
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const line = part.trim();
          if (!line.startsWith("data:")) continue;
          const json = line.slice(5).trim();
          try {
            const event: AgentEvent = JSON.parse(json);
            onEvent(event);
            if (event.type === "done") { onDone(); return; }
          } catch {
            // malformed JSON — skip
          }
        }
      }
      onDone();
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      onError?.(err as Error);
    }
  })();

  return () => controller.abort();
}

// ─── WebSocket manager ───────────────────────────────────────────────────────

export interface WSMessage {
  task: string;
  client_id?: string;
}

export interface WSEvent {
  type: string;
  content?: string;
  agent?: string;
  timestamp?: number;
}

export class AgentWebSocket {
  private ws: WebSocket | null = null;
  private url: string;
  onMessage: ((event: WSEvent) => void) | null = null;
  onOpen: (() => void) | null = null;
  onClose: (() => void) | null = null;
  onError: ((err: Event) => void) | null = null;

  constructor(url = `ws://localhost:8000/ws/agent-stream`) {
    this.url = url;
  }

  connect(): void {
    this.ws = new WebSocket(this.url);
    this.ws.onopen  = () => this.onOpen?.();
    this.ws.onclose = () => this.onClose?.();
    this.ws.onerror = (e) => this.onError?.(e);
    this.ws.onmessage = (e) => {
      try { this.onMessage?.(JSON.parse(e.data) as WSEvent); }
      catch { /* ignore */ }
    };
  }

  send(msg: WSMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  close(): void {
    this.ws?.close();
  }

  get isOpen(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
