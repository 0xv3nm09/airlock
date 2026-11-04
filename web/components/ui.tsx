/* Small UI primitives on top of the token system. Buttons are ≥ 40 px tall (comfortably
 * above the WCAG 2.5.8 24 px minimum target). */
import type { ReactNode } from "react";

export type Tone = "success" | "warning" | "danger" | "info" | "neutral";

const BADGE_STYLES: Record<Tone, string> = {
  success: "bg-success-badge text-success-text border-success-line",
  warning: "bg-warning-badge text-warning-text border-warning-line",
  danger: "bg-danger-badge text-danger-text border-danger-line",
  info: "bg-info-badge text-info-text border-info-line",
  neutral: "bg-surface-2 text-muted border-line",
};

export function Badge({
  tone = "neutral",
  icon,
  children,
  className = "",
}: {
  tone?: Tone;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-sm font-medium ${BADGE_STYLES[tone]} ${className}`}
    >
      {icon}
      {children}
    </span>
  );
}

export function Card({
  children,
  className = "",
  as: Tag = "section",
  id,
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article";
  id?: string;
}) {
  return (
    <Tag id={id} className={`card-shadow rounded-2xl border border-line bg-surface p-5 ${className}`}>{children}</Tag>
  );
}

export function CardTitle({ children, hint }: { children: ReactNode; hint?: string }) {
  return (
    <div className="mb-4 flex items-baseline justify-between gap-3">
      <h2 className="text-base font-semibold">{children}</h2>
      {hint ? <span className="text-sm text-muted">{hint}</span> : null}
    </div>
  );
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "danger" | "ghost";
};

export function Button({ variant = "primary", className = "", ...rest }: ButtonProps) {
  const styles = {
    primary: "btn-grad shadow-sm active:translate-y-px",
    danger: "bg-danger-badge text-danger-text border border-danger-line hover:opacity-90",
    ghost: "border border-line-strong text-fg hover:bg-surface-2",
  }[variant];
  return (
    <button
      {...rest}
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-lg px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${styles} ${className}`}
    />
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-muted" role="status">
      <svg
        className="h-4 w-4 animate-spin"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        aria-hidden
      >
        <path d="M21 12a9 9 0 1 1-6.22-8.56" strokeLinecap="round" />
      </svg>
      {label}
    </span>
  );
}
