"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RunOut } from "@/lib/types";
import { useRunEvents } from "@/lib/useRunEvents";
import { ContainmentCounters } from "@/components/run/ContainmentCounters";
import { FindingsPanel } from "@/components/run/FindingsPanel";
import { IntentPanel } from "@/components/run/IntentPanel";
import { LogPane } from "@/components/run/LogPane";
import { RunHeader } from "@/components/run/RunHeader";
import { Timeline } from "@/components/run/Timeline";
import { VerdictCard } from "@/components/run/VerdictCard";
import { Spinner } from "@/components/ui";
import type { Verdict } from "@/lib/types";

/* The live verdict event used to arrive with empty summary/reasons and override the full
 * meta verdict; now the event carries them, and meta fills any gap as a fallback. */
function mergeVerdict(live?: Verdict, meta?: Verdict): Verdict | undefined {
  if (!live) return meta;
  if (!meta) return live;
  return {
    ...meta,
    ...live,
    summary: live.summary || meta.summary,
    reasons: live.reasons.length ? live.reasons : meta.reasons,
    cited_findings: live.cited_findings.length ? live.cited_findings : meta.cited_findings,
  };
}

export function RunPageClient() {
  const params = useParams<{ id: string }>();
  const runId = params.id;
  const view = useRunEvents(runId);
  const [meta, setMeta] = useState<RunOut | null>(null);

  // Header metadata (pr_url, policy, usage). Re-fetch once the run completes so a human
  // decision made on the review page shows up here too.
  useEffect(() => {
    let alive = true;
    api
      .getRun(runId)
      .then((r) => alive && setMeta(r))
      .catch(() => alive && setMeta(null));
    return () => {
      alive = false;
    };
  }, [runId, view.status]);

  const testsRan = view.spans.some(
    (s) => s.name === "sandbox.exec" && s.data.step === "tests" && s.state !== "running",
  );
  const generatedTests = view.spans.some((s) => s.name === "agent.test_writer");

  if (view.status === "connecting" && !meta) {
    return (
      <div className="py-20 text-center">
        <Spinner label="Loading run…" />
      </div>
    );
  }

  if (!meta && view.trace.length === 0) {
    return (
      <div className="py-20 text-center">
        <h1 className="text-xl font-semibold">Run not found</h1>
        <p className="mt-2 text-sm text-muted">
          Demo runs stay available; other runs are only visible to their owner.
        </p>
        <Link href="/" className="mt-4 inline-block text-sm font-medium text-primary underline">
          ← Back to Airlock
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <RunHeader
        runId={runId}
        prUrl={meta?.pr_url ?? ""}
        policyVersion={meta?.policy_version ?? "…"}
        status={view.status}
        usage={meta?.usage}
      />

      {view.status === "failed" ? (
        <div role="alert" className="rounded-lg border border-danger-line bg-danger-badge px-4 py-3 text-sm text-danger-text">
          The run failed. {view.error ?? ""} Nothing was left behind — sandboxes are destroyed on
          every path.
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-6">
          <Timeline spans={view.spans} />
          <ContainmentCounters counters={view.counters} />
          <LogPane logs={view.logs} />
        </div>
        <div className="flex flex-col gap-6">
          <VerdictCard
            verdict={mergeVerdict(view.verdict, meta?.verdict ?? undefined)}
            findings={view.findings}
            testsRan={testsRan}
            generatedTests={generatedTests}
          />
          <FindingsPanel findings={view.findings} enriched={meta?.findings ?? []} />
          <IntentPanel intent={view.intent ?? meta?.intent ?? undefined} />
          {meta?.human_decision ? (
            <div className="rounded-xl border border-line bg-surface p-5 text-sm">
              <p className="font-semibold">Human decision</p>
              <p className="mt-1 text-muted">
                {meta.human_decision} by {meta.decided_by}
                {meta.human_note ? ` — “${meta.human_note}”` : ""}
              </p>
            </div>
          ) : null}
        </div>
      </div>

      <p className="text-center text-sm text-muted">
        Want the raw story?{" "}
        <Link href={`/runs/${runId}/trace`} className="font-medium text-primary underline">
          Open the trace inspector
        </Link>{" "}
        — every span, model call and event, in order.
      </p>
    </div>
  );
}
