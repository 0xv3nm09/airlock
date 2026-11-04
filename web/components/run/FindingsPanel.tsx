"use client";

import { useEffect, useState } from "react";
import { Badge, Button, Card, CardTitle } from "@/components/ui";
import { IconBan, IconCheck, IconTriangleAlert, IconX } from "@/components/Icons";
import { SEVERITY_TONE } from "./RunHeader";
import type { Finding } from "@/lib/types";

const CONFIDENCE_EXPLAIN: Record<string, string> = {
  "0.95": "failure reproduced on the PR and passes on base — counted twice",
  "0.9": "observed by the sandbox (network, canary, filesystem)",
  "0.85": "shown by one execution (exit code, timeout)",
  "0.6": "text pattern in the PR text — flagged, not proven",
};

function explain(confidence: number): string {
  const key = Object.keys(CONFIDENCE_EXPLAIN)
    .map(Number)
    .sort((a, b) => b - a)
    .find((k) => confidence >= k - 0.001);
  return key !== undefined ? CONFIDENCE_EXPLAIN[String(key)] : "heuristic signal";
}

export function FindingsPanel({
  findings,
  enriched = [],
}: {
  findings: Finding[];
  enriched?: Finding[];
}) {
  const [selected, setSelected] = useState<Finding | null>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setSelected(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // SSE finding events carry no evidence payload; the run's meta response does.
  const withEvidence = (f: Finding): Finding => {
    const full = enriched.find((m) => m.id === f.id);
    return full && full.evidence.length > 0 ? { ...f, evidence: full.evidence } : f;
  };

  return (
    <Card>
      <CardTitle hint={findings.length > 0 ? `${findings.length} found` : undefined}>
        Findings
      </CardTitle>
      {findings.length === 0 ? (
        <p className="text-sm text-muted">
          Nothing yet — findings appear as the run observes behaviour or tests fail.
        </p>
      ) : (
          <ul className="flex flex-col gap-2">
          {findings.map((f) => (
            <li key={f.id}>
              <button
                onClick={() => setSelected(withEvidence(f))}
                className="flex w-full items-start gap-3 rounded-lg border border-line bg-surface p-3 text-left hover:bg-surface-2"
                aria-haspopup="dialog"
              >
                <span className="mt-0.5 shrink-0">
                  {f.proven ? (
                    <IconCheck className="text-success" />
                  ) : (
                    <IconTriangleAlert className="text-warning" />
                  )}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium">
                    <span className="font-mono text-xs text-muted">[{f.id}]</span> {f.title}
                  </span>
                  <span className="mt-1 flex flex-wrap items-center gap-2">
                    <Badge tone={SEVERITY_TONE[f.severity] ?? "neutral"}>{f.severity}</Badge>
                    <span className="text-xs text-muted">
                      confidence {f.confidence.toFixed(2)} · {f.proven ? "proven by execution" : "pattern match"}
                    </span>
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {selected ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Receipt for finding ${selected.id}`}
          className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col overflow-y-auto border-l border-line bg-surface p-5 shadow-xl"
        >
          <div className="flex items-start justify-between gap-3">
            <h3 className="text-base font-semibold">
              Receipt · <span className="font-mono text-sm">[{selected.id}]</span>
            </h3>
            <Button variant="ghost" onClick={() => setSelected(null)} aria-label="Close receipt" className="min-h-8 w-8 px-0">
              <IconX />
            </Button>
          </div>
          <p className="mt-2 text-sm">{selected.title}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge tone={SEVERITY_TONE[selected.severity] ?? "neutral"}>{selected.severity}</Badge>
            <Badge tone="neutral">{selected.category}</Badge>
            <Badge tone={selected.proven ? "success" : "warning"}>
              {selected.proven ? "proven" : "not proven"}
            </Badge>
          </div>
          <div className="mt-4 rounded-lg border border-line bg-surface-2 p-3 text-sm">
            <p className="font-medium">Why this confidence ({selected.confidence.toFixed(2)})</p>
            <p className="mt-1 text-muted">{explain(selected.confidence)}</p>
          </div>
          <h4 className="mt-4 text-sm font-semibold">Evidence</h4>
          {selected.evidence.length === 0 ? (
            <p className="mt-1 text-sm text-muted">
              Summary-level finding; the trace holds the step that raised it.
            </p>
          ) : (
            <ul className="mt-2 flex flex-col gap-3">
              {selected.evidence.map((ev, i) => (
                <li key={i} className="rounded-lg border border-line p-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted">
                    {ev.kind}
                    {ev.step_id ? ` · ${ev.step_id}` : ""}
                  </p>
                  {ev.command ? (
                    <p className="mt-1 break-all font-mono text-xs">
                      $ {ev.command}
                      {ev.exit_code !== null && ev.exit_code !== undefined
                        ? `  (exit ${ev.exit_code})`
                        : ""}
                    </p>
                  ) : null}
                  {ev.excerpt ? (
                    <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs text-muted">
                      {ev.excerpt}
                    </pre>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {selected.proven ? (
            <p className="mt-4 flex items-start gap-2 text-xs text-muted">
              <IconBan className="mt-0.5 shrink-0 text-danger" />
              Every claim here traces to a command and its output. Nothing in this receipt comes
              from the model&apos;s opinion.
            </p>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
