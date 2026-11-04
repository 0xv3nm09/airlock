"use client";

import { Card, CardTitle } from "@/components/ui";
import { IconBan, IconCheck, IconSpinner } from "@/components/Icons";
import type { SpanView } from "@/lib/useRunEvents";

function humanSpan(name: string, data: Record<string, unknown>): string {
  const ref = typeof data.ref === "string" ? data.ref : "";
  const step = typeof data.step === "string" ? data.step : "";
  switch (name) {
    case "github.fetch_pr":
      return "Fetch pull request";
    case "preflight.static":
      return "Pre-flight · injection & static risk";
    case "preflight.osv":
      return "Pre-flight · known-malware check";
    case "agent.planner":
      return "Planner agent";
    case "agent.fixer":
      return "Fixer agent";
    case "agent.test_writer":
      return "Test-writer agent";
    case "agent.analyst":
      return "Security analyst";
    case "agent.reporter":
      return "Reporter agent";
    case "sandbox.create":
      return "Sandboxes created (base + PR)";
    case "sandbox.destroy":
      return "Sandboxes destroyed";
    case "sandbox.exec":
      return `Sandbox${ref ? ` (${ref})` : ""}${step ? ` · ${step}` : ""}`;
    case "sandbox.behaviour":
      return "Behaviour scan";
    default:
      return name;
  }
}

export function Timeline({ spans }: { spans: SpanView[] }) {
  return (
    <Card>
      <CardTitle hint="live">Run timeline</CardTitle>
      {spans.length === 0 ? (
        <p className="text-sm text-muted">Waiting for the first step…</p>
      ) : (
        <ol className="flex flex-col gap-1">
          {spans.map((s) => (
            <li
              key={s.spanKey}
              className="flex items-center gap-3 rounded-lg px-2 py-2 text-sm hover:bg-surface-2"
            >
              {s.state === "running" ? (
                <IconSpinner className="shrink-0 text-info" />
              ) : s.state === "failed" ? (
                <IconBan className="shrink-0 text-danger" />
              ) : (
                <IconCheck className="shrink-0 text-success" />
              )}
              <span className="min-w-0 flex-1 truncate" title={s.name}>
                {humanSpan(s.name, s.data)}
                {s.name === "agent.planner" && s.data.fallback ? " (fallback plan)" : ""}
              </span>
              {typeof s.data.exit_code === "number" ? (
                <span
                  className={`font-mono text-xs ${s.data.exit_code === 0 ? "text-success" : "text-danger-text"}`}
                >
                  exit {s.data.exit_code}
                </span>
              ) : null}
              {typeof s.durationMs === "number" ? (
                <span className="w-16 text-right font-mono text-xs text-muted">
                  {s.durationMs >= 1000 ? `${(s.durationMs / 1000).toFixed(1)}s` : `${Math.round(s.durationMs)}ms`}
                </span>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
