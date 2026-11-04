"use client";

import { useState } from "react";
import { Card, CardTitle } from "@/components/ui";

export function LogPane({ logs }: { logs: { base: string[]; pr: string[] } }) {
  const [tab, setTab] = useState<"base" | "pr">("pr");
  const lines = logs[tab];
  const visible = lines.slice(-40);
  return (
    <Card>
      <CardTitle hint="secrets are redacted; canaries show as [CANARY]">Sandbox logs</CardTitle>
      <div className="mb-3 flex gap-1" role="tablist" aria-label="Sandbox log side">
        {(["base", "pr"] as const).map((side) => (
          <button
            key={side}
            role="tab"
            aria-selected={tab === side}
            onClick={() => setTab(side)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
              tab === side ? "bg-surface-2 text-fg" : "text-muted hover:text-fg"
            }`}
          >
            {side === "base" ? "Base branch" : "PR head"}
          </button>
        ))}
      </div>
      <pre
        className="max-h-72 overflow-auto rounded-lg border border-line bg-surface-2 p-3 font-mono text-xs leading-5 text-muted"
        aria-live="polite"
      >
        {visible.length === 0 ? "no output yet" : visible.join("\n")}
      </pre>
    </Card>
  );
}
