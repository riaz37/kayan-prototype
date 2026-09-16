"use client";

import type { ComponentProps, ReactNode } from "react";
import { Inbox, RefreshCw, Search, type LucideIcon } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useI18n } from "@/components/providers/i18n-provider";
import type { CatalogKind } from "@/lib/i18n/catalog";
import { cn } from "@/lib/utils";
import { TONE_CHIP, toneFor } from "./tones";
import type { Tone } from "@/components/ui/badge";

/* ------------------------------------------------------------------ layout */

export function PageHead({ title, sub, right }: { title: ReactNode; sub?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-[22px] font-semibold tracking-tight text-ink">{title}</h1>
        {sub && <p className="mt-0.5 text-[13px] text-ink-muted">{sub}</p>}
      </div>
      {right}
    </div>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone = "slate",
  icon: Icon,
  onClick,
  loading,
}: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  tone?: Tone;
  icon?: LucideIcon;
  onClick?: () => void;
  loading?: boolean;
}) {
  const body = (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="text-[12px] font-medium text-ink-muted">{label}</p>
        {loading ? (
          <div className="mt-2 mb-1 h-7 w-20 animate-pulse rounded-md bg-line-soft" />
        ) : (
          <p className="mt-0.5 text-[26px] leading-9 font-semibold text-ink tabular">{value}</p>
        )}
        {hint && <p className="mt-0.5 truncate text-[11.5px] text-ink-soft">{hint}</p>}
      </div>
      {Icon && (
        <span className={cn("shrink-0 rounded-lg p-2 ring-1 ring-inset", TONE_CHIP[tone])}>
          <Icon className="size-[17px]" strokeWidth={1.8} />
        </span>
      )}
    </div>
  );
  if (onClick) {
    return (
      <Card hover className="animate-enter">
        <button
          type="button"
          onClick={onClick}
          className="block w-full cursor-pointer rounded-xl p-4 text-start outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
        >
          {body}
        </button>
      </Card>
    );
  }
  return <Card className="animate-enter p-4">{body}</Card>;
}

/** Small metric tile used in page summary rows. */
export function MiniStat({ label, value, highlight }: { label: ReactNode; value: ReactNode; highlight?: boolean }) {
  return (
    <Card className="px-4 py-3">
      <p className="text-[11.5px] text-ink-muted">{label}</p>
      <p className={cn("mt-0.5 text-[21px] font-semibold tabular", highlight ? "text-brand-700" : "text-ink")}>{value}</p>
    </Card>
  );
}

export function Field({ label, value, mono }: { label: ReactNode; value: ReactNode; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11.5px] text-ink-muted">{label}</dt>
      <dd className={cn("mt-0.5 truncate text-[13px] text-ink", mono && "tabular")}>{value ?? "—"}</dd>
    </div>
  );
}

export function Empty({ icon: Icon = Inbox, title, sub }: { icon?: LucideIcon; title: ReactNode; sub?: ReactNode }) {
  return (
    <div className="py-16 text-center">
      <div className="mb-3 inline-flex rounded-xl bg-line-soft p-3 text-ink-soft">
        <Icon className="size-5" />
      </div>
      <p className="text-[14px] font-medium text-ink">{title}</p>
      {sub && <p className="mt-1 text-[12.5px] text-ink-muted">{sub}</p>}
    </div>
  );
}

/** Inline error block with retry — shown when an API request fails. */
export function LoadError({ onRetry, className }: { onRetry?: () => void; className?: string }) {
  const { t } = useI18n();
  return (
    <div role="alert" className={cn("py-12 text-center", className)}>
      <p className="text-[14px] font-medium text-ink">{t.common.loadError}</p>
      <p className="mt-1 text-[12.5px] text-ink-muted">{t.common.loadErrorSub}</p>
      {onRetry && (
        <Button variant="outline" size="sm" className="mt-4" onClick={onRetry}>
          <RefreshCw /> {t.common.retry}
        </Button>
      )}
    </div>
  );
}

export function SearchInput({ className, ...props }: ComponentProps<typeof Input>) {
  return (
    <div className={cn("relative", className)}>
      <Search className="pointer-events-none absolute inset-y-0 start-3 my-auto size-[15px] text-ink-soft" />
      <Input type="search" className="ps-9 pe-3 [&::-webkit-search-cancel-button]:hidden" {...props} />
    </div>
  );
}

/* ------------------------------------------------------------------ data display */

const AVATAR_TONES = [
  "bg-brand-50 text-brand-700",
  "bg-violet-50 text-violet-700",
  "bg-amber-50 text-amber-700",
  "bg-sky-50 text-sky-700",
  "bg-emerald-50 text-emerald-700",
  "bg-rose-50 text-rose-700",
];

export function NameAvatar({ name, size = 34, className }: { name?: string | null; size?: number; className?: string }) {
  const clean = (name ?? "").trim();
  const initial = clean ? Array.from(clean)[0] : "?";
  const tone = AVATAR_TONES[clean.length % AVATAR_TONES.length];
  return (
    <Avatar className={cn("shrink-0 after:hidden", className)} style={{ width: size, height: size }} aria-hidden>
      <AvatarFallback dir="auto" className={cn("font-semibold", tone)} style={{ fontSize: size * 0.38 }}>
        {initial}
      </AvatarFallback>
    </Avatar>
  );
}

/** Renders user-entered text (names, subjects, messages) with its own direction. */
export function DataText({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span dir="auto" className={className}>
      {children}
    </span>
  );
}

/** Badge for a status/stage/decision code, labelled in the current locale. */
export function StatusBadge({
  kind,
  code,
  arabic,
  tone,
  dot = true,
  className,
}: {
  kind: CatalogKind;
  code?: string | null;
  arabic?: string | null;
  tone?: Tone;
  dot?: boolean;
  className?: string;
}) {
  const { label } = useI18n();
  return (
    <Badge tone={tone ?? toneFor(code)} dot={dot} className={className}>
      {label(kind, code, arabic)}
    </Badge>
  );
}

export function Ring({ value = 0, size = 62, stroke = 5 }: { value?: number; size?: number; stroke?: number }) {
  const v = Math.max(0, Math.min(100, value));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const color = v >= 90 ? "#059669" : v >= 50 ? "#0F8478" : "#D97706";
  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`${Math.round(v)}%`}
    >
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#F2F4F7" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeDasharray={c}
          strokeDashoffset={c - (c * v) / 100}
          strokeLinecap="round"
          style={{ transition: "stroke-dashoffset .9s cubic-bezier(.16,1,.3,1)" }}
        />
      </svg>
      <span className="absolute text-[13px] font-semibold text-ink tabular">
        {Math.round(v)}
        <span className="text-[9px] text-ink-soft">%</span>
      </span>
    </div>
  );
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-4">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-10 animate-pulse rounded-lg bg-line-soft" />
      ))}
    </div>
  );
}
