import { Fragment, createElement, type ReactNode } from "react";
import { intlLocale, type Locale } from "./config";
import type { Dictionary } from "./dictionaries/ar";

export type PluralForms = { other: string } & Partial<Record<Intl.LDMLPluralRule, string>>;
type Vars = Record<string, string | number>;

/** Replace `{key}` placeholders with values. */
export function format(template: string, vars: Vars = {}): string {
  return template.replace(/\{(\w+)\}/g, (m, key: string) => (key in vars ? String(vars[key]) : m));
}

/** Like `format`, but values may be React nodes (e.g. bold numbers inside a sentence). */
export function rich(template: string, vars: Record<string, ReactNode>): ReactNode {
  const parts = template.split(/(\{\w+\})/g);
  return parts.map((part, i) => {
    const m = /^\{(\w+)\}$/.exec(part);
    return createElement(Fragment, { key: i }, m && m[1] in vars ? vars[m[1]] : part);
  });
}

/**
 * Backend timestamps are UTC; some carry `Z`, some are naive ISO strings.
 * Date-only values (`2026-09-12`) are calendar dates and must not shift by timezone.
 */
export function parseApiDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const s = String(value).trim();
  const dateOnly = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (dateOnly) return new Date(Number(dateOnly[1]), Number(dateOnly[2]) - 1, Number(dateOnly[3]));
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/i.test(s);
  const d = new Date(hasZone ? s : `${s}Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

export type Sla = { breached?: boolean; remaining_seconds?: number | null; remaining_ar?: string | null };

export function createFormatters(locale: Locale, dict: Dictionary) {
  const tag = intlLocale(locale);
  const numberFmt = new Intl.NumberFormat(tag, { maximumFractionDigits: 0 });
  const decimalFmt = new Intl.NumberFormat(tag, { maximumFractionDigits: 1 });
  const dateFmt = new Intl.DateTimeFormat(tag, { year: "numeric", month: "short", day: "numeric" });
  const longDateFmt = new Intl.DateTimeFormat(tag, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const timeFmt = new Intl.DateTimeFormat(tag, { hour: "2-digit", minute: "2-digit" });
  const relFmt = new Intl.RelativeTimeFormat(tag, { numeric: "auto", style: "short" });
  const pluralRules = new Intl.PluralRules(tag);
  const dash = "—";

  const slaText = (hours: number, minutes: number) =>
    format(dict.common.slaRemaining, { h: numberFmt.format(hours), m: numberFmt.format(minutes) });

  const slaFromString = (raw: string): { text: string; breached: boolean } => {
    const s = raw.trim();
    if (!s || s === "-") return { text: dash, breached: false };
    if (s.includes("منتهية")) return { text: dict.common.slaExpired, breached: true };
    const m = /(\d+)\s*س\s*(\d+)\s*د/.exec(s);
    return m ? { text: slaText(Number(m[1]), Number(m[2])), breached: false } : { text: dash, breached: false };
  };

  return {
    number: (v: number | null | undefined) => (v == null || Number.isNaN(v) ? dash : numberFmt.format(v)),
    decimal: (v: number | null | undefined) => (v == null || Number.isNaN(v) ? dash : decimalFmt.format(v)),
    money: (v: number | null | undefined) =>
      v == null || Number.isNaN(v) ? dash : format(dict.common.moneyPattern, { amount: numberFmt.format(Math.round(v)) }),
    date: (v: string | null | undefined) => {
      const d = parseApiDate(v);
      return d ? dateFmt.format(d) : dash;
    },
    longDate: (d: Date) => longDateFmt.format(d),
    time: (v: string | Date | null | undefined) => {
      const d = v instanceof Date ? v : parseApiDate(v);
      return d ? timeFmt.format(d) : dash;
    },
    /** "3 min. ago" / "قبل 3 د" */
    relative: (v: string | null | undefined, now = Date.now()) => {
      const d = parseApiDate(v);
      if (!d) return dash;
      const secs = Math.round((d.getTime() - now) / 1000);
      const abs = Math.abs(secs);
      if (abs < 60) return relFmt.format(0, "second");
      if (abs < 3600) return relFmt.format(Math.round(secs / 60), "minute");
      if (abs < 86400) return relFmt.format(Math.round(secs / 3600), "hour");
      return relFmt.format(Math.round(secs / 86400), "day");
    },
    /** m:ss */
    duration: (seconds: number | null | undefined) => {
      const s = Math.max(0, Math.round(seconds ?? 0));
      return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
    },
    hours: (h: number | null | undefined) => format(dict.common.hoursShort, { n: h == null ? 0 : decimalFmt.format(h) }),
    plural: (forms: PluralForms, n: number) => {
      const rule = pluralRules.select(n);
      return format(forms[rule] ?? forms.other, { n: numberFmt.format(n) });
    },
    /**
     * SLA countdown. Accepts the structured object from ticket endpoints, or the
     * Arabic string the kanban endpoint returns ("47س 12د", "منتهية المدة", "-").
     */
    sla: (sla: Sla | string | null | undefined): { text: string; breached: boolean } => {
      if (sla == null) return { text: dash, breached: false };
      if (typeof sla === "string") return slaFromString(sla);
      if (sla.breached) return { text: dict.common.slaExpired, breached: true };
      const secs = sla.remaining_seconds ?? 0;
      if (secs <= 0) return sla.remaining_ar ? slaFromString(sla.remaining_ar) : { text: dash, breached: false };
      return { text: slaText(Math.floor(secs / 3600), Math.floor((secs % 3600) / 60)), breached: false };
    },
  };
}

export type Formatters = ReturnType<typeof createFormatters>;
