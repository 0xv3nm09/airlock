/* Static-demo data source for the GitHub Pages build (AIRLOCK_STATIC_BUILD=1 +
 * NEXT_PUBLIC_DEMO_MODE=1). The snapshot holds real recorded runs exported from the
 * live store by scripts/export_demo_snapshot.py — the same pattern as blind-run's
 * bundled data.js. In demo mode no backend call ever happens, so the site can't go
 * empty or show "backend offline". */

import snapshotJson from "@/demo/airlock-snapshot.json";
import type { AirlockEvent, BenchmarkCase, BenchmarkResult, RunOut } from "./types";

export const DEMO = process.env.NEXT_PUBLIC_DEMO_MODE === "1";

export interface DemoSnapshot {
  generated_at: string;
  readyz: {
    status: string;
    llm: string;
    sandbox: string;
    policy_version: string;
    queue_depth: number;
    kill_switch: boolean;
  };
  stats: Record<string, unknown>;
  runs: RunOut[];
  recent: unknown[];
  traces: Record<string, AirlockEvent[]>;
  benchmark: BenchmarkResult | null;
  benchmark_cases: BenchmarkCase[];
}

export const demoSnapshot = snapshotJson as DemoSnapshot;

export function demoRunById(id: string): RunOut | undefined {
  return demoSnapshot.runs.find((r) => r.id === id);
}
