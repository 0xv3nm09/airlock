/* API client. Same-origin /api proxy (next.config.ts rewrites) → FastAPI.
 * API key lives in localStorage; demo endpoints need no key.
 * Static GitHub Pages build (DEMO): reads resolve from the committed snapshot of real
 * recorded runs; writes fail with a clear pointer to the live deployment. */

import { DEMO, demoRunById, demoSnapshot } from "./demo";

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message || code);
    this.status = status;
    this.code = code;
  }
}

const KEY_STORAGE = "airlock_key";

export function getKey(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(KEY_STORAGE) ?? "";
}

export async function setKey(key: string): Promise<void> {
  if (key.trim()) {
    window.localStorage.setItem(KEY_STORAGE, key.trim());
    // Also set the HttpOnly cookie session: EventSource cannot send headers, so the live
    // timeline for owner runs depends on the cookie (POST /v1/auth/session). No session
    // exists on the static demo — there is no backend to authenticate against.
    if (!DEMO) {
      await fetch("/api/v1/auth/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: key.trim() }),
      }).catch(() => undefined);
    }
  } else {
    window.localStorage.removeItem(KEY_STORAGE);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const key = getKey();
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(key ? { "X-API-Key": key } : {}),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as
      | { error?: string; message?: string }
      | null;
    throw new ApiError(res.status, body?.error ?? "request_failed", body?.message ?? res.statusText);
  }
  return (await res.json()) as T;
}

/** Raised when the static demo is asked to do something only the live deployment can. */
function demoReadOnly(): ApiError {
  return new ApiError(
    403,
    "demo_readonly",
    "This public demo serves recorded runs — creating runs, benchmark runs and decisions happen on the live deployment.",
  );
}

export const api = {
  demoRun: (scenario: "clean" | "buggy" | "malicious") =>
    DEMO
      ? Promise.reject(demoReadOnly())
      : request<{ id: string }>("/v1/demo/runs", {
          method: "POST",
          body: JSON.stringify({ scenario }),
        }),
  seedLibrary: () =>
    DEMO
      ? Promise.reject(demoReadOnly())
      : request<{ enqueued: number; run_ids: string[] }>("/v1/demo/seed-library", {
          method: "POST",
        }),
  createRun: (prUrl: string) =>
    DEMO
      ? Promise.reject(demoReadOnly())
      : request<{ id: string }>("/v1/runs", {
          method: "POST",
          body: JSON.stringify({ pr_url: prUrl }),
        }),
  getRun: (id: string) => {
    if (DEMO) {
      const run = demoRunById(id);
      return run
        ? Promise.resolve(run)
        : Promise.reject(new ApiError(404, "not_found", "run not found in the recorded demo data"));
    }
    return request<import("./types").RunOut>(`/v1/runs/${id}`);
  },
  listRuns: () =>
    DEMO ? Promise.resolve(demoSnapshot.runs) : request<import("./types").RunOut[]>("/v1/runs"),
  trace: (id: string) =>
    DEMO
      ? Promise.resolve(demoSnapshot.traces[id] ?? [])
      : request<import("./types").AirlockEvent[]>(`/v1/runs/${id}/trace`),
  decide: (id: string, decision: "approved" | "rejected", note: string) =>
    DEMO
      ? Promise.reject(demoReadOnly())
      : request<import("./types").RunOut>(`/v1/runs/${id}/decision`, {
          method: "POST",
          body: JSON.stringify({ decision, note }),
        }),
  readyz: () =>
    DEMO
      ? Promise.resolve(demoSnapshot.readyz)
      : request<{ status: string; llm: string; sandbox: string; policy_version: string }>(
          "/readyz",
        ),
  stats: () =>
    DEMO
      ? Promise.resolve(demoSnapshot.stats as unknown as LiveStats)
      : request<LiveStats>("/v1/stats"),
  recentRuns: (limit = 25) =>
    DEMO
      ? Promise.resolve((demoSnapshot.recent as RecentRun[]).slice(0, limit))
      : request<RecentRun[]>(`/v1/runs/recent?limit=${limit}`),
  benchmark: () => {
    if (DEMO) {
      return demoSnapshot.benchmark
        ? Promise.resolve(demoSnapshot.benchmark)
        : Promise.reject(new ApiError(404, "not_found", "no benchmark results in the snapshot"));
    }
    return request<import("./types").BenchmarkResult>("/v1/benchmark/latest");
  },
  benchmarkCases: () =>
    DEMO
      ? Promise.resolve(demoSnapshot.benchmark_cases)
      : request<import("./types").BenchmarkCase[]>("/v1/benchmark/cases"),
  benchmarkRun: (name: string) =>
    DEMO
      ? Promise.reject(demoReadOnly())
      : request<{ id: string }>(`/v1/benchmark/run/${encodeURIComponent(name)}`, {
          method: "POST",
        }),
  adminKeys: () =>
    DEMO ? Promise.reject(demoReadOnly()) : request<ApiKeyInfo[]>("/v1/admin/keys"),
  createKey: (ownerId: string) =>
    DEMO
      ? Promise.reject(demoReadOnly())
      : request<ApiKeyCreated>("/v1/admin/keys", {
          method: "POST",
          body: JSON.stringify({ owner_id: ownerId }),
        }),
  revokeKey: (keyId: string) =>
    DEMO
      ? Promise.reject(demoReadOnly())
      : request<ApiKeyInfo>(`/v1/admin/keys/${encodeURIComponent(keyId)}/revoke`, {
          method: "POST",
        }),
};

export interface ApiKeyInfo {
  key_id: string;
  owner_id: string;
  scopes: string[];
  revoked: boolean;
  created_at: string;
}

export interface ApiKeyCreated {
  key_id: string;
  key: string; // shown once — only the hash is stored server-side
  owner_id: string;
  scopes: string[];
  revoked: boolean;
}

export interface LiveStats {
  runs_total: number;
  runs_completed: number;
  suspicious: number;
  needs_changes: number;
  safe_to_merge: number;
  inconclusive: number;
  attacks_contained: number;
  tokens_total: number;
  llm_calls_total: number;
  avg_tokens_per_run: number;
  policy_version: string;
  llm: string;
  sandbox: string;
  sandboxes_created: number;
  uptime_s: number;
}

export interface RecentRun {
  id: string;
  pr_url: string;
  status: string;
  verdict: string | null;
  confidence: number | null;
  counters: {
    network_blocked: number;
    canary_hits: number;
    writes_denied: number;
    limits_hit: number;
  };
  usage: { prompt_tokens: number; completion_tokens: number; llm_calls: number };
  created_at: string;
  containment: Array<{ name: string; detail: string; ts: string }>;
}
