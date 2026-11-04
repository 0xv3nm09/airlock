/* WCAG 2.2 contrast audit for the Airlock design tokens.
 * Parses app/globals.css (:root light block and .dark block), computes WCAG contrast
 * ratios for every declared pair, and fails if any text pair < 4.5:1 or UI/focus pair < 3:1.
 * Run: node scripts/contrast-audit.mjs */
import { readFileSync } from "node:fs";

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

function parseVars(block) {
  const vars = {};
  for (const m of block.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)) {
    vars[m[1]] = m[2];
  }
  return vars;
}

const rootBlock = css.slice(css.indexOf(":root"), css.indexOf("\n.dark"));
const darkBlock = css.slice(css.indexOf(".dark"), css.indexOf("@theme"));
const themes = { light: parseVars(rootBlock), dark: parseVars(darkBlock) };

function luminance(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = c.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(fg, bg) {
  const l1 = luminance(fg);
  const l2 = luminance(bg);
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

/* [foreground, background, min, kind] — kind: text (4.5) | ui (3) */
const PAIRS = [
  ["fg", "bg", 4.5, "text"],
  ["fg", "surface", 4.5, "text"],
  ["fg", "surface-2", 4.5, "text"],
  ["muted", "surface", 4.5, "text"],
  ["muted", "bg", 4.5, "text"],
  ["muted", "surface-2", 4.5, "text"],
  ["primary-fg", "primary", 4.5, "text"],
  ["primary", "surface", 4.5, "text"],
  ["success-text", "success-badge", 4.5, "text"],
  ["warning-text", "warning-badge", 4.5, "text"],
  ["danger-text", "danger-badge", 4.5, "text"],
  ["info-text", "info-badge", 4.5, "text"],
  ["focus", "bg", 3.0, "ui (focus ring 2.4.13)"],
  ["focus", "surface", 3.0, "ui (focus ring 2.4.13)"],
  ["primary", "bg", 3.0, "ui (button boundary 1.4.11)"],
  ["line-strong", "surface", 3.0, "ui (interactive border 1.4.11)"],
  /* gradient-text stops (large display text, kept ≥ 4.5 anyway) and console colors */
  ["grad-a", "bg", 4.5, "text (gradient headline stop)"],
  ["grad-b", "bg", 4.5, "text (gradient headline stop)"],
  ["grad-c", "bg", 4.5, "text (gradient headline stop)"],
  ["c-net", "surface-2", 4.5, "text (console feed)"],
  ["c-canary", "surface-2", 4.5, "text (console feed)"],
  ["c-write", "surface-2", 4.5, "text (console feed)"],
  ["c-limit", "surface-2", 4.5, "text (console feed)"],
];

let failures = 0;
console.log("theme  pair                          ratio   min  kind");
for (const [theme, vars] of Object.entries(themes)) {
  for (const [fg, bg, min, kind] of PAIRS) {
    const f = vars[fg];
    const b = vars[bg];
    if (!f || !b) {
      console.log(`${theme.padEnd(6)} ${`${fg}/${bg}`.padEnd(28)} MISSING TOKEN`);
      failures += 1;
      continue;
    }
    const r = ratio(f, b);
    const ok = r >= min;
    if (!ok) failures += 1;
    console.log(
      `${theme.padEnd(6)} ${(fg + "/" + bg).padEnd(28)} ${r.toFixed(2).padStart(5)}  ${String(min).padStart(4)}  ${kind}${ok ? "" : "  ✗ FAIL"}`,
    );
  }
}

console.log(
  failures === 0
    ? "\nPASS — every pair meets its WCAG 2.2 target."
    : `\nFAIL — ${failures} pair(s) below target.`,
);
process.exit(failures === 0 ? 0 : 1);
