import { Suspense } from "react";
import { runStaticParams } from "@/lib/demo-params";
import { RunPageClient } from "./run-view";
import { Spinner } from "@/components/ui";

/* The static export prerenders one page per recorded run (lib/demo-params); server
 * deployments render any run on demand. The view itself is a client component that
 * replays the run's trace (live via SSE, in the demo from the bundled snapshot). */
export function generateStaticParams() {
  return runStaticParams();
}

export default function RunPage() {
  return (
    <Suspense
      fallback={
        <div className="py-20 text-center">
          <Spinner label="Loading run…" />
        </div>
      }
    >
      <RunPageClient />
    </Suspense>
  );
}
