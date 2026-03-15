// ─── Core domain types ───────────────────────────────────────────────────────

export interface Account {
  account_number: string;
  account_type: string;
  custodian?: string;    // used in mock/frontend data
  institution?: string; // actual field name returned by backend API
  balance: number;
  currency?: string;
  is_taxable?: boolean;
}

export interface Address {
  street?: string;
  city?: string;
  state?: string;
  zip?: string;
  country?: string;
}

export interface Holding {
  client_id: string;
  ticker: string;
  name: string;
  asset_class: string;
  account_type?: string;
  shares?: number;
  current_price?: number;
  current_value: number;
  cost_basis?: number;
  unrealized_gain?: number;
  unrealized_gain_pct?: number;
  purchase_date?: string;
  is_taxable?: boolean;
}

export interface Client {
  id: string;
  name: string;
  first_name?: string;
  last_name?: string;
  date_of_birth?: string;
  age?: number;
  tier: "A" | "B" | "C" | "D";
  aum: number;
  email?: string;
  phone?: string;
  occupation?: string;
  risk_tolerance?: string;
  tax_bracket?: string;
  marital_status?: string;
  state?: string;
  last_meeting_date?: string;
  has_portfolio_drift?: boolean;
  target_allocation?: Record<string, number>;
  current_allocation?: Record<string, number>;
  portfolio_drift?: Record<string, number>;
  accounts?: Account[];
  address?: Address;
  holdings?: Holding[];
}

// ─── Trigger / Sentinel types ────────────────────────────────────────────────

export interface Trigger {
  trigger_type: string;
  description: string;
  urgency: number;
  revenue_impact?: number;
  priority_score?: number;
  details?: Record<string, unknown>;
}

export interface TriggerScanResult {
  client_id: string;
  client_name: string;
  tier: string;
  aum: number;
  triggers: Trigger[];
  compound_patterns?: string[];
  priority_score: number;
  top_trigger?: string;
}

// ─── Portfolio / financial analysis ──────────────────────────────────────────

/** One asset class row as returned by /api/portfolio/{id}/drift */
export interface DriftEntry {
  asset_class: string;
  target_pct: number;      // 0–100 scale
  current_pct: number;     // 0–100 scale
  drift_pct: number;       // signed, 0–100 scale
  current_value?: number;
  target_value?: number;
  drift_amount?: number;
  action_required?: boolean;
  status?: string;
}

export interface DriftAnalysis {
  client_id?: string;
  // Actual API response fields (from drift_calculator):
  rebalancing_needed?: boolean;
  total_portfolio_value?: number;
  drifts?: DriftEntry[];
  max_drift_pct?: number;
  suggested_trades?: unknown[];
  explanation?: string;
  // Legacy / fallback fields:
  drift_detected?: boolean;
  drifted_classes?: string[];
  drift_details?: Record<string, { target: number; current: number; drift: number }>;
  message?: string;
}

export interface TLHOpportunity {
  ticker: string;
  loss_amount: number;
  current_value: number;
  cost_basis: number;
  wash_sale_safe?: boolean;
}

export interface PortfolioResponse {
  client_id: string;
  client_name?: string;
  tier?: string;
  aum?: number;
  accounts?: Account[];
  target_allocation?: Record<string, number>;
  current_allocation?: Record<string, number>;
  holdings?: Holding[];
  holdings_allocation?: Record<string, number>;
  total_holdings_value?: number;
  has_portfolio_drift?: boolean;
}

// ─── Agent / orchestrator outputs ────────────────────────────────────────────

export interface ActionItem {
  action: string;
  priority: "high" | "medium" | "low";
  deadline?: string;
  revenue_impact?: number;
  details?: string;
}

export interface MeetingAgenda {
  topics: string[];
  estimated_duration?: string;
  key_documents?: string[];
}

export interface MeetingPrep {
  client_id: string;
  client_name?: string;
  trigger_analysis?: TriggerScanResult;
  action_items?: ActionItem[];
  meeting_agenda?: MeetingAgenda;
  document_summary?: string;
  market_context?: string;
  talking_points?: string[];
  outreach_draft?: string;
  error?: string;
}

export interface DailyScanResult {
  morning_briefing?: string;
  top_clients?: TriggerScanResult[];
  cohort_patterns?: string[];
  total_scanned?: number;
  high_priority_count?: number;
}

export interface OutreachEmail {
  subject: string;
  body: string;
  tone?: string;
  disclaimer?: string;
}

// ─── Search ──────────────────────────────────────────────────────────────────

export interface SearchResult {
  id: string;
  score: number;
  type: string;
  client_id?: string;
  source_file?: string;
  page_num?: number;
  text_preview?: string;
}

export interface SearchResponse {
  query: string;
  client_id?: string;
  modality?: string;
  total: number;
  results: SearchResult[];
}

// ─── Market Events ────────────────────────────────────────────────────────────

export interface MarketEvent {
  id: string;
  date: string;
  event_type?: string;
  title: string;
  description?: string;
  severity: "HIGH" | "MEDIUM" | "LOW" | "INFO";
  affected_sectors?: string[];
  affected_tickers?: string[];
  recommended_action?: string;
  trigger_types?: string[];
}

// ─── SSE event types ──────────────────────────────────────────────────────────

export type AgentEventType = "status" | "tool_call" | "result" | "error" | "done" | "thinking";

export interface AgentEvent {
  type: AgentEventType;
  agent?: string;
  message?: string;
  data?: unknown;
  content?: string;
  timestamp?: number;
}
