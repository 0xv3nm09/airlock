"use client";

import { Badge, Spinner } from "@/components/ui";
import { IconBan, IconCheck, IconCircleHelp, IconShieldAlert, IconTriangleAlert } from "@/components/Icons";
import type { RunStatus, VerdictLabel } from "@/lib/types";

export const VERDICT_META: Record<
  VerdictLabel,
  { tone: "success" | "warning" | "danger" | "info"; icon: React.ReactNode; text: string }
> = {
  safe_to_merge: { tone: "success", icon: <IconCheck />, text: "Safe to merge" },
  needs_changes: { tone: "warning", icon: <IconTriangleAlert />, text: "Needs changes" },
  suspicious: { tone: "danger", icon: <IconShieldAlert />, text: "Suspicious — human review" },
  inconclusive: { tone: "info", icon: <IconCircleHelp />, text: "Inconclusive" },
};

export const SEVERITY_TONE: Record<string, "success" | "warning" | "danger" | "info" | "neutral"> = {
  critical: "danger",
  high: "danger",
  medium: "warning",
  low: "info",
  info: "neutral",
};

export function StatusBadge({ status }: { status: string }) {
  if (status === "connecting" || status === "running" || status === "queued") {
    return (
      <span className="inline-flex items-center gap-2">
        <span className="live-dot inline-block h-2 w-2 rounded-full bg-info" aria-hidden />
        <Spinner label={status === "connecting" ? "connecting…" : status} />
      </span>
    );
  }
  if (status === "completed") {
    return (
      <Badge tone="success" icon={<IconCheck />}>
        completed
      </Badge>
    );
  }
  if (status === "failed") {
    return (
      <Badge tone="danger" icon={<IconBan />}>
        failed
      </Badge>
    );
  }
  return (
    <Badge tone="neutral" icon={<IconCircleHelp />}>
      {status}
    </Badge>
  );
}

export function RunHeader({
  prUrl,
  policyVersion,
  status,
  runId,
  usage,
}: {
  prUrl: string;
  policyVersion: string;
  status: RunStatus | "connecting";
  runId: string;
  usage?: { prompt_tokens: number; completion_tokens: number; llm_calls: number };
}) {
  return (
    <div className="flex flex-col gap-2 border-b border-line pb-4">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge status={status} />
        <a
          href={prUrl}
          target="_blank"
          rel="noreferrer"
          className="text-sm font-medium text-primary underline"
        >
          {prUrl}
        </a>
      </div>
      <p className="text-sm text-muted">
        run <code className="font-mono text-xs">{runId}</code> · policy{" "}
        <code className="font-mono text-xs">{policyVersion}</code>
        {usage ? ` · ${usage.llm_calls} model calls · ${usage.prompt_tokens + usage.completion_tokens} tokens` : ""}
      </p>
    </div>
  );
}
