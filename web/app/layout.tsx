import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/Nav";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Airlock — Run the PR before you trust it",
  description:
    "Airlock runs a stranger's pull request inside a throwaway sandbox, watches what it does, and reports only what it proved.",
};

const THEME_BOOT = `(() => {
  try {
    const stored = localStorage.getItem("airlock_theme");
    const dark = stored ? stored === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.classList.toggle("dark", dark);
  } catch {}
})();`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body className="flex min-h-full flex-col">
        <Nav />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
        <footer className="border-t border-line py-6 text-center text-sm text-muted">
          Airlock · every run executes inside an isolated sandbox on Vultr ·{" "}
          <a className="underline hover:text-fg" href="/about">
            what we check and what we don&apos;t
          </a>
        </footer>
      </body>
    </html>
  );
}
