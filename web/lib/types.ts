/* Hand-written mirrors of the backend contracts (app/schemas.py, Event catalogue).
 * Swap to openapi-typescript generation when the API surface settles. */

export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type VerdictLabel = "safe_to_merge" | "needs_changes" | "suspicious" | "inconclusive";
export type Route = "auto" | "human_review";
export type Severity = "info" | "low" | "medium" | "high" | "critical";
export type FindingCategory =
  | "known_malicious_dependency"
  | "young_package"
  | "prompt_injection"
  | "network_attempt"
  | "secret_access"
  | "fs_escape_attempt"
  | "resource_abuse"
  | "test_regression"
  | "bug_proven"
  | "setup_failure";

export interface Evidence {
  kind: string;
  step_id?: string | null;
  excerpt?: string;
  command?: string | null;
  exit_code?: number | null;
}

export interface Finding {
  id: string;
  category: FindingCategory;
  severity: Severity;
  title: string;
  proven: boolean;
  confidence: number;
  evidence: Evidence[];
}

export interface Verdict {
  label: VerdictLabel;
  confidence: number;
  route: Route;
  summary: string;
  reasons: string[];
  cited_findings: string[];
}

export interface Intent {
  intent: "benign" | "data_theft" | "backdoor" | "sabotage" | "cryptomining" | "unclear";
  explanation: string;
  cited_evidence: string[];
  confidence: number;
}

export interface Counters {
  network_blocked: number;
  canary_hits: number;
  writes_denied: number;
  limits_hit: number;
}

export interface RunOut {
  id: string;
  owner_id: string;
  is_demo: boolean;
  status: RunStatus;
  pr_url: string;
  policy_version: string;
  verdict: Verdict | null;
  intent: Intent | null;
  findings: Finding[];
  counters: Counters;
  usage: { prompt_tokens: number; completion_tokens: number; llm_calls: number };
  error: string | null;
  human_decision: "approved" | "rejected" | null;
  human_note: string;
  decided_by: string | null;
  created_at: string;
  finished_at: string | null;
}

/* --- trace events (SSE + /trace) --- */

export type EventType =
  | "status"
  | "span_start"
  | "span_end"
  | "log"
  | "finding"
  | "containment"
  | "verdict"
  | "error";

export interface AirlockEvent {
  run_id: string;
  seq: number;
  ts: string;
  type: EventType;
  name: string;
  data: Record<string, unknown>;
}

/* --- benchmark --- */

export interface BenchmarkRow {
  name: string;
  got: string;
  expected: string;
  verdict_ok: boolean;
  findings_ok: boolean;
  duration_s: number;
  findings: string[];
  tokens?: number;
  llm_calls?: number;
}

export interface BenchmarkCase {
  name: string;
  url: string;
  expected: string;
}

export interface BenchmarkResult {
  generated_at: string;
  mode?: string;
  all_ok: boolean;
  metrics: Record<string, string | number>;
  rows: BenchmarkRow[];
}
