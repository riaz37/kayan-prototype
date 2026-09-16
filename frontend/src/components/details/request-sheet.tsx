"use client";

import Link from "next/link";
import { useId, useState, type ReactNode } from "react";
import { Check, ClipboardList, ExternalLink, LoaderCircle, Scale, Wallet } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { DataText, Field, LoadError, StatusBadge } from "@/components/kayan/primitives";
import { toneFor } from "@/components/kayan/tones";
import { DecisionDialog, type DecisionTarget, type DecisionType } from "@/components/details/decision-dialog";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import { useDetailNav } from "@/components/shell/use-detail-nav";
import { api } from "@/lib/api/client";
import { useCaseSteps, useRevalidate, useStaff, useSupportRequest } from "@/lib/api/hooks";
import type { CaseStep, SupportRequestDetail } from "@/lib/api/types";
import { cn } from "@/lib/utils";

const DEFAULT_RESEARCHER = "STF-04";

export function RequestSheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <Sheet open={!!id} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="end" className="max-w-3xl overflow-y-auto" closeLabel={t.common.close}>
        {id && <RequestDetail key={id} id={id} />}
      </SheetContent>
    </Sheet>
  );
}

/** Wraps an API action: busy flag, success toast, error toast, revalidation of every affected view. */
function useAction(onDone: () => void) {
  const { t } = useI18n();
  const revalidate = useRevalidate();
  const [busy, setBusy] = useState<string | null>(null);
  const run = async (key: string, fn: () => Promise<unknown>, success: string) => {
    setBusy(key);
    try {
      await fn();
      toast.success(success);
      onDone();
      void revalidate("/support-requests", "/committee", "/reports", "/finance", "/beneficiary/", "/beneficiaries");
      return true;
    } catch {
      toast.error(t.request.actionFailed);
      return false;
    } finally {
      setBusy(null);
    }
  };
  return { busy, run };
}

function RequestDetail({ id }: { id: string }) {
  const { t, fmt, label } = useI18n();
  const { data: d, error, isLoading, mutate } = useSupportRequest(id);
  const { openBeneficiary } = useDetailNav();
  const { can } = useSession();
  const [decision, setDecision] = useState<DecisionTarget | null>(null);

  if (error && !d) {
    return (
      <>
        <SheetHeader>
          <div className="min-w-0">
            <SheetTitle>{t.request.notFound}</SheetTitle>
            <SheetDescription className="tabular">{id}</SheetDescription>
          </div>
        </SheetHeader>
        <LoadError onRetry={() => mutate()} />
      </>
    );
  }

  if (isLoading || !d) {
    return (
      <div className="space-y-4 p-6">
        <SheetTitle className="sr-only">{id}</SheetTitle>
        <SheetDescription className="sr-only">{id}</SheetDescription>
        <Skeleton className="h-6 w-64" />
        <Skeleton className="h-16" />
        <Skeleton className="h-40" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  const typeLabel = d.request_type_id || d.title_ar ? label("requestType", d.request_type_id, d.title_ar) : t.beneficiary.untitledRequest;
  const description = d.description_ar || d.case_description_ar;
  const decide = (type: DecisionType) =>
    setDecision({ requestId: d.id, name: d.name_ar, requestedAmount: d.requested_amount_sar, type });

  return (
    <>
      <SheetHeader>
        <div className="min-w-0">
          <SheetTitle>{typeLabel}</SheetTitle>
          <SheetDescription>
            <span className="tabular">{d.id}</span> · <DataText>{d.name_ar ?? d.beneficiary_id}</DataText>
          </SheetDescription>
        </div>
      </SheetHeader>

      <div className="space-y-4 p-6">
        <Stepper d={d} />

        <Card className="p-5">
          <p className="mb-4 text-[13px] font-semibold text-ink">{t.request.summary}</p>
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-3">
            <Field
              label={t.request.beneficiary}
              value={
                <button
                  type="button"
                  onClick={() => openBeneficiary(d.beneficiary_id)}
                  className="cursor-pointer text-start text-brand-700 hover:underline"
                >
                  <DataText>{d.name_ar ?? d.beneficiary_id}</DataText>
                </button>
              }
            />
            <Field label={t.request.program} value={label("program", d.program_id, d.program_ar)} />
            <Field label={t.request.type} value={typeLabel} />
            <Field label={t.request.requested} value={fmt.money(d.requested_amount_sar)} mono />
            <Field
              label={t.request.classification}
              value={d.internal_classification ? label("classification", d.internal_classification) : "—"}
            />
            <Field label={t.request.channel} value={d.channel ? label("channel", d.channel) : "—"} />
            <Field label={t.request.submittedAt} value={fmt.date(d.created_at)} />
          </dl>
          <div className="mt-4 border-t border-line-soft pt-4">
            <p className="text-[11.5px] text-ink-muted">{t.request.description}</p>
            <p dir="auto" className="mt-1 text-[13px] leading-relaxed whitespace-pre-wrap text-ink">
              {description || t.request.noDescription}
            </p>
          </div>
        </Card>

        {d.stage === "submitted" && !d.case_study && can("casework:manage") && <OpenCasePanel d={d} onDone={() => mutate()} />}
        {d.case_study && <CasePanel d={d} onDone={() => mutate()} />}

        {d.stage === "committee" && !d.decision && can("committee:decide") && (
          <Card className="border-violet-100 bg-violet-50/40 p-5">
            <div className="flex items-start gap-3">
              <Scale className="mt-0.5 size-4 shrink-0 text-violet-700" />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-semibold text-ink">{t.request.decisionTitle}</p>
                <p className="mt-1 text-[12.5px] text-ink-muted">{t.request.atCommittee}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button size="sm" onClick={() => decide("accepted")}>
                    <Check className="size-3.5" /> {t.committee.accept}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => decide("docs_required")}>
                    {t.committee.docs}
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => decide("declined")}>
                    {t.committee.decline}
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        )}

        {d.decision && <DecisionPanel d={d} onDone={() => mutate()} />}
      </div>

      <DecisionDialog
        target={decision}
        onClose={() => {
          setDecision(null);
          void mutate();
        }}
      />
    </>
  );
}

