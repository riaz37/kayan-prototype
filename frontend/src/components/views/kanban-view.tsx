"use client";

import { useMemo, useState, type DragEvent } from "react";
import { Clock } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { DataText, LoadError, NameAvatar, PageHead } from "@/components/kayan/primitives";
import { ShowExpiredToggle } from "@/components/kayan/show-expired-toggle";
import { TONE_DOT, toneFor } from "@/components/kayan/tones";
import { useI18n } from "@/components/providers/i18n-provider";
import { useSession } from "@/components/providers/session-provider";
import { useDetailNav } from "@/components/shell/use-detail-nav";
import { api } from "@/lib/api/client";
import { useDepartments, useKanban, useRevalidate } from "@/lib/api/hooks";
import type { Kanban, TicketStatus } from "@/lib/api/types";
import { isCardExpired } from "@/lib/tickets";
import { useShowExpired } from "@/lib/use-show-expired";
import { cn } from "@/lib/utils";

const ALL = "all";

export function KanbanView() {
  const { t, fmt, format, label, personName } = useI18n();
  const [dept, setDept] = useState(ALL);
  const kanban = useKanban(dept === ALL ? undefined : dept);
  const departments = useDepartments();
  const revalidate = useRevalidate();
  const { openTicket } = useDetailNav();
  const canManage = useSession().can("tickets:manage");
  const [dragId, setDragId] = useState<string | null>(null);
  const [overCol, setOverCol] = useState<TicketStatus | null>(null);

  const [showExpired, setShowExpired] = useShowExpired();

  const allColumns = useMemo(() => kanban.data?.columns ?? [], [kanban.data]);
  const expiredCount = useMemo(
    () => allColumns.reduce((n, c) => n + c.cards.filter(isCardExpired).length, 0),
    [allColumns],
  );
  const columns = useMemo(
    () =>
      allColumns.map((c) => {
        const cards = showExpired ? c.cards : c.cards.filter((card) => !isCardExpired(card));
        return { ...c, cards, hidden: c.cards.length - cards.length };
      }),
    [allColumns, showExpired],
  );

  const onDrop = async (e: DragEvent, target: TicketStatus) => {
    e.preventDefault();
    const id = dragId ?? e.dataTransfer.getData("text/plain");
    setDragId(null);
    setOverCol(null);
    if (!id || !kanban.data) return;
    const from = kanban.data.columns.find((c) => c.cards.some((card) => card.id === id));
    if (!from || from.status === target) return;

    // Optimistic move, rolled back by revalidation if the request fails.
    const optimistic: Kanban = {
      columns: kanban.data.columns.map((c) => {
        if (c.status === from.status) return { ...c, count: c.count - 1, cards: c.cards.filter((card) => card.id !== id) };
        if (c.status === target) {
          const card = from.cards.find((x) => x.id === id)!;
          return { ...c, count: c.count + 1, cards: [card, ...c.cards] };
        }
        return c;
      }),
    };
    try {
      await kanban.mutate(
        async () => {
          await api.patch(`/crm/tickets/${encodeURIComponent(id)}/status`, { status: target });
          return undefined;
        },
        { optimisticData: optimistic, rollbackOnError: true, populateCache: false, revalidate: true },
      );
      toast.success(format(t.kanban.moved, { id, status: label("ticketStatus", target) }));
      void revalidate("/crm/stats", "/crm/tickets", "/beneficiary/");
    } catch {
      toast.error(t.kanban.moveFailed);
    }
  };

  return (
    <div className="space-y-4">
      <PageHead
        title={t.kanban.title}
        sub={t.kanban.sub}
        right={
          <div className="flex flex-wrap items-center gap-2">
            <ShowExpiredToggle checked={showExpired} onChange={setShowExpired} count={expiredCount} />
            <Select value={dept} onValueChange={setDept}>
              <SelectTrigger className="min-w-44" aria-label={t.common.allDepartments}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent position="popper" align="end">
                <SelectItem value={ALL}>{t.common.allDepartments}</SelectItem>
                {(departments.data?.departments ?? []).map((d) => (
                  <SelectItem key={d.id} value={d.id}>
                    {label("department", d.id, d.name_ar)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        }
      />

      {kanban.error && !kanban.data ? (
        <LoadError onRetry={() => kanban.mutate()} />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          {kanban.isLoading &&
            Array.from({ length: 4 }, (_, i) => (
              <div key={i} className="space-y-2.5">
                <Skeleton className="h-6 w-32" />
                <Skeleton className="h-32 rounded-xl" />
                <Skeleton className="h-32 rounded-xl" />
              </div>
            ))}
          {columns.map((col, ci) => (
            <section key={col.status} className="animate-enter" style={{ animationDelay: `${ci * 50}ms` }} aria-label={label("ticketStatus", col.status)}>
              <div className="mb-2.5 flex items-center justify-between px-1">
                <div className="flex items-center gap-2">
                  <span className={cn("size-2 rounded-full", TONE_DOT[toneFor(col.status)])} />
                  <h2 className="text-[13px] font-semibold text-ink">{label("ticketStatus", col.status, col.title_ar)}</h2>
                </div>
                <span className="rounded-md bg-line-soft px-1.5 py-0.5 text-[11.5px] text-ink-muted tabular">{col.cards.length}</span>
              </div>
              <div
                className={cn(
                  "min-h-[120px] space-y-2.5 rounded-xl p-1 transition-colors",
                  dragId && "bg-brand-50/40",
                  overCol === col.status && "bg-brand-50 ring-2 ring-brand-200 ring-inset",
                )}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "move";
                  if (overCol !== col.status) setOverCol(col.status);
                }}
                onDragLeave={() => setOverCol((c) => (c === col.status ? null : c))}
                onDrop={(e) => onDrop(e, col.status)}
              >
                {col.cards.map((c) => {
                  const sla = fmt.sla(c.sla_remaining_ar);
                  return (
                    <button
                      key={c.id}
                      type="button"
                      draggable={canManage}
                      onDragStart={(e) => {
                        setDragId(c.id);
                        e.dataTransfer.effectAllowed = "move";
                        e.dataTransfer.setData("text/plain", c.id);
                      }}
                      onDragEnd={() => {
                        setDragId(null);
                        setOverCol(null);
                      }}
                      onClick={() => openTicket(c.id)}
                      className={cn(
                        "group w-full cursor-pointer rounded-xl border bg-white p-3.5 text-start shadow-card transition-all outline-none focus-visible:ring-2 focus-visible:ring-brand-300",
                        dragId === c.id ? "border-brand-300 opacity-50" : "border-line hover:border-brand-200 hover:shadow-pop",
                      )}
                    >
                      <div className="mb-2 flex items-start justify-between gap-2">
                        <span className="text-[11px] text-ink-soft tabular">{c.id}</span>
                        {c.priority === "high" && <Badge tone="rose">{label("priority", "high")}</Badge>}
                      </div>
                      <p className="mb-2 text-[13px] leading-snug font-medium text-ink transition-colors group-hover:text-brand-700">
                        <DataText>{c.subject_ar}</DataText>
                      </p>
                      <div className="mb-2.5 flex items-center gap-2">
                        <NameAvatar name={personName(c.customer_name_ar)} size={22} />
                        <DataText className="truncate text-[12px] text-ink-muted">{personName(c.customer_name_ar)}</DataText>
                      </div>
                      <div className="flex items-center justify-between gap-2 border-t border-line-soft pt-2">
                        <span className="truncate text-[11px] text-ink-soft">
                          {c.department_id || c.department_ar ? label("department", c.department_id, c.department_ar) : label("channel", c.channel)}
                        </span>
                        <span className={cn("inline-flex shrink-0 items-center gap-1 text-[11px] tabular", sla.breached ? "text-rose-600" : "text-ink-soft")}>
                          <Clock className="size-3" />
                          {sla.text}
                        </span>
                      </div>
                    </button>
                  );
                })}
                {!col.cards.length && (
                  <div className="rounded-xl border border-dashed border-line py-8 text-center text-[12px] text-ink-soft">
                    {col.hidden ? t.common.noActiveTickets : t.kanban.noTickets}
                  </div>
                )}
                {col.hidden > 0 && (
                  <button
                    type="button"
                    onClick={() => setShowExpired(true)}
                    className="w-full cursor-pointer rounded-lg py-1.5 text-center text-[11.5px] text-ink-soft transition-colors hover:bg-line-soft hover:text-ink"
                  >
                    {fmt.plural(t.common.expiredHidden, col.hidden)}
                  </button>
                )}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
