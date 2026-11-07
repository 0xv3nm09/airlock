"use client";

/* Dashboard: live aggregates, verdict mix, containment feed and every run this browser may
 * see (demo runs for anyone, own runs with an API key). Replaces the old Console + Records
 * pages. Polls /v1/stats, /v1/runs/recent and /v1/runs every 5 seconds. */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError, type ApiKeyInfo, type LiveStats, type RecentRun } from "@/lib/api";
import { CountUp } from "@/components/motion";
import { Badge, Button, Card, CardTitle, Spinner } from "@/components/ui";
import { VERDICT_META } from "@/components/run/RunHeader";
import {
  IconArrowRight,
  IconFileBan,
  IconGauge,
  IconGlobe,
  IconKey,
  IconShieldAlert,
  IconShieldCheck,
  IconSpinner,
} from "@/components/Icons";

type Row = RecentRun & { is_own?: boolean };
type Filter = "all" | "suspicious" | "needs_changes" | "safe_to_merge" | "inconclusive" | "active";

const FEED_STYLE: Record<string, string> = {
  network_blocked: "text-c-net",
  canary_hit: "text-c-canary",
  write_denied: "text-c-write",
  limit_hit: "text-c-limit",
  preflight_stop: "text-danger-text",
};

const FEED_ICON: Record<string, React.ReactNode> = {
  network_blocked: <IconGlobe width={13} height={13} />,
  canary_hit: <IconKey width={13} height={13} />,
  write_denied: <IconFileBan width={13} height={13} />,
  limit_hit: <IconGauge width={13} height={13} />,
};

const FILTERS: Array<{ id: Filter; label: string }> = [
  { id: "all", label: "All" },
  { id: "suspicious", label: "Suspicious" },
  { id: "needs_changes", label: "Needs changes" },
  { id: "safe_to_merge", label: "Safe" },
  { id: "inconclusive", label: "Inconclusive" },
  { id: "active", label: "In progress" },
];

function repoOf(url: string): string {
  return url.split("/pull/")[0]?.split("/").slice(-2).join("/") ?? url;
}

function timeOf(ts: string): string {
  return new Date(ts).toLocaleTimeString();
}

function contained(r: Row): number {
  const c = r.counters;
  return c.network_blocked + c.canary_hits + c.writes_denied + c.limits_hit;
}

