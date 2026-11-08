"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, setKey } from "@/lib/api";
import type { RunOut } from "@/lib/types";
import { VERDICT_META } from "@/components/run/RunHeader";
import { Badge, Button, Card, CardTitle, Spinner } from "@/components/ui";

export default function ReviewPage() {
  const [runs, setRuns] = useState<RunOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [keyInput, setKeyInput] = useState("");
  const [note, setNote] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);
  const [needsKey, setNeedsKey] = useState(false);

  const [reloadTick, setReloadTick] = useState(0);
  const aliveRef = useRef(true);
  const load = useCallback(() => setReloadTick((t) => t + 1), []);

  useEffect(() => {
    aliveRef.current = true;
    let alive = true;
    api
      .listRuns()
      .then((r) => {
        if (!alive) return;
        setRuns(r);
        setNeedsKey(false);
      })
      .catch((e) => {
        if (!alive) return;
        if (e instanceof ApiError && e.status === 401) setNeedsKey(true);
        setError(e instanceof Error ? e.message : "could not load runs");
        setRuns([]);
      });
    return () => {
      alive = false;
    };
  }, [reloadTick]);

  // Poll every 5 s: suspicious verdicts land while you're watching — a one-shot load
  // showed an empty queue that only "came back" on manual reload.
  useEffect(() => {
    const id = window.setInterval(() => setReloadTick((t) => t + 1), 5000);
    return () => window.clearInterval(id);
  }, []);

  // Public data for the gate: how many demo runs are waiting (no key needed), and
  // whether this is a local demo instance (then the stable dev key is one click away).
  const [waitingPublic, setWaitingPublic] = useState(0);
  const [devInstance, setDevInstance] = useState(false);
  useEffect(() => {
    if (!needsKey) return;
    api
      .recentRuns()
      .then((r) => {
        if (aliveRef.current) {
          setWaitingPublic(
            r.filter((x) => x.status === "completed" && x.verdict === "suspicious").length,
          );
        }
      })
      .catch(() => undefined);
    api
      .readyz()
      .then((r) => {
        if (aliveRef.current) setDevInstance(r.llm === "dummy");
      })
      .catch(() => undefined);
  }, [needsKey, reloadTick]);

  async function decide(runId: string, decision: "approved" | "rejected") {
    setBusyId(runId);
    setError(null);
    try {
      await api.decide(runId, decision, note);
      setNote("");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "decision failed");
    } finally {
      setBusyId(null);
    }
  }

  const queue = (runs ?? []).filter(
    (r) => r.status === "completed" && r.verdict?.route === "human_review" && !r.human_decision,
  );
  const decided = (runs ?? []).filter((r) => r.human_decision);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Review queue</h1>
        <p className="mt-1 text-sm text-muted">
          Suspicious verdicts always wait for a person (maker-checker). Approve or reject with the
          evidence open — the decision is recorded on the run.
        </p>
      </div>

      {error && !needsKey ? (
        <div role="alert" className="rounded-lg border border-danger-line bg-danger-badge px-4 py-3 text-sm text-danger-text">
          {error}
        </div>
      ) : null}

      {needsKey ? (
        <Card>
          <CardTitle hint="kept in this browser only">Reviewer API key</CardTitle>
          {waitingPublic > 0 ? (
            <p className="mb-3 text-sm text-muted">
              <strong className="text-fg">{waitingPublic} runs are waiting</strong> for a human
              decision right now — unlock the queue below to review them.
            </p>
          ) : null}
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setKey(keyInput);
              setError(null);
              load();
            }}
          >
            <input
              id="reviewer-key"
              type="password"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              placeholder="paste a key with the runs:approve scope"
              className="min-h-10 flex-1 rounded-lg border border-line-strong bg-surface px-3 text-sm"
            />
            <Button type="submit">Unlock queue</Button>
          </form>
          {devInstance ? (
            <button
              onClick={async () => {
                await setKey("airlock-dev-admin-key");
                setError(null);
                load();
              }}
              className="mt-3 inline-flex min-h-9 items-center rounded-lg border border-line bg-surface-2 px-3 text-xs font-medium text-muted transition hover:text-fg"
            >
              Local dev instance — use the dev key
            </button>
          ) : null}
        </Card>
      ) : null}

      {runs === null && !needsKey ? (
        <Spinner label="Loading runs…" />
      ) : needsKey ? null : (
        <>
          <section aria-label="Waiting for review" className="flex flex-col gap-3">
            <h2 className="text-base font-semibold">Waiting for review ({queue.length})</h2>
            {queue.length === 0 ? (
              <p className="text-sm text-muted">
                Nothing is waiting for a human right now. Suspicious verdicts land here
                automatically — run the full attack library from the Dashboard to see the
                maker-checker flow end to end.
              </p>
            ) : (
              queue.map((r) => {
                const meta = r.verdict ? VERDICT_META[r.verdict.label] : null;
                return (
                  <Card key={r.id} className="border-danger-line">
                    <div className="flex flex-wrap items-center gap-3">
                      {meta ? (
                        <Badge tone={meta.tone} icon={meta.icon}>
                          {meta.text}
                        </Badge>
                      ) : null}
                      <a href={`/runs/${r.id}`} className="break-all text-sm font-medium text-primary underline">
                        {r.pr_url}
                      </a>
                      <span className="text-xs text-muted">
                        confidence {r.verdict ? Math.round(r.verdict.confidence * 100) : 0}%
                      </span>
                    </div>
                    {r.verdict?.summary ? (
                      <p className="mt-2 text-sm text-muted">{r.verdict.summary}</p>
                    ) : null}
                    <ul className="mt-2 list-inside list-disc text-xs text-muted">
                      {(r.verdict?.reasons ?? []).map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                    <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                      <input
                        value={busyId === r.id ? note : note}
                        onChange={(e) => setNote(e.target.value)}
                        placeholder="decision note (optional)"
                        aria-label={`Decision note for ${r.id}`}
                        className="min-h-10 flex-1 rounded-lg border border-line-strong bg-surface px-3 text-sm"
                      />
                      <Button onClick={() => decide(r.id, "approved")} disabled={busyId !== null}>
                        Approve
                      </Button>
                      <Button variant="danger" onClick={() => decide(r.id, "rejected")} disabled={busyId !== null}>
                        Reject
                      </Button>
                    </div>
                  </Card>
                );
              })
            )}
          </section>

          {decided.length > 0 ? (
            <section aria-label="Decided" className="flex flex-col gap-2">
              <h2 className="text-base font-semibold">Recently decided</h2>
              {decided.map((r) => (
                <p key={r.id} className="text-sm text-muted">
                  <Link href={`/runs/${r.id}`} className="font-mono text-xs text-primary underline">
                    {r.id}
                  </Link>{" "}
                  — {r.human_decision} by {r.decided_by}
                  {r.human_note ? ` · “${r.human_note}”` : ""}
                </p>
              ))}
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
