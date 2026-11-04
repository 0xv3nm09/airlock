/* generateStaticParams source for the dynamic run routes. The static export must
 * enumerate every recorded run id at build time (NEXT_PUBLIC_DEMO_MODE=1). Server
 * deployments render any run on demand — Cache Components still requires at least one
 * entry for build-time validation, so return the first recorded run. */
import { DEMO, demoSnapshot } from "./demo";

export function runStaticParams(): { id: string }[] {
  if (DEMO) return demoSnapshot.runs.map((r) => ({ id: r.id }));
  return [{ id: demoSnapshot.runs[0]?.id ?? "run" }];
}