export default function DashboardPage() {
  const router = useRouter();
  const [stats, setStats] = useState<LiveStats | null>(null);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [needsKey, setNeedsKey] = useState(false);
  const [degraded, setDegraded] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    // A failed poll keeps the last good numbers on screen (only the indicator changes) —
    // blanking to zero on a transient hiccup read as "everything disappeared" (Oct 29 fix).
    api.stats()
      .then((s) => {
        setStats(s);
        setDegraded(false);
      })
      .catch(() => {
        // one retry — the first fetch can race a cold backend/proxy start
        window.setTimeout(() => {
          api
            .stats()
            .then((s) => {
              setStats(s);
              setDegraded(false);
            })
            .catch(() => setDegraded(true));
        }, 1500);
      });
    const demo = await api.recentRuns().catch(() => null);
    if (demo === null) {
      setDegraded(true);
      return; // keep the previous rows; the next poll retries
    }
    let own: Row[] = [];
    try {
      const listed = await api.listRuns();
      own = listed
        .filter((r) => !r.is_demo)
        .map((r) => ({
          id: r.id,
          pr_url: r.pr_url,
          status: r.status,
          verdict: r.verdict?.label ?? null,
          confidence: r.verdict?.confidence ?? null,
          counters: r.counters,
          usage: {
            prompt_tokens: r.usage.prompt_tokens,
            completion_tokens: r.usage.completion_tokens,
            llm_calls: r.usage.llm_calls,
          },
          created_at: r.created_at,
          containment: [],
          is_own: true,
        }));
      setNeedsKey(false);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setNeedsKey(true);
    }
    setRows([...own, ...demo].sort((a, b) => b.created_at.localeCompare(a.created_at)));
  }, []);

  useEffect(() => {
    // first load + 5 s polling; the callback only sets state after the awaits resolve
    const first = window.setTimeout(() => void refresh(), 0);
    const id = window.setInterval(() => void refresh(), 5000);
    return () => {
      window.clearTimeout(first);
      window.clearInterval(id);
    };
  }, [refresh]);

  async function startDemo(scenario: "clean" | "buggy" | "malicious") {
    setError(null);
    setBusy(scenario);
    try {
      const { id } = await api.demoRun(scenario);
      // full navigation, not router.push: the run screen must open even if the client
      // router hiccups — a stuck "Starting…" next to a running feed reads as broken
      window.location.assign(`/runs/${id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "could not start the run");
      setBusy(null);
    }
  }

  // Runs the whole 19-case library so the dashboard fills with real executions
  // (in-memory store resets on backend restart — this is the one-click refill).
  async function seedLibrary() {
    setError(null);
    setBusy("library");
    try {
      await api.seedLibrary();
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "could not start the library run");
    } finally {
      setBusy(null);
    }
  }

  const feed = useMemo(
    () =>
      (rows ?? [])
        .flatMap((r) => r.containment.map((c) => ({ ...c, run: r.id, repo: repoOf(r.pr_url) })))
        .sort((a, b) => b.ts.localeCompare(a.ts))
        .slice(0, 14),
    [rows],
  );

  const byType = useMemo(() => {
    const t = { network: 0, canary: 0, writes: 0, limits: 0 };
    for (const r of rows ?? []) {
      t.network += r.counters.network_blocked;
      t.canary += r.counters.canary_hits;
      t.writes += r.counters.writes_denied;
      t.limits += r.counters.limits_hit;
    }
    return [
      { label: "Network blocked", value: t.network, bar: "bg-c-net", text: "text-c-net", icon: <IconGlobe width={14} height={14} /> },
      { label: "Canary keys touched", value: t.canary, bar: "bg-c-canary", text: "text-c-canary", icon: <IconKey width={14} height={14} /> },
      { label: "Writes denied", value: t.writes, bar: "bg-c-write", text: "text-c-write", icon: <IconFileBan width={14} height={14} /> },
      { label: "Limits hit", value: t.limits, bar: "bg-c-limit", text: "text-c-limit", icon: <IconGauge width={14} height={14} /> },
    ];
  }, [rows]);

  const shown = (rows ?? []).filter((r) =>
    filter === "all"
      ? true
      : filter === "active"
        ? r.status === "queued" || r.status === "running"
        : r.verdict === filter,
  );

  const kpis = [
    {
      label: "Runs completed",
      value: stats?.runs_completed ?? 0,
      sub: stats ? `${stats.sandboxes_created} sandboxes created & destroyed` : "—",
      tone: "text-primary",
      icon: <IconShieldCheck width={16} height={16} />,
    },
    {
      label: "Attacks contained",
      value: stats?.attacks_contained ?? 0,
      sub: "blocked inside the sandbox",
      tone: "text-c-net",
      icon: <IconGlobe width={16} height={16} />,
    },
    {
      label: "Suspicious caught",
      value: stats?.suspicious ?? 0,
      sub: "sent to a human reviewer",
      tone: "text-danger",
      icon: <IconShieldAlert width={16} height={16} />,
    },
    {
      label: "Avg tokens / run",
      value: stats?.avg_tokens_per_run ?? 0,
      sub: stats ? `${stats.llm_calls_total} model calls in total` : "—",
      tone: "text-grad-c",
      icon: <IconGauge width={16} height={16} />,
    },
  ];

  const mix = stats
    ? [
        { key: "safe_to_merge", label: "Safe", value: stats.safe_to_merge, bar: "bg-success" },
        { key: "needs_changes", label: "Needs changes", value: stats.needs_changes, bar: "bg-warning" },
        { key: "suspicious", label: "Suspicious", value: stats.suspicious, bar: "bg-danger" },
        { key: "inconclusive", label: "Inconclusive", value: stats.inconclusive, bar: "bg-info" },
      ]
    : [];
  const mixTotal = mix.reduce((s, m) => s + m.value, 0);
  const typeMax = Math.max(1, ...byType.map((t) => t.value));

  return (
    <div className="flex flex-col gap-6">
      {/* ---- header ---- */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            <span className="grad-text">Dashboard</span>
          </h1>
          <p className="mt-1 text-sm text-muted">
            Live numbers from the instance serving this page — every figure comes from a real
            sandbox event. Refreshes every 5 s.
          </p>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            <strong className="text-fg">Integrations:</strong> link your Git provider and CI
            with a scoped API key (<button onClick={() => document.getElementById("automate-card")?.scrollIntoView({ behavior: "smooth" })} className="font-medium text-primary underline">Automate below</button>) —
            every push gets the same sandboxed review, network anomalies included. Private
            repos &amp; internal systems arrive with the GitHub App (post-event roadmap).
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {degraded ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-warning-line bg-warning-badge px-3 py-1 text-xs font-medium text-warning-text">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-warning" />
              reconnecting — showing last data
            </span>
          ) : null}
          <span className="mr-1 text-xs font-medium text-muted">New demo run</span>
          {(["clean", "buggy", "malicious"] as const).map((s) => (
            <Button
              key={s}
              variant={s === "malicious" ? "primary" : "ghost"}
              className="capitalize"
              disabled={busy !== null}
              onClick={() => startDemo(s)}
            >
              {busy === s ? "Starting…" : s}
            </Button>
          ))}
          <Button variant="ghost" disabled={busy !== null} onClick={() => seedLibrary()}>
            {busy === "library" ? "Queuing 19 runs…" : "Run demo library"}
          </Button>
        </div>
      </div>

      {error ? (
        <div
          role="alert"
          className="rounded-lg border border-danger-line bg-danger-badge px-4 py-3 text-sm text-danger-text"
        >
          {error}
        </div>
      ) : null}

      {!stats && !rows ? (
        <Spinner label="Reading the dashboard…" />
      ) : (
        <>
          {/* ---- KPIs ---- */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {kpis.map((k) => (
              <div
                key={k.label}
                className="lift card-shadow flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5 hover:border-line-strong"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-muted">{k.label}</span>
                  <span className={`icon-chip ${k.tone}`}>{k.icon}</span>
                </div>
                <div className="text-3xl font-bold tracking-tight tabular-nums">
                  <CountUp value={k.value} duration={600} />
                </div>
                <div className="text-xs text-muted">{k.sub}</div>
              </div>
            ))}
          </div>

          {/* ---- verdict mix + system ---- */}
          <div className="grid gap-4 lg:grid-cols-5">
            <Card className="lg:col-span-3">
              <CardTitle hint={stats ? `${mixTotal} verdicts` : undefined}>Verdict mix</CardTitle>
              {mixTotal === 0 ? (
                <p className="text-sm text-muted">
                  No verdicts yet — start a demo run above and this bar fills in.
                </p>
              ) : (
                <>
                  <div
                    className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full"
                    role="img"
                    aria-label={mix.map((m) => `${m.label} ${m.value}`).join(", ")}
                  >
                    {mix
                      .filter((m) => m.value > 0)
                      .map((m) => (
                        <div
                          key={m.key}
                          title={`${m.label}: ${m.value}`}
                          className={`bar-grow h-full first:rounded-l-full last:rounded-r-full ${m.bar}`}
                          style={{ width: `${(m.value / mixTotal) * 100}%` }}
                        />
                      ))}
                  </div>
                  <ul className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                    {mix.map((m) => {
                      const meta = VERDICT_META[m.key as keyof typeof VERDICT_META];
                      return (
                        <li key={m.key} className="flex flex-col gap-1">
                          <span className="flex items-center gap-1.5 text-xs text-muted">
                            <span className={`inline-block h-2 w-2 rounded-full ${m.bar}`} />
                            {m.label}
                          </span>
                          <span className="flex items-baseline gap-1.5">
                            <span className="text-xl font-bold tabular-nums">{m.value}</span>
                            <span className="text-xs text-muted">
                              {Math.round((m.value / mixTotal) * 100)}%
                            </span>
                            <span className="sr-only">{meta?.text}</span>
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
            </Card>

            <Card className="lg:col-span-2">
              <CardTitle
                hint={
                  stats
                    ? stats.uptime_s > 0
                      ? `up ${Math.floor(stats.uptime_s / 60)} min`
                      : "recorded snapshot"
                    : undefined
                }
              >
                System
              </CardTitle>
              {stats ? (
                <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  <div>
                    <dt className="text-xs text-muted">Model</dt>
                    <dd className="font-medium">{stats.llm}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Sandbox</dt>
                    <dd className="font-medium">{stats.sandbox}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Policy</dt>
                    <dd className="font-mono text-xs font-medium">{stats.policy_version}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-muted">Tokens used</dt>
                    <dd className="font-medium tabular-nums">{stats.tokens_total}</dd>
                  </div>
                </dl>
              ) : (
                <p className="text-sm text-muted">Backend unreachable — retrying every 5 s.</p>
              )}
            </Card>
          </div>

          {/* ---- containment ---- */}
          <div className="grid gap-4 lg:grid-cols-5">
            <Card className="lg:col-span-3">
              <CardTitle hint="newest first">Containment feed</CardTitle>
              {feed.length === 0 ? (
                <p className="flex min-h-20 items-center text-sm text-muted">
                  Quiet — no containment events yet. Run the malicious demo and this fills up.
                </p>
              ) : (
                <div className="flex max-h-80 min-h-20 flex-col gap-2 overflow-y-auto rounded-xl border border-line bg-surface-2 p-3 font-mono text-xs">
                  {feed.map((line, i) => (
                    <div key={`${line.run}-${i}`} className="console-line flex items-baseline gap-2">
                      <span className="shrink-0 text-muted">{timeOf(line.ts)}</span>
                      <span
                        className={`flex shrink-0 items-center gap-1 ${FEED_STYLE[line.name] ?? "text-muted"}`}
                      >
                        {FEED_ICON[line.name]}
                        {line.name}
                      </span>
                      <span
                        className="min-w-0 flex-1 truncate text-muted"
                        title={`${line.repo} — ${line.detail || "contained"}`}
                      >
                        {line.repo} — {line.detail || "contained"}
                      </span>
                      <Link href={`/runs/${line.run}`} className="shrink-0 text-primary underline">
                        {line.run.slice(4, 12)}
                      </Link>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <Card className="lg:col-span-2">
              <CardTitle hint="all visible runs">Contained by type</CardTitle>
              <ul className="flex flex-col gap-3">
                {byType.map((t) => (
                  <li key={t.label} title={`${t.label}: ${t.value}`}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="flex items-center gap-1.5">
                        <span className={t.text}>{t.icon}</span>
                        {t.label}
                      </span>
                      <span className="font-semibold tabular-nums">{t.value}</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-surface-2">
                      {t.value > 0 ? (
                        <div
                          className={`bar-grow h-full rounded-full ${t.bar}`}
                          style={{ width: `${(t.value / typeMax) * 100}%` }}
                        />
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          {/* ---- automate: team API keys + CI integration ---- */}
          {rows !== null && !needsKey ? <AutomateCard onKeysChanged={refresh} /> : null}

          {/* ---- all runs (was the Records page) ---- */}
          <Card className="p-0!">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
              <h2 className="text-base font-semibold">
                Runs{" "}
                <span className="ml-1 text-sm font-normal text-muted">
                  {shown.length} shown · {(rows ?? []).length} stored
                  {stats ? ` · ${stats.runs_total.toLocaleString("en-US")} lifetime` : ""}
                </span>
              </h2>
              <div className="flex flex-wrap gap-1" role="group" aria-label="Filter runs">
                {FILTERS.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setFilter(f.id)}
                    aria-pressed={filter === f.id}
                    className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                      filter === f.id
                        ? "border-primary bg-primary text-primary-fg"
                        : "border-line text-muted hover:border-line-strong hover:text-fg"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>
            {shown.length === 0 ? (
              <p className="px-5 py-6 text-sm text-muted">
                {(rows ?? []).length === 0
                  ? "No runs yet — use 'Run demo library' above to fill the dashboard with all 19 cases. Runs persist across restarts."
                  : "No runs match this filter."}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-line text-xs uppercase tracking-wide text-muted">
                      <th className="px-5 py-2.5 font-medium">Run</th>
                      <th className="px-3 py-2.5 font-medium">Pull request</th>
                      <th className="px-3 py-2.5 font-medium">Verdict</th>
                      <th className="px-3 py-2.5 font-medium">Contained</th>
                      <th className="px-3 py-2.5 font-medium">Tokens</th>
                      <th className="px-5 py-2.5 text-right font-medium">When</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((r) => {
                      const n = contained(r);
                      const meta = r.verdict
                        ? VERDICT_META[r.verdict as keyof typeof VERDICT_META]
                        : null;
                      return (
                        <tr
                          key={r.id}
                          onClick={() => router.push(`/runs/${r.id}`)}
                          className="cursor-pointer border-b border-line transition-colors last:border-0 hover:bg-surface-2"
                        >
                          <td className="px-5 py-3">
                            <Link
                              href={`/runs/${r.id}`}
                              className="font-mono text-xs text-primary underline"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {r.id.slice(4, 16)}
                            </Link>
                            {r.is_own ? (
                              <span className="ml-1.5 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-muted">
                                own
                              </span>
                            ) : null}
                          </td>
                          <td className="max-w-[220px] px-3 py-3">
                            <span className="block truncate text-muted" title={r.pr_url}>
                              {repoOf(r.pr_url)}
                            </span>
                          </td>
                          <td className="px-3 py-3">
                            {meta ? (
                              <Badge tone={meta.tone} icon={meta.icon}>
                                {meta.text.split(" — ")[0]}
                              </Badge>
                            ) : (
                              <Badge tone="neutral">
                                {r.status === "running" || r.status === "queued" ? (
                                  <IconSpinner width={12} height={12} className="animate-spin" />
                                ) : null}
                                {r.status}
                              </Badge>
                            )}
                          </td>
                          <td className="px-3 py-3">
                            {n > 0 ? (
                              <span
                                className="font-medium text-danger-text"
                                title={`net ${r.counters.network_blocked} · canary ${r.counters.canary_hits} · writes ${r.counters.writes_denied} · limits ${r.counters.limits_hit}`}
                              >
                                {n} blocked
                              </span>
                            ) : (
                              <span className="text-muted">—</span>
                            )}
                          </td>
                          <td className="px-3 py-3 font-mono text-xs text-muted tabular-nums">
                            {(r.usage.prompt_tokens + r.usage.completion_tokens).toLocaleString("en-US")}
                          </td>
                          <td className="whitespace-nowrap px-5 py-3 text-right text-xs text-muted">
                            {timeOf(r.created_at)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {needsKey ? (
            <p className="text-sm text-muted">
              Demo runs are public. To see your own runs here, paste your API key on the{" "}
              <Link href="/" className="text-primary underline">
                home page
              </Link>
              .
            </p>
          ) : null}

          <Link
            href="/benchmark"
            className="inline-flex w-fit items-center gap-1.5 text-sm font-semibold text-primary hover:underline"
          >
            See the 17-attack benchmark
            <IconArrowRight width={14} height={14} />
          </Link>
        </>
      )}
    </div>
  );
}

/* ---- Automate card: team API keys + CI integration (Oct 29) ---- */
function AutomateCard({ onKeysChanged }: { onKeysChanged: () => void }) {
  const [keys, setKeys] = useState<ApiKeyInfo[] | null>(null);
  const [owner, setOwner] = useState("");
  const [freshKey, setFreshKey] = useState<string | null>(null);
  const [startingKey, setStartingKey] = useState(false);
  const [copied, setCopied] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const loadKeys = useCallback(() => {
    api
      .adminKeys()
      .then(setKeys)
      .catch(() => setKeys([]));
  }, []);

  useEffect(loadKeys, [loadKeys]);

  async function create() {
    setErr(null);
    setStartingKey(true);
    try {
      const created = await api.createKey(owner.trim() || "team");
      setFreshKey(created.key);
      setOwner("");
      loadKeys();
      onKeysChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "could not create the key");
    } finally {
      setStartingKey(false);
    }
  }

  async function revoke(keyId: string) {
    await api.revokeKey(keyId).catch(() => undefined);
    loadKeys();
  }

  async function copyKey() {
    if (freshKey) {
      await navigator.clipboard.writeText(freshKey).catch(() => undefined);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    }
  }

  return (
    <Card id="automate-card">
      <CardTitle hint="keys are hashed server-side; the secret is shown once">
        Automate Airlock
      </CardTitle>
      <p className="mb-4 text-sm text-muted">
        Give your team or CI a scoped key and every push gets a real review — verdict,
        network-anomaly findings and receipts, without installing anything.
      </p>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-3">
          <div className="flex gap-2">
            <input
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              placeholder="owner name (e.g. team-alpha)"
              aria-label="Key owner"
              className="min-h-10 flex-1 rounded-lg border border-line-strong bg-surface px-3 text-sm"
            />
            <Button onClick={create} disabled={startingKey}>
              Create key
            </Button>
          </div>
          {freshKey ? (
            <div className="rounded-lg border border-success-line bg-success-badge p-3">
              <p className="text-xs font-medium text-success-text">
                Copy it now — this is the only time the full key is shown.
              </p>
              <div className="mt-2 flex items-center gap-2">
                <code className="min-w-0 flex-1 truncate rounded bg-surface px-2 py-1 font-mono text-xs text-fg">
                  {freshKey}
                </code>
                <Button variant="ghost" className="min-h-8 px-3 py-1 text-xs" onClick={copyKey}>
                  {copied ? "Copied ✓" : "Copy"}
                </Button>
              </div>
            </div>
          ) : null}
          {err ? <p className="text-xs text-danger-text">{err}</p> : null}

          <pre className="overflow-x-auto rounded-lg border border-line bg-surface-2 p-3 font-mono text-xs leading-5 text-muted">
{`curl -X POST https://your-host/v1/runs \\
  -H "X-API-Key: ak_…" \\
  -H "Content-Type: application/json" \\
  -d '{"pr_url": "https://github.com/o/r/pull/7"}'`}
          </pre>
          <p className="text-xs text-muted">
            For auto-run on every push, add the workflow from{" "}
            <code className="font-mono">deploy/examples/</code> in the repo — or wire a GitHub
            App post-event (roadmap).
          </p>
        </div>

        <div>
          {keys === null ? (
            <Spinner label="Loading keys…" />
          ) : keys.length === 0 ? (
            <p className="text-sm text-muted">No keys yet — create the first one.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {keys.map((k) => (
                <li
                  key={k.key_id}
                  className="flex items-center justify-between gap-2 rounded-lg border border-line bg-surface p-2.5 text-sm"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{k.owner_id}</span>
                    <span className="font-mono text-xs text-muted">{k.key_id}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    <Badge tone="neutral">{k.scopes.join(", ")}</Badge>
                    {k.revoked ? (
                      <Badge tone="danger">revoked</Badge>
                    ) : (
                      <Button variant="danger" className="min-h-8 px-3 py-1 text-xs" onClick={() => revoke(k.key_id)}>
                        Revoke
                      </Button>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-2 text-xs text-muted">
            Keys live in this instance&apos;s memory (SQL persistence is T08). Team keys never
            see another owner&apos;s runs, and real cloud credentials never enter a sandbox —
            only planted canaries do.
          </p>
        </div>
      </div>
    </Card>
  );
}
