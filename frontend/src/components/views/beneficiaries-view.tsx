"use client";

import { useMemo } from "react";
import { useState } from "react";
import { ChevronRight, FilePlus2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  DataText,
  Empty,
  LoadError,
  MiniStat,
  NameAvatar,
  PageHead,
  SearchInput,
  StatusBadge,
  TableSkeleton,
} from "@/components/kayan/primitives";
import { CreateFileDialog } from "@/components/details/file-form";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import { useDetailNav } from "@/components/shell/use-detail-nav";
import { useBeneficiaries } from "@/lib/api/hooks";
import { catalog, normalizeArabic } from "@/lib/i18n/catalog";
import { useUrlQuery } from "./use-url-query";

const ALL = "all";
const FILE_STATUSES = Object.keys(catalog.fileStatus);

export function BeneficiariesView() {
  const { t, fmt, label } = useI18n();
  const list = useBeneficiaries();
  const { openBeneficiary } = useDetailNav();
  const canManage = useSession().can("beneficiaries:manage");
  const [creating, setCreating] = useState(false);
  const [q, setQ] = useUrlQuery();
  const [status, setStatus] = useState(ALL);

  const all = useMemo(() => list.data?.results ?? [], [list.data]);
  const rows = useMemo(() => {
    const needle = normalizeArabic(q.toLowerCase());
    return all.filter(
      (x) =>
        (status === ALL || x.status === status) &&
        (!needle || normalizeArabic(`${x.name_ar} ${x.file_no} ${x.mobile ?? ""} ${x.id}`.toLowerCase()).includes(needle)),
    );
  }, [all, q, status]);

  const count = (pred: (s: string) => boolean) => all.filter((x) => pred(x.status)).length;

  return (
    <div className="space-y-4">
      <PageHead
        title={t.beneficiaries.title}
        sub={t.beneficiaries.sub}
        right={
          canManage && (
            <Button onClick={() => setCreating(true)}>
              <FilePlus2 /> {t.file.create}
            </Button>
          )
        }
      />
      <CreateFileDialog open={creating} onOpenChange={setCreating} onCreated={openBeneficiary} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MiniStat label={t.beneficiaries.total} value={fmt.number(all.length)} highlight />
        <MiniStat label={t.beneficiaries.approved} value={fmt.number(count((s) => s === "approved"))} />
        <MiniStat label={t.beneficiaries.inReview} value={fmt.number(count((s) => s === "submitted" || s === "under_review"))} />
        <MiniStat label={t.beneficiaries.draft} value={fmt.number(count((s) => s === "draft"))} />
      </div>
      <Card>
        <div className="flex flex-wrap gap-2.5 border-b border-line p-4">
          <SearchInput
            className="min-w-[200px] flex-1"
            placeholder={t.beneficiaries.searchPlaceholder}
            aria-label={t.beneficiaries.searchPlaceholder}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="min-w-40" aria-label={t.common.allStatuses}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent position="popper" align="end">
              <SelectItem value={ALL}>{t.common.allStatuses}</SelectItem>
              {FILE_STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  {label("fileStatus", s)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {list.error && !list.data ? (
          <LoadError onRetry={() => list.mutate()} />
        ) : list.isLoading ? (
          <TableSkeleton />
        ) : rows.length === 0 ? (
          <Empty title={t.beneficiaries.empty} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t.beneficiaries.cols.fileNo}</TableHead>
                <TableHead>{t.beneficiaries.cols.beneficiary}</TableHead>
                <TableHead>{t.beneficiaries.cols.city}</TableHead>
                <TableHead>{t.beneficiaries.cols.type}</TableHead>
                <TableHead>{t.beneficiaries.cols.completion}</TableHead>
                <TableHead>{t.beneficiaries.cols.dependents}</TableHead>
                <TableHead>{t.beneficiaries.cols.status}</TableHead>
                <TableHead>
                  <span className="sr-only">{t.common.viewAll}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((x) => (
                <TableRow
                  key={x.id}
                  tabIndex={0}
                  className="cursor-pointer outline-none hover:bg-line-soft/50 focus-visible:bg-brand-50/50"
                  onClick={() => openBeneficiary(x.id)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      openBeneficiary(x.id);
                    }
                  }}
                >
                  <TableCell className="text-[12px] text-ink-muted tabular">{x.file_no}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2.5">
                      <NameAvatar name={x.name_ar} size={30} />
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">
                          <DataText>{x.name_ar}</DataText>
                        </p>
                        <p className="text-[11.5px] text-ink-soft tabular" dir="ltr">
                          {x.mobile}
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="text-[12.5px] text-ink-muted">{x.city ? label("city", x.city) : "—"}</TableCell>
                  <TableCell>
                    <Badge tone={x.case_type === "CT-FOSTER" ? "violet" : "slate"}>{label("caseType", x.case_type)}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex w-32 items-center gap-2">
                      <Progress value={x.completion_pct} tone={x.completion_pct >= 90 ? "green" : "amber"} />
                      <span className="shrink-0 text-[11.5px] text-ink-muted tabular">{x.completion_pct}%</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-[12.5px] text-ink-muted tabular">{fmt.number(x.dependents)}</TableCell>
                  <TableCell>
                    <StatusBadge kind="fileStatus" code={x.status} />
                  </TableCell>
                  <TableCell>
                    <ChevronRight className="size-4 text-ink-soft rtl:-scale-x-100" />
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
