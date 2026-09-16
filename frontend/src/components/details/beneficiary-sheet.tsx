"use client";

import { useState } from "react";
import { FileCheck2, LoaderCircle, MessageCircle, Pencil, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Dialog, DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataText, Empty, Field, LoadError, NameAvatar, Ring, StatusBadge } from "@/components/kayan/primitives";
import { toneFor } from "@/components/kayan/tones";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import { useDetailNav } from "@/components/shell/use-detail-nav";
import { api } from "@/lib/api/client";
import { useBeneficiaryHistory, useRevalidate } from "@/lib/api/hooks";
import { EditFileDialog } from "@/components/details/file-form";
import type { BeneficiaryHistory } from "@/lib/api/types";
import { keyFromArabic } from "@/lib/i18n/catalog";

export function BeneficiarySheet({ id, onClose }: { id: string | null; onClose: () => void }) {
  const { t } = useI18n();
  return (
    <Sheet open={!!id} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="end" className="max-w-3xl overflow-y-auto" closeLabel={t.common.close}>
        {id && <BeneficiaryDetail key={id} id={id} />}
      </SheetContent>
    </Sheet>
  );
}

function BeneficiaryDetail({ id }: { id: string }) {
  const { t, fmt, format, label } = useI18n();
  const { data: d, error, isLoading, mutate } = useBeneficiaryHistory(id);
  const canManage = useSession().can("beneficiaries:manage");
  const [editing, setEditing] = useState(false);

  if (error && !d) {
    return (
      <>
        <SheetHeader>
          <div className="min-w-0">
            <SheetTitle>{t.beneficiary.notFound}</SheetTitle>
            <SheetDescription className="tabular">{id}</SheetDescription>
          </div>
        </SheetHeader>
        <LoadError onRetry={() => mutate()} />
      </>
    );
  }

  if (isLoading || !d) {
    return (
      <div className="space-y-5 p-6">
        <SheetTitle className="sr-only">{id}</SheetTitle>
        <SheetDescription className="sr-only">{id}</SheetDescription>
        <div className="flex items-center gap-4">
          <Skeleton className="size-12 rounded-full" />
          <div className="space-y-2">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-3 w-28" />
          </div>
        </div>
        <Skeleton className="h-24" />
        <Skeleton className="h-64" />
      </div>
    );
  }

  const b = d.beneficiary;
  const c = d.completeness;
  const f = d.financial;
  const missingDocs = c.missing_documents ?? [];
  const missingSections = uniqueSections(c.missing_fields ?? []);
  const needScore = f.need_score ?? 0;

  return (
    <div className="space-y-5 p-6 pt-14 sm:pt-6">
      <div className="flex items-start gap-4 pe-10 pb-1">
        <NameAvatar name={b.name_ar} size={48} />
        <div className="min-w-0 flex-1">
          <SheetTitle className="text-[17px] leading-snug font-bold">
            <DataText>{b.name_ar || "—"}</DataText>
          </SheetTitle>
          <SheetDescription asChild>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              {b.file_no && <span className="font-mono text-[12.5px] text-ink-muted">{b.file_no}</span>}
              {(b.category_ar || b.orphan_category) && (
                <span className="text-[12.5px] text-ink-soft">· {label("orphanCategory", b.orphan_category, b.category_ar)}</span>
              )}
            </div>
          </SheetDescription>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            <StatusBadge kind="fileStatus" code={b.status} />
            {b.city && <span className="text-[11.5px] text-ink-soft">{label("city", b.city)}</span>}
            {canManage && (
              <Button variant="outline" size="sm" className="ms-auto" onClick={() => setEditing(true)}>
                <Pencil className="size-3.5" /> {t.file.edit}
              </Button>
            )}
          </div>
        </div>
      </div>

      <FileReview id={b.id} status={b.status} onDone={() => mutate()} />
      {canManage && <EditFileDialog beneficiary={b} open={editing} onOpenChange={setEditing} onSaved={() => mutate()} />}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-ink-muted">{t.beneficiary.totalPaid}</p>
          <p className="mt-1 text-[22px] font-bold text-ink tabular">{fmt.money(d.payments?.total_sar)}</p>
          <p className="mt-1 text-[11px] text-ink-soft">{format(t.beneficiary.upcoming, { amount: fmt.money(d.disbursements?.upcoming_sar) })}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-ink-muted">{t.beneficiary.needScore}</p>
          <p className="mt-1 text-[22px] font-bold text-ink tabular">{f.need_score != null ? fmt.decimal(f.need_score) : "—"}</p>
          <Progress value={needScore} tone={needScore > 70 ? "rose" : "amber"} className="mt-2" />
        </Card>
        <Card className="flex items-center justify-between p-4">
          <div>
            <p className="text-[11.5px] font-medium text-ink-muted">{t.beneficiary.completion}</p>
            <p className="mt-1 text-[13px] text-ink-soft tabular">{Math.round(c.pct ?? 0)}%</p>
          </div>
          <Ring value={c.pct ?? 0} size={56} stroke={5} />
        </Card>
      </div>

      {(missingDocs.length > 0 || missingSections.length > 0) && (
        <Card className="border-amber-200 bg-amber-50/60 p-4">
          <div className="flex gap-3">
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-amber-600" />
            <div className="min-w-0 space-y-2.5">
              <p className="text-[13px] font-semibold text-amber-900">{t.beneficiary.needsCompletion}</p>
              {missingDocs.length > 0 && (
                <div>
                  <p className="mb-1.5 text-[11.5px] font-medium text-amber-700">{t.beneficiary.missingDocs}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {missingDocs.map((doc, i) => (
                      <span
                        key={doc.document_type_id ?? i}
                        className="inline-flex items-center gap-1 rounded-md bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800"
                      >
                        <TriangleAlert className="size-3 opacity-60" />
                        {label("documentType", doc.document_type_id, doc.name_ar)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {missingSections.length > 0 && (
                <div>
                  <p className="mb-1.5 text-[11.5px] font-medium text-amber-700">{t.beneficiary.missingSections}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {missingSections.map((s) => (
                      <span key={s.key} className="inline-flex items-center rounded-md bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800">
                        {label("formSection", s.id, s.ar)}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">{t.beneficiary.tabs.overview}</TabsTrigger>
          <TabsTrigger value="household">
            {t.beneficiary.tabs.household}
            <Count n={d.household?.size} />
          </TabsTrigger>
          <TabsTrigger value="requests">
            {t.beneficiary.tabs.requests}
            <Count n={d.support_requests?.length} />
          </TabsTrigger>
          <TabsTrigger value="money">
            {t.beneficiary.tabs.money}
            <Count n={d.disbursements?.count} />
          </TabsTrigger>
          <TabsTrigger value="activity">{t.beneficiary.tabs.activity}</TabsTrigger>
        </TabsList>

        <TabsContent value="overview">
          <Overview d={d} />
        </TabsContent>
        <TabsContent value="household">
          <Household d={d} />
        </TabsContent>
        <TabsContent value="requests">
          <Requests d={d} />
        </TabsContent>
        <TabsContent value="money">
          <Money d={d} />
        </TabsContent>
        <TabsContent value="activity">
          <Activity d={d} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/** Staff approval of a submitted file — the gate before any support request can be raised. */
function FileReview({ id, status, onDone }: { id: string; status: string; onDone: () => void }) {
  const { t } = useI18n();
  const canReview = useSession().can("beneficiaries:review");
  const revalidate = useRevalidate();
  const [busy, setBusy] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reason, setReason] = useState("");

  const review = async (decision: "approved" | "rejected", note?: string) => {
    setBusy(true);
    try {
      await api.post(`/beneficiary/${encodeURIComponent(id)}/review`, { decision, note_ar: note || null });
      toast.success(decision === "approved" ? t.review.approved : t.review.rejected);
      setRejectOpen(false);
      onDone();
      void revalidate("/beneficiaries", "/reports", "/beneficiary/");
    } catch {
      toast.error(t.review.failed);
    } finally {
      setBusy(false);
    }
  };

  if (status === "approved") return null;
  if (!canReview && (status === "submitted" || status === "under_review")) {
    return (
      <div className="rounded-xl border border-sky-200 bg-sky-50/50 px-4 py-3 text-[12.5px] text-ink-muted">
        {t.review.submittedHint}
      </div>
    );
  }
  if (status === "draft" || status === "rejected") {
    return (
      <div
        className={
          status === "draft"
            ? "rounded-xl border border-line bg-line-soft/50 px-4 py-3 text-[12.5px] text-ink-muted"
            : "rounded-xl border border-rose-200 bg-rose-50/60 px-4 py-3 text-[12.5px] text-rose-800"
        }
      >
        {status === "draft" ? t.review.draftHint : t.review.rejectedHint}
      </div>
    );
  }
  return (
    <Card className="border-sky-200 bg-sky-50/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <FileCheck2 className="mt-0.5 size-4 shrink-0 text-sky-700" />
          <div className="min-w-0">
            <p className="text-[13px] font-semibold text-ink">{t.review.title}</p>
            <p className="mt-0.5 text-[12.5px] text-ink-muted">{t.review.submittedHint}</p>
          </div>
        </div>
        <div className="flex gap-2">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button size="sm" disabled={busy}>
                {busy && <LoaderCircle className="animate-spin" />}
                {t.review.approve}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t.review.approveTitle}</AlertDialogTitle>
                <AlertDialogDescription>{t.review.approveBody}</AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t.common.cancel}</AlertDialogCancel>
                <AlertDialogAction onClick={() => void review("approved")}>{t.review.approve}</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button size="sm" variant="danger" disabled={busy} onClick={() => setRejectOpen(true)}>
            {t.review.reject}
          </Button>
        </div>
      </div>
      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent closeLabel={t.common.close} aria-describedby={undefined}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (reason.trim()) void review("rejected", reason.trim());
            }}
          >
            <DialogHeader>
              <DialogTitle>{t.review.rejectTitle}</DialogTitle>
            </DialogHeader>
            <DialogBody className="space-y-2">
              <Label htmlFor={`reject-${id}`} className="text-[13px] font-normal text-ink-muted">
                {t.review.rejectReason}
              </Label>
              <Textarea id={`reject-${id}`} dir="auto" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
            </DialogBody>
            <DialogFooter>
              <Button variant="outline" onClick={() => setRejectOpen(false)} disabled={busy}>
                {t.common.cancel}
              </Button>
              <Button type="submit" variant="danger" disabled={busy || !reason.trim()}>
                {busy && <LoaderCircle className="animate-spin" />}
                {t.review.reject}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function Count({ n }: { n?: number | null }) {
  if (n == null) return null;
  return <span className="text-[11px] text-ink-soft tabular">{n}</span>;
}

function uniqueSections(fields: BeneficiaryHistory["completeness"]["missing_fields"]) {
  const seen = new Map<string, { key: string; id?: string; ar?: string }>();
  for (const f of fields) {
    const id = f.section_id ?? keyFromArabic("formSection", f.section_ar);
    const key = id ?? f.section_ar ?? "";
    if (key && !seen.has(key)) seen.set(key, { key, id, ar: f.section_ar });
  }
  return [...seen.values()];
}

function Overview({ d }: { d: BeneficiaryHistory }) {
  const { t, fmt, label } = useI18n();
  const b = d.beneficiary;
  const f = d.financial;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Card className="p-5">
        <p className="mb-4 flex items-center gap-2 text-[13px] font-semibold text-ink">
          <span className="size-1.5 rounded-full bg-brand-500" />
          {t.beneficiary.basicInfo}
        </p>
        <dl className="space-y-3">
          <Field label={t.beneficiary.fileNo} value={b.file_no} mono />
          <Field label={t.beneficiary.fileType} value={label("caseType", b.case_type)} />
          <Field label={t.beneficiary.category} value={label("orphanCategory", b.orphan_category, b.category_ar)} />
          <Field label={t.beneficiary.city} value={b.city ? label("city", b.city) : "—"} />
          <Field label={t.beneficiary.registeredAt} value={fmt.date(b.created_at)} />
          <Field label={t.beneficiary.approvedAt} value={fmt.date(b.approved_at)} />
        </dl>
      </Card>
      <Card className="p-5">
        <p className="mb-4 flex items-center gap-2 text-[13px] font-semibold text-ink">
          <span className="size-1.5 rounded-full bg-emerald-500" />
          {t.beneficiary.financial}
        </p>
        <dl className="space-y-3">
          <Field label={t.beneficiary.monthlyIncome} value={fmt.money(f.monthly_income_sar)} mono />
          <Field label={t.beneficiary.obligations} value={fmt.money(f.total_obligations_sar)} mono />
          <Field label={t.beneficiary.livingCosts} value={fmt.money(f.total_person_costs_sar)} mono />
          <Field label={t.beneficiary.perCapita} value={fmt.money(f.per_capita_monthly_sar)} mono />
        </dl>
      </Card>
    </div>
  );
}

function Household({ d }: { d: BeneficiaryHistory }) {
  const { t, fmt, format, label } = useI18n();
  const rows = d.household?.dependents ?? [];
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{t.beneficiary.householdTitle}</CardTitle>
          <CardDescription>{format(t.beneficiary.householdSub, { n: d.household?.size ?? 0 })}</CardDescription>
        </div>
      </CardHeader>
      {rows.length === 0 ? (
        <Empty title={t.beneficiary.noDependents} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t.beneficiary.householdCols.name}</TableHead>
              <TableHead>{t.beneficiary.householdCols.relationship}</TableHead>
              <TableHead>{t.beneficiary.householdCols.birthDate}</TableHead>
              <TableHead>{t.beneficiary.householdCols.education}</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((x) => (
              <TableRow key={x.id}>
                <TableCell>
                  <div className="flex items-center gap-2.5">
                    <NameAvatar name={x.name_ar} size={28} />
                    <DataText className="font-medium text-ink">{x.name_ar}</DataText>
                  </div>
                </TableCell>
                <TableCell className="text-[12.5px] text-ink-muted">{x.relationship ? label("relationship", x.relationship) : "—"}</TableCell>
                <TableCell className="text-[12.5px] text-ink-muted tabular">{fmt.date(x.birth_date)}</TableCell>
                <TableCell className="text-[12.5px] text-ink-muted">{x.education ? label("education", x.education) : "—"}</TableCell>
                <TableCell>{x.special_needs ? <Badge tone="violet">{t.beneficiary.specialNeeds}</Badge> : null}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}

function Requests({ d }: { d: BeneficiaryHistory }) {
  const { t, fmt, label } = useI18n();
  const { openRequest } = useDetailNav();
  const rows = d.support_requests ?? [];
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{t.beneficiary.requestsTitle}</CardTitle>
          <CardDescription>{fmt.plural(t.beneficiary.requestsCount, rows.length)}</CardDescription>
        </div>
      </CardHeader>
      {rows.length === 0 ? (
        <Empty title={t.beneficiary.noRequests} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t.beneficiary.requestCols.program}</TableHead>
              <TableHead>{t.beneficiary.requestCols.request}</TableHead>
              <TableHead>{t.beneficiary.requestCols.stage}</TableHead>
              <TableHead>{t.beneficiary.requestCols.requested}</TableHead>
              <TableHead>{t.beneficiary.requestCols.decision}</TableHead>
              <TableHead>{t.beneficiary.requestCols.approved}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((x) => {
              const decision = x.decision ?? keyFromArabic("decision", x.decision_ar);
              return (
                <TableRow
                  key={x.id}
                  tabIndex={0}
                  className="cursor-pointer outline-none hover:bg-line-soft/50 focus-visible:bg-brand-50/50"
                  onClick={() => openRequest(x.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      openRequest(x.id);
                    }
                  }}
                >
                  <TableCell>
                    <Badge tone="brand">{label("program", x.program_id, x.program_ar)}</Badge>
                  </TableCell>
                  <TableCell className="text-[12.5px] text-ink">
                    {x.request_type_id || x.title_ar ? label("requestType", x.request_type_id, x.title_ar) : t.beneficiary.untitledRequest}
                  </TableCell>
                  <TableCell>
                    <StatusBadge kind="stage" code={x.stage} />
                  </TableCell>
                  <TableCell className="text-[12.5px] tabular">{fmt.money(x.requested_amount_sar)}</TableCell>
                  <TableCell>
                    {decision || x.decision_ar ? (
                      <StatusBadge kind="decision" code={decision} arabic={x.decision_ar} tone={toneFor(decision)} dot={false} />
                    ) : (
                      <span className="text-[12px] text-ink-soft">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-[12.5px] font-medium tabular">
                    {x.approved_amount_sar ? fmt.money(x.approved_amount_sar) : "—"}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </Card>
  );
}

function Money({ d }: { d: BeneficiaryHistory }) {
  const { t, fmt, label } = useI18n();
  const rows = d.disbursements?.rows ?? [];
  const programOf = (enrollmentId: string | null, programId?: string | null) => {
    if (programId) return label("program", programId);
    const e = d.enrollments?.find((x) => x.id === enrollmentId);
    return e ? label("program", e.program_id, e.program_ar) : "—";
  };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-ink-muted">{t.beneficiary.paid}</p>
          <p className="mt-1 text-[19px] font-bold text-emerald-600 tabular">{fmt.money(d.disbursements?.paid_sar)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-ink-muted">{t.beneficiary.upcomingLabel}</p>
          <p className="mt-1 text-[19px] font-bold text-ink tabular">{fmt.money(d.disbursements?.upcoming_sar)}</p>
        </Card>
        <Card className="p-4">
          <p className="text-[11.5px] font-medium text-ink-muted">{t.beneficiary.paymentsCount}</p>
          <p className="mt-1 text-[19px] font-bold text-ink tabular">{fmt.number(d.disbursements?.count ?? 0)}</p>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{t.beneficiary.scheduleTitle}</CardTitle>
        </CardHeader>
        {rows.length === 0 ? (
          <Empty title={t.beneficiary.noDisbursements} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t.beneficiary.scheduleCols.due}</TableHead>
                <TableHead>{t.beneficiary.scheduleCols.program}</TableHead>
                <TableHead>{t.beneficiary.scheduleCols.amount}</TableHead>
                <TableHead>{t.beneficiary.scheduleCols.status}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((x) => (
                <TableRow key={x.id}>
                  <TableCell className="text-[12.5px] tabular">{fmt.date(x.due_date)}</TableCell>
                  <TableCell className="text-[12.5px] text-ink-muted">{programOf(x.enrollment_id, x.program_id)}</TableCell>
                  <TableCell className="text-[12.5px] font-medium tabular">{fmt.money(x.amount)}</TableCell>
                  <TableCell>
                    <StatusBadge kind="disbursementStatus" code={x.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}

function Activity({ d }: { d: BeneficiaryHistory }) {
  const { t, fmt, format, label } = useI18n();
  const { openTicket } = useDetailNav();
  const tickets = d.tickets ?? [];
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>{t.beneficiary.activityTitle}</CardTitle>
          <CardDescription>
            {format(t.beneficiary.activitySub, {
              tickets: tickets.length,
              calls: d.channel_sessions?.calls ?? 0,
              whatsapp: d.channel_sessions?.whatsapp ?? 0,
            })}
          </CardDescription>
        </div>
      </CardHeader>
      <div className="px-5 pb-5">
        {tickets.length === 0 ? (
          <Empty icon={MessageCircle} title={t.beneficiary.noActivity} />
        ) : (
          <ol className="relative ms-2 border-s-2 border-line-soft">
            {tickets.map((tk) => {
              const status = tk.status ?? keyFromArabic("ticketStatus", tk.status_ar);
              return (
                <li key={tk.id} className="relative ms-5 pb-4">
                  <span className="absolute -start-[26px] top-1 size-2.5 rounded-full bg-brand-400 ring-4 ring-white" />
                  <button
                    type="button"
                    onClick={() => openTicket(tk.id)}
                    className="flex cursor-pointer flex-wrap items-center gap-2 text-start hover:text-brand-700"
                  >
                    <DataText className="text-[13px] font-medium text-ink">{tk.subject_ar || tk.id}</DataText>
                    <StatusBadge kind="ticketStatus" code={status} arabic={tk.status_ar} dot={false} />
                  </button>
                  <p className="mt-0.5 text-[11.5px] text-ink-soft">
                    {label("channel", tk.channel)} · {fmt.date(tk.opened_at)}
                  </p>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </Card>
  );
}
