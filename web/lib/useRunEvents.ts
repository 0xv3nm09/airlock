"use client";

/* Live run state: a reducer over the SSE event stream.
 * Replaying a run's events rebuilds exactly what was shown live — the trace is the truth.
 * Every event is applied once, keyed by its seq: EventSource auto-reconnects replay the
 * history after a reconnect, and double-applying would duplicate findings and counters. */
import { useEffect, useState } from "react";
import { DEMO, demoSnapshot } from "./demo";
import type {
  AirlockEvent,
  Counters,
  Finding,
  Intent,
  RunStatus,
  Verdict,
} from "./types";

export interface SpanView {
  spanKey: string;
  name: string;
  state: "running" | "done" | "failed";
  durationMs?: number;
  data: Record<string, unknown>;
}

export interface RunView {
  status: RunStatus | "connecting";
  spans: SpanView[];
  logs: { base: string[]; pr: string[] };
  findings: Finding[];
  counters: Counters;
  verdict?: Verdict;
  intent?: Intent;
  error?: string;
  trace: AirlockEvent[];
  seen: number[];
}

const INITIAL: RunView = {
  status: "connecting",
  spans: [],
  logs: { base: [], pr: [] },
  findings: [],
  counters: { network_blocked: 0, canary_hits: 0, writes_denied: 0, limits_hit: 0 },
  trace: [],
  seen: [],
};

const TERMINAL: RunStatus[] = ["completed", "failed", "cancelled"];

function reduce(v: RunView, e: AirlockEvent): RunView {
  if (v.seen.includes(e.seq)) return v;
  const base: RunView = { ...v, seen: [...v.seen, e.seq], trace: [...v.trace, e] };
  const d = e.data ?? {};
  const spanKey = typeof d.span_key === "string" ? d.span_key : e.name;
  switch (e.type) {
    case "span_start": {
      if (base.spans.some((s) => s.spanKey === spanKey)) return base;
      return {
        ...base,
        spans: [...base.spans, { spanKey, name: e.name, state: "running", data: d }],
      };
    }
    case "span_end": {
      const spans = base.spans.some((s) => s.spanKey === spanKey)
        ? base.spans.map((s) =>
            s.spanKey === spanKey
              ? {
                  ...s,
                  state: d.error ? ("failed" as const) : ("done" as const),
                  durationMs: typeof d.duration_ms === "number" ? d.duration_ms : undefined,
                  data: { ...s.data, ...d },
                }
              : s,
          )
        : [
            ...base.spans,
            {
              spanKey,
              name: e.name,
              state: d.error ? ("failed" as const) : ("done" as const),
              durationMs: typeof d.duration_ms === "number" ? d.duration_ms : undefined,
              data: d,
            },
          ];
      return { ...base, spans };
    }
    case "log": {
      const ref = d.ref === "pr" ? "pr" : "base";
      const tail = typeof d.tail === "string" ? d.tail : "";
      return { ...base, logs: { ...base.logs, [ref]: [...base.logs[ref], tail] } };
    }
    case "finding": {
      const finding: Finding = {
        id: String(d.id ?? ""),
        category: e.name as Finding["category"],
        severity: (d.severity as Finding["severity"]) ?? "medium",
        title: String(d.title ?? ""),
        proven: Number(d.confidence) >= 0.85,
        confidence: Number(d.confidence ?? 0),
        evidence: Array.isArray(d.evidence) ? (d.evidence as Finding["evidence"]) : [],
      };
      return { ...base, findings: [...base.findings, finding] };
    }
    case "containment": {
      const key = (
        {
          network_blocked: "network_blocked",
          canary_hit: "canary_hits",
          write_denied: "writes_denied",
          limit_hit: "limits_hit",
        } as const
      )[e.name as "network_blocked" | "canary_hit" | "write_denied" | "limit_hit"];
      if (!key) return base;
      const counters: Counters = { ...base.counters };
      counters[key] += 1;
      return { ...base, counters };
    }
    case "verdict": {
      const verdict: Verdict = {
        label: e.name as Verdict["label"],
        confidence: Number(d.confidence ?? 0),
        route: (d.route as Verdict["route"]) ?? "auto",
        summary: String(d.summary ?? ""),
        reasons: Array.isArray(d.reasons) ? (d.reasons as string[]) : [],
        cited_findings: Array.isArray(d.cited) ? (d.cited as string[]) : [],
      };
      return { ...base, verdict };
    }
    case "status": {
      return {
        ...base,
        status: e.name as RunStatus,
        error: e.name === "failed" ? "the run failed; see the trace" : base.error,
      };
    }
    case "error": {
      return { ...base, error: String(d.message ?? "run error") };
    }
    default:
      return base;
  }
}

/** Static demo: rebuild the exact view a completed run showed live by folding its
 * recorded trace through the same reducer the SSE stream uses — the trace is the truth. */
export function foldTrace(events: AirlockEvent[]): RunView {
  return events.reduce(reduce, INITIAL);
}

export function useRunEvents(runId: string): RunView {
  const [view, setView] = useState<RunView>(INITIAL);

  useEffect(() => {
    if (!runId) return;
    let alive = true;
    if (DEMO) {
      queueMicrotask(() => {
        if (alive) setView(foldTrace(demoSnapshot.traces[runId] ?? []));
      });
      return () => {
        alive = false;
      };
    }
    let es: EventSource | null = null;
    queueMicrotask(() => {
      if (!alive) return;
      setView(INITIAL);
      const source = new EventSource(`/api/v1/runs/${runId}/events`);
      es = source;
      const types = [
        "status",
        "span_start",
        "span_end",
        "log",
        "finding",
        "containment",
        "verdict",
        "error",
      ];
      for (const t of types) {
        source.addEventListener(t, (m) => {
          try {
            const event = JSON.parse((m as MessageEvent).data) as AirlockEvent;
            setView((v) => reduce(v, event));
            if (event.type === "status" && TERMINAL.includes(event.name as RunStatus)) {
              source.close(); // run over — stop the auto-reconnect replay loop
            }
          } catch {
            /* ignore malformed frames */
          }
        });
      }
      source.onerror = () => {
        // EventSource auto-reconnects; reconnect replays history, which the seq guard dedupes.
        setView((v) => (v.status === "connecting" ? { ...v, status: "queued" } : v));
      };
    });
    return () => {
      alive = false;
      es?.close();
    };
  }, [runId]);

  return view;
}
