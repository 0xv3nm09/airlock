import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui";
import {
  IconArrowRight,
  IconCheck,
  IconFileBan,
  IconGlobe,
  IconKey,
  IconShieldAlert,
  IconShieldCheck,
} from "@/components/Icons";

export const metadata: Metadata = {
  title: "Use cases — Airlock",
};

type UseCase = {
  icon: ReactNode;
  tone: string;
  title: string;
  who: string;
  problem: string;
  checks: string[];
  status: "today" | "roadmap";
};

const CASES: UseCase[] = [
  {
    icon: <IconKey width={18} height={18} />,
    tone: "text-c-net",
    title: "Every push, reviewed in CI",
    who: "Dev teams with a CI pipeline",
    problem:
      "Green tests don't tell you a change started phoning home. Teams want the same sandboxed review on every push, not only when someone remembers to paste a link.",
    checks: [
      "Scoped team key (runs:write) — hashed, shown once, revocable",
      "One workflow step submits each push or PR to POST /v1/runs",
      "Network anomalies fail the review even when tests pass",
    ],
    status: "today",
  },
  {
    icon: <IconShieldCheck width={18} height={18} />,
    tone: "text-primary",
    title: "Fork PRs from strangers",
    who: "Open-source maintainers",
    problem:
      "A first-time contributor's PR looks fine and the tests are green. Running it locally or in CI with secrets is exactly how projects get compromised.",
    checks: [
      "Runs base and PR side by side in throwaway sandboxes",
      "Flags network anomalies, canary-key touches and denied writes",
      "Verdict with the command and output behind every claim",
    ],
    status: "today",
  },
  {
    icon: <IconFileBan width={18} height={18} />,
    tone: "text-c-write",
    title: "PRs written by AI agents",
    who: "Teams using coding agents",
    problem:
      "Agents open more PRs than people can read. A diff review can't tell you what the code does when it actually runs.",
    checks: [
      "Generated tests prove regressions instead of guessing",
      "Tests are kept only if they run — no hallucinated findings",
      "Rule table decides; the model only explains",
    ],
    status: "today",
  },
  {
    icon: <IconKey width={18} height={18} />,
    tone: "text-c-canary",
    title: "Dependency bumps & new packages",
    who: "Anyone merging lockfile changes",
    problem:
      "Install hooks run before any test. A typo-squatted or freshly published package can steal keys during pip or npm install.",
    checks: [
      "Pre-flight: known-malicious (OSV) and very young packages",
      "Install phase can reach package registries only",
      "Fake canary keys catch exfiltration red-handed",
    ],
    status: "today",
  },
  {
    icon: <IconShieldAlert width={18} height={18} />,
    tone: "text-danger",
    title: "Security triage with receipts",
    who: "Security & platform teams",
    problem:
      "When something looks off, you need evidence you can hand to someone else — not a chatbot's opinion.",
    checks: [
      "Full step-by-step trace for every run",
      "Suspicious verdicts always route to a human reviewer",
      "Approve / reject decisions are recorded with a note",
    ],
    status: "today",
  },
  {
    icon: <IconGlobe width={18} height={18} />,
    tone: "text-c-net",
    title: "GitHub App & private repos",
    who: "Organisations with internal code",
    problem:
      "Next after the event: a GitHub App that runs on every PR without a workflow file, covers private repositories, and posts the verdict back as a check.",
    checks: [
      "Same sandbox and rule table, triggered by the PR event",
      "Verdict and receipts posted back to the PR as a check",
      "Never runs with the repository's real secrets",
    ],
    status: "roadmap",
  },
  {
    icon: <IconFileBan width={18} height={18} />,
    tone: "text-c-write",
    title: "Vendor drops & copied code",
    who: "Teams importing third-party code",
    problem:
      "A wholesale code dump from a vendor or an open-source project is too big to read line by line — and it arrives with its own install scripts.",
    checks: [
      "The imported code actually runs, in a sandbox — not just the diff text",
      "Install hooks and network behaviour on the record",
      "Receipts cover exactly what was executed, not a summary's opinion",
    ],
    status: "today",
  },
  {
    icon: <IconShieldCheck width={18} height={18} />,
    tone: "text-info",
    title: "Agency & subcontractor work",
    who: "Agencies shipping client projects",
    problem:
      "Contractor PRs land on client repositories carrying your reputation — and nobody re-runs them safely before merge.",
    checks: [
      "Every subcontractor PR executed safely before it touches the client repo",
      "Network and secret behaviour on the record for the client",
      "Suspicious verdicts wait for your reviewer, with the full trace open",
    ],
    status: "today",
  },
  {
    icon: <IconKey width={18} height={18} />,
    tone: "text-primary",
    title: "Security training & workshops",
    who: "Educators & security communities",
    problem:
      "Teaching what malicious PRs actually look like needs live examples that are safe to run in a classroom.",
    checks: [
      "The 19-case seeded attack library ships with the product",
      "Every attack is contained — read-only root, no network, no real secrets",
      "Free to run offline: dummy mode needs no cloud account at all",
    ],
    status: "today",
  },
];

