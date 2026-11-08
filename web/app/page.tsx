"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiError, getKey, setKey } from "@/lib/api";
import {
  IconArrowRight,
  IconCheck,
  IconFileBan,
  IconGauge,
  IconGlobe,
  IconKey,
  IconShieldAlert,
  IconShieldCheck,
  IconTriangleAlert,
} from "@/components/Icons";
import { Button, Card, CardTitle } from "@/components/ui";
import { Reveal } from "@/components/motion";

/* Hero coverage chips — the concrete answer to "what are we covering?". */
const COVERAGE = [
  { icon: <IconGlobe width={13} height={13} />, tone: "text-c-net", label: "network egress" },
  { icon: <IconKey width={13} height={13} />, tone: "text-c-canary", label: "canary secrets" },
  { icon: <IconFileBan width={13} height={13} />, tone: "text-c-write", label: "file writes" },
  { icon: <IconGauge width={13} height={13} />, tone: "text-c-limit", label: "resource limits" },
  { icon: <IconShieldAlert width={13} height={13} />, tone: "text-danger", label: "prompt injection" },
  { icon: <IconCheck width={13} height={13} />, tone: "text-success", label: "known-malware deps" },
];
import {
  AutomateBand,
  ComparisonTable,
  ContainmentBento,
  LiveValueCard,
  PipelineFlow,
  SampleVerdict,
  StatBand,
} from "@/components/landing/sections";

const DEMOS = [
  {
    scenario: "clean" as const,
    title: "Clean PR",
    blurb: "Small feature with passing tests.",
    outcome: "safe to merge",
    tone: "border-success-line! hover:border-success!",
  },
  {
    scenario: "buggy" as const,
    title: "Buggy PR",
    blurb: "Tests pass on main, fail on the PR.",
    outcome: "needs changes, proven",
    tone: "border-warning-line! hover:border-warning!",
  },
  {
    scenario: "malicious" as const,
    title: "Malicious PR",
    blurb: "All tests pass — but it phones home and steals a canary key.",
    outcome: "suspicious → a human",
    tone: "border-danger-line! hover:border-danger!",
  },
];

