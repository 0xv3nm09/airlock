import type { Metadata } from "next";
import { Card } from "@/components/ui";

export const metadata: Metadata = {
  title: "About Airlock — model card",
};

export default function AboutPage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">About Airlock</h1>
        <p className="mt-1 text-sm text-muted">
          The honest version: what it is for, what it can and cannot tell you, and what happens
          to the data.
        </p>
      </div>

      <Card>
        <h2 className="text-base font-semibold">Intended use</h2>
        <p className="mt-2 text-sm text-muted">
          Airlock reviews public GitHub pull requests by executing them in an isolated sandbox and
          reporting observed behaviour with receipts. It helps maintainers and small teams decide
          whether to trust a stranger&apos;s PR. Teams can also run it on every push from CI with
          a scoped API key, so network anomalies are caught even when tests pass. It is a decision
          aid: a human decides, Airlock proves.
        </p>
      </Card>

      <Card>
        <h2 className="text-base font-semibold">What a verdict means</h2>
        <ul className="mt-2 flex list-disc flex-col gap-1 pl-5 text-sm text-muted">
          <li>
            <strong>Safe to merge</strong> — tests ran and passed on base and PR, and the sandbox
            observed no dangerous behaviour. Capped at 0.82 confidence by design.
          </li>
          <li>
            <strong>Needs changes</strong> — a proven regression or bug (reproduced on PR, clean on
            base).
          </li>
          <li>
            <strong>Suspicious</strong> — dangerous behaviour observed (network escape, canary key
            access, denied write) or a known-malicious dependency. Always routed to a human.
          </li>
          <li>
            <strong>Inconclusive</strong> — tests could not run. No pretend confidence.
          </li>
        </ul>
      </Card>

      <Card>
        <h2 className="text-base font-semibold">What we do not check</h2>
        <ul className="mt-2 flex list-disc flex-col gap-1 pl-5 text-sm text-muted">
          <li>Malware that sleeps past the run window or detects sandbox environments.</li>
          <li>Encrypted exfiltration over allowed hosts during the install phase.</li>
          <li>Private repositories, non-Python/Node stacks, and browser-side behaviour.</li>
          <li>Prompt-injection patterns are text heuristics — flagged, never proven.</li>
        </ul>
      </Card>

      <Card>
        <h2 className="text-base font-semibold">The stack</h2>
        <dl className="mt-2 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="font-medium">Backend</dt>
            <dd className="text-muted">
              FastAPI (async) · Pydantic contracts · in-process queue · SQLite write-through
              store (Postgres-ready)
            </dd>
          </div>
          <div>
            <dt className="font-medium">Agents</dt>
            <dd className="text-muted">
              5 small agents (Planner, Fixer, Test-writer, Analyst, Reporter) in a code-owned
              orchestrator; Vultr Serverless Inference in prod, offline dummy adapter in demo
            </dd>
          </div>
          <div>
            <dt className="font-medium">Sandbox</dt>
            <dd className="text-muted">
              Docker + gVisor (runsc) containers: read-only root, dropped caps, two-phase
              network (registry-only install, none for tests), per-run venv, hard caps
            </dd>
          </div>
          <div>
            <dt className="font-medium">Frontend</dt>
            <dd className="text-muted">
              Next.js 16 + React 19 + Tailwind 4 · live SSE timeline · WCAG 2.2-verified
              theming
            </dd>
          </div>
          <div>
            <dt className="font-medium">Ops</dt>
            <dd className="text-muted">
              Caddy HTTPS · Squid registry-only egress proxy · GitHub Actions CI · deploy
              assets in <code className="font-mono text-xs">deploy/</code>
            </dd>
          </div>
          <div>
            <dt className="font-medium">Everything swaps</dt>
            <dd className="text-muted">
              LLM provider, sandbox backend, queue and storage are env-driven adapters — the
              demo runs fully offline, the VM entry runs 100% on Vultr
            </dd>
          </div>
        </dl>
      </Card>

      <Card>
        <h2 className="text-base font-semibold">Data handling</h2>
        <p className="mt-2 text-sm text-muted">
          Only public PR data is fetched. Sandbox logs are redacted (secret-shaped strings are
          masked; planted canaries show as [CANARY]). Runs, findings, event traces and API keys
          persist in a local SQLite file on the instance (
          <code className="font-mono text-xs">AIRLOCK_DB_PATH</code>) — nothing leaves the
          machine, and model prompts are never stored, only per-call token counts. Planned for
          the product: a prompt-hash audit trail and 30-day retention with deletion. No
          fairness decisions about people are made by this system.
        </p>
      </Card>

      <Card>
        <h2 className="text-base font-semibold">Who decides</h2>
        <p className="mt-2 text-sm text-muted">
          The verdict comes from a versioned rule table, never from the model. The model plans,
          repairs setup, writes tests, and explains — every one of its outputs is checked against
          execution evidence. &ldquo;Suspicious&rdquo; always waits for a human with the full
          trace open.
        </p>
      </Card>
    </div>
  );
}
