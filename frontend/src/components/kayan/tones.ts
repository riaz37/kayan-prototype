import type { Tone } from "@/components/ui/badge";

/** Tinted icon chip / badge colours, shared by stat cards and channel tiles. */
export const TONE_CHIP: Record<Tone, string> = {
  brand: "bg-brand-50 text-brand-700 ring-brand-100",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-100",
  amber: "bg-amber-50 text-amber-700 ring-amber-100",
  sky: "bg-sky-50 text-sky-700 ring-sky-100",
  rose: "bg-rose-50 text-rose-700 ring-rose-100",
  violet: "bg-violet-50 text-violet-700 ring-violet-100",
  slate: "bg-slate-50 text-slate-600 ring-slate-200/70",
};

export const TONE_DOT: Record<Tone, string> = {
  brand: "bg-brand-500",
  green: "bg-emerald-500",
  amber: "bg-amber-500",
  sky: "bg-sky-500",
  rose: "bg-rose-500",
  violet: "bg-violet-500",
  slate: "bg-slate-400",
};

/** Status/stage/decision code → badge tone (same mapping as the original console). */
const STATUS_TONE: Record<string, Tone> = {
  open: "green",
  in_progress: "sky",
  waiting_customer: "amber",
  replied: "violet",
  expired: "rose",
  closed: "slate",
  approved: "green",
  submitted: "sky",
  under_review: "amber",
  draft: "slate",
  rejected: "rose",
  paid: "green",
  scheduled: "sky",
  pending: "amber",
  pending_approval: "amber",
  accepted: "green",
  declined: "rose",
  docs_required: "amber",
  decided: "green",
  committee: "violet",
  under_study: "sky",
  active: "green",
  completed: "slate",
};

export function toneFor(code: string | null | undefined): Tone {
  return (code && STATUS_TONE[code]) || "slate";
}
