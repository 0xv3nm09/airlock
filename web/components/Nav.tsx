"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
import { DEMO } from "@/lib/demo";
import { IconShieldCheck } from "./Icons";
import { ThemeToggle } from "./ThemeToggle";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/console", label: "Dashboard" },
  { href: "/use-cases", label: "Use cases" },
  { href: "/benchmark", label: "Benchmark" },
  { href: "/review", label: "Review" },
  { href: "/about", label: "About" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  // run detail pages live under /runs/* — they belong to the dashboard
  if (href === "/console") return pathname.startsWith("/console") || pathname.startsWith("/runs");
  return pathname.startsWith(href);
}

export function Nav() {
  return (
    <Suspense fallback={<Shell pathname="" mode={undefined} demo={DEMO} />}>
      <NavInner />
    </Suspense>
  );
}

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5 text-base font-bold tracking-tight">
      <span className="logo-tile inline-flex h-8 w-8 items-center justify-center rounded-lg">
        <IconShieldCheck width={18} height={18} />
      </span>
      Airlock
    </Link>
  );
}

function Shell({
  pathname,
  mode,
  demo,
}: {
  pathname: string;
  mode: { llm: string; sandbox: string } | null | undefined;
  demo: boolean;
}) {
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-bg/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-3">
        <Logo />
        <nav
          aria-label="Main"
          className="ml-2 hidden items-center gap-0.5 rounded-xl border border-line bg-surface-2/60 p-1 md:flex"
        >
          {LINKS.map((l) => {
            const active = pathname !== "" && isActive(pathname, l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  active ? "card-shadow bg-surface text-fg" : "text-muted hover:text-fg"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {demo ? (
            <span className="hidden items-center gap-2 whitespace-nowrap rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-muted lg:inline-flex">
              <span className="live-dot inline-block h-1.5 w-1.5 rounded-full bg-primary" />
              read-only · recorded runs
            </span>
          ) : mode === undefined ? null : mode ? (
            <span className="hidden items-center gap-2 whitespace-nowrap rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-muted lg:inline-flex">
              <span className="live-dot inline-block h-1.5 w-1.5 rounded-full bg-success" />
              {mode.llm} llm · {mode.sandbox} sandbox
            </span>
          ) : (
            <span className="inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-warning-line bg-warning-badge px-3 py-1 text-xs font-medium text-warning-text">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-warning" />
              backend offline
            </span>
          )}
          <ThemeToggle />
        </div>
      </div>
      {/* small screens: the same links as a scrollable strip */}
      <nav aria-label="Main (mobile)" className="flex gap-1 overflow-x-auto px-4 pb-2 md:hidden">
        {LINKS.map((l) => {
          const active = pathname !== "" && isActive(pathname, l.href);
          return (
            <Link
              key={l.href}
              href={l.href}
              aria-current={active ? "page" : undefined}
              className={`shrink-0 rounded-lg px-3 py-1.5 text-sm font-medium ${
                active ? "bg-surface-2 text-fg" : "text-muted"
              }`}
            >
              {l.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}

function NavInner() {
  const pathname = usePathname();
  const [mode, setMode] = useState<{ llm: string; sandbox: string } | null | undefined>(undefined);

  useEffect(() => {
    if (DEMO) return; // static build: no backend to probe, Shell shows the demo pill
    const fetchMode = (retry: boolean) => {
      api
        .readyz()
        .then((r) => setMode({ llm: r.llm, sandbox: r.sandbox }))
        .catch(() => {
          if (retry) window.setTimeout(() => fetchMode(false), 1500);
          else queueMicrotask(() => setMode(null));
        });
    };
    fetchMode(true);
  }, []);

  return <Shell pathname={pathname} mode={mode} demo={DEMO} />;
}
