"use client";

import { useState } from "react";
import { Check, Scale } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DataText, Empty, Field, LoadError, NameAvatar, PageHead } from "@/components/kayan/primitives";
import { DecisionDialog, type DecisionTarget, type DecisionType } from "@/components/details/decision-dialog";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import { useDetailNav } from "@/components/shell/use-detail-nav";
import { useCommitteeQueue } from "@/lib/api/hooks";
import type { CommitteeItem } from "@/lib/api/types";
import { cn } from "@/lib/utils";

export function CommitteeView() {
  const { t, fmt, rich, label } = useI18n();
  const queue = useCommitteeQueue();
  const { openBeneficiary, openRequest } = useDetailNav();
  const canDecide = useSession().can("committee:decide");
  const [decision, setDecision] = useState<DecisionTarget | null>(null);
  const rows = queue.data?.queue ?? [];

  const decide = (r: CommitteeItem, type: DecisionType) =>
    setDecision({ requestId: r.support_request_id, name: r.name_ar, requestedAmount: r.requested_amount_sar, type });

  return (
    <div className="space-y-4">
      <PageHead title={t.committee.title} sub={t.committee.sub} />
      <Card className="border-brand-100 bg-brand-50/40 p-4">
        <div className="flex gap-3">
          <Scale className="mt-0.5 size-4 shrink-0 text-brand-700" />
          <p className="text-[12.5px] leading-relaxed text-brand-900">
            {rich(t.committee.note, { needScore: <b>{t.committee.needScore}</b> })}
          </p>
        </div>
      </Card>

      {queue.error && !queue.data ? (
        <Card>
          <LoadError onRetry={() => queue.mutate()} />
        </Card>
      ) : queue.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-60 rounded-xl" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <Card>
          <Empty icon={Scale} title={t.committee.empty} />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {rows.map((r, i) => {
            const score = r.need_score ?? 0;
            return (
              <Card key={r.support_request_id} className="animate-enter p-5" style={{ animationDelay: `${i * 40}ms` }}>
                <div className="mb-3 flex items-start justify-between gap-3">
                  <button
                    type="button"
                    onClick={() => openBeneficiary(r.beneficiary_id)}
                    className="flex min-w-0 cursor-pointer items-center gap-3 text-start"
                  >
                    <NameAvatar name={r.name_ar} size={38} />
                    <div className="min-w-0">
                      <p className="truncate text-[14px] font-medium text-ink hover:text-brand-700">
                        <DataText>{r.name_ar ?? r.beneficiary_id}</DataText>
                      </p>
                      <p className="text-[11.5px] text-ink-soft tabular">{r.support_request_id}</p>
                    </div>
                  </button>
                  <div className="shrink-0 text-end">
                    <p className="text-[10.5px] text-ink-muted capitalize">{t.committee.needScore}</p>
                    <p
                      className={cn(
                        "text-[19px] font-semibold tabular",
                        score > 80 ? "text-rose-600" : score > 60 ? "text-amber-600" : "text-ink",
                      )}
                    >
                      {r.need_score != null ? fmt.decimal(r.need_score) : "—"}
                    </p>
                  </div>
                </div>
                <div className="mb-3 flex flex-wrap gap-1.5">
                  <Badge tone="brand">{label("program", r.program_id, r.program_ar)}</Badge>
                  {(r.request_type_id || r.title_ar) && <Badge tone="slate">{label("requestType", r.request_type_id, r.title_ar)}</Badge>}
                </div>
                <dl className="mb-3 grid grid-cols-3 gap-2 border-b border-line-soft pb-3">
                  <Field label={t.committee.requested} value={fmt.money(r.requested_amount_sar)} mono />
                  <Field label={t.committee.perCapita} value={fmt.money(r.per_capita_monthly_sar)} mono />
                  <Field label={t.committee.household} value={fmt.number(r.household_size)} mono />
                </dl>
                {r.recommendation_ar && (
                  <p className="mb-3 text-[12px] leading-relaxed text-ink-muted">
                    <span className="font-medium text-ink">{t.committee.recommendation} </span>
                    <DataText>{r.recommendation_ar}</DataText>
                  </p>
                )}
                <div className="flex gap-2">
                  {canDecide && (
                    <>
                      <Button size="sm" className="flex-1" onClick={() => decide(r, "accepted")}>
                        <Check className="size-3.5" /> {t.committee.accept}
                      </Button>
                      <Button size="sm" variant="outline" className="flex-1" onClick={() => decide(r, "docs_required")}>
                        {t.committee.docs}
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => decide(r, "declined")}>
                        {t.committee.decline}
                      </Button>
                    </>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => openRequest(r.support_request_id)}>
                    {t.request.viewCase}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <DecisionDialog target={decision} onClose={() => setDecision(null)} />
    </div>
  );
}