export default function UseCasesPage() {
  return (
    <div className="flex flex-col gap-10">
      <section className="relative overflow-hidden rounded-2xl border border-line bg-surface/40 py-10">
        <div className="aurora" aria-hidden />
        <div className="relative mx-auto max-w-2xl text-center">
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Where Airlock <span className="grad-text">earns its keep</span>
          </h1>
          <p className="mt-3 text-muted">
            Any time you&apos;re about to trust code you didn&apos;t write — one PR at a time, or
            on every push from CI with a scoped team key. Each use case runs the same pipeline:
            execute in a sandbox, watch, prove, decide.
          </p>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2">
        {CASES.map((c) => (
          <article
            key={c.title}
            className="lift card-shadow flex flex-col gap-4 rounded-2xl border border-line bg-surface p-6 hover:border-line-strong"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3">
                <span className={`icon-chip h-10 w-10 ${c.tone}`}>{c.icon}</span>
                <div>
                  <h2 className="text-base font-semibold">{c.title}</h2>
                  <p className="text-xs text-muted">{c.who}</p>
                </div>
              </div>
              {c.status === "today" ? (
                <Badge tone="success">Working in demo</Badge>
              ) : (
                <Badge tone="neutral">Roadmap</Badge>
              )}
            </div>
            <p className="text-sm text-muted">{c.problem}</p>
            <ul className="mt-auto flex flex-col gap-2 border-t border-line pt-4 text-sm">
              {c.checks.map((x) => (
                <li key={x} className="flex items-start gap-2">
                  <IconCheck width={15} height={15} className="mt-0.5 shrink-0 text-success" />
                  {x}
                </li>
              ))}
            </ul>
          </article>
        ))}

        <article className="card-shadow flex flex-col justify-center gap-3 rounded-2xl border border-dashed md:col-span-2 border-line-strong bg-surface-2/50 p-6">
          <h2 className="text-base font-semibold">See it on a real attack</h2>
          <p className="text-sm text-muted">
            The malicious demo PR passes every test — and still gets caught phoning home with a
            canary key.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/console"
              className="btn-grad inline-flex min-h-10 items-center gap-2 rounded-lg px-4 text-sm font-semibold"
            >
              Open the dashboard
              <IconArrowRight width={14} height={14} />
            </Link>
            <Link
              href="/about"
              className="inline-flex min-h-10 items-center rounded-lg border border-line-strong bg-surface px-4 text-sm font-semibold transition hover:bg-surface-2"
            >
              What we can&apos;t catch
            </Link>
          </div>
          <p className="text-xs text-muted">
            Want it on every push? Create a team key in Dashboard → Automate and add the
            workflow from <code className="font-mono">deploy/examples/</code>.
          </p>
        </article>
      </div>
    </div>
  );
}
