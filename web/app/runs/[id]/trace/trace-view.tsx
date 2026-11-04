"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AirlockEvent } from "@/lib/types";
import { Spinner } from "@/components/ui";

function shortTs(ts: string): string {
  return new Date(ts).toLocaleTimeString();
}

function brief(e: AirlockEvent): string {
  const d = e.data ?? {};
  const parts: string[] = [];
  for (const key of ["ref", "step", "cmd", "exit_code", "duration_ms", "model", "tokens", "fallback", "detail", "id", "error"]) {
    if (d[key] !== undefined && d[key] !== null && d[key] !== "") {
      parts.push(`${key}=${String(d[key]).slice(0, 60)}`);
    }
  }
  return parts.join("  ");
}

export function TracePageClient() {
  const params = useParams<{ id: string }>();
  const runId = params.id;
  const [trace, setTrace] = useState<AirlockEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .trace(runId)
      .then(setTrace)
      .catch((e) => setError(e instanceof Error ? e.message : "could not load the trace"));
  }, [runId]);

  if (error) {
    return (
      <div className="py-20 text-center">
        <h1 className="text-xl font-semibold">Trace unavailable</h1>
        <p className="mt-2 text-sm text-muted">{error}</p>
      </div>
    );
  }
  if (!trace) {
    return (
      <div className="py-20 text-center">
        <Spinner label="Loading trace…" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-baseline justify-between">
        <h1 className="text-xl font-semibold">Trace inspector</h1>
        <Link href={`/runs/${runId}`} className="text-sm font-medium text-primary underline">
          ← Run view
        </Link>
      </div>
      <p className="text-sm text-muted">
        {trace.length} events · policy-stamped, replayable, ordered by seq. This is the full
        record behind the verdict — model calls, sandbox commands, containment events.
      </p>
      <div className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-line text-xs uppercase tracking-wide text-muted">
              <th className="px-3 py-2 font-medium">seq</th>
              <th className="px-3 py-2 font-medium">time</th>
              <th className="px-3 py-2 font-medium">type</th>
              <th className="px-3 py-2 font-medium">name</th>
              <th className="px-3 py-2 font-medium">data</th>
            </tr>
          </thead>
          <tbody>
            {trace.map((e, i) => (
              <tr key={`${e.seq}-${i}`} className="border-b border-line last:border-0 hover:bg-surface-2">
                <td className="px-3 py-2 font-mono text-xs text-muted">{e.seq}</td>
                <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-muted">{shortTs(e.ts)}</td>
                <td className="px-3 py-2 font-mono text-xs">{e.type}</td>
                <td className="whitespace-nowrap px-3 py-2 font-mono text-xs">{e.name}</td>
                <td className="max-w-md px-3 py-2 font-mono text-xs text-muted">
                  <span className="break-all">{brief(e) || (Object.keys(e.data ?? {}).length ? JSON.stringify(e.data).slice(0, 90) : "—")}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
