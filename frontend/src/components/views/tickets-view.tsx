"use client";

import { useMemo, useState } from "react";
import { ChevronRight, House, MessageCircle, Phone } from "lucide-react";
import { Card } from "@/components/ui/card";
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
import { ShowExpiredToggle } from "@/components/kayan/show-expired-toggle";
import { useI18n } from "@/components/providers/i18n-provider";
import { useDetailNav } from "@/components/shell/use-detail-nav";
import { useStats, useTickets } from "@/lib/api/hooks";
import type { TicketStatus } from "@/lib/api/types";
import { normalizeArabic } from "@/lib/i18n/catalog";
import { isTicketExpired } from "@/lib/tickets";
import { useShowExpired } from "@/lib/use-show-expired";
import { cn } from "@/lib/utils";

const ALL = "all";
const STATUSES: TicketStatus[] = ["open", "in_progress", "waiting_customer", "replied", "closed"];
const CHANNEL_ICON = { call: Phone, whatsapp: MessageCircle, portal: House } as const;

export function TicketsView() {
  const { t, fmt, label, personName } = useI18n();
  const tickets = useTickets();
  const stats = useStats();
  const { openTicket } = useDetailNav();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<string>(ALL);
  const [showExpired, setShowExpired] = useShowExpired();
  const s = stats.data;

  const expiredCount = useMemo(() => (tickets.data?.tickets ?? []).filter(isTicketExpired).length, [tickets.data]);
  const rows = useMemo(() => {
    const needle = normalizeArabic(q.toLowerCase());
    return (tickets.data?.tickets ?? []).filter(
      (tk) =>
        (showExpired || !isTicketExpired(tk)) &&
        (status === ALL || tk.status === status) &&
        (!needle || normalizeArabic(`${tk.subject_ar ?? ""} ${tk.customer_name_ar ?? ""} ${tk.id}`.toLowerCase()).includes(needle)),
    );
  }, [tickets.data, q, status, showExpired]);

  return (
    <div className="space-y-4">
      <PageHead title={t.tickets.title} sub={t.tickets.sub} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <MiniStat label={t.common.total} value={fmt.number(s?.total ?? 0)} highlight />
        {(["open", "in_progress", "replied", "closed"] as const).map((k) => (
          <MiniStat key={k} label={label("ticketStatus", k)} value={fmt.number(s?.by_status?.[k] ?? 0)} />
        ))}
      </div>
      <Card>
        <div className="flex flex-wrap gap-2.5 border-b border-line p-4">
          <SearchInput
            className="min-w-[200px] flex-1"
            placeholder={t.tickets.searchPlaceholder}
            aria-label={t.tickets.searchPlaceholder}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="min-w-40" aria-label={t.common.allStatuses}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent position="popper" align="end">
              <SelectItem value={ALL}>{t.common.allStatuses}</SelectItem>
              {STATUSES.map((st) => (
                <SelectItem key={st} value={st}>
                  {label("ticketStatus", st)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <ShowExpiredToggle checked={showExpired} onChange={setShowExpired} count={expiredCount} />
        </div>
        {tickets.error && !tickets.data ? (
          <LoadError onRetry={() => tickets.mutate()} />
        ) : tickets.isLoading ? (
          <TableSkeleton />
        ) : rows.length === 0 ? (
          <Empty title={t.tickets.empty} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t.tickets.cols.id}</TableHead>
                <TableHead>{t.tickets.cols.beneficiary}</TableHead>
                <TableHead>{t.tickets.cols.category}</TableHead>
                <TableHead>{t.tickets.cols.status}</TableHead>
                <TableHead>{t.tickets.cols.channel}</TableHead>
                <TableHead>{t.tickets.cols.remaining}</TableHead>
                <TableHead>{t.tickets.cols.updated}</TableHead>
                <TableHead>
                  <span className="sr-only">{t.common.viewAll}</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((tk) => {
                const sla = fmt.sla(tk.sla);
                const ChannelIcon = CHANNEL_ICON[tk.channel as keyof typeof CHANNEL_ICON] ?? House;
                return (
                  <TableRow
                    key={tk.id}
                    tabIndex={0}
                    className="cursor-pointer outline-none hover:bg-line-soft/50 focus-visible:bg-brand-50/50"
                    onClick={() => openTicket(tk.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        openTicket(tk.id);
                      }
                    }}
                  >
                    <TableCell>
                      <span className="text-[12px] whitespace-nowrap text-ink-muted tabular">{tk.id}</span>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2.5">
                        <NameAvatar name={personName(tk.customer_name_ar)} size={28} />
                        <div className="min-w-0 max-w-[260px]">
                          <p className="truncate font-medium text-ink">
                            <DataText>{personName(tk.customer_name_ar)}</DataText>
                          </p>
                          <p className="truncate text-[11.5px] text-ink-soft">
                            <DataText>{tk.subject_ar}</DataText>
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-[12.5px] text-ink-muted">{label("department", tk.department_id, tk.department_ar)}</TableCell>
                    <TableCell>
                      <StatusBadge kind="ticketStatus" code={tk.status} arabic={tk.status_ar} />
                    </TableCell>
                    <TableCell>
                      <span className="inline-flex items-center gap-1.5 text-[12px] text-ink-muted">
                        <ChannelIcon className="size-3.5" />
                        {label("channelShort", tk.channel)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={cn("text-[12px] tabular", sla.breached ? "font-medium text-rose-600" : "text-ink-muted")}>{sla.text}</span>
                    </TableCell>
                    <TableCell className="text-[12px] text-ink-soft">{fmt.relative(tk.last_update ?? tk.updated_at ?? tk.opened_at)}</TableCell>
                    <TableCell>
                      <ChevronRight className="size-4 text-ink-soft rtl:-scale-x-100" />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </Card>
    </div>
  );
}