/* ------------------------------------------------------------------ progress */

function Stepper({ d }: { d: SupportRequestDetail }) {
  const { t } = useI18n();
  const order = ["submitted", "under_study", "committee", "decided"];
  let current = Math.max(0, order.indexOf(d.stage));
  if (d.enrollment) current = 5;
  const outcome = d.decision?.decision;
  const steps = [
    t.request.progress.submitted,
    t.request.progress.study,
    t.request.progress.committee,
    t.request.progress.decision,
    t.request.progress.enrolled,
  ];
  return (
    <ol className="flex items-start gap-1 overflow-x-auto rounded-xl border border-line bg-white p-3">
      {steps.map((name, i) => {
        const done = i < current || (i === 3 && !!outcome);
        const active = i === current && !done;
        const blocked = i === 4 && outcome && outcome !== "accepted";
        const tone = i === 3 && outcome ? toneFor(outcome) : null;
        return (
          <li key={name} className="flex min-w-[92px] flex-1 flex-col items-center gap-1.5 text-center">
            <div className="flex w-full items-center">
              <span className={cn("h-0.5 flex-1", i === 0 ? "bg-transparent" : i <= current ? "bg-brand-400" : "bg-line")} />
              <span
                className={cn(
                  "grid size-7 shrink-0 place-items-center rounded-full text-[11px] font-semibold tabular ring-1",
                  done && !tone && "bg-brand-600 text-white ring-brand-600",
                  tone === "green" && "bg-emerald-600 text-white ring-emerald-600",
                  tone === "amber" && "bg-amber-500 text-white ring-amber-500",
                  tone === "rose" && "bg-rose-500 text-white ring-rose-500",
                  active && "bg-brand-50 text-brand-700 ring-brand-300",
                  !done && !active && "bg-white text-ink-soft ring-line",
                  blocked && "opacity-40",
                )}
              >
                {done ? <Check className="size-3.5" strokeWidth={3} /> : i + 1}
              </span>
              <span className={cn("h-0.5 flex-1", i === steps.length - 1 ? "bg-transparent" : i < current ? "bg-brand-400" : "bg-line")} />
            </div>
            <span className={cn("text-[11px]", active ? "font-semibold text-brand-700" : done ? "text-ink" : "text-ink-soft", blocked && "line-through opacity-50")}>
              {name}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/* ------------------------------------------------------------------ case study */

function PanelTitle({ icon, children, right }: { icon: ReactNode; children: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <p className="flex items-center gap-2 text-[13px] font-semibold text-ink">
        {icon}
        {children}
      </p>
      {right}
    </div>
  );
}

function StaffSelect({ value, onChange, id }: { value: string; onChange: (v: string) => void; id?: string }) {
  const { label } = useI18n();
  const staff = useStaff();
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger id={id} className="w-full min-w-56">
        <SelectValue />
      </SelectTrigger>
      <SelectContent position="popper">
        {(staff.data?.staff ?? []).map((s) => (
          <SelectItem key={s.id} value={s.id}>
            {label("staffName", s.id, s.name_ar)} · {label("staffRole", null, s.role_ar)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function OpenCasePanel({ d, onDone }: { d: SupportRequestDetail; onDone: () => void }) {
  const { t } = useI18n();
  const fieldId = useId();
  const [researcher, setResearcher] = useState(DEFAULT_RESEARCHER);
  const { busy, run } = useAction(onDone);
  return (
    <Card className="p-5">
      <PanelTitle icon={<ClipboardList className="size-4 text-brand-600" />}>{t.request.caseTitle}</PanelTitle>
      <p className="mb-4 text-[12.5px] text-ink-muted">{t.request.notStarted}</p>
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1.5">
          <Label htmlFor={fieldId} className="text-[12px] font-normal text-ink-muted">
            {t.request.researcher}
          </Label>
          <StaffSelect id={fieldId} value={researcher} onChange={setResearcher} />
        </div>
        <Button
          disabled={!!busy}
          onClick={() =>
            run(
              "open",
              () => api.post(`/support-requests/${encodeURIComponent(d.id)}/open-case?researcher_id=${encodeURIComponent(researcher)}`),
              t.request.caseOpened,
            )
          }
        >
          {busy === "open" && <LoaderCircle className="animate-spin" />}
          {t.request.openCase}
        </Button>
      </div>
    </Card>
  );
}

function CasePanel({ d, onDone }: { d: SupportRequestDetail; onDone: () => void }) {
  const { t, fmt, label } = useI18n();
  const { can } = useSession();
  const c = d.case_study!;
  const editable = c.status === "open" && d.stage === "under_study" && can("casework:manage");
  const completed = c.steps.filter((s) => s.status === "completed").length;
  return (
    <Card className="p-5">
      <PanelTitle
        icon={<ClipboardList className="size-4 text-brand-600" />}
        right={<Badge tone={c.status === "open" ? "sky" : "slate"} dot>{c.status === "open" ? label("stage", "under_study") : label("stage", "decided")}</Badge>}
      >
        {t.request.caseTitle}
      </PanelTitle>
      <dl className="mb-4 grid gap-3 sm:grid-cols-2">
        <Field label={t.request.researcher} value={c.social_researcher_id ? label("staffName", c.social_researcher_id) : "—"} />
        <Field label={t.request.openedAt} value={fmt.date(c.opened_at)} />
      </dl>

      <p className="mb-2 text-[12px] text-ink-muted">{t.request.steps}</p>
      {c.steps.length === 0 ? (
        <p className="rounded-lg border border-dashed border-line px-4 py-6 text-center text-[12.5px] text-ink-soft">{t.request.noSteps}</p>
      ) : (
        <ol className="space-y-2">
          {c.steps.map((s, i) => (
            <StepRow key={`${s.step_id}-${i}`} caseId={c.id} step={s} editable={editable} onDone={onDone} />
          ))}
        </ol>
      )}

      {c.recommendation_ar && (
        <div className="mt-4 rounded-lg bg-line-soft/60 px-3 py-2.5">
          <p className="text-[11.5px] text-ink-muted">{t.request.recommendation}</p>
          <p dir="auto" className="mt-0.5 text-[13px] text-ink">
            {c.recommendation_ar}
          </p>
        </div>
      )}

      {editable && (
        <div className="mt-5 grid gap-4 border-t border-line-soft pt-5 lg:grid-cols-2">
          <ScheduleForm caseId={c.id} researcher={c.social_researcher_id ?? DEFAULT_RESEARCHER} onDone={onDone} />
          <SubmitForm caseId={c.id} completed={completed} onDone={onDone} />
        </div>
      )}
    </Card>
  );
}

function StepRow({ caseId, step, editable, onDone }: { caseId: string; step: CaseStep; editable: boolean; onDone: () => void }) {
  const { t, fmt, format, label } = useI18n();
  const [open, setOpen] = useState(false);
  const [findings, setFindings] = useState("");
  const { busy, run } = useAction(onDone);
  const done = step.status === "completed";
  return (
    <li className="rounded-lg border border-line p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-ink">{label("caseStep", step.step_id, step.name_ar)}</p>
          <p className="mt-0.5 text-[11.5px] text-ink-soft">
            {step.scheduled_at && format(t.request.scheduledFor, { date: `${fmt.date(step.scheduled_at)} ${fmt.time(step.scheduled_at)}` })}
            {step.scheduled_at && step.assigned_staff_id && " · "}
            {step.assigned_staff_id && format(t.request.assignedTo, { name: label("staffName", step.assigned_staff_id) })}
          </p>
        </div>
        <Badge tone={done ? "green" : "amber"} dot>
          {label("caseStepStatus", done ? "completed" : "scheduled")}
        </Badge>
      </div>
      {step.findings_ar && (
        <p dir="auto" className="mt-2 rounded-md bg-emerald-50/60 px-2.5 py-1.5 text-[12.5px] text-ink">
          <span className="font-medium">{t.request.findings}: </span>
          {step.findings_ar}
        </p>
      )}
      {editable && !done && !open && (
        <Button size="sm" variant="soft" className="mt-2" onClick={() => setOpen(true)}>
          {t.request.recordFindings}
        </Button>
      )}
      {editable && !done && open && (
        <form
          className="mt-2 space-y-2"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!findings.trim()) return;
            await run(
              "findings",
              () => api.post(`/cases/${encodeURIComponent(caseId)}/record-findings`, { step_id: step.step_id, findings_ar: findings.trim() }),
              t.request.findingsSaved,
            );
          }}
        >
          <Textarea
            dir="auto"
            rows={2}
            autoFocus
            value={findings}
            onChange={(e) => setFindings(e.target.value)}
            placeholder={t.request.findingsPlaceholder}
            aria-label={t.request.findings}
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm" disabled={!!busy || !findings.trim()}>
              {busy && <LoaderCircle className="animate-spin" />}
              {t.request.recordFindings}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
              {t.common.cancel}
            </Button>
          </div>
        </form>
      )}
    </li>
  );
}

/** Tomorrow 10:00 in the browser's time zone, formatted for <input type="datetime-local">. */
function defaultSlot() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(10, 0, 0, 0);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function ScheduleForm({ caseId, researcher, onDone }: { caseId: string; researcher: string; onDone: () => void }) {
  const { t, label } = useI18n();
  const ids = { type: useId(), date: useId(), staff: useId() };
  const steps = useCaseSteps();
  const [stepId, setStepId] = useState("CS-FIELD");
  const [when, setWhen] = useState(defaultSlot);
  const [staff, setStaff] = useState(researcher);
  const { busy, run } = useAction(onDone);
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        const date = new Date(when);
        if (Number.isNaN(date.getTime())) return;
        void run(
          "schedule",
          () =>
            api.post(`/cases/${encodeURIComponent(caseId)}/schedule-step`, {
              step_id: stepId,
              scheduled_at: date.toISOString(),
              assigned_staff_id: staff,
            }),
          t.request.scheduled,
        );
      }}
    >
      <p className="text-[12.5px] font-semibold text-ink">{t.request.scheduleTitle}</p>
      <div className="space-y-1.5">
        <Label htmlFor={ids.type} className="text-[12px] font-normal text-ink-muted">
          {t.request.stepType}
        </Label>
        <Select value={stepId} onValueChange={setStepId}>
          <SelectTrigger id={ids.type} className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent position="popper">
            {(steps.data?.steps ?? []).map((s) => (
              <SelectItem key={s.id} value={s.id}>
                {label("caseStep", s.id, s.name_ar)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={ids.date} className="text-[12px] font-normal text-ink-muted">
          {t.request.stepDate}
        </Label>
        <Input id={ids.date} type="datetime-local" dir="ltr" value={when} onChange={(e) => setWhen(e.target.value)} required />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor={ids.staff} className="text-[12px] font-normal text-ink-muted">
          {t.request.researcher}
        </Label>
        <StaffSelect id={ids.staff} value={staff} onChange={setStaff} />
      </div>
      <Button type="submit" variant="outline" disabled={!!busy}>
        {busy && <LoaderCircle className="animate-spin" />}
        {t.request.schedule}
      </Button>
    </form>
  );
}

function SubmitForm({ caseId, completed, onDone }: { caseId: string; completed: number; onDone: () => void }) {
  const { t } = useI18n();
  const fieldId = useId();
  const [text, setText] = useState("");
  const { busy, run } = useAction(onDone);
  const ready = completed > 0;
  return (
    <form
      className="space-y-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (!ready || !text.trim()) return;
        void run(
          "submit",
          () => api.post(`/cases/${encodeURIComponent(caseId)}/submit-to-committee`, { recommendation_ar: text.trim() }),
          t.request.submitted,
        );
      }}
    >
      <p className="text-[12.5px] font-semibold text-ink">{t.request.submitTitle}</p>
      <div className="space-y-1.5">
        <Label htmlFor={fieldId} className="text-[12px] font-normal text-ink-muted">
          {t.request.recommendation}
        </Label>
        <Textarea
          id={fieldId}
          dir="auto"
          rows={4}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t.request.recommendationPlaceholder}
          disabled={!ready}
        />
      </div>
      {!ready && <p className="text-[11.5px] text-amber-700">{t.request.submitHint}</p>}
      <Button type="submit" disabled={!ready || !text.trim() || !!busy}>
        {busy && <LoaderCircle className="animate-spin" />}
        <Scale className="size-4" /> {t.request.submitToCommittee}
      </Button>
    </form>
  );
}

/* ------------------------------------------------------------------ decision + enrollment */

function DecisionPanel({ d, onDone }: { d: SupportRequestDetail; onDone: () => void }) {
  const { t, fmt, locale } = useI18n();
  const canEnroll = useSession().can("finance:manage");
  const dec = d.decision!;
  const accepted = dec.decision === "accepted";
  return (
    <>
      <Card className="p-5">
        <PanelTitle
          icon={<Scale className="size-4 text-brand-600" />}
          right={<StatusBadge kind="decision" code={dec.decision} arabic={dec.decision_ar} />}
        >
          {t.request.decisionTitle}
        </PanelTitle>
        <dl className="grid gap-3 sm:grid-cols-3">
          <Field label={t.request.decidedAt} value={fmt.date(dec.committee_date)} />
          {accepted && <Field label={t.request.approvedAmount} value={fmt.money(dec.approved_amount_sar)} mono />}
        </dl>
        {dec.reason_ar && (
          <div className="mt-3">
            <p className="text-[11.5px] text-ink-muted">{t.request.reason}</p>
            <p dir="auto" className="mt-0.5 text-[13px] text-ink">
              {dec.reason_ar}
            </p>
          </div>
        )}
        {!!dec.required_documents_ar?.length && (
          <div className="mt-3">
            <p className="mb-1.5 text-[11.5px] text-ink-muted">{t.request.requiredDocs}</p>
            <div className="flex flex-wrap gap-1.5">
              {dec.required_documents_ar.map((doc) => (
                <Badge key={doc} tone="amber">
                  <DataText>{doc}</DataText>
                </Badge>
              ))}
            </div>
          </div>
        )}
        {dec.decision === "docs_required" && <p className="mt-3 text-[12.5px] text-amber-700">{t.request.docsPending}</p>}
        {dec.decision === "declined" && <p className="mt-3 text-[12.5px] text-rose-700">{t.request.declinedNote}</p>}
      </Card>

      {accepted && d.enrollment && (
        <Card className="border-emerald-100 bg-emerald-50/40 p-5">
          <PanelTitle
            icon={<Wallet className="size-4 text-emerald-700" />}
            right={
              <Link href={`/${locale}/finance`} className={buttonVariants({ variant: "outline", size: "sm" })}>
                {t.request.viewDisbursements} <ExternalLink className="size-3.5" />
              </Link>
            }
          >
            {t.request.enrollment}
          </PanelTitle>
          <EnrollmentSummary d={d} />
        </Card>
      )}

      {accepted && !d.enrollment && (dec.approved_amount_sar ?? 0) > 0 && canEnroll && <EnrollForm d={d} onDone={onDone} />}
    </>
  );
}

function EnrollmentSummary({ d }: { d: SupportRequestDetail }) {
  const { t, fmt, label } = useI18n();
  const e = d.enrollment!;
  return (
    <dl className="grid gap-3 sm:grid-cols-4">
      <Field label={t.request.enrollType} value={e.type ? label("enrollmentType", e.type) : "—"} />
      <Field label={t.request.total} value={fmt.money(e.total_approved ?? d.decision?.approved_amount_sar)} mono />
      {e.type === "monthly_recurring" && <Field label={t.request.monthly} value={fmt.money(e.monthly_amount)} mono />}
      <Field label={t.request.period} value={`${fmt.date(e.start_date)} → ${fmt.date(e.end_date)}`} />
    </dl>
  );
}

function EnrollForm({ d, onDone }: { d: SupportRequestDetail; onDone: () => void }) {
  const { t, fmt, format, label } = useI18n();
  const ids = { type: useId(), months: useId(), start: useId() };
  const [type, setType] = useState<"one_time" | "monthly_recurring">("one_time");
  const [months, setMonths] = useState("6");
  const [start, setStart] = useState(() => new Date().toISOString().slice(0, 10));
  const { busy, run } = useAction(onDone);
  const n = type === "monthly_recurring" ? Math.max(1, Math.min(36, Number(months) || 1)) : 1;
  const amount = d.decision?.approved_amount_sar ?? 0;
  return (
    <Card className="p-5">
      <PanelTitle icon={<Wallet className="size-4 text-brand-600" />}>{t.request.enrollTitle}</PanelTitle>
      <p className="mb-4 text-[12.5px] text-ink-muted">{t.request.enrollHint}</p>
      <form
        className="grid gap-3 sm:grid-cols-3"
        onSubmit={(e) => {
          e.preventDefault();
          void run(
            "enroll",
            () =>
              api.post("/enrollments", {
                support_request_id: d.id,
                type,
                months: n,
                start_date: start || undefined,
              }),
            format(t.request.enrolled, { n: fmt.plural(t.finance.paymentsCount, n) }),
          );
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor={ids.type} className="text-[12px] font-normal text-ink-muted">
            {t.request.enrollType}
          </Label>
          <Select value={type} onValueChange={(v) => setType(v as typeof type)}>
            <SelectTrigger id={ids.type} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent position="popper">
              <SelectItem value="one_time">{label("enrollmentType", "one_time")}</SelectItem>
              <SelectItem value="monthly_recurring">{label("enrollmentType", "monthly_recurring")}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {type === "monthly_recurring" && (
          <div className="space-y-1.5">
            <Label htmlFor={ids.months} className="text-[12px] font-normal text-ink-muted">
              {t.request.months}
            </Label>
            <Input id={ids.months} type="number" min={1} max={36} dir="ltr" value={months} onChange={(e) => setMonths(e.target.value)} />
          </div>
        )}
        <div className="space-y-1.5">
          <Label htmlFor={ids.start} className="text-[12px] font-normal text-ink-muted">
            {t.request.startDate}
          </Label>
          <Input id={ids.start} type="date" dir="ltr" value={start} onChange={(e) => setStart(e.target.value)} />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 sm:col-span-3">
          <p className="text-[12.5px] text-ink-muted">
            {t.request.total}: <span className="font-semibold text-ink tabular">{fmt.money(amount)}</span>
            {type === "monthly_recurring" && (
              <>
                {" · "}
                {t.request.monthly}: <span className="font-semibold text-ink tabular">{fmt.money(amount / n)}</span>
              </>
            )}
          </p>
          <Button type="submit" disabled={!!busy}>
            {busy && <LoaderCircle className="animate-spin" />}
            {t.request.enroll}
          </Button>
        </div>
      </form>
    </Card>
  );
}
