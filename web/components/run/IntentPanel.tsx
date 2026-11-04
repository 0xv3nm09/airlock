"use client";

import { Badge, Card, CardTitle } from "@/components/ui";
import { IconShieldAlert } from "@/components/Icons";
import type { Intent } from "@/lib/types";

export function IntentPanel({ intent }: { intent?: Intent }) {
  if (!intent) return null;
  const hot = intent.intent !== "benign" && intent.intent !== "unclear";
  return (
    <Card className={hot ? "border-danger-line" : ""}>
      <CardTitle hint="explains intent; never changes the verdict">Security analyst</CardTitle>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={hot ? "danger" : "info"} icon={<IconShieldAlert />}>
          intent: {intent.intent.replace("_", " ")}
        </Badge>
        <span className="text-xs text-muted">analyst confidence {intent.confidence.toFixed(2)}</span>
      </div>
      <p className="mt-3 text-sm">{intent.explanation}</p>
      {intent.cited_evidence.length > 0 ? (
        <p className="mt-2 text-xs text-muted">
          Cites: {intent.cited_evidence.map((id) => `[${id}]`).join(" ")}
        </p>
      ) : null}
    </Card>
  );
}
