import { Suspense } from "react";
import { runStaticParams } from "@/lib/demo-params";
import { Spinner } from "@/components/ui";
import { TracePageClient } from "./trace-view";

/* Static export: one prerendered trace page per recorded run (lib/demo-params). */
export function generateStaticParams() {
  return runStaticParams();
}

export default function TracePage() {
  return (
    <Suspense
      fallback={
        <div className="py-20 text-center">
          <Spinner label="Loading trace…" />
        </div>
      }
    >
      <TracePageClient />
    </Suspense>
  );
}
