"use client";

import { useMemo, useState } from "react";
import { Check, Clock, Gift, LoaderCircle, Users, Wallet } from "lucide-react";
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
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DataText, Empty, LoadError, PageHead, Stat, StatusBadge, TableSkeleton } from "@/components/kayan/primitives";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import { useDetailNav } from "@/components/shell/use-detail-nav";
import { api } from "@/lib/api/client";
import { useBeneficiaries, useDisbursementRun, useOverview, usePrograms, useRevalidate, useSponsorships } from "@/lib/api/hooks";
import type { Disbursement } from "@/lib/api/types";
import { keyFromArabic } from "@/lib/i18n/catalog";

type PendingAction = { kind: "approve" | "pay"; row: Disbursement };

export function FinanceView() {
  const { t, fmt, format, label } = useI18n();
  const run = useDisbursementRun(60);
  const overview = useOverview();
  const sponsorships = useSponsorships();
  const beneficiaries = useBeneficiaries();
  const programs = usePrograms();
  const revalidate = useRevalidate();
  const { openBeneficiary } = useDetailNav();
  const canPay = useSession().can("finance:manage");
  const [pending, setPending] = useState<PendingAction | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const d = run.data;
  const o = overview.data;
  const names = useMemo(
    () => new Map((beneficiaries.data?.results ?? []).map((b) => [b.id, b.name_ar])),
    [beneficiaries.data],
  );
  const byProgram = Object.entries(d?.by_program_ar ?? {}).map(([arabic, amount]) => {
    const id = programs.data?.programs.find((p) => p.name_ar === arabic)?.id ?? keyFromArabic("program", arabic);
    return { key: id ?? arabic, name: label("program", id, arabic), amount };
  });

  const execute = async ({ kind, row }: PendingAction) => {
    setBusyId(row.id);
    try {
      if (kind === "approve") {
        await api.post(`/disbursements/${encodeURIComponent(row.id)}/approve`, { approved_by: "STF-06" });
        toast.success(t.finance.approvedToast);
      } else {
        await api.post(`/disbursements/${encodeURIComponent(row.id)}/pay`);
        toast.success(t.finance.paidToast);
      }
      void revalidate("/finance", "/reports", "/beneficiary/");
    } catch {
      toast.error(kind === "approve" ? t.finance.approveFailed : t.finance.payFailed);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-4">
      <PageHead title={t.finance.title} sub={t.finance.sub} />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label={t.finance.totalPaid} value={fmt.money(o?.payments_total_sar ?? 0)} icon={Wallet} tone="green" loading={overview.isLoading} />
        <Stat
          label={t.finance.dueIn60}
          value={fmt.money(d?.total_sar ?? 0)}
          icon={Clock}
          tone="amber"
          loading={run.isLoading}
          hint={fmt.plural(t.finance.paymentsCount, d?.count ?? 0)}
        />
        <Stat
          label={t.finance.activeSponsorships}
          value={fmt.number(sponsorships.data?.count ?? 0)}
          icon={Gift}
          tone="violet"
          loading={sponsorships.isLoading}
          hint={format(t.finance.monthly, { amount: fmt.money(sponsorships.data?.monthly_total_sar ?? 0) })}
        />
        <Stat
          label={t.finance.approvedFiles}
          value={fmt.number(o?.beneficiaries?.by_status?.approved ?? 0)}
          icon={Users}
          tone="brand"
          loading={overview.isLoading}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <div>
              <CardTitle>{t.finance.dueTitle}</CardTitle>
              <CardDescription>{t.finance.dueSub}</CardDescription>
            </div>
          </CardHeader>
          {run.error && !run.data ? (
            <LoadError onRetry={() => run.mutate()} />
          ) : run.isLoading ? (
            <TableSkeleton rows={5} />
          ) : !d?.disbursements?.length ? (
            <Empty title={t.finance.empty} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t.finance.cols.due}</TableHead>
                  <TableHead>{t.finance.cols.beneficiary}</TableHead>
                  <TableHead>{t.finance.cols.program}</TableHead>
                  <TableHead>{t.finance.cols.amount}</TableHead>
                  <TableHead>{t.finance.cols.status}</TableHead>
                  <TableHead>{t.finance.cols.action}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {d.disbursements.slice(0, 30).map((x) => (
                  <TableRow key={x.id}>
                    <TableCell className="text-[12.5px] tabular">{fmt.date(x.due_date)}</TableCell>
                    <TableCell>
                      <button
                        type="button"
                        onClick={() => openBeneficiary(x.beneficiary_id)}
                        className="cursor-pointer text-start text-[12.5px] text-ink hover:text-brand-700"
                      >
                        {names.get(x.beneficiary_id) ? (
                          <DataText>{names.get(x.beneficiary_id)}</DataText>
                        ) : (
                          <span className="text-[12px] text-ink-muted tabular">{x.beneficiary_id}</span>
                        )}
                      </button>
                    </TableCell>
                    <TableCell className="text-[12.5px] text-ink-muted">{x.program_id ? label("program", x.program_id) : "—"}</TableCell>
                    <TableCell className="text-[12.5px] font-medium tabular">{fmt.money(x.amount)}</TableCell>
                    <TableCell>
                      <StatusBadge kind="disbursementStatus" code={x.status} />
                    </TableCell>
                    <TableCell>
                      {canPay && (x.status === "scheduled" || x.status === "pending" || x.status === "pending_approval") && (
                        <Button size="sm" variant="outline" disabled={busyId === x.id} onClick={() => setPending({ kind: "approve", row: x })}>
                          {busyId === x.id && <LoaderCircle className="animate-spin" />}
                          {t.finance.approve}
                        </Button>
                      )}
                      {canPay && x.status === "approved" && (
                        <Button size="sm" disabled={busyId === x.id} onClick={() => setPending({ kind: "pay", row: x })}>
                          {busyId === x.id && <LoaderCircle className="animate-spin" />}
                          {t.finance.pay}
                        </Button>
                      )}
                      {x.status === "paid" && (
                        <span className="inline-flex items-center gap-1 text-[12px] font-medium text-emerald-600">
                          <Check className="size-3.5" /> {t.finance.paidMark}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t.finance.byProgram}</CardTitle>
          </CardHeader>
          <div className="space-y-3 px-5 pb-5">
            {run.isLoading && <Skeleton className="h-20" />}
            {byProgram.map((p) => (
              <div key={p.key} className="flex items-center justify-between gap-3 rounded-lg border border-line px-3 py-2.5">
                <span className="text-[12.5px] text-ink">{p.name}</span>
                <span className="shrink-0 text-[13px] font-medium text-ink tabular">{fmt.money(p.amount)}</span>
              </div>
            ))}
            {!run.isLoading && byProgram.length === 0 && <p className="py-6 text-center text-[12.5px] text-ink-soft">{t.finance.noProgramData}</p>}
          </div>
        </Card>
      </div>

      <AlertDialog open={!!pending} onOpenChange={(open) => !open && setPending(null)}>
        <AlertDialogContent>
          {pending && (
            <>
              <AlertDialogHeader>
                <AlertDialogTitle>{pending.kind === "approve" ? t.finance.approveTitle : t.finance.payTitle}</AlertDialogTitle>
                <AlertDialogDescription>
                  {format(pending.kind === "approve" ? t.finance.approveBody : t.finance.payBody, { amount: fmt.money(pending.row.amount) })}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t.common.cancel}</AlertDialogCancel>
                <AlertDialogAction onClick={() => void execute(pending)}>
                  {pending.kind === "approve" ? t.finance.approve : t.finance.pay}
                </AlertDialogAction>
              </AlertDialogFooter>
            </>
          )}
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
