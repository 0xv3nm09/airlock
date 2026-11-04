import type { NextConfig } from "next";

/* AIRLOCK_STATIC_BUILD=1 switches to a fully static export for GitHub Pages
 * (deploy/GO-LIVE.md → "Public demo site"). The demo build sets NEXT_PUBLIC_DEMO_MODE=1
 * so every read resolves from the committed snapshot of recorded runs — no rewrites,
 * no backend. Normal server deployments are untouched. */
const staticExport = process.env.AIRLOCK_STATIC_BUILD === "1";

const nextConfig: NextConfig = {
  // Next's built-in gzip buffers proxied SSE responses until the browser receives nothing;
  // compression belongs at the edge (Caddy sets flush_interval -1 for /v1/* streams).
  compress: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  ...(staticExport
    ? {
        output: "export" as const,
        // Must match the GitHub repo name: 0xv3nm09.github.io/<repo>/
        basePath: process.env.AIRLOCK_BASE_PATH ?? "/airlock",
        trailingSlash: true,
        images: { unoptimized: true },
      }
    : {
        // PPR cannot be enabled in export mode.
        cacheComponents: true,
        partialPrefetching: true,
        async rewrites() {
          // Same-origin proxy to the FastAPI backend: cookies and EventSource just work.
          const backend = process.env.AIRLOCK_API_URL ?? "http://127.0.0.1:8000";
          return [{ source: "/api/:path*", destination: `${backend}/:path*` }];
        },
      }),
};

export default nextConfig;
