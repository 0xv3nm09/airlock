"use client";

/* Motion primitives: scroll-reveal + count-up. Both respect prefers-reduced-motion
 * (the global CSS rule also neuters the CSS animations). */
import { useEffect, useRef, useState, type ReactNode } from "react";

export function Reveal({
  children,
  delay = 0,
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      queueMicrotask(() => setShown(true));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setShown(true);
            io.disconnect();
          }
        }
      },
      { threshold: 0, rootMargin: "0px 0px -8% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`${shown ? "reveal-in" : "reveal"} ${className}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}

export function CountUp({
  value,
  suffix = "",
  duration = 900,
  className = "",
}: {
  value: number;
  suffix?: string;
  duration?: number;
  className?: string;
}) {
  const [display, setDisplay] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const settle = () => queueMicrotask(() => setDisplay(value));
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      settle();
      return;
    }
    // The value arrived/changed after the first animation: settle straight to it, so live
    // numbers (0 → N as runs land) always track the API instead of freezing at the start.
    if (started.current) {
      settle();
      return;
    }
    const begin = () => {
      started.current = true;
      // Time-based progression: even if the event loop throttles (background pane),
      // the next tick jumps straight to the correct value — never left half-counted.
      const t0 = performance.now();
      const iv = window.setInterval(() => {
        const p = Math.min((performance.now() - t0) / duration, 1);
        setDisplay(Math.round(value * (1 - Math.pow(1 - p, 3))));
        if (p >= 1) window.clearInterval(iv);
      }, 50);
      cleanupRef.current = () => window.clearInterval(iv);
    };
    // Some embedded webviews never dispatch IntersectionObserver callbacks at all — the
    // number must not stay 0 there. If the card is already on screen, animate now;
    // otherwise let IO trigger on scroll, with a settle fallback as the last resort.
    const r = el.getBoundingClientRect();
    const onScreen =
      r.top < window.innerHeight && r.bottom > 0 && r.width > 0 && r.height > 0;
    if (onScreen) {
      begin();
      return () => {
        cleanupRef.current?.();
      };
    }
    const io = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting || started.current) continue;
        begin();
        io.disconnect();
      }
    });
    io.observe(el);
    const fallback = window.setTimeout(() => {
      if (!started.current) settle();
      io.disconnect();
    }, 2500);
    return () => {
      window.clearTimeout(fallback);
      cleanupRef.current?.();
      io.disconnect();
    };
  }, [value, duration]);

  return (
    <span ref={ref} className={className}>
      {display.toLocaleString("en-US")}
      {suffix}
    </span>
  );
}
