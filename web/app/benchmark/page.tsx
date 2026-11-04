"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { BenchmarkCase, BenchmarkResult } from "@/lib/types";
import { Badge, Card, CardTitle, Spinner } from "@/components/ui";
import { IconCheck, IconSpinner, IconTriangleAlert } from "@/components/Icons";

export default function BenchmarkPage() {
  const router = useRouter();
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [cases, setCases] = useState<BenchmarkCase[]>([]);
  const [missing, setMissing] = useState(false);
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .benchmark()
      .then(setResult)
      .catch(() => setMissing(true));
    api
      .benchmarkCases()
      .then(setCases)
      .catch(() => setCases([]));
  }, []);

  const runLive = useCallback(
    async (name: string) => {
      setError(null);
      setStarting(name);
      try {
        const { id } = await api.benchmarkRun(name);
        router.push(`/runs/${id}`);
      } catch {
        setError(`Could not start "${name}" — try again in a moment.`);
        setStarting(null);
      }
    },
    [router],
  );

  if (missing && cases.length === 0) {
    return (
      <div className="py-16 text-center">
        <h1 className="text-xl font-semibold">No benchmark results yet</h1>
        <p className="mx-auto mt-2 max-w-xl text-sm text-muted">
          Run <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs">make bench</code>{" "}
          in <code className="rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs">airlock/</code>{" "}
          to execute the seeded cases and publish the table here.
        </p>
      </div>
    );
  }
  if (!result && cases.length === 0) {
    return (
      <div className="py-20 text-center">
        <Spinner label="Loading benchmark…" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Attack-library <span className="grad-text">benchmark</span>
          </h1>
          <p className="mt-1 text-sm text-muted">
            {cases.length || result?.rows.length} seeded cases, expected verdict vs what Airlock
            decided. Every case is openable as a real run — timeline, receipts, sandbox logs and
            token spend included.
          </p>
        </div>
        {result ? (
          <div className="flex items-center gap-2">
            {result.mode ? (
              <Badge tone={result.mode.startsWith("dummy") ? "warning" : "success"}>
                mode: {result.mode}
              </Badge>
            ) : null}
            <Badge
              tone={result.all_ok ? "success" : "danger"}
              icon={result.all_ok ? <IconCheck /> : <IconTriangleAlert />}
            >
              {result.all_ok ? "all verdicts match" : "mismatches present"}
            </Badge>
          </div>
        ) : null}
      </div>

      {error ? (
        <div role="alert" className="rounded-lg border border-danger-line bg-danger-badge px-4 py-3 text-sm text-danger-text">
          {error}
        </div>
      ) : null}

      {result ? (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead>
              <tr className="border-b border-line text-xs uppercase tracking-wide text-muted">
                <th className="px-3 py-2 font-medium">case</th>
                <th className="px-3 py-2 font-medium">expected</th>
                <th className="px-3 py-2 font-medium">got</th>
                <th className="px-3 py-2 font-medium">verdict</th>
                <th className="px-3 py-2 font-medium">findings</th>
                <th className="px-3 py-2 font-medium">tokens</th>
                <th className="px-3 py-2 font-medium">time</th>
                <th className="px-3 py-2 font-medium">open</th>
              </tr>
            </thead>
            <tbody>
              {result.rows.map((row) => (
                <tr key={row.name} className="border-b border-line last:border-0 hover:bg-surface-2">
                  <td className="px-3 py-2 font-medium">{row.name}</td>
                  <td className="px-3 py-2 font-mono text-xs text-muted">{row.expected}</td>
                  <td className="px-3 py-2 font-mono text-xs">{row.got}</td>
                  <td className="px-3 py-2">
                    <span className={row.verdict_ok ? "text-success" : "text-danger-text"}>
                      {row.verdict_ok ? "✓ match" : "✗ mismatch"}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span className={row.findings_ok ? "text-success" : "text-danger-text"}>
                      {row.findings_ok ? "✓" : "✗"} {row.findings.join(", ") || "—"}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-muted">
                    {row.tokens !== undefined ? (
                      <>
                        {row.tokens}
                        {row.llm_calls ? ` · ${row.llm_calls} calls` : ""}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-xs text-muted">
                    {row.duration_s}s
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <RunLiveButton
                      name={row.name}
                      starting={starting === row.name}
                      disabled={starting !== null}
                      onClick={() => runLive(row.name)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <Card>
        <CardTitle hint="one click → a real run you can open">
          Run any case live
        </CardTitle>
        <p className="mb-3 text-sm text-muted">
          Starts a fresh execution of that case against the running instance — you get the live
          timeline, sandbox logs, receipts and this run&apos;s exact token spend. Rate-limited
          like the demo buttons; costs credits when the backend runs on real models.
        </p>
        <div className="flex flex-wrap gap-2">
          {(cases.length > 0
            ? cases
            : (result?.rows ?? []).map((r) => ({ name: r.name, url: "", expected: r.expected }))
          ).map((c) => (
            <button
              key={c.name}
              onClick={() => runLive(c.name)}
              disabled={starting !== null}
              title={`expected: ${c.expected}`}
              className="inline-flex min-h-9 items-center gap-1.5 rounded-lg border border-line bg-surface-2 px-3 text-xs font-medium text-fg transition hover:border-line-strong disabled:opacity-60"
            >
              {starting === c.name ? (
                <IconSpinner width={13} height={13} className="text-info" />
              ) : null}
              {c.name}
            </button>
          ))}
        </div>
      </Card>

      <p className="text-xs text-muted">
        {result
          ? `Recorded ${new Date(result.generated_at).toLocaleString()}${
              result.mode ? ` · mode ${result.mode}` : ""
            }. ${
              result.mode?.startsWith("dummy")
                ? "Dummy-mode numbers prove the harness, not the product — the same cases run against real repos on the Vultr VM before any result is quoted publicly."
                : "Executed against the live backend — re-run after any model, policy or catalog change, and against real seeded repos before quoting results publicly."
            }`
          : "No recorded results yet — run any case above, or `make bench` to publish the full table."}
      </p>
    </div>
  );
}

function RunLiveButton({
  name,
  starting,
  disabled,
  onClick,
}: {
  name: string;
  starting: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      aria-label={`Run ${name} live`}
      className="inline-flex min-h-8 items-center gap-1.5 rounded-lg border border-line-strong px-2.5 py-1 text-xs font-semibold text-fg transition hover:bg-surface-2 disabled:opacity-60"
    >
      {starting ? <IconSpinner width={12} height={12} className="text-info" /> : null}
      Run live →
    </button>
  );
}
