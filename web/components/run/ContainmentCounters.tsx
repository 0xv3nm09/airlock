"use client";

import { Card, CardTitle } from "@/components/ui";
import { IconFileBan, IconGauge, IconGlobe, IconKey } from "@/components/Icons";
import { CountUp } from "@/components/motion";
import type { Counters } from "@/lib/types";

const ITEMS = [
  { key: "network_blocked", icon: <IconGlobe />, label: "Network calls blocked" },
  { key: "canary_hits", icon: <IconKey />, label: "Canary keys touched" },
  { key: "writes_denied", icon: <IconFileBan />, label: "Writes denied" },
  { key: "limits_hit", icon: <IconGauge />, label: "Limits hit" },
] as const;

export function ContainmentCounters({ counters }: { counters: Counters }) {
  return (
    <Card>
      <CardTitle hint="contained in this run">Containment counters</CardTitle>
      <div className="grid grid-cols-2 gap-3">
        {ITEMS.map((item) => {
          const value = counters[item.key];
          const hot = value > 0;
          return (
            <div
              key={item.key}
              className={`lift rounded-lg border p-3 ${
                hot ? "border-danger-line bg-danger-badge" : "border-line bg-surface-2"
              }`}
            >
              <div
                className={`flex items-center gap-1.5 text-xs font-medium ${
                  hot ? "text-danger-text" : "text-muted"
                }`}
              >
                {item.icon}
                {item.label}
              </div>
              <div
                className={`mt-1 text-2xl font-bold ${hot ? "text-danger-text" : "text-fg"}`}
                aria-label={`${value} ${item.label}`}
              >
                <CountUp value={value} duration={500} />
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
