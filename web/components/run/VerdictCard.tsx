"use client";

import { Badge, Card } from "@/components/ui";
import { IconShieldCheck } from "@/components/Icons";
import { VERDICT_META } from "./RunHeader";
import type { Finding, Verdict } from "@/lib/types";

const CONFIDENCE_EXPLAIN: Array<[number, string]> = [
  [0.95, "reproduced: fails on the PR, passes on base"],
  [0.9, "observed by the sandbox (network, canary, filesystem)"],
  [0.85, "shown by one execution"],
  [0.6, "text pattern match — not proven by execution"],
];

function explainConfidence(confidence: number): string {
  for (const [min, text] of CONFIDENCE_EXPLAIN) {
    if (confidence >= min - 0.001) return text;
  }
  return "heuristic";
}

export function VerdictCard({
  verdict,
  findings,
  testsRan,
  generatedTests,
}: {
  verdict?: Verdict;
  findings: Finding[];
  testsRan: boolean;
  generatedTests: boolean;
}) {
  if (!verdict) {
    return (
      <Card>
        <h2 className="text-base font-semibold">Verdict</h2>
        <p className="mt-2 text-sm text-muted">The rules decide after every step completes…</p>
      </Card>
    );
  }
  const meta = VERDICT_META[verdict.label];
  const pct = Math.round(verdict.confidence * 100);
  return (
    <Card className={verdict.label === "suspicious" ? "border-danger-line" : ""}>
      <div className="flex flex-wrap items-center gap-3">
        <span
          className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-lg font-bold ${meta.tone === "success" ? "border-success-line bg-success-badge text-success-text" : ""} ${meta.tone === "warning" ? "border-warning-line bg-warning-badge text-warning-text" : ""} ${meta.tone === "danger" ? "border-danger-line bg-danger-badge text-danger-text" : ""} ${meta.tone === "info" ? "border-info-line bg-info-badge text-info-text" : ""}`}
        >
          {meta.icon}
          {meta.text}
        </span>
        <Badge tone={verdict.route === "auto" ? "info" : "warning"}>
          {verdict.route === "auto" ? "auto verdict" : "routed to a human"}
        </Badge>
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">Confidence</span>
          <span className="text-muted">{pct}% — {explainConfidence(verdict.confidence)}</span>
        </div>
        <div
          className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-surface-2"
          role="meter"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Verdict confidence ${pct}%`}
        >
          <div
            className={`h-full rounded-full transition-[width] duration-700 ease-out ${meta.tone === "danger" ? "bg-danger" : meta.tone === "warning" ? "bg-warning" : meta.tone === "success" ? "bg-success" : "bg-info"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {verdict.reasons.length > 0 ? (
        <div className="mt-4">
          <h3 className="text-sm font-semibold">Why this verdict</h3>
          <ul className="mt-1 list-inside list-disc text-sm text-muted">
            {verdict.reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {verdict.summary ? (
        <p className="mt-4 border-l-2 border-line-strong pl-3 text-sm">{verdict.summary}</p>
      ) : null}

      <div className="mt-4 border-t border-line pt-3 text-xs text-muted">
        <p className="flex items-center gap-1.5 font-medium">
          <IconShieldCheck width={14} height={14} className="text-success" />
          What we checked
        </p>
        <p className="mt-1">
          Tests ran on base and PR: {testsRan ? "yes" : "no"} · generated test written:{" "}
          {generatedTests ? "yes" : "no"} · behaviour watched: network, canary keys, filesystem
          writes, resource limits · findings: {findings.length}
        </p>
        <p className="mt-1">
          Not checked: private dependencies, malware that sleeps or detects sandboxes, languages
          beyond Python/Node.
        </p>
      </div>
    </Card>
  );
}
