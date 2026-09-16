"use client";

import { useMemo, useState } from "react";
import { Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DataText, Empty, LoadError, PageHead, SearchInput, StatusBadge, TableSkeleton } from "@/components/kayan/primitives";
import { DecisionDialog, type DecisionTarget, type DecisionType } from "@/components/details/decision-dialog";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import { useDetailNav } from "@/components/shell/use-detail-nav";
import { usePrograms, useSupportRequests } from "@/lib/api/hooks";
import type { SupportRequest } from "@/lib/api/types";
import { normalizeArabic, resolveLabel } from "@/lib/i18n/catalog";
import { cn } from "@/lib/utils";
import { useUrlQuery } from "./use-url-query";

export function RequestsView() {
  const { t, fmt, label, locale } = useI18n();
  const requests = useSupportRequests();
  const programs = usePrograms();
  const { openBeneficiary, openRequest } = useDetailNav();
  const canDecide = useSession().can("committee:decide");
  const [program, setProgram] = useState("");
  const [q, setQ] = useUrlQuery();
  const [decision, setDecision] = useState<DecisionTarget | null>(null);

  const all = useMemo(() => requests.data?.requests ?? [], [requests.data]);
  const rows = useMemo(() => {
    const needle = normalizeArabic(q.toLowerCase());
    return all.filter((r) => {
      if (program && r.program_id !== program) return false;
      if (!needle) return true;
      const typeLabel = resolveLabel(locale, "requestType", r.request_type_id, r.title_ar) ?? "";
      return normalizeArabic(`${r.id} ${r.name_ar ?? ""} ${r.title_ar ?? ""} ${typeLabel}`.toLowerCase()).includes(needle);
    });
  }, [all, program, q, locale]);

  const decide = (r: SupportRequest, type: DecisionType) =>
    setDecision({ requestId: r.id, name: r.name_ar, requestedAmount: r.requested_amount_sar, type });

  return (
    <div className="space-y-4">
      <PageHead title={t.requests.title} sub={t.requests.sub} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {programs.isLoading && Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-[92px] rounded-xl" />)}
        {(programs.data?.programs ?? []).map((p) => {
          const n = all.filter((r) => r.program_id === p.id).length;
          const active = program === p.id;
          return (
            <button
              key={p.id}
              type="button"
              aria-pressed={active}
              onClick={() => setProgram(active ? "" : p.id)}
              className={cn(
                "cursor-pointer rounded-xl border bg-white p-4 text-start transition-all outline-none focus-visible:ring-2 focus-visible:ring-brand-300",
                active ? "border-brand-300 shadow-card ring-2 ring-brand-100" : "border-line hover:shadow-card",
              )}
            >
              <p className="text-[13px] font-medium text-ink">{label("program", p.id, p.name_ar)}</p>
              <p className="mt-1 text-[22px] font-semibold text-brand-700 tabular">{fmt.number(n)}</p>
              <p className="text-[11px] text-ink-soft">{fmt.plural(t.requests.requestTypes, p.request_types_count)}</p>
            </button>
          );
        })}
      </div>

      <Card>
        <div className="border-b border-line p-4">
          <SearchInput placeholder={t.requests.searchPlaceholder} aria-label={t.requests.searchPlaceholder} value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {requests.error && !requests.data ? (
          <LoadError onRetry={() => requests.mutate()} />
        ) : requests.isLoading ? (
          <TableSkeleton />
        ) : rows.length === 0 ? (
          <Empty title={t.requests.empty} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t.requests.cols.id}</TableHead>
                <TableHead>{t.requests.cols.beneficiary}</TableHead>
                <TableHead>{t.requests.cols.program}</TableHead>
                <TableHead>{t.requests.cols.type}</TableHead>
                <TableHead>{t.requests.cols.classification}</TableHead>
                <TableHead>{t.requests.cols.stage}</TableHead>
                <TableHead>{t.requests.cols.requested}</TableHead>
                <TableHead>{t.requests.cols.approved}</TableHead>
                <TableHead>{t.requests.cols.action}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.slice(0, 100).map((r) => (
                <TableRow
                  key={r.id}
                  tabIndex={0}
                  className="cursor-pointer outline-none hover:bg-line-soft/50 focus-visible:bg-brand-50/50"
                  onClick={() => openRequest(r.id)}
                  onKeyDown={(e) => {
                    if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
                      e.preventDefault();
                      openRequest(r.id);
                    }
                  }}
                >
                  <TableCell className="text-[12px] whitespace-nowrap text-ink-muted tabular">{r.id}</TableCell>
                  <TableCell>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        openBeneficiary(r.beneficiary_id);
                      }}
                      className="cursor-pointer text-start text-[12.5px] font-medium text-ink hover:text-brand-700"
                    >
                      <DataText>{r.name_ar ?? r.beneficiary_id}</DataText>
                    </button>
                  </TableCell>
                  <TableCell>
                    <Badge tone="brand">{label("program", r.program_id, r.program_ar)}</Badge>
                  </TableCell>
                  <TableCell className="max-w-[240px] text-[12.5px] text-ink">
                    {r.request_type_id || r.title_ar ? label("requestType", r.request_type_id, r.title_ar) : "—"}
                  </TableCell>
                  <TableCell>
                    {r.internal_classification ? (
                      <Badge tone={r.internal_classification === "عاجل" ? "rose" : "slate"}>
                        {label("classification", r.internal_classification)}
                      </Badge>
                    ) : (
                      <span className="text-[12px] text-ink-soft">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <StatusBadge kind="stage" code={r.stage} />
                  </TableCell>
                  <TableCell className="text-[12.5px] tabular">{fmt.money(r.requested_amount_sar)}</TableCell>
                  <TableCell className="text-[12.5px] font-medium text-emerald-700 tabular">
                    {r.approved_amount_sar ? fmt.money(r.approved_amount_sar) : "—"}
                  </TableCell>
                  <TableCell>
                    {canDecide && r.stage === "committee" && !r.decision && (
                      <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                        <Button size="sm" variant="outline" onClick={() => decide(r, "accepted")}>
                          {t.requests.accept}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => decide(r, "declined")}>
                          {t.requests.decline}
                        </Button>
                      </div>
                    )}
                    {r.stage === "decided" && r.approved_amount_sar ? (
                      <span className="inline-flex items-center gap-1 text-[12px] font-medium text-emerald-600">
                        <Check className="size-3.5" /> {t.requests.approvedMark}
                      </span>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <DecisionDialog target={decision} onClose={() => setDecision(null)} />
    </div>
  );
}