export default function Landing() {
  const router = useRouter();
  const [prUrl, setPrUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [keySaved, setKeySaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function startDemo(scenario: "clean" | "buggy" | "malicious") {
    setError(null);
    setBusy(scenario);
    try {
      const { id } = await api.demoRun(scenario);
      router.push(`/runs/${id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "could not start the run");
      setBusy(null);
    }
  }

  async function runOwnPr(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy("own");
    try {
      const { id } = await api.createRun(prUrl);
      router.push(`/runs/${id}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("This needs an API key — paste one below, or run one of the sample PRs.");
      } else if (err instanceof ApiError && err.code === "invalid_pr_url") {
        setError("That doesn't look like a GitHub PR URL (https://github.com/<owner>/<repo>/pull/<n>).");
      } else {
        setError(err instanceof ApiError ? err.message : "could not start the run");
      }
      setBusy(null);
    }
  }

  async function saveKey(e: React.FormEvent) {
    e.preventDefault();
    await setKey(apiKey);
    setKeySaved(Boolean(getKey()));
  }

  return (
    <div className="flex flex-col gap-14">
      {/* ---- hero ---- */}
      <section className="relative -mt-2 overflow-hidden rounded-2xl border border-line bg-surface/40 py-12">
        <div className="aurora" aria-hidden />
        <div className="dot-grid" aria-hidden />
        <div className="relative mx-auto max-w-3xl text-center">
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-muted">
              <span className="live-dot inline-block h-1.5 w-1.5 rounded-full bg-success" />
              Vultr Agent Rush · Challenge 01 · Blast Radius Zero
            </span>
          </Reveal>
          <Reveal delay={80}>
            <h1 className="mt-5 text-4xl font-bold tracking-tight text-balance sm:text-6xl">
              Run the PR <span className="grad-text">before</span> you trust it.
            </h1>
          </Reveal>
          <Reveal delay={160}>
            <p className="mt-4 text-lg text-muted">
              AI reviewers read the diff and guess.{" "}
              <strong className="text-fg">Airlock executes</strong> a stranger&apos;s pull request
              inside a throwaway sandbox,{" "}
              <strong className="text-fg">watches what it actually does</strong>, and reports only
              what it <strong className="text-fg">proved</strong> — with the command and output
              behind every claim.{" "}
              <strong className="text-fg">What we watch:</strong> the network it tries to reach,
              the secrets it touches, the files it writes, and the resources it burns.
            </p>
          </Reveal>
          <Reveal delay={220}>
            <ul
              aria-label="What Airlock covers"
              className="mt-5 flex flex-wrap items-center justify-center gap-2"
            >
              {COVERAGE.map((c) => (
                <li
                  key={c.label}
                  className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-fg"
                >
                  <span className={c.tone}>{c.icon}</span>
                  {c.label}
                </li>
              ))}
            </ul>
          </Reveal>
          <Reveal delay={280}>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              <Button onClick={() => startDemo("malicious")} disabled={busy !== null}>
                Catch the malicious PR live
                <IconArrowRight width={14} height={14} />
              </Button>
              <Link
                href="/benchmark"
                className="inline-flex min-h-10 items-center rounded-lg border border-line-strong bg-surface px-4 text-sm font-semibold transition hover:bg-surface-2"
              >
                See the numbers first
              </Link>
            </div>
          </Reveal>
          <Reveal delay={340}>
            <p className="mx-auto mt-6 max-w-2xl text-base text-muted">
              <strong className="text-fg">Connect your team and your clouds.</strong> Link
              GitHub, GitLab or any CI with a scoped API key — every push from your team gets the
              same sandboxed review, network anomalies flagged.{" "}
              <strong className="text-fg">Private repos and internal systems</strong> arrive next
              with the GitHub App —{" "}
              <Link href="/console" className="font-medium text-primary underline">
                Dashboard → Automate
              </Link>
            </p>
          </Reveal>
        </div>
      </section>

      {error ? (
        <div
          role="alert"
          className="mx-auto max-w-3xl rounded-lg border border-danger-line bg-danger-badge px-4 py-3 text-sm text-danger-text"
        >
          {error}
        </div>
      ) : null}

      {/* ---- demo PRs (directly under the hero: try it first) ---- */}
      <section aria-label="Sample PRs">
        <Reveal>
          <h2 className="mb-2 text-center text-2xl font-bold tracking-tight">Try it in 60 seconds</h2>
          <p className="mx-auto mb-8 max-w-xl text-center text-sm text-muted">
            No login, no setup. Each seeded PR is a small repo we control — the outcome chip shows
            what the rule table should decide.
          </p>
        </Reveal>
        <div className="grid gap-4 sm:grid-cols-3">
          {DEMOS.map((d, i) => (
            <Reveal key={d.scenario} delay={i * 80}>
              <Card className={`lift flex h-full flex-col gap-3 ${d.tone}`}>
                <h3 className="text-base font-semibold">{d.title}</h3>
                <p className="flex-1 text-sm text-muted">{d.blurb}</p>
                <span className="inline-flex w-fit items-center gap-1.5 rounded-full border border-line bg-surface-2 px-2.5 py-1 text-xs font-medium text-muted">
                  <IconTriangleAlert width={12} height={12} />
                  expect: {d.outcome}
                </span>
                <Button onClick={() => startDemo(d.scenario)} disabled={busy !== null}>
                  {busy === d.scenario ? "Starting…" : "Run it live"}
                  <IconArrowRight width={14} height={14} />
                </Button>
              </Card>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ---- proof band: numbers + a real recorded verdict ---- */}
      <section aria-label="Proof" className="flex flex-col gap-6">
        <div className="grid items-stretch gap-6 lg:grid-cols-5">
          <div className="flex flex-col lg:col-span-3">
            <SampleVerdict />
          </div>
          <div className="flex flex-col gap-4 lg:col-span-2">
            <LiveValueCard />
            <StatBand />
          </div>
        </div>
      </section>

      <PipelineFlow />

      <ComparisonTable />

      <AutomateBand />

      {/* ---- containment ---- */}
      <section aria-label="How containment works">
        <Reveal>
          <h2 className="mb-2 text-center text-2xl font-bold tracking-tight">Containment first</h2>
          <p className="mx-auto mb-8 max-w-2xl text-center text-sm text-muted">
            An agent that only chats is a demo; an agent that executes safely is a product.
          </p>
        </Reveal>
        <ContainmentBento />
      </section>

      {/* ---- own PR ---- */}
      <Reveal>
        <Card className="mx-auto w-full max-w-3xl">
          <CardTitle hint="public Python & Node PRs · or automate it in CI">Review your own pull request</CardTitle>
          <form onSubmit={runOwnPr} className="flex flex-col gap-3 sm:flex-row">
            <input
              type="url"
              required
              value={prUrl}
              onChange={(e) => setPrUrl(e.target.value)}
              placeholder="https://github.com/<owner>/<repo>/pull/<number>"
              aria-label="Pull request URL"
              className="min-h-10 flex-1 rounded-lg border border-line-strong bg-surface px-3 text-sm outline-none placeholder:text-muted"
            />
            <Button type="submit" disabled={busy !== null || prUrl.length === 0}>
              {busy === "own" ? "Queuing…" : "Run in Airlock"}
            </Button>
          </form>
          <form onSubmit={saveKey} className="mt-3 flex items-center gap-2 text-sm text-muted">
            <IconKey width={14} height={14} />
            <label htmlFor="apikey">API key</label>
            <input
              id="apikey"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="paste key (stays in this browser)"
              className="min-h-8 flex-1 rounded-md border border-line bg-surface-2 px-2 text-sm outline-none"
            />
            <Button variant="ghost" type="submit" className="min-h-8 px-3 py-1">
              {keySaved ? "Saved ✓" : "Save"}
            </Button>
          </form>
        </Card>
      </Reveal>

      {/* ---- honesty strip ---- */}
      <Reveal>
        <section className="mx-auto flex max-w-3xl items-start gap-3 rounded-2xl border border-info-line bg-info-badge p-4 text-sm text-info-text">
          <IconShieldCheck className="mt-0.5 shrink-0" />
          <p>
            <strong>Nothing trusted, nothing kept.</strong> PR code never touches the app or the
            host; sandboxes hold no real secrets and are destroyed after every run. Suspicious
            verdicts always go to a human — the model explains, the rules decide. We also publish
            what we <em>can&apos;t</em> catch:{" "}
            <Link href="/about" className="underline">
              sleeping malware, encrypted egress, non-Python/Node stacks
            </Link>
            .
          </p>
        </section>
      </Reveal>
    </div>
  );
}
